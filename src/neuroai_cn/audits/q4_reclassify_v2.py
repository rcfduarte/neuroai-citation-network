"""Reclassify top-1000 bridge papers using OpenAlex subfields.

Addresses Report-14052026 issues Q4.1 (866/1000 in 'Other') and Q4.7 (LHD
physics contamination).

Method:
    1. Query DuckDB for OpenAlex `primary_topic.{display_name, subfield, field}`
       for the 1000 papers in q4_classified_nodes.
    2. DROP physics contamination (subfield ∈ {"Nuclear and High Energy
       Physics", "Particle accelerators..."}) — Q4.7.
    3. Re-classify the remaining "Other" papers using a manual
       OpenAlex-subfield → expanded-track mapping. Keeps existing regex hits;
       only replaces "Other / cross-domain" entries.

Expanded track set (10 categories, more granular than the original 6):
    Foundational DL/AI
    Bio-plausible AI            (spiking, STDP, neuromorphic hardware)
    Applied ML for brain        (decoding, fMRI, BCI, brain imaging)
    Cognitive neuroscience      (psych, attention, perception, learning)
    Molecular / cellular neuro  (synaptic, channels, plasticity)
    Statistical methods         (Bayesian, regression, MCMC, classical ML)
    Neuroengineering / hardware (EE, signal processing, BMI hardware)
    Medical imaging methods     (radiology, segmentation, registration)
    Bridge manifestos & theory  (predictive coding, free energy, NeuroAI)
    Other (residual; smaller)

Outputs:
    corrections/20260508/q4_classified_nodes_v2.parquet  (drop-in replacement)
    corrections/20260508/q4_reclassify_v2_report.json    (audit log)
"""

from __future__ import annotations

import json
import logging
import sys

import pandas as pd

from .. import config
from ..utils.duckdb import get_connection

logger = logging.getLogger(__name__)

CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"

# Physics subfields to DROP (LHD fusion-physics contamination per Q4.7)
DROP_SUBFIELDS = {
    "Nuclear and High Energy Physics",
    "Particle accelerators and beam dynamics",  # appears as topic display name
    "Plasma physics",
    "Atomic and Molecular Physics, and Optics",
}

# Map OpenAlex subfield -> expanded track
# Multiple subfields can map to the same track; first match wins.
SUBFIELD_TO_TRACK: dict[str, tuple[str, str]] = {
    # Foundational AI
    "Artificial Intelligence": ("Foundational DL/AI", "Artificial Intelligence (general)"),
    "Computer Vision and Pattern Recognition": (
        "Foundational DL/AI",
        "Computer Vision and Pattern Recognition",
    ),
    "Machine Learning": ("Foundational DL/AI", "Machine Learning"),
    "Computational Theory and Mathematics": ("Foundational DL/AI", "Computational Theory"),
    # Neuroscience side
    "Cognitive Neuroscience": ("Cognitive neuroscience", "Cognitive Neuroscience"),
    "Cellular and Molecular Neuroscience": (
        "Molecular / cellular neuro",
        "Cellular and Molecular Neuroscience",
    ),
    "Behavioral Neuroscience": ("Cognitive neuroscience", "Behavioral Neuroscience"),
    "Developmental Neuroscience": ("Molecular / cellular neuro", "Developmental Neuroscience"),
    "Endocrine and Autonomic Systems": (
        "Molecular / cellular neuro",
        "Endocrine / Autonomic Systems",
    ),
    "Sensory Systems": ("Cognitive neuroscience", "Sensory Systems"),
    "Neurology": ("Applied ML for brain", "Neurology"),
    # Statistics / engineering
    "Statistics and Probability": ("Statistical methods", "Classical statistics"),
    "Statistical and Nonlinear Physics": ("Statistical methods", "Stat. + nonlinear physics"),
    "Statistics, Probability and Uncertainty": (
        "Statistical methods",
        "Probability and Uncertainty",
    ),
    # Engineering / hardware
    "Electrical and Electronic Engineering": (
        "Neuroengineering / hardware",
        "Electrical Engineering",
    ),
    "Signal Processing": ("Neuroengineering / hardware", "Signal Processing"),
    "Control and Systems Engineering": ("Neuroengineering / hardware", "Control / Systems"),
    "Hardware and Architecture": ("Neuroengineering / hardware", "Hardware / Architecture"),
    # Medical imaging
    "Radiology, Nuclear Medicine and Imaging": ("Medical imaging methods", "Radiology / Imaging"),
    "Biomedical Engineering": ("Applied ML for brain", "Biomedical Engineering"),
    # Psychology -> Cognitive Neuroscience for our purposes
    "Developmental and Educational Psychology": (
        "Cognitive neuroscience",
        "Developmental psychology",
    ),
    "Experimental and Cognitive Psychology": ("Cognitive neuroscience", "Cognitive psychology"),
    "Social Psychology": ("Cognitive neuroscience", "Social psychology"),
    # Software / data science
    "Software": ("Statistical methods", "Software tooling"),
    "Information Systems": ("Statistical methods", "Information Systems"),
    "Computational Mechanics": ("Statistical methods", "Computational Mechanics"),
    "Computer Networks and Communications": (
        "Neuroengineering / hardware",
        "Networks / Communications",
    ),
    "Theoretical Computer Science": ("Foundational DL/AI", "Theoretical CS"),
    # Linguistics — bridge to NLP / Foundational DL/AI
    "Language and Linguistics": ("Foundational DL/AI", "Language / Linguistics"),
    "Linguistics and Language": ("Foundational DL/AI", "Language / Linguistics"),
    # Mathematics
    "Modeling and Simulation": ("Statistical methods", "Modeling / Simulation"),
    "Numerical Analysis": ("Statistical methods", "Numerical Analysis"),
    "Algebra and Number Theory": ("Statistical methods", "Algebra / Number Theory"),
}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    nodes = pd.read_parquet(CORRECTIONS_DIR / "q4_classified_nodes.parquet")
    logger.info("Loaded %d nodes", len(nodes))

    # 1. Query DuckDB for primary topic info
    work_ids = nodes["work_id"].astype(str).tolist()
    quoted = ",".join("'" + w.replace("'", "''") + "'" for w in work_ids)
    with get_connection(read_only=True) as con:
        con.execute("PRAGMA threads=4")
        con.execute("PRAGMA memory_limit='6GB'")
        topic_df = con.execute(
            f"""
            SELECT
                id AS work_id,
                primary_topic.display_name AS oa_topic_name,
                primary_topic.subfield.display_name AS oa_subfield,
                primary_topic.field.display_name AS oa_field
            FROM works
            WHERE id IN ({quoted})
            """
        ).df()
    logger.info("Retrieved OpenAlex topic info for %d works", len(topic_df))

    merged = nodes.merge(topic_df, on="work_id", how="left")

    # 2. DROP physics contamination
    before = len(merged)
    drop_mask = merged["oa_subfield"].isin(DROP_SUBFIELDS)
    dropped_physics = merged[drop_mask].copy()
    merged = merged[~drop_mask].copy()
    logger.info(
        "Dropped %d papers in physics subfields (LHD contamination); %d remain",
        before - len(merged),
        len(merged),
    )

    # 3. Reclassify "Other / cross-domain" using OpenAlex subfield mapping
    needs_reclass = merged["track"] == "Other / cross-domain"
    logger.info(
        "Reclassifying %d 'Other' papers using OpenAlex subfields", int(needs_reclass.sum())
    )

    def reclassify(row: pd.Series) -> tuple[str, str]:
        if row["track"] != "Other / cross-domain":
            return row["track"], row.get("subfield", "")
        sf = row.get("oa_subfield")
        if sf and sf in SUBFIELD_TO_TRACK:
            return SUBFIELD_TO_TRACK[sf]
        return "Other", row.get("oa_subfield", "") or row.get("oa_topic_name", "") or ""

    new_tracks, new_subfields = zip(
        *[reclassify(r) for _, r in merged.iterrows()],
        strict=True,
    )
    merged["track"] = list(new_tracks)
    merged["subfield"] = list(new_subfields)

    # 4. Re-rank within the cleaned set
    merged = merged.sort_values("B_harmonic", ascending=False).reset_index(drop=True)

    # 5. Write back
    out_cols = [
        "work_id",
        "doi",
        "title",
        "publication_year",
        "B_harmonic",
        "c_neuro",
        "c_ai",
        "bridge_paper_field",
        "cluster",
        "x",
        "y",
        "era",
        "paper_type",
        "track",
        "subfield",
        "oa_subfield",
        "oa_field",
        "oa_topic_name",
    ]
    out_df = merged[out_cols]
    out_path = CORRECTIONS_DIR / "q4_classified_nodes_v2.parquet"
    out_df.to_parquet(out_path, index=False)
    logger.info("Wrote %s (%d rows)", out_path, len(out_df))

    # 6. Diagnostics
    print("\\n=== NEW TRACK DISTRIBUTION ===")
    print(out_df["track"].value_counts().to_string())
    print("\\n=== TOP-15 SUBFIELDS within 'Other' bucket (residual after mapping) ===")
    residual = out_df[out_df["track"] == "Other"]
    print(residual["oa_subfield"].value_counts().head(15).to_string())

    audit = dict(
        date="2026-05-22",
        n_in=len(nodes),
        n_dropped_physics=len(dropped_physics),
        n_out=len(out_df),
        track_distribution=out_df["track"].value_counts().to_dict(),
        dropped_titles=dropped_physics["title"].tolist()[:25],
    )
    (CORRECTIONS_DIR / "q4_reclassify_v2_report.json").write_text(json.dumps(audit, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

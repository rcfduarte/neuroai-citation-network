"""Map each of the top-1000 classified bridge papers to its dominant institution.

For Figure 3 panel C (institution-affiliation community structure):
each paper gets ONE label = the institution most-represented in its
authorships that is also in the top-15 (or "Other" if none).

Uses the consolidated top-15 institution list so Alphabet (Google+DeepMind)
is treated as a single label.

Output:
    corrections/20260508/top1000_paper_institutions.parquet
        work_id, dominant_inst_id, dominant_inst_name, dominant_inst_type, has_top15
"""

from __future__ import annotations

import logging
import sys

import pandas as pd

from .. import config
from ..utils.duckdb import get_connection

logger = logging.getLogger(__name__)

CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"

# Parent groups for the Alphabet / Microsoft / Meta consolidation
PARENT_GROUPS = {
    "ALPHABET_GROUP": dict(
        label="Alphabet (Google + DeepMind)",
        country_code="US",
        inst_type="company",
        children_patterns=(r"^Google", r"DeepMind", r"^Alphabet"),
    ),
    "MICROSOFT_GROUP": dict(
        label="Microsoft",
        country_code="US",
        inst_type="company",
        children_patterns=(r"^Microsoft",),
    ),
    "META_GROUP": dict(
        label="Meta (Facebook)",
        country_code="US",
        inst_type="company",
        children_patterns=(r"^Meta", r"^Facebook"),
    ),
}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    nodes = pd.read_parquet(CORRECTIONS_DIR / "q4_classified_nodes.parquet")
    work_ids = nodes["work_id"].astype(str).tolist()
    logger.info("Top-1000 nodes: %d", len(work_ids))

    top_i_consolidated = pd.read_parquet(
        CORRECTIONS_DIR / "author_inst_top_institutions_consolidated.parquet"
    )
    top15 = top_i_consolidated.head(15).copy()
    top15_inst_names = set(top15["inst_name"].astype(str))
    logger.info("Top-15 consolidated institutions: %s", sorted(top15_inst_names))

    # Build parent inst-id mapping from the OpenAlex top-100 (raw) table
    top_i_raw = pd.read_parquet(CORRECTIONS_DIR / "author_inst_top_institutions.parquet")
    parent_lookup: dict[str, str] = {}  # raw inst_id -> parent canonical id
    for pid, spec in PARENT_GROUPS.items():
        for pat in spec["children_patterns"]:
            mask = top_i_raw["inst_name"].str.contains(pat, regex=True, na=False)
            for _, row in top_i_raw.loc[mask].iterrows():
                parent_lookup[str(row["inst_id"])] = pid

    # Add direct top-15 inst_ids (non-consolidated): they map to themselves
    for _, row in top15.iterrows():
        iid = str(row["inst_id"])
        if iid.startswith("https://openalex.org"):
            parent_lookup.setdefault(iid, iid)

    logger.info("Parent lookup entries: %d", len(parent_lookup))

    # Build canonical id -> display name + type
    canonical_meta: dict[str, dict] = {}
    for _, row in top15.iterrows():
        canonical_meta[str(row["inst_id"])] = dict(
            inst_name=str(row["inst_name"]),
            inst_type=str(row["inst_type"]),
            country_code=str(row.get("country_code", "")),
        )
    for pid, spec in PARENT_GROUPS.items():
        canonical_meta.setdefault(
            pid,
            dict(
                inst_name=spec["label"],
                inst_type=spec["inst_type"],
                country_code=spec["country_code"],
            ),
        )

    # Query authorships for the 1000 papers via DuckDB streaming cursor
    with get_connection(read_only=True) as con:
        con.execute("PRAGMA threads=4")
        con.execute("PRAGMA memory_limit='6GB'")
        con.execute("PRAGMA preserve_insertion_order=false")
        con.execute("CREATE TEMP TABLE _ids (work_id VARCHAR)")
        con.executemany("INSERT INTO _ids VALUES (?)", [(w,) for w in work_ids])
        # Flatten authorships server-side, only keeping institutions
        df = con.execute(
            """
            WITH all_auth AS (
                SELECT w.id AS work_id, unnest(w.authorships) AS auth
                FROM works w
                JOIN _ids b ON w.id = b.work_id
            ),
            insts AS (
                SELECT work_id, unnest(auth.institutions) AS inst
                FROM all_auth
                WHERE auth.institutions IS NOT NULL AND length(auth.institutions) > 0
            )
            SELECT work_id, inst.id AS inst_id, inst.display_name AS inst_name
            FROM insts
            WHERE inst.id IS NOT NULL
            """
        ).df()
    logger.info("Authorship rows retrieved: %d", len(df))

    # Map each work_id to a dominant canonical inst (most frequent top-15 hit;
    # otherwise None / "Other").
    df["canonical_inst"] = df["inst_id"].astype(str).map(parent_lookup)
    df_top15_only = df[df["canonical_inst"].notna()]
    counts = df_top15_only.groupby(["work_id", "canonical_inst"]).size().reset_index(name="n")
    # Per work, pick the canonical inst with highest n; tie-break by alphabetical
    dominant = counts.sort_values(
        ["work_id", "n", "canonical_inst"], ascending=[True, False, True]
    ).drop_duplicates(subset=["work_id"], keep="first")
    logger.info(
        "Papers with at least one top-15 affiliation: %d / %d", len(dominant), len(work_ids)
    )

    # Build the output table
    out = nodes[
        ["work_id", "title", "publication_year", "B_harmonic", "x", "y", "cluster", "track"]
    ].copy()
    out = out.merge(dominant[["work_id", "canonical_inst"]], on="work_id", how="left")
    out["dominant_inst_name"] = out["canonical_inst"].map(
        lambda c: (
            canonical_meta.get(c, {}).get("inst_name", "Other / outside top-15")
            if c is not None
            else "Other / outside top-15"
        )
    )
    out["dominant_inst_type"] = out["canonical_inst"].map(
        lambda c: canonical_meta.get(c, {}).get("inst_type", "other") if c is not None else "other"
    )
    out["has_top15"] = out["canonical_inst"].notna()

    out_path = CORRECTIONS_DIR / "top1000_paper_institutions.parquet"
    out.to_parquet(out_path, index=False)
    logger.info(
        "Wrote %s (%d rows; %d top-15-affiliated, %d other)",
        out_path,
        len(out),
        int(out["has_top15"].sum()),
        int((~out["has_top15"]).sum()),
    )

    # Quick breakdown
    print("\\n=== Top-1000 papers by dominant institution ===")
    print(out["dominant_inst_name"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())

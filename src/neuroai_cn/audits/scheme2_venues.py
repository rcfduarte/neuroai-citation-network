"""Scheme 2 — Venue-whitelist field assignment (per E1 triangulation).

Companion to extended_classifier (Scheme 1, Topics-based) and scheme3_s2fos
(Scheme 3, Semantic Scholar Field of Study). Together these implement the
locked E1 spec: "3-scheme triangulation: Topics + venue whitelist + S2FOS;
report each separately + agreement."

Pool 3 venue lists are described in docs/METHODS.md, section 2.3.
A work is assigned by venue ONLY if its primary_location.source.display_name
matches one of the curated venue patterns; otherwise unassigned.

Venue scheme:
    venue_neuro      — CORE-NEURO journals
    venue_ai         — CORE-AI conferences/journals
    venue_intersection — MIXED venues (Neural Computation, Bio Cybernetics, ...)
    venue_general_high — General high-impact (Science, Nature, PNAS, Cell)
    venue_other      — anything else
    venue_unknown    — primary_location is null

Outputs:
    corrections/20260508/scheme2_venue_assignments.parquet — per-work assignment
    corrections/20260508/scheme2_venue_population.parquet  — per-year per-label counts

Sentinel: _scheme2.done in audits/20260508/.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import traceback

import duckdb

from .. import config
from ..utils.duckdb import get_connection, set_temp_directory

logger = logging.getLogger(__name__)

AUDITS_DIR = config.AUDITS_DIR / "20260508"
CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"
SENTINEL_DONE = AUDITS_DIR / "_scheme2.done"
SENTINEL_FAIL = AUDITS_DIR / "_scheme2.failed"

YEAR_MIN = 1990
YEAR_MAX = 2025

# CORE-NEURO venue list (docs/METHODS.md, section 2.3)
CORE_NEURO = [
    "Neuron",
    "Nature Neuroscience",
    "Journal of Neuroscience",
    "The Journal of Neuroscience",
    "Nature Reviews Neuroscience",
    "Current Opinion in Neurobiology",
    "eLife",  # neuro section dominantly
    "Journal of Computational Neuroscience",
    "Cerebral Cortex",
    "NeuroImage",
    "Brain",
    "Trends in Neurosciences",
    "Annual Review of Neuroscience",
    "Journal of Neurophysiology",
    "The Journal of Physiology",
    "Journal of Neuroscience Methods",
    "eNeuro",
    "Network Neuroscience",
    "Brain Structure & Function",
    "Brain Structure and Function",
    "Hippocampus",
    "Neuroreport",
    "Cell Reports",  # has dominant neuro section
]

# CORE-AI
CORE_AI = [
    "Advances in Neural Information Processing Systems",  # NeurIPS
    "Neural Information Processing Systems",
    "International Conference on Machine Learning",  # ICML
    "International Conference on Learning Representations",  # ICLR
    "Journal of Machine Learning Research",  # JMLR
    "AAAI",
    "Proceedings of the AAAI Conference on Artificial Intelligence",
    "International Joint Conference on Artificial Intelligence",  # IJCAI
    "AISTATS",
    "International Conference on Artificial Intelligence and Statistics",
    "Conference on Learning Theory",  # COLT
    "Transactions on Machine Learning Research",  # TMLR
    "IEEE Conference on Computer Vision and Pattern Recognition",  # CVPR
    "Conference on Computer Vision and Pattern Recognition",
    "IEEE International Conference on Computer Vision",  # ICCV
    "European Conference on Computer Vision",  # ECCV
    "Empirical Methods in Natural Language Processing",  # EMNLP
    "Annual Meeting of the Association for Computational Linguistics",  # ACL
    "Nature Machine Intelligence",
    "Findings of the Association for Computational Linguistics",
    "North American Chapter of the Association for Computational Linguistics",  # NAACL
    "Conference of the European Chapter of the Association for Computational Linguistics",  # EACL
    "AAMAS",
    "International Conference on Intelligent Robots and Systems",  # IROS
    "International Conference on Robotics and Automation",  # ICRA
    "Knowledge Discovery and Data Mining",  # KDD
    "Web Search and Data Mining",  # WSDM
    "Recommender Systems",  # RecSys
    "Uncertainty in Artificial Intelligence",  # UAI
    "Reinforcement Learning Conference",  # RLC
    "International Conference on Automated Planning and Scheduling",  # ICAPS
]

# MIXED / INTERSECTION
MIXED_INTERSECTION = [
    "Neural Computation",
    "Biological Cybernetics",
    "Kybernetik",
    "PLoS Computational Biology",
    "PLOS Computational Biology",
    "Frontiers in Computational Neuroscience",
    "Frontiers in Neuroscience",
    "Frontiers in Neurorobotics",
    "Cognitive Computation",
    "IEEE Transactions on Neural Networks and Learning Systems",
    "Neural Networks",
    "Neurocomputing",
    "Network: Computation in Neural Systems",
    "Psychological Review",
    "Cognition",
    "Cognitive Science",
    "Trends in Cognitive Sciences",
    "Behavioral and Brain Sciences",
    "Computational Brain & Behavior",
    "Computational Brain and Behavior",
    "Synthese",
    "Philosophy of Science",
    "WIREs Cognitive Science",
    "Philosophical Transactions of the Royal Society B Biological Sciences",
    "Phil Trans R Soc B",
    "Interface Focus",
]

GENERAL_HIGH_IMPACT = [
    "Science",
    "Nature",
    "Proceedings of the National Academy of Sciences",  # PNAS
    "Nature Communications",
    "iScience",
    "Communications Biology",
    "Cell",
]


def _venues_to_sql_list(venues: list[str]) -> str:
    return "[" + ",".join("'" + v.replace("'", "''") + "'" for v in venues) + "]"


def build_venue_assignment(con: duckdb.DuckDBPyConnection, table_name: str = "work_venue") -> dict:
    """Build temp table work_venue(work_id, year, venue_label).

    Match against work.primary_location.source.display_name. Match is case-insensitive
    and substring-anchored — use exact match only (no LIKE) to avoid spurious matches.
    """
    neuro_arr = _venues_to_sql_list(CORE_NEURO)
    ai_arr = _venues_to_sql_list(CORE_AI)
    mixed_arr = _venues_to_sql_list(MIXED_INTERSECTION)
    general_arr = _venues_to_sql_list(GENERAL_HIGH_IMPACT)

    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE {table_name} AS
        SELECT
            w.id AS work_id,
            w.publication_year AS year,
            w.primary_location.source.display_name AS venue_name,
            CASE
                WHEN w.primary_location IS NULL OR w.primary_location.source IS NULL
                  THEN 'venue_unknown'
                WHEN w.primary_location.source.display_name IN (SELECT unnest({neuro_arr}))
                  THEN 'venue_neuro'
                WHEN w.primary_location.source.display_name IN (SELECT unnest({ai_arr}))
                  THEN 'venue_ai'
                WHEN w.primary_location.source.display_name IN (SELECT unnest({mixed_arr}))
                  THEN 'venue_intersection'
                WHEN w.primary_location.source.display_name IN (SELECT unnest({general_arr}))
                  THEN 'venue_general_high'
                ELSE 'venue_other'
            END AS venue_label
        FROM works w
        WHERE w.publication_year BETWEEN {YEAR_MIN} AND {YEAR_MAX}
        """
    )
    rows = con.execute(
        f"""
        SELECT venue_label, COUNT(*) FROM {table_name}
        GROUP BY venue_label
        ORDER BY COUNT(*) DESC
        """
    ).fetchall()
    pop = {r[0]: int(r[1]) for r in rows}
    logger.info("Venue assignment: %s", pop)
    return pop


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    CORRECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    for s in (SENTINEL_DONE, SENTINEL_FAIL):
        if s.exists():
            s.unlink()
    t0 = time.time()
    try:
        con = get_connection(read_only=True)
        try:
            con.execute("PRAGMA threads=10")
            con.execute("PRAGMA memory_limit='24GB'")
            set_temp_directory(con)

            pop = build_venue_assignment(con)

            # Persist per-work assignment (without venue_name column to keep file size sane)
            assign_path = CORRECTIONS_DIR / "scheme2_venue_assignments.parquet"
            con.execute(
                f"""
                COPY (
                    SELECT work_id, year, venue_label, venue_name
                    FROM work_venue
                    WHERE venue_label != 'venue_other' AND venue_label != 'venue_unknown'
                ) TO '{assign_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
                """
            )
            logger.info("Wrote venue assignments to %s", assign_path)

            # Per-year per-label population
            pop_path = CORRECTIONS_DIR / "scheme2_venue_population.parquet"
            con.execute(
                f"""
                COPY (
                    SELECT year, venue_label, COUNT(*) AS n
                    FROM work_venue
                    GROUP BY year, venue_label
                    ORDER BY year, venue_label
                ) TO '{pop_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
                """
            )

            summary = {
                "scheme": "venue_whitelist (Pool 3)",
                "venue_lists": {
                    "core_neuro_n": len(CORE_NEURO),
                    "core_ai_n": len(CORE_AI),
                    "mixed_intersection_n": len(MIXED_INTERSECTION),
                    "general_high_n": len(GENERAL_HIGH_IMPACT),
                },
                "population": pop,
                "elapsed_s": round(time.time() - t0, 1),
            }
            with (AUDITS_DIR / "scheme2_venues_summary.json").open("w") as fh:
                json.dump(summary, fh, indent=2)
            logger.info("Summary: %s", summary)
        finally:
            con.close()
        SENTINEL_DONE.write_text(
            f"scheme2: DONE — venue assignments persisted; elapsed {time.time() - t0:.1f}s\n"
        )
        return 0
    except Exception as exc:
        tb = traceback.format_exc()
        SENTINEL_FAIL.write_text(f"scheme2: ERROR — {type(exc).__name__}: {exc}\n\n{tb}\n")
        logger.exception("Scheme 2 errored")
        return 2


if __name__ == "__main__":
    sys.exit(main())

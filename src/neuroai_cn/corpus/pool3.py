"""Pool 3 — Venue whitelist (foundation §1.3 / METHODS §2.3).

Four sub-pools — works whose `primary_location.source.id` is in the curated
list:
  - 'core_neuro'    : neuroscience flagship journals
  - 'core_ai'       : AI/ML flagship venues + conferences
  - 'mixed'         : intersection venues (BBS, Neural Computation, …)
  - 'general_high'  : Science / Nature / PNAS / Cell / eLife / Nat Commun

Each ID was resolved from the live `sources` table (probed 2026-04-29) by
exact display-name match where possible, falling back to high-precision regex.
Venues that didn't surface (Nat Rev Neurosci, Cosyne, RLC, TMLR, EACL,
Bernstein Conference) are listed as TODO and will resolve when more works
arrive in the snapshot.

Output: data/derived/pool3.parquet
    work_id, in_pool=true, source_tag='pool3', sub_pool VARCHAR[]  (one of the four labels)
"""

from __future__ import annotations

import argparse
import logging
import time

import duckdb

from ..utils.duckdb import derived_dir, get_connection

logger = logging.getLogger(__name__)

# CORE-NEURO — flagship neuroscience journals.
CORE_NEURO: dict[str, str] = {
    "https://openalex.org/S45757444": "Neuron",
    "https://openalex.org/S2298632": "Nature Neuroscience",
    "https://openalex.org/S5555990": "Journal of Neuroscience",
    "https://openalex.org/S120775027": "Current Opinion in Neurobiology",
    "https://openalex.org/S114966740": "Trends in Neurosciences",
    "https://openalex.org/S131371711": "Annual Review of Neuroscience",
    "https://openalex.org/S142952003": "Journal of Neurophysiology",
    "https://openalex.org/S103225281": "NeuroImage",
    "https://openalex.org/S117898428": "Cerebral Cortex",
    "https://openalex.org/S118357697": "Brain",
    "https://openalex.org/S172319488": "Brain Structure and Function",
    "https://openalex.org/S55111660": "Hippocampus",
    "https://openalex.org/S4210172947": "eNeuro",
    "https://openalex.org/S4210225821": "Network Neuroscience",
    "https://openalex.org/S27455496": "Journal of Computational Neuroscience",
    "https://openalex.org/S115201632": "Frontiers in Neuroscience",
    "https://openalex.org/S96638545": "Brain Research",
    # TODO unresolved: Nature Reviews Neuroscience (display_name not matched)
}

# CORE-AI — flagship AI/ML venues + conferences.
CORE_AI: dict[str, str] = {
    "https://openalex.org/S4306420609": "Neural Information Processing Systems (NeurIPS)",
    "https://openalex.org/S4306419644": "International Conference on Machine Learning (ICML)",
    "https://openalex.org/S4306419637": "International Conference on Learning Representations (ICLR)",
    "https://openalex.org/S4306419999": "International Joint Conference on Artificial Intelligence (IJCAI)",
    "https://openalex.org/S4210191458": "Proceedings of the AAAI Conference on Artificial Intelligence",
    "https://openalex.org/S4306419146": "International Conference on Artificial Intelligence and Statistics (AISTATS)",
    "https://openalex.org/S2912241403": "Nature Machine Intelligence",
    "https://openalex.org/S118988714": "Journal of Machine Learning Research (JMLR)",
    "https://openalex.org/S4306420508": "Meeting of the Association for Computational Linguistics (ACL)",
    "https://openalex.org/S4306418267": "Empirical Methods in Natural Language Processing (EMNLP)",
    "https://openalex.org/S4306418318": "European Conference on Computer Vision (ECCV)",
    "https://openalex.org/S4363607701": "CVPR 2022",
    "https://openalex.org/S4363607764": "ICCV 2021",
    "https://openalex.org/S4306420424": "ACM SIGKDD",
    "https://openalex.org/S4363607759": "ICRA 2022",
    "https://openalex.org/S2729999759": "Transactions of the Association for Computational Linguistics",
    # TODO unresolved: TMLR, EACL, RLC, NAACL canonical entry, COLT, UAI, AAMAS canonical
}

# MIXED / INTERSECTION — neuro-AI overlap venues.
MIXED: dict[str, str] = {
    "https://openalex.org/S207023548": "Neural Computation",
    "https://openalex.org/S86033158": "PLoS Computational Biology",
    "https://openalex.org/S19778766": "Frontiers in Computational Neuroscience",
    "https://openalex.org/S115606517": "Frontiers in Neurorobotics",
    "https://openalex.org/S133078663": "Cognitive Computation",
    "https://openalex.org/S123019304": "Neural Networks",
    "https://openalex.org/S4210175523": "IEEE Transactions on Neural Networks and Learning Systems",
    "https://openalex.org/S78735424": "Cognitive Science",
    "https://openalex.org/S192051125": "Trends in Cognitive Sciences",
    "https://openalex.org/S59628311": "Behavioral and Brain Sciences",
    "https://openalex.org/S4210221739": "Computational Brain & Behavior",
    "https://openalex.org/S255146": "Synthese",
    "https://openalex.org/S147691735": "Philosophy of Science",
    "https://openalex.org/S91660768": "Philosophical Transactions of the Royal Society B",
    "https://openalex.org/S4306498462": "CCN 2019",
    "https://openalex.org/S4363607991": "CCN 2022",
    "https://openalex.org/S4306498296": "CCN 2018",
    "https://openalex.org/S4306419727": "International Conference on Neural Information Processing (ICONIP)",
    # TODO unresolved: WIREs Cognitive Science, Biological Cybernetics
}

# GENERAL HIGH-IMPACT — multi-disciplinary flagship venues; field assignment
# in Q1 will defer to Schemes 1+3 for these.
GENERAL_HIGH: dict[str, str] = {
    "https://openalex.org/S4393913764": "Science",
    "https://openalex.org/S137773608": "Nature",
    "https://openalex.org/S4306524276": "Proceedings of the National Academy of Sciences (PNAS)",
    "https://openalex.org/S64187185": "Nature Communications",
    "https://openalex.org/S1336409049": "eLife",
    "https://openalex.org/S2898358376": "iScience",
    "https://openalex.org/S4210225776": "Communications Biology",
    "https://openalex.org/S110447773": "Cell",
    "https://openalex.org/S169236886": "Cell Reports",
    "https://openalex.org/S4220651275": "PNAS Nexus",
}


SUB_POOLS = {
    "core_neuro": CORE_NEURO,
    "core_ai": CORE_AI,
    "mixed": MIXED,
    "general_high": GENERAL_HIGH,
}


def _tune(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("PRAGMA threads=12")
    con.execute("PRAGMA memory_limit='30GB'")


def _venue_table_sql() -> str:
    """Build a UNION ALL of (venue_id, sub_pool) literals."""
    parts = []
    for sub, mapping in SUB_POOLS.items():
        for vid, _name in mapping.items():
            parts.append(f"SELECT '{vid}' AS venue_id, '{sub}' AS sub_pool")
    return " UNION ALL ".join(parts)


def build(con: duckdb.DuckDBPyConnection | None = None) -> dict:
    owns_con = con is None
    if owns_con:
        con = get_connection(read_only=True)
    try:
        _tune(con)
        t0 = time.time()
        out_path = derived_dir() / "pool3.parquet"

        # Build a temp venues table.
        con.execute(f"CREATE OR REPLACE TEMP TABLE pool3_venues AS {_venue_table_sql()}")

        con.execute(
            f"""
            COPY (
              SELECT
                w.id AS work_id,
                TRUE AS in_pool,
                'pool3' AS source_tag,
                list_distinct(list(v.sub_pool)) AS sub_pool
              FROM works w
              JOIN pool3_venues v ON v.venue_id = w.primary_location.source.id
              WHERE w.publication_year BETWEEN 1990 AND 2026
              GROUP BY w.id
            )
            TO '{out_path}' (FORMAT 'parquet', COMPRESSION 'snappy')
            """
        )
        # Per-sub-pool stats.
        per_sub = dict(
            con.execute(
                f"""
                SELECT sub, COUNT(*) FROM (
                  SELECT UNNEST(sub_pool) AS sub FROM read_parquet('{out_path}')
                ) GROUP BY sub
                """
            ).fetchall()
        )
        n_works = con.execute(f"SELECT COUNT(*) FROM read_parquet('{out_path}')").fetchone()[0]
        elapsed = time.time() - t0
        logger.info(
            "Pool 3: wrote %s (%d works) in %.1fs; sub-pool counts: %s",
            out_path,
            n_works,
            elapsed,
            per_sub,
        )
        return {
            "pool3_works": int(n_works),
            "core_neuro_hits": int(per_sub.get("core_neuro", 0)),
            "core_ai_hits": int(per_sub.get("core_ai", 0)),
            "mixed_hits": int(per_sub.get("mixed", 0)),
            "general_high_hits": int(per_sub.get("general_high", 0)),
            "venues_total": sum(len(m) for m in SUB_POOLS.values()),
            "out_path": str(out_path),
            "elapsed_s": round(elapsed, 1),
        }
    finally:
        if owns_con:
            con.close()


def _cli() -> None:
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    summary = build()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    _cli()

"""Build the unified corpus from Pool 1-4 parquets.

C = P1 ∪ P2 ∪ P3 ∪ P4 (set union, deduplicated by work_id).

Pool overlap is reported, not collapsed, in `pool_overlap.json`, because the
overlap is itself evidence about where NeuroAI work appears.

Output:
    data/derived/corpus.parquet  — work_id, pools (VARCHAR[]), sub_pool_tags (VARCHAR[])
    data/derived/pool_overlap.json — counts per pool combination
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from itertools import combinations
from pathlib import Path

import duckdb

from ..utils.duckdb import derived_dir, get_connection

logger = logging.getLogger(__name__)

POOL_FILES = ("pool1.parquet", "pool2.parquet", "pool3.parquet", "pool4.parquet")


def _tune(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("PRAGMA threads=12")
    con.execute("PRAGMA memory_limit='30GB'")


def _validate_pool_inputs(d: Path) -> dict[str, Path]:
    available = {}
    for f in POOL_FILES:
        p = d / f
        if p.exists() and p.stat().st_size > 0:
            available[f.split(".")[0]] = p
        else:
            logger.warning("Missing pool input: %s — corpus will be partial", f)
    return available


def build(con: duckdb.DuckDBPyConnection | None = None) -> dict:
    owns_con = con is None
    if owns_con:
        con = get_connection(read_only=True)
    try:
        _tune(con)
        d = derived_dir()
        pools = _validate_pool_inputs(d)
        if not pools:
            raise RuntimeError("No pool parquets present; run Pool 1-4 builders first.")

        t0 = time.time()
        # Build a unified per-work table: pool_key, sub_pool_tags from each pool.
        # All four pools share columns (work_id, in_pool, source_tag, sub_pool VARCHAR[]).
        # Pool 4 has an extra disambiguation_needed; we extract it separately.
        union_sql_parts = []
        for key, path in pools.items():
            union_sql_parts.append(
                f"SELECT work_id, '{key}' AS pool_key, sub_pool AS sub_pool_tags FROM read_parquet('{path}')"
            )
        union_sql = " UNION ALL ".join(union_sql_parts)

        out_corpus = d / "corpus.parquet"
        con.execute(
            f"""
            COPY (
              SELECT
                work_id,
                list_distinct(list(pool_key)) AS pools,
                list_distinct(flatten(list(sub_pool_tags))) AS sub_pool_tags
              FROM ({union_sql})
              GROUP BY work_id
            )
            TO '{out_corpus}' (FORMAT 'parquet', COMPRESSION 'snappy')
            """
        )
        n_corpus = con.execute(f"SELECT COUNT(*) FROM read_parquet('{out_corpus}')").fetchone()[0]

        # Compute pool overlap structure: per-pool counts + all combinations.
        per_pool_counts = dict(
            con.execute(
                f"""
                SELECT pool, COUNT(*) FROM (
                  SELECT UNNEST(pools) AS pool FROM read_parquet('{out_corpus}')
                ) GROUP BY pool ORDER BY 1
                """
            ).fetchall()
        )
        # Overlap structure: count works belonging to exactly each subset of pools.
        overlap_rows = con.execute(
            f"SELECT pools, COUNT(*) AS n FROM read_parquet('{out_corpus}') GROUP BY pools ORDER BY n DESC"
        ).fetchall()
        # Pairwise + higher-order: count works in (pool_i AND pool_j AND ...).
        pool_keys = sorted(pools.keys())
        higher = {}
        for r in range(2, len(pool_keys) + 1):
            for combo in combinations(pool_keys, r):
                key = "+".join(combo)
                cond = " AND ".join([f"list_contains(pools, '{k}')" for k in combo])
                n = con.execute(
                    f"SELECT COUNT(*) FROM read_parquet('{out_corpus}') WHERE {cond}"
                ).fetchone()[0]
                higher[key] = int(n)

        elapsed = time.time() - t0
        overlap_json = {
            "n_corpus_works": int(n_corpus),
            "per_pool_counts": {k: int(v) for k, v in per_pool_counts.items()},
            "overlap_partition": [
                {"pools": list(r[0]) if r[0] is not None else [], "n_works": int(r[1])}
                for r in overlap_rows
            ],
            "higher_order_intersections": higher,
            "pools_built": sorted(pools.keys()),
            "missing_pools": [k for k in ("pool1", "pool2", "pool3", "pool4") if k not in pools],
        }
        out_overlap = d / "pool_overlap.json"
        out_overlap.write_text(json.dumps(overlap_json, indent=2))
        logger.info(
            "Corpus built: %d works in %.1fs. Per-pool: %s. Wrote %s and %s.",
            n_corpus,
            elapsed,
            per_pool_counts,
            out_corpus,
            out_overlap,
        )
        return {
            "corpus_works": int(n_corpus),
            "out_corpus": str(out_corpus),
            "out_overlap": str(out_overlap),
            "per_pool_counts": {k: int(v) for k, v in per_pool_counts.items()},
            "elapsed_s": round(elapsed, 1),
            "pools_built": sorted(pools.keys()),
            "missing_pools": [k for k in ("pool1", "pool2", "pool3", "pool4") if k not in pools],
        }
    finally:
        if owns_con:
            con.close()


def _cli() -> None:
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

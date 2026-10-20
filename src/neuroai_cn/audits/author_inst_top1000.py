"""Re-aggregate bridge authors + institutions to top-1000 each.

Same logic as `author_inst_bridge.py` but emits:
    - `author_inst_top_authors_1000.parquet`        — top-1000 authors
    - `author_inst_top_institutions_1000.parquet`   — top-1000 institutions
    - `author_inst_population_totals.json`          — ∑B across ALL authors / ALL insts
                                                       (denominators for cumulative share)

The 1000-row tables let the authors-vs-institutions analysis stretch from
rank 1 to rank 1000 (instead of the previous top-200 / top-100), which the
user asked for as the new scope.
"""

from __future__ import annotations

import json
import logging
import sys
import time

import pandas as pd

from .. import config
from ..utils.duckdb import get_connection

logger = logging.getLogger(__name__)

CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"
TOP_N = 1000
MIN_PAPERS_AUTHOR = 2
MIN_PAPERS_INST = 5


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    bridge = pd.read_parquet(CORRECTIONS_DIR / "q4_v3_extended_full.parquet")
    logger.info("Loaded %d bridge candidates", len(bridge))

    id_to_meta = {
        str(row.work_id): (row.B_harmonic, row.c_neuro, row.c_ai) for row in bridge.itertuples()
    }
    all_ids = list(id_to_meta.keys())
    logger.info("Bridge work-IDs: %d", len(all_ids))

    works_subset: list[tuple] = []
    with get_connection(read_only=True) as con:
        con.execute("PRAGMA threads=4")
        con.execute("PRAGMA memory_limit='6GB'")
        con.execute("PRAGMA preserve_insertion_order=false")
        t_step1 = time.time()
        # Use a temp table + streaming cursor to avoid the OOM that giant
        # IN-clauses produce.
        con.execute("CREATE TEMP TABLE _bridge_ids (work_id VARCHAR)")
        con.executemany("INSERT INTO _bridge_ids VALUES (?)", [(w,) for w in all_ids])
        logger.info(
            "Loaded %d bridge_ids into temp table (%.0fs)",
            len(all_ids),
            time.time() - t_step1,
        )
        res = con.execute(
            """
            SELECT w.id, w.authorships
            FROM works w
            JOIN _bridge_ids b ON w.id = b.work_id
            """
        )
        batch = 200
        total = 0
        while True:
            rows = res.fetchmany(batch)
            if not rows:
                break
            for wid, authships in rows:
                b, cn, ca = id_to_meta.get(wid, (None, None, None))
                works_subset.append((wid, b, cn, ca, authships))
            total += len(rows)
            if total % (batch * 25) == 0:
                logger.info(
                    "  step1 streamed %d / %d works (%.0fs)",
                    total,
                    len(all_ids),
                    time.time() - t_step1,
                )
        logger.info("Step1 done: %d works in %.0fs", len(works_subset), time.time() - t_step1)

    # Step 2: flatten authorships
    t_step2 = time.time()
    rows = []
    for work_id, b, cn, ca, authships in works_subset:
        if not authships:
            continue
        for auth_struct in authships:
            author = auth_struct.get("author") or {}
            auth_id = author.get("id")
            auth_name = author.get("display_name")
            insts = auth_struct.get("institutions") or []
            if not insts:
                rows.append(
                    dict(
                        work_id=work_id,
                        B_harmonic=b,
                        c_neuro=cn,
                        c_ai=ca,
                        author_id=auth_id,
                        author_name=auth_name,
                        inst_id=None,
                        inst_name=None,
                        country_code=None,
                        inst_type=None,
                    )
                )
                continue
            for inst in insts:
                rows.append(
                    dict(
                        work_id=work_id,
                        B_harmonic=b,
                        c_neuro=cn,
                        c_ai=ca,
                        author_id=auth_id,
                        author_name=auth_name,
                        inst_id=inst.get("id"),
                        inst_name=inst.get("display_name"),
                        country_code=inst.get("country_code"),
                        inst_type=inst.get("type"),
                    )
                )
    wai = pd.DataFrame(rows)
    logger.info("Step2 done: %d (work,author,inst) rows in %.0fs", len(wai), time.time() - t_step2)

    # AUTHORS: full distribution (no head), but the parquet only saves top-1000
    authors_all = (
        wai.dropna(subset=["author_id"])
        .drop_duplicates(subset=["work_id", "author_id"])
        .groupby("author_id")
        .agg(
            author_name=("author_name", lambda s: s.mode().iloc[0] if len(s.mode()) else None),
            n_bridge_papers=("work_id", "nunique"),
            total_B=("B_harmonic", "sum"),
            mean_B=("B_harmonic", "mean"),
            max_B=("B_harmonic", "max"),
            total_c_neuro=("c_neuro", "sum"),
            total_c_ai=("c_ai", "sum"),
        )
        .reset_index()
        .query(f"n_bridge_papers >= {MIN_PAPERS_AUTHOR}")
        .sort_values("total_B", ascending=False)
    )
    authors_top = authors_all.head(TOP_N).copy()
    authors_top.insert(0, "rank", range(1, len(authors_top) + 1))
    authors_top.to_parquet(CORRECTIONS_DIR / "author_inst_top_authors_1000.parquet", index=False)
    logger.info(
        "Top authors: saved %d/%d (full author pool size = %d)",
        len(authors_top),
        len(authors_all),
        len(authors_all),
    )

    # INSTITUTIONS
    insts_all = (
        wai.dropna(subset=["inst_id"])
        .drop_duplicates(subset=["work_id", "inst_id"])
        .groupby("inst_id")
        .agg(
            inst_name=("inst_name", lambda s: s.mode().iloc[0] if len(s.mode()) else None),
            country_code=("country_code", lambda s: s.mode().iloc[0] if len(s.mode()) else None),
            inst_type=("inst_type", lambda s: s.mode().iloc[0] if len(s.mode()) else None),
            n_bridge_papers=("work_id", "nunique"),
            total_B=("B_harmonic", "sum"),
            mean_B=("B_harmonic", "mean"),
            total_c_neuro=("c_neuro", "sum"),
            total_c_ai=("c_ai", "sum"),
        )
        .reset_index()
        .query(f"n_bridge_papers >= {MIN_PAPERS_INST}")
        .sort_values("total_B", ascending=False)
    )
    insts_top = insts_all.head(TOP_N).copy()
    insts_top.insert(0, "rank", range(1, len(insts_top) + 1))
    insts_top.to_parquet(CORRECTIONS_DIR / "author_inst_top_institutions_1000.parquet", index=False)
    logger.info(
        "Top institutions: saved %d/%d (full inst pool size = %d)",
        len(insts_top),
        len(insts_all),
        len(insts_all),
    )

    # Population totals (full distribution sums — for correct cumulative-share
    # denominators in the authors-vs-institutions analysis).
    totals = dict(
        authors_total_B=float(authors_all["total_B"].sum()),
        authors_n=len(authors_all),
        insts_total_B=float(insts_all["total_B"].sum()),
        insts_n=len(insts_all),
        date="2026-05-22",
        min_papers_author=MIN_PAPERS_AUTHOR,
        min_papers_inst=MIN_PAPERS_INST,
    )
    (CORRECTIONS_DIR / "author_inst_population_totals.json").write_text(
        json.dumps(totals, indent=2)
    )
    logger.info("Wrote population totals: %s", totals)
    return 0


if __name__ == "__main__":
    sys.exit(main())

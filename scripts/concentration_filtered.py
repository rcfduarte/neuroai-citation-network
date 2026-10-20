"""Re-aggregate bridge authors + institutions on the FIELD-FILTERED bridge set.

Why this exists
---------------
`audits/author_inst_top1000.py` aggregates over the full 133,763-row bridge
candidate set, which includes 74,485 papers whose `bridge_paper_field` is
`other`. That pool is dominated by an off-domain cluster (Large Helical Device
plasma physics at the National Institute for Fusion Science), which takes 14 of
the top 15 author slots and the #1 institution slot. Any concentration statistic
computed on it is contaminated.

This script repeats the identical aggregation on a filtered set and emits the
FULL distributions (not just the top 1000), so cumulative share can be evaluated
at any rank.

Variants
--------
V1 (primary)    bridge_paper_field in {neuro, ai}
V2 (sensitivity) V1 AND c_total_classified < 10_000  (drops mega-cited utilities)

Outputs (data/derived/corrections/20260729/):
    concentration_authors_{v1,v2}.parquet   full author distribution
    concentration_insts_{v1,v2}.parquet     full institution distribution
    concentration_summary.json              population totals + cumulative shares
"""

from __future__ import annotations

import json
import logging
import time

import pandas as pd

from neuroai_cn import config
from neuroai_cn.utils.duckdb import get_connection

logger = logging.getLogger(__name__)

SRC = config.CORRECTIONS_DIR / "20260508"
OUT = config.CORRECTIONS_DIR / "20260729"

MIN_PAPERS_AUTHOR = 2
MIN_PAPERS_INST = 5
RANKS = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000]


def flatten(works_subset: list[tuple]) -> pd.DataFrame:
    rows = []
    for work_id, b, cn, ca, authships in works_subset:
        if not authships:
            continue
        for auth_struct in authships:
            author = auth_struct.get("author") or {}
            auth_id = author.get("id")
            auth_name = author.get("display_name")
            insts = auth_struct.get("institutions") or []
            base = dict(
                work_id=work_id,
                B_harmonic=b,
                c_neuro=cn,
                c_ai=ca,
                author_id=auth_id,
                author_name=auth_name,
            )
            if not insts:
                rows.append(
                    {
                        **base,
                        "inst_id": None,
                        "inst_name": None,
                        "country_code": None,
                        "inst_type": None,
                    }
                )
                continue
            for inst in insts:
                rows.append(
                    {
                        **base,
                        "inst_id": inst.get("id"),
                        "inst_name": inst.get("display_name"),
                        "country_code": inst.get("country_code"),
                        "inst_type": inst.get("type"),
                    }
                )
    return pd.DataFrame(rows)


def aggregate(wai: pd.DataFrame, key: str, name_col: str, min_papers: int) -> pd.DataFrame:
    agg = {
        name_col: (name_col, lambda s: s.mode().iloc[0] if len(s.mode()) else None),
        "n_bridge_papers": ("work_id", "nunique"),
        "total_B": ("B_harmonic", "sum"),
        "mean_B": ("B_harmonic", "mean"),
        "max_B": ("B_harmonic", "max"),
        "total_c_neuro": ("c_neuro", "sum"),
        "total_c_ai": ("c_ai", "sum"),
    }
    if key == "inst_id":
        agg["country_code"] = (
            "country_code",
            lambda s: s.mode().iloc[0] if len(s.mode()) else None,
        )
        agg["inst_type"] = ("inst_type", lambda s: s.mode().iloc[0] if len(s.mode()) else None)
    out = (
        wai.dropna(subset=[key])
        .drop_duplicates(subset=["work_id", key])
        .groupby(key)
        .agg(**agg)
        .reset_index()
        .query(f"n_bridge_papers >= {min_papers}")
        .sort_values("total_B", ascending=False)
        .reset_index(drop=True)
    )
    out.insert(0, "rank", range(1, len(out) + 1))
    return out


def gini(x: pd.Series) -> float:
    v = x.sort_values().to_numpy(dtype=float)
    n = len(v)
    if n == 0 or v.sum() == 0:
        return float("nan")
    idx = range(1, n + 1)
    return float(
        (2 * sum(i * xi for i, xi in zip(idx, v, strict=False)) / (n * v.sum())) - (n + 1) / n
    )


def cumulative(df: pd.DataFrame) -> dict:
    total = float(df["total_B"].sum())
    out = {"n": len(df), "total_B": total, "gini": gini(df["total_B"])}
    for r in RANKS:
        if r <= len(df):
            out[f"top{r}_pct"] = round(100 * float(df.head(r)["total_B"].sum()) / total, 2)
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    bridge = pd.read_parquet(SRC / "q4_v3_extended_full.parquet")
    logger.info("Full bridge candidates: %d", len(bridge))

    v1 = bridge[bridge["bridge_paper_field"].isin(["neuro", "ai"])].copy()
    v2 = v1[v1["c_total_classified"] < 10_000].copy()
    logger.info("V1 (field-filtered): %d | V2 (+utility cap): %d", len(v1), len(v2))

    id_to_meta = {str(r.work_id): (r.B_harmonic, r.c_neuro, r.c_ai) for r in v1.itertuples()}
    all_ids = list(id_to_meta.keys())

    works_subset: list[tuple] = []
    t0 = time.time()
    with get_connection(read_only=True) as con:
        con.execute("PRAGMA threads=4")
        con.execute("PRAGMA memory_limit='6GB'")
        con.execute("PRAGMA preserve_insertion_order=false")
        con.execute("CREATE TEMP TABLE _bids (work_id VARCHAR)")
        con.executemany("INSERT INTO _bids VALUES (?)", [(w,) for w in all_ids])
        logger.info("Loaded %d ids (%.0fs)", len(all_ids), time.time() - t0)
        res = con.execute(
            "SELECT w.id, w.authorships FROM works w JOIN _bids b ON w.id = b.work_id"
        )
        total = 0
        while True:
            rows = res.fetchmany(200)
            if not rows:
                break
            for wid, authships in rows:
                b, cn, ca = id_to_meta.get(wid, (None, None, None))
                works_subset.append((wid, b, cn, ca, authships))
            total += len(rows)
            if total % 5000 == 0:
                logger.info("  streamed %d / %d (%.0fs)", total, len(all_ids), time.time() - t0)
    logger.info("Streamed %d works in %.0fs", len(works_subset), time.time() - t0)

    wai_v1 = flatten(works_subset)
    logger.info("V1 flattened rows: %d", len(wai_v1))
    v2_ids = set(v2["work_id"].astype(str))
    wai_v2 = wai_v1[wai_v1["work_id"].isin(v2_ids)]
    logger.info("V2 flattened rows: %d", len(wai_v2))

    summary = {
        "generated": "2026-07-29",
        "source": "q4_v3_extended_full.parquet",
        "n_papers_full": len(bridge),
        "n_papers_v1": len(v1),
        "n_papers_v2": len(v2),
        "min_papers_author": MIN_PAPERS_AUTHOR,
        "min_papers_inst": MIN_PAPERS_INST,
    }

    for tag, wai in (("v1", wai_v1), ("v2", wai_v2)):
        authors = aggregate(wai, "author_id", "author_name", MIN_PAPERS_AUTHOR)
        insts = aggregate(wai, "inst_id", "inst_name", MIN_PAPERS_INST)
        authors.to_parquet(OUT / f"concentration_authors_{tag}.parquet", index=False)
        insts.to_parquet(OUT / f"concentration_insts_{tag}.parquet", index=False)
        summary[tag] = {"authors": cumulative(authors), "institutions": cumulative(insts)}
        logger.info("%s: %d authors, %d institutions", tag, len(authors), len(insts))
        logger.info("%s top15 authors: %s", tag, list(authors.head(15)["author_name"]))
        logger.info("%s top10 insts: %s", tag, list(insts.head(10)["inst_name"]))

    (OUT / "concentration_summary.json").write_text(json.dumps(summary, indent=2))
    logger.info("Summary: %s", json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

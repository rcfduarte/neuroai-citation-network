"""Author-side concentration on the field-filtered bridge set, without DuckDB.

`_authorships_parts/` already holds the flattened (work_id, author_id) mapping
for the whole snapshot, so the author aggregate does not need the 493 GB works
table. Institutions still do, because the parts files carry no affiliation.

Emits the FULL author distribution for three paper sets so the contamination
can be quantified rather than asserted:
    full  all 133,763 candidates            (what the published 35% figure used)
    v1    bridge_paper_field in {neuro, ai} (59,038)
    v2    v1 and c_total_classified < 10k   (58,971)
"""

from __future__ import annotations

import glob
import json
import logging

import pandas as pd

from neuroai_cn import config

logger = logging.getLogger(__name__)

SRC = config.CORRECTIONS_DIR / "20260508"
PARTS = str(config.AUTHORSHIPS_PARTS_DIR / "*.parquet")
OUT = config.CORRECTIONS_DIR / "20260729"

MIN_PAPERS_AUTHOR = 2
RANKS = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000]


def gini(x: pd.Series) -> float:
    v = x.sort_values().to_numpy(dtype=float)
    n = len(v)
    if n == 0 or v.sum() == 0:
        return float("nan")
    return float(
        (2 * sum(i * xi for i, xi in zip(range(1, n + 1), v, strict=False)) / (n * v.sum()))
        - (n + 1) / n
    )


def cumulative(df: pd.DataFrame) -> dict:
    total = float(df["total_B"].sum())
    out = {"n": len(df), "total_B": round(total, 1), "gini": round(gini(df["total_B"]), 4)}
    for r in RANKS:
        if r <= len(df):
            out[f"top{r}_pct"] = round(100 * float(df.head(r)["total_B"].sum()) / total, 2)
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    bridge = pd.read_parquet(SRC / "q4_v3_extended_full.parquet")
    bridge["work_id"] = bridge["work_id"].astype(str)
    sets = {
        "full": bridge,
        "v1": bridge[bridge["bridge_paper_field"].isin(["neuro", "ai"])],
        "v2": bridge[
            bridge["bridge_paper_field"].isin(["neuro", "ai"])
            & (bridge["c_total_classified"] < 10_000)
        ],
    }
    for k, v in sets.items():
        logger.info("%s: %d papers", k, len(v))

    wanted = set(bridge["work_id"])
    files = sorted(glob.glob(PARTS))
    logger.info("Scanning %d authorship parts", len(files))

    chunks = []
    for i, f in enumerate(files, 1):
        d = pd.read_parquet(f, columns=["work_id", "author_id"])
        if len(d):
            d["work_id"] = d["work_id"].astype(str)
            d = d[d["work_id"].isin(wanted)]
            if len(d):
                chunks.append(d)
        if i % 50 == 0:
            logger.info(
                "  %d/%d parts, %d matched rows so far", i, len(files), sum(len(c) for c in chunks)
            )
    wa = pd.concat(chunks, ignore_index=True).drop_duplicates(["work_id", "author_id"])
    wa = wa.dropna(subset=["author_id"])
    logger.info("Matched (work, author) pairs: %d", len(wa))

    summary = {"generated": "2026-07-29", "min_papers_author": MIN_PAPERS_AUTHOR}
    for tag, sub in sets.items():
        b = sub[["work_id", "B_harmonic"]]
        m = wa.merge(b, on="work_id", how="inner")
        authors = (
            m.groupby("author_id")
            .agg(
                n_bridge_papers=("work_id", "nunique"),
                total_B=("B_harmonic", "sum"),
                mean_B=("B_harmonic", "mean"),
                max_B=("B_harmonic", "max"),
            )
            .reset_index()
            .query(f"n_bridge_papers >= {MIN_PAPERS_AUTHOR}")
            .sort_values("total_B", ascending=False)
            .reset_index(drop=True)
        )
        authors.insert(0, "rank", range(1, len(authors) + 1))
        authors.to_parquet(OUT / f"authors_{tag}.parquet", index=False)
        summary[tag] = cumulative(authors)
        logger.info("%s -> %d authors | %s", tag, len(authors), summary[tag])

    (OUT / "concentration_authors_summary.json").write_text(json.dumps(summary, indent=2))
    logger.info("DONE\n%s", json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Re-rank bridge papers, keeping only journal articles and reviews.

Audit 2026-05-22 found `book-chapter` entries (notably Duda-Hart-Stork
"Pattern Classification") in the top-15 ranked bridge papers. The piece
methodology was supposed to exclude books and book-chapters. Re-filter using
OpenAlex `type` and write a clean top-N parquet.

Kept types: article, review (peer-reviewed scientific output).
Dropped:    book, book-chapter, dataset, dissertation, other, paratext, etc.

Output:
    corrections/20260508/q4_v3_extended_filtered_by_era_papers_only.parquet
        — same schema as q4_v3_extended_filtered_by_era.parquet,
          ranked over the article/review subset only.
"""

from __future__ import annotations

import logging
import sys

import pandas as pd

from .. import config
from ..utils.duckdb import get_connection

logger = logging.getLogger(__name__)

CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"
KEEP_TYPES = ("article", "review")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    full = pd.read_parquet(CORRECTIONS_DIR / "q4_v3_extended_full.parquet")
    logger.info("Loaded 133k bridge-paper candidates: %d rows", len(full))

    # Query type for all candidates
    work_ids = full["work_id"].astype(str).tolist()
    with get_connection(read_only=True) as con:
        con.execute("PRAGMA threads=4")
        con.execute("PRAGMA memory_limit='9GB'")
        con.execute("PRAGMA preserve_insertion_order=false")
        con.execute("CREATE TEMP TABLE _bids (work_id VARCHAR)")
        con.executemany("INSERT INTO _bids VALUES (?)", [(w,) for w in work_ids])
        type_df = con.execute(
            """
            SELECT w.id AS work_id, w.type
            FROM works w
            JOIN _bids b ON w.id = b.work_id
            """
        ).df()
    logger.info("Type lookup returned %d rows", len(type_df))

    merged = full.merge(type_df, on="work_id", how="left")
    type_summary = merged["type"].value_counts().to_dict()
    logger.info("Type breakdown of bridge papers:")
    for t, n in sorted(type_summary.items(), key=lambda x: -x[1]):
        marker = " ✓" if t in KEEP_TYPES else " ✗ DROP"
        logger.info("  %-20s  %6d%s", t, n, marker)

    kept = merged[merged["type"].isin(KEEP_TYPES)].copy()
    logger.info("After type filter (article + review): %d rows", len(kept))

    # Also restrict to AI or Neuro primary classification (drop bridge_paper_field='other').
    # The original q4_v3_extended_filtered_by_era parquet applied this implicitly; the
    # "other" bucket is dominated by physics / general-science papers whose B_harmonic
    # is incidentally large but which are NOT neuro<->AI bridges.
    before = len(kept)
    kept = kept[kept["bridge_paper_field"].isin(["ai", "neuro"])]
    logger.info("After field filter (drop 'other'): %d rows (was %d)", len(kept), before)

    # Title-based deduplication: OpenAlex sometimes carries multiple work_ids
    # for the same book/paper (e.g. Sutton-Barto RL Intro 1998+2005 are listed
    # twice; Cortes-Vapnik 1995 has two near-identical records). Keep the
    # highest-B copy per normalised title.
    before = len(kept)
    kept["_title_norm"] = (
        kept["title"].astype(str).str.lower().str.strip().str.replace(r"\s+", " ", regex=True)
    )
    kept = (
        kept.sort_values("B_harmonic", ascending=False)
        .drop_duplicates(subset=["_title_norm"], keep="first")
        .drop(columns=["_title_norm"])
    )
    logger.info("After title dedup: %d rows (was %d)", len(kept), before)

    # Re-rank
    kept = kept.sort_values("B_harmonic", ascending=False).reset_index(drop=True)
    kept["rank"] = kept.index + 1

    # Era column expected by figure code; carry through if present in source.
    # The era column lived on the *by_era* parquet (38 rows) which we
    # supersede; reconstruct era by year here.
    def assign_era(y: int) -> str:
        if 1990 <= y <= 2018:
            return "bridge_era"
        if 2019 <= y <= 2025:
            return "brand_era"
        return "other"

    kept["era"] = kept["publication_year"].apply(assign_era)
    # Add the same era_year_min / max columns
    era_bounds = {"bridge_era": (1990, 2018), "brand_era": (2019, 2025)}
    kept["era_year_min"] = kept["era"].map(lambda e: era_bounds.get(e, (0, 0))[0])
    kept["era_year_max"] = kept["era"].map(lambda e: era_bounds.get(e, (0, 0))[1])

    # Schema-align: keep only the columns the downstream figure expects.
    cols_out = [
        "rank",
        "work_id",
        "doi",
        "title",
        "publication_year",
        "cited_by_count",
        "bridge_paper_field",
        "c_neuro",
        "c_ai",
        "c_total_classified",
        "B_harmonic",
        "era",
        "era_year_min",
        "era_year_max",
        "type",
    ]
    out_df = kept[cols_out].head(50)  # save top-50 for flexibility
    out = CORRECTIONS_DIR / "q4_v3_extended_filtered_by_era_papers_only.parquet"
    out_df.to_parquet(out, index=False)
    logger.info("Wrote %s (%d rows, top-50)", out, len(out_df))

    # Print top-15 for visual check
    print("\\n=== NEW TOP-15 BRIDGE PAPERS (article + review only) ===")
    print(
        out_df[["rank", "title", "publication_year", "type", "bridge_paper_field", "B_harmonic"]]
        .head(15)
        .to_string(max_colwidth=60)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

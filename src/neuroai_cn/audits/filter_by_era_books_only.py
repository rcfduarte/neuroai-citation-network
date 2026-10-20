"""Filter books out of the locked `q4_v3_extended_filtered_by_era.parquet` set.

This is the SURGICAL fix per user 2026-05-22: start from the ORIGINAL 37-paper
pre-selected set (era × field balanced) and remove only entries that are books,
book-chapters, ebook proceedings, or otherwise non-paper.

Method:
    1. Take all 37 rows from `q4_v3_extended_filtered_by_era.parquet`.
    2. Query OpenAlex `type` for each (DuckDB scan).
    3. Drop OpenAlex `type ∈ {book, book-chapter}`.
    4. Drop where the work has `primary_location.source.type ∈ {ebook platform, book series}`
       — catches NeurIPS proceedings volumes mis-typed as `article`.
    5. Drop where `title` is null or empty (data-quality artifact).
    6. Drop a hand-curated list of known book misclassifications (Sutton-Barto's
       "Reinforcement Learning: An Introduction" is the canonical example).
    7. Write the filtered set as `q4_v3_extended_filtered_by_era_no_books.parquet`.

The OLD by_era selection logic (12 ai brand + 19 ai bridge + 6 neuro bridge) is
preserved; we only remove books from that set.
"""

from __future__ import annotations

import logging
import sys

import pandas as pd

from .. import config
from ..utils.duckdb import get_connection

logger = logging.getLogger(__name__)

CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"

# Hand-curated list of known book misclassifications in OpenAlex. Update as
# we find more. Match by title prefix (case-insensitive).
KNOWN_BOOK_TITLES = {
    "reinforcement learning: an introduction",
    "pattern classification",  # safety net; should already be dropped by type
    "advances in neural information processing systems",  # any volume number
}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    src = CORRECTIONS_DIR / "q4_v3_extended_filtered_by_era.parquet"
    old = pd.read_parquet(src).copy()
    logger.info("Loaded original %d-row by_era parquet", len(old))

    work_ids = old["work_id"].astype(str).tolist()
    quoted = ",".join("'" + w.replace("'", "''") + "'" for w in work_ids)

    # Server-side: pull `type` + the primary location source type for each work.
    with get_connection(read_only=True) as con:
        con.execute("PRAGMA threads=4")
        con.execute("PRAGMA memory_limit='6GB'")
        df = con.execute(
            f"""
            SELECT
                id AS work_id,
                type AS oa_type,
                primary_location.source.type AS source_type,
                primary_location.source.display_name AS venue,
                title AS oa_title
            FROM works
            WHERE id IN ({quoted})
            """
        ).df()
    logger.info("DuckDB returned %d type rows", len(df))

    merged = old.merge(df, on="work_id", how="left")

    # Step 3: drop books / book-chapters by OpenAlex type
    before = len(merged)
    book_types = {"book", "book-chapter"}
    drop_oa_type = merged["oa_type"].isin(book_types)
    logger.info("Dropping OpenAlex type ∈ {book, book-chapter}: %d row(s)", int(drop_oa_type.sum()))

    # Step 4: drop ebook platform / book series sources
    book_sources = {"ebook platform", "book series"}
    drop_source = merged["source_type"].isin(book_sources)
    logger.info(
        "Dropping source.type ∈ {ebook platform, book series}: %d row(s)",
        int(drop_source.sum()),
    )

    # Step 5: drop empty-title rows
    drop_title = merged["title"].isna() | (merged["title"].str.strip() == "")
    logger.info("Dropping empty-title rows: %d", int(drop_title.sum()))

    # Step 6: drop hand-curated known-book titles
    def is_known_book(t: str | None) -> bool:
        if not t:
            return False
        t_lo = t.lower().strip()
        return any(t_lo.startswith(kb) for kb in KNOWN_BOOK_TITLES)

    drop_known = merged["title"].apply(is_known_book)
    logger.info("Dropping hand-curated known-book titles: %d", int(drop_known.sum()))

    drop_mask = drop_oa_type | drop_source | drop_title | drop_known
    if drop_mask.any():
        logger.info("=== Rows being dropped ===")
        cols = ["title", "publication_year", "B_harmonic", "oa_type", "source_type", "venue"]
        print(merged.loc[drop_mask, cols].to_string(max_colwidth=50))

    kept = merged.loc[~drop_mask].copy()
    logger.info("After drops: %d -> %d rows", before, len(kept))

    # Drop the audit columns before write-out so the schema matches the original
    schema_cols = [c for c in old.columns if c != "rank"]
    kept = kept.sort_values("B_harmonic", ascending=False).reset_index(drop=True)
    kept["rank"] = kept.index + 1
    out_cols = ["rank"] + [c for c in schema_cols]
    out_df = kept[out_cols]
    out = CORRECTIONS_DIR / "q4_v3_extended_filtered_by_era_no_books.parquet"
    out_df.to_parquet(out, index=False)
    logger.info("Wrote %s (%d rows)", out, len(out_df))

    # Show new top-15
    print("\\n=== NEW TOP-15 AFTER BOOKS REMOVED (preserves era×field selection) ===")
    print(
        out_df[["rank", "title", "publication_year", "bridge_paper_field", "B_harmonic"]]
        .head(15)
        .to_string(max_colwidth=60)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

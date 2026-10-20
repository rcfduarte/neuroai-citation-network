"""Fetch journal / venue names for the top-15 bridge papers (Figure 2 v3 labels).

Uses OpenAlex `primary_location.source.display_name` for each top-15 paper's
work_id. Output is consumed by the figure builder to render "Title (year).
*Journal*" inside the paper bar.

Output:
    corrections/20260508/top_paper_venues.parquet
        work_id, venue, source_type
"""

from __future__ import annotations

import logging
import sys
import time

import pandas as pd
import requests

from .. import config

logger = logging.getLogger(__name__)

CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    no_books = CORRECTIONS_DIR / "q4_v3_extended_filtered_by_era_no_books.parquet"
    src = (
        no_books
        if no_books.exists()
        else CORRECTIONS_DIR / "q4_v3_extended_filtered_by_era.parquet"
    )
    df = pd.read_parquet(src).sort_values("B_harmonic", ascending=False).head(15)

    out_rows = []
    for _, row in df.iterrows():
        wid = str(row["work_id"])
        short = wid.split("/")[-1]
        url = f"https://api.openalex.org/works/{short}?mailto={config.openalex_email()}"
        try:
            r = requests.get(url, headers={"User-Agent": "NeuroAI-CN-research/1.0"}, timeout=20)
            r.raise_for_status()
            d = r.json()
        except Exception as exc:
            logger.warning("API error for %s: %s", short, exc)
            d = {}
        src_block = (d.get("primary_location") or {}).get("source") or {}
        venue = src_block.get("display_name", "") or ""
        source_type = src_block.get("type", "") or ""
        out_rows.append(
            dict(
                work_id=wid,
                venue=venue,
                source_type=source_type,
            )
        )
        time.sleep(0.05)

    out_df = pd.DataFrame(out_rows)
    out = CORRECTIONS_DIR / "top_paper_venues.parquet"
    out_df.to_parquet(out, index=False)
    print(
        out_df.merge(df[["work_id", "title", "publication_year"]], on="work_id", how="left")[
            ["title", "publication_year", "venue", "source_type"]
        ].to_string(max_colwidth=60)
    )
    logger.info("Wrote %s (%d rows)", out, len(out_df))
    return 0


if __name__ == "__main__":
    sys.exit(main())

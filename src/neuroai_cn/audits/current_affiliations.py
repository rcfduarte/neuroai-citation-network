"""Fetch current institutional affiliations for top-15 bridge authors.

Authors change institutions; the cumulative author->institution edge table built
in `bridge_links.py` aggregates across the author's whole career. For the
Figure 2 v3 layout we want CURRENT affiliations only.

Method:
    For each top-15 author, query the OpenAlex authors API
    (https://api.openalex.org/authors/<id>) and extract
    `last_known_institutions` (the field OpenAlex maintains for "most recent
    institutional affiliations").

Output:
    corrections/20260508/author_current_affiliations.parquet
        author_id, author_name, author_rank,
        inst_id, inst_name, country_code, inst_type,
        is_in_top15  (boolean)
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

OPENALEX_AUTHORS = "https://api.openalex.org/authors"


def fetch_author_record(author_id: str) -> dict | None:
    # OpenAlex full IDs look like https://openalex.org/A5023431990 — strip prefix.
    a_short = author_id.split("/")[-1]
    url = f"{OPENALEX_AUTHORS}/{a_short}?mailto={config.openalex_email()}"
    try:
        resp = requests.get(url, headers={"User-Agent": config.openalex_user_agent()}, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("API error for %s: %s", a_short, exc)
        return None


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    top_a = (
        pd.read_parquet(CORRECTIONS_DIR / "author_inst_top_authors.parquet")
        .sort_values("total_B", ascending=False)
        .head(15)
        .reset_index(drop=True)
    )
    top_a["author_rank"] = top_a.index + 1
    top_i = pd.read_parquet(CORRECTIONS_DIR / "author_inst_top_institutions.parquet")
    top_inst_ids = set(top_i["inst_id"].astype(str))

    rows = []
    for _, row in top_a.iterrows():
        aid = str(row["author_id"])
        aname = row["author_name"]
        rank = int(row["author_rank"])
        rec = fetch_author_record(aid)
        if not rec:
            continue
        insts = rec.get("last_known_institutions") or []
        if not insts and rec.get("last_known_institution"):
            # Older API shape (singular). Coerce to list.
            insts = [rec["last_known_institution"]]
        if not insts:
            logger.warning("No last_known_institutions for %s (%s)", aname, aid)
            continue
        logger.info("  [#%d] %s -> %d affiliation(s)", rank, aname, len(insts))
        for inst in insts:
            inst_id = inst.get("id")
            rows.append(
                dict(
                    author_id=aid,
                    author_name=aname,
                    author_rank=rank,
                    inst_id=inst_id,
                    inst_name=inst.get("display_name"),
                    country_code=inst.get("country_code"),
                    inst_type=inst.get("type"),
                    is_in_top15=(inst_id in top_inst_ids),
                )
            )
        time.sleep(0.10)

    df = pd.DataFrame(rows)
    out = CORRECTIONS_DIR / "author_current_affiliations.parquet"
    df.to_parquet(out, index=False)
    logger.info(
        "Wrote %s (%d rows; %d in top-15 insts)", out, len(df), int(df["is_in_top15"].sum())
    )
    print(
        df[["author_rank", "author_name", "inst_name", "country_code", "is_in_top15"]].to_string()
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Fetch the 4 Tier 1 canonical bridge papers via OpenAlex API.

Why: in the snapshot pull, papers are partitioned by `updated_date`, which is
when OpenAlex last touched the record — independent of `publication_year`.
A reverse-chronological snapshot pull therefore does not guarantee that
heavily-cited bridge papers (e.g. Zador 2023) land in early partitions; they
appear only in whichever date OpenAlex last updated them.

To guarantee Tier 1 verification regardless of snapshot completeness, we fetch
the 4 specific bridge papers via the OpenAlex API and write them as a
supplemental parquet alongside the snapshot-derived ones. The DuckDB build
reads every `*.parquet` in the works directory, so the supplement is included
automatically.

Tier 1 papers (foundation §5):
  1. Zador 2023 Nat Commun           — 10.1038/s41467-023-37180-x
  2. Richards 2019 Nat Neurosci       — 10.1038/s41593-019-0520-2
  3. Hassabis 2017 Neuron             — 10.1016/j.neuron.2017.06.011
  4. Kriegeskorte-Douglas 2018 NN     — 10.1038/s41593-018-0210-5
"""

from __future__ import annotations

import json
import sys
import time

import requests

from neuroai_cn import config

DATA_ROOT = config.DATA_ROOT
PARQUET_DIR = config.PARQUET_DIR / "works"
OUT_FILE = PARQUET_DIR / "_tier1_supplement.parquet"

TIER1_DOIS = [
    ("Zador 2023 Nat Commun", "10.1038/s41467-023-37180-x"),
    ("Richards 2019 Nat Neurosci", "10.1038/s41593-019-0520-2"),
    ("Hassabis 2017 Neuron", "10.1016/j.neuron.2017.06.011"),
    ("Kriegeskorte-Douglas 2018", "10.1038/s41593-018-0210-5"),
]

# The fields we keep in the snapshot projection (must match
# convert_works_partition.py WORKS_PROJECTION exactly so the supplement
# parquet schema matches the snapshot ones — DuckDB read_parquet over a glob
# requires identical schemas).
KEEP_FIELDS = [
    "id",
    "doi",
    "title",
    "display_name",
    "publication_year",
    "publication_date",
    "type",
    "language",
    "is_paratext",
    "is_retracted",
    "cited_by_count",
    "fwci",
    "citation_normalized_percentile",
    "authorships",
    "primary_location",
    "primary_topic",
    "topics",
    "concepts",
    "referenced_works",
    "referenced_works_count",
    "related_works",
    "counts_by_year",
    "updated_date",
    "created_date",
]


def fetch_one(doi: str) -> dict | None:
    url = f"https://api.openalex.org/works/doi:{doi}"
    headers = {"User-Agent": config.openalex_user_agent("neuroai-citation-network/0.1.0")}
    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=30)
            if r.status_code == 200:
                return r.json()
            print(f"  attempt {attempt + 1}: HTTP {r.status_code}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  attempt {attempt + 1}: {e}", file=sys.stderr)
        time.sleep(2 * (attempt + 1))
    return None


def main() -> None:
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    fetched = []
    for name, doi in TIER1_DOIS:
        print(f"Fetching {name} ({doi})...")
        rec = fetch_one(doi)
        if rec is None:
            print(f"  FAILED — skipping {name}")
            continue
        # Project to the snapshot schema
        slim = {k: rec.get(k) for k in KEEP_FIELDS}
        # Normalize: API returns DOI as full URL, snapshot stores as full URL too
        # Some fields the API returns as nested objects we need to strip / coerce
        fetched.append(slim)
        print(f"  ✅ {name}: {slim['publication_year']}, {slim['cited_by_count']:,} citations")

    if not fetched:
        print("No Tier 1 papers fetched. Exiting without writing supplement.")
        sys.exit(1)

    # Write via duckdb so the parquet schema matches snapshot output exactly
    import duckdb

    con = duckdb.connect()
    # Materialise fetched records as in-memory JSON, then SELECT into parquet
    json_blob = "[" + ", ".join(json.dumps(r) for r in fetched) + "]"
    tmp = DATA_ROOT / "tmp" / "_tier1_supplement.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json_blob)

    # Build the projection so column order/types match the snapshot files.
    proj = ", ".join(KEEP_FIELDS)
    con.execute(f"""
        COPY (
            SELECT {proj}
            FROM read_json('{tmp}', format='array',
                           maximum_object_size=33554432)
        ) TO '{OUT_FILE}'
        (FORMAT PARQUET, COMPRESSION 'snappy', ROW_GROUP_SIZE 100000)
    """)
    tmp.unlink()

    n = con.execute(f"SELECT COUNT(*) FROM read_parquet('{OUT_FILE}')").fetchone()[0]
    print(f"\nWrote {OUT_FILE} ({n} rows)")


if __name__ == "__main__":
    main()

"""Convert a single OpenAlex works `updated_date=YYYY-MM-DD/` partition to parquet.

Used by works_incremental.sh inside the download-convert-delete loop.
Output goes to <NEUROAI_DATA>/data/parquet/works/
year-partitioned by publication_year.

Usage:
    python scripts/convert_works_partition.py updated_date=2025-12-01
"""

from __future__ import annotations

import os
import sys
import time

import duckdb

from neuroai_cn import config

DATA_ROOT = config.DATA_ROOT
SNAPSHOT_DIR = config.SNAPSHOT_DIR / "works"
PARQUET_DIR = config.PARQUET_DIR / "works"
TMP_DIR = config.TMP_DIR

os.environ["TMPDIR"] = str(TMP_DIR)
TMP_DIR.mkdir(parents=True, exist_ok=True)
PARQUET_DIR.mkdir(parents=True, exist_ok=True)

WORKS_PROJECTION = """
    id, doi, title, display_name, publication_year, publication_date,
    type, language, is_paratext, is_retracted,
    cited_by_count, fwci, citation_normalized_percentile,
    authorships, primary_location, primary_topic, topics, concepts,
    referenced_works, referenced_works_count, related_works,
    counts_by_year, updated_date, created_date
"""


def convert(partition: str) -> None:
    src_dir = SNAPSHOT_DIR / partition
    if not src_dir.exists():
        raise FileNotFoundError(f"Partition not found: {src_dir}")

    files = sorted(src_dir.glob("*.gz"))
    if not files:
        print(f"[{partition}] no .gz files; skipping")
        return

    # Use a tag in the parquet filename that encodes the source partition,
    # so re-runs and per-file batches don't collide.
    tag = partition.replace("updated_date=", "ud").replace("-", "")

    # Write one parquet file per source partition (no year partitioning).
    # Year partitioning was 5x slower because PARTITION_BY (publication_year)
    # creates ~127 year directories × ~3 files each = ~400 small files per source
    # partition. The DuckDB build doesn't need the year directories; it filters
    # via the publication_year column directly using parquet column statistics.
    out_file = PARQUET_DIR / f"{tag}.parquet"

    paths = "[" + ", ".join(f"'{f}'" for f in files) + "]"

    con = duckdb.connect()
    con.execute(f"SET temp_directory='{TMP_DIR}'")
    con.execute("SET memory_limit='30GB'")
    con.execute("SET threads=12")
    con.execute("SET preserve_insertion_order=false")

    t0 = time.time()
    con.execute(f"""
        COPY (
            SELECT {WORKS_PROJECTION}
            FROM read_json({paths}, format='newline_delimited',
                           compression='gzip', ignore_errors=true,
                           maximum_object_size=33554432)
            WHERE publication_year IS NOT NULL
              AND publication_year BETWEEN 1900 AND 2026
        ) TO '{out_file}'
        (FORMAT PARQUET, COMPRESSION 'snappy', ROW_GROUP_SIZE 100000)
    """)
    dt = time.time() - t0
    sz = out_file.stat().st_size / 1024**3
    print(f"[{partition}] {len(files)} files → {out_file.name} ({sz:.2f} GB) in {dt:.1f}s")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    convert(sys.argv[1])

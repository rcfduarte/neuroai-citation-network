"""Convert one OpenAlex snapshot partition (gzipped JSONL) to parquet.

Usage:
    python scripts/convert_to_parquet.py <partition>

E.g.:
    python scripts/convert_to_parquet.py topics

Reads from <NEUROAI_DATA>/data/openalex-snapshot/<partition>/
Writes to <NEUROAI_DATA>/data/parquet/<partition>/
Uses snappy compression. For `works`, partitions output by publication_year.

Strategy: use DuckDB to read gzipped JSONL files in chunks (per .gz file), project
to a minimal schema (drop heavy fields like abstract_inverted_index), and write
parquet. DuckDB handles streaming well; polars would load everything into RAM.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import duckdb

from neuroai_cn import config

DATA_ROOT = config.DATA_ROOT
SNAPSHOT_DIR = config.SNAPSHOT_DIR
PARQUET_DIR = config.PARQUET_DIR
TMP_DIR = config.TMP_DIR

os.environ["TMPDIR"] = str(TMP_DIR)

# Per-partition projections. Drop heavy fields not needed for Q1-Q4.
PROJECTIONS = {
    "topics": "*",
    "concepts": "*",
    "sources": "*",
    "institutions": "*",
    "publishers": "*",
    "funders": "*",
    "authors": """
        id, orcid, display_name, display_name_alternatives, works_count,
        cited_by_count, last_known_institutions, affiliations,
        works_api_url, updated_date, created_date
    """,
    # Works: drop abstract_inverted_index, keywords, mesh, sustainable_development_goals,
    # grants, apc_paid, locations (keep only primary_location).
    # Note: OpenAlex schema as of 2026-04 — `type_crossref` no longer exists.
    "works": """
        id, doi, title, display_name, publication_year, publication_date,
        type, language, is_paratext, is_retracted,
        cited_by_count, fwci, citation_normalized_percentile,
        authorships, primary_location, primary_topic, topics, concepts,
        referenced_works, referenced_works_count, related_works,
        counts_by_year, updated_date, created_date
    """,
}


def list_jsonl_files(partition: str) -> list[Path]:
    src = SNAPSHOT_DIR / partition
    if not src.exists():
        raise FileNotFoundError(f"Snapshot partition not found: {src}")
    files = sorted(src.rglob("*.gz"))
    if not files:
        raise FileNotFoundError(f"No .gz files in {src}")
    return files


def convert_partition(partition: str) -> None:
    if partition not in PROJECTIONS:
        raise ValueError(f"Unknown partition: {partition}. Known: {list(PROJECTIONS)}")
    projection = PROJECTIONS[partition]
    out_dir = PARQUET_DIR / partition
    out_dir.mkdir(parents=True, exist_ok=True)

    files = list_jsonl_files(partition)
    print(f"[{partition}] {len(files)} .gz files; output={out_dir}")

    # DuckDB: configure to use TMPDIR on data drive.
    con = duckdb.connect()
    con.execute(f"SET temp_directory='{TMP_DIR}'")
    con.execute("SET memory_limit='12GB'")
    con.execute("SET threads=8")

    if partition == "works":
        # Year-partitioned output via Hive partitioning.
        # Process in batches of N files to control memory.
        batch_size = 4
        for i in range(0, len(files), batch_size):
            batch = files[i : i + batch_size]
            paths = "[" + ", ".join(f"'{p}'" for p in batch) + "]"
            t0 = time.time()
            con.execute(f"""
                COPY (
                    SELECT {projection}
                    FROM read_json({paths}, format='newline_delimited',
                                   compression='gzip', ignore_errors=true,
                                   maximum_object_size=33554432)
                    WHERE publication_year IS NOT NULL
                      AND publication_year BETWEEN 1900 AND 2026
                ) TO '{out_dir}'
                (FORMAT PARQUET, COMPRESSION 'snappy',
                 PARTITION_BY (publication_year),
                 OVERWRITE_OR_IGNORE,
                 FILENAME_PATTERN 'works_batch{i:04d}_{{uuid}}')
            """)
            dt = time.time() - t0
            print(
                f"  [works batch {i // batch_size + 1}/{(len(files) + batch_size - 1) // batch_size}] "
                f"{len(batch)} files in {dt:.1f}s"
            )
    else:
        # Single-file partitions: write all at once.
        paths = "[" + ", ".join(f"'{p}'" for p in files) + "]"
        t0 = time.time()
        out_file = out_dir / f"{partition}.parquet"
        con.execute(f"""
            COPY (
                SELECT {projection}
                FROM read_json({paths}, format='newline_delimited',
                               compression='gzip', ignore_errors=true,
                               maximum_object_size=33554432)
            ) TO '{out_file}'
            (FORMAT PARQUET, COMPRESSION 'snappy')
        """)
        dt = time.time() - t0
        size_mb = out_file.stat().st_size / 1024 / 1024
        print(f"  [{partition}] {len(files)} files → {size_mb:.1f} MB parquet in {dt:.1f}s")

    # Validation: row count.
    if partition == "works":
        n = con.execute(f"SELECT COUNT(*) FROM read_parquet('{out_dir}/**/*.parquet')").fetchone()[
            0
        ]
    else:
        n = con.execute(f"SELECT COUNT(*) FROM read_parquet('{out_dir}/*.parquet')").fetchone()[0]
    print(f"[{partition}] DONE — {n:,} rows in parquet")


def main() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    convert_partition(sys.argv[1])


if __name__ == "__main__":
    main()

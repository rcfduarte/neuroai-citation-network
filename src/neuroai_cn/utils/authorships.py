"""Pre-computed authorship edges cache.

`works.authorships` is a nested STRUCT[] column. Every pool that filters by
author identity has to UNNEST 42M works × ~5 authors = ~210M intermediate
rows, which costs minutes per query. We materialize this once into a flat
(work_id, year, author_id) parquet so subsequent pool joins are sub-minute
hash JOINs.

The cache lives at `data/derived/_authorships.parquet` and is rebuilt only
when missing or when explicitly requested. It is invalidated implicitly when
the DuckDB index is rebuilt (newer mtime than the cache).
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import duckdb

from . import DUCKDB_PATH
from .duckdb import derived_dir

logger = logging.getLogger(__name__)


def authorships_cache_path() -> Path:
    """Sentinel file (zero-byte marker that the dataset is built and fresh)."""
    return derived_dir() / "_authorships.cache_built"


def authorships_dataset_glob() -> str:
    """Glob to read the dataset via `read_parquet(...)`."""
    return str(derived_dir() / "_authorships_parts" / "*.parquet")


def authorships_dataset_files() -> list[str]:
    """Explicit list of complete (non-zero-byte) parquet files in the cache.

    Use this in place of the glob when a build might be in flight — DuckDB's
    `read_parquet` chokes on a 0-byte placeholder file. Returns absolute paths.
    """
    parts_dir = derived_dir() / "_authorships_parts"
    if not parts_dir.exists():
        return []
    return sorted(str(p) for p in parts_dir.glob("*.parquet") if p.stat().st_size > 0)


def is_cache_stale(cache: Path | None = None) -> bool:
    """True if cache is missing or older than the DuckDB index."""
    cache = cache or authorships_cache_path()
    if not cache.exists():
        return True
    parts_dir = derived_dir() / "_authorships_parts"
    if not parts_dir.exists() or not list(parts_dir.glob("*.parquet")):
        return True
    duck = Path(DUCKDB_PATH)
    if not duck.exists():
        return False
    return cache.stat().st_mtime < duck.stat().st_mtime


HEAVY_PARTITION_BYTES = 5 * 10**9  # 5 GB — anything bigger gets HASH-chunked


def _n_chunks_for(size_bytes: int) -> int:
    """Pick chunk count so each chunk's UNNEST output stays <~50M rows."""
    gb = size_bytes / 1e9
    return max(8, min(64, round(gb / 4)))


def _connect_tuned(threads: int, memory_limit: str) -> duckdb.DuckDBPyConnection:
    from . import DATA_ROOT

    c = duckdb.connect(":memory:")
    c.execute(f"PRAGMA threads={threads}")
    c.execute(f"PRAGMA memory_limit='{memory_limit}'")
    # Spill to a scratch directory outside the (busy) drive that holds openalex.duckdb.
    spill = os.environ.get("NEUROAI_DUCKDB_TMP", f"{DATA_ROOT}/tmp")
    Path(spill).mkdir(parents=True, exist_ok=True)
    c.execute(f"PRAGMA temp_directory='{spill}'")
    c.execute("PRAGMA preserve_insertion_order=false")
    return c


def _write_unnested(
    c: duckdb.DuckDBPyConnection,
    src: Path,
    out: Path,
    *,
    chunk_idx: int | None = None,
    n_chunks: int | None = None,
) -> int:
    """COPY (UNNEST) over `src` writing to `out`. Returns row count.

    If chunk_idx + n_chunks are given, only rows where `HASH(w.id) % n_chunks
    == chunk_idx` are processed — DuckDB pushes this filter pre-UNNEST so
    only ~1/n_chunks of the source rows enter the multiplying UNNEST stage.
    """
    if chunk_idx is None or n_chunks is None:
        chunk_clause = ""
    else:
        # `hash(...)` is unsigned 64-bit; `% n_chunks` distributes uniformly.
        chunk_clause = f"AND (hash(w.id) % {n_chunks}) = {chunk_idx}"
    c.execute(
        f"""
        COPY (
          SELECT
            w.id AS work_id,
            w.publication_year AS year,
            a.author.id AS author_id,
            a.author_position AS author_position
          FROM read_parquet('{src}') w, UNNEST(w.authorships) AS t(a)
          WHERE w.publication_year BETWEEN 1990 AND 2026
            AND a.author.id IS NOT NULL
            {chunk_clause}
        ) TO '{out}' (FORMAT 'parquet', COMPRESSION 'snappy', ROW_GROUP_SIZE 100000)
        """
    )
    return int(c.execute(f"SELECT COUNT(*) FROM read_parquet('{out}')").fetchone()[0])


def build_cache(
    con: duckdb.DuckDBPyConnection | None = None,
    *,
    threads: int = 1,
    memory_limit: str = "6GB",
) -> Path:
    """Materialize `(work_id, year, author_id, author_position)` per work.

    Per-partition pattern: fresh in-memory DuckDB → COPY ... UNNEST → write a
    parquet under `_authorships_parts/`. Atomic via `.partial` rename.

    Heavy partitions (>5 GB — the OpenAlex bulk re-exports like ud20251010 at
    30 GB and ud20251106 at 198 GB) are split into N hash-bucketed chunks via
    `HASH(w.id) % N` filter; pushdown applies this *pre-UNNEST* so only ~1/N
    of the source enters the multiplying UNNEST. Each partition produces 1
    output (small) OR N outputs `<partition>__chunk_{idx:02d}_of_{N:02d}.parquet`
    (heavy). Consumers read the union via glob — extra files don't matter.
    Chunk count: max(8, min(64, ceil(size_gb / 4))).
    """
    from . import DATA_ROOT

    parts_dir = derived_dir() / "_authorships_parts"
    parts_dir.mkdir(parents=True, exist_ok=True)

    works_parquet_dir = DATA_ROOT / "data" / "parquet" / "works"
    files = sorted(works_parquet_dir.glob("*.parquet"))
    if not files:
        raise RuntimeError(f"No works parquets found in {works_parquet_dir}")

    logger.info(
        "Building authorships cache from %d partition files (threads=%d, memory_limit=%s)",
        len(files),
        threads,
        memory_limit,
    )
    t0 = time.time()
    n_total_edges = 0
    skipped_existing = 0
    for f in files:
        size_bytes = f.stat().st_size
        is_heavy = size_bytes >= HEAVY_PARTITION_BYTES
        if is_heavy:
            stem = f.stem
            n_chunks = _n_chunks_for(size_bytes)
            outs = [
                parts_dir / f"{stem}__chunk_{i:02d}_of_{n_chunks:02d}.parquet"
                for i in range(n_chunks)
            ]
            if all(p.exists() and p.stat().st_size > 0 for p in outs):
                skipped_existing += 1
                continue
            logger.info(
                "  HEAVY %s (%.1f GB) — splitting into %d HASH-bucketed chunks",
                f.name,
                size_bytes / 1e9,
                n_chunks,
            )
            for chunk_idx, out_part in enumerate(outs):
                if out_part.exists() and out_part.stat().st_size > 0:
                    continue
                out_partial = out_part.with_suffix(".parquet.partial")
                if out_partial.exists():
                    out_partial.unlink()
                c = _connect_tuned(threads, memory_limit)
                try:
                    n = _write_unnested(c, f, out_partial, chunk_idx=chunk_idx, n_chunks=n_chunks)
                finally:
                    c.close()
                out_partial.rename(out_part)
                n_total_edges += n
                logger.info(
                    "    %s chunk %d/%d → %d edges, %.1f MB",
                    f.name,
                    chunk_idx + 1,
                    n_chunks,
                    n,
                    out_part.stat().st_size / 1e6,
                )
            continue

        # Small partition — single shot.
        out_part = parts_dir / f.name
        if out_part.exists() and out_part.stat().st_size > 0:
            skipped_existing += 1
            continue
        out_partial = out_part.with_suffix(".parquet.partial")
        if out_partial.exists():
            out_partial.unlink()
        c = _connect_tuned(threads, memory_limit)
        try:
            n = _write_unnested(c, f, out_partial)
        finally:
            c.close()
        out_partial.rename(out_part)
        n_total_edges += n
        logger.info("  %s → %d edges, %.1f MB", f.name, n, out_part.stat().st_size / 1e6)

    # Build a pointer file (single-file view) by writing a 0-byte sentinel
    # parquet at the canonical path; consumers read the dataset via the parts
    # directory path returned by `authorships_dataset_path()`.
    sentinel = authorships_cache_path()
    sentinel.touch(exist_ok=True)

    elapsed = time.time() - t0
    logger.info(
        "Authorships cache: %d edges across %d parts (%d skipped fresh) in %.1fs",
        n_total_edges,
        len(files) - skipped_existing,
        skipped_existing,
        elapsed,
    )
    return parts_dir


def ensure_cache(
    con: duckdb.DuckDBPyConnection | None = None, *, allow_partial: bool = False
) -> str:
    """Build the cache if stale; return a SQL-quoted file list ready for `read_parquet(...)`.

    The return value is a DuckDB `read_parquet` argument that names every
    *complete* (non-zero-byte) parquet in the parts directory. Using an
    explicit file list — instead of a glob — avoids the failure mode where
    the glob matches a 0-byte placeholder file written by an in-flight
    builder.

    With `allow_partial=True`, skip the build if any complete parts exist,
    even when the sentinel is missing (a build is in progress or interrupted).
    """
    cache = authorships_cache_path()
    if is_cache_stale(cache):
        if allow_partial:
            files = authorships_dataset_files()
            if files:
                logger.warning(
                    "Authorships cache partial (%d complete parts, sentinel missing). Using as-is.",
                    len(files),
                )
                return _files_to_sql_list(files)
        build_cache(con)
    else:
        logger.debug("Authorships cache fresh: %s", cache)
    files = authorships_dataset_files()
    return _files_to_sql_list(files)


def _files_to_sql_list(files: list[str]) -> str:
    """Render a list of file paths as a DuckDB array literal, e.g. ['p1','p2']."""
    if not files:
        # An empty list confuses DuckDB; fall back to glob (which will also be empty).
        return authorships_dataset_glob()
    return "[" + ",".join("'" + f.replace("'", "''") + "'" for f in files) + "]"


def _cli() -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Rebuild even if fresh")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    if args.force:
        # Wipe sentinel + parts so build_cache regenerates everything.
        sentinel = authorships_cache_path()
        if sentinel.exists():
            sentinel.unlink()
        parts_dir = derived_dir() / "_authorships_parts"
        if parts_dir.exists():
            for p in parts_dir.glob("*.parquet"):
                p.unlink()
        build_cache()
    else:
        ensure_cache()
    glob = authorships_dataset_glob()
    parts = sorted((derived_dir() / "_authorships_parts").glob("*.parquet"))
    total = sum(p.stat().st_size for p in parts) / 1e9
    print(
        json.dumps(
            {"glob": glob, "n_parts": len(parts), "total_size_gb": round(total, 1)}, indent=2
        )
    )


if __name__ == "__main__":
    _cli()

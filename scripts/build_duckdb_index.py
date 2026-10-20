"""Build the DuckDB index file from parquet partitions.

Usage:
    python scripts/build_duckdb_index.py [--fresh]

By default the build is **resumable**: a sidecar JSON tracks which ud*.parquet
files have been ingested into the works table; if the DuckDB exists and the
sidecar is intact, only un-ingested partitions are inserted. Pass `--fresh`
to wipe the DuckDB + sidecar and start clean.

Creates <NEUROAI_DATA>/data/openalex.duckdb with:
    - works               (filtered to 1990 ≤ publication_year ≤ 2026)
    - authors
    - sources
    - institutions
    - topics
    - citation_edges      (denormalized works.referenced_works)

Indexes are built on (publication_year, doi, source-id, citing/cited work_id).

Schema-drift handling. The 381 ud*.parquet snapshot files have 27 distinct
top-level schemas because DuckDB's `read_json` (in convert_works_partition.py)
falls back to `JSON` typing for columns that are sparse / NULL-dominant in a
given partition. We tolerate this by:

1. Pre-creating an empty `works` skeleton from a known-good "variant 1"
   partition (`ud20260330.parquet`).
2. Looping over every ud*.parquet and using `INSERT INTO works BY NAME` —
   DuckDB coerces JSON-typed columns into the skeleton's target types
   automatically (verified across variants 1, 2, 21, 22).
3. Excluding `_tier1_supplement.parquet` (its `primary_location.source` STRUCT
   carries extra fields not present in the snapshot — all 4 Tier 1 DOIs are
   independently in the snapshot anyway).

OOM resilience. The previous 30GB memory_limit + 12-thread setting OOM-killed
the python process (48GB anon-rss) ~84 min into a fresh build. Memory limits
are now 18GB / 6 threads, and per-partition flushes via `CHECKPOINT` keep
DuckDB's WAL from accumulating.
"""

from __future__ import annotations

import argparse
import json
import os
import time

import duckdb

from neuroai_cn import config

DATA_ROOT = config.DATA_ROOT
PARQUET_DIR = config.PARQUET_DIR
DUCKDB_PATH = config.DUCKDB_PATH
SIDECAR_PATH = DATA_ROOT / "data" / "openalex.duckdb.build_progress.json"
TMP_DIR = config.TMP_DIR

# A "variant 1" partition — used as the schema template for the works table.
# 203/381 partitions share this schema; the rest type-coerce into it.
WORKS_SKELETON_PARTITION = "ud20260330.parquet"

os.environ["TMPDIR"] = str(TMP_DIR)
TMP_DIR.mkdir(parents=True, exist_ok=True)


def _load_progress() -> dict:
    if not SIDECAR_PATH.exists():
        return {"works_done": [], "stage": "init"}
    try:
        return json.loads(SIDECAR_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {"works_done": [], "stage": "init"}


def _save_progress(progress: dict) -> None:
    SIDECAR_PATH.write_text(json.dumps(progress, indent=2))


def build(fresh: bool = False) -> None:
    if fresh and DUCKDB_PATH.exists():
        print(f"  --fresh: removing {DUCKDB_PATH}")
        DUCKDB_PATH.unlink()
        if SIDECAR_PATH.exists():
            SIDECAR_PATH.unlink()

    # State reconciliation: only resume if DuckDB *and* sidecar both exist.
    # A DuckDB without a sidecar is stale (e.g. from an OOM-killed pre-resumability
    # build) — wipe it. A sidecar without a DuckDB is also stale — drop the sidecar.
    if DUCKDB_PATH.exists() and not SIDECAR_PATH.exists():
        print(
            "  DuckDB exists but no sidecar — treating as stale and wiping for clean rebuild",
            flush=True,
        )
        DUCKDB_PATH.unlink()
    if SIDECAR_PATH.exists() and not DUCKDB_PATH.exists():
        SIDECAR_PATH.unlink()

    progress = _load_progress() if DUCKDB_PATH.exists() else {"works_done": [], "stage": "init"}

    resuming = bool(progress["works_done"])
    if resuming:
        print(
            f"  RESUME: DuckDB exists, sidecar shows {len(progress['works_done'])} "
            f"works partitions already inserted (stage={progress['stage']})",
            flush=True,
        )

    con = duckdb.connect(str(DUCKDB_PATH))
    con.execute(f"SET temp_directory='{TMP_DIR}'")
    # OOM-killed the process at 30GB / 12 threads (kernel saw 48GB anon-rss).
    # 18GB / 6 threads keeps the host healthy alongside the ~30 MCP servers
    # that run during normal operation.
    con.execute("SET memory_limit='18GB'")
    con.execute("SET threads=6")

    def mk(name: str, glob: str, where: str = "", union_by_name: bool = False) -> None:
        t0 = time.time()
        path = PARQUET_DIR / glob
        opts = ", union_by_name=true" if union_by_name else ""
        sql = f"CREATE TABLE {name} AS SELECT * FROM read_parquet('{path}'{opts})"
        if where:
            sql += f" WHERE {where}"
        con.execute(sql)
        n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        print(f"  [{name}] {n:,} rows in {time.time() - t0:.1f}s")

    print("Building tables...", flush=True)

    # Works: build via skeleton + per-file INSERT BY NAME to absorb cross-
    # partition schema drift (see docstring). Resumable via sidecar JSON.
    works_dir = PARQUET_DIR / "works"
    skeleton = works_dir / WORKS_SKELETON_PARTITION
    if not skeleton.exists():
        raise FileNotFoundError(f"Skeleton partition not found: {skeleton}")

    t_works = time.time()
    if not resuming:
        print(f"  [works] creating skeleton from {WORKS_SKELETON_PARTITION}", flush=True)
        con.execute(
            f"""
            CREATE TABLE works AS
            SELECT * FROM read_parquet('{skeleton}')
            WHERE 1=0
            """
        )
        progress["stage"] = "works_inserting"
        _save_progress(progress)

    done_set = set(progress["works_done"])
    files = sorted(works_dir.glob("ud*.parquet"))
    pending = [f for f in files if f.name not in done_set]
    print(
        f"  [works] {len(done_set)} already done, {len(pending)} pending of "
        f"{len(files)} total partitions",
        flush=True,
    )
    failed: list[tuple[str, str]] = []
    n_new_inserted = 0
    for i, f in enumerate(pending, 1):
        t_f = time.time()
        try:
            con.execute(
                f"""
                INSERT INTO works BY NAME
                SELECT * FROM read_parquet('{f}')
                WHERE publication_year BETWEEN 1990 AND 2026
                """
            )
            con.execute("CHECKPOINT")
            n_new_inserted += 1
            progress["works_done"].append(f.name)
            _save_progress(progress)
            done_count = len(progress["works_done"])
            if done_count % 20 == 0 or done_count == len(files) or i == len(pending):
                total = con.execute("SELECT COUNT(*) FROM works").fetchone()[0]
                print(
                    f"    [works] {done_count}/{len(files)} done; this partition "
                    f"{f.name} took {time.time() - t_f:.1f}s; running total "
                    f"{total:,} rows",
                    flush=True,
                )
        except duckdb.Error as e:
            print(f"    [works] SKIP {f.name}: {str(e)[:150]}", flush=True)
            failed.append((f.name, str(e)[:200]))
    n_works = con.execute("SELECT COUNT(*) FROM works").fetchone()[0]
    print(
        f"  [works] FINAL {n_works:,} rows from {len(progress['works_done'])}/"
        f"{len(files)} partitions in {time.time() - t_works:.1f}s "
        f"({n_new_inserted} new this run)",
        flush=True,
    )
    if failed:
        print(f"  [works] {len(failed)} partitions failed this run:", flush=True)
        for name, err in failed:
            print(f"    - {name}: {err[:80]}", flush=True)
    progress["stage"] = "works_done"
    _save_progress(progress)

    # Skip the small lookup tables if already present (resume case).
    for tbl, glob in [
        ("authors", "authors/*.parquet"),
        ("sources", "sources/*.parquet"),
        ("institutions", "institutions/*.parquet"),
        ("topics", "topics/*.parquet"),
    ]:
        exists = (
            con.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = ?",
                [tbl],
            ).fetchone()
            is not None
        )
        if exists:
            n = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            print(f"  [{tbl}] {n:,} rows (already built — skipping)", flush=True)
        else:
            mk(tbl, glob)

    edges_exists = (
        con.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'citation_edges'",
        ).fetchone()
        is not None
    )
    if edges_exists:
        n = con.execute("SELECT COUNT(*) FROM citation_edges").fetchone()[0]
        print(f"  [citation_edges] {n:,} rows (already built — skipping)", flush=True)
    else:
        print(
            "Building citation_edges (denormalised from works.referenced_works)...",
            flush=True,
        )
        t0 = time.time()
        con.execute("""
            CREATE TABLE citation_edges AS
            SELECT
                w.id AS citing_work_id,
                w.publication_year AS citing_year,
                unnest(w.referenced_works) AS cited_work_id
            FROM works w
            WHERE w.referenced_works IS NOT NULL
              AND len(w.referenced_works) > 0
        """)
        n = con.execute("SELECT COUNT(*) FROM citation_edges").fetchone()[0]
        print(f"  [citation_edges] {n:,} rows in {time.time() - t0:.1f}s", flush=True)
        progress["stage"] = "edges_done"
        _save_progress(progress)

    print("Building indexes...", flush=True)
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_works_year ON works(publication_year)",
        "CREATE INDEX IF NOT EXISTS idx_works_doi ON works(doi)",
        "CREATE INDEX IF NOT EXISTS idx_works_id ON works(id)",
        "CREATE INDEX IF NOT EXISTS idx_authors_id ON authors(id)",
        "CREATE INDEX IF NOT EXISTS idx_authors_orcid ON authors(orcid)",
        "CREATE INDEX IF NOT EXISTS idx_sources_id ON sources(id)",
        "CREATE INDEX IF NOT EXISTS idx_topics_id ON topics(id)",
        "CREATE INDEX IF NOT EXISTS idx_edges_citing ON citation_edges(citing_work_id)",
        "CREATE INDEX IF NOT EXISTS idx_edges_cited ON citation_edges(cited_work_id)",
        "CREATE INDEX IF NOT EXISTS idx_edges_year ON citation_edges(citing_year)",
    ]
    for idx in indexes:
        t0 = time.time()
        try:
            con.execute(idx)
            print(f"  {idx.split()[5]} in {time.time() - t0:.1f}s", flush=True)
        except duckdb.Error as e:
            print(f"  SKIP {idx}: {e}", flush=True)

    progress["stage"] = "indexes_done"
    _save_progress(progress)
    con.close()
    size_gb = DUCKDB_PATH.stat().st_size / 1024**3
    print(f"\nDone — {DUCKDB_PATH} ({size_gb:.1f} GB)", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh", action="store_true", help="wipe DuckDB + sidecar before build")
    args = parser.parse_args()
    build(fresh=args.fresh)

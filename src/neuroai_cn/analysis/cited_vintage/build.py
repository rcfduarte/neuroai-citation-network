"""Heavy stage: extract the citation-edge tables the vintage analyses are computed from.

Run one stage at a time (one heavy DuckDB job at a time, read-only against the mirror):

    python -m neuroai_cn.analysis.cited_vintage.build --stage labels
    python -m neuroai_cn.analysis.cited_vintage.build --stage edges
    python -m neuroai_cn.analysis.cited_vintage.build --stage cross
    python -m neuroai_cn.analysis.cited_vintage.build --stage refage

Stages and outputs (parquet, under ``DERIVED_DIR/vintage/`` unless ``--out`` is given; these are
large and not tracked):

    labels   wl.parquet, lk.parquet     every AI or neuroscience work (labels, subfield, topic, a
                                        flag for a secondary topic in the other field) and a
                                        (work id, year) lookup for every work in the mirror
    edges    ce.parquet                 every citation edge whose citing paper is AI or neuroscience
    cross    cross_edges.parquet,       edge-level AI->neuroscience and neuroscience->AI table, and
             cited_works.parquet        one row per cited work with its title
    refage   ../../results/vintage/matrix_reference_age.csv and the reference-list coverage table

``--years LO HI`` restricts the citing years (and, in ``labels``, the work years to <= HI) so a
small slice can be recomputed for tests; the tracked matrices are then compared on that slice.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from ... import config
from ...utils.duckdb import get_connection
from .definitions import (
    CITING_YEAR_MAX,
    CITING_YEAR_MIN,
    ai_condition,
    neuro_condition,
    strict_ai_condition,
)

DEFAULT_OUT = config.DERIVED_DIR / "vintage"
MATRIX_REFAGE = config.RESULTS_DIR / "vintage" / "matrix_reference_age.csv"
COVERAGE_REFAGE = config.RESULTS_DIR / "vintage" / "reference_list_coverage.csv"


def connect(memory: str = "12GB", threads: int = 8):
    con = get_connection(read_only=True)
    config.TMP_DIR.mkdir(parents=True, exist_ok=True)
    con.execute(f"PRAGMA memory_limit='{memory}'")
    con.execute(f"PRAGMA threads={threads}")
    con.execute(f"PRAGMA temp_directory='{config.TMP_DIR}'")
    con.execute("PRAGMA preserve_insertion_order=false")
    return con


def _log(msg: str, t0: float) -> None:
    print(f"[{time.time() - t0:7.1f}s] {msg}", flush=True)


def stage_labels(out: Path, year_max: int = 2026) -> None:
    con = connect()
    t0 = time.time()
    neuro = neuro_condition("w.primary_topic")
    ai = ai_condition("w.primary_topic")
    con.execute(
        f"""
        COPY (
          SELECT w.id, CAST(substr(w.id, 23) AS BIGINT) AS wid,
                 CAST(w.publication_year AS SMALLINT) AS year, w.type,
                 CASE WHEN {neuro} THEN 'neuro' ELSE 'ai' END AS cls,
                 (NOT ({neuro}) AND {strict_ai_condition("w.primary_topic")}) AS strict_ai,
                 w.primary_topic.subfield.id AS sf_id,
                 w.primary_topic.subfield.display_name AS sf_name,
                 w.primary_topic.id AS topic_id,
                 w.primary_topic.display_name AS topic_name,
                 coalesce(CASE WHEN {neuro}
                      THEN len(list_filter(w.topics, t -> {ai_condition("t")})) > 0
                      ELSE len(list_filter(w.topics, t -> {neuro_condition("t")})) > 0 END,
                      false) AS dual,
                 w.cited_by_count, w.referenced_works_count
          FROM works w
          WHERE w.primary_topic IS NOT NULL AND ({neuro} OR {ai})
            AND w.publication_year BETWEEN 1990 AND {year_max}
        ) TO '{out}/wl.parquet' (FORMAT parquet, COMPRESSION zstd)
        """
    )
    _log("wl.parquet written", t0)
    con.execute(
        f"""
        COPY (SELECT CAST(substr(id, 23) AS BIGINT) AS wid,
                     CAST(publication_year AS SMALLINT) AS yr
              FROM works WHERE publication_year <= {year_max})
        TO '{out}/lk.parquet' (FORMAT parquet, COMPRESSION zstd)
        """
    )
    _log("lk.parquet written", t0)
    n = con.execute(
        f"SELECT cls, count(*) FROM read_parquet('{out}/wl.parquet') GROUP BY 1"
    ).fetchall()
    print(n)


def stage_edges(out: Path, lo: int, hi: int) -> None:
    con = connect()
    t0 = time.time()
    con.execute(
        f"""
        CREATE TEMP TABLE s AS
        SELECT id, wid, cls, CASE WHEN type IN ('article','review') THEN 1 ELSE 0 END AS ar
        FROM read_parquet('{out}/wl.parquet')
        """
    )
    con.execute(
        f"""
        COPY (
          SELECT s.wid AS citing, e.citing_year, s.cls, s.ar,
                 CAST(substr(e.cited_work_id, 23) AS BIGINT) AS cited
          FROM citation_edges e JOIN s ON s.id = e.citing_work_id
          WHERE e.citing_year BETWEEN {lo} AND {hi}
        ) TO '{out}/ce.parquet' (FORMAT parquet, COMPRESSION zstd)
        """
    )
    _log("ce.parquet written", t0)
    print(con.execute(f"SELECT count(*) FROM read_parquet('{out}/ce.parquet')").fetchone())


def stage_cross(out: Path) -> None:
    con = connect()
    t0 = time.time()
    con.execute(
        f"""
        COPY (
          SELECT c.citing, c.citing_year, s.year AS citing_year_work, c.cls AS citing_cls,
                 s.type AS citing_type, s.strict_ai AS citing_strict, s.dual AS citing_dual,
                 c.cited, t.id AS cited_id, t.year AS cited_year, t.cls AS cited_cls, t.sf_id, t.sf_name,
                 t.topic_id, t.topic_name, t.dual AS cited_dual
          FROM read_parquet('{out}/ce.parquet') c
          JOIN read_parquet('{out}/wl.parquet') t ON t.wid = c.cited AND t.cls <> c.cls
          JOIN read_parquet('{out}/wl.parquet') s ON s.wid = c.citing
        ) TO '{out}/cross_edges.parquet' (FORMAT parquet, COMPRESSION zstd)
        """
    )
    _log("cross_edges.parquet written", t0)
    con.execute(
        f"""
        CREATE TEMP TABLE cw AS
        SELECT DISTINCT cited_id AS id FROM read_parquet('{out}/cross_edges.parquet')
        """
    )
    con.execute(
        f"""
        COPY (
          SELECT l.id, l.wid, l.year, l.type,
                 l.cls, l.sf_id, l.sf_name, l.topic_id, l.topic_name, l.dual, l.cited_by_count,
                 w.title, w.doi
          FROM read_parquet('{out}/wl.parquet') l
          JOIN cw ON cw.id = l.id
          JOIN works w ON w.id = l.id
        ) TO '{out}/cited_works.parquet' (FORMAT parquet, COMPRESSION zstd)
        """
    )
    _log("cited_works.parquet written", t0)


def stage_refage(out: Path, lo: int, hi: int, chunk: int = 4) -> None:
    """Reference-age matrix over ALL references that resolve to a work with a year."""
    con = connect()
    t0 = time.time()
    con.execute(f"CREATE TEMP TABLE tw AS SELECT wid, cls FROM read_parquet('{out}/wl.parquet')")
    frames = []
    totals = []
    years = list(range(lo, hi + 1))
    for i in range(0, len(years), chunk):
        a, b = years[i], years[min(i + chunk, len(years)) - 1]
        d = con.execute(
            f"""
            SELECT c.cls AS citing_cls, c.ar, c.citing_year, k.yr AS cited_year,
                   coalesce(tw.cls, 'other') AS cited_cls, count(*) AS n
            FROM read_parquet('{out}/ce.parquet') c
            JOIN read_parquet('{out}/lk.parquet') k ON k.wid = c.cited
            LEFT JOIN tw ON tw.wid = c.cited
            WHERE c.citing_year BETWEEN {a} AND {b}
            GROUP BY ALL
            """
        ).df()
        tot = con.execute(
            f"""
            SELECT cls AS citing_cls, ar, citing_year, count(*) AS n_edges,
                   count(DISTINCT citing) AS n_citing_with_edges
            FROM read_parquet('{out}/ce.parquet') WHERE citing_year BETWEEN {a} AND {b}
            GROUP BY ALL
            """
        ).df()
        frames.append(d)
        totals.append(tot)
        _log(f"citing years {a}-{b}: {len(d)} matrix rows", t0)
    m = pd.concat(frames).sort_values(
        ["citing_cls", "ar", "citing_year", "cited_year", "cited_cls"]
    )
    tot = pd.concat(totals).sort_values(["citing_cls", "ar", "citing_year"])
    m.to_csv(out / "matrix_reference_age.csv", index=False)
    tot.to_csv(out / "edge_totals.csv", index=False)
    wl = con.execute(
        f"""
        SELECT cls AS citing_cls, CASE WHEN type IN ('article','review') THEN 1 ELSE 0 END AS ar,
               year AS citing_year, count(*) AS n_works,
               sum(CASE WHEN referenced_works_count > 0 THEN 1 ELSE 0 END) AS n_with_reflist,
               sum(referenced_works_count) AS n_refs_listed
        FROM read_parquet('{out}/wl.parquet') WHERE year BETWEEN {lo} AND {hi}
        GROUP BY ALL ORDER BY ALL
        """
    ).df()
    wl.to_csv(out / "reflist_coverage_raw.csv", index=False)
    _log("refage done", t0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stage", required=True, choices=["labels", "edges", "cross", "refage"])
    ap.add_argument("--years", nargs=2, type=int, default=[CITING_YEAR_MIN, CITING_YEAR_MAX])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    lo, hi = a.years
    if a.stage == "labels":
        stage_labels(a.out, year_max=2026 if hi >= CITING_YEAR_MAX else hi)
    elif a.stage == "edges":
        stage_edges(a.out, lo, hi)
    elif a.stage == "cross":
        stage_cross(a.out)
    else:
        stage_refage(a.out, max(lo, 2000), hi)


if __name__ == "__main__":
    main()

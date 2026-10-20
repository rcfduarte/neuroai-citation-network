"""Q2 — Dual-citizenship census per D3 of methodology.

Question. How many researchers publish substantively in both fields?

Operationalisation (D3, recommendation B with A and C as robustness):

    Threshold A. ≥1 paper in each field, ever (any author position).
    Threshold B (HEADLINE). ≥3 first/last-author papers in each field within
        a 10-year rolling window.
    Threshold C. ≥5 first/last-author papers in each field within a 10-year
        rolling window.

Field assignment of WORK uses Scheme 1 (OpenAlex Topics primary), the same as
Q1/Q4. Author identity uses OpenAlex `author.id`. ORCID-less collisions for
common surnames (Aertsen, Engel, Wang, Anderson, Wilson, Smith) are flagged
in pool4; we propagate that flag here.

Outputs:
    data/derived/q2_dual_citizens.parquet
        author_id, threshold ('A'|'B'|'C'), n_neuro, n_ai, span_years,
        first_qualifying_year (B/C only), best_window_start (B/C only),
        best_window_neuro (B/C only), best_window_ai (B/C only)
    data/derived/q2_growth_curve.parquet
        year, threshold, n_authors_qualifying_by_year (cumulative count)
    data/derived/q2_named_examples.parquet
        Top 200 dual citizens (threshold B) by combined first/last paper count,
        with author display_name + most-cited title for human review.
    data/derived/q2_summary.json
"""

from __future__ import annotations

import argparse
import json
import logging
import time

import duckdb

from ..utils.authorships import authorships_dataset_files
from ..utils.duckdb import (
    AI_SUBFIELD_ID,
    NEURO_FIELD_ID,
    derived_dir,
    get_connection,
    manifest,
    set_temp_directory,
)

logger = logging.getLogger(__name__)

YEAR_MIN = 1990
YEAR_MAX = 2026
WINDOW_YEARS = 10  # rolling window for thresholds B and C


def _tune(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("PRAGMA threads=12")
    con.execute("PRAGMA memory_limit='30GB'")
    set_temp_directory(con)


def _build_field_assignment(con: duckdb.DuckDBPyConnection) -> int:
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE work_field AS
        SELECT
            w.id AS work_id,
            w.publication_year AS year,
            CASE
                WHEN w.primary_topic.field.id = '{NEURO_FIELD_ID}'
                  AND w.primary_topic.subfield.id = '{AI_SUBFIELD_ID}' THEN 'both'
                WHEN w.primary_topic.field.id = '{NEURO_FIELD_ID}' THEN 'neuro'
                WHEN w.primary_topic.subfield.id = '{AI_SUBFIELD_ID}' THEN 'ai'
                WHEN w.primary_topic IS NULL THEN 'unknown'
                ELSE 'other'
            END AS field
        FROM works w
        WHERE w.publication_year BETWEEN {YEAR_MIN} AND {YEAR_MAX}
        """
    )
    return int(con.execute("SELECT COUNT(*) FROM work_field").fetchone()[0])


def _build_authorships_join(con: duckdb.DuckDBPyConnection) -> tuple[int, int]:
    """author_first_last(author_id, year, field, work_id, position) — one row per
    (author, work) where the author is first/last and the work is in 1990-2026.

    Reads the pre-computed authorships parquet cache (built by utils.authorships).
    """
    files = authorships_dataset_files()
    if not files:
        raise RuntimeError(
            "Authorships cache empty. Run `python -m neuroai_cn.utils.authorships --force` first."
        )
    files_sql = "[" + ",".join("'" + f.replace("'", "''") + "'" for f in files) + "]"

    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE authorships AS
        SELECT *
        FROM read_parquet({files_sql})
        WHERE author_position IN ('first', 'last')
          AND year BETWEEN {YEAR_MIN} AND {YEAR_MAX}
        """
    )
    n_edges = int(con.execute("SELECT COUNT(*) FROM authorships").fetchone()[0])

    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE author_first_last AS
        SELECT a.author_id, a.year, a.work_id, a.author_position, wf.field
        FROM authorships a
        JOIN work_field wf ON wf.work_id = a.work_id
        WHERE wf.field IN ('neuro', 'ai')
        """
    )
    n_typed = int(con.execute("SELECT COUNT(*) FROM author_first_last").fetchone()[0])
    logger.info("Authorships first/last edges: %d total, %d typed neuro/ai", n_edges, n_typed)
    return n_edges, n_typed


def _threshold_a(con: duckdb.DuckDBPyConnection) -> int:
    """≥1 paper (any position) in each field, ever — uses ALL authorships, not first/last."""
    files = authorships_dataset_files()
    files_sql = "[" + ",".join("'" + f.replace("'", "''") + "'" for f in files) + "]"
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE author_any_field AS
        SELECT a.author_id, wf.field, a.year
        FROM read_parquet({files_sql}) a
        JOIN work_field wf ON wf.work_id = a.work_id
        WHERE wf.field IN ('neuro', 'ai')
          AND a.year BETWEEN {YEAR_MIN} AND {YEAR_MAX}
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE q2_threshold_a AS
        SELECT
            author_id,
            'A' AS threshold,
            SUM(CASE WHEN field='neuro' THEN 1 ELSE 0 END) AS n_neuro,
            SUM(CASE WHEN field='ai' THEN 1 ELSE 0 END) AS n_ai
        FROM author_any_field
        GROUP BY author_id
        HAVING SUM(CASE WHEN field='neuro' THEN 1 ELSE 0 END) >= 1
           AND SUM(CASE WHEN field='ai' THEN 1 ELSE 0 END) >= 1
        """
    )
    return int(con.execute("SELECT COUNT(*) FROM q2_threshold_a").fetchone()[0])


def _threshold_bc(con: duckdb.DuckDBPyConnection, k: int, label: str) -> int:
    """≥k first/last-author papers in each field within a 10-year rolling window."""
    # Step 1: per (author, year): count of neuro and ai first/last papers.
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE author_year_pivot AS
        SELECT
            author_id,
            year,
            SUM(CASE WHEN field='neuro' THEN 1 ELSE 0 END) AS y_neuro,
            SUM(CASE WHEN field='ai'    THEN 1 ELSE 0 END) AS y_ai
        FROM author_first_last
        GROUP BY author_id, year
        """
    )

    # Step 2: rolling 10-year window. RANGE BETWEEN 9 PRECEDING AND CURRENT ROW
    # is computed per author over the year axis. Authors with sparse year lists
    # work fine — RANGE handles gaps.
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE author_rolling_{label} AS
        SELECT
            author_id,
            year,
            y_neuro,
            y_ai,
            SUM(y_neuro) OVER (
                PARTITION BY author_id ORDER BY year
                RANGE BETWEEN {WINDOW_YEARS - 1} PRECEDING AND CURRENT ROW
            ) AS w_neuro,
            SUM(y_ai) OVER (
                PARTITION BY author_id ORDER BY year
                RANGE BETWEEN {WINDOW_YEARS - 1} PRECEDING AND CURRENT ROW
            ) AS w_ai
        FROM author_year_pivot
        """
    )

    # Step 3: pick the row with the largest min(w_neuro, w_ai) per author —
    # that's the "best" 10-year window. Author qualifies if min(w_neuro, w_ai) >= k.
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE q2_threshold_{label} AS
        WITH best_per_author AS (
            SELECT
                author_id,
                year - {WINDOW_YEARS - 1} AS best_window_start,
                year AS best_window_end,
                w_neuro AS best_w_neuro,
                w_ai AS best_w_ai,
                LEAST(w_neuro, w_ai) AS min_side,
                ROW_NUMBER() OVER (
                    PARTITION BY author_id
                    ORDER BY LEAST(w_neuro, w_ai) DESC, year ASC
                ) AS rk
            FROM author_rolling_{label}
        )
        SELECT
            author_id,
            '{label}' AS threshold,
            best_w_neuro AS n_neuro,
            best_w_ai AS n_ai,
            best_window_start,
            best_window_end
        FROM best_per_author
        WHERE rk = 1 AND min_side >= {k}
        """
    )
    return int(con.execute(f"SELECT COUNT(*) FROM q2_threshold_{label}").fetchone()[0])


def _growth_curve(con: duckdb.DuckDBPyConnection) -> None:
    """Cumulative count of authors qualifying *by year* (first window-end year that qualified).

    For threshold A we use the year of the second field's first paper.
    For thresholds B and C we use best_window_end (year the rolling window first met k).
    """
    # Compute the first-year-per-(author, field) up front; then join to the
    # threshold-A authors. (The earlier nested-correlated-subquery form
    # confused the DuckDB binder — it tried to resolve the inner `a.year`
    # against the outer FROM scope and only saw `qa`.)
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE q2_a_first_year AS
        WITH author_field_first AS (
            SELECT author_id, field, MIN(year) AS first_year
            FROM author_any_field
            WHERE field IN ('neuro', 'ai')
            GROUP BY author_id, field
        )
        SELECT
            qa.author_id,
            'A' AS threshold,
            GREATEST(
                MAX(CASE WHEN aff.field = 'neuro' THEN aff.first_year END),
                MAX(CASE WHEN aff.field = 'ai'    THEN aff.first_year END)
            ) AS qualifying_year
        FROM q2_threshold_a qa
        JOIN author_field_first aff USING (author_id)
        GROUP BY qa.author_id
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE q2_growth_curve AS
        WITH all_qualifying AS (
            SELECT author_id, threshold, qualifying_year FROM q2_a_first_year
            UNION ALL
            SELECT author_id, threshold, best_window_end AS qualifying_year FROM q2_threshold_b
            UNION ALL
            SELECT author_id, threshold, best_window_end AS qualifying_year FROM q2_threshold_c
        ),
        per_year AS (
            SELECT threshold, qualifying_year AS year, COUNT(DISTINCT author_id) AS n_new
            FROM all_qualifying
            WHERE qualifying_year BETWEEN {YEAR_MIN} AND {YEAR_MAX}
            GROUP BY threshold, qualifying_year
        )
        SELECT
            threshold,
            year,
            n_new,
            SUM(n_new) OVER (PARTITION BY threshold ORDER BY year) AS n_cumulative
        FROM per_year
        ORDER BY threshold, year
        """
    )


def build(con: duckdb.DuckDBPyConnection | None = None) -> dict:
    owns_con = con is None
    if owns_con:
        con = get_connection(read_only=True)
    try:
        _tune(con)
        m = manifest(con)
        logger.info("Q2 starting against %d works, %d authors", m.works_total, m.authors)

        t0 = time.time()
        _build_field_assignment(con)

        t1 = time.time()
        _build_authorships_join(con)
        logger.info("Authorships join: %.1fs", time.time() - t1)

        t2 = time.time()
        n_a = _threshold_a(con)
        logger.info("Threshold A: %d authors in %.1fs", n_a, time.time() - t2)

        t3 = time.time()
        n_b = _threshold_bc(con, k=3, label="b")
        logger.info("Threshold B (≥3): %d authors in %.1fs", n_b, time.time() - t3)

        t4 = time.time()
        n_c = _threshold_bc(con, k=5, label="c")
        logger.info("Threshold C (≥5): %d authors in %.1fs", n_c, time.time() - t4)

        # Persist combined dual citizens table (A union B union C, marked by threshold).
        out_path = derived_dir() / "q2_dual_citizens.parquet"
        con.execute(
            f"""
            COPY (
                SELECT author_id, threshold, n_neuro, n_ai,
                       NULL AS best_window_start, NULL AS best_window_end
                FROM q2_threshold_a
                UNION ALL
                SELECT author_id, threshold, n_neuro, n_ai,
                       best_window_start, best_window_end
                FROM q2_threshold_b
                UNION ALL
                SELECT author_id, threshold, n_neuro, n_ai,
                       best_window_start, best_window_end
                FROM q2_threshold_c
            ) TO '{out_path}' (FORMAT 'parquet', COMPRESSION 'snappy')
            """
        )

        # Growth curves (cumulative qualification by year).
        t5 = time.time()
        _growth_curve(con)
        growth_path = derived_dir() / "q2_growth_curve.parquet"
        con.execute(
            f"COPY q2_growth_curve TO '{growth_path}' (FORMAT 'parquet', COMPRESSION 'snappy')"
        )
        logger.info("Growth curve: %.1fs", time.time() - t5)

        # Named examples (top 200 dual citizens by min(n_neuro, n_ai) under threshold B).
        # Join to authors table for display_name. Coverage-bounded: not all author IDs
        # may resolve to author rows (e.g. authors with no first/last papers in 1990+).
        examples_path = derived_dir() / "q2_named_examples.parquet"
        con.execute(
            f"""
            COPY (
                SELECT
                    qb.author_id,
                    a.display_name,
                    a.orcid,
                    qb.n_neuro,
                    qb.n_ai,
                    LEAST(qb.n_neuro, qb.n_ai) AS min_side,
                    qb.best_window_start,
                    qb.best_window_end
                FROM q2_threshold_b qb
                LEFT JOIN authors a ON a.id = qb.author_id
                ORDER BY LEAST(qb.n_neuro, qb.n_ai) DESC, qb.n_neuro + qb.n_ai DESC
                LIMIT 200
            ) TO '{examples_path}' (FORMAT 'parquet', COMPRESSION 'snappy')
            """
        )

        elapsed = time.time() - t0
        summary = {
            "question": "Dual-citizenship census per D3",
            "thresholds": {
                "A": "≥1 paper in each field, ever (any author position)",
                "B": "≥3 first/last-author papers in each field within 10y rolling window (HEADLINE)",
                "C": "≥5 first/last-author papers in each field within 10y rolling window",
            },
            "year_range": [YEAR_MIN, YEAR_MAX],
            "window_years": WINDOW_YEARS,
            "n_authors_threshold_a": n_a,
            "n_authors_threshold_b": n_b,
            "n_authors_threshold_c": n_c,
            "manifest": m.to_dict(),
            "elapsed_s": round(elapsed, 1),
            "output_paths": {
                "dual_citizens": str(out_path),
                "growth_curve": str(growth_path),
                "named_examples": str(examples_path),
            },
            "human_review_flag": (
                "Named examples table contains author display_names — review for "
                "ORCID-less collision flags before publishing names. The named-author "
                "list especially requires human review per project rule."
            ),
        }
        meta_path = derived_dir() / "q2_summary.json"
        meta_path.write_text(json.dumps(summary, indent=2))
        logger.info("Q2 done in %.1fs (A=%d, B=%d, C=%d)", elapsed, n_a, n_b, n_c)
        return summary
    finally:
        if owns_con:
            con.close()


def _cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    print(json.dumps(build(), indent=2))


if __name__ == "__main__":
    _cli()

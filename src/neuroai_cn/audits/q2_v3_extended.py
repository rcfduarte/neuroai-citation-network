"""Q2 v3 — dual citizens with extended classifier + Block C cleaning rules.

Drop-in replacement for the production q2_dual_citizens.build():
1. Field assignment uses extended_classifier.build_extended_field_assignment
   (broader AI side: subfield 1702 minus BAD + 1707 + topic T10502).
2. Author enrichment computes the three Block C flags
   (placeholder, entity_not_human, supercluster) and a derived
   `dual_citizen_v3_status` column:
       'reject_placeholder', 'reject_entity', 'demote_supercluster', 'keep'
3. Two output rankings:
       q2_v3_named_examples_uncleaned.parquet  — full top-200 with flag columns
       q2_v3_named_examples_cleaned.parquet    — top-200 after applying rules

Sentinel: _q2v3.done in audits/20260508/.

Cleaning rules applied (per audit3_REPORT.md):
- placeholder_id (`A9999...`) → reject (drop)
- entity_not_human (Journal/Press/University/etc. regex) → reject (drop)
- supercluster (>1000 papers AND >5 distinct institutions) → demote
  (kept in output but marked, sorted to bottom)
- common_collision_risk → flag only (kept, sorted normally)
"""

from __future__ import annotations

import json
import logging
import sys
import time
import traceback

import duckdb

from .. import config
from ..utils.authorships import authorships_dataset_files
from ..utils.duckdb import get_connection, set_temp_directory
from .audit3_q2_entities import (
    detect_collision_risk,
    detect_entity_not_human,
    detect_placeholder_id,
)
from .extended_classifier import build_extended_field_assignment

logger = logging.getLogger(__name__)

AUDITS_DIR = config.AUDITS_DIR / "20260508"
CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"
SENTINEL_DONE = AUDITS_DIR / "_q2v3.done"
SENTINEL_FAIL = AUDITS_DIR / "_q2v3.failed"

YEAR_MIN = 1990
YEAR_MAX = 2026
WINDOW_YEARS = 10


def _build_authorships_join(con: duckdb.DuckDBPyConnection) -> tuple[int, int]:
    files = authorships_dataset_files()
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
    return n_edges, n_typed


def _threshold_b(con: duckdb.DuckDBPyConnection, k: int = 3) -> int:
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
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE author_rolling_b AS
        SELECT
            author_id, year, y_neuro, y_ai,
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
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE q2v3_threshold_b AS
        WITH best_per_author AS (
            SELECT
                author_id,
                year - {WINDOW_YEARS - 1} AS best_window_start,
                year AS best_window_end,
                w_neuro, w_ai,
                LEAST(w_neuro, w_ai) AS min_side,
                ROW_NUMBER() OVER (
                    PARTITION BY author_id
                    ORDER BY LEAST(w_neuro, w_ai) DESC, year ASC
                ) AS rk
            FROM author_rolling_b
        )
        SELECT
            author_id,
            'b' AS threshold,
            w_neuro AS n_neuro,
            w_ai AS n_ai,
            best_window_start,
            best_window_end
        FROM best_per_author
        WHERE rk = 1 AND min_side >= {k}
        """
    )
    return int(con.execute("SELECT COUNT(*) FROM q2v3_threshold_b").fetchone()[0])


def _enrich_top_authors(con: duckdb.DuckDBPyConnection, top_n: int = 500) -> list[dict]:
    """Get top-N dual citizens from threshold B with author-table enrichment."""
    rows = con.execute(
        f"""
        WITH top_b AS (
            SELECT
                author_id, n_neuro, n_ai, best_window_start, best_window_end,
                LEAST(n_neuro, n_ai) AS min_side
            FROM q2v3_threshold_b
            ORDER BY min_side DESC, n_neuro + n_ai DESC
            LIMIT {top_n}
        ),
        with_author AS (
            SELECT
                t.author_id,
                a.display_name,
                a.orcid,
                a.works_count,
                a.cited_by_count,
                t.n_neuro, t.n_ai, t.best_window_start, t.best_window_end, t.min_side
            FROM top_b t
            LEFT JOIN authors a ON a.id = t.author_id
        )
        SELECT * FROM with_author ORDER BY min_side DESC, n_neuro + n_ai DESC
        """
    ).fetchall()
    cols = [
        "author_id",
        "display_name",
        "orcid",
        "works_count",
        "cited_by_count",
        "n_neuro",
        "n_ai",
        "best_window_start",
        "best_window_end",
        "min_side",
    ]
    out = []
    for r in rows:
        d = dict(zip(cols, r, strict=False))
        out.append(
            {
                "author_id": d["author_id"],
                "display_name": d["display_name"],
                "orcid": d["orcid"],
                "works_count": int(d["works_count"]) if d["works_count"] is not None else None,
                "cited_by_count": int(d["cited_by_count"])
                if d["cited_by_count"] is not None
                else None,
                "n_neuro": int(d["n_neuro"]) if d["n_neuro"] is not None else 0,
                "n_ai": int(d["n_ai"]) if d["n_ai"] is not None else 0,
                "best_window_start": int(d["best_window_start"])
                if d["best_window_start"]
                else None,
                "best_window_end": int(d["best_window_end"]) if d["best_window_end"] else None,
                "min_side": int(d["min_side"]) if d["min_side"] else 0,
            }
        )
    return out


def _institution_diversity(
    con: duckdb.DuckDBPyConnection, author_ids: list[str]
) -> dict[str, dict]:
    if not author_ids:
        return {}
    con.execute("CREATE OR REPLACE TEMP TABLE _q2v3_aids (author_id VARCHAR)")
    con.executemany("INSERT INTO _q2v3_aids VALUES (?)", [(a,) for a in author_ids])
    rows = con.execute("""
        WITH unrolled AS (
            SELECT t.author_id, UNNEST(a.affiliations) AS aff
            FROM _q2v3_aids t
            LEFT JOIN authors a ON a.id = t.author_id
        )
        SELECT
            author_id,
            COUNT(DISTINCT aff.institution.id) AS n_distinct_inst,
            COUNT(DISTINCT aff.institution.country_code) AS n_distinct_country
        FROM unrolled
        GROUP BY author_id
    """).fetchall()
    return {
        aid: {"n_distinct_institutions": int(ni or 0), "n_distinct_countries": int(nc or 0)}
        for aid, ni, nc in rows
    }


def _apply_cleaning_rules(records: list[dict]) -> list[dict]:
    """Add status column based on Block C flags."""
    for r in records:
        name = r.get("display_name") or ""
        aid = r.get("author_id")
        works = r.get("works_count") or 0
        n_inst = r.get("n_distinct_institutions") or 0

        is_placeholder = detect_placeholder_id(aid)
        is_entity = detect_entity_not_human(name)
        is_supercluster = bool(works > 1000 and n_inst > 5)
        is_collision_risk = detect_collision_risk(name, aid)

        r["flag_placeholder_id"] = is_placeholder
        r["flag_entity_not_human"] = is_entity or is_placeholder
        r["flag_supercluster"] = is_supercluster
        r["flag_common_collision_risk"] = is_collision_risk

        # Status: hard-reject if placeholder/entity; demote if supercluster; otherwise keep
        if is_placeholder:
            r["dual_citizen_v3_status"] = "reject_placeholder"
        elif is_entity:
            r["dual_citizen_v3_status"] = "reject_entity"
        elif is_supercluster:
            r["dual_citizen_v3_status"] = "demote_supercluster"
        else:
            r["dual_citizen_v3_status"] = "keep"
    return records


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    CORRECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    for s in (SENTINEL_DONE, SENTINEL_FAIL):
        if s.exists():
            s.unlink()
    t0 = time.time()
    try:
        con = get_connection(read_only=True)
        try:
            con.execute("PRAGMA threads=12")
            con.execute("PRAGMA memory_limit='30GB'")
            set_temp_directory(con)

            logger.info("Building extended field assignment...")
            pop = build_extended_field_assignment(con, year_min=YEAR_MIN, year_max=YEAR_MAX)
            logger.info("pop: %s", pop)

            logger.info("Building authorships join (first/last)...")
            n_edges, n_typed = _build_authorships_join(con)
            logger.info("authorships: %d total, %d typed", n_edges, n_typed)

            logger.info("Threshold B (k=3, 10y window)...")
            n_b = _threshold_b(con, k=3)
            logger.info("Threshold B count (extended): %d", n_b)

            logger.info("Enriching top-500 with author table data...")
            top = _enrich_top_authors(con, top_n=500)
            aids = [r["author_id"] for r in top]
            inst = _institution_diversity(con, aids)
            for r in top:
                e = inst.get(r["author_id"], {})
                r["n_distinct_institutions"] = e.get("n_distinct_institutions", 0)
                r["n_distinct_countries"] = e.get("n_distinct_countries", 0)
            top = _apply_cleaning_rules(top)

            # Persist uncleaned + cleaned versions
            uncleaned_path = CORRECTIONS_DIR / "q2_v3_named_examples_uncleaned.parquet"
            con.execute(
                "CREATE OR REPLACE TEMP TABLE _q2v3_uncleaned (rank INTEGER, author_id VARCHAR, display_name VARCHAR, orcid VARCHAR, works_count BIGINT, cited_by_count BIGINT, n_neuro INTEGER, n_ai INTEGER, min_side INTEGER, best_window_start INTEGER, best_window_end INTEGER, n_distinct_institutions INTEGER, n_distinct_countries INTEGER, flag_placeholder_id BOOLEAN, flag_entity_not_human BOOLEAN, flag_supercluster BOOLEAN, flag_common_collision_risk BOOLEAN, dual_citizen_v3_status VARCHAR)"
            )
            con.executemany(
                "INSERT INTO _q2v3_uncleaned VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        i + 1,
                        r["author_id"],
                        r["display_name"],
                        r["orcid"],
                        r["works_count"],
                        r["cited_by_count"],
                        r["n_neuro"],
                        r["n_ai"],
                        r["min_side"],
                        r["best_window_start"],
                        r["best_window_end"],
                        r["n_distinct_institutions"],
                        r["n_distinct_countries"],
                        r["flag_placeholder_id"],
                        r["flag_entity_not_human"],
                        r["flag_supercluster"],
                        r["flag_common_collision_risk"],
                        r["dual_citizen_v3_status"],
                    )
                    for i, r in enumerate(top)
                ],
            )
            con.execute(
                f"COPY _q2v3_uncleaned TO '{uncleaned_path}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )

            cleaned_path = CORRECTIONS_DIR / "q2_v3_named_examples_cleaned.parquet"
            con.execute(
                f"""
                COPY (
                    SELECT * FROM _q2v3_uncleaned
                    WHERE dual_citizen_v3_status NOT IN ('reject_placeholder', 'reject_entity')
                    ORDER BY
                        CASE WHEN dual_citizen_v3_status = 'demote_supercluster' THEN 1 ELSE 0 END,
                        min_side DESC,
                        n_neuro + n_ai DESC
                    LIMIT 200
                ) TO '{cleaned_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
                """
            )

            # Growth curves under extended scheme — minimal version: just threshold B
            growth_path = CORRECTIONS_DIR / "q2_v3_growth_curve.parquet"
            con.execute(
                f"""
                COPY (
                    WITH per_year AS (
                        SELECT best_window_end AS year, COUNT(DISTINCT author_id) AS n_new
                        FROM q2v3_threshold_b
                        WHERE best_window_end BETWEEN {YEAR_MIN} AND {YEAR_MAX}
                        GROUP BY best_window_end
                    )
                    SELECT
                        'b' AS threshold,
                        year, n_new,
                        SUM(n_new) OVER (ORDER BY year) AS n_cumulative
                    FROM per_year
                    ORDER BY year
                ) TO '{growth_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
                """
            )

            # Summary JSON
            summary = {
                "scheme": "extended (subfield 1702 minus BAD + 1707 + T10502)",
                "year_range": [YEAR_MIN, YEAR_MAX],
                "window_years": WINDOW_YEARS,
                "n_authors_threshold_b_extended": n_b,
                "n_top_500_enriched": len(top),
                "cleaning_rules_applied": [
                    "reject_placeholder (A9999...)",
                    "reject_entity (Journal/Press/University regex)",
                    "demote_supercluster (works>1000 AND distinct_inst>5)",
                ],
                "n_rejected_placeholder": sum(
                    1 for r in top if r["dual_citizen_v3_status"] == "reject_placeholder"
                ),
                "n_rejected_entity": sum(
                    1 for r in top if r["dual_citizen_v3_status"] == "reject_entity"
                ),
                "n_demoted_supercluster": sum(
                    1 for r in top if r["dual_citizen_v3_status"] == "demote_supercluster"
                ),
                "n_kept": sum(1 for r in top if r["dual_citizen_v3_status"] == "keep"),
                "elapsed_s": round(time.time() - t0, 1),
            }
            with (AUDITS_DIR / "q2_v3_summary.json").open("w") as fh:
                json.dump(summary, fh, indent=2)
            logger.info("Summary: %s", summary)
        finally:
            con.close()
        SENTINEL_DONE.write_text(
            f"q2_v3: DONE — extended classifier + Block C cleaning; "
            f"n_b={n_b}; elapsed {time.time() - t0:.1f}s\n"
        )
        return 0
    except Exception as exc:
        tb = traceback.format_exc()
        SENTINEL_FAIL.write_text(f"q2_v3: ERROR — {type(exc).__name__}: {exc}\n\n{tb}\n")
        logger.exception("Q2 v3 errored")
        return 2


if __name__ == "__main__":
    sys.exit(main())

"""Q1 — merged Scheme 1 (extended Topics) + Scheme 2 (venue whitelist) field assignment.

Merge logic (hierarchical, Scheme 1 primary):
    field_merged =
      scheme1.field          if scheme1.field IN ('neuro','ai')
      'neuro'                if scheme1.field IN ('other','unknown') AND scheme2.venue = 'venue_neuro'
      'ai'                   if scheme1.field IN ('other','unknown') AND scheme2.venue = 'venue_ai'
      scheme1.field          otherwise

The merge ONLY adds labels where Scheme 1 abstains and Scheme 2 has a strict-core
match (CORE_NEURO=23 or CORE_AI=31 venues). The ambiguous categories
(venue_intersection, venue_general_high, venue_other, venue_unknown) never override
Scheme 1 — those venues are themselves under-determined for the bridge-detection
question.

Outputs (under data/derived/corrections/20260514/):
    q1_merged_s1_s2_or_by_year.parquet      — primary OR series (per-year per-direction)
    q1_merged_s1_s2_era_slopes.parquet      — OLS slopes per fixed era
    q1_merged_s1_s2_changepoints.parquet    — piecewise-linear change-point detection
    q1_merged_s1_s2_population.parquet      — per-year per-label population
    q1_merged_s1_s2_relabel_diagnostic.parquet — per-year flow of relabels (other→neuro etc.)
    q1_merged_s1_s2_summary.json            — summary metadata

Sentinel: _q1_merged_s1_s2.done in audits/20260514/.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import traceback

import duckdb
import pandas as pd

from .. import config
from ..utils.duckdb import get_connection, set_temp_directory
from .extended_classifier import build_extended_field_assignment
from .q1_v3_extended import compute_or_by_year, detect_changepoints, era_slopes
from .scheme2_venues import build_venue_assignment

logger = logging.getLogger(__name__)

AUDITS_DIR = config.AUDITS_DIR / "20260514"
CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260514"
SENTINEL_DONE = AUDITS_DIR / "_q1_merged_s1_s2.done"
SENTINEL_FAIL = AUDITS_DIR / "_q1_merged_s1_s2.failed"

YEAR_MIN = 1990
YEAR_MAX = 2025


def build_merged_assignment(
    con: duckdb.DuckDBPyConnection,
    table_name: str = "work_field",
) -> dict[str, int]:
    """Build temp table work_field_merged then rename it to ``table_name`` so
    downstream Q1 functions (compute_or_by_year) see it under their expected name.

    Returns the population dict for the merged scheme.
    """
    # Build Scheme 1 (work_field_s1) and Scheme 2 (work_venue) temp tables
    logger.info("Building Scheme 1 (extended topics) temp table work_field_s1...")
    pop_s1 = build_extended_field_assignment(
        con, year_min=YEAR_MIN, year_max=YEAR_MAX, table_name="work_field_s1"
    )
    logger.info("Scheme 1 population: %s", pop_s1)

    logger.info("Building Scheme 2 (venue whitelist) temp table work_venue...")
    pop_s2 = build_venue_assignment(con, table_name="work_venue")
    logger.info("Scheme 2 population: %s", pop_s2)

    # Merge: Scheme 1 primary, Scheme 2 fills 'other'/'unknown' with strict core
    logger.info("Merging Scheme 1 + Scheme 2 → %s temp table...", table_name)
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE {table_name} AS
        SELECT
            wf.work_id,
            wf.year,
            CASE
                WHEN wf.field IN ('neuro', 'ai') THEN wf.field
                WHEN wf.field IN ('other', 'unknown') AND wv.venue_label = 'venue_neuro' THEN 'neuro'
                WHEN wf.field IN ('other', 'unknown') AND wv.venue_label = 'venue_ai' THEN 'ai'
                ELSE wf.field
            END AS field,
            wf.field AS scheme1_field,
            COALESCE(wv.venue_label, 'venue_unknown') AS scheme2_venue
        FROM work_field_s1 wf
        LEFT JOIN work_venue wv ON wv.work_id = wf.work_id
        """
    )

    rows = con.execute(
        f"""
        SELECT field, COUNT(*) AS n
        FROM {table_name}
        GROUP BY field
        """
    ).fetchall()
    pop = {f: int(n) for f, n in rows}
    logger.info("Merged scheme population: %s", pop)

    # Compute relabel diagnostic: how many works flipped from each Scheme 1 label
    relabel_rows = con.execute(
        f"""
        SELECT year, scheme1_field, scheme2_venue, field AS final_field, COUNT(*) AS n
        FROM {table_name}
        WHERE scheme1_field IN ('other', 'unknown')
          AND field IN ('neuro', 'ai')
        GROUP BY year, scheme1_field, scheme2_venue, field
        ORDER BY year, scheme1_field, final_field
        """
    ).fetchall()
    relabel_df = pd.DataFrame(
        relabel_rows,
        columns=["year", "scheme1_field", "scheme2_venue", "final_field", "n"],
    )
    relabel_df.to_parquet(
        CORRECTIONS_DIR / "q1_merged_s1_s2_relabel_diagnostic.parquet", index=False
    )
    total_relabeled = int(relabel_df["n"].sum())
    logger.info(
        "Relabel diagnostic: %d works lifted from other/unknown → neuro/ai via Scheme 2 strict core",
        total_relabeled,
    )

    return pop


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
            con.execute("PRAGMA threads=10")
            con.execute("PRAGMA memory_limit='24GB'")
            set_temp_directory(con)

            pop = build_merged_assignment(con, table_name="work_field")

            # Persist per-year population
            pop_path = CORRECTIONS_DIR / "q1_merged_s1_s2_population.parquet"
            con.execute(
                f"""
                COPY (
                    SELECT year, field, COUNT(*) AS n
                    FROM work_field
                    GROUP BY year, field
                    ORDER BY year, field
                ) TO '{pop_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
                """
            )

            logger.info("Computing OR by year against merged scheme...")
            df_or = compute_or_by_year(con)
            df_or.to_parquet(CORRECTIONS_DIR / "q1_merged_s1_s2_or_by_year.parquet", index=False)
            logger.info("Wrote OR-by-year: %d rows", len(df_or))

            logger.info("Computing era-anchored slopes...")
            eras_df = era_slopes(df_or)
            eras_df.to_parquet(CORRECTIONS_DIR / "q1_merged_s1_s2_era_slopes.parquet", index=False)

            logger.info("Detecting changepoints (up to 2 breakpoints)...")
            cps = detect_changepoints(df_or, max_breakpoints=2)
            cps.to_parquet(CORRECTIONS_DIR / "q1_merged_s1_s2_changepoints.parquet", index=False)

            summary = {
                "scheme": "merged_s1_s2_hierarchical",
                "merge_logic": (
                    "Scheme 1 primary; Scheme 2 strict-core (CORE_NEURO/CORE_AI) "
                    "only fills 'other'/'unknown' gaps. venue_intersection / "
                    "venue_general_high / venue_other / venue_unknown never override."
                ),
                "n_works_assigned": pop,
                "year_range": [YEAR_MIN, YEAR_MAX],
                "n_or_rows": len(df_or),
                "n_era_rows": len(eras_df),
                "n_changepoint_segments": len(cps),
                "elapsed_s": round(time.time() - t0, 1),
            }
            with (AUDITS_DIR / "q1_merged_s1_s2_summary.json").open("w") as fh:
                json.dump(summary, fh, indent=2, default=str)
            logger.info("Summary: %s", summary)
        finally:
            con.close()
        elapsed = time.time() - t0
        SENTINEL_DONE.write_text(
            f"q1_merged_s1_s2: DONE — OR + era slopes + change-point on merged S1+S2; "
            f"elapsed {elapsed:.1f}s\n"
        )
        return 0
    except Exception as exc:
        tb = traceback.format_exc()
        SENTINEL_FAIL.write_text(f"q1_merged_s1_s2: ERROR — {type(exc).__name__}: {exc}\n\n{tb}\n")
        logger.exception("Q1 merged S1+S2 errored")
        return 2


if __name__ == "__main__":
    sys.exit(main())

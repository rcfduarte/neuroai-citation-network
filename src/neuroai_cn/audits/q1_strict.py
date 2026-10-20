"""Q1 strict — counter-factual to q1_v3_extended.

Reuses every analysis function from q1_v3_extended (compute_or_by_year,
rolling_slopes, yoy_changes, era_slopes, detect_changepoints) but swaps the
field-assignment builder to the strict (curated-35) classifier.

Outputs to ``corrections/20260508/strict/`` (parallel to extended outputs).
"""

from __future__ import annotations

import json
import logging
import sys
import time
import traceback

from .. import config
from ..utils.duckdb import get_connection, set_temp_directory
from .q1_v3_extended import (
    YEAR_MAX,
    YEAR_MIN,
    compute_or_by_year,
    detect_changepoints,
    era_slopes,
    rolling_slopes,
    yoy_changes,
)
from .strict_classifier import build_strict_field_assignment

logger = logging.getLogger(__name__)

AUDITS_DIR = config.AUDITS_DIR / "20260508"
CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508" / "strict"
SENTINEL_DONE = AUDITS_DIR / "_q1_strict.done"
SENTINEL_FAIL = AUDITS_DIR / "_q1_strict.failed"


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
            logger.info("Building STRICT field assignment (curated 35-topic AI core)...")
            pop = build_strict_field_assignment(con, year_min=YEAR_MIN, year_max=YEAR_MAX)
            logger.info("Computing OR by year (strict scheme)...")
            df_or = compute_or_by_year(con)
            df_or.to_parquet(CORRECTIONS_DIR / "q1_strict_or_by_year.parquet", index=False)
            logger.info("Wrote OR-by-year: %d rows", len(df_or))

            roll_5 = rolling_slopes(df_or, window=5)
            roll_7 = rolling_slopes(df_or, window=7)
            import pandas as pd

            roll = pd.concat([roll_5, roll_7], ignore_index=True)
            roll.to_parquet(CORRECTIONS_DIR / "q1_strict_rolling_slopes.parquet", index=False)

            yoy = yoy_changes(df_or)
            yoy.to_parquet(CORRECTIONS_DIR / "q1_strict_yoy.parquet", index=False)

            eras_df = era_slopes(df_or)
            eras_df.to_parquet(CORRECTIONS_DIR / "q1_strict_era_slopes.parquet", index=False)

            cps = detect_changepoints(df_or, max_breakpoints=2)
            cps.to_parquet(CORRECTIONS_DIR / "q1_strict_changepoints.parquet", index=False)

            summary = {
                "scheme": "strict (curated 35-topic AI core, production)",
                "n_works_assigned": pop,
                "year_range": [YEAR_MIN, YEAR_MAX],
                "n_or_rows": len(df_or),
                "n_rolling_rows": len(roll),
                "n_yoy_rows": len(yoy),
                "n_era_rows": len(eras_df),
                "n_changepoint_segments": len(cps),
                "elapsed_s": time.time() - t0,
            }
            with (AUDITS_DIR / "q1_strict_summary.json").open("w") as fh:
                json.dump(summary, fh, indent=2, default=str)
        finally:
            con.close()
        elapsed = time.time() - t0
        SENTINEL_DONE.write_text(f"q1_strict: DONE — elapsed {elapsed:.1f}s\n")
        logger.info("Q1 strict DONE in %.1fs", elapsed)
        return 0
    except Exception as exc:
        tb = traceback.format_exc()
        SENTINEL_FAIL.write_text(f"q1_strict: ERROR — {type(exc).__name__}: {exc}\n\n{tb}\n")
        logger.exception("Q1 strict errored")
        return 2


if __name__ == "__main__":
    sys.exit(main())

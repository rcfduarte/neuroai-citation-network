"""Q4 strict — counter-factual to q4_v3_extended using the curated 35-topic AI core.

Reuses the analysis machinery from q4_v3_extended (build_bridge_table,
materialize_full, variants, tier1 check, spearman) but builds work_field via
the strict classifier. Outputs to ``corrections/20260508/strict/``.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import traceback

import pandas as pd

from .. import config
from ..utils.duckdb import get_connection, set_temp_directory
from .q4_v3_extended import (
    TOP_N,
    YEAR_MAX,
    YEAR_MIN,
    build_bridge_table,
    by_era_split,
    materialize_full,
    spearman_rho,
    tier1_surface_check,
    utility_diagnostic,
    variant_filtered_top,
    variant_normalised_top,
)
from .strict_classifier import build_strict_field_assignment

logger = logging.getLogger(__name__)

AUDITS_DIR = config.AUDITS_DIR / "20260508"
CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508" / "strict"
SENTINEL_DONE = AUDITS_DIR / "_q4_strict.done"
SENTINEL_FAIL = AUDITS_DIR / "_q4_strict.failed"


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
            con.execute("PRAGMA threads=6")
            con.execute("PRAGMA memory_limit='20GB'")
            set_temp_directory(con)
            con.execute("PRAGMA preserve_insertion_order=false")

            logger.info("Building STRICT field assignment...")
            pop = build_strict_field_assignment(con, year_min=YEAR_MIN, year_max=YEAR_MAX)
            logger.info("pop: %s", pop)

            logger.info("Building bridge table...")
            n_bridge = build_bridge_table(con)
            logger.info("Bridge candidates: %d", n_bridge)

            full_path = CORRECTIONS_DIR / "q4_strict_full.parquet"
            materialize_full(con, full_path)

            df_full = pd.read_parquet(full_path)

            top_norm = variant_normalised_top(df_full, top_n=TOP_N)
            top_filt = variant_filtered_top(df_full, top_n=TOP_N)

            top_norm.to_parquet(CORRECTIONS_DIR / "q4_strict_normalised.parquet", index=False)
            top_filt.to_parquet(CORRECTIONS_DIR / "q4_strict_filtered.parquet", index=False)

            era_norm = by_era_split(top_norm, top_per_era=25)
            era_filt = by_era_split(top_filt, top_per_era=25)
            era_norm.to_parquet(
                CORRECTIONS_DIR / "q4_strict_normalised_by_era.parquet", index=False
            )
            era_filt.to_parquet(CORRECTIONS_DIR / "q4_strict_filtered_by_era.parquet", index=False)

            ud = utility_diagnostic(con, df_full, top_norm, top_filt)
            ud.to_parquet(CORRECTIONS_DIR / "q4_strict_utility_diagnostic.parquet", index=False)

            t1 = tier1_surface_check(top_norm, "E1_normalised")
            t2 = tier1_surface_check(top_filt, "E2_filtered")
            rho = spearman_rho(top_norm, top_filt)

            summary = {
                "scheme": "strict (curated 35-topic AI core, production)",
                "n_bridge_candidates": n_bridge,
                "tier1_surface_check": [t1, t2],
                "spearman_rho_E1_vs_E2": rho,
                "n_top_norm": len(top_norm),
                "n_top_filt": len(top_filt),
                "elapsed_s": round(time.time() - t0, 1),
            }
            with (AUDITS_DIR / "q4_strict_summary.json").open("w") as fh:
                json.dump(summary, fh, indent=2, default=str)
            logger.info("Summary: %s", summary)
        finally:
            con.close()
        SENTINEL_DONE.write_text(
            f"q4_strict: DONE — {n_bridge} candidates; rho={rho:.3f}; elapsed {time.time() - t0:.1f}s\n"
        )
        return 0
    except Exception as exc:
        tb = traceback.format_exc()
        SENTINEL_FAIL.write_text(f"q4_strict: ERROR — {type(exc).__name__}: {exc}\n\n{tb}\n")
        logger.exception("Q4 strict errored")
        return 2


if __name__ == "__main__":
    sys.exit(main())

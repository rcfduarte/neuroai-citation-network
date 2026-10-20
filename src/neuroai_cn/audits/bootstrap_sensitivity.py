"""Bootstrap CIs on Q1 trends + leave-one-topic-out sensitivity over BAD_1702.

Two analyses:

(A) Bootstrap CIs on Q1 era slopes
    - For each (era, direction, metric), resample years with replacement (B=500)
    - Refit OLS slope on the resampled subset
    - Report slope mean, percentile 95% CI, fraction-positive

(B) Leave-one-topic-out (LOTO) sensitivity over BAD_1702
    - For each topic in BAD_1702_TOPIC_IDS (26 of them):
      * Add it back into the AI core (now 1702-NOT-BAD-(t) + 1707 + T10502)
      * Recompute the per-year OR for ai_to_neuro (1990-2025)
      * Compare to the canonical extended OR series — report rank-correlation
        + max abs delta + which years move the most
    - Goal: identify topics whose addition meaningfully shifts the trend
      (vs benign cosmetic changes)

Outputs (under data/derived/corrections/20260508/):
    bootstrap_era_slopes.parquet     — bootstrap distribution per era/direction/metric
    bootstrap_era_summary.parquet    — mean, ci_lo, ci_hi, frac_positive per (era, dir, metric)
    loto_sensitivity.parquet         — per-topic delta vs canonical
    loto_summary.json                — topics ranked by impact

Sentinel: _bootstrap.done in audits/20260508/.
"""

from __future__ import annotations

import json
import logging
import math
import sys
import time
import traceback

import duckdb
import numpy as np
import pandas as pd

from .. import config
from ..utils.duckdb import NEURO_FIELD_ID, get_connection, set_temp_directory
from .extended_classifier import (
    AI_SUBFIELD_1702,
    AI_SUBFIELD_1707,
    BAD_1702_TOPIC_IDS,
    NEURAL_MEMORY_TOPIC_2208,
)
from .q1_v3_extended import ERAS, ols_slope

logger = logging.getLogger(__name__)

AUDITS_DIR = config.AUDITS_DIR / "20260508"
CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"
SENTINEL_DONE = AUDITS_DIR / "_bootstrap.done"
SENTINEL_FAIL = AUDITS_DIR / "_bootstrap.failed"

YEAR_MIN = 1990
YEAR_MAX = 2025
N_BOOT = 500


def bootstrap_era_slopes(
    or_df: pd.DataFrame, n_boot: int = N_BOOT
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Resample years within each era and refit OLS slope. Returns
    (per-resample distributions, summary)."""
    rng = np.random.default_rng(42)
    out_dist = []
    out_summary = []
    for direction in ("ai_to_neuro", "neuro_to_ai"):
        for label, lo, hi in ERAS:
            for metric in ("or_restricted", "or_population"):
                sub = or_df[
                    (or_df["direction"] == direction)
                    & (or_df["year"] >= lo)
                    & (or_df["year"] <= hi)
                ].sort_values("year")
                xs = sub["year"].to_numpy(dtype=float)
                ys = sub[metric].to_numpy(dtype=float)
                mask = ~np.isnan(ys)
                xs = xs[mask]
                ys = ys[mask]
                if len(xs) < 4:
                    continue
                slopes = []
                for _b in range(n_boot):
                    idx = rng.integers(0, len(xs), size=len(xs))
                    s = ols_slope(xs[idx], ys[idx])
                    if not math.isnan(s["slope"]):
                        slopes.append(s["slope"])
                if not slopes:
                    continue
                arr = np.array(slopes)
                out_dist.extend(
                    [
                        {
                            "era": label,
                            "direction": direction,
                            "metric": metric,
                            "boot_idx": i,
                            "slope": float(v),
                        }
                        for i, v in enumerate(arr)
                    ]
                )
                out_summary.append(
                    {
                        "era": label,
                        "year_min": lo,
                        "year_max": hi,
                        "direction": direction,
                        "metric": metric,
                        "n_years": len(xs),
                        "n_boot": len(slopes),
                        "slope_mean": float(arr.mean()),
                        "slope_median": float(np.median(arr)),
                        "ci_lo": float(np.percentile(arr, 2.5)),
                        "ci_hi": float(np.percentile(arr, 97.5)),
                        "frac_positive": float((arr > 0).mean()),
                        "frac_negative": float((arr < 0).mean()),
                    }
                )
    return pd.DataFrame(out_dist), pd.DataFrame(out_summary)


def compute_or_for_loto(
    con: duckdb.DuckDBPyConnection,
    bad_subset: frozenset[str],
) -> pd.DataFrame:
    """Compute per-year OR_restricted for ai→neuro and neuro→ai with the given
    BAD_1702 subset (i.e., exclude these topics from AI; include 1702 \\ subset
    + 1707 + T10502).
    """
    bad_arr = "[" + ",".join("'" + t + "'" for t in bad_subset) + "]"
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE work_field AS
        SELECT
            w.id AS work_id,
            w.publication_year AS year,
            CASE
                WHEN w.primary_topic IS NULL THEN 'unknown'
                WHEN w.primary_topic.field.id = '{NEURO_FIELD_ID}' THEN 'neuro'
                WHEN (
                        w.primary_topic.subfield.id = '{AI_SUBFIELD_1702}'
                        AND w.primary_topic.id NOT IN (SELECT unnest({bad_arr}))
                     )
                  OR w.primary_topic.subfield.id = '{AI_SUBFIELD_1707}'
                  OR w.primary_topic.id = '{NEURAL_MEMORY_TOPIC_2208}'
                THEN 'ai'
                ELSE 'other'
            END AS field
        FROM works w
        WHERE w.publication_year BETWEEN {YEAR_MIN} AND {YEAR_MAX}
        """
    )
    pop_rows = con.execute(
        f"""
        SELECT year,
               SUM(CASE WHEN field='neuro' THEN 1 ELSE 0 END) AS n_neuro,
               SUM(CASE WHEN field='ai' THEN 1 ELSE 0 END) AS n_ai
        FROM work_field
        WHERE year BETWEEN {YEAR_MIN} AND {YEAR_MAX}
        GROUP BY year
        """
    ).fetchall()
    pop = {int(r[0]): {"neuro": int(r[1]), "ai": int(r[2])} for r in pop_rows}

    edge_rows = con.execute(
        f"""
        SELECT
            e.citing_year AS year,
            src.field AS src_field,
            tgt.field AS tgt_field,
            COUNT(*) AS n
        FROM citation_edges e
        JOIN work_field src ON src.work_id = e.citing_work_id
        LEFT JOIN work_field tgt ON tgt.work_id = e.cited_work_id
        WHERE e.citing_year BETWEEN {YEAR_MIN} AND {YEAR_MAX}
          AND src.field IN ('neuro', 'ai')
        GROUP BY e.citing_year, src.field, tgt.field
        """
    ).fetchall()

    edges = {}
    for y, sf, tf, n in edge_rows:
        edges[(int(y), sf, tf)] = int(n)

    out = []
    for year in sorted({k[0] for k in edges}):
        for src in ("neuro", "ai"):
            tgt = "ai" if src == "neuro" else "neuro"
            n_within = edges.get((year, src, src), 0)
            n_target = edges.get((year, src, tgt), 0)
            denom_r = n_within + n_target
            rho_r = n_target / denom_r if denom_r > 0 else float("nan")
            popy = pop.get(year, {"neuro": 0, "ai": 0})
            denom_null = popy[src] + popy[tgt]
            rho_null = popy[tgt] / denom_null if denom_null > 0 else float("nan")
            if rho_null > 0 and rho_null < 1 and not math.isnan(rho_r):
                if rho_r <= 0:
                    or_r = 0.0
                elif rho_r >= 1:
                    or_r = float("inf")
                else:
                    or_r = (rho_r / (1 - rho_r)) / (rho_null / (1 - rho_null))
            else:
                or_r = float("nan")
            out.append({"year": year, "direction": f"{src}_to_{tgt}", "or_restricted": or_r})
    return pd.DataFrame(out)


def loto_sensitivity(con: duckdb.DuckDBPyConnection) -> tuple[pd.DataFrame, dict]:
    """For each BAD_1702 topic, add it back to AI and compute delta vs canonical."""
    # Canonical (full BAD list = current extended classifier)
    logger.info("Computing canonical OR series ...")
    canonical = compute_or_for_loto(con, BAD_1702_TOPIC_IDS)
    canonical = canonical.rename(columns={"or_restricted": "or_canonical"})

    rows = []
    summary_rows = []
    bad_list = sorted(BAD_1702_TOPIC_IDS)
    for i, topic in enumerate(bad_list):
        logger.info("LOTO %d/%d: removing %s from BAD list ...", i + 1, len(bad_list), topic)
        loto_bad = frozenset(b for b in BAD_1702_TOPIC_IDS if b != topic)
        loto_or = compute_or_for_loto(con, loto_bad)
        loto_or = loto_or.rename(columns={"or_restricted": "or_loto"})
        merged = loto_or.merge(canonical, on=["year", "direction"])
        merged["delta"] = merged["or_loto"] - merged["or_canonical"]
        merged["pct_change"] = np.where(
            (merged["or_canonical"] > 0) & np.isfinite(merged["or_canonical"]),
            merged["delta"] / merged["or_canonical"],
            np.nan,
        )
        merged["topic_added"] = topic
        rows.append(merged)
        # Summary: max abs delta per direction
        for direction in ("ai_to_neuro", "neuro_to_ai"):
            sub = merged[merged["direction"] == direction]
            if sub.empty:
                continue
            abs_delta = sub["delta"].abs()
            ix = int(abs_delta.idxmax())
            summary_rows.append(
                {
                    "topic": topic,
                    "direction": direction,
                    "max_abs_delta": float(abs_delta.max()),
                    "max_abs_delta_year": int(sub.loc[ix, "year"]),
                    "max_abs_delta_pct": float(sub.loc[ix, "pct_change"])
                    if not math.isnan(sub.loc[ix, "pct_change"])
                    else float("nan"),
                    "mean_abs_delta": float(abs_delta.mean()),
                    "rank_corr_with_canonical": float(
                        sub["or_loto"].corr(sub["or_canonical"], method="spearman")
                    )
                    if len(sub) > 5
                    else float("nan"),
                }
            )
    df = pd.concat(rows, ignore_index=True)
    summary_df = pd.DataFrame(summary_rows).sort_values("max_abs_delta", ascending=False)
    return df, summary_df.to_dict(orient="records")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    CORRECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    for s in (SENTINEL_DONE, SENTINEL_FAIL):
        if s.exists():
            s.unlink()
    t0 = time.time()
    try:
        # PART A: bootstrap CIs (uses existing extended Q1 OR-by-year parquet)
        # Skip if already present from a prior partial run.
        boot_dist_path = CORRECTIONS_DIR / "bootstrap_era_slopes.parquet"
        boot_summary_path = CORRECTIONS_DIR / "bootstrap_era_summary.parquet"
        if boot_dist_path.exists() and boot_summary_path.exists():
            logger.info("PART A: skipping (already present)")
        else:
            logger.info("PART A: Bootstrap CIs on extended-Q1 era slopes ...")
            or_path = CORRECTIONS_DIR / "q1_v3_extended_or_by_year.parquet"
            if not or_path.exists():
                raise FileNotFoundError(or_path)
            or_df = pd.read_parquet(or_path)
            boot_dist, boot_summary = bootstrap_era_slopes(or_df, n_boot=N_BOOT)
            boot_dist.to_parquet(boot_dist_path, index=False)
            boot_summary.to_parquet(boot_summary_path, index=False)
            logger.info(
                "Bootstrap done: %d distributions, %d summaries", len(boot_dist), len(boot_summary)
            )

        # PART B: LOTO sensitivity over BAD_1702
        logger.info(
            "PART B: Leave-one-topic-out sensitivity over BAD_1702 (%d topics)...",
            len(BAD_1702_TOPIC_IDS),
        )
        con = get_connection(read_only=True)
        try:
            con.execute("PRAGMA threads=4")
            con.execute("PRAGMA memory_limit='8GB'")
            set_temp_directory(con)
            con.execute("PRAGMA preserve_insertion_order=false")
            loto_df, loto_summary = loto_sensitivity(con)
            loto_df.to_parquet(CORRECTIONS_DIR / "loto_sensitivity.parquet", index=False)
        finally:
            con.close()

        with (AUDITS_DIR / "loto_summary.json").open("w") as fh:
            json.dump(loto_summary, fh, indent=2, default=str)

        full_summary = {
            "n_boot": N_BOOT,
            "n_era_summaries": len(boot_summary),
            "n_loto_topics": len(BAD_1702_TOPIC_IDS),
            "elapsed_s": round(time.time() - t0, 1),
        }
        with (AUDITS_DIR / "bootstrap_full_summary.json").open("w") as fh:
            json.dump(full_summary, fh, indent=2, default=str)
        SENTINEL_DONE.write_text(
            f"bootstrap+loto: DONE — {N_BOOT} resamples × {len(boot_summary)} cells; {len(BAD_1702_TOPIC_IDS)} LOTO; elapsed {time.time() - t0:.1f}s\n"
        )
        return 0
    except Exception as exc:
        tb = traceback.format_exc()
        SENTINEL_FAIL.write_text(f"bootstrap: ERROR — {type(exc).__name__}: {exc}\n\n{tb}\n")
        logger.exception("Bootstrap errored")
        return 2


if __name__ == "__main__":
    sys.exit(main())

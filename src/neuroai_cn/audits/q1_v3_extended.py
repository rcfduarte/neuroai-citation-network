"""Q1 v3 — cross-citation OR with the extended classifier + finer-grained trend analysis.

Extends the production q1_cross_citation in two ways:
1. Field assignment via extended_classifier (subfield 1702 minus BAD + 1707 +
   topic T10502 from 2208), instead of the curated 35-topic core.
2. Adds finer-grained trend analyses per user request 2026-05-08:
   - Rolling 5y and 7y window OLS slopes computed at every year
   - Year-over-year change rates (delta and percentage)
   - Era-anchored slopes: pre-DL (1990-2011), DL emergence (2012-2016),
     DL expansion (2017-2018), brand era (2019-2025), ChatGPT era (2023-2025)
   - Change-point detection (piecewise linear regression with two breakpoints)

Outputs (under data/derived/corrections/20260508/):
    q1_v3_extended_or_by_year.parquet      — primary OR series
    q1_v3_extended_rolling_slopes.parquet  — rolling 5y/7y OLS slopes per year
    q1_v3_extended_yoy.parquet             — year-over-year deltas
    q1_v3_extended_era_slopes.parquet      — era-anchored slopes
    q1_v3_extended_changepoints.parquet    — detected breakpoints

Sentinel: _q1v3_extended.done in audits/20260508/.

The OR formula is unchanged (E2 locked); only the field-assignment scheme +
post-hoc trend analyses are modified.
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
from scipy.stats import t as t_dist

from .. import config
from ..utils.duckdb import get_connection, set_temp_directory
from .extended_classifier import build_extended_field_assignment

logger = logging.getLogger(__name__)

AUDITS_DIR = config.AUDITS_DIR / "20260508"
CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"
SENTINEL_DONE = AUDITS_DIR / "_q1v3_extended.done"
SENTINEL_FAIL = AUDITS_DIR / "_q1v3_extended.failed"

YEAR_MIN = 1990
YEAR_MAX = 2025

# Era anchors per user 2026-05-08, updated 2026-05-14 to use disjoint primary
# eras with DL expansion widened to 4 years (2016-2019) for stable OLS.
# ChatGPT-era + BERT-to-GPT4 retained as overlapping sub-eras for panel C.
ERAS = [
    ("pre-DL", 1990, 2011),
    ("DL-emergence", 2012, 2015),
    ("DL-expansion", 2016, 2019),
    ("brand-era", 2020, 2025),
    ("ChatGPT-era", 2023, 2025),
    ("BERT-to-GPT4", 2018, 2024),
]


def _odds_ratio(rho: float, rho_null: float) -> float:
    if rho_null <= 0 or rho_null >= 1:
        return float("nan")
    if rho <= 0:
        return 0.0
    if rho >= 1:
        return float("inf")
    return (rho / (1 - rho)) / (rho_null / (1 - rho_null))


def _wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    z2 = z * z
    denom = 1 + z2 / n
    centre = p + z2 / (2 * n)
    spread = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return ((centre - spread) / denom, (centre + spread) / denom)


def compute_or_by_year(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Compute per-year per-direction OR_restricted + OR_population using
    the extended-classifier work_field temp table."""
    pop_rows = con.execute(
        f"""
        SELECT
            year,
            SUM(CASE WHEN field = 'neuro' THEN 1 ELSE 0 END) AS n_neuro,
            SUM(CASE WHEN field = 'ai' THEN 1 ELSE 0 END) AS n_ai,
            SUM(CASE WHEN field = 'other' THEN 1 ELSE 0 END) AS n_other,
            COUNT(*) AS n_total
        FROM work_field
        WHERE year BETWEEN {YEAR_MIN} AND {YEAR_MAX}
        GROUP BY year
        ORDER BY year
        """
    ).fetchall()
    pop = {
        int(r[0]): {"neuro": int(r[1]), "ai": int(r[2]), "other": int(r[3]), "total": int(r[4])}
        for r in pop_rows
    }

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
          AND src.field IN ('neuro','ai')
        GROUP BY e.citing_year, src.field, tgt.field
        """
    ).fetchall()

    edge_dict: dict[tuple[int, str, str | None], int] = {}
    for y, sf, tf, n in edge_rows:
        edge_dict[(int(y), sf, tf)] = int(n)

    out_rows = []
    for year in sorted({k[0] for k in edge_dict}):
        for src in ("neuro", "ai"):
            tgt = "ai" if src == "neuro" else "neuro"
            n_within = edge_dict.get((year, src, src), 0)
            n_target = edge_dict.get((year, src, tgt), 0)
            n_other = edge_dict.get((year, src, "other"), 0)
            n_unknown = edge_dict.get((year, src, "unknown"), 0)
            n_missing = edge_dict.get((year, src, None), 0)
            denom_r = n_within + n_target
            rho_r = n_target / denom_r if denom_r > 0 else float("nan")
            denom_p = n_within + n_target + n_other + n_unknown
            rho_p = n_target / denom_p if denom_p > 0 else float("nan")

            popy = pop.get(year, {"neuro": 0, "ai": 0, "other": 0, "total": 0})
            n_target_pop = popy[tgt]
            n_src_pop = popy[src]
            n_other_pop = popy["other"]
            denom_null_r = n_src_pop + n_target_pop
            rho_null_r = n_target_pop / denom_null_r if denom_null_r > 0 else float("nan")
            denom_null_p = n_src_pop + n_target_pop + n_other_pop
            rho_null_p = n_target_pop / denom_null_p if denom_null_p > 0 else float("nan")

            or_r = (
                _odds_ratio(rho_r, rho_null_r)
                if not (math.isnan(rho_r) or math.isnan(rho_null_r))
                else float("nan")
            )
            or_p = (
                _odds_ratio(rho_p, rho_null_p)
                if not (math.isnan(rho_p) or math.isnan(rho_null_p))
                else float("nan")
            )

            r_lo, r_hi = _wilson(rho_r, denom_r) if denom_r > 0 else (0.0, 0.0)
            p_lo, p_hi = _wilson(rho_p, denom_p) if denom_p > 0 else (0.0, 0.0)
            or_r_lo = _odds_ratio(r_lo, rho_null_r) if not math.isnan(rho_null_r) else float("nan")
            or_r_hi = _odds_ratio(r_hi, rho_null_r) if not math.isnan(rho_null_r) else float("nan")
            or_p_lo = _odds_ratio(p_lo, rho_null_p) if not math.isnan(rho_null_p) else float("nan")
            or_p_hi = _odds_ratio(p_hi, rho_null_p) if not math.isnan(rho_null_p) else float("nan")

            out_rows.append(
                {
                    "year": year,
                    "direction": f"{src}_to_{tgt}",
                    "n_to_within": n_within,
                    "n_to_target": n_target,
                    "n_to_other": n_other,
                    "n_to_unknown": n_unknown,
                    "n_to_missing": n_missing,
                    "rho_restricted": rho_r,
                    "rho_null_restricted": rho_null_r,
                    "rho_population": rho_p,
                    "rho_null_population": rho_null_p,
                    "or_restricted": or_r,
                    "or_restricted_lo": or_r_lo,
                    "or_restricted_hi": or_r_hi,
                    "or_population": or_p,
                    "or_population_lo": or_p_lo,
                    "or_population_hi": or_p_hi,
                    "n_works_source": n_src_pop,
                    "n_works_target": n_target_pop,
                    "n_works_other": n_other_pop,
                }
            )
    return pd.DataFrame(out_rows)


def ols_slope(x: np.ndarray, y: np.ndarray) -> dict:
    """Numpy-only OLS regression. Returns slope, intercept, r2, se, t, p."""
    mask = ~np.isnan(y)
    x = x[mask].astype(float)
    y = y[mask].astype(float)
    n = len(x)
    if n < 3:
        return {
            "n": n,
            "slope": float("nan"),
            "intercept": float("nan"),
            "r2": float("nan"),
            "se": float("nan"),
            "t": float("nan"),
            "p": float("nan"),
        }
    x_mean = x.mean()
    y_mean = y.mean()
    sxx = float(((x - x_mean) ** 2).sum())
    sxy = float(((x - x_mean) * (y - y_mean)).sum())
    if sxx == 0:
        return {
            "n": n,
            "slope": float("nan"),
            "intercept": float("nan"),
            "r2": float("nan"),
            "se": float("nan"),
            "t": float("nan"),
            "p": float("nan"),
        }
    slope = sxy / sxx
    intercept = y_mean - slope * x_mean
    yhat = slope * x + intercept
    ss_res = float(((y - yhat) ** 2).sum())
    ss_tot = float(((y - y_mean) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    s_err = math.sqrt(ss_res / (n - 2)) if n > 2 else float("nan")
    se = s_err / math.sqrt(sxx) if sxx > 0 else float("nan")
    t = slope / se if se and not math.isnan(se) and se > 0 else float("nan")
    # Two-tailed p from the t distribution (scipy is a hard dependency; no silent fallback).
    p = 2.0 * (1.0 - float(t_dist.cdf(abs(t), df=n - 2))) if not math.isnan(t) else float("nan")
    return {"n": n, "slope": slope, "intercept": intercept, "r2": r2, "se": se, "t": t, "p": p}


def rolling_slopes(df: pd.DataFrame, window: int) -> pd.DataFrame:
    """Compute rolling-window OLS slopes per (direction, metric, end_year).
    Window = number of years covered (e.g., 5 = 5 consecutive years)."""
    out = []
    for direction in ("ai_to_neuro", "neuro_to_ai"):
        sub = df[df["direction"] == direction].sort_values("year")
        years = sub["year"].to_numpy()
        for metric in ("or_restricted", "or_population"):
            vals = sub[metric].to_numpy()
            for i in range(window - 1, len(years)):
                yslice = years[i - window + 1 : i + 1]
                vslice = vals[i - window + 1 : i + 1]
                stats = ols_slope(yslice.astype(float), vslice.astype(float))
                out.append(
                    {
                        "direction": direction,
                        "metric": metric,
                        "window_size": window,
                        "window_start": int(yslice[0]),
                        "window_end": int(yslice[-1]),
                        **stats,
                    }
                )
    return pd.DataFrame(out)


def yoy_changes(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for direction in ("ai_to_neuro", "neuro_to_ai"):
        sub = df[df["direction"] == direction].sort_values("year").reset_index(drop=True)
        for metric in ("or_restricted", "or_population"):
            for i in range(1, len(sub)):
                prev = sub.loc[i - 1, metric]
                curr = sub.loc[i, metric]
                delta = curr - prev
                pct = (
                    (delta / prev) if prev and not math.isnan(prev) and prev != 0 else float("nan")
                )
                out.append(
                    {
                        "direction": direction,
                        "metric": metric,
                        "year": int(sub.loc[i, "year"]),
                        "prev_value": prev,
                        "curr_value": curr,
                        "delta": delta,
                        "pct_change": pct,
                    }
                )
    return pd.DataFrame(out)


def era_slopes(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for direction in ("ai_to_neuro", "neuro_to_ai"):
        sub = df[df["direction"] == direction]
        for label, lo, hi in ERAS:
            sub2 = sub[(sub["year"] >= lo) & (sub["year"] <= hi)]
            if sub2.empty:
                continue
            x = sub2["year"].to_numpy(dtype=float)
            for metric in ("or_restricted", "or_population"):
                y = sub2[metric].to_numpy(dtype=float)
                stats = ols_slope(x, y)
                out.append(
                    {
                        "direction": direction,
                        "metric": metric,
                        "era": label,
                        "year_min": lo,
                        "year_max": hi,
                        **stats,
                    }
                )
    return pd.DataFrame(out)


def detect_changepoints(df: pd.DataFrame, max_breakpoints: int = 2) -> pd.DataFrame:
    """Detect 1 or 2 breakpoints by exhaustive search minimizing total residual sum.

    For 1 breakpoint at year y*: fit two OLS lines to [year_min, y*] and [y*+1, year_max].
    Pick y* minimizing sum of residuals. Same for 2 breakpoints.
    """
    out = []
    for direction in ("ai_to_neuro", "neuro_to_ai"):
        for metric in ("or_restricted", "or_population"):
            sub = df[df["direction"] == direction].sort_values("year")
            years = sub["year"].to_numpy()
            vals = sub[metric].to_numpy()
            mask = ~np.isnan(vals)
            years = years[mask]
            vals = vals[mask]
            if len(years) < 6:
                continue

            def fit_segments(
                splits: list[int], _years=years, _vals=vals
            ) -> tuple[float, list[dict]]:
                """splits = list of indices where segments end (inclusive). Each segment >= 3 pts.

                _years/_vals are bound at definition time to avoid late-binding issues
                (the outer years/vals get rebound on each metric/direction iteration).
                """
                segments = []
                start = 0
                total_ss = 0.0
                for end in [*splits, len(_years) - 1]:
                    if end - start + 1 < 3:
                        return float("inf"), []
                    x = _years[start : end + 1].astype(float)
                    y = _vals[start : end + 1].astype(float)
                    s = ols_slope(x, y)
                    if math.isnan(s["slope"]):
                        return float("inf"), []
                    yhat = s["slope"] * x + s["intercept"]
                    ss_res = float(((y - yhat) ** 2).sum())
                    total_ss += ss_res
                    segments.append(
                        {
                            "year_start": int(_years[start]),
                            "year_end": int(_years[end]),
                            "slope": s["slope"],
                            "intercept": s["intercept"],
                            "r2": s["r2"],
                            "n": s["n"],
                        }
                    )
                    start = end + 1
                return total_ss, segments

            best = {"n_breakpoints": 0, "ss": float("inf"), "segments": []}
            # 0 breakpoints baseline
            ss0, segs0 = fit_segments([])
            best = {"n_breakpoints": 0, "ss": ss0, "segments": segs0}
            # 1 breakpoint
            for end0 in range(2, len(years) - 3):
                ss, segs = fit_segments([end0])
                if ss < best["ss"]:
                    best = {"n_breakpoints": 1, "ss": ss, "segments": segs}
            # 2 breakpoints
            if max_breakpoints >= 2 and len(years) >= 9:
                for end0 in range(2, len(years) - 6):
                    for end1 in range(end0 + 3, len(years) - 3):
                        ss, segs = fit_segments([end0, end1])
                        if ss < best["ss"]:
                            best = {"n_breakpoints": 2, "ss": ss, "segments": segs}

            for i, seg in enumerate(best["segments"]):
                out.append(
                    {
                        "direction": direction,
                        "metric": metric,
                        "n_breakpoints_optimal": best["n_breakpoints"],
                        "segment_index": i,
                        "year_start": seg["year_start"],
                        "year_end": seg["year_end"],
                        "slope": seg["slope"],
                        "intercept": seg["intercept"],
                        "r2": seg["r2"],
                        "n_years": seg["n"],
                        "total_ss": best["ss"],
                    }
                )
    return pd.DataFrame(out)


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
            logger.info("Building extended field assignment (work_field temp table)...")
            pop = build_extended_field_assignment(con, year_min=YEAR_MIN, year_max=YEAR_MAX)
            logger.info("Computing OR by year (extended scheme)...")
            df_or = compute_or_by_year(con)
            df_or.to_parquet(CORRECTIONS_DIR / "q1_v3_extended_or_by_year.parquet", index=False)
            logger.info("Wrote OR-by-year: %d rows", len(df_or))

            logger.info("Computing rolling slopes (5y, 7y)...")
            roll_5 = rolling_slopes(df_or, window=5)
            roll_7 = rolling_slopes(df_or, window=7)
            roll = pd.concat([roll_5, roll_7], ignore_index=True)
            roll.to_parquet(CORRECTIONS_DIR / "q1_v3_extended_rolling_slopes.parquet", index=False)
            logger.info("Wrote rolling slopes: %d rows", len(roll))

            logger.info("Computing year-over-year deltas...")
            yoy = yoy_changes(df_or)
            yoy.to_parquet(CORRECTIONS_DIR / "q1_v3_extended_yoy.parquet", index=False)

            logger.info("Computing era-anchored slopes...")
            eras_df = era_slopes(df_or)
            eras_df.to_parquet(CORRECTIONS_DIR / "q1_v3_extended_era_slopes.parquet", index=False)

            logger.info("Detecting changepoints (up to 2 breakpoints)...")
            cps = detect_changepoints(df_or, max_breakpoints=2)
            cps.to_parquet(CORRECTIONS_DIR / "q1_v3_extended_changepoints.parquet", index=False)

            # Summary metadata
            summary = {
                "scheme": "extended (subfield 1702 minus BAD + 1707 + T10502)",
                "n_works_assigned": pop,
                "year_range": [YEAR_MIN, YEAR_MAX],
                "n_or_rows": len(df_or),
                "n_rolling_rows": len(roll),
                "n_yoy_rows": len(yoy),
                "n_era_rows": len(eras_df),
                "n_changepoint_segments": len(cps),
                "elapsed_s": time.time() - t0,
            }
            with (AUDITS_DIR / "q1_v3_extended_summary.json").open("w") as fh:
                json.dump(summary, fh, indent=2, default=str)
        finally:
            con.close()
        elapsed = time.time() - t0
        SENTINEL_DONE.write_text(
            f"q1_v3_extended: DONE — extended OR + rolling/yoy/era/changepoint analyses; elapsed {elapsed:.1f}s\n"
        )
        logger.info("Q1 v3 extended DONE in %.1fs", elapsed)
        return 0
    except Exception as exc:
        tb = traceback.format_exc()
        SENTINEL_FAIL.write_text(f"q1_v3_extended: ERROR — {type(exc).__name__}: {exc}\n\n{tb}\n")
        logger.exception("Q1 v3 extended errored")
        return 2


if __name__ == "__main__":
    sys.exit(main())

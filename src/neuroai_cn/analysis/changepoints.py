"""Change points of the citation-flow odds ratio, recomputed from ``results/flow/or_by_year.csv`` only.

Two different procedures are run on the same series (``or_restricted``, the yearly odds ratio the
figure plots; thin line, not the 5-year mean) and everything is written to
``results/flow/changepoints.csv`` and ``results/flow/segment_slopes.csv``.

1. ``piecewise-OLS exhaustive``: the search the article figure uses, called through the very function
   the figure calls (``figures.cross_source.detect_changepoints_series``): zero, one or two
   breakpoints, every placement tried, the set with the smallest total squared error kept, each
   segment an OLS line.
   * ``figure``: window 1995-2023, at most 2 breakpoints, minimum segment 4 years (as coded).
   * ``audit``: window 1990-2025, minimum segment 3 years, a re-implementation of the search in
     ``audits/q1_v3_extended.py`` that produced ``q1_v3_extended_changepoints.parquet`` and the
     breakpoints (2005, 2022 and 1993, 2005) that the docs call "PELT" (see the finding below).
2. ``PELT`` (Killick, Fearnhead and Eckley 2012) from the ``ruptures`` package. Settings declared in
   advance and all reported, none tuned: cost ``l2`` on the series standardized to mean 0 and
   standard deviation 1 (ddof = 0, within the analysed window), ``min_size`` 3, ``jump`` 1, and the
   penalty per segment ``pen = c * sigma2 * ln(n)`` with one free parameter per segment (the segment
   mean) and ``sigma2 = 1`` (the variance of the standardized series, which is the ruptures
   documentation convention): ``BIC`` c = 1, ``2xBIC`` c = 2, and an ``AIC-like`` constant penalty
   ``2 * sigma2 * 1 = 2``. ``n`` is the number of years in the window. Windows: 1990-2025 (the
   whole series) and 1995-2023 (the window the OLS search uses).

A further block (``declared_in_advance = False``) repeats PELT on other series or windows only to
see which choice comes closest to the old numbers; it is labelled exploratory and is not a source
claim.

Breakpoint convention. ``first_of_new`` is the first year of the new segment (what the figure
labels and what ``year_start`` of the next segment in the parquet holds); ``last_of_old`` is the last
year of the old segment, which is one year earlier. A break reported as "2005" in one convention is
"2006" in the other. ``ruptures`` returns the index of the first point of the new segment, so its
natural convention is ``first_of_new``.

    python -m neuroai_cn.analysis.changepoints
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from .. import config
from ..figures.cross_source import detect_changepoints_series

FLOW_DIR = config.RESULTS_DIR / "flow"
OR_BY_YEAR_CSV = FLOW_DIR / "or_by_year.csv"

DIRECTIONS = ("neuro_to_ai", "ai_to_neuro")
CITING_LABEL = {
    "neuro_to_ai": "neuroscience papers citing AI",
    "ai_to_neuro": "AI papers citing neuroscience",
}
OLS_WINDOW_FIGURE = (1995, 2023)
OLS_WINDOW_AUDIT = (1990, 2025)
PELT_WINDOWS = ((1990, 2025), (1995, 2023))
PELT_MIN_SIZE = 3
PELT_PENALTIES = (("BIC", 1.0, True), ("2xBIC", 2.0, True), ("AIC-like", None, False))
AIC_LIKE_PENALTY = 2.0

CP_COLUMNS = [
    "procedure",
    "setting",
    "series",
    "direction",
    "citing_field",
    "window",
    "declared_in_advance",
    "n_years",
    "n_breakpoints",
    "breakpoint_rank",
    "breakpoint_year_first_of_new_segment",
    "breakpoint_year_last_of_old_segment",
]
SLOPE_COLUMNS = [
    "procedure",
    "setting",
    "series",
    "direction",
    "citing_field",
    "window",
    "declared_in_advance",
    "segment_index",
    "year_start",
    "year_end",
    "n_years",
    "slope_per_year",
    "se_slope",
    "ci95_lo",
    "ci95_hi",
    "r2",
]


def load_or_by_year(path=OR_BY_YEAR_CSV) -> pd.DataFrame:
    """The committed snapshot table (36 years x 2 directions)."""
    return pd.read_csv(path, float_precision="round_trip")


def get_series(
    df: pd.DataFrame, direction: str, window: tuple[int, int], series: str = "or_restricted"
) -> tuple[np.ndarray, np.ndarray]:
    """Years and values of one direction inside an inclusive year window."""
    s = df[(df["direction"] == direction) & df["year"].between(*window)].sort_values("year")
    if series == "log_or_restricted":
        vals = np.log(s["or_restricted"].to_numpy(dtype=float))
    else:
        vals = s[series].to_numpy(dtype=float)
    return s["year"].to_numpy(dtype=int), vals


def segment_stats(years: np.ndarray, vals: np.ndarray, first_years: list[int]) -> list[dict]:
    """OLS line per segment, segments starting at ``first_years`` (first one is the window start).

    Returns slope per year, its standard error, the 95% t interval (df = n - 2) and R2.
    """
    starts = sorted(first_years)
    ends = [s - 1 for s in starts[1:]] + [int(years[-1])]
    out = []
    for i, (lo, hi) in enumerate(zip(starts, ends, strict=True)):
        m = (years >= lo) & (years <= hi)
        x, y = years[m].astype(float), vals[m]
        n = len(x)
        sxx = float(((x - x.mean()) ** 2).sum())
        slope = float(((x - x.mean()) * (y - y.mean())).sum() / sxx)
        icpt = float(y.mean() - slope * x.mean())
        sse = float(((y - (icpt + slope * x)) ** 2).sum())
        sst = float(((y - y.mean()) ** 2).sum())
        se = math.sqrt(sse / (n - 2) / sxx) if n > 2 else float("nan")
        tq = float(stats.t.ppf(0.975, n - 2)) if n > 2 else float("nan")
        out.append(
            {
                "segment_index": i,
                "year_start": int(lo),
                "year_end": int(hi),
                "n_years": n,
                "slope_per_year": slope,
                "se_slope": se,
                "ci95_lo": slope - tq * se,
                "ci95_hi": slope + tq * se,
                "r2": 1 - sse / sst if sst > 0 else float("nan"),
            }
        )
    return out


def ols_breakpoints(
    years: np.ndarray, vals: np.ndarray, min_segment: int, max_breakpoints: int = 2
) -> list[int]:
    """First year of each new segment from the exhaustive piecewise-OLS search of the figure."""
    segs = detect_changepoints_series(
        years, vals, max_breakpoints=max_breakpoints, min_segment=min_segment
    )
    return [int(s["year_start"]) for s in segs[1:]]


def pelt_breakpoints(
    years: np.ndarray, vals: np.ndarray, penalty: float, min_size: int = PELT_MIN_SIZE
) -> list[int]:
    """First year of each new segment from ruptures PELT (l2 cost) on the standardized series."""
    import ruptures as rpt  # imported here so that the OLS part works without the package

    z = (vals - vals.mean()) / vals.std()  # ddof = 0, so the variance is exactly 1
    ends = (
        rpt.Pelt(model="l2", min_size=min_size, jump=1).fit(z.reshape(-1, 1)).predict(pen=penalty)
    )
    return [
        int(years[e]) for e in ends[:-1]
    ]  # drop the terminal n; e = index of first point of new


def pelt_penalty(label: str, factor: float | None, n: int, sigma2: float = 1.0) -> float:
    """Penalty per segment: factor * sigma2 * ln(n) (BIC family) or the AIC-like constant 2 * sigma2."""
    if factor is None:
        return AIC_LIKE_PENALTY * sigma2
    return factor * sigma2 * math.log(n)


def _record(frames_cp, frames_sl, meta, years, vals, breaks):
    n_bp = len(breaks)
    base = {**meta, "n_years": len(years), "n_breakpoints": n_bp}
    if n_bp == 0:
        frames_cp.append(
            {
                **base,
                "breakpoint_rank": np.nan,
                "breakpoint_year_first_of_new_segment": np.nan,
                "breakpoint_year_last_of_old_segment": np.nan,
            }
        )
    for r, b in enumerate(breaks, start=1):
        prev = years[np.searchsorted(years, b) - 1]
        frames_cp.append(
            {
                **base,
                "breakpoint_rank": r,
                "breakpoint_year_first_of_new_segment": int(b),
                "breakpoint_year_last_of_old_segment": int(prev),
            }
        )
    for seg in segment_stats(years, vals, [int(years[0]), *breaks]):
        frames_sl.append({**meta, **seg})


def run_all(df: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Every procedure and setting; returns (changepoints, segment_slopes) tables."""
    df = load_or_by_year() if df is None else df
    cps: list[dict] = []
    sls: list[dict] = []

    def meta(procedure, setting, series, direction, window, declared):
        return {
            "procedure": procedure,
            "setting": setting,
            "series": series,
            "direction": direction,
            "citing_field": CITING_LABEL[direction],
            "window": f"{window[0]}-{window[1]}",
            "declared_in_advance": declared,
        }

    for d in DIRECTIONS:
        # 1. exhaustive piecewise OLS
        for win, mseg, label, declared in (
            (OLS_WINDOW_FIGURE, 4, "figure: max 2 breakpoints, min segment 4", True),
            (OLS_WINDOW_AUDIT, 3, "audit: max 2 breakpoints, min segment 3", True),
            (OLS_WINDOW_FIGURE, 3, "max 2 breakpoints, min segment 3", False),
        ):
            years, vals = get_series(df, d, win)
            b = ols_breakpoints(years, vals, mseg)
            m = meta("piecewise-OLS exhaustive", label, "or_restricted", d, win, declared)
            _record(cps, sls, m, years, vals, b)

        # 2. PELT: declared grid
        for win in PELT_WINDOWS:
            years, vals = get_series(df, d, win)
            for pen_label, factor, _ in PELT_PENALTIES:
                pen = pelt_penalty(pen_label, factor, len(years))
                b = pelt_breakpoints(years, vals, pen)
                setting = f"l2, standardized, min_size 3, {pen_label} (pen {pen:.4f})"
                m = meta("PELT (ruptures)", setting, "or_restricted", d, win, True)
                _record(cps, sls, m, years, vals, b)

        # 3. PELT: exploratory neighbours (other series, one extra window), same three penalties
        for series, win in (
            ("or_population", (1990, 2025)),
            ("or_population", (1995, 2023)),
            ("log_or_restricted", (1990, 2025)),
            ("log_or_restricted", (1995, 2023)),
            ("or_restricted", (1990, 2023)),
        ):
            years, vals = get_series(df, d, win, series)
            for pen_label, factor, _ in PELT_PENALTIES:
                pen = pelt_penalty(pen_label, factor, len(years))
                b = pelt_breakpoints(years, vals, pen)
                setting = f"l2, standardized, min_size 3, {pen_label} (pen {pen:.4f})"
                m = meta("PELT (ruptures)", setting, series, d, win, False)
                _record(cps, sls, m, years, vals, b)

    cp_df = pd.DataFrame(cps)[CP_COLUMNS]
    for c in ("breakpoint_rank", "breakpoint_year_first_of_new_segment"):
        cp_df[c] = cp_df[c].astype("Int64")
    cp_df["breakpoint_year_last_of_old_segment"] = cp_df[
        "breakpoint_year_last_of_old_segment"
    ].astype("Int64")
    return cp_df, pd.DataFrame(sls)[SLOPE_COLUMNS]


def main() -> None:
    cp_df, sl_df = run_all()
    FLOW_DIR.mkdir(parents=True, exist_ok=True)
    cp_df.to_csv(FLOW_DIR / "changepoints.csv", index=False)
    sl_df.to_csv(FLOW_DIR / "segment_slopes.csv", index=False)
    print(FLOW_DIR / "changepoints.csv", len(cp_df))
    print(FLOW_DIR / "segment_slopes.csv", len(sl_df))


if __name__ == "__main__":
    main()

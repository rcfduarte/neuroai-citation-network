"""Cross-source data loading + per-1000 / slope helpers for figure1_main_v2.

Loads the OpenAlex snapshot (March 2026) and the three cross-source cell files
(OpenAlex re-downloaded May 2026 strict + extended, Semantic Scholar) and
returns a unified long-format DataFrame with `per1000` and Wilson CIs.

See `ContentLab/commissioned-pieces/TheTransmitter/neuroai-cross-pollination/
fig1-construction-brief-20260528.md` for spec.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

from .. import config

# Default: read the committed CSVs under results/ (written by analysis/export_flow_inputs.py).
# Heavy-data variant: NEUROAI_FLOW_SOURCE=heavy reads the DuckDB-derived parquet under
# $NEUROAI_DATA and the raw cells.jsonl files under $NEUROAI_CELLS_ROOT (default <repo>/data/derived).
FLOW_DIR = config.RESULTS_DIR / "flow"
CROSS_DIR = config.RESULTS_DIR / "crosssource"
OR_BY_YEAR_CSV = FLOW_DIR / "or_by_year.csv"
SNAPSHOT_PARQUET = (
    config.DERIVED_DIR / "corrections" / "20260508" / "q1_v3_extended_or_by_year.parquet"
)
_CELLS_ROOT = Path(os.environ.get("NEUROAI_CELLS_ROOT", config.REPO_ROOT / "data" / "derived"))


def heavy_source() -> bool:
    """True when the heavy-data (parquet + jsonl) variant is requested."""
    return os.environ.get("NEUROAI_FLOW_SOURCE", "csv").lower() == "heavy"


def load_snapshot_table() -> pd.DataFrame:
    """The 72-row snapshot table (36 years x 2 directions), from CSV or, if requested, parquet."""
    if heavy_source():
        return pd.read_parquet(SNAPSHOT_PARQUET)
    return pd.read_csv(OR_BY_YEAR_CSV, float_precision="round_trip")


_CELLS_FILES = {
    "oa_live_strict": ("openalex_live", "api_crosscite/openalex_live/cells.jsonl"),
    "oa_live_extended": (
        "openalex_live_extended",
        "api_crosscite/openalex_live_extended/cells.jsonl",
    ),
    "s2": ("s2", "api_crosscite/s2/cells.jsonl"),
}


def _cells_path(source: str) -> Path | None:
    if source not in _CELLS_FILES:
        return None
    stem, rel = _CELLS_FILES[source]
    return _CELLS_ROOT / rel if heavy_source() else CROSS_DIR / f"{stem}.csv"


def _read_cells(p: Path) -> list[dict]:
    """Rows of a cells file as plain dicts (absent fields dropped), from .csv or .jsonl."""
    if p.suffix == ".jsonl":
        return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]
    df = pd.read_csv(p, float_precision="round_trip")
    return [{k: v for k, v in r.items() if not pd.isna(v)} for r in df.to_dict("records")]


DIRECTIONS = ("neuro_to_ai", "ai_to_neuro")  # data convention


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 95% CI on a binomial proportion p = k/n.

    Returns (lo, hi) on the proportion scale (multiply by 1000 for per1000).
    """
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, centre - half), min(1.0, centre + half))


def load_snapshot_per1000() -> pd.DataFrame:
    """Snapshot parquet -> long-format per-1000 + Wilson CIs.

    Uses the POPULATION (full-classified) denominator: within + target + other.
    This matches `rho_population * 1000` and is the metric the verification
    verdict (openalex-spike-verification-20260528) uses for its cross-source
    diff tables ("snapshot extended" / "OA-live extended" columns).

    "Population per-1000" reads as: "of every 1,000 references in this paper's
    bibliography, how many cross to the other field". The restricted version
    (target/(within+target)) is sensitive to within-field growth (e.g. AI's
    internal citation boom mechanically depresses ai_to_neuro restricted shares)
    and so is reserved for the OR analysis where the within-rate confound is
    explicitly modelled by the null.

    Returns columns: source, direction, year, per1000, ci_lo, ci_hi, n_target,
                     n_classified  (n_classified = within + target + other)
    """
    df = load_snapshot_table()
    needed = {
        "year",
        "direction",
        "n_to_within",
        "n_to_target",
        "n_to_other",
    }
    missing = needed - set(df.columns)
    assert not missing, f"snapshot parquet missing columns: {missing}"

    df = df[["year", "direction", "n_to_within", "n_to_target", "n_to_other"]].copy()
    # POPULATION denominator: within + target + other (matches verdict, matches
    # cells per1000 convention)
    df["n_classified"] = df["n_to_within"] + df["n_to_target"] + df["n_to_other"]
    df["per1000"] = df["n_to_target"] / df["n_classified"] * 1000.0
    cis = df.apply(
        lambda r: wilson_ci(int(r["n_to_target"]), int(r["n_classified"])),
        axis=1,
    )
    df["ci_lo"] = cis.map(lambda t: t[0] * 1000.0)
    df["ci_hi"] = cis.map(lambda t: t[1] * 1000.0)
    df["source"] = "snapshot"
    df["n_target"] = df["n_to_target"]
    return (
        df[["source", "direction", "year", "per1000", "ci_lo", "ci_hi", "n_target", "n_classified"]]
        .sort_values(["direction", "year"])
        .reset_index(drop=True)
    )


def load_cells_per1000(source: str) -> pd.DataFrame:
    """Cross-source cells -> long-format per-1000 + Wilson CIs.

    Uses the cells file's existing per1000 field (target / n_refs_classified) which
    is the POPULATION metric (within + target + other), matching the snapshot
    loader convention.
    """
    p = _cells_path(source)
    if p is None or not p.exists():
        return pd.DataFrame(
            columns=[
                "source",
                "direction",
                "year",
                "per1000",
                "ci_lo",
                "ci_hi",
                "n_target",
                "n_classified",
            ]
        )
    rows = []
    for c in _read_cells(p):
        n_target = int(c.get("target", 0))
        n_classified = int(c.get("n_refs_classified", 0))
        if n_classified == 0:
            continue
        per1000 = float(c.get("per1000", n_target / n_classified * 1000.0))
        ci_lo = float(c.get("ci_lo", 0.0))
        ci_hi = float(c.get("ci_hi", 0.0))
        rows.append(
            {
                "source": source,
                "direction": c["direction"],
                "year": int(c["year"]),
                "per1000": per1000,
                "ci_lo": ci_lo,
                "ci_hi": ci_hi,
                "n_target": n_target,
                "n_classified": n_classified,
            }
        )
    return pd.DataFrame(rows).sort_values(["direction", "year"]).reset_index(drop=True)


def load_snapshot_or() -> pd.DataFrame:
    """Snapshot parquet -> long-format OR_restricted + CI.

    Returns columns: source, direction, year, value, ci_lo, ci_hi, rho_null
    where 'value' is OR_restricted and rho_null is needed to back-compute
    implied OR for cross-source cells (which only have rho_obs).
    """
    df = load_snapshot_table()
    needed = {
        "year",
        "direction",
        "or_restricted",
        "or_restricted_lo",
        "or_restricted_hi",
        "rho_null_restricted",
        "n_to_within",
        "n_to_target",
    }
    missing = needed - set(df.columns)
    assert not missing, f"snapshot parquet missing columns: {missing}"
    df = df[
        [
            "year",
            "direction",
            "or_restricted",
            "or_restricted_lo",
            "or_restricted_hi",
            "rho_null_restricted",
            "n_to_within",
            "n_to_target",
        ]
    ].copy()
    df["source"] = "snapshot"
    df["value"] = df["or_restricted"]
    df["ci_lo"] = df["or_restricted_lo"]
    df["ci_hi"] = df["or_restricted_hi"]
    df["rho_null"] = df["rho_null_restricted"]
    return (
        df[["source", "direction", "year", "value", "ci_lo", "ci_hi", "rho_null"]]
        .sort_values(["direction", "year"])
        .reset_index(drop=True)
    )


def load_cells_or_implied(source: str, null_df: pd.DataFrame) -> pd.DataFrame:
    """Cross-source cells -> implied OR using the snapshot's rho_null.

    Cells only carry within/target counts; the OR null model (rho_null) depends
    on field population sizes which are not in the cells. We borrow the
    snapshot's rho_null at the same (year, direction) — defensible because
    rho_null reflects field sizes in the corpus, which differ across sources
    but track each other within ~20% (see verdict Check 5).

    Implied OR = (rho_obs / (1 - rho_obs)) / (rho_null / (1 - rho_null))
    where rho_obs = target / (within + target) from the cell.
    """
    p = _cells_path(source)
    if p is None or not p.exists():
        return pd.DataFrame(columns=["source", "direction", "year", "value", "ci_lo", "ci_hi"])
    null_map = {
        (int(r["year"]), r["direction"]): float(r["rho_null"]) for _, r in null_df.iterrows()
    }
    rows = []
    for c in _read_cells(p):
        year = int(c["year"])
        direction = c["direction"]
        within = int(c.get("within", 0))
        target = int(c.get("target", 0))
        n_restricted = within + target
        if n_restricted == 0:
            continue
        rho_obs = target / n_restricted
        rho_null = null_map.get((year, direction))
        if rho_null is None or rho_null in (0.0, 1.0) or rho_obs in (0.0, 1.0):
            continue
        odds_obs = rho_obs / (1 - rho_obs)
        odds_null = rho_null / (1 - rho_null)
        or_val = odds_obs / odds_null if odds_null > 0 else float("nan")
        # Wilson CI on rho_obs, propagated to OR
        ci_lo_p, ci_hi_p = wilson_ci(target, n_restricted)

        def _to_or(p, odds_null=odds_null):
            return (p / (1 - p)) / odds_null if p not in (0.0, 1.0) else float("nan")

        rows.append(
            {
                "source": source,
                "direction": direction,
                "year": year,
                "value": or_val,
                "ci_lo": _to_or(ci_lo_p),
                "ci_hi": _to_or(ci_hi_p),
            }
        )
    return pd.DataFrame(rows).sort_values(["direction", "year"]).reset_index(drop=True)


def load_all_sources_or() -> pd.DataFrame:
    """Snapshot OR + cross-source implied OR (using snapshot's null)."""
    snap = load_snapshot_or()
    frames = [snap[["source", "direction", "year", "value", "ci_lo", "ci_hi"]]]
    null_df = snap[["year", "direction", "rho_null"]].copy()
    # Use same source-precedence as load_all_sources
    extended = load_cells_or_implied("oa_live_extended", null_df)
    strict = load_cells_or_implied("oa_live_strict", null_df)
    if not extended.empty and not strict.empty:
        covered = set(zip(extended["direction"], extended["year"], strict=False))
        fill = strict[~strict.apply(lambda r: (r["direction"], r["year"]) in covered, axis=1)]
        oa_live = pd.concat([extended, fill], ignore_index=True)
    elif not extended.empty:
        oa_live = extended
    else:
        oa_live = strict
    if not oa_live.empty:
        oa_live = oa_live.assign(source="oa_live")
        frames.append(oa_live[["source", "direction", "year", "value", "ci_lo", "ci_hi"]])
    s2 = load_cells_or_implied("s2", null_df)
    if not s2.empty:
        frames.append(s2[["source", "direction", "year", "value", "ci_lo", "ci_hi"]])
    out = pd.concat(frames, ignore_index=True)
    # Rename `value` -> `per1000` so the rest of the figure code can stay
    # agnostic (treat OR as the y-axis quantity)
    out = out.rename(columns={"value": "per1000"})
    return out


def load_all_sources(include_strict_as_fallback: bool = True) -> pd.DataFrame:
    """Load snapshot + all available cross-source cells.

    If `include_strict_as_fallback`, use oa_live_extended where present and
    fall back to oa_live_strict for years not covered by extended (extended
    only covers 2010-2025).
    """
    frames = [load_snapshot_per1000()]
    s2 = load_cells_per1000("s2")
    if not s2.empty:
        frames.append(s2)
    extended = load_cells_per1000("oa_live_extended")
    strict = load_cells_per1000("oa_live_strict")
    if not extended.empty and include_strict_as_fallback and not strict.empty:
        # Use extended where available, fall back to strict elsewhere
        covered = set(zip(extended["direction"], extended["year"], strict=False))
        fill = strict[
            ~strict.apply(lambda r: (r["direction"], r["year"]) in covered, axis=1)
        ].assign(source="oa_live_extended_fallback")
        oa_live = pd.concat([extended, fill], ignore_index=True)
    elif not extended.empty:
        oa_live = extended
    else:
        oa_live = strict
    if not oa_live.empty:
        # Unify label to a single "May download" source for plotting
        oa_live = oa_live.assign(source="oa_live")
        frames.append(oa_live)
    out = pd.concat(frames, ignore_index=True)
    return out


def slope_per_decade(
    df: pd.DataFrame,
    year_min: int = 1990,
    year_max: int = 2023,
) -> pd.DataFrame:
    """OLS slope per decade for per-1000 ~ year, per source × direction.

    Returns columns: source, direction, slope_per_decade, se_per_decade,
                     ci_lo, ci_hi, n_years, r2
    """
    out = []
    for (src, dirn), sub in df.groupby(["source", "direction"], observed=True):
        sub = (
            sub[(sub["year"] >= year_min) & (sub["year"] <= year_max)]
            .dropna(subset=["per1000"])
            .sort_values("year")
        )
        if len(sub) < 5:
            continue
        x = sub["year"].to_numpy(dtype=float)
        y = sub["per1000"].to_numpy(dtype=float)
        # OLS via numpy
        n = len(x)
        xbar, ybar = x.mean(), y.mean()
        sxx = ((x - xbar) ** 2).sum()
        sxy = ((x - xbar) * (y - ybar)).sum()
        slope = sxy / sxx
        intercept = ybar - slope * xbar
        y_hat = intercept + slope * x
        resid = y - y_hat
        sse = (resid**2).sum()
        sst = ((y - ybar) ** 2).sum()
        r2 = 1 - sse / sst if sst > 0 else float("nan")
        # SE on slope
        if n > 2:
            sigma2 = sse / (n - 2)
            se_slope = math.sqrt(sigma2 / sxx)
        else:
            se_slope = float("nan")
        slope_dec = slope * 10
        se_dec = se_slope * 10
        out.append(
            {
                "source": src,
                "direction": dirn,
                "slope_per_decade": slope_dec,
                "se_per_decade": se_dec,
                "ci_lo": slope_dec - 1.96 * se_dec,
                "ci_hi": slope_dec + 1.96 * se_dec,
                "n_years": n,
                "r2": r2,
            }
        )
    return pd.DataFrame(out)


def rolling_mean(y: np.ndarray, window: int = 5) -> np.ndarray:
    """Centered rolling mean, NaN at edges where window doesn't fit."""
    return pd.Series(y).rolling(window=window, center=True, min_periods=3).mean().to_numpy()


def _ols(x: np.ndarray, y: np.ndarray) -> dict:
    n = len(x)
    if n < 2:
        return {
            "slope": float("nan"),
            "intercept": float("nan"),
            "r2": float("nan"),
            "n": n,
            "ss_res": float("nan"),
        }
    xbar, ybar = x.mean(), y.mean()
    sxx = ((x - xbar) ** 2).sum()
    if sxx == 0:
        return {
            "slope": float("nan"),
            "intercept": float("nan"),
            "r2": float("nan"),
            "n": n,
            "ss_res": float("nan"),
        }
    slope = ((x - xbar) * (y - ybar)).sum() / sxx
    intercept = ybar - slope * xbar
    yhat = slope * x + intercept
    ss_res = float(((y - yhat) ** 2).sum())
    sst = float(((y - ybar) ** 2).sum())
    r2 = 1 - ss_res / sst if sst > 0 else float("nan")
    return {"slope": slope, "intercept": intercept, "r2": r2, "n": n, "ss_res": ss_res}


def detect_changepoints_series(
    years: np.ndarray,
    vals: np.ndarray,
    max_breakpoints: int = 2,
    min_segment: int = 4,
) -> list[dict]:
    """Detect 0, 1, or 2 breakpoints by exhaustive search minimizing total SS.

    Adapted from src/neuroai_cn/audits/q1_v3_extended.py::detect_changepoints.

    Returns list of segment dicts:
        [{year_start, year_end, slope, intercept, r2, n}, ...]
    The segment count = breakpoints + 1.
    """
    mask = ~np.isnan(vals)
    years = years[mask].astype(int)
    vals = vals[mask].astype(float)
    n = len(years)
    if n < 2 * min_segment:
        if n < 2:
            return []
        s = _ols(years.astype(float), vals)
        return [
            {
                "year_start": int(years[0]),
                "year_end": int(years[-1]),
                "slope": s["slope"],
                "intercept": s["intercept"],
                "r2": s["r2"],
                "n": s["n"],
            }
        ]

    def fit_at(splits: list[int]) -> tuple[float, list[dict]]:
        segs = []
        start = 0
        total = 0.0
        for end in [*splits, n - 1]:
            if end - start + 1 < min_segment:
                return float("inf"), []
            x = years[start : end + 1].astype(float)
            y = vals[start : end + 1]
            s = _ols(x, y)
            if np.isnan(s["slope"]):
                return float("inf"), []
            total += s["ss_res"]
            segs.append(
                {
                    "year_start": int(years[start]),
                    "year_end": int(years[end]),
                    "slope": s["slope"],
                    "intercept": s["intercept"],
                    "r2": s["r2"],
                    "n": s["n"],
                }
            )
            start = end + 1
        return total, segs

    best_ss, best_segs = fit_at([])
    # 1 breakpoint
    for e0 in range(min_segment - 1, n - min_segment):
        ss, segs = fit_at([e0])
        if ss < best_ss:
            best_ss, best_segs = ss, segs
    # 2 breakpoints (only if enough data)
    if max_breakpoints >= 2 and n >= 3 * min_segment:
        for e0 in range(min_segment - 1, n - 2 * min_segment):
            for e1 in range(e0 + min_segment, n - min_segment):
                ss, segs = fit_at([e0, e1])
                if ss < best_ss:
                    best_ss, best_segs = ss, segs
    return best_segs


def detect_all_changepoints(
    df_all: pd.DataFrame,
    year_min: int = 1990,
    year_max: int = 2023,
    max_breakpoints: int = 2,
) -> pd.DataFrame:
    """Run changepoint detection per (source, direction) on per1000 series.

    Excludes 2024-2025 from CP detection (artifact-affected per
    openalex-spike-verification-20260528).

    Returns long-format DataFrame:
        [source, direction, segment_index, year_start, year_end,
         slope_per_year, slope_per_decade, intercept, r2, n]
    Plus an attribute `.attrs['changepoints']` mapping
    (source, direction) -> list of changepoint years.
    """
    rows = []
    cp_index: dict[tuple[str, str], list[int]] = {}
    for (src, dirn), sub in df_all.groupby(["source", "direction"], observed=True):
        sub = sub[(sub["year"] >= year_min) & (sub["year"] <= year_max)].sort_values("year")
        years = sub["year"].to_numpy(dtype=int)
        vals = sub["per1000"].to_numpy(dtype=float)
        segs = detect_changepoints_series(years, vals, max_breakpoints=max_breakpoints)
        cps = []
        for i, s in enumerate(segs):
            if i > 0:
                cps.append(int(s["year_start"]))
            rows.append(
                {
                    "source": src,
                    "direction": dirn,
                    "segment_index": i,
                    "year_start": s["year_start"],
                    "year_end": s["year_end"],
                    "slope_per_year": s["slope"],
                    "slope_per_decade": s["slope"] * 10,
                    "intercept": s["intercept"],
                    "r2": s["r2"],
                    "n": s["n"],
                }
            )
        cp_index[(src, dirn)] = cps
    out = pd.DataFrame(rows)
    out.attrs["changepoints"] = cp_index
    return out


def consensus_changepoints(
    cp_index: dict[tuple[str, str], list[int]],
    tolerance: int = 3,
) -> dict[str, list[tuple[int, int]]]:
    """Cluster per-(source, direction) changepoints into per-direction consensus.

    Returns: {direction -> [(consensus_year, n_sources_agreeing), ...]}
    A "consensus" is a cluster of CPs within `tolerance` years across sources;
    consensus_year is the rounded mean of the cluster.
    """
    out: dict[str, list[tuple[int, int]]] = {}
    for direction in ("ai_to_neuro", "neuro_to_ai"):
        all_cps = []
        for (src, d), cps in cp_index.items():
            if d != direction:
                continue
            for c in cps:
                all_cps.append((c, src))
        # Simple agglomerative clustering by tolerance
        clusters: list[list[tuple[int, str]]] = []
        for cp, src in sorted(all_cps):
            placed = False
            for cluster in clusters:
                mean_cp = np.mean([c for c, _ in cluster])
                if abs(cp - mean_cp) <= tolerance:
                    cluster.append((cp, src))
                    placed = True
                    break
            if not placed:
                clusters.append([(cp, src)])
        out[direction] = [
            (int(round(np.mean([c for c, _ in cluster]))), len(set(s for _, s in cluster)))  # noqa: RUF046
            for cluster in clusters
        ]
    return out

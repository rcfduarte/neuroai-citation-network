"""Figure 1 of the article (metric "or") and its per-1,000 and combined variants.

`python -m neuroai_cn.figures.figure1_main_v2` (default argument `or`) draws the article's
Figure 1, "Three decades of asymmetric citation", to `figures/figure1_article.png/.svg` and
writes the plotted values to `results/flow/figure1_article_*.csv` (see `write_article_bundle`).
Other arguments: `per1000` (raw-share variant, `figures/figure1_main_v2.*`) and `combined`.

Layout of the article figure:

    Panel A (top) — yearly odds ratio of cross-field citation, March 2026 snapshot, 1995-2025
        * pale band = Wilson 95% CI of the yearly odds ratio
        * thick line = centered 5-year rolling mean (min. 3 points) over 1995-2025
        * open circles 2024-25 = the same quantity from the May 2026 re-download
        * hatched band 2023-25 labelled "2024-25: unstable"
        * dashed verticals = snapshot changepoints (piecewise-linear OLS, 1995-2023)
        * era shading (style.CANONICAL_ERAS), thin verticals = style.TIER1_BRIDGES
    Panel B (bottom left) — OLS slope per year within the four eras, bootstrap CI
    Panel C (bottom right) — OLS slope per year within the changepoint segments
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .. import config
from .cross_source import (
    CROSS_DIR,
    consensus_changepoints,
    detect_all_changepoints,
    load_all_sources,
    load_all_sources_or,
    load_snapshot_table,
    rolling_mean,
)
from .style import (
    CANONICAL_ERAS,
    DIRECTION_COLORS,
    DISPLAY_LABELS_PLAIN,
    TIER1_BRIDGES,
    TRANSMITTER,
    add_era_shading,
    apply_style,
    finalize,
)

logger = logging.getLogger(__name__)

OUT_DIR = config.FIGURES_DIR

X_MIN, X_MAX = 1995, 2025
SETTLING_LO, SETTLING_HI = 2023.0, 2025.5
CP_DETECTION_WINDOW = (1995, 2023)  # exclude 2024-25 from CP detection
BOOTSTRAP_B = 500
RNG_SEED = 20260528

SOURCE_STYLE = {
    "snapshot": {"ls": "-", "lw": 2.8, "alpha": 1.00, "label": "OpenAlex (March 2026)"},
    "oa_live": {"ls": "--", "lw": 1.6, "alpha": 0.85, "label": "OpenAlex (May 2026)"},
    "s2": {"ls": ":", "lw": 1.6, "alpha": 0.85, "label": "Semantic Scholar"},
}
SOURCES = ("snapshot", "oa_live", "s2")
DIRECTIONS = ("neuro_to_ai", "ai_to_neuro")  # data convention


# ---------------------------------------------------------------------------
# Panel A
# ---------------------------------------------------------------------------


RECENT_OVERLAY_LO, RECENT_OVERLAY_HI = 2023, 2025


def _plot_traces(ax: plt.Axes, df_all: pd.DataFrame) -> None:
    """Main traces (full range): snapshot only, bold solid + Wilson CI band.

    Cross-source overlay (OA-live, S2) is drawn separately by
    `_plot_recent_overlay` and confined to the 2023-2025 settling region.
    """
    for direction in DIRECTIONS:
        color = DIRECTION_COLORS[direction]
        sub = df_all[
            (df_all["source"] == "snapshot")
            & (df_all["direction"] == direction)
            & (df_all["year"] >= X_MIN)
            & (df_all["year"] <= X_MAX)
        ].sort_values("year")
        if sub.empty:
            continue
        years = sub["year"].to_numpy(dtype=float)
        y = sub["per1000"].to_numpy(dtype=float)
        ma = rolling_mean(y, window=5)
        lo = sub["ci_lo"].to_numpy(dtype=float)
        hi = sub["ci_hi"].to_numpy(dtype=float)
        ax.fill_between(years, lo, hi, color=color, alpha=0.10, linewidth=0, zorder=1)
        ax.plot(
            years,
            ma,
            color=color,
            linestyle="-",
            linewidth=2.8,
            alpha=1.0,
            zorder=3,
            solid_capstyle="round",
        )


def _plot_recent_overlay(ax: plt.Axes, df_all: pd.DataFrame) -> None:
    """Single markers for the new OpenAlex pull (May 2026) in 2024-25 only.

    No connecting lines, no S2 overlay. Just markers (open circles) to flag
    that a fresh re-download disagrees with the snapshot at those years.
    """
    for direction in DIRECTIONS:
        color = DIRECTION_COLORS[direction]
        sub = df_all[
            (df_all["source"] == "oa_live")
            & (df_all["direction"] == direction)
            & (df_all["year"] >= 2024)
            & (df_all["year"] <= RECENT_OVERLAY_HI)
        ].sort_values("year")
        if sub.empty:
            continue
        ax.plot(
            sub["year"].to_numpy(dtype=float),
            sub["per1000"].to_numpy(dtype=float),
            color=color,
            linestyle="none",
            marker="o",
            markersize=7.0,
            markerfacecolor="none",
            markeredgecolor=color,
            markeredgewidth=1.6,
            alpha=0.9,
            zorder=4,
        )


def _plot_changepoints(
    ax: plt.Axes,
    cp_index: dict[tuple[str, str], list[int]],
) -> None:
    """Snapshot-only changepoints as vertical dashed lines per direction.

    Now that cross-source full traces are removed from the main panel, only
    the snapshot CPs are shown (they are also the eras for Panel B).
    """
    label_y_used: dict[int, float] = {}
    for direction in DIRECTIONS:
        cps = cp_index.get(("snapshot", direction), [])
        color = DIRECTION_COLORS[direction]
        for cp in cps:
            ax.axvline(
                cp,
                color=color,
                linestyle="--",
                linewidth=1.0,
                alpha=0.55,
                zorder=2,
            )
            y_pos = 0.96 - 0.04 * label_y_used.get(cp, 0)
            label_y_used[cp] = label_y_used.get(cp, 0) + 1
            ax.text(
                cp,
                y_pos,
                str(cp),
                transform=ax.get_xaxis_transform(),
                ha="center",
                va="top",
                fontsize=7.5,
                color=color,
                alpha=0.85,
                fontweight="bold",
            )


def _plot_settling_shade(ax: plt.Axes) -> None:
    """Diagonal-hatched shade aligned to 2023 + single italic note.

    The diagonal stripes mark the region as unstable (database still updating).
    Open circles on top of the bold snapshot line in 2024-25 are the new
    OpenAlex pull from May 2026 — they sit off the snapshot trace at those
    years, visibly demonstrating the offset.
    """
    # Diagonal-hatched fill (no fill color, just the hatch pattern + a faint
    # base shade for visibility on light background)
    ax.axvspan(
        SETTLING_LO,
        SETTLING_HI,
        facecolor=TRANSMITTER["grid"],
        alpha=0.30,
        zorder=0,
        hatch="///",
        edgecolor=TRANSMITTER["gray"],
        linewidth=0,
    )
    ax.text(
        (SETTLING_LO + SETTLING_HI) / 2,
        0.06,
        "2024–25: unstable\n(database still\nadding papers;\n○ = re-download)",
        transform=ax.get_xaxis_transform(),
        ha="center",
        va="bottom",
        fontsize=7.5,
        color=TRANSMITTER["gray"],
        style="italic",
        alpha=0.95,
        linespacing=1.15,
    )


def _build_legend(ax: plt.Axes) -> None:
    """Single-tier legend: direction colors + small dotted overlay note."""
    from matplotlib.lines import Line2D

    direction_handles = [
        Line2D([], [], color=DIRECTION_COLORS[d], lw=2.8, label=DISPLAY_LABELS_PLAIN[d])
        for d in DIRECTIONS
    ]
    # Lower-left, not upper-left: the plain-language labels (2026-09-14) are far
    # longer than the old "AI -> Neuro" arrows and ran straight into the 2002
    # change-point label at the top of the panel.
    leg = ax.legend(
        handles=direction_handles,
        loc="lower left",
        fontsize=11,
        ncols=1,
        frameon=False,
        bbox_to_anchor=(0.005, 0.02),
    )
    ax.add_artist(leg)


def _plot_tier1_bridges(ax: plt.Axes) -> None:
    """Tier-1 canonical bridge papers as thin vertical lines + rotated labels.

    Hassabis/Kriegeskorte/Richards labels anchored near the x-axis (reading
    upward). Zador 2023 stays high (it's in the settling region, easier to read
    when not crowded by the x-axis annotations or shade).
    """
    # (year): (y_axes_fraction, va, stagger_x)
    label_pos = {
        2012: (0.04, "bottom", 0.18),  # Krizhevsky 2012 (AlexNet)
        2017: (0.04, "bottom", 0.18),  # Hassabis 2017
        2018: (0.04, "bottom", 0.18),  # Kriegeskorte 2018 (same baseline)
        2019: (0.04, "bottom", 0.18),  # Richards 2019 (same baseline)
        2020: (0.04, "bottom", 0.18),  # GPT-3 2020 (Brown et al.)
        2023: (0.84, "top", 0.18),  # Zador 2023 (kept at top)
    }
    for label, year in TIER1_BRIDGES.items():
        if year < X_MIN or year > X_MAX:
            continue
        y, va, dx = label_pos.get(year, (0.04, "bottom", 0.18))
        ax.axvline(year, color=TRANSMITTER["navy"], lw=0.5, ls="-", alpha=0.22, zorder=1)
        ax.text(
            year + dx,
            y,
            label,
            transform=ax.get_xaxis_transform(),
            rotation=90,
            ha="left",
            va=va,
            fontsize=9,
            color=TRANSMITTER["navy"],
            alpha=0.9,
        )


def panel_a(
    ax: plt.Axes,
    df_all: pd.DataFrame,
    cp_index: dict[tuple[str, str], list[int]],
    ylabel: str,
    ylim: tuple[float, float],
    yscale: str = "log",
    title: str = "A  ·  Citation flow over time",
    with_legend: bool = True,
    with_era_shading: bool = True,
    with_bridges: bool = True,
) -> None:
    if with_era_shading:
        # Crop canonical eras to figure's year window so Pre-DL doesn't extend below X_MIN
        cropped_eras = [
            (lbl, max(lo, X_MIN), min(hi, X_MAX))
            for lbl, lo, hi in CANONICAL_ERAS
            if hi >= X_MIN and lo <= X_MAX
        ]
        add_era_shading(ax, cropped_eras, label_eras=True, label_y=1.015)
    _plot_settling_shade(ax)
    _plot_traces(ax, df_all)
    _plot_recent_overlay(ax, df_all)
    if with_bridges:
        _plot_tier1_bridges(ax)
    _plot_changepoints(ax, cp_index)

    ax.set_yscale(yscale)
    ax.set_xlim(X_MIN - 0.5, X_MAX + 0.5)
    ax.set_ylim(*ylim)
    ax.set_ylabel(ylabel, color=TRANSMITTER["navy"])
    ax.set_title(
        title,
        loc="left",
        fontsize=12.5,
        fontweight="bold",
        color=TRANSMITTER["navy"],
        pad=10,
    )
    if with_legend:
        _build_legend(ax)


# ---------------------------------------------------------------------------
# Panel B
# ---------------------------------------------------------------------------


def _build_era_partition(
    cp_index: dict[tuple[str, str], list[int]],
    year_min: int = 1990,
    year_max: int = 2023,
) -> list[tuple[str, int, int]]:
    """Build a canonical era partition from the SNAPSHOT changepoints.

    Snapshot is the rigorous source of truth; use its CPs as the era boundaries
    and score all sources within those eras. Returns:
        [(label, year_start, year_end), ...]
    Era boundaries are the union of snapshot CPs for both directions.
    """
    snap_cps: set[int] = set()
    for (src, _), cps in cp_index.items():
        if src == "snapshot":
            snap_cps.update(cps)
    boundaries = sorted([year_min, *snap_cps, year_max + 1])
    eras = []
    for i in range(len(boundaries) - 1):
        lo = boundaries[i]
        hi = boundaries[i + 1] - 1
        if hi < lo:
            continue
        eras.append((f"{lo}–{hi}", lo, hi))
    return eras


def _bootstrap_slope_cis(
    x: np.ndarray,
    y: np.ndarray,
    B: int = BOOTSTRAP_B,
    seed: int = RNG_SEED,
) -> dict:
    """B-replicate bootstrap of OLS slope. Returns 95% + 99% percentile CIs +
    fraction of bootstrap slopes > 0 and < 0 (used for sig markers).
    """
    rng = np.random.default_rng(seed)
    n = len(x)
    if n < 3:
        return {
            "slope": float("nan"),
            "ci95_lo": float("nan"),
            "ci95_hi": float("nan"),
            "ci99_lo": float("nan"),
            "ci99_hi": float("nan"),
            "frac_pos": float("nan"),
            "frac_neg": float("nan"),
        }
    # Point estimate
    xbar, ybar = x.mean(), y.mean()
    sxx = ((x - xbar) ** 2).sum()
    slope_pt = ((x - xbar) * (y - ybar)).sum() / sxx if sxx > 0 else float("nan")
    # Bootstrap (resample index pairs with replacement)
    slopes = np.empty(B)
    for b in range(B):
        idx = rng.integers(0, n, n)
        xb, yb = x[idx], y[idx]
        xbb, ybb = xb.mean(), yb.mean()
        sxxb = ((xb - xbb) ** 2).sum()
        slopes[b] = ((xb - xbb) * (yb - ybb)).sum() / sxxb if sxxb > 0 else np.nan
    slopes = slopes[~np.isnan(slopes)]
    if len(slopes) < B // 2:
        return {
            "slope": slope_pt,
            "ci95_lo": float("nan"),
            "ci95_hi": float("nan"),
            "ci99_lo": float("nan"),
            "ci99_hi": float("nan"),
            "frac_pos": float("nan"),
            "frac_neg": float("nan"),
        }
    return {
        "slope": slope_pt,
        "ci95_lo": float(np.percentile(slopes, 2.5)),
        "ci95_hi": float(np.percentile(slopes, 97.5)),
        "ci99_lo": float(np.percentile(slopes, 0.5)),
        "ci99_hi": float(np.percentile(slopes, 99.5)),
        "frac_pos": float((slopes > 0).mean()),
        "frac_neg": float((slopes < 0).mean()),
    }


def _era_slopes(
    df_all: pd.DataFrame,
    eras: list[tuple[str, int, int]],
    sources: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """OLS slope (per year) with bootstrap 95%/99% CIs per
    (source, direction, era). If `sources` is given, restrict to those sources.

    Note: returns slope in per-year units (not per-decade — the bars are
    per-era so a per-decade rescaling would be misleading for short eras).
    """
    sources = sources or SOURCES
    rows = []
    for (src, dirn), sub in df_all.groupby(["source", "direction"], observed=True):
        if src not in sources:
            continue
        for era_label, lo, hi in eras:
            block = sub[(sub["year"] >= lo) & (sub["year"] <= hi)].dropna(subset=["per1000"])
            n = len(block)
            if n < 3:
                continue
            x = block["year"].to_numpy(dtype=float)
            y = block["per1000"].to_numpy(dtype=float)
            boot = _bootstrap_slope_cis(x, y)
            rows.append(
                {
                    "source": src,
                    "direction": dirn,
                    "era": era_label,
                    "year_start": lo,
                    "year_end": hi,
                    "slope": boot["slope"],
                    "ci95_lo": boot["ci95_lo"],
                    "ci95_hi": boot["ci95_hi"],
                    "ci99_lo": boot["ci99_lo"],
                    "ci99_hi": boot["ci99_hi"],
                    "frac_pos": boot["frac_pos"],
                    "frac_neg": boot["frac_neg"],
                    "n_years": n,
                }
            )
    return pd.DataFrame(rows)


def _segment_slopes(
    df_all: pd.DataFrame,
    cp_index: dict[tuple[str, str], list[int]],
    source: str = "snapshot",
    year_min: int = 1995,
    year_max: int = 2023,
) -> pd.DataFrame:
    """OLS slope (per year) per data-driven segment per direction.

    Segments are defined by per-direction snapshot CPs: e.g. CPs [2006, 2020]
    → segments (year_min, 2005), (2006, 2019), (2020, year_max).
    """
    rows = []
    for direction in DIRECTIONS:
        cps = sorted(cp_index.get((source, direction), []))
        bounds = [year_min, *[c for c in cps if year_min < c <= year_max], year_max + 1]
        for i in range(len(bounds) - 1):
            lo = bounds[i]
            hi = bounds[i + 1] - 1
            if hi < lo:
                continue
            era_label = f"{lo}–{hi}"
            sub = df_all[
                (df_all["source"] == source)
                & (df_all["direction"] == direction)
                & (df_all["year"] >= lo)
                & (df_all["year"] <= hi)
            ].dropna(subset=["per1000"])
            n = len(sub)
            if n < 3:
                continue
            x = sub["year"].to_numpy(dtype=float)
            y = sub["per1000"].to_numpy(dtype=float)
            boot = _bootstrap_slope_cis(x, y)
            rows.append(
                {
                    "source": source,
                    "direction": direction,
                    "segment_index": i,
                    "era": era_label,
                    "year_start": lo,
                    "year_end": hi,
                    "slope": boot["slope"],
                    "ci95_lo": boot["ci95_lo"],
                    "ci95_hi": boot["ci95_hi"],
                    "ci99_lo": boot["ci99_lo"],
                    "ci99_hi": boot["ci99_hi"],
                    "frac_pos": boot["frac_pos"],
                    "frac_neg": boot["frac_neg"],
                    "n_years": n,
                }
            )
    return pd.DataFrame(rows)


def _sig_marker(frac_pos: float, frac_neg: float) -> str:
    """Bootstrap one-sided significance marker.

    one_sided = max(frac_pos, frac_neg). 95% CI excludes 0 if one_sided >= 0.975
    (*); 99% CI excludes 0 if one_sided >= 0.995 (**); else n.s.
    """
    if np.isnan(frac_pos) or np.isnan(frac_neg):
        return ""
    one_sided = max(frac_pos, frac_neg)
    if one_sided >= 0.995:
        return "**"
    if one_sided >= 0.975:
        return "*"
    return "n.s."


def panel_b(
    ax: plt.Axes,
    df_all: pd.DataFrame,
    cp_index: dict[tuple[str, str], list[int]],
    ylabel: str = "slope per decade\n(per-1,000 / decade)",
    title: str = "B  ·  Slope by era (snapshot only; * 95% CI / ** 99% CI excludes 0)",
) -> None:
    eras = _build_era_partition(cp_index, year_min=X_MIN, year_max=X_MAX - 2)
    logger.info("eras (from snapshot CPs): %s", eras)
    # Snapshot only for Panel B (stable source; cross-source bars belong in supplement)
    era_df = _era_slopes(df_all, eras, sources=("snapshot",))
    logger.info("era slopes (snapshot, bootstrap):\n%s", era_df.to_string(index=False))

    n_eras = len(eras)
    bar_w = 0.34
    group_centers = np.arange(n_eras, dtype=float)
    pos_in_group = {
        "neuro_to_ai": -bar_w / 2,
        "ai_to_neuro": +bar_w / 2,
    }

    for dirn, offset in pos_in_group.items():
        color = DIRECTION_COLORS[dirn]
        for ei, (era_label, _, _) in enumerate(eras):
            row = era_df[
                (era_df["source"] == "snapshot")
                & (era_df["direction"] == dirn)
                & (era_df["era"] == era_label)
            ]
            if row.empty:
                continue
            r = row.iloc[0]
            x = group_centers[ei] + offset
            slope = float(r["slope"])
            cl95 = float(r["ci95_lo"])
            ch95 = float(r["ci95_hi"])
            ax.bar(
                x,
                slope,
                width=bar_w,
                color=color,
                alpha=0.90,
                edgecolor=TRANSMITTER["navy"],
                linewidth=0.6,
                zorder=3,
            )
            err_lo = max(0.0, slope - cl95)
            err_hi = max(0.0, ch95 - slope)
            ax.errorbar(
                x,
                slope,
                yerr=[[err_lo], [err_hi]],
                fmt="none",
                ecolor=TRANSMITTER["navy"],
                elinewidth=0.7,
                capsize=2.5,
                alpha=0.85,
                zorder=4,
            )
            # Significance marker above (or below) the bar
            sig = _sig_marker(float(r["frac_pos"]), float(r["frac_neg"]))
            if sig:
                y_top = max(slope, ch95) if slope >= 0 else min(slope, cl95)
                # Pad in axes fraction units roughly
                pad = (
                    (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.025
                    if ax.get_ylim()[1] > ax.get_ylim()[0]
                    else 0.001
                )
                pad = pad if slope >= 0 else -pad
                va = "bottom" if slope >= 0 else "top"
                ax.text(
                    x,
                    y_top + pad,
                    sig,
                    ha="center",
                    va=va,
                    fontsize=10.0 if sig in ("*", "**") else 8.0,
                    fontweight="bold",
                    color=TRANSMITTER["navy"],
                    alpha=0.95,
                )

    ax.axhline(0.0, color=TRANSMITTER["navy"], lw=0.6, alpha=0.7, zorder=2)
    ax.set_xticks(group_centers)
    ax.set_xticklabels([e[0] for e in eras], fontsize=10.0)
    ax.set_ylabel(ylabel, color=TRANSMITTER["navy"])
    ax.set_title(
        title,
        loc="left",
        fontsize=12.5,
        fontweight="bold",
        color=TRANSMITTER["navy"],
        pad=10,
    )
    # Within-era separator (faint vertical lines between era groups)
    for i in range(n_eras - 1):
        ax.axvline(
            (group_centers[i] + group_centers[i + 1]) / 2,
            color=TRANSMITTER["grid"],
            lw=0.5,
            alpha=0.7,
            zorder=1,
        )


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


MAIN_TITLE = "Three decades of asymmetric citation"
MAIN_SUBTITLE_OR = (
    "The odds a paper cites the other field, relative to chance. AI and neuroscience, 1995–2025."
)
MAIN_SUBTITLE_PER1000 = "Cross-field references per 1,000, AI and neuroscience, 1995–2025."

METRIC_CONFIG = {
    "per1000": {
        "loader": load_all_sources,
        "ylabel": "cross-field references per 1,000",
        "subtitle": MAIN_SUBTITLE_PER1000,
        "ylim": (0.3, 40),
        "yscale": "log",
        "panel_b_ylabel": "OLS slope per year\n(per-1,000 / yr)",
        "out_stem": "figure1_main_v2",
    },
    "or": {
        "loader": load_all_sources_or,
        "ylabel": "likelihood of cross-field citation\n(odds ratio vs chance)",
        "subtitle": MAIN_SUBTITLE_OR,
        "ylim": (0.005, 0.3),
        "yscale": "log",
        "panel_b_ylabel": "OLS slope per year\n(OR / yr)",
        "out_stem": "figure1_article",
    },
}

ARTICLE_BUNDLE_DIR = config.RESULTS_DIR / "flow"
ARTICLE_BUNDLE_STEM = "figure1_article"


# ---------------------------------------------------------------------------
# Data bundle of the article figure (metric "or")
# ---------------------------------------------------------------------------


def _panel_a_table(df_all: pd.DataFrame) -> pd.DataFrame:
    """Panel A as plotted: band, thick line (same window and smoothing as `_plot_traces`)."""
    snap = load_snapshot_table()
    rows = []
    for direction in DIRECTIONS:
        sub = df_all[
            (df_all["source"] == "snapshot")
            & (df_all["direction"] == direction)
            & (df_all["year"] >= X_MIN)
            & (df_all["year"] <= X_MAX)
        ].sort_values("year")
        years = sub["year"].to_numpy(dtype=int)
        y = sub["per1000"].to_numpy(dtype=float)
        ma = rolling_mean(y, window=5)
        n_in = pd.Series(y).rolling(window=5, center=True, min_periods=3).count().to_numpy()
        s = snap[snap["direction"] == direction].set_index("year")
        for i, yr in enumerate(years):
            r = s.loc[yr]
            rows.append(
                {
                    "year": int(yr),
                    "direction": direction,
                    "line_in_figure": DISPLAY_LABELS_PLAIN[direction],
                    "colour": "teal" if direction == "ai_to_neuro" else "gold",
                    "odds_ratio_yearly": y[i],
                    "band_wilson95_lo": float(sub["ci_lo"].iloc[i]),
                    "band_wilson95_hi": float(sub["ci_hi"].iloc[i]),
                    "thick_line_5yr_centred_mean": ma[i],
                    "thick_line_n_years_averaged": int(n_in[i]),
                    "refs_to_own_field": int(r["n_to_within"]),
                    "refs_to_other_field": int(r["n_to_target"]),
                    "refs_to_third_fields": int(r["n_to_other"]),
                    "observed_share": float(r["rho_restricted"]),
                    "expected_share": float(r["rho_null_restricted"]),
                    "citing_field_papers": int(r["n_works_source"]),
                    "cited_field_papers": int(r["n_works_target"]),
                    "provisional_year": bool(yr >= 2024),
                }
            )
    return pd.DataFrame(rows)


def _circles_table(df_all: pd.DataFrame, panel_a: pd.DataFrame) -> pd.DataFrame:
    """Open circles of panel A: the May 2026 re-download in 2024-25, next to the snapshot."""
    cells = pd.read_csv(CROSS_DIR / "openalex_live_extended.csv", float_precision="round_trip")
    snap = load_snapshot_table().set_index(["year", "direction"])
    pa = panel_a.set_index(["year", "direction"])
    rows = []
    for direction in DIRECTIONS:
        sub = df_all[
            (df_all["source"] == "oa_live")
            & (df_all["direction"] == direction)
            & (df_all["year"] >= 2024)
            & (df_all["year"] <= RECENT_OVERLAY_HI)
        ].sort_values("year")
        for _, c in sub.iterrows():
            yr = int(c["year"])
            cell = cells[(cells["direction"] == direction) & (cells["year"] == yr)].iloc[0]
            s = snap.loc[(yr, direction)]
            rows.append(
                {
                    "year": yr,
                    "direction": direction,
                    "line_in_figure": DISPLAY_LABELS_PLAIN[direction],
                    "circle_odds_ratio": float(c["per1000"]),
                    "circle_wilson95_lo_not_drawn": float(c["ci_lo"]),
                    "circle_wilson95_hi_not_drawn": float(c["ci_hi"]),
                    "sample_papers": int(cell["n_papers"]),
                    "sample_refs_to_own_field": int(cell["within"]),
                    "sample_refs_to_other_field": int(cell["target"]),
                    "sample_observed_share": cell["target"] / (cell["within"] + cell["target"]),
                    "expected_share_from_snapshot": float(s["rho_null_restricted"]),
                    "snapshot_odds_ratio_yearly": float(s["or_restricted"]),
                    "snapshot_thick_line": float(
                        pa.loc[(yr, direction), "thick_line_5yr_centred_mean"]
                    ),
                    "circle_over_snapshot_yearly": float(c["per1000"]) / float(s["or_restricted"]),
                    "sample_per1000_classified": float(cell["per1000"]),
                    "sample_per1000_bootstrap95_lo": float(cell["ci_lo"]),
                    "sample_per1000_bootstrap95_hi": float(cell["ci_hi"]),
                    "snapshot_per1000_classified": 1000.0
                    * float(s["n_to_target"])
                    / float(s["n_to_within"] + s["n_to_target"] + s["n_to_other"]),
                }
            )
    return pd.DataFrame(rows)


def _with_markers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["marker_in_figure"] = [
        _sig_marker(p, n) for p, n in zip(df["frac_pos"], df["frac_neg"], strict=True)
    ]
    df["line_in_figure"] = df["direction"].map(DISPLAY_LABELS_PLAIN)
    return df


def _markers_table(cp_index: dict[tuple[str, str], list[int]]) -> pd.DataFrame:
    """Vertical marks and shaded spans of panel A, with the x-range each covers as drawn."""
    rows = [
        {
            "type": "era (shaded)",
            "label": lbl,
            "first_year": max(lo, X_MIN),
            "last_year": min(hi, X_MAX),
            "x_from": max(lo, X_MIN),
            "x_to": min(hi, X_MAX) + 1,
        }
        for lbl, lo, hi in CANONICAL_ERAS
        if hi >= X_MIN and lo <= X_MAX
    ]
    for d in DIRECTIONS:
        for cp in cp_index.get(("snapshot", d), []):
            rows.append(
                {
                    "type": "changepoint (dashed, first year of new segment)",
                    "label": DISPLAY_LABELS_PLAIN[d],
                    "first_year": cp,
                    "last_year": cp,
                    "x_from": cp,
                    "x_to": cp,
                }
            )
    for label, year in TIER1_BRIDGES.items():
        rows.append(
            {
                "type": "milestone paper (thin grey vertical)",
                "label": label,
                "first_year": year,
                "last_year": year,
                "x_from": year,
                "x_to": year,
            }
        )
    rows.append(
        {
            "type": "hatched band",
            "label": "2024–25: unstable (database still adding papers; ○ = re-download)",
            "first_year": 2024,
            "last_year": 2025,
            "x_from": SETTLING_LO,
            "x_to": SETTLING_HI,
        }
    )
    return pd.DataFrame(rows)


def _companion_table() -> pd.DataFrame:
    """Counts, raw shares and field sizes per year (quoted in supplement S3)."""
    d = load_snapshot_table()
    n = d[d.direction == "neuro_to_ai"].set_index("year").sort_index()
    a = d[d.direction == "ai_to_neuro"].set_index("year").sort_index()
    return pd.DataFrame(
        {
            "neuroscience_papers": n.n_works_source,
            "ai_papers": a.n_works_source,
            "citations_neuroscience_citing_ai": n.n_to_target,
            "citations_ai_citing_neuroscience": a.n_to_target,
            "cross_refs_per_1000_refs_neuroscience_citing_ai": n.rho_population * 1000,
            "cross_refs_per_1000_refs_ai_citing_neuroscience": a.rho_population * 1000,
            "refs_per_neuroscience_paper": (n.n_to_within + n.n_to_target + n.n_to_other)
            / n.n_works_source,
            "refs_per_ai_paper": (a.n_to_within + a.n_to_target + a.n_to_other) / a.n_works_source,
        }
    ).reset_index()


def write_article_bundle(
    df_all: pd.DataFrame, cp_index: dict[tuple[str, str], list[int]], out_dir: Path | None = None
) -> dict[str, Path]:
    """Write the values plotted in the article's Figure 1 to `results/flow/figure1_article_*.csv`.

    panelA: one row per year (1995-2025) and line; circles: the four open circles;
    panelB / panelC: the bars, whiskers and markers; markers: shaded spans and vertical lines.
    Also rewrites `companion_counts_shares_sizes.csv` (S3), which is derived from the same table.
    """
    out_dir = out_dir or ARTICLE_BUNDLE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    era_windows = [
        (lbl, max(lo, X_MIN), min(hi, X_MAX - 2))
        for lbl, lo, hi in CANONICAL_ERAS
        if hi >= X_MIN and lo <= X_MAX - 2
    ]
    panel_a_df = _panel_a_table(df_all)
    tables = {
        "panelA": panel_a_df,
        "circles": _circles_table(df_all, panel_a_df),
        "panelB": _with_markers(_era_slopes(df_all, era_windows, sources=("snapshot",))),
        "panelC": _with_markers(
            _segment_slopes(df_all, cp_index, source="snapshot", year_min=X_MIN, year_max=X_MAX - 2)
        ),
        "markers": _markers_table(cp_index),
    }
    paths = {}
    for key, table in tables.items():
        p = out_dir / f"{ARTICLE_BUNDLE_STEM}_{key}.csv"
        table.to_csv(p, index=False)
        paths[key] = p
    p = out_dir / "companion_counts_shares_sizes.csv"
    _companion_table().to_csv(p, index=False)
    paths["companion"] = p
    return paths


def panel_b_canonical(
    ax: plt.Axes,
    df_all: pd.DataFrame,
    ylabel: str,
    year_min: int = X_MIN,
    year_max: int = X_MAX - 2,
) -> None:
    """Bottom-left: bars for the 4 canonical pre-registered eras × 2 directions."""
    cropped_eras = [
        (lbl, max(lo, year_min), min(hi, year_max))
        for lbl, lo, hi in CANONICAL_ERAS
        if hi >= year_min and lo <= year_max
    ]
    era_df = _era_slopes(df_all, cropped_eras, sources=("snapshot",))
    logger.info("canonical-era slopes:\n%s", era_df.to_string(index=False))

    n_eras = len(cropped_eras)
    bar_w = 0.34
    group_centers = np.arange(n_eras, dtype=float)
    pos_in_group = {
        "neuro_to_ai": -bar_w / 2,
        "ai_to_neuro": +bar_w / 2,
    }

    for dirn, offset in pos_in_group.items():
        color = DIRECTION_COLORS[dirn]
        for ei, (era_label, _, _) in enumerate(cropped_eras):
            row = era_df[
                (era_df["source"] == "snapshot")
                & (era_df["direction"] == dirn)
                & (era_df["era"] == era_label)
            ]
            if row.empty:
                continue
            r = row.iloc[0]
            x = group_centers[ei] + offset
            slope = float(r["slope"])
            cl95 = float(r["ci95_lo"])
            ch95 = float(r["ci95_hi"])
            ax.bar(
                x,
                slope,
                width=bar_w,
                color=color,
                alpha=0.90,
                edgecolor=TRANSMITTER["navy"],
                linewidth=0.6,
                zorder=3,
            )
            err_lo = max(0.0, slope - cl95)
            err_hi = max(0.0, ch95 - slope)
            ax.errorbar(
                x,
                slope,
                yerr=[[err_lo], [err_hi]],
                fmt="none",
                ecolor=TRANSMITTER["navy"],
                elinewidth=0.7,
                capsize=2.5,
                alpha=0.85,
                zorder=4,
            )
            sig = _sig_marker(float(r["frac_pos"]), float(r["frac_neg"]))
            if sig:
                y_top = max(slope, ch95) if slope >= 0 else min(slope, cl95)
                ylim = ax.get_ylim()
                pad = (ylim[1] - ylim[0]) * 0.025 if ylim[1] > ylim[0] else 0.001
                pad = pad if slope >= 0 else -pad
                va = "bottom" if slope >= 0 else "top"
                ax.text(
                    x,
                    y_top + pad,
                    sig,
                    ha="center",
                    va=va,
                    fontsize=10.0 if sig in ("*", "**") else 8.0,
                    fontweight="bold",
                    color=TRANSMITTER["navy"],
                    alpha=0.95,
                )

    ax.axhline(0.0, color=TRANSMITTER["navy"], lw=0.6, alpha=0.7, zorder=2)
    ax.set_xticks(group_centers)
    ax.set_xticklabels(
        [f"{lbl}\n{lo}–{hi}" for lbl, lo, hi in cropped_eras],
        fontsize=8.5,
    )
    ax.set_ylabel(ylabel, color=TRANSMITTER["navy"])
    ax.set_title(
        "B  ·  Pre-registered eras",
        loc="left",
        fontsize=12.0,
        fontweight="bold",
        color=TRANSMITTER["navy"],
        pad=8,
    )


def panel_c_segments(
    ax: plt.Axes,
    df_all: pd.DataFrame,
    cp_index: dict[tuple[str, str], list[int]],
    ylabel: str,
) -> None:
    """Bottom-right: bars for data-driven CP segments, grouped per direction.

    Each direction gets its own group of segment bars (3 per direction by
    default, with year ranges labelled below).
    """
    seg_df = _segment_slopes(
        df_all, cp_index, source="snapshot", year_min=X_MIN, year_max=X_MAX - 2
    )
    logger.info("CP-segment slopes:\n%s", seg_df.to_string(index=False))

    bar_w = 0.7
    group_gap = 1.2
    n_segs_per_dir = max(len(seg_df[seg_df["direction"] == d]) for d in DIRECTIONS)
    x_positions = []
    bar_data = []  # (x, slope, cl95, ch95, sig, year_label, color)
    for gi, direction in enumerate(DIRECTIONS):
        d = seg_df[seg_df["direction"] == direction].sort_values("segment_index")
        base = gi * (n_segs_per_dir + group_gap)
        for si, (_, r) in enumerate(d.iterrows()):
            x = base + si
            slope = float(r["slope"])
            cl95 = float(r["ci95_lo"])
            ch95 = float(r["ci95_hi"])
            sig = _sig_marker(float(r["frac_pos"]), float(r["frac_neg"]))
            bar_data.append(
                (
                    x,
                    slope,
                    cl95,
                    ch95,
                    sig,
                    r["era"],
                    DIRECTION_COLORS[direction],
                    direction,
                )
            )
        x_positions.append(base + (n_segs_per_dir - 1) / 2)

    for x, slope, cl95, ch95, sig, _era_label, color, _dirn in bar_data:
        ax.bar(
            x,
            slope,
            width=bar_w,
            color=color,
            alpha=0.90,
            edgecolor=TRANSMITTER["navy"],
            linewidth=0.6,
            zorder=3,
        )
        err_lo = max(0.0, slope - cl95)
        err_hi = max(0.0, ch95 - slope)
        ax.errorbar(
            x,
            slope,
            yerr=[[err_lo], [err_hi]],
            fmt="none",
            ecolor=TRANSMITTER["navy"],
            elinewidth=0.7,
            capsize=2.5,
            alpha=0.85,
            zorder=4,
        )
        if sig:
            y_top = max(slope, ch95) if slope >= 0 else min(slope, cl95)
            ylim = ax.get_ylim()
            pad = (ylim[1] - ylim[0]) * 0.025 if ylim[1] > ylim[0] else 0.001
            pad = pad if slope >= 0 else -pad
            va = "bottom" if slope >= 0 else "top"
            ax.text(
                x,
                y_top + pad,
                sig,
                ha="center",
                va=va,
                fontsize=10.0 if sig in ("*", "**") else 8.0,
                fontweight="bold",
                color=TRANSMITTER["navy"],
                alpha=0.95,
            )

    ax.axhline(0.0, color=TRANSMITTER["navy"], lw=0.6, alpha=0.7, zorder=2)
    xs = [b[0] for b in bar_data]
    ax.set_xticks(xs)
    ax.set_xticklabels(
        [b[5] for b in bar_data],
        fontsize=7.5,
        rotation=30,
        ha="right",
    )
    # No direction headers (bars are color-coded; legend in Panel A is the
    # single key for direction colors throughout the figure).
    ax.set_ylabel(ylabel, color=TRANSMITTER["navy"])
    ax.set_title(
        "C  ·  Data-driven segments",
        loc="left",
        fontsize=12.0,
        fontweight="bold",
        color=TRANSMITTER["navy"],
        pad=8,
    )


def build(metric: str = "per1000") -> Path:
    apply_style()
    cfg = METRIC_CONFIG[metric]

    logger.info("loading sources (metric=%s)...", metric)
    df_all = cfg["loader"]()

    logger.info("detecting per-series changepoints (1995-2023 window)...")
    seg_df = detect_all_changepoints(df_all, *CP_DETECTION_WINDOW, max_breakpoints=2)
    cp_index = seg_df.attrs["changepoints"]
    logger.info("per-series changepoints:")
    for (src, dirn), cps in sorted(cp_index.items()):
        logger.info("  %-8s %-13s : %s", src, dirn, cps)
    consensus = consensus_changepoints(cp_index)
    logger.info("consensus changepoints per direction: %s", consensus)

    # 3-panel layout: Panel A spans top; B (canonical eras) bottom-left,
    # C (data-driven segments) bottom-right. Matches v1 figure1_main.py shape.
    fig = plt.figure(figsize=(13.0, 8.6))
    gs = fig.add_gridspec(
        2,
        2,
        height_ratios=[2.6, 1.6],
        width_ratios=[1.0, 0.95],
        hspace=0.22,
        wspace=0.22,
    )
    ax_a = fig.add_subplot(gs[0, :])
    ax_b = fig.add_subplot(gs[1, 0])
    ax_c = fig.add_subplot(gs[1, 1])

    panel_a(ax_a, df_all, cp_index, ylabel=cfg["ylabel"], ylim=cfg["ylim"], yscale=cfg["yscale"])
    panel_b_canonical(ax_b, df_all, ylabel=cfg["panel_b_ylabel"])
    panel_c_segments(ax_c, df_all, cp_index, ylabel=cfg["panel_b_ylabel"])

    source_blurb = (
        "(A) OpenAlex March 2026 download (~458M works), 5-year centered "
        "rolling mean ± Wilson 95% CI. Open circles in 2024–25 = same query "
        "against a fresh May 2026 re-download; offset shows the database is "
        "still ingesting recent papers (cross-source comparison: supplement). "
        "Vertical dashed lines = snapshot changepoints (piecewise-linear OLS, "
        "0–2 breakpoints). Thin grey verticals = tier-1 bridge papers. "
        "(B) OLS slope per year within pre-registered eras ± 95% bootstrap "
        "CI (B=500); * = 95% CI excludes 0, ** = 99% CI excludes 0. "
        "(C) OLS slope per year within data-driven segments (per-direction "
        "snapshot changepoints), same significance scheme."
    )
    if metric == "or":
        source_blurb += (
            " OR = (rho_obs / rho_null) of cross-field citation under a "
            "size-blind null; ratio > 1 = above chance."
        )

    finalize(
        fig,
        title=MAIN_TITLE,
        subtitle=cfg["subtitle"],
        source=source_blurb,
        byline="R. Duarte // The Transmitter",
        subtitle_y=0.955,  # tight title-subtitle spacing
    )
    fig.subplots_adjust(top=0.88, bottom=0.13, left=0.07, right=0.97)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_png = OUT_DIR / f"{cfg['out_stem']}.png"
    out_svg = OUT_DIR / f"{cfg['out_stem']}.svg"
    fig.savefig(out_png)
    fig.savefig(out_svg)
    plt.close(fig)
    logger.info("Wrote %s and %s", out_png, out_svg)
    if metric == "or":
        paths = write_article_bundle(df_all, cp_index)
        logger.info("Wrote data bundle: %s", ", ".join(str(p) for p in paths.values()))
    return out_png


def build_combined() -> Path:
    """4-panel combined figure: raw per-1000 (left) + OR (right), A/B per metric."""
    apply_style()

    logger.info("loading both metrics for combined figure...")
    df_p = load_all_sources()
    df_o = load_all_sources_or()

    logger.info("detecting per-series changepoints (per-1000)...")
    seg_p = detect_all_changepoints(df_p, *CP_DETECTION_WINDOW, max_breakpoints=2)
    cp_p = seg_p.attrs["changepoints"]
    logger.info("detecting per-series changepoints (OR)...")
    seg_o = detect_all_changepoints(df_o, *CP_DETECTION_WINDOW, max_breakpoints=2)
    cp_o = seg_o.attrs["changepoints"]

    cfg_p = METRIC_CONFIG["per1000"]
    cfg_o = METRIC_CONFIG["or"]

    fig = plt.figure(figsize=(16.5, 9.4))
    gs = fig.add_gridspec(
        2,
        2,
        height_ratios=[2.0, 1.2],
        width_ratios=[1.0, 1.0],
        hspace=0.42,
        wspace=0.20,
    )
    ax_a_l = fig.add_subplot(gs[0, 0])
    ax_a_r = fig.add_subplot(gs[0, 1])
    ax_b_l = fig.add_subplot(gs[1, 0])
    ax_b_r = fig.add_subplot(gs[1, 1])

    panel_a(
        ax_a_l,
        df_p,
        cp_p,
        ylabel=cfg_p["ylabel"],
        ylim=cfg_p["ylim"],
        yscale=cfg_p["yscale"],
        title="A  ·  Raw share — cross-field references per 1,000",
        with_legend=True,
    )
    panel_a(
        ax_a_r,
        df_o,
        cp_o,
        ylabel=cfg_o["ylabel"],
        ylim=cfg_o["ylim"],
        yscale=cfg_o["yscale"],
        title="A'  ·  Likelihood vs chance — odds ratio",
        with_legend=False,
    )
    panel_b(
        ax_b_l, df_p, cp_p, ylabel=cfg_p["panel_b_ylabel"], title="B  ·  Slope by era (raw share)"
    )
    panel_b(
        ax_b_r, df_o, cp_o, ylabel=cfg_o["panel_b_ylabel"], title="B'  ·  Slope by era (odds ratio)"
    )

    finalize(
        fig,
        title=MAIN_TITLE,
        subtitle=(
            "Raw share (left) and odds ratio (right). AI and neuroscience, "
            "1995–2025. Snapshot only; ○ = May 2026 re-download."
        ),
        source=(
            "(A/A') OpenAlex March 2026 snapshot (~458M works), 5-year "
            "centered rolling mean ± Wilson 95% CI. Open circles in 2024–25 "
            "= same query against a fresh May 2026 re-download. Vertical "
            "dashed lines = snapshot changepoints (piecewise-linear OLS, "
            "0–2 breakpoints). (B/B') OLS slope per era ± 95% bootstrap CI "
            "(B=500); * = 95% CI excludes 0, ** = 99% CI excludes 0. "
            "OR = (rho_obs / rho_null) of cross-field citation under a "
            "size-blind null."
        ),
        byline="R. Duarte // The Transmitter",
        subtitle_y=0.955,
    )
    fig.subplots_adjust(top=0.88, bottom=0.12, left=0.06, right=0.98)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_png = OUT_DIR / "figure1_main_v2_combined.png"
    out_svg = OUT_DIR / "figure1_main_v2_combined.svg"
    fig.savefig(out_png)
    fig.savefig(out_svg)
    plt.close(fig)
    logger.info("Wrote %s and %s", out_png, out_svg)
    return out_png


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    import sys

    args = sys.argv[1:] or ["or"]
    for a in args:
        if a == "combined":
            build_combined()
        else:
            build(a)

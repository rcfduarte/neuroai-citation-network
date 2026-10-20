"""Article Figure 1 (v3), 2026-10-06, with a self-contained data bundle.

Odds-ratio metric (the same data and calculations as figure1_main_v2):
  * thin line = yearly value, pale band = Wilson 95% interval, thick line = centred 5-year mean;
  * all computed on the March 2026 OpenAlex snapshot, the 5-year mean over the full series
    (so 2024-25 enter it exactly as in figure1_main_v2);
  * 2024-25 continue the same lines, dashed inside the hatched provisional band; no markers,
    no error bars, no second data source.
Panels B and C unchanged (slopes through 2023).

Writes `figures/figure1_article_v3*` and the CSV bundle under `results/flow/`.
Reads `results/flow/or_by_year.csv` (see `analysis/export_flow_inputs.py`).
"""

from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .. import config
from . import figure1_main_v2 as f1
from .cross_source import (
    detect_all_changepoints,
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
    apply_style,
    finalize,
)

logger = logging.getLogger(__name__)

STEM = "figure1_article_v3"
NAVY, GRAY = TRANSMITTER["navy"], TRANSMITTER["gray"]
LAST_SOLID = 2023
FIG_DIR = config.FIGURES_DIR  # the figure files
BUNDLE = config.RESULTS_DIR / "flow"  # the data bundle (CSV)


# ---------------------------------------------------------------------------
# Panel A drawing (patched into figure1_main_v2.panel_a for this process only)
# ---------------------------------------------------------------------------


def _traces(ax: plt.Axes, df_all: pd.DataFrame) -> None:
    for direction in f1.DIRECTIONS:
        color = DIRECTION_COLORS[direction]
        sub = df_all[
            (df_all["source"] == "snapshot")
            & (df_all["direction"] == direction)
            & (df_all["year"] >= f1.X_MIN)
            & (df_all["year"] <= f1.X_MAX)
        ].sort_values("year")
        years = sub["year"].to_numpy(dtype=float)
        y = sub["per1000"].to_numpy(dtype=float)
        ma = rolling_mean(y, window=5)
        ax.fill_between(
            years, sub["ci_lo"], sub["ci_hi"], color=color, alpha=0.10, linewidth=0, zorder=1
        )
        ax.plot(years, y, color=color, lw=0.9, alpha=0.45, zorder=2)
        solid = years <= LAST_SOLID
        ax.plot(years[solid], ma[solid], color=color, lw=2.8, zorder=3, solid_capstyle="round")
        tail = years >= LAST_SOLID
        ax.plot(years[tail], ma[tail], color=color, lw=2.8, ls=(0, (3.2, 1.6)), zorder=3)


def _no_overlay(ax, df_all):
    return


def _shade(ax: plt.Axes) -> None:
    ax.axvspan(
        LAST_SOLID + 0.5,
        f1.X_MAX + 0.5,
        facecolor=TRANSMITTER["grid"],
        alpha=0.30,
        zorder=0,
        hatch="///",
        edgecolor=GRAY,
        linewidth=0,
    )
    ax.text(
        (LAST_SOLID + 0.5 + f1.X_MAX + 0.5) / 2,
        0.06,
        "2024–25:\nprovisional\n(database still\nadding papers)",
        transform=ax.get_xaxis_transform(),
        ha="center",
        va="bottom",
        fontsize=7.5,
        color=GRAY,
        style="italic",
        alpha=0.95,
        linespacing=1.15,
    )


def _changepoints(ax: plt.Axes, cp_index: dict) -> None:
    by_year: dict[int, list[str]] = {}
    for d in f1.DIRECTIONS:
        for cp in cp_index.get(("snapshot", d), []):
            by_year.setdefault(cp, []).append(d)
    for cp, dirs in sorted(by_year.items()):
        color = DIRECTION_COLORS[dirs[0]] if len(dirs) == 1 else NAVY
        ax.axvline(cp, color=color, ls="--", lw=1.0, alpha=0.55, zorder=2)
        ax.text(
            cp,
            0.96,
            str(cp),
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=7.5,
            color=color,
            alpha=0.9,
            fontweight="bold",
        )


def _patch() -> None:
    f1._plot_traces = _traces
    f1._plot_recent_overlay = _no_overlay
    f1._plot_settling_shade = _shade
    f1._plot_changepoints = _changepoints


# ---------------------------------------------------------------------------
# Data bundle
# ---------------------------------------------------------------------------


def _timeseries_table() -> pd.DataFrame:
    d = load_snapshot_table()
    rows = []
    for direction in f1.DIRECTIONS:
        s = d[d.direction == direction].sort_values("year").reset_index(drop=True)
        y = s["or_restricted"].to_numpy(dtype=float)
        yrs = s["year"].to_numpy()
        ma_all = rolling_mean(y, window=5)
        ma_cut = (
            pd.Series(np.where(yrs <= LAST_SOLID, y, np.nan))
            .rolling(5, center=True, min_periods=3)
            .mean()
            .to_numpy()
        )
        for i, r in s.iterrows():
            rows.append(
                {
                    "year": int(r.year),
                    "direction": direction,
                    "line_in_figure": DISPLAY_LABELS_PLAIN[direction],
                    "colour": "teal" if direction == "ai_to_neuro" else "gold",
                    "odds_ratio_yearly": r.or_restricted,
                    "odds_ratio_ci95_lo": r.or_restricted_lo,
                    "odds_ratio_ci95_hi": r.or_restricted_hi,
                    "odds_ratio_5yr_centred_mean_PLOTTED": ma_all[i],
                    "odds_ratio_5yr_mean_using_data_to_2023_only": ma_cut[i],
                    "refs_to_own_field": int(r.n_to_within),
                    "refs_to_other_field": int(r.n_to_target),
                    "refs_to_third_fields": int(r.n_to_other),
                    "share_cross_of_own_plus_cross": r.rho_restricted,
                    "share_expected_by_chance": r.rho_null_restricted,
                    "citing_field_papers_in_year": int(r.n_works_source),
                    "cited_field_papers_in_year": int(r.n_works_target),
                    "provisional_year": bool(r.year > LAST_SOLID),
                }
            )
    return pd.DataFrame(rows)


def _markers_table(cp_index: dict) -> pd.DataFrame:
    rows = [
        {"type": "pre-defined period", "label": lbl, "start_year": lo, "end_year": hi}
        for lbl, lo, hi in CANONICAL_ERAS
    ]
    for d in f1.DIRECTIONS:
        for cp in cp_index.get(("snapshot", d), []):
            rows.append(
                {
                    "type": "turning point found in data",
                    "label": DISPLAY_LABELS_PLAIN[d],
                    "start_year": cp,
                    "end_year": cp,
                }
            )
    rows += [
        {"type": "milestone paper", "label": k, "start_year": v, "end_year": v}
        for k, v in TIER1_BRIDGES.items()
    ]
    rows.append(
        {
            "type": "provisional years",
            "label": "database still adding papers",
            "start_year": LAST_SOLID + 1,
            "end_year": 2025,
        }
    )
    return pd.DataFrame(rows)


def _companion_table() -> pd.DataFrame:
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


def _write_bundle(df_all: pd.DataFrame, cp_index: dict) -> None:
    era = f1._era_slopes(
        df_all,
        [(label, max(lo, f1.X_MIN), min(hi, f1.X_MAX - 2)) for label, lo, hi in CANONICAL_ERAS],
        sources=("snapshot",),
    )
    seg = f1._segment_slopes(
        df_all, cp_index, source="snapshot", year_min=f1.X_MIN, year_max=f1.X_MAX - 2
    )
    d = BUNDLE
    d.mkdir(parents=True, exist_ok=True)
    _timeseries_table().to_csv(d / "fig1A_timeseries.csv", index=False)
    era.to_csv(d / "fig1B_era_slopes.csv", index=False)
    seg.to_csv(d / "fig1C_segment_slopes.csv", index=False)
    _markers_table(cp_index).to_csv(d / "fig1_markers.csv", index=False)
    _companion_table().to_csv(d / "companion_counts_shares_sizes.csv", index=False)


def build() -> None:
    apply_style()
    _patch()
    df_all = load_all_sources_or()
    seg_df = detect_all_changepoints(df_all, *f1.CP_DETECTION_WINDOW, max_breakpoints=2)
    cp_index = seg_df.attrs["changepoints"]

    fig = plt.figure(figsize=(13.0, 8.6))
    gs = fig.add_gridspec(
        2, 2, height_ratios=[2.6, 1.6], width_ratios=[1.0, 0.95], hspace=0.30, wspace=0.22
    )
    ax_a = fig.add_subplot(gs[0, :])
    ax_b, ax_c = fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])

    cfg = f1.METRIC_CONFIG["or"]
    f1.panel_a(
        ax_a,
        df_all,
        cp_index,
        ylabel="odds ratio\n(1 = chance; log scale)",
        ylim=cfg["ylim"],
        yscale="log",
        title="A  ·  Citation flow over time",
    )
    ax_a.annotate(
        "chance level (= 1) lies above the top of this scale",
        xy=(0.5, 1.0),
        xycoords="axes fraction",
        xytext=(0.5, 0.905),
        textcoords="axes fraction",
        ha="center",
        va="top",
        fontsize=7.5,
        color=GRAY,
        style="italic",
        arrowprops={"arrowstyle": "->", "color": GRAY, "lw": 0.8},
    )
    yl = "change in odds ratio\nper year"
    f1.panel_b_canonical(ax_b, df_all, ylabel=yl)
    ax_b.set_title(
        "B  ·  Change within four pre-defined periods",
        loc="left",
        fontsize=12,
        fontweight="bold",
        color=NAVY,
        pad=8,
    )
    f1.panel_c_segments(ax_c, df_all, cp_index, ylabel=yl)
    ax_c.set_title(
        "C  ·  Change between turning points found in the data",
        loc="left",
        fontsize=12,
        fontweight="bold",
        color=NAVY,
        pad=8,
    )

    finalize(
        fig,
        title="Three decades of asymmetric citation",
        subtitle="How often neuroscience and AI papers cite each other, compared with chance, 1995–2025.",
        source="OpenAlex, March 2026 download (about 458 million works).",
        byline="R. Duarte // The Transmitter",
        subtitle_y=0.955,
    )
    fig.subplots_adjust(top=0.88, bottom=0.10, left=0.07, right=0.97)

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / f"{STEM}.png")
    fig.savefig(FIG_DIR / f"{STEM}.svg")
    fig.savefig(FIG_DIR / f"{STEM}-onwhite.png", facecolor="white", transparent=False)
    plt.close(fig)
    _write_bundle(df_all, cp_index)
    logger.info("wrote %s and %s", FIG_DIR, BUNDLE)


if __name__ == "__main__":
    build()

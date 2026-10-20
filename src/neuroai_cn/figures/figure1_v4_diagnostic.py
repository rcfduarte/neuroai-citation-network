"""Figure 1 v4 — Q1 diagnostic multi-panel (Scheme 1 / extended classifier).

Four panels, no figure title, panel labels A/B/C/D in upper-left of each axis.
Shares x-axis [1989, 2026]. Uses corrections/20260508/ parquets (Scheme 1
extended). Adds the trend-analysis panels (rolling OLS slopes, YoY deltas,
piecewise-linear change-point segmentation) that exist in the parquets but
are not plotted in the article figure.

Panels:
  A — OR_restricted per-year (both directions) with Wilson 95% CI ribbons,
      5y centered rolling-mean overlay (dashed), era shading, Tier-1 vertical
      markers. Log y-scale. This is the headline.
  B — Rolling-window OLS slope per year on OR_restricted; window 5y (solid) +
      window 7y (dashed), both directions. Zero line. Linear y-scale. Shows
      trend stability over different smoothing scales.
  C — Year-over-year delta (Δ OR_restricted) per year, both directions, as
      stem/bar plot with zero line. Linear y-scale.
  D — Piecewise-linear change-point segmentation: per-segment OLS fits
      overlaid on the OR_restricted series. Breakpoint year marked as
      vertical dashed line with annotation; per-segment slope + R²
      summarised at bottom. Headline finding lives here.

Output: corrections/20260508/figures/figure1_v4_diagnostic.{png,svg}

Usage:
    uv run python -m neuroai_cn.figures.figure1_v4_diagnostic
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .. import config
from .style import (
    CANONICAL_ERAS,
    TRANSMITTER,
    add_era_shading,
    apply_style,
    finalize,
)
from .style import (
    DIRECTION_COLORS as COLORS,
)
from .style import (
    DIRECTION_LABELS as LABELS,
)
from .style import (
    TIER1_BRIDGES as TIER1,
)

logger = logging.getLogger(__name__)

CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"
FIGURES_DIR = CORRECTIONS_DIR / "figures"

X_MIN, X_MAX = 1990, 2026


def _add_eras(ax: plt.Axes) -> None:
    add_era_shading(ax, CANONICAL_ERAS, label_eras=True, label_y=1.015)


def _add_panel_label(ax: plt.Axes, letter: str) -> None:
    ax.text(
        0.005,
        0.985,
        letter,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=14,
        fontweight="bold",
        color=TRANSMITTER["navy"],
    )


def _add_tier1(ax: plt.Axes) -> None:
    # Stagger the y-position when years cluster (Hassabis 2017 / Kriegeskorte 2018
    # / Richards 2019 are adjacent) so the rotated text doesn't visually merge.
    stagger_y = {2017: 0.70, 2018: 0.86, 2019: 0.70, 2023: 0.86}
    for label, year in TIER1.items():
        ax.axvline(year, color=TRANSMITTER["navy"], lw=0.4, ls="-", alpha=0.22)
        ax.text(
            year + 0.18,
            stagger_y.get(year, 0.78),
            label,
            transform=ax.get_xaxis_transform(),
            rotation=90,
            va="top",
            fontsize=7.0,
            color=TRANSMITTER["navy"],
            alpha=0.55,
        )


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------


def panel_a_or_curves(ax: plt.Axes, df: pd.DataFrame) -> None:
    _add_eras(ax)
    _add_tier1(ax)
    for direction in ("ai_to_neuro", "neuro_to_ai"):
        sub = df[df["direction"] == direction].sort_values("year")
        years = sub["year"].to_numpy()
        y = sub["or_restricted"].to_numpy(dtype=float)
        lo = sub["or_restricted_lo"].to_numpy(dtype=float)
        hi = sub["or_restricted_hi"].to_numpy(dtype=float)
        ax.fill_between(years, lo, hi, color=COLORS[direction], alpha=0.13, zorder=1)
        ax.plot(
            years,
            y,
            "o-",
            color=COLORS[direction],
            lw=1.5,
            ms=4,
            label=LABELS[direction],
            zorder=2,
        )
        roll5 = pd.Series(y).rolling(window=5, center=True).mean().to_numpy()
        ax.plot(
            years,
            roll5,
            "--",
            color=COLORS[direction],
            lw=1.6,
            alpha=0.55,
            zorder=3,
        )
    ax.axhline(1.0, color="black", ls=":", lw=0.7, alpha=0.55)
    ax.text(X_MIN + 0.4, 1.02, "OR = 1 (chance)", fontsize=7, alpha=0.6, va="bottom")
    ax.set_yscale("log")
    ax.set_xlim(X_MIN, X_MAX)
    ax.set_ylabel(r"OR$_\mathrm{restricted}$ (Wilson 95% CI)")
    ax.legend(loc="upper left", fontsize=8, ncols=2, framealpha=0.9, bbox_to_anchor=(0.04, 1.0))
    ax.grid(alpha=0.2)


def panel_b_rolling_slopes(ax: plt.Axes, df_roll: pd.DataFrame) -> None:
    _add_eras(ax)
    sub = df_roll[df_roll["metric"] == "or_restricted"].copy()
    sub["x"] = sub["window_end"]
    for direction in ("ai_to_neuro", "neuro_to_ai"):
        c = COLORS[direction]
        for window, ls, alpha in ((5, "-", 1.0), (7, "--", 0.85)):
            s = sub[(sub["direction"] == direction) & (sub["window_size"] == window)].sort_values(
                "x"
            )
            if s.empty:
                continue
            ax.plot(
                s["x"],
                s["slope"],
                ls,
                color=c,
                lw=1.4,
                alpha=alpha,
                label=f"{LABELS[direction]} · {window}y window",
            )
    ax.axhline(0.0, color="black", ls=":", lw=0.7, alpha=0.55)
    ax.set_xlim(X_MIN, X_MAX)
    ax.set_ylabel("Rolling-window OLS slope\n(d OR$_\\mathrm{restricted}$ / dy)")
    ax.legend(loc="upper left", fontsize=7, ncols=2, framealpha=0.9)
    ax.grid(alpha=0.2)


def panel_c_yoy(ax: plt.Axes, df_yoy: pd.DataFrame) -> None:
    _add_eras(ax)
    sub = df_yoy[df_yoy["metric"] == "or_restricted"].copy()
    offset = {"ai_to_neuro": -0.18, "neuro_to_ai": +0.18}
    width = 0.36
    for direction in ("ai_to_neuro", "neuro_to_ai"):
        s = sub[sub["direction"] == direction].sort_values("year")
        ax.bar(
            s["year"] + offset[direction],
            s["delta"],
            width=width,
            color=COLORS[direction],
            alpha=0.85,
            label=LABELS[direction],
            zorder=2,
        )
    ax.axhline(0.0, color="black", lw=0.7, alpha=0.6)
    ax.set_xlim(X_MIN, X_MAX)
    ax.set_ylabel(r"Year-over-year Δ OR$_\mathrm{restricted}$")
    ax.legend(loc="upper left", fontsize=8, ncols=2, framealpha=0.9)
    ax.grid(alpha=0.2, axis="y")


def panel_d_changepoints(ax: plt.Axes, df: pd.DataFrame, df_cp: pd.DataFrame) -> None:
    _add_eras(ax)
    # Faint OR curve in background (both directions) for context
    for direction in ("ai_to_neuro", "neuro_to_ai"):
        sub = df[df["direction"] == direction].sort_values("year")
        ax.plot(
            sub["year"],
            sub["or_restricted"],
            "o-",
            color=COLORS[direction],
            lw=0.8,
            ms=2.5,
            alpha=0.32,
            zorder=1,
        )
    # Headline: overlay piecewise-linear segments for both directions
    for direction in ("ai_to_neuro", "neuro_to_ai"):
        cps = df_cp[
            (df_cp["direction"] == direction) & (df_cp["metric"] == "or_restricted")
        ].sort_values("segment_index")
        if cps.empty:
            continue
        annotation_pieces = []
        breakpoint_years = []
        for _, seg in cps.iterrows():
            xs = np.array([seg["year_start"], seg["year_end"]], dtype=float)
            ys = seg["slope"] * xs + seg["intercept"]
            ax.plot(
                xs,
                ys,
                "-",
                color=COLORS[direction],
                lw=3.0,
                alpha=0.92,
                zorder=4,
                path_effects=[pe.Stroke(linewidth=4.0, foreground="white"), pe.Normal()],
            )
            annotation_pieces.append(
                f"[{int(seg['year_start'])}-{int(seg['year_end'])}] "
                f"slope={seg['slope']:+.4f}, R²={seg['r2']:.2f}"
            )
            if seg["segment_index"] > 0:
                breakpoint_years.append(int(seg["year_start"]))
        for by in breakpoint_years:
            ax.axvline(by, color=COLORS[direction], ls="--", lw=1.0, alpha=0.55)
            ax.text(
                by + 0.1,
                0.06,
                f"CP {by}",
                color=COLORS[direction],
                rotation=90,
                fontsize=7.5,
                alpha=0.85,
                va="bottom",
                transform=ax.get_xaxis_transform(),
            )
        # Annotation block per direction at the bottom of the panel
        y_anchor = 0.92 if direction == "ai_to_neuro" else 0.78
        ax.text(
            0.985,
            y_anchor,
            f"{LABELS[direction]}: " + "; ".join(annotation_pieces),
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=7,
            color=COLORS[direction],
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="lightgrey", alpha=0.9),
        )
    ax.set_yscale("log")
    ax.set_xlim(X_MIN, X_MAX)
    ax.set_xlabel("Publication year")
    ax.set_ylabel(r"OR$_\mathrm{restricted}$  (piecewise-linear fits overlaid)")
    ax.grid(alpha=0.2)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def build() -> Path:
    apply_style()

    df = pd.read_parquet(CORRECTIONS_DIR / "q1_v3_extended_or_by_year.parquet")
    df_roll = pd.read_parquet(CORRECTIONS_DIR / "q1_v3_extended_rolling_slopes.parquet")
    df_yoy = pd.read_parquet(CORRECTIONS_DIR / "q1_v3_extended_yoy.parquet")
    df_cp = pd.read_parquet(CORRECTIONS_DIR / "q1_v3_extended_changepoints.parquet")

    fig, axes = plt.subplots(
        4,
        1,
        figsize=(11, 14),
        sharex=True,
        gridspec_kw={"height_ratios": [3.0, 2.0, 1.8, 3.0], "hspace": 0.28},
    )
    ax_a, ax_b, ax_c, ax_d = axes

    panel_a_or_curves(ax_a, df)
    panel_b_rolling_slopes(ax_b, df_roll)
    panel_c_yoy(ax_c, df_yoy)
    panel_d_changepoints(ax_d, df, df_cp)

    for letter, ax in zip("ABCD", axes, strict=False):
        _add_panel_label(ax, letter)

    finalize(
        fig,
        source=(
            "OpenAlex snapshot 2026-03-30. Restricted-universe OR. Rolling-window slopes (5y solid, "
            "7y dashed); year-over-year deltas; PELT-L2 piecewise-linear segments overlaid in panel D."
        ),
        byline="Renato Duarte // The Transmitter (supplement)",
    )
    fig.subplots_adjust(top=0.96, bottom=0.05, left=0.08, right=0.97)

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    out_png = FIGURES_DIR / "figure1_v4_diagnostic.png"
    out_svg = FIGURES_DIR / "figure1_v4_diagnostic.svg"
    fig.savefig(out_png)
    fig.savefig(out_svg)
    plt.close(fig)
    logger.info("Wrote %s and %s", out_png, out_svg)
    return out_png


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    try:
        build()
        sys.exit(0)
    except Exception as exc:
        logger.exception("figure1_v4_diagnostic errored: %s", exc)
        sys.exit(2)

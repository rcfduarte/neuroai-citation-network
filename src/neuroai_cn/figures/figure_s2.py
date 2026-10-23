"""Supplement S2 figures, all drawn from the small files committed under results/.

    figure_s2_trends       Figure S2.1  segment fits and rolling slopes of the odds-ratio series
    figure_s2_sensitivity  Figure S2.2  restricted against unrestricted odds ratio; leave-one-topic-out

Colors follow Figure 1: gold = neuroscience papers citing AI, teal = AI papers citing neuroscience.
Long notes live in the captions of docs/supplements/S2-citation-flow.md, not in the images.

Run:
    python -m neuroai_cn.figures.figure_s2
"""

from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from .. import config
from .style import DIRECTION_COLORS, TRANSMITTER, apply_style

logger = logging.getLogger(__name__)

GOLD, TEAL = DIRECTION_COLORS["neuro_to_ai"], DIRECTION_COLORS["ai_to_neuro"]
NAVY, GRAY = TRANSMITTER["navy"], TRANSMITTER["gray"]
FLOW = config.RESULTS_DIR / "flow"
CROSS = config.RESULTS_DIR / "crosssource"
FIG_DIR = config.FIGURES_DIR
LABELS = {
    "neuro_to_ai": "Neuroscience papers citing AI",
    "ai_to_neuro": "AI papers citing neuroscience",
}
COLORS = {"neuro_to_ai": GOLD, "ai_to_neuro": TEAL}
LAST_SOLID = 2023  # 2024 and 2025 are provisional


def _shade_provisional(ax: plt.Axes, x_max: float = 2025.5) -> None:
    ax.axvspan(LAST_SOLID + 0.5, x_max, color=GRAY, alpha=0.13, lw=0)


def _source(fig: plt.Figure, text: str, y: float = 0.0) -> None:
    """One short source line at the bottom left."""
    fig.text(0.01, y, text, ha="left", va="top", fontsize=8, style="italic", color=GRAY)


def _save(fig: plt.Figure, name: str) -> None:
    FIG_DIR.mkdir(exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(FIG_DIR / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)
    logger.info("wrote figures/%s.{png,svg}", name)


def _wide(col: str, path=FLOW / "or_by_year.csv") -> pd.DataFrame:
    return pd.read_csv(path).pivot(index="year", columns="direction", values=col)


def rolling_slopes(series: pd.Series, window: int, first: int = 1995, last: int = LAST_SOLID):
    """OLS slope in a centered window of `window` years, windows inside first..last only."""
    half = window // 2
    out = {}
    for y in range(first + half, last - half + 1):
        seg = series.loc[y - half : y + half]
        out[y] = np.polyfit(seg.index.to_numpy(float), seg.to_numpy(), 1)[0]
    return pd.Series(out)


# ---------------------------------------------------------------------------
# Figure S2.1
# ---------------------------------------------------------------------------


def figure_trends() -> None:
    orr = _wide("or_restricted")
    seg = pd.read_csv(FLOW / "segment_slopes.csv")
    seg = seg[seg.setting.str.startswith("figure")]
    fig, (ax_a, ax_b) = plt.subplots(
        2,
        1,
        figsize=(9.5, 8.2),
        sharex=True,
        gridspec_kw={"height_ratios": [1.5, 1], "hspace": 0.12},
    )
    for d in ("ai_to_neuro", "neuro_to_ai"):
        s = orr[d].loc[1995:2025]
        ax_a.plot(s.index, s.values, "o", color=COLORS[d], ms=3.5, alpha=0.6)
        for _, r in seg[seg.direction == d].iterrows():
            ys = orr[d].loc[int(r.year_start) : int(r.year_end)]
            b1, b0 = np.polyfit(ys.index.to_numpy(float), ys.to_numpy(), 1)
            x = np.array([r.year_start, r.year_end], float)
            ax_a.plot(x, b1 * x + b0, color=COLORS[d], lw=3.2, solid_capstyle="butt")
        for w, ls in ((5, "-"), (7, "--")):
            rs = rolling_slopes(orr[d], w)
            ax_b.plot(rs.index, rs.values, ls, color=COLORS[d], lw=1.8)
    ax_a.set_yscale("log")
    ax_a.set_ylabel("Odds ratio (log scale)")
    ax_a.set_title(
        "A  Yearly odds ratio, segment fits and change points (dashed) of Figure 1C",
        fontsize=11,
        pad=8,
    )
    ax_b.axhline(0, color=GRAY, lw=0.8, ls=":")
    ax_b.set_ylabel("Slope (odds ratio per year)")
    ax_b.set_xlabel("Year")
    ax_b.set_title(
        "B  Rolling OLS slope, 5-year (solid) and 7-year (dashed) windows", fontsize=11, pad=8
    )
    handles = [
        plt.Line2D([], [], color=GOLD, lw=3, label=LABELS["neuro_to_ai"]),
        plt.Line2D([], [], color=TEAL, lw=3, label=LABELS["ai_to_neuro"]),
    ]
    ax_a.legend(handles=handles, loc="lower left", fontsize=9, frameon=False)
    for ax in (ax_a, ax_b):
        _shade_provisional(ax)
        ax.set_xlim(1994.5, 2025.5)
    ax_a.text(
        2024.5,
        ax_a.get_ylim()[0] * 1.15,
        "provisional",
        rotation=90,
        ha="center",
        va="bottom",
        fontsize=8,
        color=GRAY,
    )
    cps = pd.read_csv(FLOW / "changepoints.csv")
    cps = cps[
        cps.setting.str.startswith("figure")
        & (cps.series == "or_restricted")
        & cps.breakpoint_year_first_of_new_segment.notna()
    ]
    for d in ("neuro_to_ai", "ai_to_neuro"):
        for yr in sorted(cps[cps.direction == d].breakpoint_year_first_of_new_segment.astype(int)):
            for ax in (ax_a, ax_b):
                ax.axvline(yr - 0.5, color=COLORS[d], lw=1.1, ls="--", alpha=0.9)
            ax_b.text(
                yr - 0.3,
                0.97 if d == "ai_to_neuro" else 0.89,
                str(yr),
                transform=ax_b.get_xaxis_transform(),
                fontsize=8.5,
                color=COLORS[d],
                fontweight="bold",
                va="top",
            )
    fig.align_ylabels([ax_a, ax_b])
    ax_a.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax_a.yaxis.set_minor_formatter(mticker.NullFormatter())
    ax_a.set_yticks([0.01, 0.02, 0.03, 0.05, 0.08])
    fig.subplots_adjust(bottom=0.1, top=0.95)
    _source(fig, "OpenAlex snapshot of 30 March 2026", y=0.035)
    _save(fig, "figure_s2_trends")


# ---------------------------------------------------------------------------
# Figure S2.2
# ---------------------------------------------------------------------------


def loto_max_change(first: int = 1995, last: int = 2025) -> pd.Series:
    """Largest absolute relative change of the odds ratio per re-admitted topic (fraction)."""
    lo = pd.read_csv(FLOW / "sensitivity_loto.csv").query("@first <= year <= @last")
    return (
        lo.assign(a=lo["pct_change"].abs())
        .groupby("topic_added")
        .a.max()
        .sort_values(ascending=False)
    )


def figure_sensitivity() -> None:
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(13, 4.8))
    for col, ls, lw, kind in (
        ("or_restricted", "-", 2.4, "restricted"),
        ("or_population", "--", 1.5, "unrestricted"),
    ):
        w = _wide(col).loc[1995:2025]
        for d in ("ai_to_neuro", "neuro_to_ai"):
            ax_a.plot(
                w.index,
                w[d],
                ls,
                color=COLORS[d],
                lw=lw,
                alpha=1 if ls == "-" else 0.8,
                label=f"{LABELS[d]}, {kind}",
            )
    ax_a.axhline(1.0, color=GRAY, lw=0.9, ls=":")
    ax_a.set_yscale("log")
    ax_a.set_xlim(1995, 2025.5)
    ax_a.set_xlabel("Year")
    ax_a.set_ylabel("Odds ratio (log scale)")
    ax_a.set_title("A  Restricted and unrestricted odds ratio", fontsize=11, pad=8)
    ax_a.legend(fontsize=7.6, frameon=False, loc="center left", bbox_to_anchor=(0.02, 0.57))
    _shade_provisional(ax_a)
    top = loto_max_change().head(12)[::-1]
    names = [t.rsplit("/", 1)[-1] for t in top.index]
    colors = [TRANSMITTER["crimson"] if n == "T12157" else GRAY for n in names]
    ax_b.barh(range(len(top)), top.values * 100, color=colors, height=0.68)
    ax_b.set_xscale("log")  # T12157 is about 500 percent, the other eleven are 2 to 9 percent
    ax_b.set_xlim(1, 1500)
    ax_b.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}"))
    for i, v in enumerate(top.values * 100):
        ax_b.text(v * 1.08, i, f"{v:.1f}", va="center", fontsize=8)
    ax_b.set_yticks(range(len(top)))
    ax_b.set_yticklabels(names, fontsize=8)
    ax_b.set_xlabel("Largest change in the odds ratio, 1995 to 2025 (%, log scale)")
    ax_b.set_title("B  Leave-one-topic-out, twelve largest effects", fontsize=11, pad=8)
    ax_b.grid(axis="x", alpha=0.25)
    ax_b.grid(axis="y", visible=False)
    _source(fig, "OpenAlex snapshot of 30 March 2026")
    fig.tight_layout()
    _save(fig, "figure_s2_sensitivity")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    apply_style()
    figure_trends()
    figure_sensitivity()


if __name__ == "__main__":
    main()

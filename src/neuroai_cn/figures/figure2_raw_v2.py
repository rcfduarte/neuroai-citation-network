"""Figure 2 for the article (2026-10-06): the raw numbers, two panels, no ratios.

A: cross-field citations per year (how many references cross, in thousands).
B: share of references that cross to the other field (per 1,000 references).

Same colours, same line style as article Fig. 1: thin yearly line, thick centred 5-year mean over the
full series, dashed inside the hatched provisional band (2024-25). Snapshot data only (OpenAlex,
March 2026). Reads results/flow/or_by_year.csv; writes figures/figure2_raw_v2.* and
results/flow/figure2_raw_v2_data.csv.
"""

from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd

from .. import config
from .cross_source import load_snapshot_table, rolling_mean
from .style import DIRECTION_COLORS, TRANSMITTER, apply_style, finalize

logger = logging.getLogger(__name__)
GOLD, TEAL = DIRECTION_COLORS["neuro_to_ai"], DIRECTION_COLORS["ai_to_neuro"]
NAVY, GRAY = TRANSMITTER["navy"], TRANSMITTER["gray"]
LAST_SOLID, X_MIN, X_MAX = 2023, 1995, 2025
FIG_DIR = config.FIGURES_DIR
DATA_DIR = config.RESULTS_DIR / "flow"
LABELS = {
    "neuro_to_ai": "Neuroscience papers citing AI",
    "ai_to_neuro": "AI papers citing neuroscience",
}


def table() -> pd.DataFrame:
    d = load_snapshot_table()
    rows = []
    for dirn in ("neuro_to_ai", "ai_to_neuro"):
        s = d[d.direction == dirn].sort_values("year")
        refs = s.n_to_within + s.n_to_target + s.n_to_other
        cnt = s.n_to_target.to_numpy(dtype=float) / 1000
        shr = (s.n_to_target / refs * 1000).to_numpy(dtype=float)
        mc, ms = rolling_mean(cnt, 5), rolling_mean(shr, 5)
        for i, y in enumerate(s.year.to_numpy()):
            rows.append(
                {
                    "year": int(y),
                    "line_in_figure": LABELS[dirn],
                    "colour": "gold" if dirn == "neuro_to_ai" else "teal",
                    "A_cross_field_citations": int(s.n_to_target.iloc[i]),
                    "A_thousands_yearly": cnt[i],
                    "A_thousands_5yr_centred_mean_PLOTTED": mc[i],
                    "B_cross_refs_per_1000_references_yearly": shr[i],
                    "B_per_1000_5yr_centred_mean_PLOTTED": ms[i],
                    "total_references_recorded": int(refs.iloc[i]),
                    "provisional_year": bool(y > LAST_SOLID),
                }
            )
    return pd.DataFrame(rows)


def _band(ax):
    ax.axvspan(
        LAST_SOLID + 0.5,
        X_MAX + 0.5,
        facecolor=TRANSMITTER["grid"],
        alpha=0.30,
        zorder=0,
        hatch="///",
        edgecolor=GRAY,
        linewidth=0,
    )


def _draw(ax, t, ycol, macol, ylabel, title, ylim, key=""):
    for dirn, c in (("neuro_to_ai", GOLD), ("ai_to_neuro", TEAL)):
        s = t[t.line_in_figure == LABELS[dirn]].sort_values("year")
        yrs = s.year.to_numpy(dtype=float)
        ax.plot(yrs, s[ycol], color=c, lw=0.9, alpha=0.45, zorder=2)
        ma = s[macol].to_numpy()
        solid, tail = yrs <= LAST_SOLID, yrs >= LAST_SOLID
        ax.plot(yrs[solid], ma[solid], color=c, lw=2.8, zorder=3, solid_capstyle="round")
        ax.plot(yrs[tail], ma[tail], color=c, lw=2.8, ls=(0, (3.2, 1.6)), zorder=3)
    _band(ax)
    ax.set_xlim(X_MIN - 0.5, X_MAX + 0.5)
    ax.set_ylim(*ylim)
    ax.set_ylabel(ylabel, color=NAVY)
    ax.set_title(title, loc="left", fontsize=12.5, fontweight="bold", color=NAVY, pad=26)
    ax.text(
        0, 1.02, key, transform=ax.transAxes, fontsize=9.5, color=GRAY, style="italic", va="bottom"
    )


def build() -> None:
    apply_style()
    t = table()
    fig, (a, b) = plt.subplots(1, 2, figsize=(13.0, 5.4))
    _draw(
        a,
        t,
        "A_thousands_yearly",
        "A_thousands_5yr_centred_mean_PLOTTED",
        "thousand citations per year",
        "A  ·  Citations from one field to the other",
        (0, 118),
        key="Citations that cross the boundary, per year.",
    )
    _draw(
        b,
        t,
        "B_cross_refs_per_1000_references_yearly",
        "B_per_1000_5yr_centred_mean_PLOTTED",
        "per 1,000 papers cited",
        "B  ·  Papers cited from the other field, per 1,000",
        (0, 28),
        key="A, divided by everything the field cites, in any science.",
    )
    from matplotlib.lines import Line2D

    b.legend(
        handles=[
            Line2D([], [], color=GOLD, lw=2.8, label=LABELS["neuro_to_ai"]),
            Line2D([], [], color=TEAL, lw=2.8, label=LABELS["ai_to_neuro"]),
        ],
        loc="lower right",
        fontsize=10,
        frameon=False,
    )
    a.text(
        (LAST_SOLID + 0.5 + X_MAX + 0.5) / 2,
        0.04,
        "2024–25:\nprovisional",
        transform=a.get_xaxis_transform(),
        ha="center",
        va="bottom",
        fontsize=7.5,
        color=GRAY,
        style="italic",
    )
    finalize(
        fig,
        title="Raw knowledge exchange",
        subtitle="Citations between neuroscience and AI per year, and their share of everything each field cites, 1995–2025.",
        source="OpenAlex, March 2026 download (about 458 million works).",
        byline="R. Duarte // The Transmitter",
        subtitle_y=0.94,
    )
    fig.subplots_adjust(top=0.76, bottom=0.12, left=0.07, right=0.97, wspace=0.18)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / "figure2_raw_v2.png")
    fig.savefig(FIG_DIR / "figure2_raw_v2.svg")
    fig.savefig(FIG_DIR / "figure2_raw_v2-onwhite.png", facecolor="white", transparent=False)
    t.to_csv(DATA_DIR / "figure2_raw_v2_data.csv", index=False)
    plt.close(fig)
    logger.info("wrote %s and %s", FIG_DIR, DATA_DIR)


if __name__ == "__main__":
    build()

"""Supplement S3 figure: how much of the post-2015 movement of each odds ratio is the raw share and how much is field size.

For each direction the odds ratio of article Figure 1 is the product of two things: the odds of the observed
share of cross-field references (own plus other-field references in the denominator) and the inverse of the
odds expected from field sizes, which for these two fields is the ratio of the citing field's papers to the
cited field's papers. Both factors, and their product, are drawn as an index with 2020 = 100 for 2015 to
2025, so the distance between the lines is the part of the odds ratio that comes from field sizes. Reads
results/flow/or_by_year.csv (via neuroai_cn.analysis.flow_numbers); writes figures/figure_s3_dilution.png and
.svg and results/flow/figure_s3_dilution_data.csv.
"""

from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

from .. import config
from ..analysis import flow_numbers as fn
from .style import DIRECTION_COLORS, TRANSMITTER, apply_style, finalize

logger = logging.getLogger(__name__)
GOLD, TEAL = DIRECTION_COLORS["neuro_to_ai"], DIRECTION_COLORS["ai_to_neuro"]
NAVY, GRAY = TRANSMITTER["navy"], TRANSMITTER["gray"]
X_MIN, X_MAX, LAST_SOLID, BASE = 2015, 2025, 2023, 2020
FIG_DIR = config.FIGURES_DIR
DATA_DIR = config.RESULTS_DIR / "flow"
LABELS = {
    "neuro_to_ai": "Neuroscience papers citing AI",
    "ai_to_neuro": "AI papers citing neuroscience",
}


def table() -> pd.DataFrame:
    """One row per year and direction: odds ratio, its two factors, and each indexed to 2020 = 100."""
    d = fn.load()
    rows = []
    for dirn in fn.DIRECTIONS:
        s = d[(d.direction == dirn) & d.year.between(X_MIN, X_MAX)].set_index("year")
        obs_odds = s.rho_restricted / (1 - s.rho_restricted)
        size_factor = s.n_works_source / s.n_works_target  # citing papers / cited papers
        t = pd.DataFrame(
            {
                "year": s.index,
                "direction": dirn,
                "line_in_figure": LABELS[dirn],
                "odds_ratio": s.or_restricted,
                "observed_odds": obs_odds,
                "size_factor_citing_over_cited_papers": size_factor,
            }
        )
        for col in ("odds_ratio", "observed_odds", "size_factor_citing_over_cited_papers"):
            t[col + "_index_2020_100"] = 100 * t[col] / t.loc[t.year == BASE, col].iloc[0]
        t["provisional_year"] = t.year > LAST_SOLID
        rows.append(t)
    return pd.concat(rows, ignore_index=True)


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


def build() -> None:
    apply_style()
    t = table()
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.4), sharey=True)
    panels = (
        ("ai_to_neuro", TEAL, "A  ·  AI papers citing neuroscience"),
        ("neuro_to_ai", GOLD, "B  ·  Neuroscience papers citing AI"),
    )
    for ax, (dirn, colour, title) in zip(axes, panels, strict=True):
        s = t[t.direction == dirn].sort_values("year")
        ax.axhline(100, color=GRAY, lw=0.8, ls=":", zorder=1)
        ax.plot(s.year, s.odds_ratio_index_2020_100, color=colour, lw=2.8, zorder=3)
        ax.plot(
            s.year,
            s.observed_odds_index_2020_100,
            color=colour,
            lw=1.8,
            ls=(0, (4, 2)),
            zorder=3,
        )
        ax.plot(
            s.year,
            s.size_factor_citing_over_cited_papers_index_2020_100,
            color=GRAY,
            lw=1.8,
            ls=(0, (1, 1.6)),
            zorder=3,
        )
        _band(ax)
        ax.set_xlim(X_MIN - 0.5, X_MAX + 0.5)
        ax.set_title(title, loc="left", fontsize=12.5, fontweight="bold", color=NAVY)
        ax.set_xticks(range(2015, 2026, 2))
        ax.legend(
            handles=[
                Line2D([], [], color=colour, lw=2.8, label="odds ratio of Figure 1"),
                Line2D(
                    [], [], color=colour, lw=1.8, ls=(0, (4, 2)), label="observed odds (raw share)"
                ),
                Line2D(
                    [],
                    [],
                    color=GRAY,
                    lw=1.8,
                    ls=(0, (1, 1.6)),
                    label="field-size factor (citing / cited papers)",
                ),
            ],
            loc="upper left",
            fontsize=9.5,
            frameon=False,
        )
    axes[0].set_ylabel("index, 2020 = 100", color=NAVY)
    axes[0].text(
        (LAST_SOLID + 0.5 + X_MAX + 0.5) / 2,
        0.04,
        "2024–25:\nprovisional",
        transform=axes[0].get_xaxis_transform(),
        ha="center",
        va="bottom",
        fontsize=7.5,
        color=GRAY,
        style="italic",
    )
    finalize(
        fig,
        title="Raw share versus field size",
        subtitle="Odds ratio = observed odds x field-size factor, each indexed to 2020, 2015–2025.",
        source="OpenAlex, March 2026 snapshot. Data: results/flow/figure_s3_dilution_data.csv.",
        byline="R. Duarte",
        subtitle_y=0.94,
    )
    fig.subplots_adjust(top=0.80, bottom=0.12, left=0.07, right=0.97, wspace=0.06)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / "figure_s3_dilution.png")
    fig.savefig(FIG_DIR / "figure_s3_dilution.svg")
    t.to_csv(DATA_DIR / "figure_s3_dilution_data.csv", index=False)
    plt.close(fig)
    logger.info("wrote %s and %s", FIG_DIR, DATA_DIR)


if __name__ == "__main__":
    build()

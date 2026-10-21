"""Supplement S6 figure: publication year of the top 100 under four rankings.

Figure S6.1 counts, for each of four rankings of the bridge papers (published, citations per
year to 2023, equal 8-year window, growth-normalized 8-year window), the works of its top 100
by first publication year, stacked by hand-coded class. Reads only committed files:
``results/citation_age/ranking_{orig,rate,win8,win8_share}_top100.csv`` and ``classification.csv``.

Run ``python -m neuroai_cn.figures.figure_s6``; writes PNG and SVG to ``figures/``.
"""

from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .. import config
from .style import TRANSMITTER, apply_style, finalize

logger = logging.getLogger(__name__)
R = config.RESULTS_DIR / "citation_age"

PANELS = {
    "orig": "Published ranking (all-time counts)",
    "rate": "Citations per year to 2023",
    "win8": "Equal 8-year window (works 1990-2015)",
    "win8_share": "Equal 8-year window, growth-normalized",
}
CLASSES = ("concept", "method", "tool", "book", "artefact")
# Gold and teal are reserved for the two citation flows, so classes use other colors.
COLORS = {
    "concept": TRANSMITTER["navy"],
    "method": TRANSMITTER["purple"],
    "tool": TRANSMITTER["coral"],
    "book": TRANSMITTER["muted"],
    "artefact": TRANSMITTER["grid"],
}
LABELS = {
    "concept": "Concept (claim about brains or minds)",
    "method": "Machine-learning method",
    "tool": "Tool (software, data, benchmark, analysis method)",
    "book": "Textbook typed as article",
    "artefact": "Merged or generic record",
}


def main() -> None:
    apply_style()
    cl = pd.read_csv(R / "classification.csv", comment="#").rename(columns={"class": "cls"})
    years = np.arange(1988, 2027)  # 1988 = "before 1990" bin
    fig, axes = plt.subplots(4, 1, figsize=(9.5, 10.8), sharex=True, sharey=True)
    for ax, (name, label) in zip(axes, PANELS.items(), strict=True):
        g = pd.read_csv(R / f"ranking_{name}_top100.csv").merge(
            cl[["title_norm", "cls", "true_year"]], on="title_norm", how="left"
        )
        g = g.sort_values("rank").head(100)
        g["plot_year"] = g["true_year"].where(g["true_year"] >= 1990, 1988)
        bottom = np.zeros(len(years))
        for c in CLASSES:
            h = g[g["cls"] == c]["plot_year"].value_counts().reindex(years, fill_value=0)
            ax.bar(years, h.values, bottom=bottom, width=0.82, color=COLORS[c], label=LABELS[c])
            bottom += h.values
        ax.axvline(2005.5, color=TRANSMITTER["crimson"], lw=1.1, ls="--")
        n_late = int(((g["cls"] == "concept") & (g["true_year"] > 2005)).sum())
        ax.set_title(
            f"{label}\ntop 100: median year {g['true_year'].median():.0f}; "
            f"{n_late} concepts published after 2005",
            loc="left",
            fontsize=10,
            color=TRANSMITTER["navy"],
        )
        if name in ("win8", "win8_share"):
            ax.axvspan(2015.5, 2026.7, color=TRANSMITTER["grid"], alpha=0.7, lw=0)
        if name == "rate":
            ax.axvspan(2023.5, 2026.7, color=TRANSMITTER["grid"], alpha=0.7, lw=0)
        ax.set_ylabel("works")
    ymax = max(ax.get_ylim()[1] for ax in axes) + 3
    for ax in axes:
        ax.set_ylim(0, ymax)
    for ax in axes[2:]:
        ax.text(
            2021.1,
            ymax * 0.93,
            "not eligible:\nwindow would close\nafter 2023",
            ha="center",
            va="top",
            fontsize=8,
            color=TRANSMITTER["gray"],
        )
    axes[1].text(
        2025.1, ymax * 0.93, "after\n2023", ha="center", va="top", fontsize=8, color="gray"
    )
    axes[0].text(
        2005.8, ymax * 0.97, "after 2005", fontsize=8.5, color=TRANSMITTER["crimson"], va="top"
    )
    axes[0].legend(loc="upper left", fontsize=8, frameon=False, ncol=1)
    axes[-1].set_xlabel("first publication year")
    ticks = [1988, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025]
    axes[-1].set_xticks(ticks)
    axes[-1].set_xticklabels(["<1990", *map(str, ticks[1:])])
    axes[-1].set_xlim(1987.2, 2026.8)
    finalize(
        fig,
        title="Publication year of the 100 strongest bridge works, four rankings",
        source="OpenAlex snapshot of 30 March 2026.",
        byline="R. Duarte",
    )
    fig.subplots_adjust(top=0.92, bottom=0.07, left=0.07, right=0.98, hspace=0.45)
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(config.FIGURES_DIR / f"figure_s6_top100_years.{ext}")
    plt.close(fig)
    logger.info("wrote figures/figure_s6_top100_years.{png,svg}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()

"""Supplement S1 figure: how many works each field holds per year, and how many carry references.

A: works per publication year, 1990-2025, for neuroscience (OpenAlex field 28) and for three
definitions of AI (the extended definition used in the article, whole subfield 1702, and the
curated 35-topic core used as a sensitivity check). B: the share of those works whose reference
list is present in the snapshot, which is the part of each field that can cite at all. Reads
results/flow/field_sizes_by_year.csv (written by neuroai_cn.analysis.export_field_sizes); writes
figures/figure_s1_field_sizes.png and .svg.
"""

from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

from .. import config
from .style import DIRECTION_COLORS, TRANSMITTER, apply_style, finalize

logger = logging.getLogger(__name__)
GOLD, TEAL = DIRECTION_COLORS["neuro_to_ai"], DIRECTION_COLORS["ai_to_neuro"]
NAVY, GRAY = TRANSMITTER["navy"], TRANSMITTER["gray"]
X_MIN, X_MAX, LAST_SOLID = 1990, 2025, 2023
SRC = config.RESULTS_DIR / "flow" / "field_sizes_by_year.csv"

SERIES = (
    ("neuroscience", "Neuroscience (field 28)", GOLD, "-"),
    ("ai_extended", "AI, extended definition (article)", TEAL, "-"),
    ("ai_subfield_1702_whole", "AI, whole subfield 1702", TEAL, (0, (4, 2))),
    ("ai_strict_core35", "AI, curated 35-topic core", TEAL, (0, (1, 1.6))),
)


def load() -> pd.DataFrame:
    d = pd.read_csv(SRC)
    return d[(d.year >= X_MIN) & (d.year <= X_MAX)]


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
    d = load()
    n = d.pivot(index="year", columns="definition", values="n_works")
    r = d.pivot(index="year", columns="definition", values="n_with_references")
    fig, (a, b) = plt.subplots(1, 2, figsize=(13.0, 5.4))
    for key, _label, colr, ls in SERIES:
        a.plot(n.index, n[key], color=colr, ls=ls, lw=2.4, zorder=3)
        b.plot(n.index, 100 * r[key] / n[key], color=colr, ls=ls, lw=2.4, zorder=3)
    for ax in (a, b):
        _band(ax)
        ax.set_xlim(X_MIN - 0.5, X_MAX + 0.5)
        ax.axvline(2002, color=GRAY, lw=0.8, ls=":", zorder=1)
    a.set_yscale("log")
    ticks = [10_000, 30_000, 100_000, 300_000, 1_000_000, 3_000_000]
    a.set_yticks(ticks, ["10k", "30k", "100k", "300k", "1M", "3M"])
    a.minorticks_off()
    a.set_ylim(9_000, 4_500_000)
    b.set_ylim(0, 100)
    a.set_ylabel("works per year (log scale)", color=NAVY)
    b.set_ylabel("percent of the field's works", color=NAVY)
    a.set_title("A  ·  Works per year", loc="left", fontsize=12.5, fontweight="bold", color=NAVY)
    b.set_title(
        "B  ·  Works with a reference list",
        loc="left",
        fontsize=12.5,
        fontweight="bold",
        color=NAVY,
    )
    a.text(
        2002.3,
        0.12,
        "2002: AI count\nnearly doubles",
        transform=a.get_xaxis_transform(),
        fontsize=8,
        color=GRAY,
        va="top",
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
    a.legend(
        handles=[Line2D([], [], color=c, ls=ls, lw=2.4, label=lab) for _, lab, c, ls in SERIES],
        loc="upper left",
        fontsize=9,
        frameon=False,
    )
    finalize(
        fig,
        title="How big each field is",
        subtitle="Works per publication year by field definition, and the share whose references are recorded, 1990–2025.",
        source="OpenAlex, March 2026 snapshot; primary topic of each work. Data: results/flow/field_sizes_by_year.csv.",
        byline="R. Duarte",
        subtitle_y=0.94,
    )
    fig.subplots_adjust(top=0.80, bottom=0.12, left=0.07, right=0.97, wspace=0.18)
    out = config.FIGURES_DIR
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "figure_s1_field_sizes.png")
    fig.savefig(out / "figure_s1_field_sizes.svg")
    plt.close(fig)
    logger.info("wrote %s", out / "figure_s1_field_sizes.png")


if __name__ == "__main__":
    build()

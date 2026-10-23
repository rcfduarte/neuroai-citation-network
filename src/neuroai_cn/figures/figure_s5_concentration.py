"""Supplement S5 figure: how concentrated the bridge weight is across authors and institutions.

Panel A draws, for authors (teal) and institutions (gold), the share of all bridge weight held by the
top N entities (log axis). The thick line is the article's pool (the sensitivity bound of S5, which
drops entities averaging more than 400 units of B per paper); the thin dashed lines are two other
pools of the same table. Panel B draws the Gini coefficient of bridge weight: for the top 1,000
entities of the article's pool, and for every entity of the 58,971 eligible papers.

Reads ``results/bridge/concentration_tiers.csv`` and ``headline_numbers.csv``. Run
``python -m neuroai_cn.figures.figure_s5_concentration``; writes PNG and SVG to ``figures/``.
"""

from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from .. import config
from .style import TRANSMITTER, apply_style, finalize

logger = logging.getLogger(__name__)
R = config.RESULTS_DIR / "bridge"
GOLD, TEAL, NAVY, GRAY = (TRANSMITTER[k] for k in ("mustard", "teal", "navy", "gray"))
POOLS = (
    ("all_133763_minus_mean_B_gt_400", "Pool of the article", "-", 3.0),
    ("e2_58971", "Eligible papers (58,971)", (0, (4, 2)), 1.5),
    ("all_133763_unfiltered", "Every paper passing the gate (133,763)", (0, (1, 1.6)), 1.5),
)
COLORS = {"authors": TEAL, "institutions": GOLD}


def main() -> None:
    apply_style()
    t = pd.read_csv(R / "concentration_tiers.csv")
    h = {
        k: float(v)
        for k, v in pd.read_csv(R / "headline_numbers.csv").values
        if k.startswith("gini_")
    }
    fig, (ax, bx) = plt.subplots(
        1, 2, figsize=(12.0, 5.2), gridspec_kw={"width_ratios": [1.5, 1], "wspace": 0.22}
    )
    for pool, _, ls, lw in POOLS:
        for entity, color in COLORS.items():
            s = t[(t.pool == pool) & (t.entity == entity)].sort_values("top_n")
            ax.plot(s.top_n, s.share_pct, color=color, lw=lw, ls=ls)
    main_pool = t[t.pool == POOLS[0][0]]
    for entity, color in COLORS.items():
        for n in (100,):
            v = float(
                main_pool[(main_pool.entity == entity) & (main_pool.top_n == n)].share_pct.iloc[0]
            )
            ax.scatter([n], [v], color=color, s=38, zorder=5)
            ax.annotate(
                f"top {n}: {v:.1f}%",
                (n, v),
                xytext=(8, -4 if entity == "institutions" else -20),
                textcoords="offset points",
                fontsize=10,
                color=color,
                fontweight="bold",
            )
    ax.set_xscale("log")
    ax.set_ylim(0, 100)
    ax.set_xlabel("N, the number of top-ranked entities (log scale)", color=NAVY)
    ax.set_ylabel("share of all bridge weight held by the top N (%)", color=NAVY)
    ax.set_title(
        "A  Cumulative concentration", loc="left", fontsize=12, fontweight="bold", color=NAVY
    )
    ax.grid(True, axis="y", color=TRANSMITTER["grid"], lw=0.6)
    handles = [
        Line2D([], [], color=TEAL, lw=3, label="authors"),
        Line2D([], [], color=GOLD, lw=3, label="institutions"),
    ] + [Line2D([], [], color=GRAY, lw=lw, ls=ls, label=lab) for _, lab, ls, lw in POOLS]
    ax.legend(handles=handles, loc="upper left", fontsize=9, frameon=False)

    groups = (
        ("Pool of the article\n(top 1,000 entities)", "gini_adjusted_{}_top1000"),
        ("Eligible papers\n(all entities)", "gini_e2_58971_{}_all"),
    )
    width = 0.36
    x = np.arange(len(groups))
    for j, entity in enumerate(("authors", "institutions")):
        vals = [h[key.format(entity)] for _, key in groups]
        bars = bx.bar(x + (j - 0.5) * width, vals, width, color=COLORS[entity], label=entity)
        for b, v in zip(bars, vals, strict=True):
            bx.text(
                b.get_x() + b.get_width() / 2,
                v + 0.015,
                f"{v:.2f}",
                ha="center",
                fontsize=10,
                color=NAVY,
                fontweight="bold",
            )
    bx.set_xticks(x)
    bx.set_xticklabels([g[0] for g in groups], fontsize=9.5)
    bx.set_ylim(0, 1)
    bx.set_ylabel("Gini coefficient of bridge weight", color=NAVY)
    bx.set_title("B  Inequality", loc="left", fontsize=12, fontweight="bold", color=NAVY)
    bx.grid(True, axis="y", color=TRANSMITTER["grid"], lw=0.6)
    bx.legend(loc="upper left", fontsize=9, frameon=False)
    finalize(
        fig,
        title="Bridge weight concentrates more by place than by person",
        source="OpenAlex snapshot of 30 March 2026. Data: results/bridge/concentration_tiers.csv, headline_numbers.csv.",
        byline="R. Duarte",
    )
    fig.subplots_adjust(top=0.84, bottom=0.17, left=0.07, right=0.98)
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(config.FIGURES_DIR / f"figure_s5_concentration.{ext}")
    plt.close(fig)
    logger.info("wrote figures/figure_s5_concentration.{png,svg}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()

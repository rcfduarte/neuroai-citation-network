"""Supplement S5 figure: when the strongest bridge papers were published.

For the top 100, the top 1,000 and all 58,971 eligible papers ranked by B, draws the share published
before 2012, in 2012 to 2015, in 2016 to 2019 and from 2020 onward (no display filters).
Reads ``results/bridge/era_composition.csv``. Run ``python -m neuroai_cn.figures.figure_s5_eras``;
writes PNG and SVG to ``figures/``.
"""

from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd

from .. import config
from .style import TRANSMITTER, apply_style, finalize

logger = logging.getLogger(__name__)
BINS = (
    ("n_before_2012", "before 2012", "#0F3047"),
    ("n_2012_2015", "2012 to 2015", "#59278A"),
    ("n_2016_2019", "2016 to 2019", "#FD6760"),
    ("n_2020_onward", "2020 onward", "#9C978D"),
)
TIERS = (("top_100", "Top 100"), ("top_1000", "Top 1,000"), ("all_eligible", "All 58,971 eligible"))


def main() -> None:
    apply_style()
    d = pd.read_csv(config.RESULTS_DIR / "bridge" / "era_composition.csv").set_index("tier")
    fig, ax = plt.subplots(figsize=(9.5, 3.6))
    for i, (tier, _label) in enumerate(TIERS):
        left = 0.0
        row = d.loc[tier]
        for col, _, color in BINS:
            pct = 100 * row[col] / row["n"]
            ax.barh(i, pct, left=left, color=color, height=0.6)
            if pct >= 4:
                ax.text(
                    left + pct / 2,
                    i,
                    f"{pct:.0f}%",
                    ha="center",
                    va="center",
                    fontsize=10,
                    color="white",
                    fontweight="bold",
                )
            left += pct
        ax.text(
            101,
            i,
            f"median {int(row['median_year'])}",
            va="center",
            fontsize=9.5,
            color=TRANSMITTER["gray"],
        )
    ax.set_yticks(range(len(TIERS)))
    ax.set_yticklabels([t[1] for t in TIERS])
    ax.invert_yaxis()
    ax.set_xlim(0, 112)
    ax.set_xlabel("share of the papers (%)")
    ax.grid(False)
    ax.legend(
        handles=[plt.Rectangle((0, 0), 1, 1, color=c, label=lab) for _, lab, c in BINS],
        loc="upper center",
        bbox_to_anchor=(0.45, -0.28),
        ncol=4,
        frameon=False,
        fontsize=9.5,
        title="publication year",
    )
    finalize(
        fig,
        title="Publication year of the strongest bridge papers",
        source="OpenAlex snapshot of 30 March 2026. Data: results/bridge/era_composition.csv.",
        byline="R. Duarte",
    )
    fig.subplots_adjust(top=0.85, bottom=0.34, left=0.17, right=0.98)
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(config.FIGURES_DIR / f"figure_s5_eras.{ext}")
    plt.close(fig)
    logger.info("wrote figures/figure_s5_eras.{png,svg}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()

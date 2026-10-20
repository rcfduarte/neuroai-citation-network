"""Supplement figure S2.4: two sensitivity checks of the citation-flow result.

    A  restricted versus population odds ratio (S2 section 4.6)
    B  leave-one-topic-out, the effect of each excluded topic (S2 section 4.7)

Both panels read the 2026-05-08 correction vintage that feeds the article's main figure, so
nothing here is cross-vintage.

Run:
    python -m neuroai_cn.figures.sensitivity_fig
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .. import config
from .style import TRANSMITTER, apply_style

logger = logging.getLogger(__name__)

D = config.CORRECTIONS_DIR / "20260508"
YEAR_MIN, YEAR_MAX = 1995, 2025
UNSTABLE_FROM = 2024  # OpenAlex rebuild; shaded in every time panel.

# Article labels follow where influence lands; data columns are named after the
# citation link, which is the reverse. See S1 section 2.
INFLUENCE = {
    "ai_to_neuro": ("Neuro→AI  (neuroscience informs AI)", TRANSMITTER["teal"]),
    "neuro_to_ai": ("AI→Neuro  (AI informs neuroscience)", TRANSMITTER["mustard"]),
}


def _shade_unstable(ax: plt.Axes) -> None:
    ax.axvspan(UNSTABLE_FROM - 0.5, YEAR_MAX + 0.5, color=TRANSMITTER["gray"], alpha=0.13, lw=0)


def _clip(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df.year >= YEAR_MIN) & (df.year <= YEAR_MAX)]


def panel_a(ax: plt.Axes) -> None:
    df = _clip(pd.read_parquet(D / "q1_v3_extended_or_by_year.parquet"))
    for d, (label, color) in INFLUENCE.items():
        s = df[df.direction == d].sort_values("year")
        ax.plot(
            s.year,
            s.or_restricted,
            color=color,
            lw=2.2,
            label=f"{label.split('  ')[0]}, restricted",
        )
        ax.plot(
            s.year,
            s.or_population,
            color=color,
            lw=1.4,
            ls="--",
            alpha=0.75,
            label=f"{label.split('  ')[0]}, population",
        )
    ax.axhline(1.0, color=TRANSMITTER["gray"], lw=0.9, ls=":")
    ax.set_yscale("log")
    ax.set_ylabel("Odds ratio (log scale)")
    ax.set_title("A  Restricted versus population null", loc="left", fontsize=10.5, pad=8)
    ax.legend(fontsize=7.4, frameon=False, loc="lower right", ncol=1)
    _shade_unstable(ax)
    ax.text(
        UNSTABLE_FROM + 0.2,
        ax.get_ylim()[0] * 1.25,
        "unstable",
        fontsize=7,
        color=TRANSMITTER["gray"],
        rotation=90,
        va="bottom",
    )


def panel_b(ax: plt.Axes) -> None:
    lo = pd.read_parquet(D / "loto_sensitivity.parquet")
    lo = lo[(lo.year >= YEAR_MIN) & (lo.year <= YEAR_MAX)]
    per_topic = (
        lo.assign(abs_pct=lo["pct_change"].abs())
        .groupby("topic_added")
        .abs_pct.max()
        .sort_values(ascending=False)
    )
    top = per_topic.head(12)[::-1]
    names = [t.rsplit("/", 1)[-1] for t in top.index]
    colors = [TRANSMITTER["crimson"] if n == "T12157" else TRANSMITTER["gray"] for n in names]
    ax.barh(range(len(top)), top.values * 100, color=colors, height=0.68)
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel("Largest change in the odds ratio if the topic is re-admitted (%)")
    ax.set_title(
        "B  Leave-one-topic-out, twelve most influential", loc="left", fontsize=10.5, pad=8
    )
    ax.grid(axis="x", alpha=0.25)
    ax.text(
        0.97,
        0.06,
        "T12157 = the geology\nre-export artifact",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=7.6,
        color=TRANSMITTER["crimson"],
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    apply_style()

    fig, axes = plt.subplots(1, 2, figsize=(13.0, 4.8))
    panel_a(axes[0])
    panel_b(axes[1])
    axes[0].set_xlim(YEAR_MIN, YEAR_MAX)
    axes[0].set_xlabel("Year")
    axes[0].grid(alpha=0.22)

    fig.suptitle(
        "Sensitivity of the citation-flow result to the null and to the excluded topics",
        x=0.006,
        ha="left",
        fontsize=13,
        color=TRANSMITTER["navy"],
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))

    out = Path(__file__).resolve().parents[3] / "figures"
    out.mkdir(exist_ok=True)
    for e in ("png", "svg"):
        fig.savefig(
            out / f"fig_sensitivity.{e}", bbox_inches="tight", dpi=200 if e == "png" else None
        )
    logger.info("wrote %s/fig_sensitivity.{png,svg}", out)


if __name__ == "__main__":
    main()

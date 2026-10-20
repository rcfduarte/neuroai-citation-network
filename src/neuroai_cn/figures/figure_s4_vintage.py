"""Supplement S4 figures: what each field cites in the other, how old it is, the six NeuroAI papers.

Four figures, all drawn from committed files under ``results/`` only:

* ``figure_s4_composition``: A, AI papers citing neuroscience, share of citations by OpenAlex
  subfield of the cited work and citing year (35-topic AI core, exclusive cited set); B, the
  cognitive and the cellular-and-molecular shares for citing years 2020-2025 under the 35-topic
  core and the two cited sets; C and D, neuroscience papers citing AI, share by
  category of the cited AI topic and citing year, extended definition and 35-topic core.
  Data: ``results/vintage/matrix_cited_vintage.csv``, ``results/vintage/subfield_breakdown.csv``,
  ``results/flow/flow_composition_topic_year.csv``.
* ``figure_s4_vintage``: distribution of the publication year of the cited work, 2010-2019 against
  2020-2025 citing papers, for AI citing neuroscience (A) and neuroscience citing AI (B), exclusive
  cited sets; C, median cited year by citing year. Data: ``matrix_cited_vintage.csv``,
  ``vintage_summary.csv``, ``vintage_by_year.csv``.
* ``figure_s4_manifestos``: A, citations from AI papers to the six NeuroAI review papers of the
  article sidebar, per year and paper; B, those citations as a share of all AI-to-neuroscience
  citations. Data: ``results/manifestos/citations_by_paper_year_field.csv``,
  ``share_of_flow_by_year.csv``.
* ``figure_s4_reference_age``: A, distribution of reference age for AI and neuroscience articles
  and reviews of 2020-2023; B, median reference age by citing year; C, share of papers with any
  reference list. Data: ``matrix_reference_age.csv``, ``reference_age_by_field.csv``,
  ``reference_list_coverage.csv``.

Run ``python -m neuroai_cn.figures.figure_s4_vintage``; writes PNG and SVG to ``figures/``.
"""

from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from .. import config
from .flow_composition_fig import COLORS as CAT_COLORS
from .flow_composition_fig import ORDER as CAT_ORDER
from .style import DIRECTION_COLORS, TRANSMITTER, apply_style, finalize

logger = logging.getLogger(__name__)
V = config.RESULTS_DIR / "vintage"
M = config.RESULTS_DIR / "manifestos"
F = config.RESULTS_DIR / "flow"
FIG_DIR = config.FIGURES_DIR
TEAL, GOLD = DIRECTION_COLORS["ai_to_neuro"], DIRECTION_COLORS["neuro_to_ai"]
NAVY, GRAY = TRANSMITTER["navy"], TRANSMITTER["gray"]
LAST_SOLID = 2023
SOURCE = "OpenAlex, March 2026 snapshot (works from 1990 on)."

SUBFIELD_GROUPS = {
    "Cognitive Neuroscience": ("Cognitive neuroscience", TEAL),
    "Cellular and Molecular Neuroscience": ("Cellular and molecular", TRANSMITTER["coral"]),
    "Neurology": ("Neurology", TRANSMITTER["purple"]),
}
OTHER_SUBFIELDS = ("Five other subfields", TRANSMITTER["muted"])


def _band(ax, x_max: int = 2025) -> None:
    ax.axvspan(
        LAST_SOLID + 0.5,
        x_max + 0.5,
        facecolor=TRANSMITTER["grid"],
        alpha=0.30,
        zorder=0,
        hatch="///",
        edgecolor=GRAY,
        linewidth=0,
    )


def _save(fig, name: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(FIG_DIR / f"{name}.{ext}")
    plt.close(fig)
    logger.info("wrote figures/%s.{png,svg}", name)


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


def ai_citing_neuro_by_subfield(
    cited_set: str = "unrestricted", core_only: bool = False
) -> pd.DataFrame:
    """Share of AI-to-neuroscience citations per citing year by group of cited subfield, percent.

    ``core_only`` keeps the citing papers of the 35-topic AI core.
    """
    m = pd.read_csv(V / "matrix_cited_vintage.csv")
    m = m[m.direction == "ai_to_neuro"]
    if core_only:
        m = m[m.citing_strict == 1]
    if cited_set == "exclusive":
        m = m[m.cited_dual == 0]
    m = m.assign(group=m.cited_sf_name.map(lambda s: s if s in SUBFIELD_GROUPS else "other"))
    p = m.pivot_table(index="citing_year", columns="group", values="n", aggfunc="sum").fillna(0)
    p = p[[*SUBFIELD_GROUPS, "other"]]
    return p.div(p.sum(axis=1), axis=0) * 100


def neuro_citing_ai_by_category(classifier: str) -> pd.DataFrame:
    d = pd.read_csv(F / "flow_composition_topic_year.csv")
    d = d[(d.classifier == classifier) & d.citing_year.between(1995, 2025)]
    p = d.pivot_table(index="citing_year", columns="category", values="n_cites", aggfunc="sum")
    p = p.reindex(columns=CAT_ORDER).fillna(0)
    return p.div(p.sum(axis=1), axis=0) * 100


def figure_composition() -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 10.2))
    (ax_a, ax_b), (ax_c, ax_d) = axes

    p = ai_citing_neuro_by_subfield("exclusive", core_only=True).loc[1995:2025]
    cols = [SUBFIELD_GROUPS[c][1] for c in SUBFIELD_GROUPS] + [OTHER_SUBFIELDS[1]]
    ax_a.stackplot(p.index, p.T.values, colors=cols, edgecolor="white", linewidth=0.4)
    _band(ax_a)
    ax_a.set_xlim(1995, 2025.5)
    ax_a.set_ylim(0, 100)
    ax_a.set_ylabel("share of citations (%)")
    ax_a.set_title(
        "A  ·  AI papers (35-topic core) citing neuroscience, by cited subfield", fontsize=12
    )
    ax_a.legend(
        handles=[
            Patch(color=SUBFIELD_GROUPS[c][1], label=SUBFIELD_GROUPS[c][0]) for c in SUBFIELD_GROUPS
        ]
        + [Patch(color=OTHER_SUBFIELDS[1], label=OTHER_SUBFIELDS[0])],
        loc="lower left",
        fontsize=8.5,
        ncol=2,
        bbox_to_anchor=(0.0, 0.02),
        frameon=True,
        facecolor="white",
        edgecolor="none",
    )

    s = pd.read_csv(V / "subfield_breakdown.csv")
    s = s[(s.direction == "ai_to_neuro") & (s.citing_def == "all") & (s.period == "2020-2025")]
    cells = [
        ("strict35", "exclusive", "35-topic core,\nexclusive"),
        ("strict35", "unrestricted", "35-topic core,\nunrestricted"),
    ]
    x = np.arange(len(cells))
    for off, sf, colour in (
        (-0.2, "Cognitive Neuroscience", TEAL),
        (0.2, "Cellular and Molecular Neuroscience", TRANSMITTER["coral"]),
    ):
        vals = [
            100
            * s[
                (s.classifier == c) & (s.cited_set == cs) & (s.cited_sf_name == sf)
            ].share_edges.iloc[0]
            for c, cs, _ in cells
        ]
        ax_b.bar(x + off, vals, width=0.38, color=colour)
        for xi, v in zip(x + off, vals, strict=True):
            ax_b.text(xi, v + 1.2, f"{v:.1f}", ha="center", va="bottom", fontsize=8.5, color=NAVY)
    ax_b.axhline(90, color=GRAY, lw=0.9, ls=":")
    ax_b.axhline(5, color=GRAY, lw=0.9, ls=":")
    ax_b.text(1.62, 90, "90", va="center", fontsize=8, color=GRAY)
    ax_b.text(1.62, 5, "5", va="center", fontsize=8, color=GRAY)
    ax_b.set_xticks(x, [c[2] for c in cells], fontsize=9)
    ax_b.set_xlim(-0.6, 1.85)
    ax_b.set_ylim(0, 118)
    ax_b.set_ylabel("share of citations, citing years 2020–2025 (%)")
    ax_b.set_title("B  ·  The 90 / 5 sentence, 35-topic AI core", fontsize=12)
    ax_b.legend(
        handles=[
            Patch(color=TEAL, label="Cognitive neuroscience"),
            Patch(color=TRANSMITTER["coral"], label="Cellular and molecular"),
        ],
        loc="upper center",
        ncol=2,
        fontsize=8.5,
    )

    for ax, classifier, title in (
        (ax_c, "extended", "C  ·  Neuroscience papers citing AI, extended AI definition"),
        (ax_d, "strict", "D  ·  Neuroscience papers citing AI, 35-topic AI core"),
    ):
        q = neuro_citing_ai_by_category(classifier)
        ax.stackplot(
            q.index,
            q.T.values,
            colors=[CAT_COLORS[c] for c in CAT_ORDER],
            edgecolor="white",
            linewidth=0.4,
        )
        _band(ax)
        ax.set_xlim(1995, 2025.5)
        ax.set_ylim(0, 100)
        ax.set_ylabel("share of citations (%)")
        ax.set_title(title, fontsize=12)
    fig.legend(
        handles=[Patch(color=CAT_COLORS[c], label=c) for c in CAT_ORDER],
        loc="lower center",
        ncol=3,
        fontsize=9,
        bbox_to_anchor=(0.5, 0.035),
    )
    for ax in (ax_a, ax_c, ax_d):
        ax.set_xlabel("year of the citing paper")
    finalize(
        fig,
        title="What each field cites when it cites the other",
        subtitle="Shares of cross-field citations; hatched: 2024–25 provisional.",
        source=SOURCE + " Data: results/vintage/matrix_cited_vintage.csv, subfield_breakdown.csv;"
        " results/flow/flow_composition_topic_year.csv.",
        byline="R. Duarte",
        subtitle_y=0.955,
    )
    fig.subplots_adjust(top=0.90, bottom=0.14, left=0.06, right=0.98, hspace=0.32, wspace=0.18)
    _save(fig, "figure_s4_composition")


# ---------------------------------------------------------------------------
# Vintage of the cited work
# ---------------------------------------------------------------------------


def cited_year_distribution(direction: str, period: tuple[int, int]) -> pd.Series:
    """Share of citation edges (percent) by publication year of the cited work, exclusive set."""
    m = pd.read_csv(V / "matrix_cited_vintage.csv")
    m = m[(m.direction == direction) & (m.cited_dual == 0) & m.citing_year.between(*period)]
    s = m.groupby("cited_year").n.sum()
    return 100 * s / s.sum()


def figure_vintage() -> None:
    summ = pd.read_csv(V / "vintage_summary.csv")
    summ = summ[
        (summ.cited_set == "exclusive")
        & (summ.citing_def == "all")
        & (summ.classifier == "extended")
    ]
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.4), gridspec_kw={"width_ratios": [1, 1, 0.9]})
    for ax, direction, colour, title in (
        (axes[0], "ai_to_neuro", TEAL, "A  ·  AI papers citing neuroscience"),
        (axes[1], "neuro_to_ai", GOLD, "B  ·  Neuroscience papers citing AI"),
    ):
        for period, ls, lw in (((2010, 2019), (0, (4, 2)), 1.8), ((2020, 2025), "-", 2.4)):
            d = cited_year_distribution(direction, period)
            ax.plot(d.index, d.values, color=colour, ls=ls, lw=lw)
            label = f"{period[0]}-{period[1]}"
            med = summ[
                (summ.direction == direction) & (summ.period == label)
            ].median_cited_year.iloc[0]
            ax.axvline(med, color=colour, ls=ls, lw=1.0, alpha=0.8)
        ax.axvline(2005.5, color=GRAY, lw=0.8, ls=":")
        ax.set_xlim(1990, 2025)
        ax.set_xlabel("publication year of the cited work")
        ax.set_title(title, fontsize=12)
        ax.legend(
            handles=[
                Line2D(
                    [], [], color=colour, lw=1.8, ls=(0, (4, 2)), label="citing papers of 2010–2019"
                ),
                Line2D([], [], color=colour, lw=2.4, label="citing papers of 2020–2025"),
                Line2D([], [], color=GRAY, lw=0.8, ls=":", label="2005 boundary"),
            ],
            loc="upper left",
            fontsize=8.5,
        )
        for period in ("2010-2019", "2020-2025"):
            med = summ[
                (summ.direction == direction) & (summ.period == period)
            ].median_cited_year.iloc[0]
            ax.text(
                med,
                0.03,
                f"median {int(med)}",
                transform=ax.get_xaxis_transform(),
                rotation=90,
                ha="right",
                va="bottom",
                fontsize=8,
                color=colour,
            )
    axes[0].set_ylabel("share of citations (%)")

    by = pd.read_csv(V / "vintage_by_year.csv")
    by = by[(by.cited_set == "exclusive") & by.citing_year.between(2000, 2025)]
    ax = axes[2]
    for direction, colour in (("ai_to_neuro", TEAL), ("neuro_to_ai", GOLD)):
        s = by[by.direction == direction].sort_values("citing_year")
        ax.plot(s.citing_year, s.median_cited_year, color=colour, lw=2.2)
    _band(ax)
    ax.set_xlim(2000, 2025.5)
    ax.set_xlabel("year of the citing paper")
    ax.set_ylabel("median publication year of cited work")
    ax.set_title("C  ·  Median cited year by citing year", fontsize=12)
    ax.legend(
        handles=[
            Line2D([], [], color=TEAL, lw=2.2, label="AI citing neuroscience"),
            Line2D([], [], color=GOLD, lw=2.2, label="Neuroscience citing AI"),
        ],
        loc="upper left",
        fontsize=8.5,
    )
    finalize(
        fig,
        title="How old is the work each field cites in the other",
        subtitle="Exclusive cited sets, extended AI definition, every work type; hatched: provisional.",
        source=SOURCE
        + " Data: results/vintage/matrix_cited_vintage.csv, vintage_summary.csv, vintage_by_year.csv.",
        byline="R. Duarte",
        subtitle_y=0.93,
    )
    fig.subplots_adjust(top=0.80, bottom=0.14, left=0.05, right=0.98, wspace=0.22)
    _save(fig, "figure_s4_vintage")


# ---------------------------------------------------------------------------
# The six NeuroAI papers
# ---------------------------------------------------------------------------

PAPER_ORDER = [
    "Hassabis 2017",
    "Richards 2019",
    "Sinz 2019",
    "Lillicrap 2020",
    "Macpherson 2021",
    "Zador 2023",
]
PAPER_COLORS = dict(
    zip(
        PAPER_ORDER,
        [
            TEAL,
            TRANSMITTER["navy"],
            TRANSMITTER["muted"],
            GOLD,
            TRANSMITTER["coral"],
            TRANSMITTER["purple"],
        ],
        strict=True,
    )
)


def figure_manifestos() -> None:
    c = pd.read_csv(M / "citations_by_paper_year_field.csv")
    c = c[(c.citing_cls == "ai") & c.citing_year.between(2015, 2025)]
    p = c.pivot_table(index="citing_year", columns="short", values="n", aggfunc="sum").fillna(0)
    p = p[PAPER_ORDER]
    sh = pd.read_csv(M / "share_of_flow_by_year.csv").set_index("year").loc[2015:2025]

    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.4))
    ax = axes[0]
    bottom = np.zeros(len(p))
    for paper in PAPER_ORDER:
        ax.bar(
            p.index,
            p[paper].values,
            bottom=bottom,
            color=PAPER_COLORS[paper],
            width=0.75,
            label=paper,
        )
        bottom += p[paper].values
    _band(ax)
    ax.set_xlim(2014.5, 2025.5)
    ax.set_ylim(0, 290)
    ax.set_xlabel("year of the citing AI paper")
    ax.set_ylabel("citations from AI papers")
    ax.set_title("A  ·  Citations of the six papers from AI papers", fontsize=12)
    ax.legend(loc="upper left", fontsize=8.5, ncol=2)

    ax = axes[1]
    ax.plot(sh.index, 100 * sh.share_of_ai_to_neuro_all_six, color=TEAL, lw=2.4, marker="o", ms=4)
    _band(ax)
    ax.set_xlim(2014.5, 2025.5)
    ax.set_ylim(0, 0.4)
    ax.set_xlabel("year of the citing AI paper")
    ax.set_ylabel("share of all AI-to-neuroscience citations (%)")
    ax.set_title("B  ·  As a share of the AI-to-neuroscience flow", fontsize=12)
    ax2 = ax.twinx()
    ax2.plot(sh.index, sh.flow_ai_to_neuro_edges / 1000, color=GRAY, lw=1.6, ls=(0, (4, 2)))
    ax2.set_ylim(0, 110)
    ax2.set_ylabel("all AI-to-neuroscience citations (thousands)", color=GRAY)
    ax2.grid(False)
    ax.legend(
        handles=[
            Line2D(
                [], [], color=TEAL, lw=2.4, marker="o", ms=4, label="share held by the six (left)"
            ),
            Line2D(
                [],
                [],
                color=GRAY,
                lw=1.6,
                ls=(0, (4, 2)),
                label="all AI-to-neuroscience citations (right)",
            ),
        ],
        loc="upper left",
        fontsize=8.5,
    )
    finalize(
        fig,
        title="Citations of the six NeuroAI review papers",
        subtitle="Citing papers labelled AI by the extended definition; hatched: 2024–25 provisional.",
        source=SOURCE
        + " Data: results/manifestos/citations_by_paper_year_field.csv, share_of_flow_by_year.csv.",
        byline="R. Duarte",
        subtitle_y=0.93,
    )
    fig.subplots_adjust(top=0.80, bottom=0.14, left=0.07, right=0.93, wspace=0.30)
    _save(fig, "figure_s4_manifestos")


# ---------------------------------------------------------------------------
# Reference age
# ---------------------------------------------------------------------------


def reference_age_distribution(field: str, years: tuple[int, int] = (2020, 2023)) -> pd.Series:
    m = pd.read_csv(V / "matrix_reference_age.csv")
    m = m[(m.citing_cls == field) & (m.ar == 1) & m.citing_year.between(*years)]
    age = m.citing_year - m.cited_year
    s = m.assign(age=age)[age >= 0].groupby("age").n.sum()
    return 100 * s / s.sum()


def figure_reference_age() -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.4))
    pooled = pd.read_csv(V / "reference_age_pooled.csv")
    pooled = pooled[
        (pooled.types == "article_review")
        & (pooled.scope == "all_references")
        & (pooled.period == "2020-2023")
    ].set_index("citing_field")
    ax = axes[0]
    for field, colour, label, y_lab in (
        ("ai", TEAL, "AI papers", 0.96),
        ("neuro", GOLD, "Neuroscience papers", 0.88),
    ):
        d = reference_age_distribution(field)
        d = d.loc[:33]
        ax.plot(d.index, d.values, color=colour, lw=2.2, label=label)
        med = pooled.loc[field, "median_age"]
        ax.axvline(med, color=colour, lw=1.0, ls=(0, (4, 2)))
        ax.text(
            med + 0.4,
            y_lab,
            f"median {int(med)}",
            transform=ax.get_xaxis_transform(),
            fontsize=8.5,
            color=colour,
            va="top",
        )
    ax.set_xlim(0, 33)
    ax.set_xlabel("age of the cited work (citing year minus cited year)")
    ax.set_ylabel("share of references (%)")
    ax.set_title("A  ·  Reference age, 2020–2023", fontsize=12)
    ax.legend(loc="center right", fontsize=8.5)

    by = pd.read_csv(V / "reference_age_by_field.csv")
    by = by[(by.types == "article_review") & (by.scope == "all_references")]
    ax = axes[1]
    for field, colour in (("ai", TEAL), ("neuro", GOLD)):
        s = by[by.citing_field == field].sort_values("citing_year")
        ax.plot(s.citing_year, s.median_age, color=colour, lw=2.2)
        ax.plot(s.citing_year, s.p90_age, color=colour, lw=1.4, ls=(0, (4, 2)))
    _band(ax)
    ax.set_xlim(2000, 2025.5)
    ax.set_ylim(0, 25)
    ax.set_xlabel("year of the citing paper")
    ax.set_ylabel("reference age (years)")
    ax.set_title("B  ·  Median and 90th percentile by year", fontsize=12)
    ax.legend(
        handles=[
            Line2D([], [], color=TEAL, lw=2.2, label="AI, median"),
            Line2D([], [], color=GOLD, lw=2.2, label="Neuroscience, median"),
            Line2D([], [], color=GRAY, lw=1.4, ls=(0, (4, 2)), label="90th percentile"),
        ],
        loc="upper left",
        fontsize=8.5,
    )

    cov = pd.read_csv(V / "reference_list_coverage.csv")
    ax = axes[2]
    for field, colour in (("ai", TEAL), ("neuro", GOLD)):
        for types, ls in (("all", "-"), ("article_review", (0, (4, 2)))):
            s = cov[(cov.citing_field == field) & (cov.types == types)].sort_values("citing_year")
            ax.plot(s.citing_year, 100 * s.share_with_reflist, color=colour, lw=2.0, ls=ls)
    _band(ax)
    ax.set_xlim(2000, 2025.5)
    ax.set_ylim(0, 100)
    ax.set_xlabel("year of the citing paper")
    ax.set_ylabel("papers with any reference list (%)")
    ax.set_title("C  ·  Coverage of reference lists", fontsize=12)
    ax.legend(
        handles=[
            Line2D([], [], color=TEAL, lw=2.0, label="AI"),
            Line2D([], [], color=GOLD, lw=2.0, label="Neuroscience"),
            Line2D([], [], color=GRAY, lw=2.0, label="every work type"),
            Line2D([], [], color=GRAY, lw=2.0, ls=(0, (4, 2)), label="articles and reviews"),
        ],
        loc="lower left",
        fontsize=8.5,
    )
    finalize(
        fig,
        title="How far back each field's references reach",
        subtitle="All references that resolve to a dated work in the mirror; hatched: provisional.",
        source=SOURCE
        + " Data: results/vintage/matrix_reference_age.csv, reference_age_by_field.csv, reference_list_coverage.csv.",
        byline="R. Duarte",
        subtitle_y=0.93,
    )
    fig.subplots_adjust(top=0.80, bottom=0.14, left=0.05, right=0.98, wspace=0.24)
    _save(fig, "figure_s4_reference_age")


def build() -> None:
    apply_style()
    figure_composition()
    figure_vintage()
    figure_manifestos()
    figure_reference_age()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    build()

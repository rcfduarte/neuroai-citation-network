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
  article sidebar, per year and paper; B, those citations as a share of all citations of
  neuroscience by AI papers. Data: ``results/manifestos/citations_by_paper_year_field.csv``,
  ``share_of_flow_by_year.csv``.
* ``figure_s4_reference_age``: A, distribution of reference age for AI and neuroscience articles
  and reviews of 2020-2023; B, median reference age by citing year; C, share of papers with any
  reference list. Data: ``matrix_reference_age.csv``, ``reference_age_by_field.csv``,
  ``reference_list_coverage.csv``.

Run ``python -m neuroai_cn.figures.figure_s4``; writes PNG and SVG to ``figures/``.
"""

from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from .. import config
from .style import DIRECTION_COLORS, TRANSMITTER, apply_style, finalize

logger = logging.getLogger(__name__)
V = config.RESULTS_DIR / "vintage"
M = config.RESULTS_DIR / "manifestos"
F = config.RESULTS_DIR / "flow"
FIG_DIR = config.FIGURES_DIR
TEAL, GOLD = DIRECTION_COLORS["ai_to_neuro"], DIRECTION_COLORS["neuro_to_ai"]
NAVY, GRAY = TRANSMITTER["navy"], TRANSMITTER["gray"]
LAST_SOLID = 2023
SOURCE = "OpenAlex snapshot of 30 March 2026."

# Gold and teal are reserved for the two citation flows, so categories use other colors.
SUBFIELD_GROUPS = {
    "Cognitive Neuroscience": ("Cognitive neuroscience", NAVY),
    "Cellular and Molecular Neuroscience": ("Cellular and molecular", TRANSMITTER["coral"]),
    "Neurology": ("Neurology", TRANSMITTER["purple"]),
}
OTHER_SUBFIELDS = ("Five other subfields", TRANSMITTER["muted"])


CAT_ORDER = [
    "Foundational deep learning and AI",
    "Neuroimaging and medical image processing",
    "General statistics and ML software",
    "Computer vision applications",
    "Brain-adjacent modelling",
    "Off-topic or misclassified",
]
CAT_LABELS = {
    c: c.replace("modelling", "modeling").replace("ML software", "machine-learning software")
    for c in CAT_ORDER
}
CAT_COLORS = dict(
    zip(
        CAT_ORDER,
        [
            NAVY,
            TRANSMITTER["purple"],
            TRANSMITTER["coral"],
            "#8FB3D9",
            "#B79BD1",
            TRANSMITTER["muted"],
        ],
        strict=True,
    )
)


def _band(ax, x_max: int = 2025, over: bool = False) -> None:
    """Mark the provisional years 2024-25.

    ``over=True`` draws a light wash and a hatch above filled areas (stacked areas would hide a
    band drawn beneath them) and a dashed boundary at the last solid year.
    """
    if over:
        ax.axvspan(
            LAST_SOLID + 0.5,
            x_max + 0.5,
            facecolor=(1, 1, 1, 0.45),
            edgecolor=(0.35, 0.38, 0.45, 0.85),
            hatch="///",
            linewidth=0,
            zorder=5,
        )
        ax.axvline(LAST_SOLID + 0.5, color="white", lw=1.6, ls="--", zorder=6)
        return
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
    """Share of citations of neuroscience by AI papers per citing year, by group of cited subfield (%).

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
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 10.6))
    (ax_a, ax_b), (ax_c, ax_d) = axes

    p = ai_citing_neuro_by_subfield("exclusive", core_only=True).loc[1995:2025]
    cols = [SUBFIELD_GROUPS[c][1] for c in SUBFIELD_GROUPS] + [OTHER_SUBFIELDS[1]]
    ax_a.stackplot(p.index, p.T.values, colors=cols, edgecolor="white", linewidth=0.4)
    _band(ax_a, over=True)
    ax_a.set_xlim(1995, 2025.5)
    ax_a.set_ylim(0, 100)
    ax_a.set_ylabel("share of citations (%)")
    ax_a.set_title(
        "A  AI papers citing neuroscience\n(35-topic core), by cited subfield", fontsize=11.5
    )

    s = pd.read_csv(V / "subfield_breakdown.csv")
    s = s[(s.direction == "ai_to_neuro") & (s.citing_def == "all") & (s.period == "2020-2025")]
    cells = [
        ("strict35", "exclusive", "35-topic core,\nexclusive set"),
        ("strict35", "unrestricted", "35-topic core,\nall-neuroscience set"),
        ("extended", "exclusive", "extended,\nexclusive set"),
    ]
    x = np.arange(len(cells))
    for off, sf, colour in (
        (-0.2, "Cognitive Neuroscience", NAVY),
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
            ax_b.text(
                xi,
                v + 1.2,
                f"{v:.2f}" if v < 50 else f"{v:.1f}",
                ha="center",
                va="bottom",
                fontsize=10,
                color=NAVY,
            )
    ax_b.axhline(90, color=GRAY, lw=0.9, ls=":")
    ax_b.axhline(5, color=GRAY, lw=0.9, ls=":")
    ax_b.set_xticks(x, [c[2] for c in cells], fontsize=10)
    ax_b.set_xlim(-0.6, 2.6)
    ax_b.set_ylim(0, 105)
    ax_b.set_ylabel("share of citations (%)")
    ax_b.set_title(
        "B  Cognitive and cellular-molecular\nshares, citing years 2020–2025", fontsize=11.5
    )

    for ax, classifier, title in (
        (
            ax_c,
            "extended",
            "C  Neuroscience papers citing AI\n(extended definition), by AI category",
        ),
        (ax_d, "strict", "D  Neuroscience papers citing AI\n(35-topic core), by AI category"),
    ):
        q = neuro_citing_ai_by_category(classifier)
        ax.stackplot(
            q.index,
            q.T.values,
            colors=[CAT_COLORS[c] for c in CAT_ORDER],
            edgecolor="white",
            linewidth=0.4,
        )
        _band(ax, over=True)
        ax.set_xlim(1995, 2025.5)
        ax.set_ylim(0, 100)
        ax.set_ylabel("share of citations (%)")
        ax.set_title(title, fontsize=11.5)
    for ax in (ax_a, ax_c, ax_d):
        ax.set_xlabel("year of the citing paper")
    leg_a = fig.legend(
        handles=[
            Patch(color=SUBFIELD_GROUPS[c][1], label=SUBFIELD_GROUPS[c][0]) for c in SUBFIELD_GROUPS
        ]
        + [Patch(color=OTHER_SUBFIELDS[1], label=OTHER_SUBFIELDS[0])],
        title="A and B: subfield of the cited neuroscience",
        loc="upper left",
        ncol=1,
        fontsize=10,
        title_fontsize=10,
        bbox_to_anchor=(0.04, 0.195),
        frameon=False,
        alignment="left",
    )
    fig.add_artist(leg_a)
    fig.legend(
        handles=[Patch(color=CAT_COLORS[c], label=CAT_LABELS[c]) for c in CAT_ORDER],
        title="C and D: category of the cited AI topic",
        loc="upper left",
        ncol=1,
        fontsize=10,
        title_fontsize=10,
        bbox_to_anchor=(0.45, 0.195),
        frameon=False,
        alignment="left",
    )
    finalize(
        fig,
        title="What each field cites when it cites the other",
        subtitle="Hatched, right of the dashed line: 2024–25 provisional. Same colors mean different things in A, B and C, D.",
        source=SOURCE,
        byline="R. Duarte",
        subtitle_y=0.962,
    )
    fig.subplots_adjust(top=0.875, bottom=0.235, left=0.08, right=0.98, hspace=0.50, wspace=0.26)
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
    fig = plt.figure(figsize=(10.5, 9.6))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 0.85], hspace=0.42, wspace=0.22)
    axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, :])]
    for ax, direction, colour, title in (
        (axes[0], "ai_to_neuro", TEAL, "A  AI papers citing\nneuroscience"),
        (axes[1], "neuro_to_ai", GOLD, "B  Neuroscience papers\nciting AI"),
    ):
        handles = []
        for period, ls, lw in (((2010, 2019), (0, (4, 2)), 2.0), ((2020, 2025), "-", 2.6)):
            d = cited_year_distribution(direction, period)
            ax.plot(d.index, d.values, color=colour, ls=ls, lw=lw)
            label = f"{period[0]}-{period[1]}"
            med = int(
                summ[(summ.direction == direction) & (summ.period == label)].median_cited_year.iloc[
                    0
                ]
            )
            ax.axvline(med, ymax=0.76, color=colour, ls=ls, lw=1.0, alpha=0.8)
            handles.append(
                Line2D([], [], color=colour, lw=lw, ls=ls, label=f"citing {label}: median {med}")
            )
        ax.axvline(2005.5, ymax=0.76, color=GRAY, lw=0.8, ls=":")
        handles.append(Line2D([], [], color=GRAY, lw=0.8, ls=":", label="2005 boundary"))
        ax.legend(handles=handles, loc="upper left", fontsize=10, frameon=False)
        ax.set_xlim(1990, 2025)
        ax.set_ylim(0, 11)
        ax.set_yticks(range(0, 9, 2))
        ax.set_xlabel("publication year of the cited work")
        ax.set_title(title, fontsize=11.5)
    axes[0].set_ylabel("share of citations (%)")

    by = pd.read_csv(V / "vintage_by_year.csv")
    by = by[(by.cited_set == "exclusive") & by.citing_year.between(2000, 2025)]
    ax = axes[2]
    for direction, colour in (("ai_to_neuro", TEAL), ("neuro_to_ai", GOLD)):
        s = by[by.direction == direction].sort_values("citing_year")
        ax.plot(s.citing_year, s.median_cited_year, color=colour, lw=2.6)
    _band(ax)
    ax.set_xlim(2000, 2025.5)
    ax.set_xlabel("year of the citing paper")
    ax.set_ylabel("median publication year\nof the cited work")
    ax.set_title("C  Median cited year by citing year", fontsize=11.5)
    ax.legend(
        handles=[
            Line2D([], [], color=TEAL, lw=2.6, label="AI papers citing neuroscience"),
            Line2D([], [], color=GOLD, lw=2.6, label="Neuroscience papers citing AI"),
        ],
        loc="upper left",
        fontsize=10.5,
        frameon=False,
    )
    finalize(
        fig,
        title="How old is the work each field cites in the other",
        subtitle="Exclusive cited sets, extended definition, every work type. Hatched in C: 2024–25 provisional.",
        source=SOURCE,
        byline="R. Duarte",
        subtitle_y=0.955,
    )
    fig.subplots_adjust(top=0.86, bottom=0.07, left=0.08, right=0.98)
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
            NAVY,
            TRANSMITTER["coral"],
            TRANSMITTER["muted"],
            TRANSMITTER["purple"],
            "#8FB3D9",
            "#7FA05B",
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

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.4))
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
    ax.set_title("A  Citations of the six papers\nby AI papers", fontsize=11.5)
    ax.legend(loc="upper left", fontsize=10, ncol=2, frameon=False)

    ax = axes[1]
    ax.plot(sh.index, 100 * sh.share_of_ai_to_neuro_all_six, color=NAVY, lw=2.4, marker="o", ms=4)
    _band(ax)
    ax.set_xlim(2014.5, 2025.5)
    ax.set_ylim(0, 0.45)
    ax.set_xlabel("year of the citing AI paper")
    ax.set_ylabel("share of AI papers' citations\nof neuroscience (%)")
    ax.set_title("B  The six as a share of AI papers'\ncitations of neuroscience", fontsize=11.5)
    ax2 = ax.twinx()
    ax2.plot(sh.index, sh.flow_ai_to_neuro_edges / 1000, color=TEAL, lw=1.8, ls=(0, (4, 2)))
    ax2.set_ylim(0, 110)
    ax2.set_ylabel("all citations of neuroscience\nby AI papers (thousands)", color=TEAL)
    ax2.grid(False)
    ax.legend(
        handles=[
            Line2D(
                [], [], color=NAVY, lw=2.4, marker="o", ms=4, label="share held by the six (left)"
            ),
            Line2D(
                [],
                [],
                color=TEAL,
                lw=1.8,
                ls=(0, (4, 2)),
                label="AI papers citing neuroscience, all (right)",
            ),
        ],
        loc="upper left",
        fontsize=10,
        frameon=False,
    )
    finalize(
        fig,
        title="Citations of the six NeuroAI review papers",
        subtitle="Citing papers are AI papers by the extended definition; hatched: 2024–25 provisional.",
        source=SOURCE,
        byline="R. Duarte",
        subtitle_y=0.93,
    )
    fig.subplots_adjust(top=0.78, bottom=0.14, left=0.08, right=0.90, wspace=0.42)
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
    fig = plt.figure(figsize=(10.5, 9.6))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 0.85], hspace=0.42, wspace=0.26)
    axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, :])]
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
        ax.plot(d.index, d.values, color=colour, lw=2.6, label=label)
        med = pooled.loc[field, "median_age"]
        ax.axvline(med, color=colour, lw=1.2, ls=(0, (4, 2)))
        ax.text(
            med + 0.5,
            y_lab,
            f"median {int(med)}",
            transform=ax.get_xaxis_transform(),
            fontsize=10.5,
            color=colour,
            va="top",
        )
    ax.set_xlim(0, 33)
    ax.set_xlabel("age of the cited work (years)")
    ax.set_ylabel("share of references (%)")
    ax.set_title("A  Reference age, 2020–2023", fontsize=11.5)
    ax.legend(loc="center right", fontsize=10.5, frameon=False)

    by = pd.read_csv(V / "reference_age_by_field.csv")
    by = by[(by.types == "article_review") & (by.scope == "all_references")]
    ax = axes[1]
    for field, colour in (("ai", TEAL), ("neuro", GOLD)):
        s = by[by.citing_field == field].sort_values("citing_year")
        ax.plot(s.citing_year, s.median_age, color=colour, lw=2.6)
        ax.plot(s.citing_year, s.p90_age, color=colour, lw=1.6, ls=(0, (4, 2)))
    _band(ax)
    ax.set_xlim(2000, 2025.5)
    ax.set_ylim(0, 31)
    ax.set_yticks(range(0, 26, 5))
    ax.set_xlabel("year of the citing paper")
    ax.set_ylabel("reference age (years)")
    ax.set_title("B  Median and 90th percentile\nby citing year", fontsize=11.5)
    ax.legend(
        handles=[
            Line2D([], [], color=TEAL, lw=2.6, label="AI papers, median"),
            Line2D([], [], color=GOLD, lw=2.6, label="Neuroscience papers, median"),
            Line2D([], [], color=GRAY, lw=1.6, ls=(0, (4, 2)), label="90th percentile (dashed)"),
        ],
        loc="upper left",
        fontsize=10,
        frameon=False,
    )

    cov = pd.read_csv(V / "reference_list_coverage.csv")
    ax = axes[2]
    for field, colour in (("ai", TEAL), ("neuro", GOLD)):
        for types, ls in (("all", "-"), ("article_review", (0, (4, 2)))):
            s = cov[(cov.citing_field == field) & (cov.types == types)].sort_values("citing_year")
            ax.plot(s.citing_year, 100 * s.share_with_reflist, color=colour, lw=2.4, ls=ls)
    _band(ax)
    ax.set_xlim(2000, 2025.5)
    ax.set_ylim(0, 100)
    ax.set_xlabel("year of the citing paper")
    ax.set_ylabel("papers with any\nreference list (%)")
    ax.set_title("C  Coverage of reference lists", fontsize=11.5)
    ax.legend(
        handles=[
            Line2D([], [], color=TEAL, lw=2.4, label="AI papers"),
            Line2D([], [], color=GOLD, lw=2.4, label="Neuroscience papers"),
            Line2D([], [], color=GRAY, lw=2.4, label="every work type (solid)"),
            Line2D(
                [], [], color=GRAY, lw=2.4, ls=(0, (4, 2)), label="articles and reviews (dashed)"
            ),
        ],
        loc="lower left",
        fontsize=10.5,
        ncol=2,
        frameon=False,
    )
    finalize(
        fig,
        title="How far back each field's references reach",
        subtitle="All references that resolve to a dated work in the snapshot. Hatched: 2024–25 provisional.",
        source=SOURCE,
        byline="R. Duarte",
        subtitle_y=0.955,
    )
    fig.subplots_adjust(top=0.86, bottom=0.07, left=0.08, right=0.98)
    _save(fig, "figure_s4_reference_age")


def build() -> None:
    apply_style()
    # Larger type than the house default, so that the figures stay legible at 800 px width.
    plt.rcParams.update(
        {
            "font.size": 12,
            "axes.labelsize": 12,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
        }
    )
    figure_composition()
    figure_vintage()
    figure_manifestos()
    figure_reference_age()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    build()

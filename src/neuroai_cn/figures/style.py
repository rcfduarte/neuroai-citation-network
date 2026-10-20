"""Transmitter house-style for figures.

Centralised palette + matplotlib rcParams replicating The Transmitter's
data-visualization conventions (cream background, teal+mustard 2-category
encoding, no spines, horizontal gridlines only, bold left-aligned titles,
italic source line below the chart).

Palette extracted from production CSS at
`stateofneuroscience.thetransmitter.org/_app/immutable/assets/0.BxYzz2Ml.css`
and visually verified from "By the Numbers" 2022 chart PNGs.

Reference: ``Assets/claude/outputs/research/transmitter-figure-style-spec-20260522.md``

Usage:
    from neuroai_cn.figures.style import TRANSMITTER, apply_style, finalize
    apply_style()
    fig, ax = plt.subplots()
    ...
    finalize(fig, title="Headline takeaway",
             source="OpenAlex snapshot 2026-03-30; n=458M works",
             byline="Renato Duarte // The Transmitter")
"""

from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

TRANSMITTER: dict[str, str] = {
    "bg": "#FFFFFF",  # background (kept WHITE per user preference 2026-05-22; the
    # Transmitter's native cream #FBF5E9 is reserved for editorial
    # publication; switch back via finalize_for_publication())
    "cream": "#FBF5E9",  # editorial cream — kept available for the published version
    "navy": "#0F3047",  # body text + spines + dark accents
    "teal": "#277E8A",  # primary categorical (AI -> Neuro in our piece)
    "mustard": "#D4A521",  # secondary categorical (Neuro -> AI)
    "coral": "#FD6760",  # highlight overlay
    "crimson": "#DC143C",  # trend / change-point / inflection
    "purple": "#59278A",  # tertiary categorical (rarely needed)
    "gray": "#6A7282",  # axis tick labels, secondary text
    "grid": "#E5E7EB",  # horizontal gridlines
    "muted": "#9C978D",  # connecting / annotation leader lines
}

# Directional convention for the NeuroAI piece
DIRECTION_COLORS: dict[str, str] = {
    "ai_to_neuro": TRANSMITTER["teal"],
    "neuro_to_ai": TRANSMITTER["mustard"],
}
DIRECTION_LABELS: dict[str, str] = {
    "ai_to_neuro": "AI → Neuro",  # AI → Neuro
    "neuro_to_ai": "Neuro → AI",  # Neuro → AI
}
# DEPRECATED — uses the citation-link convention (X→Y = X cites Y). Kept for the
# original figure1_main.py and any pre-2026-05-28 supplementaries. Any NEW figure
# (including figure1_main_v2.py and onward) MUST use DISPLAY_LABELS_INFLUENCE
# below, which uses the intellectual-influence convention (X→Y = X influences Y).

DISPLAY_LABELS_INFLUENCE: dict[str, str] = {
    # Data 'direction' value -> display label under the new (influence) convention.
    # Data column 'neuro_to_ai' means "neuroscience papers cite AI papers" (rising,
    # headline); under influence convention this is "AI -> Neuro" (AI influences
    # neuroscience).
    # Data column 'ai_to_neuro' means "AI papers cite neuroscience papers" (flat);
    # under influence convention this is "Neuro -> AI" (neuroscience influences AI).
    # Capital N on "Neuro" per user style preference.
    "neuro_to_ai": "AI → Neuro",
    "ai_to_neuro": "Neuro → AI",
}

# Editor's request (2026-08-31, comment [186]): "I still think the
# label AI->neuroscience is ambiguous... For figures, the reader should understand
# immediately what it shows rather than having to interpret it." These say what is
# counted, so no arrow convention has to be learned at all. Use these on anything
# that goes to the outlet.
#
# ⚠ The comment on DISPLAY_LABELS_INFLUENCE above states which series is rising and
# has it BACKWARDS. Measured on q1_or_by_year.parquet: `ai_to_neuro` (AI papers
# citing neuroscience) is the steep one, OR 0.0137 (1995) -> 0.0527 (2025);
# `neuro_to_ai` (neuroscience papers citing AI) is flat in OR, 0.0331 -> 0.0208,
# and only rises in raw counts. Corrected 2026-09-14.
DISPLAY_LABELS_PLAIN: dict[str, str] = {
    "ai_to_neuro": "AI papers citing neuroscience",
    "neuro_to_ai": "Neuroscience papers citing AI",
}

# Era shading: (face_color, alpha) — kept very subtle on cream background.
ERA_SHADING: dict[str, tuple[str, float]] = {
    "Pre-DL": ("#000000", 0.03),
    "DL emergence": ("#000000", 0.06),
    "DL expansion": ("#000000", 0.09),
    "NeuroAI era": (TRANSMITTER["teal"], 0.10),
}

# Change-point line style
CP_STYLE: dict[str, object] = {
    "color": TRANSMITTER["crimson"],
    "linestyle": "--",
    "linewidth": 1.2,
    "alpha": 0.75,
}

# ---------------------------------------------------------------------------
# rcParams
# ---------------------------------------------------------------------------


def apply_style() -> None:
    """Install the Transmitter house style as matplotlib defaults.

    Call once at the top of any figure-building script. Idempotent.
    """
    mpl.rcParams.update(
        {
            # Fonts ---------------------------------------------------------------
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Inter",
                "Source Sans 3",
                "Source Sans Pro",
                "Helvetica Neue",
                "Arial",
                "DejaVu Sans",
            ],
            "font.size": 10,
            "axes.titlesize": 14,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.titlepad": 12,
            "axes.titlecolor": TRANSMITTER["navy"],
            "axes.labelsize": 10.5,
            "axes.labelcolor": TRANSMITTER["navy"],
            "axes.labelweight": "regular",
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "xtick.color": TRANSMITTER["gray"],
            "ytick.color": TRANSMITTER["gray"],
            "legend.fontsize": 9.5,
            "legend.frameon": False,
            "legend.loc": "upper left",
            "legend.handlelength": 1.4,
            "legend.handleheight": 1.0,
            "legend.borderaxespad": 0.0,
            # Spines: bottom only -------------------------------------------------
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.spines.left": False,
            "axes.spines.bottom": True,
            "axes.edgecolor": TRANSMITTER["navy"],
            "axes.linewidth": 0.8,
            # Ticks: labels visible, marks hidden ---------------------------------
            "xtick.major.size": 0,
            "ytick.major.size": 0,
            "xtick.minor.size": 0,
            "ytick.minor.size": 0,
            "xtick.major.pad": 4,
            "ytick.major.pad": 4,
            # Grid: horizontals only ---------------------------------------------
            "axes.grid": True,
            "axes.grid.axis": "y",
            "grid.color": TRANSMITTER["grid"],
            "grid.linewidth": 0.6,
            "grid.linestyle": "-",
            "axes.axisbelow": True,
            # Background: warm cream throughout -----------------------------------
            "figure.facecolor": TRANSMITTER["bg"],
            "axes.facecolor": TRANSMITTER["bg"],
            "savefig.facecolor": TRANSMITTER["bg"],
            "savefig.edgecolor": TRANSMITTER["bg"],
            # Figure --------------------------------------------------------------
            "figure.figsize": (8.4, 5.2),  # ~840px @ 100 dpi, matches Transmitter native width
            "figure.dpi": 110,
            "savefig.dpi": 200,
            "savefig.bbox": "tight",
            # Lines ---------------------------------------------------------------
            "lines.linewidth": 2.0,
            "lines.solid_capstyle": "round",
            "lines.solid_joinstyle": "round",
            "patch.linewidth": 0,
            # Color cycle ---------------------------------------------------------
            "axes.prop_cycle": mpl.cycler(
                color=[
                    TRANSMITTER["teal"],
                    TRANSMITTER["mustard"],
                    TRANSMITTER["coral"],
                    TRANSMITTER["purple"],
                    TRANSMITTER["navy"],
                    TRANSMITTER["gray"],
                ]
            ),
        }
    )


# ---------------------------------------------------------------------------
# Caption + source helpers
# ---------------------------------------------------------------------------


def finalize(
    fig: plt.Figure,
    *,
    title: str | None = None,
    subtitle: str | None = None,
    source: str | None = None,
    byline: str | None = None,
    x_title: float = 0.0,
    y_title_offset: float = 0.0,
    subtitle_y: float = 0.94,
) -> None:
    """Apply Transmitter-style title / subtitle / source line / byline.

    Parameters
    ----------
    fig : Figure
    title : bold left-aligned headline above the plot (single sentence)
    subtitle : regular dek under the title (optional)
    source : italic source line under the chart
    byline : right-aligned attribution line at the bottom
    """
    if title:
        fig.suptitle(
            title,
            x=0.02 + x_title,
            y=0.99 + y_title_offset,
            ha="left",
            va="top",
            fontsize=15,
            fontweight="bold",
            color=TRANSMITTER["navy"],
        )
    if subtitle:
        fig.text(
            0.02,
            subtitle_y,
            subtitle,
            ha="left",
            va="top",
            fontsize=11,
            color=TRANSMITTER["gray"],
        )
    if source:
        # Wrap long source lines: split at 110 chars max so it can sit on two lines
        # without colliding with the byline at right.
        src_text = f"Source: {source}"
        fig.text(
            0.02,
            0.012,
            src_text,
            ha="left",
            va="bottom",
            fontsize=8.0,
            style="italic",
            color=TRANSMITTER["gray"],
            wrap=True,
        )
    if byline:
        fig.text(
            0.98,
            0.012,
            byline,
            ha="right",
            va="bottom",
            fontsize=8.0,
            color=TRANSMITTER["gray"],
        )


def add_era_shading(
    ax: plt.Axes,
    eras: list[tuple[str, int, int]] | None = None,
    *,
    label_eras: bool = True,
    label_y: float = 0.98,
) -> None:
    """Shade era windows on a time-axis with subtle gray bands + top labels.

    Parameters
    ----------
    ax : Axes
    eras : list of (label, year_start, year_end) inclusive
    label_eras : draw era labels at the top of the panel
    label_y : axes-fraction y position for era labels
    """
    if eras is None:
        eras = CANONICAL_ERAS
    for label, lo, hi in eras:
        face, alpha = ERA_SHADING.get(label, ("#000000", 0.05))
        ax.axvspan(lo, hi + 1, facecolor=face, alpha=alpha, edgecolor="none", zorder=0)
        if label_eras:
            mid = (lo + hi + 1) / 2.0
            ax.text(
                mid,
                label_y,
                label,
                transform=ax.get_xaxis_transform(),
                ha="center",
                va="bottom",
                fontsize=8.5,
                color=TRANSMITTER["gray"],
                alpha=0.9,
                clip_on=False,
            )


def add_changepoints(
    ax: plt.Axes,
    years: list[int],
    *,
    label: bool = True,
    label_y: float = 0.04,
    annotation: dict[int, str] | None = None,
) -> None:
    """Draw vertical dashed CP lines in crimson with optional year annotations."""
    annotation = annotation or {}
    for y in years:
        ax.axvline(y, **CP_STYLE, zorder=2)
        if label:
            txt = annotation.get(y, f"CP {y}")
            ax.text(
                y + 0.15,
                label_y,
                txt,
                transform=ax.get_xaxis_transform(),
                rotation=90,
                ha="left",
                va="bottom",
                fontsize=8.0,
                color=TRANSMITTER["crimson"],
                alpha=0.85,
            )


# ---------------------------------------------------------------------------
# Canonical era definitions (single source of truth across all figures)
# ---------------------------------------------------------------------------

# CANONICAL_ERAS is the locked four-era partition for the main figure.
# All era-OLS, bootstrap, and figure-shading code must use these exact
# boundaries. Alternates (BERT-to-GPT4, ChatGPT-era) belong to supplementaries.

CANONICAL_ERAS: list[tuple[str, int, int]] = [
    ("Pre-DL", 1990, 2011),
    ("DL emergence", 2012, 2015),
    ("DL expansion", 2016, 2019),
    ("NeuroAI era", 2020, 2025),
]

# Data-driven change-points from `q1_v3_extended_changepoints.parquet`
# (PELT/L2 optimal 2 breakpoints per direction).
CANONICAL_CHANGEPOINTS: dict[str, list[int]] = {
    "ai_to_neuro": [2005, 2022],
    "neuro_to_ai": [1993, 2005],
}

# Tier-1 canonical bridge papers (vertical markers for the headline panel).
TIER1_BRIDGES: dict[str, int] = {
    # Editor's request [185], 2026-08-31: "Is there a specific paper in 2011/2012
    # that marks the emergence of DL? If so, can you add it to the graph, similar
    # to Hassabis 2017". AlexNet is the canonical marker.
    "AlexNet 2012": 2012,
    "Hassabis 2017": 2017,
    "Kriegeskorte 2018": 2018,
    "Richards 2019": 2019,
    "GPT-3 2020": 2020,  # Brown et al. 2020; reviewer comment 4 (2026-09-26)
    "Zador 2023": 2023,
}

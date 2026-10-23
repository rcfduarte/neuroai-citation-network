"""Figure 2 v3 — Bridge papers · authors · institutions, single 3-column layout.

Spec (LOCKED 2026-05-22 evening):

    Three side-by-side bar columns with curves flowing both ways from the
    middle (authors) column:

        Papers (left)  ⟶  Authors (middle)  ⟶  Institutions (right)
                       ⟵                    ⟵

    Per-column:
        * Top 15 entities, ranked top-to-bottom
        * Horizontal bars sized by metric (B-harmonic / ∑ B-harmonic)
        * x-axis at bottom of each column shows the metric scale
        * Bars colored by neuro_share gradient (teal -> mustard)

    Authors column specifics:
        * Author name rendered INSIDE the bar in white
          (with a dark navy stroke for legibility on lighter mid-gradient fills)
        * Bars grow rightward from a fixed left anchor

    Edges:
        * Paper -> Author: curves from paper bar's right edge to author bar's left edge.
          Edge weight: last_author = 2.0, first_author = 1.5, middle = 1.0.
        * Author -> Institution: curves from author bar's right edge to inst
          bar's left edge. Uses CURRENT affiliations only
          (`author_institution_edges.csv`). Edge weight = 1.0 (single
          current affiliation per author-institution pair); only drawn when
          the institution is in the top-15 set.

Data sources (results/bridge/, written by ``python -m neuroai_cn.analysis.export_bridge_tables``):
    table_s1_papers.csv                       top-15 papers (with venue)
    table_s2_authors.csv                      top-15 authors
    table_s3_institutions_consolidated.csv    top-15 institutions, corporate groups merged
    table_s3b_institutions_separated.csv      top-15 institutions as OpenAlex ships them
    paper_author_links.csv                    paper->author edges with authorship position
    author_institution_edges.csv              hand-verified author->institution edges (current/past)

Output (config.FIGURES_DIR):
    figure2_v3.{png,svg}
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib as mpl
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from .. import config
from .style import (
    TRANSMITTER,
    apply_style,
    finalize,
)

logger = logging.getLogger(__name__)

BRIDGE_DIR = config.RESULTS_DIR / "bridge"
FIGURES_DIR = config.FIGURES_DIR
N = 15

# Authorship-position weighting per user 2026-05-22 decision.
POSITION_WEIGHT: dict[str, float] = {
    "last": 2.0,
    "first": 1.5,
    "middle": 1.0,
    "corresponding": 2.0,  # treat corresponding similar to last
}

NEUROSHARE_CMAP = LinearSegmentedColormap.from_list(
    "ai_to_neuro_gradient",
    [
        (0.00, TRANSMITTER["teal"]),
        (0.50, "#D9D2BD"),
        (1.00, TRANSMITTER["mustard"]),
    ],
    N=256,
)


# ---------------------------------------------------------------------------
# Layout constants (axes-data coordinates of the single big axes)
# ---------------------------------------------------------------------------

X_PAPERS_RIGHT = 0.30  # right edge of papers column (bars grow leftward)
X_PAPERS_BAR_MAX = 0.30  # max bar length

X_AUTHORS_LEFT = 0.42  # left edge of authors column
X_AUTHORS_BAR_MAX = 0.16  # max bar length (shorter, name-inside)

X_INSTS_LEFT = 0.70  # left edge of institutions column
X_INSTS_BAR_MAX = 0.30  # max bar length

Y_TOP = 0.95
Y_BOTTOM = 0.10
BAR_HEIGHT = (Y_TOP - Y_BOTTOM) / (N + 1) * 0.85  # slim but visible


def _truncate(s: str, n: int) -> str:
    s = str(s).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _color_for(neuro_share: float) -> str:
    return mpl.colors.to_hex(NEUROSHARE_CMAP(np.clip(neuro_share, 0, 1)))


def _is_light(hex_color: str) -> bool:
    """Heuristic: is this color light enough that white text would not work?"""
    rgb = mpl.colors.to_rgb(hex_color)
    lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    return lum > 0.55


# ---------------------------------------------------------------------------
# Bar + label drawing
# ---------------------------------------------------------------------------


def _draw_left_column_bars(
    ax: plt.Axes,
    df: pd.DataFrame,
    metric_col: str,
    label_col: str,
    label_max: int,
    max_metric: float,
    venues: dict[str, str] | None = None,
) -> dict[int, tuple[float, float]]:
    """Papers column — bars grow LEFT from X_PAPERS_RIGHT.

    Label format: "Title (year). Journal" rendered OUTSIDE the bar on the
    LEFT (since papers grow left, the open side is to the left). Two-line
    layout if the long-label wraps: first line = title (year), second line
    = journal in italics.
    """
    out = {}
    venues = venues or {}
    y_positions = np.linspace(Y_TOP, Y_BOTTOM, len(df))
    for (_, row), y in zip(df.iterrows(), y_positions, strict=True):
        rank = int(row["paper_rank"])
        v = float(row[metric_col])
        bar_len = X_PAPERS_BAR_MAX * (v / max_metric)
        x_outer = X_PAPERS_RIGHT - bar_len
        color = _color_for(row["neuro_share"])
        ax.add_patch(
            mpatches.Rectangle(
                (x_outer, y - BAR_HEIGHT / 2),
                bar_len,
                BAR_HEIGHT,
                facecolor=color,
                edgecolor=TRANSMITTER["navy"],
                linewidth=0.4,
                zorder=4,
            )
        )
        # Two-line label outside the bar to the left
        title_clean = str(row[label_col]).strip().replace("<b>", "").replace("</b>", "")
        try:
            yr = int(row.get("publication_year"))
            line1 = f"{_truncate(title_clean, label_max)} ({yr})"
        except (TypeError, ValueError):
            line1 = _truncate(title_clean, label_max)
        venue = venues.get(str(row.get("work_id", "")), "")
        ax.text(
            x_outer - 0.005,
            y + BAR_HEIGHT * 0.30,
            line1,
            ha="right",
            va="center",
            fontsize=8.5,
            color=TRANSMITTER["navy"],
            zorder=5,
        )
        if venue:
            ax.text(
                x_outer - 0.005,
                y - BAR_HEIGHT * 0.30,
                _truncate(venue, label_max),
                ha="right",
                va="center",
                fontsize=7.5,
                color=TRANSMITTER["gray"],
                style="italic",
                zorder=5,
            )
        out[rank] = (X_PAPERS_RIGHT, y)
    return out


def _draw_middle_column_bars(
    ax: plt.Axes,
    df: pd.DataFrame,
    metric_col: str,
    label_col: str,
    max_metric: float,
) -> tuple[dict[int, tuple[float, float, float]], dict[int, float]]:
    """Authors column — bars grow RIGHT from X_AUTHORS_LEFT. Label INSIDE the bar.

    Returns:
        - left_attach   {author_rank -> (x_left, y, _padding)} — curve endpoint
                        for paper->author edges (= X_AUTHORS_LEFT, fixed)
        - right_attach  {author_rank -> x_right} — bar right edge (variable),
                        endpoint for author->inst curves
    """
    left_attach: dict[int, tuple[float, float, float]] = {}
    right_attach: dict[int, float] = {}
    y_positions = np.linspace(Y_TOP, Y_BOTTOM, len(df))
    for (_, row), y in zip(df.iterrows(), y_positions, strict=True):
        rank = int(row["author_rank"])
        v = float(row[metric_col])
        bar_len = X_AUTHORS_BAR_MAX * (v / max_metric)
        # Ensure label fits: enforce a minimum visual length
        bar_len = max(bar_len, X_AUTHORS_BAR_MAX * 0.55)
        x_right = X_AUTHORS_LEFT + bar_len
        color = _color_for(row["neuro_share"])
        ax.add_patch(
            mpatches.Rectangle(
                (X_AUTHORS_LEFT, y - BAR_HEIGHT / 2),
                bar_len,
                BAR_HEIGHT,
                facecolor=color,
                edgecolor=TRANSMITTER["navy"],
                linewidth=0.4,
                zorder=4,
            )
        )
        # Label INSIDE the bar (centered)
        text_color = TRANSMITTER["navy"] if _is_light(color) else "white"
        ax.text(
            X_AUTHORS_LEFT + bar_len / 2,
            y,
            _truncate(row[label_col], 22),
            ha="center",
            va="center",
            fontsize=8.5,
            fontweight="bold",
            color=text_color,
            zorder=5,
        )
        left_attach[rank] = (X_AUTHORS_LEFT, y, 0.0)
        right_attach[rank] = x_right
    return left_attach, right_attach


INST_TYPE_BADGE: dict[str, tuple[str, str]] = {
    # type -> (short_label, hex_color)
    "education": ("EDU", TRANSMITTER["navy"]),
    "company": ("IND", TRANSMITTER["crimson"]),
    "facility": ("FAC", TRANSMITTER["purple"]),
    "government": ("GOV", TRANSMITTER["coral"]),
    "healthcare": ("HC", "#0F7A30"),
    "nonprofit": ("NP", TRANSMITTER["mustard"]),
    "funder": ("FUND", TRANSMITTER["gray"]),
    "other": ("OTH", TRANSMITTER["muted"]),
}


# Hand-curated initials for the top-15 institutions (covers both raw-OpenAlex
# and consolidated views). Anything not in the map falls back to the
# full-name display (truncated to fit).
INSTITUTION_INITIALS: dict[str, str] = {
    "Massachusetts Institute of Technology": "MIT",
    "University of California, Berkeley": "UC Berkeley",
    "University of California, San Diego": "UCSD",
    "Harvard University": "Harvard",
    "University College London": "UCL",
    "Stanford University": "Stanford",
    "University of Oxford": "Oxford",
    "Carnegie Mellon University": "CMU",
    "California Institute of Technology": "Caltech",
    "University of Toronto": "U Toronto",
    "University of Pennsylvania": "U Penn",
    "École Polytechnique Fédérale de Lausanne": "EPFL",
    "Howard Hughes Medical Institute": "HHMI",
    "New York University": "NYU",
    "Google (United States)": "Google",
    "DeepMind (United Kingdom)": "DeepMind",
    "Microsoft (United States)": "Microsoft",
    "Microsoft Research (United Kingdom)": "MS Research",
    "Meta (Israel)": "Meta",
    # Consolidated parent orgs
    "Alphabet (Google + DeepMind)": "Alphabet",
    "Microsoft": "Microsoft",
    "Meta (Facebook)": "Meta",
}


def _initials(inst_name: str) -> str:
    """Return short label for an institution name; fall back to truncated original."""
    short = INSTITUTION_INITIALS.get(str(inst_name).strip())
    return short if short else _truncate(str(inst_name), 14)


def _format_paper_label(title: str, year: int | float, venue: str) -> tuple[str, str]:
    """Return (short_label_for_bar, long_label_for_overflow).

    short_label: "Title (year). *Journal*" — truncation handled by caller.
    long_label:  same; we let the caller decide where to spill.
    """
    title_clean = str(title).strip().replace("<b>", "").replace("</b>", "")
    parts = [title_clean]
    try:
        yr = int(year)
        parts[0] = f"{title_clean} ({yr})"
    except (TypeError, ValueError):
        pass
    if venue and str(venue).strip():
        parts.append(f"{str(venue).strip()}")
    long_label = ". ".join(parts)
    return long_label, long_label


def _draw_right_column_bars(
    ax: plt.Axes,
    df: pd.DataFrame,
    metric_col: str,
    label_col: str,
    label_max: int,
    max_metric: float,
) -> dict[int, tuple[float, float]]:
    """Institutions — bars grow RIGHT from X_INSTS_LEFT. Name INSIDE the bar;
    type badge (IND / EDU / FAC / GOV / HC / NP) at the bar's outer EDGE."""
    out = {}
    y_positions = np.linspace(Y_TOP, Y_BOTTOM, len(df))
    for (_, row), y in zip(df.iterrows(), y_positions, strict=True):
        rank = int(row["inst_rank"])
        v = float(row[metric_col])
        bar_len = X_INSTS_BAR_MAX * (v / max_metric)
        x_outer = X_INSTS_LEFT + bar_len
        color = _color_for(row["neuro_share"])
        ax.add_patch(
            mpatches.Rectangle(
                (X_INSTS_LEFT, y - BAR_HEIGHT / 2),
                bar_len,
                BAR_HEIGHT,
                facecolor=color,
                edgecolor=TRANSMITTER["navy"],
                linewidth=0.4,
                zorder=4,
            )
        )

        # Type badge AT THE OUTER EDGE of the bar (right side)
        itype = str(row.get("inst_type", "other") or "other").lower()
        badge, badge_color = INST_TYPE_BADGE.get(itype, INST_TYPE_BADGE["other"])
        ax.text(
            x_outer + 0.004,
            y,
            badge,
            ha="left",
            va="center",
            fontsize=7.5,
            fontweight="bold",
            color=badge_color,
            zorder=5,
        )

        # Institution INITIALS inside the bar; full name + badge outside.
        full_name = str(row[label_col]).strip()
        short = _initials(full_name)
        text_color = TRANSMITTER["navy"] if _is_light(color) else "white"
        # Try to fit initials inside the bar; if too short, render initials
        # just outside (left, navy) before the badge+name.
        chars_inside = max(int(bar_len / 0.0058) - 1, 0)
        if chars_inside >= len(short):
            ax.text(
                X_INSTS_LEFT + bar_len / 2,
                y,
                short,
                ha="center",
                va="center",
                fontsize=8.5,
                fontweight="bold",
                color=text_color,
                zorder=5,
            )
        else:
            # bar too short for initials; render initials just outside before badge
            ax.text(
                X_INSTS_LEFT + bar_len + 0.002,
                y,
                short,
                ha="left",
                va="center",
                fontsize=8.5,
                fontweight="bold",
                color=TRANSMITTER["navy"],
                zorder=5,
            )

        # OUTSIDE the bar: badge + full name (with a small offset past the
        # initials block if it was rendered outside above).
        badge_x = x_outer + (0.028 if chars_inside < len(short) else 0.005)
        ax.text(
            badge_x,
            y,
            badge,
            ha="left",
            va="center",
            fontsize=7.5,
            fontweight="bold",
            color=badge_color,
            zorder=5,
        )
        ax.text(
            badge_x + 0.020,
            y,
            _truncate(full_name, label_max),
            ha="left",
            va="center",
            fontsize=8.5,
            color=TRANSMITTER["navy"],
            zorder=5,
        )
        out[rank] = (X_INSTS_LEFT, y)
    return out


# ---------------------------------------------------------------------------
# Curve helpers
# ---------------------------------------------------------------------------


def _smooth_curve(x0, y0, x1, y1, n=40):
    t = np.linspace(0, 1, n)
    s = 3 * t**2 - 2 * t**3
    xs = x0 + s * (x1 - x0)
    ys = y0 + s * (y1 - y0)
    return xs, ys


def _draw_curves(
    ax: plt.Axes,
    edges: list[tuple[float, float, float, float, float]],
    *,
    base_alpha: float = 0.30,
    max_lw: float = 1.8,
) -> None:
    if not edges:
        return
    strengths = np.array([e[4] for e in edges], dtype=float)
    if strengths.max() == 0:
        return
    norm = strengths / strengths.max()
    for (xa, ya, xb, yb, _w), n in zip(edges, norm, strict=True):
        xs, ys = _smooth_curve(xa, ya, xb, yb)
        alpha = base_alpha + (1 - base_alpha) * n * 0.6
        lw = 0.4 + max_lw * n
        ax.plot(xs, ys, "-", color=TRANSMITTER["muted"], lw=lw, alpha=alpha, zorder=2)


# ---------------------------------------------------------------------------
# X-axis indicators at the bottom of each column
# ---------------------------------------------------------------------------


def _draw_column_xaxis(
    ax: plt.Axes,
    x_anchor: float,
    bar_max_len: float,
    metric_max: float,
    *,
    grow_direction: str,
    label: str,
    y: float = 0.05,
    n_ticks: int = 4,
) -> None:
    """Draw a mini horizontal axis at the bottom of one column.

    grow_direction = "left": bars grow leftward from x_anchor (papers).
    grow_direction = "right": bars grow rightward from x_anchor (authors, insts).
    """
    if grow_direction == "left":
        x_min, x_max = x_anchor - bar_max_len, x_anchor
    else:
        x_min, x_max = x_anchor, x_anchor + bar_max_len
    # Axis line
    ax.plot([x_min, x_max], [y, y], "-", color=TRANSMITTER["navy"], lw=0.8, zorder=3)
    # Ticks
    tick_xs = np.linspace(x_min, x_max, n_ticks)
    # Tick values (mapped from x position to metric value).
    # For grow_direction == "left", the LEFT-most tick corresponds to metric_max
    # (longest bar). For grow_direction == "right", the LEFT-most tick is 0.
    if grow_direction == "left":
        tick_vals = np.linspace(metric_max, 0, n_ticks)
    else:
        tick_vals = np.linspace(0, metric_max, n_ticks)
    for xt, vt in zip(tick_xs, tick_vals, strict=True):
        ax.plot([xt, xt], [y - 0.006, y], "-", color=TRANSMITTER["navy"], lw=0.8)
        ax.text(
            xt,
            y - 0.012,
            f"{vt:.0f}",
            ha="center",
            va="top",
            fontsize=7.5,
            color=TRANSMITTER["gray"],
        )
    ax.text(
        (x_min + x_max) / 2,
        y - 0.03,
        label,
        ha="center",
        va="top",
        fontsize=8.5,
        color=TRANSMITTER["navy"],
        fontweight="bold",
    )


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def _read(name: str) -> pd.DataFrame:
    """A results/bridge table; floats are parsed so that they round-trip exactly."""
    return pd.read_csv(BRIDGE_DIR / name, float_precision="round_trip")


def _load(use_consolidated: bool = True) -> tuple:
    papers = _read("table_s1_papers.csv")
    papers = (
        papers.rename(
            columns={
                "rank": "paper_rank",
                "year": "publication_year",
                "B": "B_harmonic",
                "openalex_id": "work_id",
            }
        )
        .sort_values("B_harmonic", ascending=False)
        .head(N)
        .reset_index(drop=True)
    )
    papers["paper_rank"] = papers.index + 1
    papers["neuro_share"] = papers["c_neuro"] / (papers["c_neuro"] + papers["c_ai"]).clip(lower=1)

    authors = (
        _read("table_s2_authors.csv")
        .sort_values("total_B", ascending=False)
        .head(N)
        .reset_index(drop=True)
    )
    authors["author_rank"] = authors.index + 1
    authors["neuro_share"] = authors["total_c_neuro"] / (
        authors["total_c_neuro"] + authors["total_c_ai"]
    ).clip(lower=1)

    # Institutions: corporate groups merged (main figure) or as OpenAlex ships them.
    if use_consolidated:
        insts = _read("table_s3_institutions_consolidated.csv")
        logger.info("Using CONSOLIDATED institutions (Alphabet / Microsoft / Meta merged)")
    else:
        insts = _read("table_s3b_institutions_separated.csv")
        logger.info("Using OpenAlex-separated institutions")
    insts = insts.sort_values("total_B", ascending=False).head(N).reset_index(drop=True)
    insts["inst_rank"] = insts.index + 1
    insts["neuro_share"] = insts["total_c_neuro"] / (
        insts["total_c_neuro"] + insts["total_c_ai"]
    ).clip(lower=1)

    pa = _read("paper_author_links.csv")
    pa["pos_weight"] = pa["author_position"].fillna("middle").map(POSITION_WEIGHT).fillna(1.0)
    pa_top = pa[pa["paper_rank"].notna() & pa["author_rank"].notna()].copy()
    pa_top["paper_rank"] = pa_top["paper_rank"].astype(int)
    pa_top["author_rank"] = pa_top["author_rank"].astype(int)

    # Hand-verified author -> institution edges (current / past); an edge is drawn only when its
    # institution is one of the 15 shown.
    cur = _read("author_institution_edges.csv")
    cur = cur.merge(insts[["inst_id", "inst_rank"]], on="inst_id", how="left")
    cur_top = cur[cur["inst_rank"].notna()].copy()
    cur_top["author_rank"] = cur_top["author_rank"].astype(int)
    cur_top["inst_rank"] = cur_top["inst_rank"].astype(int)

    # Venues of the top papers ("Title (year). Journal" labels); blank where OpenAlex has none.
    venues = {
        w: v for w, v in zip(papers["work_id"], papers["venue"], strict=True) if isinstance(v, str)
    }

    return papers, authors, insts, pa_top, cur_top, venues


def build(use_consolidated: bool = True, name: str = "figure2_v3") -> Path:
    """Build Figure 2 v3.

    use_consolidated=True   -> Alphabet / Microsoft / Meta corporate groups
                               merged in the institutions column (main figure).
    use_consolidated=False  -> raw OpenAlex separated entities (Figure S5.1 of the supplements).
    """
    apply_style()
    papers, authors, insts, pa_top, cur_top, venues = _load(use_consolidated=use_consolidated)
    logger.info(
        "Loaded top entities: %d papers, %d authors, %d insts; pa-edges=%d, cur-affil-top15=%d",
        len(papers),
        len(authors),
        len(insts),
        len(pa_top),
        len(cur_top),
    )

    fig, ax = plt.subplots(figsize=(17, 10))
    ax.set_xlim(-0.02, 1.10)
    ax.set_ylim(0, 1.02)
    ax.axis("off")
    ax.set_facecolor(TRANSMITTER["bg"])

    # Column bars
    paper_attach = _draw_left_column_bars(
        ax,
        papers,
        metric_col="B_harmonic",
        label_col="title",
        label_max=52,
        max_metric=float(papers["B_harmonic"].max()),
        venues=venues,
    )
    author_left, author_right = _draw_middle_column_bars(
        ax,
        authors,
        metric_col="total_B",
        label_col="author_name",
        max_metric=float(authors["total_B"].max()),
    )
    inst_attach = _draw_right_column_bars(
        ax,
        insts,
        metric_col="total_B",
        label_col="inst_name",
        label_max=34,
        max_metric=float(insts["total_B"].max()),
    )

    # Paper -> Author curves (left side of authors column)
    pa_edges = []
    for _, row in pa_top.iterrows():
        rkp = int(row["paper_rank"])
        rka = int(row["author_rank"])
        if rkp not in paper_attach or rka not in author_left:
            continue
        xp, yp = paper_attach[rkp]
        xa, ya, _ = author_left[rka]
        pa_edges.append((xp, yp, xa, ya, float(row["pos_weight"])))
    _draw_curves(ax, pa_edges)
    logger.info("Drew %d paper->author edges", len(pa_edges))

    # Author -> Institution curves (right side of authors column).
    # CURRENT affiliations = solid navy; PAST affiliations = faded gray (thinner,
    # low alpha). Status comes from the hand-verified curated affiliations table.
    cur_edges = []
    past_edges = []
    for _, row in cur_top.iterrows():
        rka = int(row["author_rank"])
        rki = int(row["inst_rank"])
        if rka not in author_right or rki not in inst_attach:
            continue
        xa = author_right[rka]
        ya = author_left[rka][1]
        xi, yi = inst_attach[rki]
        if str(row.get("affiliation_status", "current")) == "past":
            past_edges.append((xa, ya, xi, yi))
        else:
            cur_edges.append((xa, ya, xi, yi))
    # Past first (underneath), then current on top.
    for xa, ya, xb, yb in past_edges:
        xs, ys = _smooth_curve(xa, ya, xb, yb)
        ax.plot(xs, ys, "-", color=TRANSMITTER["muted"], lw=0.9, alpha=0.22, zorder=2)
    for xa, ya, xb, yb in cur_edges:
        xs, ys = _smooth_curve(xa, ya, xb, yb)
        ax.plot(xs, ys, "-", color=TRANSMITTER["navy"], lw=1.5, alpha=0.62, zorder=3)
    logger.info(
        "Drew %d current (solid) + %d past (faded) author->inst edges",
        len(cur_edges),
        len(past_edges),
    )

    # Column headers
    ax.text(
        X_PAPERS_RIGHT - X_PAPERS_BAR_MAX / 2,
        Y_TOP + 0.025,
        "TOP 15 BRIDGE PAPERS",
        ha="center",
        va="bottom",
        fontsize=11,
        fontweight="bold",
        color=TRANSMITTER["navy"],
    )
    ax.text(
        X_AUTHORS_LEFT + X_AUTHORS_BAR_MAX / 2,
        Y_TOP + 0.025,
        "TOP 15 BRIDGE AUTHORS",
        ha="center",
        va="bottom",
        fontsize=11,
        fontweight="bold",
        color=TRANSMITTER["navy"],
    )
    ax.text(
        X_INSTS_LEFT + X_INSTS_BAR_MAX / 2,
        Y_TOP + 0.025,
        "TOP 15 INSTITUTIONS",
        ha="center",
        va="bottom",
        fontsize=11,
        fontweight="bold",
        color=TRANSMITTER["navy"],
    )

    # Mini x-axes at the bottom of each column
    _draw_column_xaxis(
        ax,
        x_anchor=X_PAPERS_RIGHT,
        bar_max_len=X_PAPERS_BAR_MAX,
        metric_max=float(papers["B_harmonic"].max()),
        grow_direction="left",
        label="B-harmonic",
    )
    _draw_column_xaxis(
        ax,
        x_anchor=X_AUTHORS_LEFT,
        bar_max_len=X_AUTHORS_BAR_MAX,
        metric_max=float(authors["total_B"].max()),
        grow_direction="right",
        label="∑ B-harmonic",
    )
    _draw_column_xaxis(
        ax,
        x_anchor=X_INSTS_LEFT,
        bar_max_len=X_INSTS_BAR_MAX,
        metric_max=float(insts["total_B"].max()),
        grow_direction="right",
        label="∑ B-harmonic",
    )

    # (Explanatory note removed — methodology + caveats now live in the figure
    # caption / supplement. Functional legends below are retained.)

    # Visual key: solid = current affiliation, faded = past affiliation.
    key_ax = fig.add_axes([0.50, 0.930, 0.18, 0.020])
    key_ax.axis("off")
    key_ax.set_xlim(0, 1)
    key_ax.set_ylim(0, 1)
    key_ax.plot([0.00, 0.10], [0.72, 0.72], "-", color=TRANSMITTER["navy"], lw=1.5, alpha=0.62)
    key_ax.text(
        0.13, 0.72, "current affiliation", va="center", fontsize=8.0, color=TRANSMITTER["navy"]
    )
    key_ax.plot([0.00, 0.10], [0.20, 0.20], "-", color=TRANSMITTER["muted"], lw=0.9, alpha=0.40)
    key_ax.text(
        0.13, 0.20, "past affiliation", va="center", fontsize=8.0, color=TRANSMITTER["gray"]
    )

    # Institution-type legend below the missing-affiliations note
    legend_pieces = [
        "EDU = education",
        "IND = industry",
        "FAC = facility",
        "GOV = government",
        "HC = healthcare",
        "NP = nonprofit",
    ]
    fig.text(
        0.99,
        0.965,
        "  ·  ".join(legend_pieces),
        ha="right",
        va="top",
        fontsize=7.5,
        color=TRANSMITTER["gray"],
    )

    # Colorbar legend (enlarged per user feedback 2026-05-22)
    cbar_ax = fig.add_axes([0.03, 0.952, 0.32, 0.020])
    norm = mpl.colors.Normalize(vmin=0, vmax=1)
    sm = mpl.cm.ScalarMappable(cmap=NEUROSHARE_CMAP, norm=norm)
    sm.set_array([])
    cb = fig.colorbar(sm, cax=cbar_ax, orientation="horizontal")
    cb.outline.set_visible(False)
    cb.set_ticks([0.0, 0.5, 1.0])
    cb.set_ticklabels(["AI-leaning", "mixed", "neuro-leaning"])
    cb.ax.tick_params(
        labelsize=9.0, color=TRANSMITTER["gray"], labelcolor=TRANSMITTER["gray"], pad=3
    )
    # Title above the colorbar
    fig.text(
        0.03,
        0.985,
        "Citation orientation (neuro_share)",
        fontsize=9.5,
        color=TRANSMITTER["navy"],
        fontweight="bold",
        ha="left",
        va="bottom",
    )

    finalize(
        fig,
        source="Data: OpenAlex (snapshot 2026-03-30). See supplement for methods.",
        byline="Renato Duarte // The Transmitter",
    )
    fig.subplots_adjust(top=0.92, bottom=0.04, left=0.02, right=0.99)

    out_png = FIGURES_DIR / f"{name}.png"
    out_svg = FIGURES_DIR / f"{name}.svg"
    fig.savefig(out_png)
    fig.savefig(out_svg)
    plt.close(fig)
    logger.info("Wrote %s and %s", out_png, out_svg)
    return out_png


if __name__ == "__main__":
    # Main: consolidated corporate groups
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    build(use_consolidated=True)

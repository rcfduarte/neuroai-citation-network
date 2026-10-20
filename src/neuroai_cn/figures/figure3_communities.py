"""Figure 3 — Community structure of the top-1000 bridge papers.

Two complementary views on the same 1000-paper UMAP scatter:

    Panel A — TRACK-BASED TAXONOMY
        Color: 5 named tracks (Foundational DL/AI, Bio-plausible AI,
        Applied ML for brain, Bridge manifestos, Statistical methods)
        + a muted "Other / cross-domain" residual.
        Size : sqrt(B_harmonic).
        Label: top-3 papers per track (smallest text, drawn lines).

    Panel B — ERA STRATIFICATION  (companion view; same UMAP coords)
        Color: 4 canonical eras.
        Size : sqrt(B_harmonic).
        Useful for the "where do new clusters emerge" sub-narrative.

Data: corrections/20260508/q4_classified_nodes.parquet (1000 rows w/
UMAP x,y, Leiden cluster, hand-labeled track, era, paper_type, subfield).

Output: figures/figure3_track_communities.{png,svg}
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .. import config
from .style import (
    CANONICAL_ERAS,
    TRANSMITTER,
    apply_style,
    finalize,
)

logger = logging.getLogger(__name__)

CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"
FIGURES_DIR = CORRECTIONS_DIR / "figures"


# Expanded track palette (10 categories) — v2 classification post-OpenAlex
# subfield mapping; physics contamination dropped (Q4.7).
TRACK_COLORS: dict[str, str] = {
    "Foundational DL/AI": "#1f6f7e",
    "Cognitive neuroscience": TRANSMITTER["mustard"],
    "Statistical methods": "#6A7282",
    "Applied ML for brain": TRANSMITTER["coral"],
    "Neuroengineering / hardware": "#1f78b4",
    "Bio-plausible AI": "#33a02c",
    "Molecular / cellular neuro": "#e7298a",
    "Medical imaging methods": "#a6761d",
    "Bridge manifestos & theory": TRANSMITTER["purple"],
    "Other": "#D9D2BD",
    # Backwards compatible for v1 if needed
    "Other / cross-domain": "#D9D2BD",
}
ERA_COLORS_SCATTER: dict[str, str] = {
    "Pre-DL": "#9CB7B9",
    "DL emergence": "#5E8A93",
    "DL expansion": "#277E8A",
    "NeuroAI era": TRANSMITTER["crimson"],
}


def assign_canonical_era(year: float | int) -> str | None:
    if pd.isna(year):
        return None
    for name, lo, hi in CANONICAL_ERAS:
        if lo <= int(year) <= hi:
            return name
    return None


def _truncate(s: str, n: int) -> str:
    s = str(s).strip().replace("<b>", "").replace("</b>", "")
    return s if len(s) <= n else s[: n - 1] + "…"


def _pull_to_label_centroid(
    df: pd.DataFrame,
    label_col: str,
    *,
    alpha_named: float = 0.55,
    alpha_other: float | None = None,
    other_label: str = "Other / cross-domain",
    x_col: str = "x",
    y_col: str = "y",
    jitter: float = 0.6,
    seed: int = 17,
) -> pd.DataFrame:
    """Shift points toward their label centroid so labels cluster spatially.

    For each label group, compute the median (x, y) and move every point a
    fraction `alpha` of the way toward that centroid. A small Gaussian jitter
    is added afterwards to prevent overplotting at the centroid.

    `alpha_other` (if set) is applied only to the residual label so the
    "Other" cloud doesn't collapse to a point.
    """
    if alpha_other is None:
        alpha_other = alpha_named
    rng = np.random.default_rng(seed)
    centroids = df.groupby(label_col)[[x_col, y_col]].median()
    out = df.copy()
    new_x = out[x_col].to_numpy(dtype=float).copy()
    new_y = out[y_col].to_numpy(dtype=float).copy()
    for label, (cx, cy) in centroids.iterrows():
        mask = out[label_col].to_numpy() == label
        alpha = alpha_other if label == other_label else alpha_named
        new_x[mask] = alpha * cx + (1 - alpha) * new_x[mask]
        new_y[mask] = alpha * cy + (1 - alpha) * new_y[mask]
        n = int(mask.sum())
        new_x[mask] = new_x[mask] + rng.normal(0, jitter, n)
        new_y[mask] = new_y[mask] + rng.normal(0, jitter, n)
    out[x_col + "_pulled"] = new_x
    out[y_col + "_pulled"] = new_y
    return out


def _scatter_with_tracks(
    ax: plt.Axes,
    df: pd.DataFrame,
    *,
    annotate_papers: bool = False,
) -> None:
    """Track-colored scatter. Paper titles are NOT annotated by default
    (per user 2026-05-22: titles obscure clusters)."""
    df = df.copy()
    df["track_norm"] = df["track"].fillna("Other")
    df["track_norm"] = df["track_norm"].apply(lambda t: t if t in TRACK_COLORS else "Other")
    # Pull points toward their track centroid for spatial clustering
    df = _pull_to_label_centroid(
        df,
        "track_norm",
        alpha_named=0.62,
        alpha_other=0.08,
        other_label="Other",
        jitter=0.7,
    )

    # Order: residual first (background), then named tracks by size descending
    order_by_size = df["track_norm"].value_counts().sort_values(ascending=False).index.tolist()
    if "Other" in order_by_size:
        order_by_size.remove("Other")
        order_by_size = ["Other", *order_by_size]

    sizes_raw = np.sqrt(df["B_harmonic"].clip(lower=0).to_numpy())
    s_scale = 24.0 / max(sizes_raw.max(), 1.0)

    for track in order_by_size:
        sub = df[df["track_norm"] == track]
        if sub.empty:
            continue
        color = TRACK_COLORS.get(track, "#888888")
        alpha = 0.20 if track == "Other" else 0.85
        sub_sizes = np.sqrt(sub["B_harmonic"].clip(lower=0).to_numpy()) * s_scale
        ax.scatter(
            sub["x_pulled"],
            sub["y_pulled"],
            s=sub_sizes**2,
            c=color,
            alpha=alpha,
            edgecolor="white",
            linewidth=0.4,
            label=f"{track}  (n={len(sub)})",
            zorder=3 if track != "Other" else 2,
        )

    ax.set_xlabel("UMAP-1 (label-pulled)")
    ax.set_ylabel("UMAP-2 (label-pulled)")
    ax.set_title(
        "A  ·  Track classification of top-1000 bridge papers (v2)",
        loc="left",
        fontsize=12,
        fontweight="bold",
        color=TRANSMITTER["navy"],
        pad=8,
    )
    ax.legend(
        loc="upper left",
        fontsize=7.5,
        ncols=1,
        frameon=False,
        labelspacing=0.4,
        bbox_to_anchor=(1.01, 1.0),
    )
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def _track_size_density_barplot(
    ax: plt.Axes,
    df: pd.DataFrame,
    label_col: str,
    color_map: dict[str, str],
    title: str,
) -> None:
    """Underneath panel: bar chart of cluster size (n) and density (mean B / paper).

    Two bars per label group, side-by-side:
      * Solid bar: n_papers (left y-axis)
      * Outline bar: mean B-harmonic per paper (right y-axis, %-scaled)
    """
    df = df.copy()
    df["label"] = df[label_col].fillna("Other")
    summary = (
        df.groupby("label")
        .agg(n=("work_id", "nunique"), mean_B=("B_harmonic", "mean"), total_B=("B_harmonic", "sum"))
        .reset_index()
        .sort_values("n", ascending=False)
    )
    x = np.arange(len(summary))
    bar_w = 0.4

    # n (left axis)
    colors = [color_map.get(lbl, "#888888") for lbl in summary["label"]]
    ax.bar(
        x - bar_w / 2,
        summary["n"],
        width=bar_w,
        color=colors,
        alpha=0.92,
        edgecolor=TRANSMITTER["navy"],
        linewidth=0.4,
        label="N papers",
    )
    ax.set_ylabel("N papers", color=TRANSMITTER["navy"])
    ax.set_xticks(x)
    ax.set_xticklabels(summary["label"].tolist(), rotation=35, ha="right", fontsize=8.5)

    # mean B per paper (right axis)
    ax_r = ax.twinx()
    ax_r.bar(
        x + bar_w / 2,
        summary["mean_B"],
        width=bar_w,
        color="none",
        edgecolor=TRANSMITTER["navy"],
        linewidth=1.0,
        hatch="///",
        label="mean B-harmonic",
    )
    ax_r.set_ylabel("mean B-harmonic per paper", color=TRANSMITTER["navy"])
    ax_r.spines["top"].set_visible(False)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    ax.set_title(
        title, loc="left", fontsize=10, fontweight="bold", color=TRANSMITTER["navy"], pad=4
    )


def _scatter_with_era(ax: plt.Axes, df: pd.DataFrame) -> None:
    df = df.copy()
    df["era_canon"] = df["publication_year"].apply(assign_canonical_era)
    df = df[df["era_canon"].notna()].copy()
    # Pull each point toward its era centroid so eras cluster spatially.
    df = _pull_to_label_centroid(
        df,
        "era_canon",
        alpha_named=0.55,
        alpha_other=0.55,
        other_label="__none__",
        jitter=0.7,
    )
    sizes_raw = np.sqrt(df["B_harmonic"].clip(lower=0).to_numpy())
    s_scale = 24.0 / max(sizes_raw.max(), 1.0)
    order = ["Pre-DL", "DL emergence", "DL expansion", "NeuroAI era"]
    for era in order:
        sub = df[df["era_canon"] == era]
        if sub.empty:
            continue
        sub_sizes = np.sqrt(sub["B_harmonic"].clip(lower=0).to_numpy()) * s_scale
        ax.scatter(
            sub["x_pulled"],
            sub["y_pulled"],
            s=sub_sizes**2,
            c=ERA_COLORS_SCATTER[era],
            alpha=0.80,
            edgecolor="white",
            linewidth=0.4,
            label=f"{era}  (n={len(sub)})",
            zorder=3 if era != "Pre-DL" else 2,
        )
    ax.set_xlabel("UMAP-1")
    ax.set_ylabel("UMAP-2")
    ax.set_title(
        "B  ·  Era stratification of the same 1000 papers",
        loc="left",
        fontsize=12,
        fontweight="bold",
        color=TRANSMITTER["navy"],
        pad=8,
    )
    ax.legend(loc="upper left", fontsize=7.5, frameon=False, labelspacing=0.4)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def build() -> Path:
    apply_style()
    # Prefer the v2 reclassified set if available
    v2 = CORRECTIONS_DIR / "q4_classified_nodes_v2.parquet"
    src = v2 if v2.exists() else CORRECTIONS_DIR / "q4_classified_nodes.parquet"
    df = pd.read_parquet(src)
    logger.info("Loaded %d papers from %s", len(df), src.name)

    # 2-row layout: scatter (top) + bar (bottom) per panel
    fig = plt.figure(figsize=(15, 11))
    gs = fig.add_gridspec(
        2,
        2,
        height_ratios=[2.4, 1.0],
        hspace=0.48,
        wspace=0.30,
    )
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_a_bar = fig.add_subplot(gs[1, 0])
    ax_b_bar = fig.add_subplot(gs[1, 1])

    _scatter_with_tracks(ax_a, df)
    _scatter_with_era(ax_b, df)

    # Add era column to df for the era barplot
    df_era = df.copy()
    df_era["era_canon"] = df_era["publication_year"].apply(assign_canonical_era)

    # Bar plots: cluster size + density
    _track_size_density_barplot(
        ax_a_bar,
        df,
        "track",
        TRACK_COLORS,
        "Cluster size + mean B-harmonic per track",
    )
    _track_size_density_barplot(
        ax_b_bar,
        df_era[df_era["era_canon"].notna()],
        "era_canon",
        ERA_COLORS_SCATTER,
        "Cluster size + mean B-harmonic per era",
    )

    finalize(
        fig,
        source=(
            "OpenAlex 2026-03-30. Top-1000 bridge papers (Leiden-clustered + UMAP). "
            "v2 classification: OpenAlex `primary_topic.subfield` used to "
            "reclassify the 'Other / cross-domain' bucket; physics contamination "
            "dropped (140 papers); 860 papers shown. Node size ∝ √(B-harmonic). "
            "Coordinates pulled toward each label's centroid so labels cluster spatially."
        ),
        byline="Renato Duarte // The Transmitter",
    )
    fig.subplots_adjust(top=0.95, bottom=0.10, left=0.05, right=0.96)

    out_png = FIGURES_DIR / "figure3_track_communities.png"
    out_svg = FIGURES_DIR / "figure3_track_communities.svg"
    fig.savefig(out_png)
    fig.savefig(out_svg)
    plt.close(fig)
    logger.info("Wrote %s and %s", out_png, out_svg)
    return out_png


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    build()

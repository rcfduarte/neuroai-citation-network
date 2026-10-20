#!/usr/bin/env python3
"""Aggregate + plot the cross-source replication of the neuro<->AI citation-flow finding.

Three sources, two directions:
    - FROZEN SNAPSHOT  (OpenAlex March-2026 vintage, topic-based, STRICT 1702 def)
    - OPENALEX LIVE    (OpenAlex May-2026 vintage, topic-based, same STRICT def)
    - SEMANTIC SCHOLAR (independent graph, VENUE-based def, non-elided subset)

CRITICAL: compare SHAPE, never absolute level across sources (each source has its own
classifier vintage / field definition -> its own level; see HANDOFF CRITICAL RULES).
So the primary figure is a 2x3 small-multiples grid, each panel with its OWN y-axis.
A second "overlay" figure normalises each series to its own reference-window mean to make
the shape comparison literal.

Metric (all sources): cross-field refs per 1,000 classified refs
    = n_to_target / (n_to_within + n_to_target + n_to_other) * 1000.

Outputs:
    <figdir>/figure1_share_crosscheck.{png,svg}          (2x3 grid, native levels + CIs)
    <figdir>/figure1_share_crosscheck_overlay.{png,svg}  (1x2 shape overlay, normalised)
    <out>/results_summary.md                              (per-source slopes + caveats)

Usage:
    uv run python scripts/api_crosscite/plot_crosscite_compare.py
    uv run python scripts/api_crosscite/plot_crosscite_compare.py --snapshot extended
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from neuroai_cn import config

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---- style (matched to figure1_share_v5.svg) -------------------------------------------
C_NEURO_TO_AI = "#c77f0a"  # orange: neuroscience cites AI (borrows from AI)
C_AI_TO_NEURO = "#0f8b8d"  # teal:   AI cites neuroscience (borrows from neuroscience)
C_TEXT = "#1a1a1a"
C_GREY = "#9aa0a6"
C_BAND = "#f4f4f4"
DIR_COLOR = {"neuro_to_ai": C_NEURO_TO_AI, "ai_to_neuro": C_AI_TO_NEURO}
DIR_LABEL = {
    "neuro_to_ai": "Neuroscience cites AI  (borrows from AI)",
    "ai_to_neuro": "AI cites neuroscience  (borrows from neuroscience)",
}
SRC_ORDER = ["snapshot", "openalex_live", "s2"]
SRC_LABEL = {
    "snapshot": "Frozen snapshot\n(OpenAlex Mar 2026, topic-based)",
    "openalex_live": "OpenAlex live\n(May 2026 vintage, topic-based)",
    "s2": "Semantic Scholar\n(independent graph, venue-based)",
}
TAKEOFF = 2014  # deep-learning inflection asserted by the headline finding
START = 2000  # slope/trend window start (1990s are noisy small samples)
CLEAN_MAX = 2023  # drop 2024-25 (snapshot re-indexing artifact) for clean slopes
PLOT_MIN_YEAR = 1995  # display floor (matches figure1_share_v5); pre-1995 is small-sample noise
OVERLAP = (2010, 2023)  # window used to normalise the overlay (all sources present, pre-artifact)

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
        "text.color": C_TEXT,
        "axes.labelcolor": C_TEXT,
        "xtick.color": C_TEXT,
        "ytick.color": C_TEXT,
        "axes.edgecolor": C_GREY,
        "svg.fonttype": "none",
    }
)

REPO = Path(__file__).resolve().parents[2]
SNAP_BASE = config.CORRECTIONS_DIR / "20260508"
FIGDIR = config.FIGURES_DIR


# ---- loaders ----------------------------------------------------------------------------
def load_snapshot(which: str) -> pd.DataFrame:
    """which in {strict, extended}; returns year,direction,per1000 (population, no sampling CI)."""
    path = (
        (SNAP_BASE / "strict" / "q1_strict_or_by_year.parquet")
        if which == "strict"
        else (SNAP_BASE / "q1_v3_extended_or_by_year.parquet")
    )
    df = pd.read_parquet(path)
    denom = df["n_to_within"] + df["n_to_target"] + df["n_to_other"]
    df["per1000"] = df["n_to_target"] / denom * 1000.0
    df["ci_lo"] = np.nan
    df["ci_hi"] = np.nan
    df["source"] = "snapshot"
    return df[["source", "direction", "year", "per1000", "ci_lo", "ci_hi"]].copy()


def load_cells(out_dir: Path, source: str) -> pd.DataFrame:
    """Load a sampler's cells.jsonl -> tidy frame. Returns empty frame if file absent."""
    p = out_dir / "cells.jsonl"
    if not p.exists():
        return pd.DataFrame(columns=["source", "direction", "year", "per1000", "ci_lo", "ci_hi"])
    rows = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["source", "direction", "year", "per1000", "ci_lo", "ci_hi"])
    df["source"] = source
    keep = ["source", "direction", "year", "per1000", "ci_lo", "ci_hi"]
    for col in ("elision_rate", "n_papers", "n_refs_classified", "n_elided", "n_sampled"):
        if col in df.columns:
            keep.append(col)
    return df[keep].sort_values(["direction", "year"]).reset_index(drop=True)


# ---- stats ------------------------------------------------------------------------------
def ols_slope(years, vals, weights=None):
    """Return (slope_per_year, n) over finite points; slope in per-1000 units / yr.

    `weights`, if given, lets us downweight noisy years (e.g., 1/var from bootstrap CIs).
    Without weights, equal weight per year. With sampled estimates and rare events
    (AI->neuro per-1000), a single high-variance year can swing the OLS estimate by an
    order of magnitude — weighting fixes this.
    """
    years = np.asarray(years, float)
    vals = np.asarray(vals, float)
    m = np.isfinite(years) & np.isfinite(vals)
    if weights is not None:
        w = np.asarray(weights, float)
        m = m & np.isfinite(w) & (w > 0)
    if m.sum() < 3:
        return float("nan"), int(m.sum())
    if weights is None:
        b1, _b0 = np.polyfit(years[m], vals[m], 1)
    else:
        # Weighted least squares: minimise sum w_i (y_i - (b0 + b1 x_i))^2
        b1, _b0 = np.polyfit(years[m], vals[m], 1, w=w[m])
    return float(b1), int(m.sum())


def series(df, source, direction):
    s = df[(df["source"] == source) & (df["direction"] == direction)].sort_values("year")
    return s


def _slope_window(s, y0, y1):
    """Inverse-variance-weighted OLS in [y0, y1]; falls back to unweighted if no CI columns."""
    m = (s["year"] >= y0) & (s["year"] <= y1)
    sub = s.loc[m]
    weights = None
    if {"ci_lo", "ci_hi"}.issubset(sub.columns):
        halfw = (sub["ci_hi"] - sub["ci_lo"]) / 2.0
        # Variance ≈ (halfwidth / 1.96)^2 for 95% bootstrap CI; weight = 1/var.
        # Add tiny floor so width=0 years (e.g., S2 cells where target=0) don't blow up.
        var = np.maximum((halfw / 1.96) ** 2, 1e-3)
        w = 1.0 / var
        if w.notna().any():
            weights = w
    return ols_slope(sub["year"], sub["per1000"], weights=weights)


def slope_table(df) -> pd.DataFrame:
    """Per source x direction slopes over meaningful windows.

    Windows start at 2000 (the headline claim's window; 1990s are noisy small samples):
      slope_2000_end   : full recent trend, incl. 2024-25
      slope_2000_2023  : clean trend (drops the snapshot 2024-25 re-indexing artifact)
      slope_2014_2023  : post-deep-learning takeoff window
    """
    recs = []
    for source in SRC_ORDER:
        for direction in ("neuro_to_ai", "ai_to_neuro"):
            s = series(df, source, direction)
            s = s[np.isfinite(s["per1000"])]
            if s.empty:
                continue
            yrs, vals = s["year"].to_numpy(), s["per1000"].to_numpy()
            ymax = int(yrs.max())
            sl_end, n_end = _slope_window(s, START, ymax)
            sl_clean, n_clean = _slope_window(s, START, CLEAN_MAX)
            sl_take, n_take = _slope_window(s, TAKEOFF, CLEAN_MAX)

            def at(y, s=s):
                row = s[s["year"] == y]
                return round(float(row["per1000"].iloc[0]), 2) if len(row) else None

            recs.append(
                {
                    "source": source,
                    "direction": direction,
                    "year_min": int(yrs.min()),
                    "year_max": ymax,
                    "val_2000": at(2000),
                    "val_2023": at(2023),
                    "val_last": round(float(vals[-1]), 2),
                    "slope_2000_end": round(sl_end, 4),
                    "n_end": n_end,
                    "slope_2000_2023": round(sl_clean, 4),
                    "n_clean": n_clean,
                    "slope_2014_2023": round(sl_take, 4),
                    "n_take": n_take,
                }
            )
    return pd.DataFrame(recs)


# ---- plotting ---------------------------------------------------------------------------
def _panel(ax, s, direction, show_ci=True):
    color = DIR_COLOR[direction]
    s = s.sort_values("year")
    s = s[np.isfinite(s["per1000"]) & (s["year"] >= PLOT_MIN_YEAR)]
    if s.empty:
        ax.text(
            0.5,
            0.5,
            "no data yet",
            transform=ax.transAxes,
            ha="center",
            va="center",
            color=C_GREY,
            fontsize=10,
            style="italic",
        )
        return
    yrs = s["year"].to_numpy()
    vals = s["per1000"].to_numpy()
    if show_ci and "ci_lo" in s and np.isfinite(s["ci_lo"]).any():
        lo = s["ci_lo"].to_numpy()
        hi = s["ci_hi"].to_numpy()
        mok = np.isfinite(lo) & np.isfinite(hi)
        ax.fill_between(yrs[mok], lo[mok], hi[mok], color=color, alpha=0.18, lw=0)
    ax.plot(yrs, vals, "-", color=color, lw=2.0, solid_capstyle="round")
    ax.plot(yrs, vals, "o", color=color, ms=2.5, alpha=0.5)
    ax.axvline(TAKEOFF, color=C_GREY, lw=0.8, ls=":", alpha=0.7, zorder=0)
    # end-of-line value label
    ax.annotate(
        f"{vals[-1]:.0f}",
        xy=(yrs[-1], vals[-1]),
        xytext=(4, 0),
        textcoords="offset points",
        va="center",
        color=color,
        fontsize=9,
        fontweight="bold",
    )


def fig_grid(df, s2_elision_note, snap_which, out_png, out_svg):
    fig, axes = plt.subplots(2, 3, figsize=(12.5, 6.4), sharex=True)
    for r, direction in enumerate(("neuro_to_ai", "ai_to_neuro")):
        for c, source in enumerate(SRC_ORDER):
            ax = axes[r, c]
            _panel(ax, series(df, source, direction), direction, show_ci=(source != "snapshot"))
            ax.set_xlim(1993, 2026)
            ax.tick_params(labelsize=8)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            if r == 0:
                lbl = SRC_LABEL[source]
                if source == "snapshot":
                    lbl = lbl.replace("topic-based", f"{snap_which} 1702 def")
                ax.set_title(lbl, fontsize=9.5, color=C_TEXT, pad=8)
            if c == 0:
                ax.set_ylabel(
                    DIR_LABEL[direction].split("  ")[0],
                    fontsize=9.5,
                    color=DIR_COLOR[direction],
                    fontweight="bold",
                )
            if r == 1:
                ax.set_xlabel("year", fontsize=9)
    # S2 elision annotation on the two S2 panels (col index 2)
    for r in (0, 1):
        axes[r, 2].annotate(
            s2_elision_note,
            xy=(0.03, 0.04),
            xycoords="axes fraction",
            fontsize=7.2,
            color=C_GREY,
            style="italic",
            va="bottom",
        )
    # ~2014 marker label (top-left panel)
    axes[0, 0].annotate(
        "~2014",
        xy=(TAKEOFF, axes[0, 0].get_ylim()[1]),
        xytext=(TAKEOFF + 0.5, axes[0, 0].get_ylim()[1]),
        fontsize=7,
        color=C_GREY,
        va="top",
    )
    fig.suptitle(
        "Cross-source replication: does “neuroscience leans on AI; AI does not lean back” "
        "hold across data sources?",
        fontsize=13,
        fontweight="bold",
        color=C_TEXT,
        y=0.985,
    )
    fig.text(
        0.5,
        0.945,
        "Each column is an independent re-derivation. Compare the SHAPE down each row "
        "(rising vs. flat) — not levels across columns (each source has its own classifier "
        "vintage / field definition).",
        ha="center",
        fontsize=8.8,
        color=C_GREY,
    )
    fig.text(
        0.5,
        0.012,
        "Metric: cross-field references per 1,000 classified references, per (field, year). "
        "Shaded = 95% cluster-bootstrap CI over sampled papers (snapshot is the full population, no sampling CI). "
        "Dotted line = 2014. "
        "Sources: OpenAlex snapshot (Mar 2026) & live API (May 2026), topic-based; Semantic Scholar API, venue-based, "
        "non-elided subset. · R. Duarte / The Transmitter",
        ha="center",
        fontsize=6.6,
        color=C_GREY,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.93))
    fig.savefig(out_png, dpi=200, bbox_inches="tight", facecolor="white")
    fig.savefig(out_svg, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _norm_factor(s):
    """100 / (mean per1000 over OVERLAP window, else over all finite years)."""
    s = s[np.isfinite(s["per1000"])]
    if s.empty:
        return None
    win = s[(s["year"] >= OVERLAP[0]) & (s["year"] <= OVERLAP[1])]
    base = win["per1000"].mean() if len(win) >= 3 else s["per1000"].mean()
    if not np.isfinite(base) or base == 0:
        return None
    return 100.0 / base


SRC_STYLE = {  # line style per source for the overlay
    "snapshot": dict(ls="-", lw=2.4, alpha=0.95),
    "openalex_live": dict(ls="--", lw=2.0, alpha=0.95),
    "s2": dict(ls=":", lw=2.2, alpha=0.95),
}
SRC_SHORT = {"snapshot": "snapshot", "openalex_live": "OpenAlex live", "s2": "Semantic Scholar"}


def fig_overlay(df, out_png, out_svg):
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 5.0), sharey=True)
    for c, direction in enumerate(("neuro_to_ai", "ai_to_neuro")):
        ax = axes[c]
        color = DIR_COLOR[direction]
        for source in SRC_ORDER:
            s = series(df, source, direction)
            f = _norm_factor(s)
            if f is None:
                continue
            s = s[np.isfinite(s["per1000"]) & (s["year"] >= START)].sort_values("year")
            if s.empty:
                continue
            st = SRC_STYLE[source]
            ax.plot(s["year"], s["per1000"] * f, color=color, label=SRC_SHORT[source], **st)
        ax.axvline(TAKEOFF, color=C_GREY, lw=0.8, ls=":", alpha=0.7, zorder=0)
        ax.axhline(100, color=C_GREY, lw=0.7, alpha=0.5, zorder=0)
        ax.set_title(DIR_LABEL[direction], fontsize=11, color=color, fontweight="bold")
        ax.set_xlim(START - 1, 2026)
        ax.set_xlabel("year", fontsize=9)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    axes[0].set_ylabel(
        f"share, indexed to each source's\nown {OVERLAP[0]}–{OVERLAP[1]} mean = 100", fontsize=9.5
    )
    fig.suptitle(
        "Shape comparison (each source normalised to its own level): "
        "neuroscience→AI rises; AI→neuroscience stays flat",
        fontsize=12.5,
        fontweight="bold",
        color=C_TEXT,
    )
    fig.text(
        0.5,
        0.01,
        f"Each curve divided by its own {OVERLAP[0]}–{OVERLAP[1]} mean so SHAPES overlay "
        "(levels are not comparable across sources). Dotted vertical = 2014. "
        "· R. Duarte / The Transmitter",
        ha="center",
        fontsize=7,
        color=C_GREY,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(out_png, dpi=200, bbox_inches="tight", facecolor="white")
    fig.savefig(out_svg, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fig_extended_replication(snap_ext, oa_ext, out_png, out_svg):
    """1×2 panels: snapshot-extended vs OA-live-extended, 2010-2025, headline def (1702+1707).

    Critical visual: the same-graph, same-definition vintage replication of the headline.
    """
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6), sharex=True)
    for c, direction in enumerate(("neuro_to_ai", "ai_to_neuro")):
        ax = axes[c]
        color = DIR_COLOR[direction]
        s = snap_ext[snap_ext["direction"] == direction].sort_values("year")
        s = s[(s["year"] >= 2010) & (s["year"] <= 2025)]
        o = oa_ext[oa_ext["direction"] == direction].sort_values("year")
        o = o[np.isfinite(o["per1000"])]
        # snapshot extended = population, no sampling CI; plot as solid heavy line
        ax.plot(
            s["year"],
            s["per1000"],
            "-",
            color=color,
            lw=2.6,
            alpha=0.95,
            label="snapshot (Mar 2026 vintage)",
        )
        # OA-live extended = sampled, with CI band
        if "ci_lo" in o and o["ci_lo"].notna().any():
            ax.fill_between(o["year"], o["ci_lo"], o["ci_hi"], color=color, alpha=0.18, lw=0)
        ax.plot(
            o["year"],
            o["per1000"],
            "--",
            color=color,
            lw=2.0,
            alpha=0.95,
            label="OA-live (May 2026 vintage)",
        )
        ax.plot(o["year"], o["per1000"], "o", color=color, ms=3, alpha=0.6)
        ax.axvline(TAKEOFF, color=C_GREY, lw=0.8, ls=":", alpha=0.7, zorder=0)
        ax.set_title(DIR_LABEL[direction], fontsize=11, color=color, fontweight="bold")
        ax.set_xlim(2009, 2026)
        ax.set_xlabel("year", fontsize=9)
        ax.tick_params(labelsize=9)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.legend(
            frameon=False,
            fontsize=8.5,
            loc="upper left" if direction == "neuro_to_ai" else "lower left",
        )
    axes[0].set_ylabel(
        "cross-field references per 1,000\n(extended AI def: subfields 1702+1707)", fontsize=9.5
    )
    fig.suptitle(
        "Same-graph, same-definition vintage replication of the headline (extended AI def)",
        fontsize=12.5,
        fontweight="bold",
        color=C_TEXT,
    )
    fig.text(
        0.5,
        0.01,
        "Both series use OpenAlex with the extended AI definition (subfield 1702 + subfield 1707, "
        "matching the snapshot's q1_v3_extended scheme modulo topic T10502, which contributes <2%). "
        "The neuroscience→AI rise reproduces at full magnitude in fresh vintage; the AI→neuro 2024–25 "
        "spike does not — it appears only in the March-2026 snapshot. "
        "OA-live: N=1,500 papers/cell, shaded 95% bootstrap CI. · R. Duarte / The Transmitter",
        ha="center",
        fontsize=6.8,
        color=C_GREY,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(out_png, dpi=200, bbox_inches="tight", facecolor="white")
    fig.savefig(out_svg, bbox_inches="tight", facecolor="white")
    plt.close(fig)


SRC_FULL = {
    "snapshot": "Frozen snapshot (OpenAlex Mar-2026 vintage, topic-based, {snap} 1702 def)",
    "openalex_live": "OpenAlex live (May-2026 vintage, topic-based, strict 1702 def)",
    "s2": "Semantic Scholar (independent graph, venue-based, non-elided subset)",
}


def _verdict(tbl):
    """Per-source qualitative verdict on the headline shape.

    Headline: neuro->AI RISES (positive clean slope, accelerating post-2014);
              AI->neuro FLAT (clean slope near zero / slightly negative).
    """
    lines = []
    for source in SRC_ORDER:
        sub = tbl[tbl["source"] == source]
        if sub.empty:
            lines.append(f"- **{source}**: no data yet.")
            continue
        n2a = sub[sub["direction"] == "neuro_to_ai"]
        a2n = sub[sub["direction"] == "ai_to_neuro"]
        parts = []
        if not n2a.empty and pd.notna(n2a["slope_2000_2023"].iloc[0]):
            sl = n2a["slope_2000_2023"].iloc[0]
            tk = n2a["slope_2014_2023"].iloc[0]
            rise = "RISES" if sl > 0 else "does NOT rise"
            parts.append(
                f"neuro→AI {rise} (clean slope {sl:+.3f}/yr; 2014–23 takeoff {tk:+.3f}/yr)"
            )
        if not a2n.empty and pd.notna(a2n["slope_2000_2023"].iloc[0]):
            sl = a2n["slope_2000_2023"].iloc[0]
            flat = "FLAT" if abs(sl) < 0.15 else ("rising" if sl > 0 else "declining")
            parts.append(f"AI→neuro {flat} (clean slope {sl:+.3f}/yr)")
        verdict = (
            "replicates"
            if (
                not n2a.empty
                and not a2n.empty
                and pd.notna(n2a["slope_2000_2023"].iloc[0])
                and n2a["slope_2000_2023"].iloc[0] > 0
                and pd.notna(a2n["slope_2000_2023"].iloc[0])
                and a2n["slope_2000_2023"].iloc[0] < 0.15
            )
            else "PARTIAL/TBD"
        )
        lines.append(
            f"- **{SRC_FULL[source].split(' (')[0]}** — *{verdict}*: " + "; ".join(parts) + "."
        )
    return "\n".join(lines)


def _md_table(d: pd.DataFrame) -> str:
    cols = list(d.columns)
    head = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    rows = [
        "| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |"
        for r in d.itertuples(index=False)
    ]
    return "\n".join([head, sep, *rows])


def write_results_summary(df, tbl, s2_note, snap_which, out: Path):
    n_oa = int((df["source"] == "openalex_live").sum())
    n_s2 = int((df["source"] == "s2").sum())
    md = []
    md.append("# Cross-source replication — results summary\n")
    md.append(
        f"_Generated by `plot_crosscite_compare.py`. Snapshot def plotted: **{snap_which}** "
        "(1702-only; matches the API samplers). Slopes in cross-field refs per 1,000 per year._\n"
    )
    md.append(f"- OpenAlex-live cells: **{n_oa}/72** · Semantic Scholar cells: **{n_s2}/72**")
    md.append(f"- Semantic Scholar reference {s2_note}.\n")
    md.append("## Per-source slopes\n")
    if tbl.empty:
        md.append("_(no data yet)_\n")
    else:
        show = tbl[
            [
                "source",
                "direction",
                "year_min",
                "year_max",
                "val_2000",
                "val_2023",
                "val_last",
                "slope_2000_2023",
                "slope_2014_2023",
                "slope_2000_end",
            ]
        ]
        md.append(_md_table(show))
        md.append("")
    md.append("## Verdict (auto-derived; review against CIs)\n")
    md.append(
        "Headline to reproduce: **neuroscience→AI rises (takes off ~2014); AI→neuroscience stays flat.**\n"
    )
    md.append(_verdict(tbl) + "\n")
    md.append("## Caveats\n")
    md.append(
        "- **Levels are not comparable across sources** (classifier vintage / field definition differ "
        "by ~2×); only SHAPE/trend is comparable. Never splice snapshot + live.\n"
    )
    md.append(
        "- **Strict (1702-only) AI** gives a gentler neuro→AI rise than the headline **extended** AI "
        "definition (which shows ~3× / +0.5 per-1000/yr); the strict def is used here because the API "
        "samplers classify AI as subfield 1702. The *shape* (rise + 2014 inflection) is the test, not magnitude.\n"
    )
    md.append(
        "- **2024–25**: the frozen snapshot's AI→neuro values are inflated by an OpenAlex within-AI "
        "re-indexing artifact; clean slopes use ≤2023. Fresh-vintage OpenAlex-live and venue-based S2 are "
        "independent of that specific artifact.\n"
    )
    md.append(
        "- **Semantic Scholar elision**: references are publisher-elided for ~⅓ of neuro papers; the S2 "
        "estimate is over the non-elided subset.\n"
    )
    # elision-trend check (does elision worsen for recent years? -> recent tail less reliable)
    if "elision_rate" in df.columns:
        # neuro-field cells (direction neuro_to_ai) are where publisher elision bites
        es = df[(df["source"] == "s2") & (df["direction"] == "neuro_to_ai")][
            ["year", "elision_rate"]
        ].dropna()
        if len(es) >= 5:
            sl, _ = ols_slope(es["year"], es["elision_rate"])
            r = np.corrcoef(es["year"], es["elision_rate"])[0, 1]
            # Direction of trend matters: decreasing elision means recent S2 has BETTER coverage,
            # so the recent tail is MORE reliable, not less. Only rising elision is a concern.
            if abs(r) <= 0.5:
                flag = "elision roughly stable over time — shape usable"
            elif r > 0:
                flag = "⚠️ elision RISES with year — recent-tail shape is less reliable"
            else:
                flag = "elision DECREASES with year — recent-tail shape is MORE reliable than early years"
            md.append("### S2 elision trend (neuro papers)\n")
            md.append(
                f"- mean {es['elision_rate'].mean() * 100:.0f}% "
                f"(range {es['elision_rate'].min() * 100:.0f}–{es['elision_rate'].max() * 100:.0f}%), "
                f"slope {sl * 100:+.2f} pp/yr, r={r:+.2f} → **{flag}**.\n"
            )
    (out / "results_summary.md").write_text("\n".join(md))
    print(f"[wrote] {out / 'results_summary.md'}")


# ---- main -------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--snapshot",
        choices=["strict", "extended"],
        default="strict",
        help="frozen-snapshot definition to plot (strict = 1702-only, matches API samplers)",
    )
    ap.add_argument("--out", default=str(REPO / "data/derived/api_crosscite"))
    ap.add_argument("--figdir", default=str(FIGDIR))
    args = ap.parse_args()
    out = Path(args.out)
    figdir = Path(args.figdir)
    figdir.mkdir(parents=True, exist_ok=True)

    snap = load_snapshot(args.snapshot)
    oa = load_cells(out / "openalex_live", "openalex_live")
    s2 = load_cells(out / "s2", "s2")
    df = pd.concat([snap, oa, s2], ignore_index=True)
    for col in ("year", "per1000", "ci_lo", "ci_hi"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # S2 elision summary — neuro cells only (publisher-elision is a neuro-paper phenomenon;
    # AI cells have a different "no-refs" mechanism = S2 ref-coverage gaps, not publisher elision).
    s2_note = "elision: n/a (no S2 data yet)"
    if "elision_rate" in s2.columns and "direction" in s2.columns:
        er_neuro = s2.loc[s2["direction"] == "neuro_to_ai", "elision_rate"].dropna()
        if len(er_neuro):
            s2_note = (
                f"refs elided for {er_neuro.mean() * 100:.0f}% of neuro papers "
                f"(range {er_neuro.min() * 100:.0f}–{er_neuro.max() * 100:.0f}%)"
            )

    print(f"[counts] snapshot={len(snap)} openalex_live={len(oa)} s2={len(s2)}")
    tbl = slope_table(df)
    if not tbl.empty:
        print(tbl.to_string(index=False))

    fig_grid(
        df,
        s2_note,
        args.snapshot,
        figdir / "figure1_share_crosscheck.png",
        figdir / "figure1_share_crosscheck.svg",
    )
    fig_overlay(
        df,
        figdir / "figure1_share_crosscheck_overlay.png",
        figdir / "figure1_share_crosscheck_overlay.svg",
    )
    print(f"[wrote] {figdir / 'figure1_share_crosscheck.png'}")
    print(f"[wrote] {figdir / 'figure1_share_crosscheck_overlay.png'}")

    # Extended-AI replication figure (snapshot-extended vs OA-live-extended, 2010-2025).
    # Only generated if the extended OA-live cells exist (loader returns empty frame otherwise).
    snap_ext = load_snapshot("extended")
    oa_ext = load_cells(out / "openalex_live_extended", "openalex_live_extended")
    if not oa_ext.empty:
        for col in ("year", "per1000", "ci_lo", "ci_hi"):
            oa_ext[col] = pd.to_numeric(oa_ext[col], errors="coerce")
        snap_ext = snap_ext.copy()
        snap_ext["per1000"] = pd.to_numeric(snap_ext["per1000"], errors="coerce")
        fig_extended_replication(
            snap_ext,
            oa_ext,
            figdir / "figure1_extended_replication.png",
            figdir / "figure1_extended_replication.svg",
        )
        print(f"[wrote] {figdir / 'figure1_extended_replication.png'}")

    # write a machine-readable aggregate too
    df.to_csv(out / "crosscite_aggregate.csv", index=False)
    tbl.to_csv(out / "crosscite_slopes.csv", index=False)
    print(f"[wrote] {out / 'crosscite_aggregate.csv'}  {out / 'crosscite_slopes.csv'}")
    write_results_summary(df, tbl, s2_note, args.snapshot, out)
    return tbl, s2_note


if __name__ == "__main__":
    main()

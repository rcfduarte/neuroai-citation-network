"""Who pulls more weight in the NeuroAI bridge: authors or institutions?

Comparative analysis. For each top-N tier (N=1, 5, 15, 50, 100) we compute:

    1. CUMULATIVE SHARE  — fraction of total ∑B-harmonic captured by the top-N
       entities (∑B summed within author/institution aggregate tables).
    2. GINI COEFFICIENT  — inequality of ∑B distribution within authors and
       within institutions (across the top-200 / top-100 respectively).
    3. COVERAGE          — fraction of unique bridge papers that have at least
       one author / one institution among the top-N.
    4. WITHIN-INSTITUTION CONCENTRATION — for each top-15 institution, the
       share of its bridge papers contributed by its top-3 individual authors.
       High share ⇒ institutions are vessels for star authors (authors drive).
       Low share  ⇒ institutional ecosystems matter (institutions drive).

Output:
    corrections/20260508/figures/figure_supp_authors_vs_inst.{png,svg}
        Comparison plot: cumulative-share curve for authors vs institutions
        + Gini bars.
"""

from __future__ import annotations

import logging
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .. import config
from ..figures.style import TRANSMITTER, apply_style, finalize

logger = logging.getLogger(__name__)

CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"
FIGURES_DIR = CORRECTIONS_DIR / "figures"


def gini(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x[x >= 0]
    if x.size < 2 or x.sum() == 0:
        return float("nan")
    x = np.sort(x)
    n = x.size
    cum = np.cumsum(x)
    return (
        n + 1 - 2 * cum.sum() / x[-1]
        if False
        else (2 * np.sum(np.arange(1, n + 1) * x) - (n + 1) * x.sum()) / (n * x.sum())
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    apply_style()
    # Prefer top-1000 tables if available; fall back to top-200/100 otherwise.
    top1000_a = CORRECTIONS_DIR / "author_inst_top_authors_1000.parquet"
    top1000_i = CORRECTIONS_DIR / "author_inst_top_institutions_1000.parquet"
    pop_path = CORRECTIONS_DIR / "author_inst_population_totals.json"
    if top1000_a.exists() and top1000_i.exists():
        authors = (
            pd.read_parquet(top1000_a)
            .sort_values("total_B", ascending=False)
            .reset_index(drop=True)
        )
        insts = (
            pd.read_parquet(top1000_i)
            .sort_values("total_B", ascending=False)
            .reset_index(drop=True)
        )
        logger.info("Using TOP-1000 tables (authors=%d, insts=%d)", len(authors), len(insts))
        if pop_path.exists():
            import json as _json

            pop = _json.loads(pop_path.read_text())
            POP_AUTHORS_TOTAL_B = float(pop["authors_total_B"])
            POP_INSTS_TOTAL_B = float(pop["insts_total_B"])
            POP_AUTHORS_N = int(pop["authors_n"])
            POP_INSTS_N = int(pop["insts_n"])
        else:
            POP_AUTHORS_TOTAL_B = float(authors["total_B"].sum())
            POP_INSTS_TOTAL_B = float(insts["total_B"].sum())
            POP_AUTHORS_N = len(authors)
            POP_INSTS_N = len(insts)
    else:
        authors = (
            pd.read_parquet(CORRECTIONS_DIR / "author_inst_top_authors.parquet")
            .sort_values("total_B", ascending=False)
            .reset_index(drop=True)
        )
        insts_path = (
            CORRECTIONS_DIR / "author_inst_top_institutions_consolidated.parquet"
            if (CORRECTIONS_DIR / "author_inst_top_institutions_consolidated.parquet").exists()
            else CORRECTIONS_DIR / "author_inst_top_institutions.parquet"
        )
        insts = (
            pd.read_parquet(insts_path)
            .sort_values("total_B", ascending=False)
            .reset_index(drop=True)
        )
        POP_AUTHORS_TOTAL_B = float(authors["total_B"].sum())
        POP_INSTS_TOTAL_B = float(insts["total_B"].sum())
        POP_AUTHORS_N = len(authors)
        POP_INSTS_N = len(insts)
        logger.warning("Using FALLBACK top-200/100 tables")

    # Compute cumulative share at multiple tiers using the FULL-population
    # totals (denominators = ∑B across ALL 80k+ authors / ~5.6k institutions).
    tiers = [1, 5, 10, 15, 25, 50, 100, 250, 500, 1000]
    a_total = POP_AUTHORS_TOTAL_B
    i_total = POP_INSTS_TOTAL_B
    rows = []
    for N in tiers:
        a_share = float(authors["total_B"].head(N).sum()) / a_total
        if len(insts) >= N:
            i_share = float(insts["total_B"].head(N).sum()) / i_total
        else:
            i_share = float("nan")
        rows.append(dict(top_n=N, authors_share=a_share, insts_share=i_share))
    cum_df = pd.DataFrame(rows)
    logger.info("Cumulative share by top-N:")
    print(cum_df.to_string(index=False, float_format="%.3f"))

    # Gini coefficients
    g_authors = gini(authors["total_B"].to_numpy())
    g_insts = gini(insts["total_B"].to_numpy())

    # Within-institution concentration: for each top-15 institution, what % of
    # its papers (∑n_papers in author→inst edges, restricted to that institution)
    # is contributed by its top-3 authors?
    ai = pd.read_parquet(CORRECTIONS_DIR / "bridge_links_author_inst.parquet")
    top15_inst = insts.head(15)["inst_id"].astype(str).tolist()
    conc_rows = []
    for iid in top15_inst:
        # `bridge_links_author_inst.parquet` is keyed on raw OpenAlex inst_ids,
        # so the consolidated parent rows (canonical IDs like ALPHABET_GROUP)
        # don't have entries; skip them.
        sub = ai[ai["inst_id"].astype(str) == iid].sort_values("n_papers", ascending=False)
        if sub.empty:
            continue
        total = float(sub["n_papers"].sum())
        top3 = float(sub.head(3)["n_papers"].sum())
        conc_rows.append(
            dict(
                inst_id=iid,
                inst_name=insts.loc[insts["inst_id"] == iid, "inst_name"].iloc[0],
                n_authors=len(sub),
                total_papers_contrib=int(total),
                top3_share=top3 / total if total > 0 else float("nan"),
            )
        )
    conc_df = pd.DataFrame(conc_rows)
    median_top3 = conc_df["top3_share"].median() if not conc_df.empty else float("nan")
    logger.info("Top-3-author concentration per top-15 institution (median = %.2f):", median_top3)
    print(conc_df.to_string(index=False, float_format="%.3f"))

    # ------------------------------------------------------------------
    # Build the comparison plot
    # ------------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(12, 4.8), gridspec_kw={"width_ratios": [1.4, 0.9]}
    )

    # Panel 1: cumulative-share curves (normalised by full-population totals)
    a_cum = authors["total_B"].cumsum() / a_total
    i_cum = insts["total_B"].cumsum() / i_total
    ax1.plot(
        np.arange(1, len(a_cum) + 1),
        a_cum.to_numpy(),
        "-",
        color=TRANSMITTER["teal"],
        lw=2.2,
        label=f"Authors (top-{len(a_cum)} of {POP_AUTHORS_N:,})",
    )
    ax1.plot(
        np.arange(1, len(i_cum) + 1),
        i_cum.to_numpy(),
        "-",
        color=TRANSMITTER["mustard"],
        lw=2.2,
        label=f"Institutions (top-{len(i_cum)} of {POP_INSTS_N:,})",
    )
    # Annotate selected tier markers
    for N_mark in (15, 100, 1000):
        if N_mark > min(len(a_cum), len(i_cum)):
            continue
        ax1.axvline(N_mark, color=TRANSMITTER["navy"], ls=":", lw=0.6, alpha=0.45)
        a_v = float(a_cum.iloc[N_mark - 1])
        i_v = float(i_cum.iloc[N_mark - 1])
        ax1.text(
            N_mark * 1.05,
            a_v,
            f" {a_v * 100:.0f}%",
            color=TRANSMITTER["teal"],
            fontsize=7.5,
            va="center",
        )
        ax1.text(
            N_mark * 1.05,
            i_v + 0.025,
            f" {i_v * 100:.0f}%",
            color=TRANSMITTER["mustard"],
            fontsize=7.5,
            va="center",
        )
    ax1.set_xlabel("Rank (N) [log scale]")
    ax1.set_ylabel("Cumulative share of ∑ B-harmonic (full-pop denom.)")
    ax1.set_xscale("log")
    ax1.set_ylim(0, 1.02)
    ax1.legend(loc="lower right", fontsize=9)
    ax1.set_title(
        "A · Cumulative concentration",
        loc="left",
        fontsize=11,
        fontweight="bold",
        color=TRANSMITTER["navy"],
        pad=8,
    )

    # Panel 2: Gini bars + within-institution top-3-author share
    bars_x = ["Authors", "Institutions"]
    bars_y = [g_authors, g_insts]
    ax2.bar(
        bars_x,
        bars_y,
        color=[TRANSMITTER["teal"], TRANSMITTER["mustard"]],
        alpha=0.92,
        edgecolor=TRANSMITTER["navy"],
        linewidth=0.4,
    )
    for xi, yv in enumerate(bars_y):
        ax2.text(
            xi,
            yv + 0.012,
            f"{yv:.2f}",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
            color=TRANSMITTER["navy"],
        )
    ax2.set_ylim(0, 1.0)
    ax2.set_ylabel("Gini coefficient (∑ B-harmonic)")
    ax2.set_title(
        "B · Inequality of bridge weight",
        loc="left",
        fontsize=11,
        fontweight="bold",
        color=TRANSMITTER["navy"],
        pad=8,
    )

    finalize(
        fig,
        source=(
            "OpenAlex 2026-03-30. ∑ B-harmonic computed per author "
            "(`author_inst_top_authors`, top-200) and per institution "
            "(`author_inst_top_institutions(_consolidated)`, top-100 / top-97)."
        ),
        byline="Renato Duarte // The Transmitter",
    )
    fig.subplots_adjust(top=0.88, bottom=0.18, left=0.07, right=0.97, wspace=0.30)

    out_png = FIGURES_DIR / "figure_supp_authors_vs_inst.png"
    out_svg = FIGURES_DIR / "figure_supp_authors_vs_inst.svg"
    fig.savefig(out_png)
    fig.savefig(out_svg)
    plt.close(fig)

    logger.info("Cumulative share by tier:\n%s", cum_df.to_string(index=False))
    logger.info("Gini (B-harmonic): authors=%.3f institutions=%.3f", g_authors, g_insts)
    logger.info("Median top-3 author share across top-15 institutions: %.0f%%", median_top3 * 100)
    logger.info("Wrote figure: %s", out_png)
    return 0


if __name__ == "__main__":
    sys.exit(main())

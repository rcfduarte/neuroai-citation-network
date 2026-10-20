"""Fig. 1 and Fig. 2 re-plotted from the FRESH data only (OpenAlex pull, 06/10/2026). Reads and writes only fresh-recheck paths."""

import glob
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from neuroai_cn import config

D = Path("data/derived/_fresh_recheck_20261006")
OUT = config.FIGURES_DIR / "fresh-recheck-20261006"
OUT.mkdir(parents=True, exist_ok=True)
GOLD, TEAL, NAVY, GRAY = "#D4A521", "#277E8A", "#10304A", "#6B7280"
fs = pd.read_csv(D / "field_sizes_fresh_20261006.csv", index_col="year")
cells = pd.concat(
    [
        pd.read_json(f, lines=True)
        for f in sorted(glob.glob(str(D / "sample_extended_n1500*/cells.jsonl")))
    ]
)
cells = cells.drop_duplicates(["direction", "year"]).sort_values(["direction", "year"])

rows = []
for _, r in cells.iterrows():
    y, d = int(r.year), r.direction
    neuro, ai = fs.loc[y, "neuro"], fs.loc[y, "ai_extended"]
    own, other = (neuro, ai) if d == "neuro_to_ai" else (ai, neuro)
    null = other / (own + other)
    refs_pp = r.n_refs_classified / r.n_papers
    k = (r.within + r.target + r.other) / (r.within + r.target)  # per-1000 -> restricted share

    def to_or(p, null=null):
        return (p / (1 - p)) / (null / (1 - null))

    p, plo, phi = r.per1000 / 1000 * k, r.ci_lo / 1000 * k, r.ci_hi / 1000 * k
    rows.append(
        dict(
            year=y,
            direction=d,
            per1000=r.per1000,
            per1000_lo=r.ci_lo,
            per1000_hi=r.ci_hi,
            refs_per_paper=refs_pp,
            field_papers=own,
            chance_share=null,
            restricted_share=p,
            odds_ratio=to_or(p),
            odds_ratio_lo=to_or(plo),
            odds_ratio_hi=to_or(phi),
            est_cross_citations_k=r.per1000 / 1000 * refs_pp * own / 1000,
            est_cross_citations_k_lo=r.ci_lo / 1000 * refs_pp * own / 1000,
            est_cross_citations_k_hi=r.ci_hi / 1000 * refs_pp * own / 1000,
        )
    )
t = pd.DataFrame(rows)
t.to_csv(OUT / "fresh_fig1_fig2_data.csv", index=False)
LAB = {
    "neuro_to_ai": ("Neuroscience papers citing AI", GOLD),
    "ai_to_neuro": ("AI papers citing neuroscience", TEAL),
}
x0 = int(t.year.min()) - 0.5


def series(ax, col, lo, hi, log=False):
    for d, (lab, c) in LAB.items():
        s = t[t.direction == d].sort_values("year")
        y = s[col].to_numpy()
        e = [y - s[lo].to_numpy(), s[hi].to_numpy() - y]
        ax.errorbar(
            s.year,
            y,
            yerr=e,
            color=c,
            lw=2.6,
            marker="o",
            ms=5,
            capsize=2.5,
            elinewidth=1,
            label=lab,
        )
    ax.axvspan(
        2023.5,
        2025.5,
        facecolor="#E5E7EB",
        alpha=0.5,
        hatch="///",
        edgecolor=GRAY,
        linewidth=0,
        zorder=0,
    )
    ax.set_xlim(x0, 2025.5)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    if log:
        ax.set_yscale("log")


SRC = "Fresh OpenAlex download, October 2026: 1,500 sampled papers per field and year (bars: 95% range); field sizes counted directly. Hatched: 2024–25 provisional."
# Fig 1 (fresh): odds ratio
fig, ax = plt.subplots(figsize=(10, 5.4))
series(ax, "odds_ratio", "odds_ratio_lo", "odds_ratio_hi", log=True)
ax.set_ylabel("odds ratio (1 = chance; log scale)", color=NAVY)
ax.legend(frameon=False, loc="lower left")
ax.set_title(
    "Fresh data · Citation flow over time (odds ratio)",
    loc="left",
    fontsize=12.5,
    fontweight="bold",
    color=NAVY,
)
fig.text(0.01, 0.01, SRC, fontsize=7.5, style="italic", color=GRAY)
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(OUT / "fresh_fig1_odds_ratio.png", dpi=150)
fig.savefig(OUT / "fresh_fig1_odds_ratio.svg")
plt.close(fig)
# Fig 2 (fresh): estimated counts and share
fig, (a, b) = plt.subplots(1, 2, figsize=(13, 5.2))
series(a, "est_cross_citations_k", "est_cross_citations_k_lo", "est_cross_citations_k_hi")
a.set_ylabel("thousand citations per year (estimated)", color=NAVY)
a.set_title(
    "A  ·  Citations from one field to the other",
    loc="left",
    fontsize=12.5,
    fontweight="bold",
    color=NAVY,
)
series(b, "per1000", "per1000_lo", "per1000_hi")
b.set_ylabel("per 1,000 papers cited", color=NAVY)
b.set_title(
    "B  ·  Papers cited from the other field, per 1,000",
    loc="left",
    fontsize=12.5,
    fontweight="bold",
    color=NAVY,
)
b.legend(frameon=False, loc="lower right")
fig.text(
    0.01,
    0.01,
    SRC + " A = share × references per paper × papers per year.",
    fontsize=7.5,
    style="italic",
    color=GRAY,
)
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(OUT / "fresh_fig2_raw.png", dpi=150)
fig.savefig(OUT / "fresh_fig2_raw.svg")
plt.close(fig)
print(
    t[["year", "direction", "per1000", "odds_ratio", "est_cross_citations_k"]]
    .round(3)
    .to_string(index=False)
)

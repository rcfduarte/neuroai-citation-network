"""Separate recheck plots (06/10/2026): fresh OpenAlex pull against the March snapshot, 2020-2025. Touches no existing file."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from neuroai_cn import config

D = Path("data/derived/_fresh_recheck_20261006")
OUT = config.FIGURES_DIR / "fresh-recheck-20261006"
OUT.mkdir(parents=True, exist_ok=True)
t = pd.read_csv(D / "tables/fresh_vs_snapshot_2020_2025.csv")
GOLD, TEAL = "#D4A521", "#277E8A"
a = t[t.direction == "ai_to_neuro"].set_index("year")
n = t[t.direction == "neuro_to_ai"].set_index("year")
fig, ax = plt.subplots(1, 3, figsize=(15, 4.6))
ax[0].plot(a.index, a.snap_null, "-o", color=TEAL, label="March snapshot")
ax[0].plot(a.index, a.fresh_null, "--s", color=TEAL, label="fresh pull (Oct 2026)")
ax[0].set_title(
    "Neuroscience's share of the combined\nneuroscience + AI literature (chance baseline)",
    fontsize=10,
    loc="left",
)
ax[0].legend(frameon=False)
ax[1].plot(a.index, a.snap_refs_per_paper, "-o", color=TEAL, label="AI papers, snapshot")
ax[1].plot(a.index, a.fresh_refs_per_paper, "--s", color=TEAL, label="AI papers, fresh")
ax[1].plot(n.index, n.snap_refs_per_paper, "-o", color=GOLD, label="neuroscience papers, snapshot")
ax[1].plot(n.index, n.fresh_refs_per_paper, "--s", color=GOLD, label="neuroscience papers, fresh")
ax[1].set_title("References recorded per paper", fontsize=10, loc="left")
ax[1].legend(frameon=False, fontsize=8)
ax[2].plot(a.index, a.snap_per1000, "-o", color=TEAL)
ax[2].plot(a.index, a.fresh_per1000, "--s", color=TEAL)
ax[2].plot(n.index, n.snap_per1000, "-o", color=GOLD)
ax[2].plot(n.index, n.fresh_per1000, "--s", color=GOLD)
ax[2].set_title(
    "Cross-field references per 1,000 references\n(solid: snapshot; dashed: fresh, 1,500 papers per cell, noisy for AI)",
    fontsize=10,
    loc="left",
)
for x in ax:
    x.spines[["top", "right"]].set_visible(False)
    x.set_xlabel("year")
fig.tight_layout()
fig.savefig(OUT / "fresh_vs_snapshot_2020_2025.png", dpi=150)
fig.savefig(OUT / "fresh_vs_snapshot_2020_2025.svg")
t.to_csv(OUT / "fresh_vs_snapshot_2020_2025.csv", index=False)

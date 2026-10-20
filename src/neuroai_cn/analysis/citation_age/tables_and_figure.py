"""Step 3: tables, summary numbers and the figure for REPORT.md.

Reads rankings.parquet (step 2, config.DERIVED_DIR / citation_age) and classification.csv
(hand coding, results/citation_age) and writes

    results/citation_age/tables.md     top-25 tables for the three primary rankings
    results/citation_age/summary.json  every number quoted in the report
    figures/fig_top100_years.svg / .png / -onwhite.png

Classes (classification.csv header has the rules):
    concept   a claim about brains or minds (the article's "genuine bridge works")
    method    a new ML model, algorithm or architecture, or a review of ML methods
    tool      software, data, benchmark, analysis method, methods tutorial or survey
    book      a textbook OpenAlex types as an article (the article excludes books)
    artefact  not a single work: a merged, generic or whole-volume record

Recency questions use true_year (first publication year; differs from the OpenAlex
year only for reprints such as Miller 1956, dated 1994). "After 2005" means
true_year >= 2006.
"""

import json
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from neuroai_cn.analysis.citation_age.paths import RESULTS, WORK_DIR
from neuroai_cn.config import FIGURES_DIR
from neuroai_cn.figures.style import TRANSMITTER, apply_style

PRIMARY = {
    "orig": "Published ranking (all-time counts)",
    "rate": "Age-normalised (citations per year to 2023)",
    "win8": "Fixed window (first 8 years; works 1990-2015)",
}
SENS = {
    "orig_1990_2015": "Published score, works 1990-2015 only",
    "win7": "Fixed window, first 7 years (1990-2015)",
    "win5_to2018": "Fixed window, first 5 years (1990-2018)",
    "win8_share": "Fixed window 8 y, growth-normalised",
    "rate_share": "Per-year rate, growth-normalised",
    "rate_noceil": "Per-year rate, E2 ceiling removed",
    "win8_noceil": "Fixed window 8 y, E2 ceiling removed",
    "rate_unknown": "Per-year rate, 'unknown' field admitted",
}
HEAD = {
    "orig": 100,
    "rate": 100,
    "win8": 100,
    "orig_1990_2015": 50,
    "win7": 50,
    "win5_to2018": 50,
    "rate_noceil": 25,
    "win8_noceil": 25,
    "rate_unknown": 25,
    "win8_share": 100,
    "rate_share": 50,
}
CLASSES = ("concept", "method", "tool", "book", "artefact")


def main() -> None:
    rk = pd.read_parquet(WORK_DIR / "rankings.parquet")
    cl = pd.read_csv(RESULTS / "classification.csv", comment="#").rename(columns={"class": "cls"})
    assert set(cl["cls"]) <= set(CLASSES), set(cl["cls"]) - set(CLASSES)
    assert cl["title_norm"].is_unique
    rk = rk.merge(
        cl[["title_norm", "cls", "true_year", "short", "note"]], on="title_norm", how="left"
    )

    need = rk[rk.apply(lambda r: r["rank"] <= HEAD[r["ranking"]], axis=1)]
    missing = need[need["cls"].isna()].drop_duplicates("title_norm")
    if len(missing):
        missing[["title_norm", "work_id", "title", "publication_year", "ranking", "rank"]].to_csv(
            WORK_DIR / "to_classify_missing.csv", index=False
        )
        sys.exit(f"{len(missing)} ranked works have no class; see to_classify_missing.csv")

    R = {name: g.sort_values("rank").reset_index(drop=True) for name, g in rk.groupby("ranking")}
    orig_by_id = R["orig"].set_index("work_id")["rank"]
    orig_by_title = R["orig"].set_index("title_norm")["rank"]

    def published_rank(r) -> str:
        if r.work_id in orig_by_id.index:
            return str(int(orig_by_id[r.work_id]))
        if r.title_norm in orig_by_title.index:
            return f"{int(orig_by_title[r.title_norm])}*"
        return "excl."

    def most_recent(
        g: pd.DataFrame, k: int, classes: tuple[str, ...] = ("concept",)
    ) -> dict | None:
        h = g[(g["rank"] <= k) & g["cls"].isin(classes)]
        if h.empty:
            return None
        r = h.sort_values(["true_year", "rank"], ascending=[False, True]).iloc[0]
        return {"year": int(r["true_year"]), "rank": int(r["rank"]), "work": r["short"]}

    def after2005(g: pd.DataFrame, k: int, cls: str = "concept") -> list[str]:
        h = g[(g["rank"] <= k) & (g["cls"] == cls) & (g["true_year"] > 2005)]
        return [f"{r.short} ({int(r.true_year)}, #{r.rank})" for r in h.itertuples()]

    def recency_block(name: str) -> dict:
        g = R[name]
        return {
            f"top{k}": {
                "most_recent_concept": most_recent(g, k),
                "most_recent_concept_or_method": most_recent(g, k, ("concept", "method")),
                "n_concepts": int(((g["rank"] <= k) & (g["cls"] == "concept")).sum()),
                "concepts_after_2005": after2005(g, k),
                "methods_after_2005": after2005(g, k, "method"),
            }
            for k in (15, 25, 50)
        }

    summary: dict = {name: recency_block(name) for name in list(PRIMARY) + list(SENS)}

    # ------------------------------------------------------------------ top-25 tables
    md: list[str] = []
    for name, label in PRIMARY.items():
        g = R[name].head(25)
        unit = {"orig": "citations", "rate": "citations per year", "win8": "citations in window"}[
            name
        ]
        md += [
            f"#### {label}",
            "",
            f"| # | Work | Year | Class | neuro ({unit}) | AI ({unit}) | Score | Published rank |",
            "|-:|-|-:|-|-:|-:|-:|-:|",
        ]
        for r in g.itertuples():
            cn, ca = {
                "orig": (f"{r.c_neuro:,}", f"{r.c_ai:,}"),
                "rate": (f"{r.r_neuro:.0f}", f"{r.r_ai:.0f}"),
                "win8": (f"{r.w8_neuro:,}", f"{r.w8_ai:,}"),
            }[name]
            yr = (
                f"{int(r.true_year)}"
                if r.true_year == r.publication_year
                else f"{int(r.true_year)} (OA {r.publication_year})"
            )
            cls = f"**{r.cls}**" if r.cls == "concept" else r.cls
            md.append(
                f"| {r.rank} | {r.short} | {yr} | {cls} | {cn} | {ca} | {r.score:,.0f} | "
                f"{published_rank(r)} |"
            )
        md.append("")

    # ------------------------------------------------------- top-100 year distribution
    FIG = {
        **PRIMARY,
        "win8_share": "Sensitivity: fixed window, growth-normalised (share of each field's references)",
    }
    dist = {}
    for name in FIG:
        g = R[name].head(100)
        yrs = g["true_year"]
        dist[name] = {
            "median_year": float(yrs.median()),
            "iqr": [float(yrs.quantile(0.25)), float(yrs.quantile(0.75))],
            "n_after_2005": int((yrs > 2005).sum()),
            "n_after_2010": int((yrs > 2010).sum()),
            "by_class": g["cls"].value_counts().to_dict(),
            "concepts_after_2005": int(((g["cls"] == "concept") & (yrs > 2005)).sum()),
            "bins": pd.cut(
                yrs,
                [0, 1989, 1995, 2000, 2005, 2010, 2015, 2020, 2026],
                labels=[
                    "<1990",
                    "1990-95",
                    "1996-00",
                    "2001-05",
                    "2006-10",
                    "2011-15",
                    "2016-20",
                    "2021-26",
                ],
            )
            .value_counts(sort=False)
            .to_dict(),
        }
    summary["top100_year_distribution"] = dist

    # ------------------------------------------------ where the published top-15 land
    land = []
    for r in R["orig"].head(15).itertuples():
        row = {"work": r.short, "year": int(r.true_year), "class": r.cls}
        for name in ("orig", "rate", "win8", "win8_share", "rate_share"):
            m = R[name][R[name]["title_norm"] == r.title_norm]
            row[name] = int(m["rank"].iloc[0]) if len(m) else None
        land.append(row)
    summary["published_top15_landing"] = land

    # Growth normalisation weights early-1990s citations heavily (the indexed citing literature
    # was small then). Re-rank win8_share among works first published 1996 or later only.
    g = R["win8_share"][R["win8_share"]["true_year"] >= 1996].reset_index(drop=True)
    g["rank96"] = np.arange(1, len(g) + 1)
    top = g.head(15)
    summary["win8_share_from_1996"] = {
        "top15": [f"{r.short} ({int(r.true_year)}, {r.cls})" for r in top.itertuples()],
        "most_recent_concept_top15": most_recent(g.assign(rank=g["rank96"]), 15),
        "most_recent_concept_top50": most_recent(g.assign(rank=g["rank96"]), 50),
        "yamins2014_rank": int(
            g.loc[g["short"].str.startswith("Yamins et al., perf"), "rank96"].iloc[0]
        ),
    }

    # ---------------------------------------------------- recency summary, all variants
    def fmt(d):
        return "none" if d is None else f"{d['work']} ({d['year']}, #{d['rank']})"

    md += [
        "#### Most recent conceptual work, every ranking",
        "",
        "| Ranking | Concepts in top 15 | Most recent concept, top 15 | Concepts after 2005, "
        "top 15 / top 50 | Most recent concept, top 50 |",
        "|-|-:|-|-:|-|",
    ]
    for name, label in {**PRIMARY, **SENS}.items():
        t15, t50 = summary[name]["top15"], summary[name]["top50"]
        md.append(
            f"| {label} | {t15['n_concepts']} | {fmt(t15['most_recent_concept'])} | "
            f"{len(t15['concepts_after_2005'])} / {len(t50['concepts_after_2005'])} | "
            f"{fmt(t50['most_recent_concept'])} |"
        )
    md.append("")

    md += [
        "#### Publication year of the top 100",
        "",
        "| Ranking | Median (IQR) | After 2005 | Concepts | Concepts after 2005 | <1990 | 1990-95 "
        "| 1996-00 | 2001-05 | 2006-10 | 2011-15 | 2016-20 | 2021-26 |",
        "|-|-|-:|-:|-:|-:|-:|-:|-:|-:|-:|-:|-:|",
    ]
    for name, label in FIG.items():
        d = dist[name]
        b = d["bins"]
        md.append(
            f"| {label} | {d['median_year']:.0f} ({d['iqr'][0]:.0f}-{d['iqr'][1]:.0f}) | "
            f"{d['n_after_2005']} | {d['by_class'].get('concept', 0)} | "
            f"{d['concepts_after_2005']} | " + " | ".join(str(v) for v in b.values()) + " |"
        )
    md.append("")

    md += [
        "#### Where the published top 15 land",
        "",
        "| Published # | Work | Year | Class | Per-year rate | Fixed window 8 y | "
        "Growth-normalised window | Growth-normalised rate |",
        "|-:|-|-:|-|-:|-:|-:|-:|",
    ]
    for r in land:

        def rk_(v):
            return "n/a (after 2015)" if v is None else str(v)

        md.append(
            f"| {r['orig']} | {r['work']} | {r['year']} | {r['class']} | {rk_(r['rate'])} | "
            f"{rk_(r['win8'])} | {rk_(r['win8_share'])} | {rk_(r['rate_share'])} |"
        )
    md.append("")

    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    (RESULTS / "tables.md").write_text("\n".join(md) + "\n")
    for name in list(PRIMARY) + list(SENS):
        s15, s50 = summary[name]["top15"], summary[name]["top50"]
        print(
            f"{name:15s} top15: n_concepts={s15['n_concepts']:2d} most_recent={s15['most_recent_concept']}"
            f"\n{'':15s}        after2005={s15['concepts_after_2005']}"
            f"\n{'':15s} top50: most_recent={s50['most_recent_concept']} "
            f"n_after2005={len(s50['concepts_after_2005'])}"
        )
    print(json.dumps(dist, indent=1, default=str))
    print(pd.DataFrame(land).to_string())

    # ------------------------------------------------------------------------- figure
    apply_style()
    colors = {
        "concept": TRANSMITTER["mustard"],
        "method": TRANSMITTER["purple"],
        "tool": TRANSMITTER["teal"],
        "book": TRANSMITTER["muted"],
        "artefact": TRANSMITTER["grid"],
    }
    labels = {
        "concept": "Concept (claim about brains or minds)",
        "method": "ML method (model, algorithm, ML review)",
        "tool": "Tool (software, data, benchmark, analysis method)",
        "book": "Textbook typed as article",
        "artefact": "Merged or generic record",
    }
    years = np.arange(1988, 2027)  # 1988 = "before 1990" bin (Miller 1956, Ebbinghaus 1885)
    fig, axes = plt.subplots(4, 1, figsize=(9.5, 10.8), sharex=True, sharey=True)
    for ax, (name, label) in zip(axes, FIG.items(), strict=True):
        g = R[name].head(100).copy()
        g["plot_year"] = g["true_year"].where(g["true_year"] >= 1990, 1988)
        bottom = np.zeros(len(years))
        for c in CLASSES:
            h = g[g["cls"] == c]["plot_year"].value_counts().reindex(years, fill_value=0)
            ax.bar(
                years,
                h.values,
                bottom=bottom,
                width=0.82,
                color=colors[c],
                label=labels[c],
                edgecolor="none",
            )
            bottom += h.values
        ax.axvline(2005.5, color=TRANSMITTER["crimson"], lw=1.1, ls="--")
        d = dist[name]
        ax.set_title(
            f"{label}\ntop 100: median year {d['median_year']:.0f}; "
            f"{d['concepts_after_2005']} concepts published after 2005",
            loc="left",
            fontsize=10,
            color=TRANSMITTER["navy"],
        )
        if name in ("win8", "win8_share"):
            ax.axvspan(2015.5, 2026.7, color=TRANSMITTER["grid"], alpha=0.7, lw=0)
        if name == "rate":
            ax.axvspan(2023.5, 2026.7, color=TRANSMITTER["grid"], alpha=0.7, lw=0)
        ax.set_ylabel("works")
    ymax = max(ax.get_ylim()[1] for ax in axes) + 3
    for ax in axes:
        ax.set_ylim(0, ymax)
    for ax in axes[2:]:
        ax.text(
            2021.1,
            ymax * 0.93,
            "not eligible:\nwindow would close\nafter 2023",
            ha="center",
            va="top",
            fontsize=8,
            color=TRANSMITTER["gray"],
        )
    axes[0].text(
        2005.8, ymax * 0.97, "after 2005", fontsize=8.5, color=TRANSMITTER["crimson"], va="top"
    )
    axes[0].legend(loc="upper left", fontsize=8, frameon=False, ncol=1)
    axes[-1].set_xlabel("first publication year")
    axes[-1].set_xticks([1988, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025])
    axes[-1].set_xticklabels(
        ["<1990", "1990", "1995", "2000", "2005", "2010", "2015", "2020", "2025"]
    )
    axes[-1].set_xlim(1987.2, 2026.8)
    fig.suptitle(
        "Publication year of the 100 strongest bridge works, with citation age controlled",
        x=0.02,
        ha="left",
        fontsize=13,
        fontweight="bold",
        color=TRANSMITTER["navy"],
    )
    fig.text(
        0.02,
        0.004,
        "Source: OpenAlex snapshot 2026-03-30; extended classifier; published "
        "eligibility rules (Supplement S3). Score = harmonic mean of neuroscience and AI "
        "citations.",
        fontsize=7.5,
        style="italic",
        color=TRANSMITTER["gray"],
    )
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES_DIR / "fig_top100_years.svg")
    fig.savefig(FIGURES_DIR / "fig_top100_years.png", dpi=200, transparent=True)
    fig.savefig(FIGURES_DIR / "fig_top100_years-onwhite.png", dpi=200, facecolor="white")
    print("figure written")


if __name__ == "__main__":
    main()

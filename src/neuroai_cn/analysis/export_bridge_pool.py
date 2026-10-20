"""Export the eligibility funnel and ceiling effects of the bridge-paper pool to results/bridge/ (supplement S5).

Reads the pipeline's candidate table (`corrections/20260508/q4_v3_extended_full.parquet`, the 133,763
papers with at least five classified citations from each side) and writes small CSV files that the
supplement quotes: the step-by-step counts of the eligibility filters (`eligibility_funnel.csv`), the
top 40 papers by harmonic score in the neuroscience-or-AI pool with the 10,000-citation ceiling switched
off and a flag for the papers the ceiling removes (`ceiling_effect_top40.csv`), the field labels of
the highest-scoring papers of the unfiltered pool (`unfiltered_top_papers.csv`), the publication-year
composition of the eligible pool by tier and era (`era_composition.csv`), the track, era and paper-type
counts of the 860 hand-labelled papers of the clustering analysis, read from the persisted
classification (`clustered_set_composition.csv`; that set is the top 1,000 papers of the unfiltered
pool minus 140 plasma-physics papers, not the eligible pool), and one-number-per-row facts, including
two real papers that are heavily cited by one side only (`pool_numbers.csv`).
Nothing is edited by hand and the export is deterministic. Run from the repository root:

    python -m neuroai_cn.analysis.export_bridge_pool

The paper-type and book filters that Table S1 applies after the eligibility step need a database
lookup and are not repeated here, so the "no ceiling" table is a ranking of eligible works before
those filters.
"""

from __future__ import annotations

import json

import pandas as pd

from .. import config

CORR = config.DERIVED_DIR / "corrections" / "20260508"
OUT = config.RESULTS_DIR / "bridge"
CEILING = 10_000
N_TOP = 40
TIER_SIZES = (100, 1000)
ERAS = (
    ("before_2012", None, 2011),
    ("2012_2015", 2012, 2015),
    ("2016_2019", 2016, 2019),
    ("2020_onward", 2020, None),
)


def _era_counts(years: pd.Series) -> dict[str, int]:
    out = {}
    for name, lo, hi in ERAS:
        m = pd.Series(True, index=years.index)
        if lo is not None:
            m &= years >= lo
        if hi is not None:
            m &= years <= hi
        out[name] = int(m.sum())
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    full = pd.read_parquet(CORR / "q4_v3_extended_full.parquet")
    full = full.sort_values(["B_harmonic", "work_id"], ascending=[False, True]).reset_index(
        drop=True
    )
    full["rank_unfiltered"] = full.index + 1

    # ---- funnel -------------------------------------------------------------------------------
    field = full["bridge_paper_field"]
    na = full[field.isin(["neuro", "ai"])]
    elig = na[na["c_total_classified"] < CEILING]
    funnel = pd.DataFrame(
        [
            ("gate: at least 5 classified citations from each side", len(full), 0),
            (
                "own field label neuro or ai (drops other and unknown)",
                len(na),
                len(full) - len(na),
            ),
            (
                "classified citations under the 10,000 ceiling (E2)",
                len(elig),
                len(na) - len(elig),
            ),
        ],
        columns=["step", "n_remaining", "n_removed"],
    )
    funnel.to_csv(OUT / "eligibility_funnel.csv", index=False)

    # ---- ceiling effect -------------------------------------------------------------------------
    na_sorted = na.sort_values(["B_harmonic", "work_id"], ascending=[False, True]).reset_index(
        drop=True
    )
    top = na_sorted.head(N_TOP).copy()
    top.insert(0, "rank_no_ceiling", range(1, len(top) + 1))
    top["removed_by_ceiling"] = top["c_total_classified"] >= CEILING
    top["neuro_share"] = top["c_neuro"] / (top["c_neuro"] + top["c_ai"])
    top[
        [
            "rank_no_ceiling",
            "title",
            "publication_year",
            "bridge_paper_field",
            "c_neuro",
            "c_ai",
            "c_total_classified",
            "B_harmonic",
            "neuro_share",
            "removed_by_ceiling",
            "work_id",
        ]
    ].to_csv(OUT / "ceiling_effect_top40.csv", index=False)

    # ---- unfiltered top papers --------------------------------------------------------------------
    cols = [
        "rank_unfiltered",
        "title",
        "publication_year",
        "bridge_paper_field",
        "c_neuro",
        "c_ai",
        "c_total_classified",
        "B_harmonic",
        "work_id",
    ]
    full.head(1000)[cols].head(20).to_csv(OUT / "unfiltered_top_papers.csv", index=False)

    # ---- era composition of the eligible pool ----------------------------------------------------
    elig_sorted = elig.sort_values(["B_harmonic", "work_id"], ascending=[False, True])
    rows = []
    for label, sub in [(f"top_{n}", elig_sorted.head(n)) for n in TIER_SIZES] + [
        ("all_eligible", elig_sorted)
    ]:
        counts = _era_counts(sub["publication_year"])
        rows.append(
            {
                "tier": label,
                "n": len(sub),
                "median_year": float(sub["publication_year"].median()),
                **{f"n_{k}": v for k, v in counts.items()},
            }
        )
    pd.DataFrame(rows).to_csv(OUT / "era_composition.csv", index=False)

    # ---- one number per row ------------------------------------------------------------------------
    s1 = pd.read_csv(OUT / "table_s1_papers.csv")
    b15 = float(s1["B"].iloc[14])
    top1000 = full.head(1000)
    dropped_na = na[na["c_total_classified"] >= CEILING]
    nums: dict[str, object] = {
        "n_gate": len(full),
        "n_other_label_over_ceiling": int(
            ((field == "other") & (full["c_total_classified"] >= CEILING)).sum()
        ),
        "n_dropped_by_ceiling": len(dropped_na),
        "n_dropped_by_ceiling_ai": int((dropped_na["bridge_paper_field"] == "ai").sum()),
        "n_dropped_by_ceiling_neuro": int((dropped_na["bridge_paper_field"] == "neuro").sum()),
        "n_dropped_above_table_s1_rank15": int((dropped_na["B_harmonic"] > b15).sum()),
        "table_s1_rank15_B": b15,
        "n_top15_no_ceiling_removed_by_ceiling": int(top.head(15)["removed_by_ceiling"].sum()),
        "unfiltered_top1000_n_other": int((top1000["bridge_paper_field"] == "other").sum()),
        "unfiltered_top1000_n_ai": int((top1000["bridge_paper_field"] == "ai").sum()),
        "unfiltered_top1000_n_neuro": int((top1000["bridge_paper_field"] == "neuro").sum()),
        "n_eligible_B_ge_1000": int((elig["B_harmonic"] >= 1000).sum()),
        "n_eligible_B_ge_100": int((elig["B_harmonic"] >= 100).sum()),
        "n_eligible_both_sides_ge_100": int(
            ((elig["c_neuro"] >= 100) & (elig["c_ai"] >= 100)).sum()
        ),
        "max_B_unfiltered": float(full["B_harmonic"].max()),
    }
    ai_skew = elig[elig["c_ai"] >= 1000].assign(r=lambda d: d.c_ai / d.c_neuro)
    ai_skew = ai_skew.sort_values(["r", "work_id"], ascending=[False, True]).iloc[0]
    neuro_skew = elig[elig["c_neuro"] >= 1000].assign(r=lambda d: d.c_neuro / d.c_ai)
    neuro_skew = neuro_skew.sort_values(["r", "work_id"], ascending=[False, True]).iloc[0]
    for tag, row in (("ai_skew_example", ai_skew), ("neuro_skew_example", neuro_skew)):
        nums[f"{tag}_title"] = row["title"]
        nums[f"{tag}_year"] = int(row["publication_year"])
        nums[f"{tag}_c_neuro"] = int(row["c_neuro"])
        nums[f"{tag}_c_ai"] = int(row["c_ai"])
        nums[f"{tag}_B"] = float(row["B_harmonic"])
    # ---- the 860 hand-labelled papers of the clustering analysis -------------------------------------
    cl = pd.read_parquet(CORR / "q4_classified_nodes_v2.parquet")
    report = json.loads((CORR / "q4_reclassify_v2_report.json").read_text())
    comp = []
    for track, g in cl.groupby("track"):
        comp.append(("track", track, len(g), float(g["B_harmonic"].mean())))
    for ptype, g in cl.groupby("paper_type"):
        comp.append(("paper_type", ptype, len(g), float(g["B_harmonic"].mean())))
    for name, lo, hi in ERAS:
        m = pd.Series(True, index=cl.index)
        if lo is not None:
            m &= cl["publication_year"] >= lo
        if hi is not None:
            m &= cl["publication_year"] <= hi
        comp.append(("era", name, int(m.sum()), float(cl.loc[m, "B_harmonic"].mean())))
    comp_df = pd.DataFrame(comp, columns=["kind", "label", "n", "mean_B"])
    comp_df["share_pct"] = 100 * comp_df["n"] / len(cl)
    comp_df.to_csv(OUT / "clustered_set_composition.csv", index=False)
    manifestos = cl[cl["track"] == "Bridge manifestos & theory"].sort_values("publication_year")
    nums["clustered_n"] = len(cl)
    nums["clustered_n_dropped_physics"] = int(report["n_dropped_physics"])
    nums["clustered_median_year"] = float(cl["publication_year"].median())
    nums["clustered_n_field_other"] = int((cl["bridge_paper_field"] == "other").sum())
    nums["clustered_n_over_ceiling"] = int((cl["c_neuro"] + cl["c_ai"] >= CEILING).sum())
    for i, (_, r) in enumerate(manifestos.iterrows(), 1):
        nums[f"clustered_manifesto_{i}_year"] = int(r["publication_year"])
        nums[f"clustered_manifesto_{i}_title"] = r["title"]
    pd.DataFrame({"key": list(nums), "value": list(nums.values())}).to_csv(
        OUT / "pool_numbers.csv", index=False
    )


if __name__ == "__main__":
    main()

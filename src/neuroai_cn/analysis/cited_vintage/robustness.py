"""Robustness check that can fail: drop individually identified AI works from the cited side.

The rule is declared in ``definitions.py`` (module docstring) before any result was inspected:

    (a) remove every cited work whose title matches ``definitions.AI_TITLE_REGEX`` (generous, so it
        also removes legitimate neuroscience with "neural network" in the title);
    (b) from the survivors of (a), take the 25 most-cited works of each period (2010-2019 and
        2020-2025; citations counted as edges from AI papers in the period) and remove those that,
        on reading the title, are AI or machine-learning methods papers. The decisions are frozen in
        ``MANUAL_REMOVALS`` below, each with its reason and a tier (clear, or borderline for
        computational models a reader could file either way; borderline works are removed only in
        the last stage). ``--inspect`` writes the lists that were read.

The primary-topic half of the rule ("primary topic puts them in AI under the extended classifier")
is empty by construction, because the classifier tests field 28 first; ``--inspect`` also writes the
count (zero) as a check. The secondary-topic half is the EXCLUSIVE cited set of ``vintage.py``.

The check FAILS (is a finding) if, in any period, the cognitive-neuroscience share of cited edges
moves by more than 2 percentage points, the median cited year by more than 1 year, or the share
published in 2005 or earlier by more than 2 percentage points, relative to the same cited set before
removal. Both cited sets (exclusive and unrestricted) and three stages (regex only, regex plus
manual, and the baseline) are written to ``results/vintage/robustness.csv``; every removed work to
``results/vintage/removed_works.csv``.

    python -m neuroai_cn.analysis.cited_vintage.robustness --inspect
    python -m neuroai_cn.analysis.cited_vintage.robustness
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ... import config
from ...audits.extended_classifier import AI_SUBFIELD_1702, AI_SUBFIELD_1707
from . import vintage
from .definitions import AI_TITLE_REGEX, COGNITIVE_SUBFIELD, PERIODS

RESULTS = config.RESULTS_DIR / "vintage"
DERIVED = config.DERIVED_DIR / "vintage"
TOP_N = 25
INSPECT_PERIODS = ("2010-2019", "2020-2025")

# Frozen after reading results/vintage/top25_inspection.csv (titles only, before any removal
# statistics were computed): OpenAlex work id -> (tier, reason). Tier "clear" is an AI, machine-
# learning or computer-vision algorithm, dataset or method paper; tier "borderline" is a
# computational or cognitive model with an engineering flavour (saliency models, cognitive
# architectures, neuromorphic circuits, modelling software) that a reader could file either way.
# The borderline works are removed only in the strictest stage.
W = "https://openalex.org/"
MANUAL_REMOVALS: dict[str, tuple[str, str]] = {
    W + "W2113606819": ("clear", "Efficient sparse coding algorithms: ML method (NIPS)"),
    W + "W2125127226": ("clear", "Facial-expression analysis database: computer-vision dataset"),
    W + "W1576452626": ("clear", "Neuro-dynamic programming: reinforcement-learning monograph"),
    W + "W1924619199": ("clear", "A neural algorithm of artistic style: deep-learning method"),
    W + "W2166761907": ("clear", "Contextual priming for object detection: computer vision"),
    W + "W2144468361": ("clear", "Image quality assessment: image-processing method"),
    W + "W2003856922": ("clear", "Affective image classification: ML/computer vision"),
    W + "W2893425640": ("clear", "Semantics from corpora contain human-like biases: NLP/AI"),
    W + "W4312820606": ("clear", "MetaFormer: deep-learning architecture"),
    W + "W2545656684": ("clear", "A learned representation for artistic style: deep learning"),
    W + "W2964122153": ("clear", "PixelCNN++: deep generative model"),
    W + "W2054802006": ("borderline", "Itti-Koch-Niebur saliency model (IEEE TPAMI)"),
    W + "W2046863527": ("borderline", "Modeling attention to salient proto-objects"),
    W + "W1969258103": ("borderline", "Modeling the role of salience in overt attention"),
    W + "W2136518234": ("borderline", "An integrated theory of the mind (cognitive architecture)"),
    W + "W2055111849": ("borderline", "Components of bottom-up gaze allocation (saliency)"),
    W + "W2039546655": ("borderline", "Bayesian surprise attracts human attention (saliency)"),
    W + "W2119228922": ("borderline", "Visual correlates of fixation selection (saliency)"),
    W + "W2036963181": ("borderline", "Connectionist models of recognition memory"),
    W + "W1572063013": ("borderline", "Cortex-inspired silicon circuit (neuromorphic)"),
    W + "W2065125569": ("borderline", "Nengo: Python tool for brain models (software)"),
}

THRESHOLDS = {"share_pp": 2.0, "median_years": 1.0}


def _period_counts(edges: pd.DataFrame) -> pd.DataFrame:
    """Cited-work-level edge counts per period (AI papers citing neuroscience works)."""
    e = edges[edges["citing_cls"] == "ai"]
    cols = {}
    for p, (a, b) in PERIODS.items():
        cols[f"n_{p}"] = e[e["citing_year"].between(a, b)].groupby("cited_id").size()
    return pd.DataFrame(cols).fillna(0).astype(int)


def identify(edges: pd.DataFrame, works: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (candidates table with rule flags, top-25 inspection table)."""
    nw = works[works["cls"] == "neuro"].set_index("id")
    counts = _period_counts(edges)
    t = nw.join(counts, how="inner")
    t["regex_hit"] = t["title"].fillna("").str.contains(AI_TITLE_REGEX, case=False, regex=True)
    surv = t[~t["regex_hit"]]
    tops = []
    for p in INSPECT_PERIODS:
        top = surv.sort_values(f"n_{p}", ascending=False).head(TOP_N).copy()
        top["period"] = p
        top["rank"] = range(1, len(top) + 1)
        tops.append(top)
    insp = pd.concat(tops).reset_index()[
        [
            "period",
            "rank",
            "id",
            "title",
            "year",
            "sf_name",
            "topic_name",
            "dual",
            "cited_by_count",
            "n_2010-2019",
            "n_2020-2025",
        ]
    ]
    return t, insp


def apply_stage(edges: pd.DataFrame, removed_ids: set[str]) -> pd.DataFrame:
    return edges[~edges["cited_id"].isin(removed_ids)]


def cell_stats(edges: pd.DataFrame, cited_set: str) -> dict[str, dict]:
    """Per period: headline vintage statistics and the cognitive share, AI -> neuroscience, all types."""
    e = edges[edges["citing_cls"] == "ai"]
    m = vintage.build_matrix(e)
    out = {}
    for p, period in PERIODS.items():
        s = vintage.select(m, "ai_to_neuro", cited_set, "all", "extended", period)
        st = vintage.stats_from_counts(s)
        n = s["n"].sum()
        st["cognitive_share"] = float(s.loc[s["cited_sf_id"] == COGNITIVE_SUBFIELD, "n"].sum() / n)
        out[p] = st
    return out


def run(edges: pd.DataFrame, works: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    t, _ = identify(edges, works)
    regex_ids = set(t.index[t["regex_hit"]])
    clear_ids = {i for i, (tier, _) in MANUAL_REMOVALS.items() if tier == "clear"}
    manual_ids = set(MANUAL_REMOVALS)
    stages = {
        "baseline": set(),
        "regex_titles": regex_ids,
        "regex_plus_clear_manual": regex_ids | clear_ids,
        "regex_plus_clear_plus_borderline": regex_ids | manual_ids,
    }
    rows = []
    base: dict[tuple[str, str], dict] = {}
    for stage, ids in stages.items():
        kept = apply_stage(edges, ids)
        for cited_set in ("exclusive", "unrestricted"):
            st = cell_stats(kept, cited_set)
            for p, v in st.items():
                if stage == "baseline":
                    base[(cited_set, p)] = v
                b = base[(cited_set, p)]
                rows.append(
                    {
                        "stage": stage,
                        "cited_set": cited_set,
                        "period": p,
                        "n_removed_works": len(ids),
                        "n_edges": v["n_edges"],
                        "cognitive_share": v["cognitive_share"],
                        "median_cited_year": v["median_cited_year"],
                        "share_le2005": v["share_le2005"],
                        "mean_age": v["mean_age"],
                        "d_cognitive_share_pp": 100 * (v["cognitive_share"] - b["cognitive_share"]),
                        "d_median_years": v["median_cited_year"] - b["median_cited_year"],
                        "d_share_le2005_pp": 100 * (v["share_le2005"] - b["share_le2005"]),
                    }
                )
    r = pd.DataFrame(rows)
    r["fails"] = (
        (r["d_cognitive_share_pp"].abs() > THRESHOLDS["share_pp"])
        | (r["d_median_years"].abs() > THRESHOLDS["median_years"])
        | (r["d_share_le2005_pp"].abs() > THRESHOLDS["share_pp"])
    )
    removed = t.loc[sorted(regex_ids | manual_ids)].reset_index()
    removed["rule"] = [
        ("manual (" + MANUAL_REMOVALS[i][0] + "): " + MANUAL_REMOVALS[i][1])
        if i in MANUAL_REMOVALS
        else "title regex"
        for i in removed["id"]
    ]
    removed = removed[
        [
            "id",
            "title",
            "year",
            "sf_name",
            "topic_name",
            "dual",
            "cited_by_count",
            "n_2010-2019",
            "n_2020-2025",
            "n_2020-2023",
            "rule",
        ]
    ].sort_values(["n_2020-2025", "n_2010-2019"], ascending=False)
    return r, removed


def shift_table(r: pd.DataFrame) -> pd.DataFrame:
    """The between-period shift (the quantity claim 2 is about) at every stage."""
    rows = []
    for (stage, cited_set), g in r.groupby(["stage", "cited_set"], sort=False):
        g = g.set_index("period")
        for late in ("2020-2025", "2020-2023"):
            rows.append(
                {
                    "stage": stage,
                    "cited_set": cited_set,
                    "comparison": f"2010-2019 -> {late}",
                    "median_shift_years": g.loc[late, "median_cited_year"]
                    - g.loc["2010-2019", "median_cited_year"],
                    "share_le2005_change_pp": 100
                    * (g.loc[late, "share_le2005"] - g.loc["2010-2019", "share_le2005"]),
                    "cognitive_share_change_pp": 100
                    * (g.loc[late, "cognitive_share"] - g.loc["2010-2019", "cognitive_share"]),
                    "median_2010_2019": g.loc["2010-2019", "median_cited_year"],
                    f"median_{late}": g.loc[late, "median_cited_year"],
                }
            )
    t = pd.DataFrame(rows)
    return t[
        [
            "stage",
            "cited_set",
            "comparison",
            "median_shift_years",
            "share_le2005_change_pp",
            "cognitive_share_change_pp",
        ]
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--inspect", action="store_true")
    ap.add_argument("--src", type=Path, default=DERIVED)
    a = ap.parse_args()
    edges = pd.read_parquet(a.src / "cross_edges.parquet")
    works = pd.read_parquet(a.src / "cited_works.parquet")
    RESULTS.mkdir(parents=True, exist_ok=True)
    if a.inspect:
        t, insp = identify(edges, works)
        insp.to_csv(RESULTS / "top25_inspection.csv", index=False)
        print("regex hits:", int(t["regex_hit"].sum()), "of", len(t), "cited neuroscience works")
        print(
            "primary-topic AI inside field 28:",
            int(
                (
                    (works["cls"] == "neuro")
                    & works["sf_id"].isin([AI_SUBFIELD_1702, AI_SUBFIELD_1707])
                ).sum()
            ),
            "(check; the classifier tests field 28 first, so none can be AI)",
        )
        with pd.option_context("display.max_colwidth", 110, "display.width", 250):
            print(insp[["period", "rank", "id", "title", "year", "dual"]].to_string(index=False))
        return
    r, removed = run(edges, works)
    r.to_csv(RESULTS / "robustness.csv", index=False)
    shift_table(r).to_csv(RESULTS / "robustness_shift.csv", index=False)
    removed.to_csv(RESULTS / "removed_works.csv", index=False)


if __name__ == "__main__":
    main()

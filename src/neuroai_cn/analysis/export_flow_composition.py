"""Export the composition of the neuroscience-citing-AI flow to committed CSV files.

Supplement S4 describes what neuroscience papers cite when they cite AI: the OpenAlex topic of
every cited AI work, per citing year, grouped into six hand-assigned categories, under the extended
AI definition of the article and under the curated 35-topic core. The counts were computed by
``python -m neuroai_cn.audits.flow_composition --classifier {extended,strict}`` and the list of the
200 most-cited AI works by ``python -m neuroai_cn.audits.flow_concentration`` (both scan the
citation graph and wrote small parquet and JSON files under ``DERIVED_DIR``). This script only reads
those small files, attaches the category of each topic from ``CATEGORIES`` in
``neuroai_cn.figures.flow_composition_fig`` (the single source of the grouping), checks that the
yearly totals equal the cross-field counts ``n_to_target`` of ``results/flow/or_by_year.csv``
(extended) and ``results/flow/sensitivity_strict_or_by_year.csv`` (strict), and writes three CSV
files to ``results/flow/`` in a fixed row order. It never touches the DuckDB mirror. Run:

    python -m neuroai_cn.analysis.export_flow_composition
"""

from __future__ import annotations

import json

import pandas as pd

from .. import config
from ..figures.flow_composition_fig import ORDER, TOPIC_TO_CAT

SRC = config.DERIVED_DIR
FLOW = config.RESULTS_DIR / "flow"
OUT_TOPIC_YEAR = FLOW / "flow_composition_topic_year.csv"
OUT_HEAD = FLOW / "flow_composition_head.csv"
OUT_CONC = FLOW / "flow_concentration.csv"
CHECK_TABLES = {
    "extended": FLOW / "or_by_year.csv",
    "strict": FLOW / "sensitivity_strict_or_by_year.csv",
}


def topic_year() -> pd.DataFrame:
    """One row per classifier, citing year and cited AI topic, with its category and count."""
    parts = []
    for classifier, check in CHECK_TABLES.items():
        d = pd.read_parquet(SRC / f"flow_composition_{classifier}.parquet")
        d["category"] = d.topic.map(TOPIC_TO_CAT)
        missing = sorted(d.loc[d.category.isna(), "topic"].unique())
        if missing:
            raise SystemExit(f"[{classifier}] topics without a category: {missing}")
        ref = pd.read_csv(check)
        ref = ref[ref.direction == "neuro_to_ai"].set_index("year").n_to_target
        got = d.groupby("citing_year").n_cites.sum()
        if not got.reindex(ref.index, fill_value=0).astype(int).equals(ref.astype(int)):
            raise SystemExit(f"[{classifier}] yearly totals differ from {check.name}")
        d.insert(0, "classifier", classifier)
        parts.append(d)
    out = pd.concat(parts, ignore_index=True)
    out["category_order"] = out.category.map({c: i for i, c in enumerate(ORDER)})
    out = out.sort_values(["classifier", "citing_year", "category_order", "topic_id"])
    cols = ["classifier", "citing_year", "topic_id", "topic", "category", "n_cites"]
    return out[cols].reset_index(drop=True)


def head() -> pd.DataFrame:
    """The 200 AI works most cited by neuroscience papers (extended definition, citing 1990-2025)."""
    h = pd.read_parquet(SRC / "flow_concentration_head.parquet")
    h["category"] = h.topic.map(TOPIC_TO_CAT)
    h = h.rename(columns={"rnk": "rank"}).sort_values("rank")
    h["cum_cites"] = h.cum_cites.astype(int)
    cols = [
        "rank",
        "cited_work_id",
        "title",
        "publication_year",
        "topic_id",
        "topic",
        "category",
        "n_cites",
        "cum_cites",
    ]
    return h[cols].reset_index(drop=True)


def concentration() -> pd.DataFrame:
    """How many distinct cited AI works carry 50, 80, 90 and 95 percent of the flow."""
    j = json.loads((SRC / "flow_concentration.json").read_text())
    c = j["concentration"]
    rows = [
        {
            "citing_years": f"{j['era'][0]}-{j['era'][1]}",
            "quantile_of_citations": float(q),
            "n_works": v["n_works"],
            "share_of_works": v["share_of_works"],
            "total_edges": c["total_edges"],
            "n_distinct_cited_works": c["n_distinct_cited_works"],
        }
        for q, v in sorted(c["quantiles"].items())
    ]
    return pd.DataFrame(rows)


def main() -> None:
    FLOW.mkdir(parents=True, exist_ok=True)
    ty = topic_year()
    hd = head()
    if hd.n_cites.sum() > ty[ty.classifier == "extended"].n_cites.sum():
        raise SystemExit("head table exceeds the flow total")
    ty.to_csv(OUT_TOPIC_YEAR, index=False)
    hd.to_csv(OUT_HEAD, index=False)
    concentration().to_csv(OUT_CONC, index=False)
    for p in (OUT_TOPIC_YEAR, OUT_HEAD, OUT_CONC):
        print(f"wrote {p.relative_to(config.REPO_ROOT)}")


if __name__ == "__main__":
    main()

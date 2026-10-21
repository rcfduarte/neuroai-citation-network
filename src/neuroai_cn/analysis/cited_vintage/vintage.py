"""Vintage statistics of the cited side, in both directions (definitions: see ``definitions.py``).

    python -m neuroai_cn.analysis.cited_vintage.vintage   # from the edge table (needs build)

Every table except the distinct-work counts can be recomputed from the tracked matrix alone with
``summary_table``, ``subfield_table`` and ``by_year_table`` (the tests do this).

Writes to ``results/vintage/`` (tracked):

    matrix_cited_vintage.csv   citation-edge counts by direction, citing flags, citing year, cited
                               year, cited subfield and the cited work's secondary-topic flag; every
                               other table except the distinct-work counts is a function of this
    vintage_summary.csv        per direction, cited set, citing definition, classifier and period
    subfield_breakdown.csv     the share of every OpenAlex subfield of the cited side, per period
    vintage_by_year.csv        median, quartiles, mean age and share <= 2005 by citing year
    claims.json                the two claims against the recomputed values
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ... import config
from .definitions import (
    CELLULAR_SUBFIELD,
    COGNITIVE_SUBFIELD,
    PERIODS,
)

RESULTS = config.RESULTS_DIR / "vintage"
DERIVED = config.DERIVED_DIR / "vintage"
MATRIX = RESULTS / "matrix_cited_vintage.csv"
KEYS = [
    "direction",
    "citing_strict",
    "citing_ar",
    "citing_year",
    "cited_year",
    "cited_sf_id",
    "cited_sf_name",
    "cited_dual",
]


def build_matrix(edges: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the edge-level cross-field table into the tracked count matrix."""
    e = edges.copy()
    e["direction"] = np.where(e["citing_cls"] == "ai", "ai_to_neuro", "neuro_to_ai")
    e["citing_strict"] = e["citing_strict"].astype(int)
    e["citing_ar"] = e["citing_type"].isin(["article", "review"]).astype(int)
    e["cited_dual"] = e["cited_dual"].astype(int)
    e = e.rename(columns={"sf_id": "cited_sf_id", "sf_name": "cited_sf_name"})
    m = e.groupby(KEYS, as_index=False).size().rename(columns={"size": "n"})
    return m.sort_values(KEYS).reset_index(drop=True)


def load_matrix(path: Path = MATRIX) -> pd.DataFrame:
    return pd.read_csv(path)


def select(
    m: pd.DataFrame,
    direction: str,
    cited_set: str,
    citing_def: str,
    classifier: str,
    period: tuple[int, int],
) -> pd.DataFrame:
    """Rows of the matrix for one analysis cell."""
    s = m[(m["direction"] == direction) & m["citing_year"].between(*period)]
    if cited_set == "exclusive":
        s = s[s["cited_dual"] == 0]
    if citing_def == "article_review":
        s = s[s["citing_ar"] == 1]
    if classifier == "strict35":
        s = s[s["citing_strict"] == 1]
    return s


def _kth(years: np.ndarray, cum: np.ndarray, k: int) -> int:
    return int(years[np.searchsorted(cum, k)])


def stats_from_counts(s: pd.DataFrame) -> dict:
    """Median, quartiles, mean age and old-share from a matrix subset (cited_year, citing_year, n)."""
    g = s.groupby("cited_year")["n"].sum().sort_index()
    n = int(g.sum())
    if n == 0:
        return {"n_edges": 0}
    years = g.index.to_numpy()
    cum = np.cumsum(g.to_numpy())
    median = (_kth(years, cum, (n + 1) // 2) + _kth(years, cum, n // 2 + 1)) / 2
    age_sum = int((s["n"] * (s["citing_year"] - s["cited_year"])).sum())
    old = g[g.index <= 2005].sum()
    old4 = g[g.index <= 2004].sum()
    return {
        "n_edges": n,
        "median_cited_year": median,
        "q1_cited_year": _kth(years, cum, int(np.ceil(0.25 * n))),
        "q3_cited_year": _kth(years, cum, int(np.ceil(0.75 * n))),
        "mean_age": age_sum / n,
        "n_le2005": int(old),
        "share_le2005": int(old) / n,
        "n_le2004": int(old4),
        "share_le2004": int(old4) / n,
        "n_future_dated": int(s.loc[s["cited_year"] > s["citing_year"], "n"].sum()),
    }


CELLS = [
    # (direction, cited_set, citing_def, classifier)
    ("ai_to_neuro", "exclusive", "all", "extended"),
    ("ai_to_neuro", "unrestricted", "all", "extended"),
    ("ai_to_neuro", "exclusive", "article_review", "extended"),
    ("ai_to_neuro", "unrestricted", "article_review", "extended"),
    ("ai_to_neuro", "unrestricted", "all", "strict35"),
    ("ai_to_neuro", "exclusive", "all", "strict35"),
    ("neuro_to_ai", "exclusive", "all", "extended"),
    ("neuro_to_ai", "unrestricted", "all", "extended"),
    ("neuro_to_ai", "exclusive", "article_review", "extended"),
    ("neuro_to_ai", "unrestricted", "article_review", "extended"),
]


def summary_table(m: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for direction, cited_set, citing_def, classifier in CELLS:
        for pname, period in PERIODS.items():
            s = select(m, direction, cited_set, citing_def, classifier, period)
            rows.append(
                {
                    "direction": direction,
                    "cited_set": cited_set,
                    "citing_def": citing_def,
                    "classifier": classifier,
                    "period": pname,
                    **stats_from_counts(s),
                }
            )
    return pd.DataFrame(rows)


def subfield_table(m: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for direction, cited_set, citing_def, classifier in CELLS:
        for pname, period in PERIODS.items():
            s = select(m, direction, cited_set, citing_def, classifier, period)
            g = s.groupby(["cited_sf_id", "cited_sf_name"])["n"].sum().reset_index()
            tot = g["n"].sum()
            g["share_edges"] = g["n"] / tot
            g = g.rename(columns={"n": "n_edges"}).sort_values("n_edges", ascending=False)
            for _, r in g.iterrows():
                rows.append(
                    {
                        "direction": direction,
                        "cited_set": cited_set,
                        "citing_def": citing_def,
                        "classifier": classifier,
                        "period": pname,
                        **r.to_dict(),
                    }
                )
    return pd.DataFrame(rows)


def by_year_table(m: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for direction, cited_set, citing_def, classifier in CELLS:
        if citing_def != "all" or classifier != "extended":
            continue
        for y in range(int(m["citing_year"].min()), int(m["citing_year"].max()) + 1):
            s = select(m, direction, cited_set, citing_def, classifier, (y, y))
            rows.append(
                {
                    "direction": direction,
                    "cited_set": cited_set,
                    "citing_year": y,
                    **stats_from_counts(s),
                }
            )
    return pd.DataFrame(rows)


def distinct_work_counts(edges: pd.DataFrame) -> pd.DataFrame:
    """Distinct cited works per analysis cell and per subfield (needs the edge-level table)."""
    e = edges.copy()
    e["direction"] = np.where(e["citing_cls"] == "ai", "ai_to_neuro", "neuro_to_ai")
    e["citing_ar"] = e["citing_type"].isin(["article", "review"]).astype(int)
    e["cited_dual"] = e["cited_dual"].astype(int)
    rows = []
    for direction, cited_set, citing_def, classifier in CELLS:
        for pname, (a, b) in PERIODS.items():
            s = e[(e["direction"] == direction) & e["citing_year"].between(a, b)]
            if cited_set == "exclusive":
                s = s[s["cited_dual"] == 0]
            if citing_def == "article_review":
                s = s[s["citing_ar"] == 1]
            if classifier == "strict35":
                s = s[s["citing_strict"]]
            tot = s["cited"].nunique()
            rows.append(
                {
                    "direction": direction,
                    "cited_set": cited_set,
                    "citing_def": citing_def,
                    "classifier": classifier,
                    "period": pname,
                    "sf_id": "ALL",
                    "n_cited_works": tot,
                }
            )
            for sf, n in s.groupby("sf_id")["cited"].nunique().items():
                rows.append(
                    {
                        "direction": direction,
                        "cited_set": cited_set,
                        "citing_def": citing_def,
                        "classifier": classifier,
                        "period": pname,
                        "sf_id": sf,
                        "n_cited_works": int(n),
                    }
                )
    return pd.DataFrame(rows)


def claims(summary: pd.DataFrame, sub: pd.DataFrame) -> dict:
    def cell(direction, cited_set, citing_def, classifier, period):
        r = summary[
            (summary["direction"] == direction)
            & (summary["cited_set"] == cited_set)
            & (summary["citing_def"] == citing_def)
            & (summary["classifier"] == classifier)
            & (summary["period"] == period)
        ]
        return r.iloc[0].to_dict()

    def share(cited_set, period, sf, classifier="extended"):
        r = sub[
            (sub["direction"] == "ai_to_neuro")
            & (sub["cited_set"] == cited_set)
            & (sub["citing_def"] == "all")
            & (sub["classifier"] == classifier)
            & (sub["period"] == period)
            & (sub["cited_sf_id"] == sf)
        ]
        return float(r["share_edges"].iloc[0]) if len(r) else 0.0

    def pct(x, digits=1):
        return f"{100 * x:.{digits}f}"

    a = cell("ai_to_neuro", "exclusive", "all", "extended", "2010-2019")
    b = cell("ai_to_neuro", "exclusive", "all", "extended", "2020-2025")
    cog = share("exclusive", "2020-2025", COGNITIVE_SUBFIELD, "strict35")
    cel = share("exclusive", "2020-2025", CELLULAR_SUBFIELD, "strict35")
    out = {
        "claim1_text": f"{pct(cog)} percent cognitive neuroscience, {pct(cel, 2)} percent cellular and "
        "molecular (AI papers 2020-2025; 35-topic core definition, exclusive cited set)",
        "claim2_text": f"median cited year {a['median_cited_year']:.0f} -> {b['median_cited_year']:.0f}; "
        f"share published in 2005 or earlier {pct(a['share_le2005'])}% -> {pct(b['share_le2005'])}% "
        "(AI papers 2010-2019 -> 2020-2025; extended definition, exclusive cited set)",
        "claim1": {},
        "claim2": {},
    }
    for classifier in ("extended", "strict35"):
        for cited_set in ("exclusive", "unrestricted"):
            for period in ("2020-2025", "2020-2023"):
                out["claim1"][f"{classifier}_{cited_set}_{period}"] = {
                    "cognitive_neuroscience_share": share(
                        cited_set, period, COGNITIVE_SUBFIELD, classifier
                    ),
                    "cellular_molecular_share": share(
                        cited_set, period, CELLULAR_SUBFIELD, classifier
                    ),
                }
    for label, args in {
        "extended_exclusive": ("ai_to_neuro", "exclusive", "all", "extended"),
        "extended_unrestricted": ("ai_to_neuro", "unrestricted", "all", "extended"),
        "extended_exclusive_article_review": (
            "ai_to_neuro",
            "exclusive",
            "article_review",
            "extended",
        ),
        "strict35_unrestricted_earlier_script": ("ai_to_neuro", "unrestricted", "all", "strict35"),
        "strict35_exclusive": ("ai_to_neuro", "exclusive", "all", "strict35"),
    }.items():
        out["claim2"][label] = {
            p: {
                k: cell(*args, p)[k]
                for k in (
                    "n_edges",
                    "median_cited_year",
                    "share_le2005",
                    "share_le2004",
                    "mean_age",
                )
            }
            for p in ("2010-2019", "2020-2025", "2020-2023")
        }
    return out


def write_all(m: pd.DataFrame, edges: pd.DataFrame | None) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    m.to_csv(MATRIX, index=False)
    summ = summary_table(m)
    sub = subfield_table(m)
    if edges is not None:
        dw = distinct_work_counts(edges)
        tot = dw[dw["sf_id"] == "ALL"].drop(columns="sf_id")
        summ = summ.merge(
            tot, on=["direction", "cited_set", "citing_def", "classifier", "period"], how="left"
        )
        per_sf = dw[dw["sf_id"] != "ALL"].rename(
            columns={"sf_id": "cited_sf_id", "n_cited_works": "n_cited_works"}
        )
        sub = sub.merge(
            per_sf,
            on=["direction", "cited_set", "citing_def", "classifier", "period", "cited_sf_id"],
            how="left",
        )
        sub["share_works"] = sub["n_cited_works"] / sub.groupby(
            ["direction", "cited_set", "citing_def", "classifier", "period"]
        )["n_cited_works"].transform("sum")
    summ.to_csv(RESULTS / "vintage_summary.csv", index=False)
    sub.to_csv(RESULTS / "subfield_breakdown.csv", index=False)
    by_year_table(m).to_csv(RESULTS / "vintage_by_year.csv", index=False)
    (RESULTS / "claims.json").write_text(json.dumps(claims(summ, sub), indent=1) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--edges", type=Path, default=DERIVED / "cross_edges.parquet")
    a = ap.parse_args()
    edges = pd.read_parquet(a.edges)
    write_all(build_matrix(edges), edges)


if __name__ == "__main__":
    main()

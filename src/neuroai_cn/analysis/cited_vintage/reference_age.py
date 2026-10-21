"""Reference-age profile of AI and neuroscience papers (test of the "short citation memory" claim).

A commentator argues that machine-learning papers have a short citation memory: in a small spot
check, about two-thirds of the references of contemporary AI conference papers were five years old
or younger, median age three years, against eight years for neuroscience journal papers. This
module measures the same quantities on the whole classified corpus.

Definitions, fixed in advance
    * Citing papers: AI (extended classifier) or neuroscience (field 28), citing years 2000-2023;
      2024-2025 are written out but flagged provisional. Two type definitions: article and review
      only (the comparison of the claim is between conference and journal papers) and every OpenAlex type.
    * References: every reference of the citing paper that resolves to a work with a publication
      year in the mirror, not only cross-field ones; and, separately, only those whose cited work
      is in the other field (AI paper citing neuroscience, neuroscience paper citing AI).
    * Age = citing year minus cited year. References dated after the citing year (record errors)
      are dropped and counted. Median = mean of the two middle ages; 90th percentile = smallest age
      with at least 90 percent of references at or below it; shares of references aged at most 5
      and at most 10 years.
    * The mirror holds works from 1990 only, so references to older works do not resolve and
      cannot be aged. The truncation grows with the citing year (for a 2000 paper every reference
      older than ten years is lost), so the old tail is understated, and shares of recent
      references overstated, most strongly for the early years. The table
      ``reference_list_coverage.csv`` reports, by year, how many references were listed on the
      papers and what fraction resolved to a dated work, and what share of papers have any
      reference list at all (conference papers may be under-indexed).

Run ``python -m neuroai_cn.analysis.cited_vintage.reference_age`` after the ``refage`` stage of
``build`` (reads its outputs from ``DERIVED_DIR/vintage``) to write the tracked tables to
``results/vintage``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ... import config

RESULTS = config.RESULTS_DIR / "vintage"
DERIVED = config.DERIVED_DIR / "vintage"
MATRIX = RESULTS / "matrix_reference_age.csv"
YEAR_MIN, YEAR_MAX, PROVISIONAL_FROM = 2000, 2025, 2024
POOLS = {
    "2000-2009": (2000, 2009),
    "2010-2019": (2010, 2019),
    "2020-2023": (2020, 2023),
    "2024-2025": (2024, 2025),
}
ZADOR = {
    "ai_conference_spot_check": {"share_le5": 2 / 3, "median_age": 3},
    "neuroscience_journal_spot_check": {"median_age": 8},
}


def age_stats(ages: np.ndarray, n: np.ndarray) -> dict:
    """Median, mean, p90 and shares at most 5 / 10 years from (age, count) pairs."""
    total = int(n.sum())
    if total == 0:
        return {"n_refs": 0}
    order = np.argsort(ages)
    a, c = ages[order], n[order]
    cum = np.cumsum(c)

    def kth(k: int) -> int:
        return int(a[np.searchsorted(cum, k)])

    return {
        "n_refs": total,
        "median_age": (kth((total + 1) // 2) + kth(total // 2 + 1)) / 2,
        "mean_age": float((a * c).sum() / total),
        "p90_age": kth(int(np.ceil(0.9 * total))),
        "share_le5": float(c[a <= 5].sum() / total),
        "share_le10": float(c[a <= 10].sum() / total),
    }


def _prepare(m: pd.DataFrame) -> pd.DataFrame:
    m = m.copy()
    m["age"] = m["citing_year"] - m["cited_year"]
    return m


def by_year_table(m: pd.DataFrame) -> pd.DataFrame:
    m = _prepare(m)
    rows = []
    for field in ("ai", "neuro"):
        for types in ("article_review", "all"):
            for scope in ("all_references", "to_other_field"):
                s = m[m["citing_cls"] == field]
                if types == "article_review":
                    s = s[s["ar"] == 1]
                if scope == "to_other_field":
                    s = s[s["cited_cls"] == ("neuro" if field == "ai" else "ai")]
                for y in range(YEAR_MIN, YEAR_MAX + 1):
                    sy = s[s["citing_year"] == y]
                    dropped = int(sy.loc[sy["age"] < 0, "n"].sum())
                    sy = sy[sy["age"] >= 0]
                    rows.append(
                        {
                            "citing_field": field,
                            "types": types,
                            "scope": scope,
                            "citing_year": y,
                            "provisional": y >= PROVISIONAL_FROM,
                            **age_stats(sy["age"].to_numpy(), sy["n"].to_numpy()),
                            "n_dropped_future_dated": dropped,
                        }
                    )
    return pd.DataFrame(rows)


def pooled_table(m: pd.DataFrame) -> pd.DataFrame:
    m = _prepare(m)
    rows = []
    for field in ("ai", "neuro"):
        for types in ("article_review", "all"):
            for scope in ("all_references", "to_other_field"):
                s = m[(m["citing_cls"] == field) & (m["age"] >= 0)]
                if types == "article_review":
                    s = s[s["ar"] == 1]
                if scope == "to_other_field":
                    s = s[s["cited_cls"] == ("neuro" if field == "ai" else "ai")]
                for name, (a, b) in POOLS.items():
                    sp = s[s["citing_year"].between(a, b)]
                    g = sp.groupby("age")["n"].sum()
                    rows.append(
                        {
                            "citing_field": field,
                            "types": types,
                            "scope": scope,
                            "period": name,
                            "provisional": a >= PROVISIONAL_FROM,
                            **age_stats(g.index.to_numpy(), g.to_numpy()),
                        }
                    )
    return pd.DataFrame(rows)


def coverage_table(m: pd.DataFrame, totals: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """Reference-list coverage by citing field, type definition and year."""
    dated = m.groupby(["citing_cls", "ar", "citing_year"])["n"].sum().rename("n_refs_dated")
    t = totals.set_index(["citing_cls", "ar", "citing_year"])
    r = raw.set_index(["citing_cls", "ar", "citing_year"])
    c = r.join(t).join(dated).reset_index()
    out = []
    for field in ("ai", "neuro"):
        for types in ("article_review", "all"):
            s = c[c["citing_cls"] == field]
            if types == "article_review":
                s = s[s["ar"] == 1]
            g = s.groupby("citing_year")[
                [
                    "n_works",
                    "n_with_reflist",
                    "n_refs_listed",
                    "n_edges",
                    "n_citing_with_edges",
                    "n_refs_dated",
                ]
            ].sum()
            g["citing_field"], g["types"] = field, types
            out.append(g.reset_index())
    o = pd.concat(out)
    o["share_with_reflist"] = o["n_with_reflist"] / o["n_works"]
    o["share_with_edges_in_mirror"] = o["n_citing_with_edges"] / o["n_works"]
    o["share_refs_dated"] = o["n_refs_dated"] / o["n_refs_listed"]
    cols = ["citing_field", "types", "citing_year"] + [
        c for c in o.columns if c not in ("citing_field", "types", "citing_year")
    ]
    return o[cols].sort_values(["citing_field", "types", "citing_year"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", type=Path, default=DERIVED)
    a = ap.parse_args()
    m = pd.read_csv(a.src / "matrix_reference_age.csv")
    totals = pd.read_csv(a.src / "edge_totals.csv")
    raw = pd.read_csv(a.src / "reflist_coverage_raw.csv")
    RESULTS.mkdir(parents=True, exist_ok=True)
    m.to_csv(MATRIX, index=False)
    by_year_table(m).to_csv(RESULTS / "reference_age_by_field.csv", index=False)
    pooled_table(m).to_csv(RESULTS / "reference_age_pooled.csv", index=False)
    coverage_table(m, totals, raw).to_csv(RESULTS / "reference_list_coverage.csv", index=False)


if __name__ == "__main__":
    main()

"""Do the NeuroAI "manifesto" papers follow the same citation curve as the overall flow?

Question (raised by a reviewer of the article): "do citations of the manifestos follow the
same curve? It would be interesting to see if AI researchers are influenced by our neuro
manifestos." The six manifesto and review papers listed in the article sidebar are identified by
DOI in ``MANIFESTOS`` below.

Definitions, fixed before the numbers were looked at
    * Work labels: the extended classifier on the work's own primary topic (neuroscience = field 28,
      AI = subfield 1702 minus 26 topics, plus 1707, plus T10502, else other), as in the main flow
      analysis. The label of each of the six is reported, not assumed.
    * Citations received in year y: citation edges whose citing paper was published in y, split by
      the citing paper's own label (ai, neuro, or other when it is neither).
    * Share of the flow: citations received from AI papers, divided by all AI-to-neuroscience
      citation edges that year (``n_to_target`` of ``ai_to_neuro`` in ``results/flow/or_by_year.csv``).
      The numerator is reported both for all six and for the subset the classifier labels
      neuroscience, because only the latter sit inside that denominator.
    * Odds-ratio check: the restricted odds ratio of ``audits/q1_v3_extended.py`` (observed share of
      cross-field references among own-field plus cross-field references, over the share expected
      from field sizes) recomputed with the six works removed as TARGET works: their incoming edges
      are removed from the counts of the matching cell (cross-field when the work is labelled in the
      target field, within-field when it is labelled like the citing field) and the work is removed
      from the population count of its own label in its publication year.
    * Curve comparison: Spearman correlation, over 2015-2023, of the year-over-year change in
      log(1 + x) of the manifesto citations received from AI papers against that of (a) the number of
      AI-to-neuroscience citation edges and (b) the restricted odds ratio. The p-value is exact
      (all 9! permutations of the nine changes, 2014->2015 through 2022->2023). The question is descriptive: six papers cannot
      support a test of influence.

Usage
    python -m neuroai_cn.analysis.manifesto_citations            # tables from the committed counts
    python -m neuroai_cn.analysis.manifesto_citations --recompute  # re-query the mirror first
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .. import config
from ..utils.duckdb import get_connection
from .cited_vintage.definitions import ai_condition, neuro_condition

OUT = config.RESULTS_DIR / "manifestos"
OR_BY_YEAR = config.RESULTS_DIR / "flow" / "or_by_year.csv"
OR_FALLBACK = config.DERIVED_DIR / "corrections" / "20260508" / "q1_v3_extended_or_by_year.parquet"

MANIFESTOS: dict[str, str] = {
    "10.1016/j.neuron.2017.06.011": "Hassabis 2017",
    "10.1038/s41467-023-37180-x": "Zador 2023",
    "10.1038/s41593-019-0520-2": "Richards 2019",
    "10.1016/j.neunet.2021.09.018": "Macpherson 2021",
    "10.1016/j.neuron.2019.08.034": "Sinz 2019",
    "10.1038/s41583-020-0277-3": "Lillicrap 2020",
}
YEARS = range(1995, 2026)
CURVE_WINDOW = (2015, 2023)


def _label_sql(prefix: str = "w") -> str:
    t = f"{prefix}.primary_topic"
    return (
        f"CASE WHEN {t} IS NULL THEN 'unknown' WHEN {neuro_condition(t)} THEN 'neuro' "
        f"WHEN {ai_condition(t)} THEN 'ai' ELSE 'other' END"
    )


def fetch(out: Path = OUT, years: tuple[int, int] = (1995, 2025)) -> None:
    """Query the mirror: resolve the DOIs and count incoming edges by year and citing label."""
    con = get_connection(read_only=True)
    con.execute("PRAGMA memory_limit='12GB'")
    con.execute("PRAGMA threads=8")
    dois = ["https://doi.org/" + d for d in MANIFESTOS]
    in_list = "(" + ",".join(f"'{d}'" for d in dois) + ")"
    works = con.execute(
        f"""
        SELECT w.doi, w.id AS work_id, w.title, w.publication_year AS year, w.type,
               w.primary_topic.display_name AS primary_topic,
               w.primary_topic.subfield.display_name AS subfield,
               w.primary_topic.field.display_name AS field,
               {_label_sql()} AS label, w.cited_by_count
        FROM works w WHERE w.doi IN {in_list}
        """
    ).df()
    works["doi"] = works["doi"].str.replace("https://doi.org/", "", regex=False)
    works["short"] = works["doi"].map(MANIFESTOS)
    missing = sorted(set(MANIFESTOS) - set(works["doi"]))
    works["resolved"] = True
    for d in missing:
        works.loc[len(works)] = {
            "doi": d,
            "short": MANIFESTOS[d],
            "resolved": False,
        }
    ids = works["work_id"].dropna().tolist()
    id_list = "(" + ",".join(f"'{i}'" for i in ids) + ")"
    edges = con.execute(
        f"""
        WITH ed AS (
          SELECT cited_work_id, citing_work_id, citing_year FROM citation_edges
          WHERE cited_work_id IN {id_list} AND citing_year BETWEEN {years[0]} AND {years[1]}
        )
        SELECT ed.cited_work_id AS work_id, ed.citing_year,
               CASE WHEN w.primary_topic IS NULL THEN 'other'
                    WHEN {neuro_condition("w.primary_topic")} THEN 'neuro'
                    WHEN {ai_condition("w.primary_topic")} THEN 'ai' ELSE 'other' END AS citing_cls,
               count(*) AS n
        FROM ed JOIN works w ON w.id = ed.citing_work_id
        GROUP BY ALL
        """
    ).df()
    out.mkdir(parents=True, exist_ok=True)
    works.to_csv(out / "resolved_works.csv", index=False)
    edges = edges.merge(works[["work_id", "short"]], on="work_id").sort_values(
        ["short", "citing_year", "citing_cls"]
    )
    edges.to_csv(out / "citations_by_year.csv", index=False)


def load_or() -> pd.DataFrame:
    if OR_BY_YEAR.exists():
        return pd.read_csv(OR_BY_YEAR)
    return pd.read_parquet(OR_FALLBACK)


def odds_ratio(n_within: float, n_target: float, n_src: float, n_tgt: float) -> float:
    rho = n_target / (n_within + n_target)
    null = n_tgt / (n_src + n_tgt)
    return (rho / (1 - rho)) / (null / (1 - null))


def per_paper_table(edges: pd.DataFrame) -> pd.DataFrame:
    """Citations received per paper, year and citing label, with zero rows filled in."""
    idx = pd.MultiIndex.from_product(
        [sorted(edges["short"].unique()), list(YEARS), ["ai", "neuro", "other"]],
        names=["short", "citing_year", "citing_cls"],
    )
    t = edges.set_index(["short", "citing_year", "citing_cls"])["n"].reindex(idx, fill_value=0)
    return t.reset_index()


def flow_share_table(edges: pd.DataFrame, works: pd.DataFrame, orr: pd.DataFrame) -> pd.DataFrame:
    p = per_paper_table(edges)
    lab = works.set_index("short")["label"]
    p["label"] = p["short"].map(lab)
    ai = p[p["citing_cls"] == "ai"].groupby("citing_year")["n"].sum()
    ai_inside = (
        p[(p["citing_cls"] == "ai") & (p["label"] == "neuro")].groupby("citing_year")["n"].sum()
    )
    ne = p[p["citing_cls"] == "neuro"].groupby("citing_year")["n"].sum()
    allc = p.groupby("citing_year")["n"].sum()
    flow = orr[orr["direction"] == "ai_to_neuro"].set_index("year")
    rev = orr[orr["direction"] == "neuro_to_ai"].set_index("year")
    t = pd.DataFrame(
        {
            "from_ai": ai,
            "from_ai_to_neuro_labelled": ai_inside,
            "from_neuro": ne,
            "from_all": allc,
        }
    )
    t["flow_ai_to_neuro_edges"] = flow["n_to_target"]
    t["flow_neuro_to_ai_edges"] = rev["n_to_target"]
    t["share_of_ai_to_neuro_all_six"] = t["from_ai"] / t["flow_ai_to_neuro_edges"]
    t["share_of_ai_to_neuro_neuro_labelled"] = (
        t["from_ai_to_neuro_labelled"] / t["flow_ai_to_neuro_edges"]
    )
    return t.reset_index().rename(columns={"citing_year": "year"})


def or_excluding(edges: pd.DataFrame, works: pd.DataFrame, orr: pd.DataFrame) -> pd.DataFrame:
    """Restricted odds ratio with the six works removed as target works, both directions."""
    p = per_paper_table(edges)
    w = works.dropna(subset=["work_id"]).set_index("short")
    rows = []
    for direction in ("ai_to_neuro", "neuro_to_ai"):
        src_cls, tgt_cls = ("ai", "neuro") if direction == "ai_to_neuro" else ("neuro", "ai")
        for _, r in orr[orr["direction"] == direction].iterrows():
            y = int(r["year"])
            if y not in YEARS:
                continue
            within, target = r["n_to_within"], r["n_to_target"]
            n_src, n_tgt = r["n_works_source"], r["n_works_target"]
            rm_within = rm_target = 0
            for short, wr in w.iterrows():
                n = int(
                    p[
                        (p["short"] == short)
                        & (p["citing_year"] == y)
                        & (p["citing_cls"] == src_cls)
                    ]["n"].sum()
                )
                if wr["label"] == tgt_cls:
                    rm_target += n
                    n_tgt -= int(wr["year"] == y)
                elif wr["label"] == src_cls:
                    rm_within += n
                    n_src -= int(wr["year"] == y)
            rows.append(
                {
                    "year": y,
                    "direction": direction,
                    "or_restricted_baseline": r["or_restricted"],
                    "or_restricted_without_six": odds_ratio(
                        within - rm_within, target - rm_target, n_src, n_tgt
                    ),
                    "edges_removed_cross": rm_target,
                    "edges_removed_within": rm_within,
                }
            )
    t = pd.DataFrame(rows)
    t["relative_change"] = t["or_restricted_without_six"] / t["or_restricted_baseline"] - 1
    return t


def _exact_spearman(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Spearman correlation with an exact two-sided permutation p-value (all n! pairings)."""
    rx = pd.Series(x).rank().to_numpy()
    ry = pd.Series(y).rank().to_numpy()
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    perms = np.array(list(itertools.permutations(range(len(x)))))
    denom = np.sqrt((rx**2).sum() * (ry**2).sum())
    rho = float((rx * ry).sum() / denom)
    rhos = (ry[perms] * rx).sum(axis=1) / denom
    return rho, float(np.mean(np.abs(rhos) >= abs(rho) - 1e-12))


def curve_comparison(share: pd.DataFrame, orr: pd.DataFrame) -> dict:
    a, b = CURVE_WINDOW
    s = share.set_index("year")
    o = orr[orr["direction"] == "ai_to_neuro"].set_index("year")["or_restricted"]
    yrs = list(range(a - 1, b + 1))
    series = {
        "manifesto_citations_from_ai": s.loc[yrs, "from_ai"].to_numpy(float),
        "flow_ai_to_neuro_edges": s.loc[yrs, "flow_ai_to_neuro_edges"].to_numpy(float),
        "flow_or_restricted": o.loc[yrs].to_numpy(float),
    }
    d = {
        k: np.diff(np.log1p(v)) if k != "flow_or_restricted" else np.diff(np.log(v))
        for k, v in series.items()
    }
    out = {"window": [a, b], "n_changes": len(d["manifesto_citations_from_ai"])}
    for k in ("flow_ai_to_neuro_edges", "flow_or_restricted"):
        rho, p = _exact_spearman(d["manifesto_citations_from_ai"], d[k])
        out[f"spearman_changes_vs_{k}"] = rho
        out[f"exact_p_vs_{k}"] = p
    for k, v in series.items():
        out[f"level_{k}_2015_to_2023"] = [float(x) for x in v[1:]]
    # level rank correlation as a second descriptive number
    rho, p = _exact_spearman(
        series["manifesto_citations_from_ai"][1:], series["flow_ai_to_neuro_edges"][1:]
    )
    out["spearman_levels_vs_flow_ai_to_neuro_edges"] = rho
    return out


def analyse(out: Path = OUT) -> dict:
    works = pd.read_csv(out / "resolved_works.csv")
    edges = pd.read_csv(out / "citations_by_year.csv")
    orr = load_or()
    per = per_paper_table(edges)
    per = per.merge(
        works[["short", "label", "year"]].rename(columns={"year": "pub_year"}), on="short"
    )
    per.to_csv(out / "citations_by_paper_year_field.csv", index=False)
    totals = (
        per[per["citing_year"].between(2020, 2023)]
        .pivot_table(index="short", columns="citing_cls", values="n", aggfunc="sum")
        .assign(total=lambda d: d.sum(axis=1))
        .reset_index()
    )
    totals.to_csv(out / "totals_2020_2023_by_citing_field.csv", index=False)
    share = flow_share_table(edges, works, orr)
    share.to_csv(out / "share_of_flow_by_year.csv", index=False)
    ore = or_excluding(edges, works, orr)
    ore.to_csv(out / "or_excluding_manifestos.csv", index=False)
    cc = curve_comparison(share, orr)
    (out / "curve_comparison.json").write_text(json.dumps(cc, indent=1) + "\n")
    return cc


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--recompute", action="store_true", help="re-query the DuckDB mirror")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--years", nargs=2, type=int, default=[1995, 2025])
    a = ap.parse_args()
    if a.recompute:
        fetch(a.out, tuple(a.years))
        if tuple(a.years) != (1995, 2025):
            return  # a slice cannot feed the full-window tables
    analyse(a.out)


if __name__ == "__main__":
    main()

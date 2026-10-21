"""Export the bridge-builders tables (article Figure 3, supplement S5 Tables S5.1 to S5.3 and the concentration tables) to results/bridge/.

Everything is recomputed from the pipeline outputs under ``<NEUROAI_DATA>/data/derived``, never copied
from the supplement text:

    corrections/20260508/q4_v3_extended_full.parquet           133,763 papers with >= 5 citations per side
    corrections/20260508/q4_v3_extended_filtered_by_era_no_books.parquet   the figure's paper input
    corrections/20260508/author_inst_top_authors.parquet         top-200 authors (top-5,000 E2 papers)
    corrections/20260508/author_inst_top_institutions(_consolidated).parquet
    corrections/20260508/author_current_affiliations_curated.parquet   the 26 hand-verified edges
    corrections/20260508/bridge_links_paper_author.parquet       earlier paper-author links (optional cross-check)
    corrections/20260508/author_inst_top_{authors,institutions}_1000.parquet + population_totals.json
    corrections/20260729/concentration_{authors,insts}_{v1,v2}.parquet   full distributions, clean pools

Table S5.1 is rebuilt from the full parquet (eligibility filters, then the book filters of
``audits/filter_by_era_books_only.py``) and must equal the figure's input, otherwise the script stops.
The only step that touches the OpenAlex DuckDB is a read-only lookup for the ~40 best candidates
(work type, source, authorships); it is capped at DUCKDB_MEMORY_LIMIT.

    python -m neuroai_cn.analysis.export_bridge_tables

Outputs (results/bridge/): table_s1_papers.csv, table_s2_authors.csv,
table_s3_institutions_consolidated.csv, table_s3b_institutions_separated.csv,
institution_ranks_top100.csv, author_institution_edges.csv, paper_author_links.csv,
s1_eligibility_check.csv, concentration_tiers.csv, headline_numbers.csv.
"""

from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd

from .. import config

CORR = config.DERIVED_DIR / "corrections" / "20260508"
CONC = config.DERIVED_DIR / "corrections" / "20260729"
OUT = config.RESULTS_DIR / "bridge"

N_TOP = 15
N_CANDIDATES = 40  # eligible papers looked up in DuckDB to rebuild Table S5.1
CEILING = 10_000  # E2: all-time classified citations must stay below this
MIN_SIDE = 5  # admission gate: citations from each side
DUCKDB_MEMORY_LIMIT = "4GB"
TIERS = (1, 5, 10, 15, 25, 50, 100, 250, 500, 1000)
ADJUST_MEAN_B = 400.0  # sensitivity bound of supplement section 8.3

OK_TYPES = {"article", "review"}
BOOK_SOURCES = {"ebook platform", "book series"}
# Same list as audits/filter_by_era_books_only.py (title prefixes, case-insensitive).
KNOWN_BOOK_TITLES = (
    "reinforcement learning: an introduction",
    "pattern classification",
    "advances in neural information processing systems",
)

# Hand coding of the 15 papers of Table S5.1: a tool is software, a benchmark, an analysis method or a
# methods survey that both fields cite because they run it; a concept is a claim about brains or minds.
# Source: supplement S3 section 5 (seven tools); the same split is in the citation-age hand coding
# (results/citation_age/classification.csv) for the 14 papers it covers.
PAPER_CLASS = {
    "W1641498739": "tool",  # BRATS benchmark
    "W2147101007": "concept",  # Bi and Poo
    "W2164653071": "concept",  # Izhikevich
    "W2145889472": "concept",  # Olshausen and Field
    "W2144764737": "concept",  # Itti and Koch 2001
    "W1984314602": "concept",  # Miller (1956 paper, OpenAlex year 1994)
    "W1951724000": "tool",  # lme4
    "W2136573752": "tool",  # HMRF brain MR segmentation
    "W2592929672": "tool",  # deep learning in medical image analysis survey
    "W2128272608": "concept",  # Itti, Koch and Niebur
    "W3003257820": "tool",  # SciPy 1.0
    "W2112927743": "concept",  # Zucker and Regehr
    "W2158698691": "tool",  # ROC analysis
    "W2149194912": "concept",  # Riesenhuber and Poggio
    "W2295598076": "tool",  # XGBoost
}
PAPER_NOTE = {"W1984314602": "OpenAlex dates the 1956 original by its 1994 reprint"}


def _short(openalex_id: str) -> str:
    return str(openalex_id).rsplit("/", 1)[-1]


def _norm_title(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(t))).strip().lower()


def _share(c_neuro, c_ai):
    return c_neuro / (c_neuro + c_ai).clip(lower=1)


def gini(x) -> float:
    v = np.sort(np.asarray(x, dtype=float))
    n = len(v)
    return float((2 * np.sum(np.arange(1, n + 1) * v) - (n + 1) * v.sum()) / (n * v.sum()))


# ---------------------------------------------------------------------------
# Papers
# ---------------------------------------------------------------------------


def eligible_pool(full: pd.DataFrame) -> pd.DataFrame:
    """E2: own field label neuro or ai, all-time classified citations under the ceiling."""
    return full[
        full["bridge_paper_field"].isin(["neuro", "ai"]) & (full["c_total_classified"] < CEILING)
    ]


def lookup_openalex(work_ids: list[str]) -> pd.DataFrame:
    """One read-only DuckDB pass: type, source and full authorship list of the given works."""
    from ..utils.duckdb import get_connection

    quoted = ",".join("'" + w.replace("'", "''") + "'" for w in work_ids)
    con = get_connection(read_only=True)
    try:
        con.execute("PRAGMA threads=4")
        con.execute(f"PRAGMA memory_limit='{DUCKDB_MEMORY_LIMIT}'")
        return con.execute(
            f"""
            SELECT id AS work_id, type AS oa_type,
                   primary_location.source.type AS source_type,
                   primary_location.source.display_name AS venue,
                   authorships
            FROM works WHERE id IN ({quoted})
            """
        ).df()
    finally:
        con.close()


def _first_author(authorships) -> str:
    for a in authorships if authorships is not None else []:
        if a.get("author_position") == "first":
            return (a.get("author") or {}).get("display_name") or ""
    return ""


def build_s1(full: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (table_s1, eligibility_check, authorships of the 15 papers)."""
    cand = eligible_pool(full).sort_values("B_harmonic", ascending=False).head(N_CANDIDATES).copy()
    cand = cand.merge(lookup_openalex(cand["work_id"].tolist()), on="work_id", how="left")
    title = cand["title"].fillna("").astype(str)

    reason = pd.Series("", index=cand.index)
    reason[~cand["oa_type"].isin(OK_TYPES)] = "type " + cand["oa_type"].astype(str)
    reason[(reason == "") & cand["source_type"].isin(BOOK_SOURCES)] = "source " + cand[
        "source_type"
    ].astype(str)
    reason[(reason == "") & (title.str.strip() == "")] = "empty title"
    known = title.str.lower().str.strip().str.startswith(KNOWN_BOOK_TITLES)
    reason[(reason == "") & known] = "known book title"
    cand["_t"] = title.map(_norm_title)
    dup = cand["_t"].duplicated(keep="first")  # sorted by B, so the first is the best record
    reason[(reason == "") & dup] = "duplicate title"
    cand["included"] = reason == ""
    cand["exclusion_reason"] = reason
    cand["candidate_rank"] = np.arange(1, len(cand) + 1)

    kept = cand[cand["included"]].head(N_TOP).reset_index(drop=True)
    kept["rank"] = kept.index + 1
    kept["first_author"] = kept["authorships"].map(_first_author)
    kept["neuro_share"] = _share(kept["c_neuro"], kept["c_ai"])
    kept["paper_class"] = kept["work_id"].map(lambda w: PAPER_CLASS[_short(w)])
    kept["note"] = kept["work_id"].map(lambda w: PAPER_NOTE.get(_short(w), ""))
    kept["venue"] = kept["venue"].fillna("")
    s1 = kept.rename(
        columns={"publication_year": "year", "B_harmonic": "B", "work_id": "openalex_id"}
    )[
        [
            "rank",
            "title",
            "year",
            "first_author",
            "c_neuro",
            "c_ai",
            "B",
            "neuro_share",
            "venue",
            "oa_type",
            "paper_class",
            "note",
            "openalex_id",
            "doi",
        ]
    ]
    check = cand[
        [
            "candidate_rank",
            "work_id",
            "title",
            "publication_year",
            "B_harmonic",
            "oa_type",
            "source_type",
            "included",
            "exclusion_reason",
        ]
    ].rename(columns={"work_id": "openalex_id", "publication_year": "year", "B_harmonic": "B"})

    # The figure's input is a pre-built file; Table S5.1 must be its top 15, work for work.
    fig_in = pd.read_parquet(CORR / "q4_v3_extended_filtered_by_era_no_books.parquet")
    fig_top = fig_in.sort_values("B_harmonic", ascending=False).head(N_TOP)["work_id"].tolist()
    if fig_top != s1["openalex_id"].tolist():
        raise RuntimeError(
            "Table S5.1 rebuilt from the full parquet differs from the figure input:\n"
            f"  figure input: {fig_top}\n  rebuilt:      {s1['openalex_id'].tolist()}"
        )
    return s1, check, kept[["work_id", "rank", "title", "authorships"]]


# ---------------------------------------------------------------------------
# Authors, institutions, edges, links
# ---------------------------------------------------------------------------


def build_s2() -> pd.DataFrame:
    a = pd.read_parquet(CORR / "author_inst_top_authors.parquet")
    a = a.sort_values("total_B", ascending=False).head(N_TOP).reset_index(drop=True)
    a["rank"] = a.index + 1
    a["neuro_share"] = _share(a["total_c_neuro"], a["total_c_ai"])
    return a[
        [
            "rank",
            "author_id",
            "author_name",
            "n_bridge_papers",
            "total_B",
            "mean_B",
            "max_B",
            "total_c_neuro",
            "total_c_ai",
            "neuro_share",
        ]
    ]


def _institutions(consolidated: bool) -> pd.DataFrame:
    name = (
        "author_inst_top_institutions_consolidated"
        if consolidated
        else "author_inst_top_institutions"
    )
    d = pd.read_parquet(CORR / f"{name}.parquet").sort_values("total_B", ascending=False)
    d = d.reset_index(drop=True)
    d["rank"] = d.index + 1
    d["neuro_share"] = _share(d["total_c_neuro"], d["total_c_ai"])
    if "consolidated_from" not in d:
        d["consolidated_from"] = ""
    d["consolidated_from"] = d["consolidated_from"].fillna("")
    return d[
        [
            "rank",
            "inst_id",
            "inst_name",
            "inst_type",
            "country_code",
            "n_bridge_papers",
            "total_B",
            "total_c_neuro",
            "total_c_ai",
            "neuro_share",
            "consolidated_from",
        ]
    ]


def build_edges(s2: pd.DataFrame, cons: pd.DataFrame, sep: pd.DataFrame) -> pd.DataFrame:
    cur = pd.read_parquet(CORR / "author_current_affiliations_curated.parquet")
    rank_of = dict(zip(s2["author_id"], s2["rank"], strict=True))
    if not set(cur["author_id"]) <= set(s2["author_id"]):
        raise RuntimeError("curated affiliations name authors outside the top 15 of Table S5.2")
    cur["author_rank"] = cur["author_id"].map(rank_of)  # recomputed, not trusted
    r_cons = dict(zip(cons["inst_id"].head(N_TOP), cons["rank"].head(N_TOP), strict=True))
    r_sep = dict(zip(sep["inst_id"].head(N_TOP), sep["rank"].head(N_TOP), strict=True))
    cur["inst_rank_consolidated"] = cur["inst_id"].map(r_cons).astype("Int64")
    cur["inst_rank_separated"] = cur["inst_id"].map(r_sep).astype("Int64")
    cur["drawn_main"] = cur["inst_rank_consolidated"].notna()
    cur["drawn_separated"] = cur["inst_rank_separated"].notna()
    cols = [
        "author_rank",
        "author_id",
        "author_name",
        "inst_id",
        "inst_name",
        "affiliation_status",
        "inst_rank_consolidated",
        "inst_rank_separated",
        "drawn_main",
        "drawn_separated",
        "note",
    ]
    # Stable sort: within an author the curated order (current first, then past) is kept.
    return cur.sort_values("author_rank", kind="stable")[cols].reset_index(drop=True)


def build_links(papers: pd.DataFrame, s2: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Paper-to-author links between the 15 papers and the 15 authors, from the authorship lists."""
    rank_of = dict(zip(s2["author_id"], s2["rank"], strict=True))
    rows = []
    for p in papers.itertuples():
        for a in p.authorships if p.authorships is not None else []:
            author = a.get("author") or {}
            if author.get("id") in rank_of:
                rows.append(
                    {
                        "paper_rank": p.rank,
                        "openalex_id": p.work_id,
                        "author_rank": rank_of[author["id"]],
                        "author_id": author["id"],
                        "author_name": author.get("display_name"),
                        "author_position": a.get("author_position"),
                    }
                )
    links = pd.DataFrame(rows).sort_values(["paper_rank", "author_rank"]).reset_index(drop=True)

    # Cross-check with the links file an earlier version of the figure read (an earlier pipeline
    # output kept under CORR; the check is skipped when the file is absent).
    legacy = CORR / "bridge_links_paper_author.parquet"
    if not legacy.exists():
        return links, {"links_drawn_recomputed": len(links)}
    pipe_all = pd.read_parquet(legacy)
    pipe = pipe_all[pipe_all["paper_rank"].notna() & pipe_all["author_rank"].notna()]
    got = {
        (int(r), int(a), p)
        for r, a, p in zip(links.paper_rank, links.author_rank, links.author_position, strict=True)
    }
    old = {
        (int(r), int(a), p)
        for r, a, p in zip(pipe.paper_rank, pipe.author_rank, pipe.author_position, strict=True)
    }
    check = {
        "links_drawn_recomputed": len(got),
        "links_drawn_in_pipeline_file": len(old),
        "links_only_in_recomputed": sorted(got - old),
        "links_only_in_pipeline_file": sorted(old - got),
        "pipeline_links_file_rows": len(pipe_all),
        "pipeline_links_file_papers": int(pipe_all["paper_rank"].nunique()),
    }
    return links, check


# ---------------------------------------------------------------------------
# Concentration
# ---------------------------------------------------------------------------


def _tiers(pool: str, entity: str, total_by_rank: pd.Series, denom: float, n: int) -> list[dict]:
    cum = total_by_rank.cumsum()
    return [
        {
            "pool": pool,
            "entity": entity,
            "top_n": t,
            "share_pct": float(100 * cum.iloc[t - 1] / denom),
            "n_entities": n,
            "total_B": denom,
        }
        for t in TIERS
        if t <= len(total_by_rank)
    ]


def build_concentration() -> tuple[pd.DataFrame, dict]:
    rows: list[dict] = []
    gin: dict[str, float] = {}

    # Published basis: all 133,763 candidates, top-1000 tables over population denominators.
    pop = json.loads((CORR / "author_inst_population_totals.json").read_text())
    ta = pd.read_parquet(CORR / "author_inst_top_authors_1000.parquet").sort_values(
        "total_B", ascending=False
    )
    ti = pd.read_parquet(CORR / "author_inst_top_institutions_1000.parquet").sort_values(
        "total_B", ascending=False
    )
    spec = [
        ("authors", ta, pop["authors_total_B"], pop["authors_n"]),
        ("institutions", ti, pop["insts_total_B"], pop["insts_n"]),
    ]
    for entity, df, denom, n in spec:
        rows += _tiers("all_133763_unfiltered", entity, df["total_B"], denom, n)
        gin[f"gini_all_133763_{entity}_top1000"] = gini(df["total_B"])
        # Sensitivity bound: drop entities averaging more than 400 B per paper (the fusion block).
        keep = df[df["mean_B"] <= ADJUST_MEAN_B]
        den_adj = denom - df.loc[df["mean_B"] > ADJUST_MEAN_B, "total_B"].sum()
        rows += _tiers("all_133763_minus_mean_B_gt_400", entity, keep["total_B"], den_adj, n)
        gin[f"gini_adjusted_{entity}_top1000"] = gini(keep["total_B"])
        gin[f"n_dropped_mean_B_gt_400_{entity}"] = int((df["mean_B"] > ADJUST_MEAN_B).sum())

    # Clean pools, full distributions (scripts/concentration_{authors_fast,filtered}.py).
    for tag, label in (("v1", "neuro_ai_59038"), ("v2", "e2_58971")):
        for entity, fname in (("authors", "authors"), ("institutions", "insts")):
            d = pd.read_parquet(CONC / f"concentration_{fname}_{tag}.parquet")
            d = d.sort_values("total_B", ascending=False)
            rows += _tiers(label, entity, d["total_B"], float(d["total_B"].sum()), len(d))
            gin[f"gini_{label}_{entity}_all"] = gini(d["total_B"])
            gin[f"gini_{label}_{entity}_top100"] = gini(d["total_B"].head(100))
    return pd.DataFrame(rows), gin


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    full = pd.read_parquet(CORR / "q4_v3_extended_full.parquet")

    s1, check, papers = build_s1(full)
    s2 = build_s2()
    cons, sep = _institutions(True), _institutions(False)
    edges = build_edges(s2, cons, sep)
    links, link_check = build_links(papers, s2)
    tiers, gin = build_concentration()

    s1.to_csv(OUT / "table_s1_papers.csv", index=False)
    s2.to_csv(OUT / "table_s2_authors.csv", index=False)
    cons.head(N_TOP).to_csv(OUT / "table_s3_institutions_consolidated.csv", index=False)
    sep.head(N_TOP).to_csv(OUT / "table_s3b_institutions_separated.csv", index=False)
    pd.concat(
        [cons.head(100).assign(variant="consolidated"), sep.head(100).assign(variant="separated")]
    )[
        ["variant", "rank", "inst_id", "inst_name", "inst_type", "n_bridge_papers", "total_B"]
    ].to_csv(OUT / "institution_ranks_top100.csv", index=False)
    edges.to_csv(OUT / "author_institution_edges.csv", index=False)
    links.to_csv(OUT / "paper_author_links.csv", index=False)
    check.to_csv(OUT / "s1_eligibility_check.csv", index=False)
    tiers.to_csv(OUT / "concentration_tiers.csv", index=False)

    # Headline numbers: one key per row.
    gate = (full["c_neuro"] >= MIN_SIDE) & (full["c_ai"] >= MIN_SIDE)
    elig = eligible_pool(full)
    concept_years = s1.loc[s1["paper_class"] == "concept", "year"]
    oliva = s2[s2["author_name"] == "Aude Oliva"]

    def share(pool: str, entity: str, n: int) -> float:
        m = (tiers["pool"] == pool) & (tiers["entity"] == entity) & (tiers["top_n"] == n)
        return float(tiers.loc[m, "share_pct"].iloc[0])

    head: dict[str, object] = {
        "n_papers_with_ge5_citations_each_side": int(gate.sum()),
        "n_papers_in_parquet": len(full),
        "n_field_other": int((full["bridge_paper_field"] == "other").sum()),
        "n_field_unknown": int((full["bridge_paper_field"] == "unknown").sum()),
        "n_field_neuro_or_ai": int(full["bridge_paper_field"].isin(["neuro", "ai"]).sum()),
        "n_eligible_works_e2": len(elig),
        "n_works_dropped_by_ceiling": int(
            (
                full["bridge_paper_field"].isin(["neuro", "ai"])
                & (full["c_total_classified"] >= CEILING)
            ).sum()
        ),
        "n_tools_top15": int((s1["paper_class"] == "tool").sum()),
        "n_concepts_top15": int((s1["paper_class"] == "concept").sum()),
        "tool_fraction_top15": float((s1["paper_class"] == "tool").mean()),
        "most_recent_concept_year_top15": int(concept_years.max()),
        "most_recent_concept_title_top15": s1.loc[concept_years.idxmax(), "title"],
        "most_recent_tool_year_top15": int(s1.loc[s1["paper_class"] == "tool", "year"].max()),
        "median_year_top15": float(s1["year"].median()),
        "oliva_in_top15_authors": bool(len(oliva)),
        "oliva_rank": int(oliva["rank"].iloc[0]) if len(oliva) else None,
        "oliva_n_papers": int(oliva["n_bridge_papers"].iloc[0]) if len(oliva) else None,
        "oliva_total_B": float(oliva["total_B"].iloc[0]) if len(oliva) else None,
        "n_edges_total": len(edges),
        "n_edges_current": int((edges["affiliation_status"] == "current").sum()),
        "n_edges_past": int((edges["affiliation_status"] == "past").sum()),
        "n_edges_drawn_main": int(edges["drawn_main"].sum()),
        "n_edges_drawn_separated": int(edges["drawn_separated"].sum()),
        "n_paper_author_links_drawn": len(links),
    }
    for pool in (
        "all_133763_unfiltered",
        "all_133763_minus_mean_B_gt_400",
        "neuro_ai_59038",
        "e2_58971",
    ):
        for entity, key in (("authors", "authors"), ("institutions", "institutions")):
            head[f"top100_{key}_share_pct__{pool}"] = share(pool, entity, 100)
    head.update(gin)
    # Gini within the persisted E2 tables (top 5,000 papers): supplement section 8.3, last paragraph.
    head["gini_e2_top5000_authors_top100"] = gini(
        pd.read_parquet(CORR / "author_inst_top_authors.parquet")["total_B"].head(100)
    )
    head["gini_e2_top5000_institutions_consolidated"] = gini(cons["total_B"])
    head["gini_e2_top5000_institutions_separated_top100"] = gini(sep["total_B"].head(100))
    head.update({f"link_check_{k}": v for k, v in link_check.items()})
    pd.DataFrame(
        {
            "key": list(head),
            "value": [json.dumps(v) if isinstance(v, (list, dict)) else v for v in head.values()],
        }
    ).to_csv(OUT / "headline_numbers.csv", index=False)
    for p in sorted(OUT.glob("*.csv")):
        print(p)


if __name__ == "__main__":
    main()

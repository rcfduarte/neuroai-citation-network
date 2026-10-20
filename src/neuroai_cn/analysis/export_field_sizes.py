"""Export field sizes, corpus totals, pool sizes and anchor labels to committed CSV files.

Supplement S1 (data, corpus and field classification) needs a handful of numbers that live only
in the heavy data: how many works each field holds per publication year under each AI definition
(extended, the curated 35-topic core, whole subfield 1702, and the parts the extended definition is
built from), how many of those works carry a reference list, how many works the snapshot holds in
the parquet files and in the DuckDB index, every topic the field definitions touch with its label,
the sizes and overlaps of the four curated pools, and the labels that the topic, venue and Semantic
Scholar schemes give a hand-picked set of anchor papers (copied from the May 2026 audit table). The
script reads the DuckDB index read-only with a 4 GB memory limit and runs two aggregate scans of the
``works`` table (year by primary topic by work type by reference flag; year by venue for the AI side
in 2000-2004) and one metadata read of the parquet files; it never scans ``citation_edges`` row by
row. The year-by-topic aggregate is cached under ``DERIVED_DIR/field_sizes`` so later runs are fast.
Output is deterministic (fixed row order, integer counts). Run it once on a machine with the data:

    python -m neuroai_cn.analysis.export_field_sizes            # everything
    python -m neuroai_cn.analysis.export_field_sizes --no-scan  # rebuild CSVs from the cache only
"""

from __future__ import annotations

import argparse

import duckdb
import numpy as np
import pandas as pd

from .. import config
from ..audits.extended_classifier import (
    AI_SUBFIELD_1702,
    AI_SUBFIELD_1707,
    BAD_1702_TOPIC_IDS,
    NEURAL_MEMORY_TOPIC_2208,
)
from ..utils.duckdb import AI_CORE_TOPIC_IDS, NEURO_FIELD_ID

YEAR_MIN, YEAR_MAX = 1990, 2026  # the DuckDB index window; 2026 is incomplete
T12157 = "https://openalex.org/T12157"
CACHE_DIR = config.DERIVED_DIR / "field_sizes"
CACHE_TOPICS = CACHE_DIR / "works_by_year_topic_type_refs.parquet"
CACHE_SOURCES = CACHE_DIR / "ai_works_2000_2004_breakdown.parquet"
ANCHOR_TABLE = config.CORRECTIONS_DIR / "20260508" / "triangulation_anchors.parquet"

FLOW = config.RESULTS_DIR / "flow"
CORPUS = config.RESULTS_DIR / "corpus"
OUT_SIZES = FLOW / "field_sizes_by_year.csv"
OUT_TOPICS = FLOW / "ai_topic_sizes_by_year.csv"
OUT_JUMP = FLOW / "ai_works_2000_2004_breakdown.csv"
OUT_SUBFIELDS = FLOW / "subfield_sizes_2000_2004.csv"
OUT_TOTALS = CORPUS / "corpus_totals.csv"
OUT_POOLS = CORPUS / "pool_sizes.csv"
OUT_ANCHORS = CORPUS / "anchor_labels.csv"
OUT_CLASS = CORPUS / "classification_topics.csv"

# Order of the definitions in field_sizes_by_year.csv (one row per year and definition).
DEFINITIONS = (
    ("all_works", "every work in the DuckDB index with this publication year"),
    ("with_primary_topic", "works that carry an OpenAlex primary topic"),
    ("unknown", "works with no primary topic (field unknown)"),
    ("neuroscience", "primary topic in field 28, Neuroscience"),
    ("ai_extended", "AI as used in the article: 1702 minus 26 topics, plus 1707, plus T10502"),
    ("ai_strict_core35", "AI as the curated 35-topic core of subfield 1702 (sensitivity)"),
    ("ai_subfield_1702_whole", "every topic of subfield 1702, Artificial Intelligence"),
    ("ai_1702_minus_excluded", "subfield 1702 minus the 26 excluded topics"),
    ("ai_subfield_1707", "subfield 1707, Computer Vision and Pattern Recognition"),
    ("ai_topic_T10502", "topic T10502, Advanced Memory and Neural Computing (subfield 2208)"),
    ("excluded_26_topics", "the 26 topics of subfield 1702 that the extended definition drops"),
    ("excluded_T12157", "topic T12157, Geochemistry and Geologic Mapping (one of the 26)"),
    ("other_extended", "works with a primary topic in neither field, extended definition"),
)


def _connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    con.execute("PRAGMA memory_limit='4GB'")
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA disable_progress_bar")
    return con


def scan_topics(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """One pass over ``works``: counts by year, primary topic, article/review flag, reference flag."""
    return con.execute(
        f"""
        SELECT publication_year AS year,
               primary_topic.id AS topic_id,
               primary_topic.subfield.id AS subfield_id,
               primary_topic.field.id AS field_id,
               coalesce(type IN ('article', 'review'), false) AS article_or_review,
               coalesce(len(referenced_works) > 0, false) AS has_references,
               count(*) AS n
        FROM works
        WHERE publication_year BETWEEN {YEAR_MIN} AND {YEAR_MAX}
        GROUP BY ALL
        """
    ).df()


def scan_sources(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """AI works (extended definition) in 2000-2004 by year, venue, DOI registrant, work type,
    reference flag, OpenAlex record-creation year and whether the date is a bare 1 January."""
    bad = ",".join(f"'{t}'" for t in sorted(BAD_1702_TOPIC_IDS))
    return con.execute(
        f"""
        SELECT publication_year AS year,
               primary_location.source.id AS source_id,
               primary_location.source.display_name AS source_name,
               split_part(doi, '/', 4) AS doi_prefix,
               type,
               coalesce(len(referenced_works) > 0, false) AS has_references,
               year(created_date) AS created_year,
               coalesce(month(publication_date) = 1 AND day(publication_date) = 1, false)
                   AS dated_1_january,
               count(*) AS n
        FROM works
        WHERE publication_year BETWEEN 2000 AND 2004
          AND ((primary_topic.subfield.id = '{AI_SUBFIELD_1702}' AND primary_topic.id NOT IN ({bad}))
               OR primary_topic.subfield.id = '{AI_SUBFIELD_1707}'
               OR primary_topic.id = '{NEURAL_MEMORY_TOPIC_2208}')
        GROUP BY ALL
        """
    ).df()


def _masks(t: pd.DataFrame) -> dict[str, pd.Series]:
    has = t["topic_id"].notna()
    neuro = t["field_id"] == NEURO_FIELD_ID
    s1702 = t["subfield_id"] == AI_SUBFIELD_1702
    bad = t["topic_id"].isin(BAD_1702_TOPIC_IDS)
    s1707 = t["subfield_id"] == AI_SUBFIELD_1707
    t10502 = t["topic_id"] == NEURAL_MEMORY_TOPIC_2208
    # Same precedence as build_extended_field_assignment: the neuroscience test comes first.
    ext = ~neuro & ((s1702 & ~bad) | s1707 | t10502)
    return {
        "all_works": pd.Series(True, index=t.index),
        "with_primary_topic": has,
        "unknown": ~has,
        "neuroscience": neuro,
        "ai_extended": ext,
        "ai_strict_core35": t["topic_id"].isin(AI_CORE_TOPIC_IDS),
        "ai_subfield_1702_whole": s1702,
        "ai_1702_minus_excluded": s1702 & ~bad,
        "ai_subfield_1707": s1707,
        "ai_topic_T10502": t10502,
        "excluded_26_topics": bad,
        "excluded_T12157": t["topic_id"] == T12157,
        "other_extended": has & ~neuro & ~ext,
    }


def field_sizes(t: pd.DataFrame) -> pd.DataFrame:
    masks = _masks(t)
    rows = []
    years = range(YEAR_MIN, YEAR_MAX + 1)
    for name, desc in DEFINITIONS:
        sub = t[masks[name]]
        g = sub.groupby("year")
        n = g["n"].sum()
        refs = sub[sub["has_references"]].groupby("year")["n"].sum()
        art = sub[sub["article_or_review"]].groupby("year")["n"].sum()
        for y in years:
            rows.append(
                {
                    "year": y,
                    "definition": name,
                    "n_works": int(n.get(y, 0)),
                    "n_with_references": int(refs.get(y, 0)),
                    "n_article_or_review": int(art.get(y, 0)),
                    "description": desc,
                }
            )
    return pd.DataFrame(rows)


def ai_topic_sizes(t: pd.DataFrame, con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Per topic of subfields 1702 and 1707 and topic T10502: works per year, with their status."""
    sel = t[
        t["subfield_id"].isin([AI_SUBFIELD_1702, AI_SUBFIELD_1707])
        | (t["topic_id"] == NEURAL_MEMORY_TOPIC_2208)
    ]
    agg = sel.groupby(["topic_id", "year"]).agg(n_works=("n", "sum")).reset_index()
    refs = (
        sel[sel["has_references"]]
        .groupby(["topic_id", "year"])["n"]
        .sum()
        .rename("n_with_references")
        .reset_index()
    )
    agg = agg.merge(refs, on=["topic_id", "year"], how="left").fillna({"n_with_references": 0})
    names = con.execute(
        "SELECT id AS topic_id, display_name AS topic_name, subfield.display_name AS subfield_name "
        "FROM topics"
    ).df()
    agg = agg.merge(names, on="topic_id", how="left")
    agg["subfield"] = np.where(
        agg["topic_id"] == NEURAL_MEMORY_TOPIC_2208,
        "2208",
        np.where(
            agg["topic_id"].isin(sel[sel.subfield_id == AI_SUBFIELD_1707].topic_id), "1707", "1702"
        ),
    )
    agg["status"] = np.select(
        [agg["topic_id"].isin(BAD_1702_TOPIC_IDS), agg["topic_id"].isin(AI_CORE_TOPIC_IDS)],
        ["excluded", "extended_and_core35"],
        default="extended_only",
    )
    agg["n_with_references"] = agg["n_with_references"].astype("int64")
    cols = ["topic_id", "topic_name", "subfield", "subfield_name", "status", "year"]
    return agg[[*cols, "n_works", "n_with_references"]].sort_values(["topic_id", "year"])


def ai_jump_breakdown(s: pd.DataFrame) -> pd.DataFrame:
    """Extended-AI works per year 2000-2004 broken down several ways, to locate the 2002 jump.

    One block per dimension (venue, DOI registrant, work type, venue recorded or not, reference
    list present or not, OpenAlex record-creation year, date given as a bare 1 January); venues
    and registrants keep the 25 with the largest 2001-to-2002 increase and pool the rest.
    """
    s = s.copy()
    s["venue"] = s["source_name"].fillna("(no venue recorded)")
    s["doi_registrant"] = s["doi_prefix"].replace("", None).fillna("(no DOI)")
    s["venue_recorded"] = s["source_id"].notna().map({True: "yes", False: "no"})
    s["reference_list"] = s["has_references"].map({True: "yes", False: "no"})
    s["record_created"] = s["created_year"].astype("Int64").astype(str)
    s["dated_1_january"] = s["dated_1_january"].map({True: "yes", False: "no"})
    blocks = []
    for dim, top in (
        ("venue", 25),
        ("doi_registrant", 25),
        ("type", None),
        ("venue_recorded", None),
        ("reference_list", None),
        ("record_created", None),
        ("dated_1_january", None),
    ):
        w = s.pivot_table(index=dim, columns="year", values="n", aggfunc="sum").fillna(0)
        w = w.astype("int64")
        w["jump_2002_minus_2001"] = w[2002] - w[2001]
        w = w.sort_values("jump_2002_minus_2001", ascending=False)
        if top is not None and len(w) > top:
            rest = w.iloc[top:].sum().to_frame().T
            rest.index = ["(all others)"]
            w = pd.concat([w.iloc[:top], rest])
        w.insert(0, "key", w.index.astype(str))
        w.insert(0, "dimension", dim)
        blocks.append(w.reset_index(drop=True))
    out = pd.concat(blocks, ignore_index=True)
    out.columns = [
        *out.columns[:2],
        *[f"n_{c}" if isinstance(c, int) else c for c in out.columns[2:]],
    ]
    return out


def subfield_sizes_2000_2004(t: pd.DataFrame, con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Works per year 2000-2004 for every OpenAlex field and every subfield with at least 5,000
    works in 2001, with the 2002/2001 ratio: does the 2002 jump belong to AI alone?"""
    names = con.execute(
        "SELECT DISTINCT subfield.id AS subfield_id, subfield.display_name AS subfield_name, "
        "field.id AS field_id, field.display_name AS field_name FROM topics"
    ).df()
    sub = t[(t.year >= 2000) & (t.year <= 2004) & t.topic_id.notna()]
    blocks = []
    for level, key, name in (
        ("field", "field_id", "field_name"),
        ("subfield", "subfield_id", "subfield_name"),
    ):
        w = (
            sub.pivot_table(index=key, columns="year", values="n", aggfunc="sum")
            .fillna(0)
            .astype("int64")
        )
        if level == "subfield":
            w = w[w[2001] >= 5000]
        w["ratio_2002_to_2001"] = (w[2002] / w[2001]).round(4)
        lab = names.drop_duplicates(key).set_index(key)[name]
        w.insert(0, "name", w.index.map(lab))
        w.insert(0, "id", w.index.str.rsplit("/", n=1).str[-1])
        w.insert(0, "level", level)
        blocks.append(w.sort_values("ratio_2002_to_2001", ascending=False).reset_index(drop=True))
    out = pd.concat(blocks, ignore_index=True)
    out.columns = [
        *out.columns[:3],
        *[f"n_{c}" if isinstance(c, int) else c for c in out.columns[3:]],
    ]
    return out


def corpus_totals(con: duckdb.DuckDBPyConnection, sizes: pd.DataFrame) -> pd.DataFrame:
    pq = str(config.PARQUET_DIR / "works" / "*.parquet")
    meta = (
        duckdb.connect()
        .execute(
            f"""
        SELECT file_name LIKE '%_tier1_supplement%' AS supplement,
               count(DISTINCT file_name) AS n_files, sum(n) AS n_rows
        FROM (SELECT DISTINCT file_name, row_group_id, row_group_num_rows AS n
              FROM parquet_metadata('{pq}'))
        GROUP BY 1
        """
        )
        .df()
    )
    daily = meta[~meta["supplement"]].iloc[0]
    supp = meta[meta["supplement"]].iloc[0]
    yr = con.execute(
        "SELECT count(*), min(publication_year), max(publication_year) FROM works"
    ).fetchone()
    edges = con.execute("SELECT count(*) FROM citation_edges").fetchone()[0]
    topics = con.execute("SELECT count(*) FROM topics").fetchone()[0]
    s = sizes.pivot(index="year", columns="definition", values="n_works")
    r = sizes.pivot(index="year", columns="definition", values="n_with_references")
    rows = [
        (
            "parquet_daily_partitions",
            int(daily["n_files"]),
            "daily update files of the OpenAlex works snapshot",
        ),
        (
            "parquet_work_records",
            int(daily["n_rows"]),
            "work records in those files, all publication years",
        ),
        (
            "parquet_supplement_records",
            int(supp["n_rows"]),
            "hand-added records for tier-1 anchors (_tier1_supplement)",
        ),
        ("index_works", int(yr[0]), "works in the DuckDB index"),
        ("index_year_min", int(yr[1]), "earliest publication year in the index"),
        ("index_year_max", int(yr[2]), "latest publication year in the index"),
        (
            "index_works_1990_2025",
            int(s.loc[1990:2025, "all_works"].sum()),
            "works published 1990-2025",
        ),
        (
            "index_works_with_primary_topic",
            int(s["with_primary_topic"].sum()),
            "works with a primary topic, 1990-2026",
        ),
        (
            "index_works_with_references",
            int(r["all_works"].sum()),
            "works with a non-empty reference list, 1990-2026",
        ),
        (
            "citation_edges",
            int(edges),
            "rows of citation_edges, one per entry of a reference list (the cited work may lie outside the index)",
        ),
        ("topics", int(topics), "OpenAlex topics in the index"),
    ]
    return pd.DataFrame(rows, columns=["quantity", "value", "definition"])


def pool_sizes() -> pd.DataFrame:
    """Pool sizes, the exact overlap partition and the Pool 1 split, from the derived pool files."""
    d = config.DERIVED_DIR
    con = duckdb.connect()
    con.execute("PRAGMA memory_limit='4GB'")
    rows = []
    for p in ("pool1", "pool2", "pool3", "pool4"):
        n = con.execute(
            f"SELECT count(DISTINCT work_id) FROM read_parquet('{d / p}.parquet')"
        ).fetchone()[0]
        rows.append(("pool_size", p, int(n)))
    n_sum = sum(r[2] for r in rows)
    rows.append(("pool_size", "sum_before_dedup", int(n_sum)))
    n_u = con.execute(
        f"SELECT count(DISTINCT work_id) FROM read_parquet('{d / 'corpus.parquet'}')"
    ).fetchone()[0]
    rows.append(("pool_size", "union_unique", int(n_u)))
    part = con.execute(
        f"""
        SELECT array_to_string(list_sort(list_distinct(pools)), '+') AS combo, count(*) AS n
        FROM read_parquet('{d / "corpus.parquet"}') GROUP BY 1 ORDER BY 1
        """
    ).fetchall()
    rows += [("exclusive_combination", c, int(n)) for c, n in part]
    sub = con.execute(
        f"""
        SELECT array_to_string(list_sort(list_distinct(sub_pool)), '+') AS combo, count(*)
        FROM read_parquet('{d / "pool1.parquet"}') GROUP BY 1 ORDER BY 1
        """
    ).fetchall()
    rows += [("pool1_sub_pool", str(c), int(n)) for c, n in sub]
    return pd.DataFrame(rows, columns=["kind", "key", "n_works"])


NEIGHBOR_SUBFIELDS = {  # adjacent subfields that are deliberately left in the third field
    "https://openalex.org/subfields/3205": "Experimental and Cognitive Psychology",
    "https://openalex.org/subfields/3206": "Neuropsychology and Physiological Psychology",
    "https://openalex.org/subfields/1708": "Hardware and Architecture",
}


def classification_topics(t: pd.DataFrame, con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Every topic that the field definitions touch, with its label and works 1990-2025."""
    top = con.execute(
        "SELECT id AS topic_id, display_name AS topic_name, subfield.id AS subfield_id, "
        "subfield.display_name AS subfield_name, field.id AS field_id, "
        "field.display_name AS field_name FROM topics"
    ).df()
    neighbors = list(NEIGHBOR_SUBFIELDS)
    sel = top[
        (top.field_id == NEURO_FIELD_ID)
        | top.subfield_id.isin([AI_SUBFIELD_1702, AI_SUBFIELD_1707, *neighbors])
        | (top.topic_id == NEURAL_MEMORY_TOPIC_2208)
    ].copy()
    neuro = sel.field_id == NEURO_FIELD_ID
    bad = sel.topic_id.isin(BAD_1702_TOPIC_IDS)
    ext = ~neuro & (
        ((sel.subfield_id == AI_SUBFIELD_1702) & ~bad)
        | (sel.subfield_id == AI_SUBFIELD_1707)
        | (sel.topic_id == NEURAL_MEMORY_TOPIC_2208)
    )
    sel["label_extended"] = np.select([neuro, ext], ["neuroscience", "ai"], default="other")
    sel["label_strict_core35"] = np.select(
        [neuro, sel.topic_id.isin(AI_CORE_TOPIC_IDS)], ["neuroscience", "ai"], default="other"
    )
    sel["note"] = np.select(
        [bad, sel.subfield_id.isin(neighbors)],
        ["excluded from AI (one of the 26)", "neighboring subfield, not counted"],
        default="",
    )
    w = t[(t.year >= 1990) & (t.year <= 2025)].groupby("topic_id")["n"].sum()
    sel["n_works_1990_2025"] = sel.topic_id.map(w).fillna(0).astype("int64")
    for c in ("subfield_id", "field_id"):
        sel[c] = sel[c].str.rsplit("/", n=1).str[-1]
    sel["topic_id"] = sel["topic_id"].str.rsplit("/", n=1).str[-1]
    return sel.sort_values(["label_extended", "subfield_id", "topic_id"]).reset_index(drop=True)


def anchor_labels() -> pd.DataFrame:
    """Labels of the hand-picked anchor papers: expected, topic scheme (extended and whole 1702),
    venue scheme and Semantic Scholar fields of study, from the May 2026 triangulation audit."""
    t = pd.read_parquet(ANCHOR_TABLE)
    whole = np.where(
        t["pt_field"] == NEURO_FIELD_ID,
        "neuro",
        np.where(
            t["pt_subfield"] == AI_SUBFIELD_1702,
            "ai",
            np.where(t["pt_subfield"].isna(), "NOT_FOUND", "other"),
        ),
    )
    out = pd.DataFrame(
        {
            "anchor": t["anchor_name"],
            "expected": t["expected_label"],
            "doi": t["doi_norm"],
            "primary_topic": t["pt_name"],
            "subfield": t["pt_subfield"].str.rsplit("/", n=1).str[-1],
            "field": t["pt_field"].str.rsplit("/", n=1).str[-1],
            "label_extended": t["scheme1_topics_extended"],
            "label_whole_1702": whole,
            "label_venue": t["scheme2_venue"],
            "venue": t["venue_name"],
            "label_semantic_scholar": t["scheme3_s2fos"],
        }
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-scan", action="store_true", help="use the cached aggregates only")
    ap.add_argument(
        "--only-breakdown", action="store_true", help="rescan the 2000-2004 AI works only"
    )
    args = ap.parse_args()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    FLOW.mkdir(parents=True, exist_ok=True)
    CORPUS.mkdir(parents=True, exist_ok=True)
    con = _connect()
    try:
        if not (args.no_scan and CACHE_TOPICS.exists()) and not args.only_breakdown:
            scan_topics(con).to_parquet(CACHE_TOPICS, index=False)
        if not (args.no_scan and CACHE_SOURCES.exists()):
            scan_sources(con).to_parquet(CACHE_SOURCES, index=False)
        t = pd.read_parquet(CACHE_TOPICS)
        sizes = field_sizes(t)
        sizes.to_csv(OUT_SIZES, index=False)
        ai_topic_sizes(t, con).to_csv(OUT_TOPICS, index=False)
        ai_jump_breakdown(pd.read_parquet(CACHE_SOURCES)).to_csv(OUT_JUMP, index=False)
        subfield_sizes_2000_2004(t, con).to_csv(OUT_SUBFIELDS, index=False)
        corpus_totals(con, sizes).to_csv(OUT_TOTALS, index=False)
        classification_topics(t, con).to_csv(OUT_CLASS, index=False)
    finally:
        con.close()
    pool_sizes().to_csv(OUT_POOLS, index=False)
    anchor_labels().to_csv(OUT_ANCHORS, index=False)
    for p in (
        OUT_SIZES,
        OUT_TOPICS,
        OUT_JUMP,
        OUT_SUBFIELDS,
        OUT_TOTALS,
        OUT_CLASS,
        OUT_POOLS,
        OUT_ANCHORS,
    ):
        print(p)


if __name__ == "__main__":
    main()

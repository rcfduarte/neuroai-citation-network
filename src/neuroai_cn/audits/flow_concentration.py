"""How concentrated is the AI->Neuro flow?

The article claims that neuroscience's rising references to AI are carried
substantially by tools rather than theory. Testing that means classifying the
AI works neuroscience actually cites. Whether that is feasible from abstracts
(live API) or only from OpenAlex topics (local snapshot) depends on how many
distinct AI works carry the citation mass.

This module measures exactly that: over the edges where a neuroscience paper
cites an AI paper (the article's `AI->Neuro` gold line), how many distinct
cited AI works account for 50%, 80%, 90% and 95% of the citations.

Field assignment reuses the published extended classifier so the edge set is
the same one behind Figure 1. Output is written to
`data/derived/flow_concentration.json` plus a head table of the most-cited
AI works as `data/derived/flow_concentration_head.parquet`.

Run:
    python -m neuroai_cn.audits.flow_concentration
    python -m neuroai_cn.audits.flow_concentration --era 2016 2025
"""

from __future__ import annotations

import argparse
import json
import logging
import time

import duckdb

from ..utils.duckdb import derived_dir, get_connection, set_temp_directory
from .extended_classifier import build_extended_field_assignment

logger = logging.getLogger(__name__)

QUANTILES = (0.50, 0.80, 0.90, 0.95)
HEAD_N = 200


def _tune(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("PRAGMA threads=8")
    con.execute("PRAGMA memory_limit='24GB'")
    set_temp_directory(con)


def build_cited_counts(con: duckdb.DuckDBPyConnection, year_min: int, year_max: int) -> None:
    """Per cited AI work, how many citations arrive from neuroscience.

    `citing_year` is the year of the citing (neuroscience) paper, matching the
    citing-year axis used throughout Q1. The cited AI work may be of any year.
    """
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE cited_counts AS
        SELECT
            e.cited_work_id AS cited_work_id,
            COUNT(*)        AS n_cites
        FROM citation_edges e
        JOIN work_field src ON src.work_id = e.citing_work_id
        JOIN work_field tgt ON tgt.work_id = e.cited_work_id
        WHERE src.field = 'neuro'
          AND tgt.field = 'ai'
          AND e.citing_year BETWEEN {year_min} AND {year_max}
        GROUP BY e.cited_work_id
        """
    )


def concentration(con: duckdb.DuckDBPyConnection) -> dict:
    total_edges, n_works = con.execute("SELECT SUM(n_cites), COUNT(*) FROM cited_counts").fetchone()
    total_edges = int(total_edges or 0)
    n_works = int(n_works or 0)
    if total_edges == 0:
        return {"total_edges": 0, "n_distinct_cited_works": 0, "quantiles": {}}

    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE ranked AS
        SELECT
            cited_work_id,
            n_cites,
            ROW_NUMBER() OVER (ORDER BY n_cites DESC, cited_work_id) AS rnk,
            SUM(n_cites) OVER (
                ORDER BY n_cites DESC, cited_work_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS cum_cites
        FROM cited_counts
        """
    )

    out: dict[str, object] = {
        "total_edges": total_edges,
        "n_distinct_cited_works": n_works,
        "quantiles": {},
    }
    for q in QUANTILES:
        row = con.execute(
            f"SELECT MIN(rnk) FROM ranked WHERE cum_cites >= {q} * {total_edges}"
        ).fetchone()
        rank = int(row[0]) if row and row[0] is not None else None
        out["quantiles"][f"{q:.2f}"] = {
            "n_works": rank,
            "share_of_works": (rank / n_works) if rank else None,
        }
    return out


def topic_coverage(con: duckdb.DuckDBPyConnection) -> dict:
    """What fraction of the cited AI works carry a usable OpenAlex topic.

    This is the feasibility check for the topic-based instrument: a decomposition
    by `primary_topic` is only as complete as topic coverage on the cited side.
    """
    row = con.execute(
        """
        SELECT
            COUNT(*)                                                  AS n_works,
            SUM(CASE WHEN w.primary_topic IS NOT NULL THEN 1 ELSE 0 END) AS n_with_topic,
            SUM(c.n_cites)                                            AS n_cites,
            SUM(CASE WHEN w.primary_topic IS NOT NULL THEN c.n_cites ELSE 0 END)
                                                                      AS n_cites_with_topic
        FROM cited_counts c
        JOIN works w ON w.id = c.cited_work_id
        """
    ).fetchone()
    n_works, n_with_topic, n_cites, n_cites_with_topic = (int(x or 0) for x in row)
    return {
        "works_resolved": n_works,
        "works_with_primary_topic": n_with_topic,
        "work_coverage": (n_with_topic / n_works) if n_works else None,
        "citations_resolved": n_cites,
        "citations_with_primary_topic": n_cites_with_topic,
        "citation_weighted_coverage": (n_cites_with_topic / n_cites) if n_cites else None,
    }


def write_head(con: duckdb.DuckDBPyConnection, n: int = HEAD_N) -> str:
    path = derived_dir() / "flow_concentration_head.parquet"
    con.execute(
        f"""
        COPY (
            SELECT
                r.rnk,
                r.cited_work_id,
                w.title,
                w.publication_year,
                w.primary_topic.id           AS topic_id,
                w.primary_topic.display_name AS topic,
                r.n_cites,
                r.cum_cites
            FROM ranked r
            LEFT JOIN works w ON w.id = r.cited_work_id
            WHERE r.rnk <= {n}
            ORDER BY r.rnk
        ) TO '{path}' (FORMAT PARQUET)
        """
    )
    return str(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--era", nargs=2, type=int, metavar=("MIN", "MAX"), default=[1990, 2025])
    args = ap.parse_args()
    year_min, year_max = args.era

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    t0 = time.time()

    con = get_connection(read_only=True)
    _tune(con)

    logger.info("Building extended field assignment (%d-%d)...", year_min, year_max)
    pop = build_extended_field_assignment(con, year_min=year_min, year_max=year_max)

    logger.info("Aggregating neuro->AI citations per cited AI work...")
    build_cited_counts(con, year_min, year_max)

    logger.info("Computing concentration...")
    conc = concentration(con)

    logger.info("Checking topic coverage on the cited side...")
    cov = topic_coverage(con)

    head_path = write_head(con)

    result = {
        "era": [year_min, year_max],
        "populations": pop,
        "concentration": conc,
        "topic_coverage": cov,
        "head_table": head_path,
        "elapsed_s": round(time.time() - t0, 1),
    }
    out = derived_dir() / "flow_concentration.json"
    out.write_text(json.dumps(result, indent=2))
    logger.info("Wrote %s (%.1fs)", out, result["elapsed_s"])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

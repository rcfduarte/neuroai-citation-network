"""Compute the bipartite link tables needed for Figure 2 v2.

For each entity-type pair (paper-author, author-institution), enumerate the
edges where at least one endpoint is in our top-15 list. This lets us draw
a 2-panel bipartite diagram with curves linking only those entities that
actually co-occur in the bridge corpus.

Inputs (corrections/20260508/):
    q4_v3_extended_filtered_by_era.parquet   — top bridge papers
    author_inst_top_authors.parquet          — top bridge authors
    author_inst_top_institutions.parquet     — top bridge institutions
    [via DuckDB] openalex.duckdb works.authorships field — full author+inst structure

Outputs (corrections/20260508/):
    bridge_links_paper_author.parquet
        work_id, paper_rank, author_id, author_name, author_rank, author_position
    bridge_links_author_inst.parquet
        author_id, author_name, author_rank, inst_id, inst_name, inst_rank,
        country_code, n_papers_shared
"""

from __future__ import annotations

import logging

import pandas as pd

from .. import config
from ..utils.duckdb import get_connection

logger = logging.getLogger(__name__)

CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"

TOP_N = 15


def main() -> int:
    # Prefer the books-filtered set if present; else fall back to original.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    no_books = CORRECTIONS_DIR / "q4_v3_extended_filtered_by_era_no_books.parquet"
    src = (
        no_books
        if no_books.exists()
        else CORRECTIONS_DIR / "q4_v3_extended_filtered_by_era.parquet"
    )
    logger.info("Top papers source: %s", src.name)
    top_p = (
        pd.read_parquet(src)
        .sort_values("B_harmonic", ascending=False)
        .head(TOP_N)
        .reset_index(drop=True)
    )
    top_p["paper_rank"] = top_p.index + 1

    top_a = (
        pd.read_parquet(CORRECTIONS_DIR / "author_inst_top_authors.parquet")
        .sort_values("total_B", ascending=False)
        .head(TOP_N)
        .reset_index(drop=True)
    )
    top_a["author_rank"] = top_a.index + 1

    top_i = (
        pd.read_parquet(CORRECTIONS_DIR / "author_inst_top_institutions.parquet")
        .sort_values("total_B", ascending=False)
        .head(TOP_N)
        .reset_index(drop=True)
    )
    top_i["inst_rank"] = top_i.index + 1

    top_author_ids = set(top_a["author_id"].astype(str))
    top_inst_ids = set(top_i["inst_id"].astype(str))
    top_paper_ids = set(top_p["work_id"].astype(str))

    logger.info(
        "Top entities: %d papers, %d authors, %d institutions",
        len(top_paper_ids),
        len(top_author_ids),
        len(top_inst_ids),
    )

    # ------------------------------------------------------------------
    # Pull (work, authorships) from DuckDB for two scopes:
    #   * the top-N papers (for paper->author edges)
    #   * the full bridge-paper set that includes any of our top-N authors
    #     (for author->institution edges)
    # ------------------------------------------------------------------
    with get_connection(read_only=True) as con:
        con.execute("PRAGMA threads=4")
        con.execute("PRAGMA memory_limit='9GB'")
        con.execute("PRAGMA preserve_insertion_order=false")

        # 1) Paper -> Author edges (limited to top 15 papers)
        paper_ids_q = ",".join("'" + p.replace("'", "''") + "'" for p in top_paper_ids)
        rows_pa = con.execute(
            f"SELECT id, authorships FROM works WHERE id IN ({paper_ids_q})"
        ).fetchall()

        pa_rows = []
        for wid, authships in rows_pa:
            if not authships:
                continue
            for a in authships:
                author = a.get("author") or {}
                auth_id = author.get("id")
                auth_name = author.get("display_name")
                position = a.get("author_position")
                if auth_id:
                    pa_rows.append(
                        dict(
                            work_id=wid,
                            author_id=auth_id,
                            author_name=auth_name,
                            author_position=position,
                        )
                    )
        pa = pd.DataFrame(pa_rows)
        pa = pa.merge(top_p[["work_id", "paper_rank"]], on="work_id", how="left")
        # Annotate which authors are in our top-15
        pa = pa.merge(top_a[["author_id", "author_rank"]], on="author_id", how="left")
        pa.to_parquet(CORRECTIONS_DIR / "bridge_links_paper_author.parquet", index=False)
        logger.info("Wrote paper-author edges: %d rows", len(pa))

        # 2) Author -> Institution edges (papers including top-N authors)
        # Skip if the cumulative output already exists — this analysis does not
        # depend on the top-papers list, so re-running is wasted compute.
        ai_out = CORRECTIONS_DIR / "bridge_links_author_inst.parquet"
        if ai_out.exists():
            logger.info("bridge_links_author_inst.parquet already exists, skipping step 2.")
            return 0

        bridge_full = pd.read_parquet(CORRECTIONS_DIR / "q4_v3_extended_full.parquet")
        bridge_ids = bridge_full["work_id"].astype(str).tolist()
        logger.info("Querying authorships for %d bridge papers (batched)", len(bridge_ids))

        author_to_inst: dict[tuple[str, str], dict] = {}
        author_id_to_name: dict[str, str] = dict(
            zip(top_a["author_id"].astype(str), top_a["author_name"], strict=True)
        )

        # Temp tables for both bridge_ids and top_author_ids — let DuckDB do the
        # heavy lifting via unnest + filter server-side instead of streaming
        # 133k full authorship structs to Python.
        con.execute("CREATE TEMP TABLE _bridge_ids (work_id VARCHAR)")
        con.executemany("INSERT INTO _bridge_ids VALUES (?)", [(w,) for w in bridge_ids])
        con.execute("CREATE TEMP TABLE _top_authors (author_id VARCHAR)")
        con.executemany("INSERT INTO _top_authors VALUES (?)", [(a,) for a in top_author_ids])
        logger.info(
            "Loaded %d bridge_ids + %d top author ids into temp tables",
            len(bridge_ids),
            len(top_author_ids),
        )

        # Server-side: unnest authorships -> (author, institutions list), then
        # join with _top_authors to restrict, then unnest institutions, then
        # GROUP BY (author, inst). DuckDB lambdas don't support sub-queries,
        # so we use plain JOIN-on-IN for the filter step.
        logger.info("Running unnest + filter server-side ...")
        df_ai = con.execute(
            """
            WITH all_authors AS (
                SELECT w.id AS work_id, unnest(w.authorships) AS auth
                FROM works w
                JOIN _bridge_ids b ON w.id = b.work_id
            ),
            auth_filtered AS (
                SELECT
                    f.work_id,
                    f.auth.author.id AS author_id,
                    f.auth.institutions AS insts
                FROM all_authors f
                JOIN _top_authors t ON f.auth.author.id = t.author_id
            ),
            insts_flat AS (
                SELECT work_id, author_id, unnest(insts) AS inst
                FROM auth_filtered
                WHERE insts IS NOT NULL AND length(insts) > 0
            )
            SELECT
                author_id,
                inst.id AS inst_id,
                any_value(inst.display_name) AS inst_name,
                any_value(inst.country_code) AS country_code,
                any_value(inst.type) AS inst_type,
                COUNT(DISTINCT work_id) AS n_papers
            FROM insts_flat
            WHERE inst.id IS NOT NULL
            GROUP BY author_id, inst_id
            """
        ).df()
        logger.info("DuckDB returned %d (author, inst) rows", len(df_ai))
        # Build the same dict structure expected downstream
        for _, row in df_ai.iterrows():
            author_to_inst[(row["author_id"], row["inst_id"])] = dict(
                author_id=row["author_id"],
                inst_id=row["inst_id"],
                inst_name=row["inst_name"],
                country_code=row["country_code"],
                inst_type=row["inst_type"],
                n_papers=int(row["n_papers"]),
            )

        ai = pd.DataFrame(list(author_to_inst.values()))
        ai["author_name"] = ai["author_id"].map(author_id_to_name)
        ai = ai.merge(top_a[["author_id", "author_rank"]], on="author_id", how="left")
        ai = ai.merge(top_i[["inst_id", "inst_rank"]], on="inst_id", how="left")
        ai.to_parquet(CORRECTIONS_DIR / "bridge_links_author_inst.parquet", index=False)
        logger.info("Wrote author-inst edges: %d rows", len(ai))

        # Diagnostic summary
        ai_top_links = ai[(ai["author_rank"].notna()) & (ai["inst_rank"].notna())]
        logger.info(
            "Edges where both endpoints are in their respective top-%d: %d / %d",
            TOP_N,
            len(ai_top_links),
            len(ai),
        )

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())

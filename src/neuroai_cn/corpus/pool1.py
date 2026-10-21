"""Pool 1 — Self-proclaimed NeuroAI.

Two components:
  - 1a "anchor-signatory": papers by any author who signed one of the 5 anchor
    publications (Zador 2023/2022, Luppi 2024, Mineault 2024, Hassabis 2017).
  - 1b "neuroai-program-faculty": papers by any author whose `affiliations[]`
    includes one of the curated NeuroAI sub-institute OpenAlex IDs during
    2019-2026 (the "brand era" window).

Output: data/derived/pool1.parquet with columns
    work_id, in_pool=true, source_tag='pool1', sub_pool (list of '1a'/'1b')

Design notes:
  - Anchor authors are resolved with a DOI-CTE first to avoid DuckDB scanning
    all 42M works during UNNEST (the doi-index is only used outside lambdas).
  - Faculty authors use `list_filter` with a literal `list_contains`, which
    avoids exploding the affiliations list across 113M authors. ~108s on the
    current snapshot for 22 institutions.
  - DuckDB lambdas DO NOT support subqueries — institution/author lists must
    be passed as inline VARCHAR[] literals.
"""

from __future__ import annotations

import argparse
import logging
import time

import duckdb

from ..utils.authorships import ensure_cache
from ..utils.duckdb import derived_dir, get_connection, set_temp_directory

logger = logging.getLogger(__name__)

ANCHOR_DOIS: tuple[str, ...] = (
    "https://doi.org/10.1038/s41467-023-37180-x",  # Zador et al. 2023 Nat Commun
    "https://doi.org/10.48550/arxiv.2210.08340",  # Zador et al. 2022 arXiv (precursor)
    "https://doi.org/10.1038/s41467-024-53375-2",  # Luppi/Achterberg et al. 2024 Nat Commun
    "https://doi.org/10.48550/arxiv.2411.18526",  # Mineault et al. 2024 arXiv (NeuroAI for Safety)
    "https://doi.org/10.1016/j.neuron.2017.06.011",  # Hassabis et al. 2017 Neuron
)

# Curated NeuroAI sub-institute OpenAlex IDs (probed 2026-04-29). Whole-university
# IDs (Stanford, Princeton, MIT, …) are deliberately EXCLUDED — they would dilute
# Pool 1 with non-NeuroAI work. Extending this list is encouraged once OpenAlex
# resolves more sub-units (Kempner, Wu Tsai, ARNI, etc. were not present at probe time).
NEUROAI_SUB_INSTITUTE_IDS: tuple[str, ...] = (
    "https://openalex.org/I4387153999",  # Flatiron Institute
    "https://openalex.org/I4210092532",  # National Bernstein Network Computational Neuroscience
    "https://openalex.org/I4210152641",  # Bernstein Center for Computational Neuroscience Berlin
    "https://openalex.org/I4210098324",  # Bernstein Center for Computational Neuroscience Freiburg
    "https://openalex.org/I4210087171",  # Bernstein Center for Computational Neuroscience Göttingen
    "https://openalex.org/I4210109659",  # Bernstein Center for Computational Neuroscience Heidelberg-Mannheim
    "https://openalex.org/I4396570676",  # Sainsbury Wellcome Centre
    "https://openalex.org/I4405252512",  # Centro Champalimaud
    "https://openalex.org/I113358080",  # Champalimaud Foundation
    "https://openalex.org/I4210164802",  # Mila — Quebec AI Institute
    "https://openalex.org/I4210112925",  # Max Planck Institute for Biological Cybernetics
    "https://openalex.org/I4210135521",  # Max Planck Institute for Intelligent Systems
    "https://openalex.org/I1307098950",  # Salk Institute
    "https://openalex.org/I1314596251",  # Allen Institute for Brain Science
    "https://openalex.org/I2750212522",  # Cold Spring Harbor Laboratory
    "https://openalex.org/I4210090411",  # Google DeepMind (UK)
    "https://openalex.org/I4387930290",  # Anthropic
    "https://openalex.org/I2800939219",  # RIKEN Center for Brain Science
    "https://openalex.org/I4387153830",  # Neuromatch
    "https://openalex.org/I4405261313",  # Donders Institute for Brain, Cognition and Behaviour
    "https://openalex.org/I4405259014",  # Donders Centre for Cognitive Neuroimaging
)

BRAND_ERA_START = 2019
BRAND_ERA_END = 2026


def _tune(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("PRAGMA threads=12")
    con.execute("PRAGMA memory_limit='30GB'")
    set_temp_directory(con)


def _sql_varchar_list(values: tuple[str, ...]) -> str:
    """Render a Python tuple of strings as a DuckDB VARCHAR[] literal."""
    return "[" + ",".join("'" + v.replace("'", "''") + "'" for v in values) + "]::VARCHAR[]"


def _resolve_pool1_authors(con: duckdb.DuckDBPyConnection) -> tuple[int, int, int]:
    """Build temp table pool1_authors(author_id, sub_pools VARCHAR[]) and return (n_anchor, n_faculty, n_total)."""
    dois_lit = _sql_varchar_list(ANCHOR_DOIS)
    inst_lit = _sql_varchar_list(NEUROAI_SUB_INSTITUTE_IDS)

    # 1a: anchor signatories.
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _anchor_authors AS
        WITH anchors AS (
            SELECT id, authorships
            FROM works
            WHERE doi IN (SELECT UNNEST({dois_lit}))
        )
        SELECT DISTINCT a.author.id AS author_id
        FROM anchors, UNNEST(anchors.authorships) AS t(a)
        WHERE a.author.id IS NOT NULL
        """
    )
    n_anchor = con.execute("SELECT COUNT(*) FROM _anchor_authors").fetchone()[0]

    # 1b: faculty at curated sub-institutes during the brand era.
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _faculty_authors AS
        SELECT id AS author_id
        FROM authors a
        WHERE list_filter(
            a.affiliations,
            aff -> list_contains({inst_lit}, aff.institution.id)
                AND list_filter(aff.years, y -> y BETWEEN {BRAND_ERA_START} AND {BRAND_ERA_END}) <> []
        ) <> []
        """
    )
    n_faculty = con.execute("SELECT COUNT(*) FROM _faculty_authors").fetchone()[0]

    # Combine, with sub_pool tags.
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE pool1_authors AS
        WITH combined AS (
            SELECT author_id, '1a' AS tag FROM _anchor_authors
            UNION ALL
            SELECT author_id, '1b' AS tag FROM _faculty_authors
        )
        SELECT author_id, list_distinct(list(tag)) AS sub_pools
        FROM combined
        GROUP BY author_id
        """
    )
    n_total = con.execute("SELECT COUNT(*) FROM pool1_authors").fetchone()[0]
    return int(n_anchor), int(n_faculty), int(n_total)


def build(con: duckdb.DuckDBPyConnection | None = None) -> dict:
    """Build pool1.parquet. Returns summary stats."""
    owns_con = con is None
    if owns_con:
        con = get_connection(read_only=True)
    try:
        _tune(con)
        t0 = time.time()
        n_anchor, n_faculty, n_total = _resolve_pool1_authors(con)
        n_overlap = con.execute(
            "SELECT COUNT(*) FROM pool1_authors WHERE len(sub_pools) > 1"
        ).fetchone()[0]
        t_authors = time.time() - t0
        logger.info(
            "Pool 1 authors: %d total (1a=%d, 1b=%d, overlap=%d) in %.1fs",
            n_total,
            n_anchor,
            n_faculty,
            n_overlap,
            t_authors,
        )

        # Use the pre-flattened authorships cache for a fast hash JOIN.
        # Cache is invalidated automatically when the DuckDB index is rebuilt.
        # `allow_partial=True` lets pool builds proceed with a partially-built cache —
        # the morning rebuild will refresh once Track A completes.
        cache_path = ensure_cache(con, allow_partial=True)
        out_path = derived_dir() / "pool1.parquet"
        t1 = time.time()
        con.execute(
            f"""
            COPY (
              SELECT
                e.work_id,
                TRUE AS in_pool,
                'pool1' AS source_tag,
                list_distinct(flatten(list(p.sub_pools))) AS sub_pool
              FROM read_parquet({cache_path}) e
              JOIN pool1_authors p ON p.author_id = e.author_id
              WHERE e.year BETWEEN 1990 AND 2026
              GROUP BY e.work_id
            )
            TO '{out_path}' (FORMAT 'parquet', COMPRESSION 'snappy')
            """
        )
        t_works = time.time() - t1
        n_works = con.execute(f"SELECT COUNT(*) FROM read_parquet('{out_path}')").fetchone()[0]
        elapsed = time.time() - t0
        logger.info(
            "Pool 1: wrote %s (%d works) total=%.1fs (authors %.1fs, works-join %.1fs)",
            out_path,
            n_works,
            elapsed,
            t_authors,
            t_works,
        )
        return {
            "anchor_signatory_authors": n_anchor,
            "faculty_authors": n_faculty,
            "anchor_and_faculty_overlap": int(n_overlap),
            "pool1_authors_total": n_total,
            "pool1_works": int(n_works),
            "out_path": str(out_path),
            "elapsed_authors_s": round(t_authors, 1),
            "elapsed_works_join_s": round(t_works, 1),
            "elapsed_total_s": round(elapsed, 1),
        }
    finally:
        if owns_con:
            con.close()


def _cli() -> None:
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    summary = build()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    _cli()

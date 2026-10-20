"""What is the AI->Neuro citation flow actually made of?

Figure 1's gold line says neuroscience's chance-corrected propensity to cite AI
has risen since 2006. It does not say *what kind* of AI is being cited. This
module decomposes that flow by the OpenAlex topic of the cited AI work, per
citing-year, under both field classifiers:

* ``extended`` — the published classifier: subfield 1702 minus 26 topics,
  union all of subfield 1707 (Computer Vision and Pattern Recognition), union
  topic T10502.
* ``strict`` — the 35-topic curated AI core (``AI_CORE_TOPIC_IDS``), which
  excludes subfield 1707 entirely.

The contrast matters because 1707 carries medical image segmentation and
registration. Any "neuroscience mostly imports tools" claim that appears only
under ``extended`` is partly definitional rather than empirical.

Outputs, both to ``data/derived/``:
    flow_composition_{classifier}.parquet   topic x citing_year x n_cites
    flow_composition_{classifier}_topics.parquet   topic totals, citation-weighted

Run:
    python -m neuroai_cn.audits.flow_composition --classifier extended
    python -m neuroai_cn.audits.flow_composition --classifier strict
"""

from __future__ import annotations

import argparse
import logging
import time

import duckdb

from ..utils.duckdb import (
    AI_CORE_TOPIC_IDS,
    NEURO_FIELD_ID,
    derived_dir,
    get_connection,
    set_temp_directory,
)
from .extended_classifier import (
    AI_SUBFIELD_1702,
    AI_SUBFIELD_1707,
    BAD_1702_TOPIC_IDS,
    NEURAL_MEMORY_TOPIC_2208,
)

logger = logging.getLogger(__name__)

YEAR_MIN = 1990
YEAR_MAX = 2025


def _tune(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("PRAGMA threads=8")
    con.execute("PRAGMA memory_limit='24GB'")
    set_temp_directory(con)


def _ai_predicate(classifier: str) -> str:
    """SQL predicate selecting AI works from `works w`."""
    if classifier == "extended":
        bad = "[" + ",".join("'" + t + "'" for t in BAD_1702_TOPIC_IDS) + "]"
        return f"""(
            (
                w.primary_topic.subfield.id = '{AI_SUBFIELD_1702}'
                AND w.primary_topic.id NOT IN (SELECT unnest({bad}))
            )
            OR w.primary_topic.subfield.id = '{AI_SUBFIELD_1707}'
            OR w.primary_topic.id = '{NEURAL_MEMORY_TOPIC_2208}'
        )"""
    if classifier == "strict":
        core = "[" + ",".join("'" + t + "'" for t in AI_CORE_TOPIC_IDS) + "]"
        return f"(w.primary_topic.id IN (SELECT unnest({core})))"
    raise ValueError(f"unknown classifier: {classifier}")


def build_field_table(con: duckdb.DuckDBPyConnection, classifier: str) -> dict[str, int]:
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE work_field AS
        SELECT
            w.id AS work_id,
            w.publication_year AS year,
            w.primary_topic.id AS topic_id,
            w.primary_topic.display_name AS topic,
            CASE
                WHEN w.primary_topic IS NULL THEN 'unknown'
                WHEN w.primary_topic.field.id = '{NEURO_FIELD_ID}' THEN 'neuro'
                WHEN {_ai_predicate(classifier)} THEN 'ai'
                ELSE 'other'
            END AS field
        FROM works w
        WHERE w.publication_year BETWEEN {YEAR_MIN} AND {YEAR_MAX}
        """
    )
    rows = con.execute("SELECT field, COUNT(*) FROM work_field GROUP BY field").fetchall()
    pop = {f: int(n) for f, n in rows}
    logger.info("[%s] %s", classifier, ", ".join(f"{k}={v:,}" for k, v in sorted(pop.items())))
    return pop


def decompose(con: duckdb.DuckDBPyConnection, classifier: str) -> None:
    """Neuro->AI citations by cited-work topic and citing year."""
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE flow AS
        SELECT
            tgt.topic_id       AS topic_id,
            tgt.topic          AS topic,
            e.citing_year      AS citing_year,
            COUNT(*)           AS n_cites
        FROM citation_edges e
        JOIN work_field src ON src.work_id = e.citing_work_id
        JOIN work_field tgt ON tgt.work_id = e.cited_work_id
        WHERE src.field = 'neuro'
          AND tgt.field = 'ai'
          AND e.citing_year BETWEEN {YEAR_MIN} AND {YEAR_MAX}
        GROUP BY tgt.topic_id, tgt.topic, e.citing_year
        """
    )
    d = derived_dir()
    con.execute(
        f"COPY (SELECT * FROM flow ORDER BY citing_year, n_cites DESC) "
        f"TO '{d / f'flow_composition_{classifier}.parquet'}' (FORMAT PARQUET)"
    )
    con.execute(
        f"""
        COPY (
            SELECT topic_id, topic, SUM(n_cites) AS n_cites
            FROM flow GROUP BY topic_id, topic ORDER BY n_cites DESC
        ) TO '{d / f"flow_composition_{classifier}_topics.parquet"}' (FORMAT PARQUET)
        """
    )
    total = con.execute("SELECT SUM(n_cites) FROM flow").fetchone()[0]
    logger.info("[%s] total neuro->AI edges: %s", classifier, f"{int(total or 0):,}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--classifier", choices=["extended", "strict"], required=True)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    t0 = time.time()
    con = get_connection(read_only=True)
    _tune(con)
    build_field_table(con, args.classifier)
    decompose(con, args.classifier)
    logger.info("done in %.0fs", time.time() - t0)


if __name__ == "__main__":
    main()

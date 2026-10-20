"""Strict (production) field-assignment scheme — counter-factual to extended v3.

Mirrors the curated 35-topic AI core used in production
``q1_cross_citation._build_field_assignment``, exposed via the same interface as
``extended_classifier.build_extended_field_assignment`` so q1/q2/q4 modules can
swap between strict and extended by import alone.

Strict scheme:
    * NEURO = field 28
    * AI = AI_CORE_TOPIC_IDS (curated 35 from subfield 1702)
    * No 1707, no T10502, no BAD_1702 inclusion at all

This is the "before" classifier; the extended scheme is the "after". Re-running
Q1, Q2, Q4 under both gives the editor a clean apples-to-apples comparison for the
methodology disclosure.
"""

from __future__ import annotations

import logging

import duckdb

from ..utils.duckdb import AI_CORE_TOPIC_IDS, NEURO_FIELD_ID

logger = logging.getLogger(__name__)


def build_strict_field_assignment(
    con: duckdb.DuckDBPyConnection,
    year_min: int = 1990,
    year_max: int = 2025,
    table_name: str = "work_field",
) -> dict[str, int]:
    """Build temp table ``work_field(work_id, year, field)`` using the strict
    curated-35 AI core. Returns dict with population sizes per label."""
    ai_arr = "[" + ",".join("'" + t + "'" for t in AI_CORE_TOPIC_IDS) + "]"
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE {table_name} AS
        SELECT
            w.id AS work_id,
            w.publication_year AS year,
            CASE
                WHEN w.primary_topic IS NULL THEN 'unknown'
                WHEN w.primary_topic.field.id = '{NEURO_FIELD_ID}' THEN 'neuro'
                WHEN w.primary_topic.id IN (SELECT unnest({ai_arr})) THEN 'ai'
                ELSE 'other'
            END AS field
        FROM works w
        WHERE w.publication_year BETWEEN {year_min} AND {year_max}
        """
    )
    rows = con.execute(f"SELECT field, COUNT(*) AS n FROM {table_name} GROUP BY field").fetchall()
    pop = {f: int(n) for f, n in rows}
    logger.info(
        "Strict field assignment: %s",
        ", ".join(f"{k}={v:,}" for k, v in sorted(pop.items())),
    )
    return pop

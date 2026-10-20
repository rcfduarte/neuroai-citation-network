"""Q1 — Bidirectional NeuroAI citation flow over time.

For each year y and direction (neuro→ai, ai→neuro) we compute two odds ratios:

1. **Restricted-universe OR** (`OR_restricted`, *recommended*).
   Conditions on edges where both endpoints are in the {neuro, ai} universe;
   ignores all edges to/from the dominant 'other' pool. This isolates the
   neuro–ai cross-talk question from the population dominance of unrelated
   fields (medicine, geology, etc.) which would drag the population baseline
   below 1 by construction.

       rho_{n→a}(y)      = #edges_{n→a}(y) / (#edges_{n→a}(y) + #edges_{n→n}(y))
       rho_null_a(y)     = N_ai(y) / (N_neuro(y) + N_ai(y))
       OR_restricted(y)  = odds(rho) / odds(rho_null)

   OR > 1 ⇒ source over-cites target relative to the target's population
   share within {neuro, ai}.

2. **Population-baseline OR** (`OR_population`, kept for transparency).
   The original formulation; chance baseline is target's share of the full
   classified corpus (neuro + ai + other). Reported alongside but visualized
   in a sensitivity panel only.

Field assignment uses Scheme 1 with **curated** AI topic IDs (see
`AI_CORE_TOPIC_IDS` in utils/duckdb.py). The whole `subfield = 1702` is too
loose — it sweeps in domain-AI buckets (medicine, education, geology) and is
also corrupted in the ud2025-11-06 OpenAlex bulk re-export, where topic
T12157 ("Geochemistry and Geologic Mapping") jumped 51k→2.82M works in a
single year. The curated list excludes that and the ~40 other non-core
topics in subfield 1702.

Year range: 1990–2025. We deliberately exclude 2026 (only ~25% complete in
this snapshot — would distort trends).

Output: `data/derived/q1_or_by_year.parquet` with columns:
    year, direction, n_edges_total, n_to_within, n_to_target, n_to_other,
    n_to_missing, rho_restricted, rho_null_restricted, rho_population,
    rho_null_population, OR_restricted, OR_population,
    or_restricted_lo, or_restricted_hi, or_population_lo, or_population_hi,
    n_works_source, n_works_target, n_works_other.

Confidence intervals: Wilson score on each rho, propagated through the OR.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import time

import duckdb

from ..utils.duckdb import (
    AI_CORE_TOPIC_IDS,
    NEURO_FIELD_ID,
    derived_dir,
    get_connection,
    manifest,
    set_temp_directory,
)

logger = logging.getLogger(__name__)

YEAR_MIN = 1990
YEAR_MAX = 2025  # 2026 excluded — only ~25% complete in snapshot.


def _tune(con: duckdb.DuckDBPyConnection) -> None:
    # Conservative: stage 04 (authorships rebuild) is running concurrently
    # in the orchestrator. Cap memory + threads so we don't OOM.
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='12GB'")
    set_temp_directory(con)


def _ai_core_sql_array() -> str:
    """Render AI_CORE_TOPIC_IDS as a SQL array literal."""
    return "[" + ",".join("'" + tid + "'" for tid in AI_CORE_TOPIC_IDS) + "]"


def _build_field_assignment(con: duckdb.DuckDBPyConnection) -> int:
    """Build temp table work_field(work_id, year, field) where field ∈
    {'neuro','ai','other','unknown'}.

    Topic IDs are uniquely assigned to one (field, subfield) in OpenAlex's
    canonical topics taxonomy, so a single work cannot simultaneously be
    Neuro-field AND AI-core-topic. The 'both' bucket from v2 is structurally
    empty under this curated scheme, so we drop it.
    """
    ai_arr = _ai_core_sql_array()
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE work_field AS
        SELECT
            w.id AS work_id,
            w.publication_year AS year,
            CASE
                WHEN w.primary_topic.field.id = '{NEURO_FIELD_ID}' THEN 'neuro'
                WHEN w.primary_topic.id IN (SELECT unnest({ai_arr})) THEN 'ai'
                WHEN w.primary_topic IS NULL THEN 'unknown'
                ELSE 'other'
            END AS field
        FROM works w
        WHERE w.publication_year BETWEEN {YEAR_MIN} AND {YEAR_MAX}
        """
    )
    return int(con.execute("SELECT COUNT(*) FROM work_field").fetchone()[0])


def _wilson_interval(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 95% CI for a binomial proportion. Returns (lo, hi)."""
    if n == 0:
        return (0.0, 0.0)
    z2 = z * z
    denom = 1 + z2 / n
    centre = p + z2 / (2 * n)
    spread = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return ((centre - spread) / denom, (centre + spread) / denom)


def _odds_ratio(rho: float, rho_null: float) -> float:
    if rho_null <= 0 or rho_null >= 1:
        return float("nan")
    if rho <= 0:
        return 0.0
    if rho >= 1:
        return float("inf")
    return (rho / (1 - rho)) / (rho_null / (1 - rho_null))


def build(con: duckdb.DuckDBPyConnection | None = None) -> dict:
    owns_con = con is None
    if owns_con:
        con = get_connection(read_only=True)
    try:
        _tune(con)
        m = manifest(con)
        if m.tier1_present_count < 4:
            logger.warning("Tier 1 incomplete: %d/4. Q1 is preliminary.", m.tier1_present_count)
        cov = m.coverage_fraction()
        logger.info(
            "Q1 starting against %d works (coverage ≈ %.0f%%, %d citation edges)",
            m.works_total,
            cov * 100,
            m.citation_edges,
        )
        logger.info(
            "Field assignment: Scheme 1 + curated AI list (%d core topics; subfield 1702 has 77 total)",
            len(AI_CORE_TOPIC_IDS),
        )

        t0 = time.time()
        n_assigned = _build_field_assignment(con)
        logger.info("Field assignment: %d works in %.1fs", n_assigned, time.time() - t0)

        # Per-year field-population counts.
        per_year_pop = con.execute(
            f"""
            SELECT
                year,
                SUM(CASE WHEN field = 'neuro' THEN 1 ELSE 0 END) AS n_neuro,
                SUM(CASE WHEN field = 'ai' THEN 1 ELSE 0 END) AS n_ai,
                SUM(CASE WHEN field = 'other' THEN 1 ELSE 0 END) AS n_other,
                SUM(CASE WHEN field = 'unknown' THEN 1 ELSE 0 END) AS n_unknown,
                COUNT(*) AS n_total
            FROM work_field
            WHERE year BETWEEN {YEAR_MIN} AND {YEAR_MAX}
            GROUP BY year
            ORDER BY year
            """
        ).fetchall()
        pop_by_year = {
            int(r[0]): {
                "neuro": int(r[1]),
                "ai": int(r[2]),
                "other": int(r[3]),
                "unknown": int(r[4]),
                "total": int(r[5]),
            }
            for r in per_year_pop
        }

        # Per-year direction tallies. We need n_to_within (e.g., neuro→neuro),
        # n_to_target (neuro→ai), n_to_other, n_to_missing — to construct both
        # the restricted-universe and the population-baseline ORs.
        t1 = time.time()
        edge_tallies = con.execute(
            f"""
            WITH labeled_edges AS (
                SELECT
                    e.citing_year AS year,
                    src.field AS src_field,
                    tgt.field AS tgt_field
                FROM citation_edges e
                JOIN work_field src ON src.work_id = e.citing_work_id
                LEFT JOIN work_field tgt ON tgt.work_id = e.cited_work_id
                WHERE e.citing_year BETWEEN {YEAR_MIN} AND {YEAR_MAX}
                  AND src.field IN ('neuro','ai')
            )
            SELECT
                year,
                src_field,
                COUNT(*) AS n_total,
                SUM(CASE WHEN tgt_field = 'neuro' THEN 1 ELSE 0 END) AS n_to_neuro,
                SUM(CASE WHEN tgt_field = 'ai'    THEN 1 ELSE 0 END) AS n_to_ai,
                SUM(CASE WHEN tgt_field = 'other' THEN 1 ELSE 0 END) AS n_to_other,
                SUM(CASE WHEN tgt_field IS NULL   THEN 1 ELSE 0 END) AS n_to_missing
            FROM labeled_edges
            GROUP BY year, src_field
            ORDER BY year, src_field
            """
        ).fetchall()
        logger.info("Edge tallies computed in %.1fs", time.time() - t1)

        rows = []
        for year, src, n_total, n_to_neuro, n_to_ai, n_to_other, n_to_missing in edge_tallies:
            year = int(year)
            n_total = int(n_total)
            n_to_neuro = int(n_to_neuro)
            n_to_ai = int(n_to_ai)
            n_to_other = int(n_to_other)
            n_to_missing = int(n_to_missing)
            if src not in ("neuro", "ai"):
                continue
            tgt_label = "ai" if src == "neuro" else "neuro"
            n_to_target = n_to_ai if src == "neuro" else n_to_neuro
            n_to_within = n_to_neuro if src == "neuro" else n_to_ai

            pop = pop_by_year.get(year)
            if pop is None:
                continue

            # ---- Restricted-universe OR (recommended) -------------------
            # Conditions on edges to {neuro, ai}; excludes 'other' and missing.
            n_restricted = n_to_within + n_to_target
            if n_restricted == 0:
                continue
            rho_r = n_to_target / n_restricted
            denom_r = pop["neuro"] + pop["ai"]
            if denom_r == 0:
                continue
            rho_null_r = pop[tgt_label] / denom_r
            or_r = _odds_ratio(rho_r, rho_null_r)
            rho_r_lo, rho_r_hi = _wilson_interval(rho_r, n_restricted)
            or_r_lo = _odds_ratio(rho_r_lo, rho_null_r) if rho_r_lo > 0 else 0.0
            or_r_hi = _odds_ratio(rho_r_hi, rho_null_r) if rho_r_hi < 1 else float("inf")

            # ---- Population-baseline OR (sensitivity / transparency) ----
            n_known_pop = n_total - n_to_missing
            if n_known_pop == 0:
                rho_p = float("nan")
                rho_null_p = float("nan")
                or_p = float("nan")
                or_p_lo = float("nan")
                or_p_hi = float("nan")
            else:
                rho_p = n_to_target / n_known_pop
                denom_p = pop["neuro"] + pop["ai"] + pop["other"]
                if denom_p == 0:
                    rho_null_p = float("nan")
                    or_p = float("nan")
                    or_p_lo = float("nan")
                    or_p_hi = float("nan")
                else:
                    rho_null_p = pop[tgt_label] / denom_p
                    or_p = _odds_ratio(rho_p, rho_null_p)
                    rho_p_lo, rho_p_hi = _wilson_interval(rho_p, n_known_pop)
                    or_p_lo = _odds_ratio(rho_p_lo, rho_null_p) if rho_p_lo > 0 else 0.0
                    or_p_hi = _odds_ratio(rho_p_hi, rho_null_p) if rho_p_hi < 1 else float("inf")

            rows.append(
                {
                    "year": year,
                    "direction": f"{src}_to_{tgt_label}",
                    "n_edges_total": n_total,
                    "n_to_within": n_to_within,
                    "n_to_target": n_to_target,
                    "n_to_other": n_to_other,
                    "n_to_missing": n_to_missing,
                    "rho_restricted": rho_r,
                    "rho_null_restricted": rho_null_r,
                    "rho_population": rho_p,
                    "rho_null_population": rho_null_p,
                    "OR_restricted": or_r,
                    "OR_population": or_p,
                    "or_restricted_lo": or_r_lo,
                    "or_restricted_hi": or_r_hi,
                    "or_population_lo": or_p_lo,
                    "or_population_hi": or_p_hi,
                    "n_works_source": pop[src],
                    "n_works_target": pop[tgt_label],
                    "n_works_other": pop["other"],
                }
            )

        # Persist.
        out_path = derived_dir() / "q1_or_by_year.parquet"
        con.execute(
            """
            CREATE OR REPLACE TEMP TABLE q1_rows (
                year INT,
                direction VARCHAR,
                n_edges_total BIGINT,
                n_to_within BIGINT,
                n_to_target BIGINT,
                n_to_other BIGINT,
                n_to_missing BIGINT,
                rho_restricted DOUBLE,
                rho_null_restricted DOUBLE,
                rho_population DOUBLE,
                rho_null_population DOUBLE,
                OR_restricted DOUBLE,
                OR_population DOUBLE,
                or_restricted_lo DOUBLE,
                or_restricted_hi DOUBLE,
                or_population_lo DOUBLE,
                or_population_hi DOUBLE,
                n_works_source BIGINT,
                n_works_target BIGINT,
                n_works_other BIGINT
            )
            """
        )

        def _clean(x: float) -> float | None:
            if x is None:
                return None
            try:
                if math.isinf(x) or math.isnan(x):
                    return None
            except TypeError:
                return None
            return x

        for r in rows:
            con.execute(
                "INSERT INTO q1_rows VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [
                    r["year"],
                    r["direction"],
                    r["n_edges_total"],
                    r["n_to_within"],
                    r["n_to_target"],
                    r["n_to_other"],
                    r["n_to_missing"],
                    _clean(r["rho_restricted"]),
                    _clean(r["rho_null_restricted"]),
                    _clean(r["rho_population"]),
                    _clean(r["rho_null_population"]),
                    _clean(r["OR_restricted"]),
                    _clean(r["OR_population"]),
                    _clean(r["or_restricted_lo"]),
                    _clean(r["or_restricted_hi"]),
                    _clean(r["or_population_lo"]),
                    _clean(r["or_population_hi"]),
                    r["n_works_source"],
                    r["n_works_target"],
                    r["n_works_other"],
                ],
            )
        con.execute(f"COPY q1_rows TO '{out_path}' (FORMAT 'parquet', COMPRESSION 'snappy')")
        elapsed = time.time() - t0

        # Companion JSON metadata.
        meta_path = derived_dir() / "q1_metadata.json"
        meta = {
            "scheme": "1 (OpenAlex Topics primary, curated AI core)",
            "neuro_field_id": NEURO_FIELD_ID,
            "ai_core_topic_ids": list(AI_CORE_TOPIC_IDS),
            "ai_core_n_topics": len(AI_CORE_TOPIC_IDS),
            "year_range": [YEAR_MIN, YEAR_MAX],
            "year_2026_excluded_reason": "snapshot is ~25% complete for 2026; would distort trends",
            "or_methodology": {
                "primary": "OR_restricted (conditions on edges within {neuro, ai} universe)",
                "secondary": "OR_population (chance baseline includes 'other' pool)",
            },
            "n_works_assigned": n_assigned,
            "n_rows_q1": len(rows),
            "manifest": m.to_dict(),
            "elapsed_s": round(elapsed, 1),
        }
        meta_path.write_text(json.dumps(meta, indent=2))
        logger.info("Q1: wrote %s (%d rows) in %.1fs", out_path, len(rows), elapsed)
        return {
            "out_q1_parquet": str(out_path),
            "out_metadata_json": str(meta_path),
            "n_rows": len(rows),
            "elapsed_s": round(elapsed, 1),
            "coverage_fraction": round(cov, 3),
            "tier1_present": m.tier1_present_count,
        }
    finally:
        if owns_con:
            con.close()


def _cli() -> None:
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

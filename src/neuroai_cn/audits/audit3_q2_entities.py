"""Block C — Audit 3: Q2 entity diagnosis.

Diagnoses what passes the current q2_dual_citizens.py threshold-B filter.
The user does not write cleaning rules tonight — this audit produces the
table the user reads in the morning to write rules from.

Outputs (under data/derived/audits/20260508/):
    audit3_top100_diagnosis.csv  — top-100 dual citizens with 3 flags + hand_verdict blank
    audit3_random100_baseline.csv — random-100 from the long tail with same schema
    audit3_REPORT.md             — 1-page summary

Three flags computed per row:
    flag_supercluster        — total_paper_count > 1000 AND distinct_institutions > 5
    flag_entity_not_human    — display_name regex match (Journal/Press/Inc/University/etc.)
    flag_common_collision_risk — high-frequency surname + single-initial pattern

Sentinel: _audit3.done on success.

This audit is diagnostic only — no pass/fail criteria.
"""

from __future__ import annotations

import csv
import logging
import re
import sys
import time
import traceback
from pathlib import Path

import duckdb

from .. import config
from ..utils.duckdb import get_connection

logger = logging.getLogger(__name__)

AUDITS_DIR = config.AUDITS_DIR / "20260508"
SENTINEL_DONE = AUDITS_DIR / "_audit3.done"
SENTINEL_FAIL = AUDITS_DIR / "_audit3.failed"

ENTITY_PATTERN = re.compile(
    r"\b(Journal|Journals|Press|Inc\.?|Inc$|LLC|GmbH|Ltd|Limited|"
    r"University|Universidad|Université|Universität|Università|"
    r"Institute|Institut|Department|Hospital|"
    r"Authors|Anonymous|Editors|Editorial|Society|"
    r"Conference|Proceedings|Group|Foundation|"
    r"Tagung|Conférence|Konferenz|Programa)\b",
    re.IGNORECASE,
)

# OpenAlex placeholder pattern — A99999999... and similar.
PLACEHOLDER_ID_PATTERN = re.compile(r"^https?://openalex\.org/A9{4,}")

# Common surnames empirically associated with OpenAlex disambiguation collisions.
# This is a TECHNICAL DISAMBIGUATION RISK INDICATOR. Combined with single-initial
# given names, it flags author records likely to be disambiguation aggregates,
# not quality judgements about any individual.
COLLISION_PRONE_SURNAMES = {
    "wang",
    "liu",
    "chen",
    "li",
    "zhang",
    "patel",
    "kumar",
    "singh",
    "mohammed",
    "khan",
    "park",
    "kim",
    "lee",
    "yang",
    "zhao",
    "wu",
    "yu",
    "huang",
    "xu",
    "sun",
    "yan",
    "qiu",
    "tan",
    "zhou",
    "ma",
    "guo",
    "zheng",
    "chang",
    "wong",
    "ho",
    "cho",
}

INITIAL_PATTERN = re.compile(r"^([A-Z][a-zA-Záéíóúäöüñ]+)\s+([A-Z]\.?)$")


def detect_entity_not_human(display_name: str | None) -> bool:
    if not display_name:
        return False
    return bool(ENTITY_PATTERN.search(display_name))


def detect_collision_risk(display_name: str | None, author_id: str | None) -> bool:
    """High-frequency surname + single-initial given name pattern.

    Flag is a technical disambiguation risk indicator, not a quality judgement
    about any author. Flagged records need ORCID + affiliation cross-check
    before being interpreted as a single human researcher.
    """
    if not display_name:
        return False
    # Pattern: 'Surname X.' or 'Surname X' (single initial)
    m = INITIAL_PATTERN.match(display_name.strip())
    if m is None:
        return False
    surname = m.group(1).lower()
    return surname in COLLISION_PRONE_SURNAMES


def detect_placeholder_id(author_id: str | None) -> bool:
    if not author_id:
        return False
    return bool(PLACEHOLDER_ID_PATTERN.match(author_id))


def enrich_authors(con: duckdb.DuckDBPyConnection, author_ids: list[str]) -> dict[str, dict]:
    """Look up enrichment data for a list of author IDs.

    Returns a dict author_id -> {total_paper_count, orcid, n_distinct_inst,
        n_distinct_country, raw_display_name}.
    """
    if not author_ids:
        return {}
    # Insert into temp table for join
    con.execute("""
        CREATE OR REPLACE TEMP TABLE _aud3_target_authors (author_id VARCHAR)
    """)
    con.executemany(
        "INSERT INTO _aud3_target_authors VALUES (?)",
        [(a,) for a in author_ids],
    )

    # Get authors table info
    out = {}
    rows = con.execute("""
        SELECT
            t.author_id,
            a.display_name,
            a.orcid,
            a.works_count,
            a.cited_by_count
        FROM _aud3_target_authors t
        LEFT JOIN authors a ON a.id = t.author_id
    """).fetchall()
    for aid, dn, orcid, wc, cc in rows:
        out[aid] = {
            "author_id": aid,
            "display_name_authors_table": dn,
            "orcid": orcid,
            "total_paper_count_authors_table": int(wc) if wc is not None else None,
            "cited_by_count": int(cc) if cc is not None else None,
            "n_distinct_institutions": 0,
            "n_distinct_countries": 0,
        }

    # Distinct institution + country counts via authorships.
    # We use the authorships dataset cache (parquet files at _authorships_parts).
    # But since we already have per-author rich enrichment from authors table
    # for total works, and getting institution diversity over the whole
    # bibliography is expensive, we use a simpler proxy: distinct institutions
    # from the `authors.affiliations` array (precomputed by OpenAlex).
    inst_rows = con.execute("""
        WITH unrolled AS (
            SELECT
                t.author_id,
                UNNEST(a.affiliations) AS aff
            FROM _aud3_target_authors t
            LEFT JOIN authors a ON a.id = t.author_id
        )
        SELECT
            author_id,
            COUNT(DISTINCT aff.institution.id) AS n_distinct_inst,
            COUNT(DISTINCT aff.institution.country_code) AS n_distinct_country
        FROM unrolled
        GROUP BY author_id
    """).fetchall()
    for aid, ni, nc in inst_rows:
        if aid in out:
            out[aid]["n_distinct_institutions"] = int(ni) if ni else 0
            out[aid]["n_distinct_countries"] = int(nc) if nc else 0
    return out


def compute_flags(record: dict) -> dict:
    """Return three flags + the diagnostic substring used."""
    name = record.get("display_name") or record.get("display_name_authors_table") or ""
    aid = record.get("author_id")
    total = record.get("total_paper_count") or record.get("total_paper_count_authors_table") or 0
    n_inst = record.get("n_distinct_institutions") or 0

    flag_supercluster = bool(total > 1000 and n_inst > 5)
    flag_entity = detect_entity_not_human(name)
    flag_collision = detect_collision_risk(name, aid)
    flag_placeholder = detect_placeholder_id(aid)

    return {
        "flag_supercluster": flag_supercluster,
        "flag_entity_not_human": flag_entity or flag_placeholder,
        "flag_placeholder_id": flag_placeholder,
        "flag_common_collision_risk": flag_collision,
    }


def write_csv(rows: list[dict], out_path: Path) -> None:
    fields = [
        "rank",
        "author_id",
        "display_name",
        "n_neuro_papers",
        "n_ai_papers",
        "total_paper_count",
        "orcid_present",
        "n_distinct_institutions",
        "n_distinct_countries",
        "best_window_start",
        "best_window_end",
        "flag_supercluster",
        "flag_entity_not_human",
        "flag_placeholder_id",
        "flag_common_collision_risk",
        "any_flag",
        "hand_verdict",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({f: r.get(f, "") for f in fields})


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    for s in (SENTINEL_DONE, SENTINEL_FAIL):
        if s.exists():
            s.unlink()
    t0 = time.time()
    try:
        con = get_connection(read_only=True)
        try:
            con.execute("PRAGMA threads=8")
            con.execute("PRAGMA memory_limit='12GB'")

            # 1) Load existing q2_named_examples.parquet (top-200 dual citizens, threshold B)
            named_path = str(config.DERIVED_DIR / "q2_named_examples.parquet")
            top_rows = con.execute(f"""
                SELECT
                    ROW_NUMBER() OVER (ORDER BY min_side DESC, n_neuro DESC) AS rank,
                    author_id,
                    display_name,
                    orcid,
                    n_neuro,
                    n_ai,
                    min_side,
                    best_window_start,
                    best_window_end
                FROM read_parquet('{named_path}')
                ORDER BY min_side DESC, n_neuro DESC
                LIMIT 100
            """).fetchall()
            logger.info("Loaded top-100 dual citizens from q2_named_examples")

            top_records = []
            for rk, aid, dn, orcid, nn, na, ms, ws, we in top_rows:
                top_records.append(
                    {
                        "rank": int(rk),
                        "author_id": aid,
                        "display_name": dn,
                        "orcid": orcid,
                        "n_neuro_papers": int(nn) if nn else 0,
                        "n_ai_papers": int(na) if na else 0,
                        "min_side": int(ms) if ms else 0,
                        "best_window_start": int(ws) if ws else None,
                        "best_window_end": int(we) if we else None,
                    }
                )

            top_aids = [r["author_id"] for r in top_records]
            logger.info("Enriching top-100 author records...")
            top_enrich = enrich_authors(con, top_aids)
            for r in top_records:
                e = top_enrich.get(r["author_id"], {})
                r["total_paper_count"] = e.get("total_paper_count_authors_table")
                r["n_distinct_institutions"] = e.get("n_distinct_institutions", 0)
                r["n_distinct_countries"] = e.get("n_distinct_countries", 0)
                r["orcid_present"] = bool(r.get("orcid"))
                # Merge enrichment for flag computation
                r["display_name_authors_table"] = e.get("display_name_authors_table")
                flags = compute_flags(r)
                r.update(flags)
                r["any_flag"] = (
                    flags["flag_supercluster"]
                    or flags["flag_entity_not_human"]
                    or flags["flag_common_collision_risk"]
                )
                r["hand_verdict"] = ""

            top_csv = AUDITS_DIR / "audit3_top100_diagnosis.csv"
            write_csv(top_records, top_csv)
            logger.info("Wrote top-100 diagnosis to %s", top_csv)

            # 2) Random-100 baseline from the long tail (rank 201+ in the q2 dual_citizens
            #    parquet at threshold B)
            dc_path = str(config.DERIVED_DIR / "q2_dual_citizens.parquet")
            dc_schema = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{dc_path}')").fetchall()
            logger.info("q2_dual_citizens schema: %s", [c[0] for c in dc_schema])
            # Use threshold = B and sample randomly outside top-200.
            random_rows = con.execute(f"""
                WITH ranked AS (
                    SELECT
                        author_id,
                        n_neuro,
                        n_ai,
                        LEAST(n_neuro, n_ai) AS min_side,
                        best_window_start,
                        ROW_NUMBER() OVER (ORDER BY LEAST(n_neuro, n_ai) DESC) AS rk
                    FROM read_parquet('{dc_path}')
                    WHERE LOWER(threshold) = 'b'
                )
                SELECT
                    r.rk,
                    r.author_id,
                    r.n_neuro,
                    r.n_ai,
                    r.min_side,
                    r.best_window_start
                FROM ranked r
                WHERE r.rk > 200
                USING SAMPLE 100
            """).fetchall()
            logger.info("Sampled %d random tail records", len(random_rows))

            random_records = []
            for rk, aid, nn, na, ms, ws in random_rows:
                random_records.append(
                    {
                        "rank": int(rk),
                        "author_id": aid,
                        "display_name": "",  # filled from authors lookup
                        "orcid": None,
                        "n_neuro_papers": int(nn) if nn else 0,
                        "n_ai_papers": int(na) if na else 0,
                        "min_side": int(ms) if ms else 0,
                        "best_window_start": int(ws) if ws else None,
                        "best_window_end": None,
                    }
                )

            rand_aids = [r["author_id"] for r in random_records]
            rand_enrich = enrich_authors(con, rand_aids)
            for r in random_records:
                e = rand_enrich.get(r["author_id"], {})
                r["display_name"] = e.get("display_name_authors_table") or ""
                r["orcid"] = e.get("orcid")
                r["orcid_present"] = bool(r["orcid"])
                r["total_paper_count"] = e.get("total_paper_count_authors_table")
                r["n_distinct_institutions"] = e.get("n_distinct_institutions", 0)
                r["n_distinct_countries"] = e.get("n_distinct_countries", 0)
                r["display_name_authors_table"] = e.get("display_name_authors_table")
                flags = compute_flags(r)
                r.update(flags)
                r["any_flag"] = (
                    flags["flag_supercluster"]
                    or flags["flag_entity_not_human"]
                    or flags["flag_common_collision_risk"]
                )
                r["hand_verdict"] = ""

            rand_csv = AUDITS_DIR / "audit3_random100_baseline.csv"
            write_csv(random_records, rand_csv)
            logger.info("Wrote random-100 baseline to %s", rand_csv)

            # 3) Compute summary rates + write report
            def rate(rows: list[dict], key: str) -> tuple[int, float]:
                n = sum(1 for r in rows if r.get(key))
                return n, n / len(rows) if rows else 0.0

            top_summary = {
                k: rate(top_records, k)
                for k in [
                    "flag_supercluster",
                    "flag_entity_not_human",
                    "flag_placeholder_id",
                    "flag_common_collision_risk",
                    "any_flag",
                ]
            }
            rand_summary = {
                k: rate(random_records, k)
                for k in [
                    "flag_supercluster",
                    "flag_entity_not_human",
                    "flag_placeholder_id",
                    "flag_common_collision_risk",
                    "any_flag",
                ]
            }

            report_path = AUDITS_DIR / "audit3_REPORT.md"
            with report_path.open("w", encoding="utf-8") as fh:
                fh.write("# Audit 3 — Q2 entity diagnosis report\n\n")
                fh.write("**Date:** 2026-05-08 (overnight run)\n\n")
                fh.write("**Diagnostic only** — no pass/fail. The user reads the two CSVs\n")
                fh.write("in the morning and writes Q2 cleaning rules from them.\n\n")
                fh.write("## Top-100 dual citizens (threshold B)\n\n")
                fh.write(
                    "Loaded from `data/derived/q2_named_examples.parquet`, ranked by `min_side` then `n_neuro`. CSV: `audit3_top100_diagnosis.csv`.\n\n"
                )
                fh.write("Flag rates:\n\n")
                for k, (n, r) in top_summary.items():
                    fh.write(f"- **{k}** — {n}/100 = {r:.2%}\n")
                fh.write("\n")
                fh.write(
                    "## Random-100 baseline (rank > 200, sampled from long tail at threshold B)\n\n"
                )
                fh.write("CSV: `audit3_random100_baseline.csv`.\n\n")
                fh.write("Flag rates:\n\n")
                for k, (n, r) in rand_summary.items():
                    fh.write(f"- **{k}** — {n}/100 = {r:.2%}\n")
                fh.write("\n")
                fh.write("## Comparison\n\n")
                fh.write("| Flag | top-100 | random-100 | top - random |\n")
                fh.write("|------|--------:|-----------:|-------------:|\n")
                for k in top_summary:
                    _, tr = top_summary[k]
                    _, rr = rand_summary[k]
                    fh.write(f"| {k} | {tr:.2%} | {rr:.2%} | {(tr - rr):+.2%} |\n")
                fh.write("\n")
                fh.write("## Examples by flag class (top-100)\n\n")
                for flag in [
                    "flag_supercluster",
                    "flag_entity_not_human",
                    "flag_placeholder_id",
                    "flag_common_collision_risk",
                ]:
                    fh.write(f"### {flag}\n")
                    examples = [r for r in top_records if r.get(flag)][:10]
                    for e in examples:
                        fh.write(
                            f"- rank {e['rank']:3d}: {e['display_name']!r} (id={e['author_id']}, total_papers={e.get('total_paper_count')}, n_neuro={e['n_neuro_papers']}, n_ai={e['n_ai_papers']}, n_distinct_institutions={e.get('n_distinct_institutions')})\n"
                        )
                    fh.write("\n")
                fh.write("## Suggested cleaning-rule starting points (user finalises)\n\n")
                fh.write("These are starting points, NOT decisions. The user should examine the\n")
                fh.write("top-100 CSV directly and define final rules. Suggestions:\n\n")
                fh.write(
                    "1. **Hard-reject placeholder IDs.** Records with `flag_placeholder_id` (`A9999999999`, etc.) are not real OpenAlex authors.\n"
                )
                fh.write(
                    "2. **Hard-reject entity-not-human.** Records matching `flag_entity_not_human` (Journal/Press/University/Conference/etc.) are venue/institution names mis-classified as authors.\n"
                )
                fh.write(
                    "3. **Demote (or manual whitelist) superclusters.** `flag_supercluster` = total works > 1000 AND >5 distinct institutions. Most are disambiguation-aggregate authors that should be split. A few may be real prolific authors with broad institutional affiliations — manual whitelist if so.\n"
                )
                fh.write(
                    "4. **Common-surname single-initial collision risk.** `flag_common_collision_risk` flags need ORCID + institution cross-check. Where ORCID is present and institution is consistent, the record is likely a real author. Where neither is present, treat as un-disambiguatable.\n"
                )
                fh.write("\n")
                fh.write("## Bias diagnostic\n\n")
                fh.write(
                    "If flag rates are substantially higher in top-100 than in the random-100 baseline,\n"
                )
                fh.write(
                    "the threshold-B selection is biased toward bad entries — i.e. the criteria most\n"
                )
                fh.write(
                    "affecting Q2 (number of papers in each field) correlate with the same patterns\n"
                )
                fh.write("that produce false-positive author records (supercluster aggregation).\n")

            logger.info("Wrote report to %s", report_path)
        finally:
            con.close()

        elapsed = time.time() - t0
        SENTINEL_DONE.write_text(
            f"audit3: DONE — top-100 + random-100 enriched and flagged; "
            f"see audit3_REPORT.md; elapsed {elapsed:.1f}s\n"
        )
        logger.info("Audit 3 DONE in %.1fs", elapsed)
        return 0
    except Exception as exc:
        tb = traceback.format_exc()
        SENTINEL_FAIL.write_text(f"audit3: ERROR — {type(exc).__name__}: {exc}\n\n{tb}\n")
        logger.exception("Audit 3 errored")
        return 2


if __name__ == "__main__":
    sys.exit(main())

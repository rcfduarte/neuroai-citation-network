"""Verify the DuckDB index — row counts, sanity checks, canonical-bridge presence.

Writes results to logs/build-status.md (appends a new section).

Usage:
    python scripts/verify_index.py
"""

from __future__ import annotations

import time

import duckdb

from neuroai_cn import config

DATA_ROOT = config.DATA_ROOT
DUCKDB_PATH = config.DUCKDB_PATH
REPO_ROOT = config.REPO_ROOT
STATUS_MD = REPO_ROOT / "logs" / "build-status.md"

# Tier 1 canonical bridges — must surface (foundation §5).
TIER1_DOIS = [
    ("Zador 2023 Nat Commun", "10.1038/s41467-023-37180-x"),
    ("Richards 2019 Nat Neurosci", "10.1038/s41593-019-0520-2"),
    ("Hassabis 2017 Neuron", "10.1016/j.neuron.2017.06.011"),
    ("Kriegeskorte-Douglas 2018 Nat Neurosci", "10.1038/s41593-018-0210-5"),
]


def run_query(con: duckdb.DuckDBPyConnection, label: str, sql: str) -> tuple[str, str]:
    t0 = time.time()
    rows = con.execute(sql).fetchall()
    dt = time.time() - t0
    if len(rows) == 1 and len(rows[0]) == 1:
        result = f"{rows[0][0]:,}" if isinstance(rows[0][0], int) else str(rows[0][0])
    else:
        result = "\n" + "\n".join("  " + " | ".join(str(c) for c in r) for r in rows)
    return label, f"{result}  _(query: {dt:.1f}s)_"


def main() -> None:
    if not DUCKDB_PATH.exists():
        raise FileNotFoundError(f"DuckDB not found at {DUCKDB_PATH}")

    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    # Bound memory tightly — verification queries are aggregates, not full
    # scans, so even 8GB is generous. The COUNT(DISTINCT primary_topic.id)
    # query previously OOM-killed the process at ~37 GB without an explicit
    # cap; retired here in favour of a cheap topics-table count.
    con.execute("SET memory_limit='8GB'")
    con.execute("SET threads=4")

    queries = [
        (
            "Total works (1990-2026)",
            "SELECT COUNT(*) FROM works WHERE publication_year BETWEEN 1990 AND 2026",
        ),
        ("Authors", "SELECT COUNT(*) FROM authors"),
        ("Sources", "SELECT COUNT(*) FROM sources"),
        ("Institutions", "SELECT COUNT(*) FROM institutions"),
        ("Topics (master table)", "SELECT COUNT(*) FROM topics"),
        ("Citation edges", "SELECT COUNT(*) FROM citation_edges"),
        ("Works with primary_topic", "SELECT COUNT(*) FROM works WHERE primary_topic IS NOT NULL"),
        (
            "Works with referenced_works (citing edges)",
            "SELECT COUNT(*) FROM works WHERE referenced_works IS NOT NULL AND len(referenced_works) > 0",
        ),
        ("Works in 2023", "SELECT COUNT(*) FROM works WHERE publication_year = 2023"),
    ]

    results = []
    for label, sql in queries:
        try:
            results.append(run_query(con, label, sql))
        except duckdb.Error as e:
            results.append((label, f"ERROR — {e}"))

    # Tier 1 bridges
    bridge_rows = []
    for name, doi in TIER1_DOIS:
        # OpenAlex stores DOIs as full URL (`https://doi.org/X`); the API
        # supplement also uses that form. Match either form for robustness.
        sql = f"""
            SELECT id, doi, title, publication_year, cited_by_count, updated_date
            FROM works
            WHERE doi = 'https://doi.org/{doi}' OR doi = '{doi}'
            LIMIT 1
        """
        try:
            rows = con.execute(sql).fetchall()
            if rows:
                _id, _doi, title, year, cites, upd = rows[0]
                title_short = (title or "")[:60]
                # Heuristic: if updated_date matches today, almost certainly the API supplement
                src = " (API supplement)" if upd and str(upd).startswith("2026-04-29") else ""
                bridge_rows.append(
                    f"  ✅ {name} — `{_doi}` — {year}, {cites:,} citations{src} — {title_short}…"
                )
            else:
                bridge_rows.append(f"  ❌ {name} — `{doi}` — NOT FOUND")
        except duckdb.Error as e:
            bridge_rows.append(f"  ⚠️  {name} — `{doi}` — query error: {e}")

    # Format markdown section
    lines = []
    lines.append("")
    lines.append(f"## Verification — {time.strftime('%Y-%m-%dT%H:%M:%S%z')}")
    lines.append("")
    lines.append(f"DuckDB file: `{DUCKDB_PATH}` ({DUCKDB_PATH.stat().st_size / 1024**3:.1f} GB)")
    lines.append("")
    lines.append("### Row counts + sanity checks")
    lines.append("")
    for label, val in results:
        lines.append(f"- **{label}:** {val}")
    lines.append("")
    lines.append("### Tier 1 canonical bridges (must surface)")
    lines.append("")
    lines.extend(bridge_rows)
    lines.append("")
    if all("✅" in r for r in bridge_rows):
        lines.append("**Tier 1 PASSED — all 4 canonical bridges present.**")
    else:
        lines.append(
            "**Tier 1 FAILED — one or more canonical bridges missing. Investigate before Q1.**"
        )
    lines.append("")

    section = "\n".join(lines)
    print(section)

    with STATUS_MD.open("a", encoding="utf-8") as f:
        f.write(section)
    print(f"\nAppended to {STATUS_MD}")


if __name__ == "__main__":
    main()

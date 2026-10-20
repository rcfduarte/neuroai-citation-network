"""Pool 4 — Seed authors (foundation §1.4 / METHODS §2.4).

Six sub-tiers (4a–4f) of named authors whose entire publication output enters
the corpus. The hard rule (cross-pool): seed authors from classical
molecular/cellular/circuits work MUST have demonstrated a functional connection
to computation/learning/cognition. Pure-anatomy figures are filtered.

Author resolution strategy (tonight's pragmatic version):
  - Where ORCID is known, match by ORCID (deterministic).
  - Otherwise match by `display_name` against the `authors` table. We then
    enforce a `works_count` floor of 5 to filter out ORCID-less near-namesake
    junior authors and a `display_name = ?` exact match (case-insensitive) to
    avoid surname-only matches.
  - Surname collisions (Aertsen, Engel, Wang) are flagged but not filtered out
    automatically — disambiguating them requires per-paper institutional check
    that we'll add later. Marked `disambiguation_needed=true` in the output.

Output: data/derived/pool4.parquet
    work_id, in_pool=true, source_tag='pool4', sub_pool VARCHAR[]
"""

from __future__ import annotations

import argparse
import logging
import time

import duckdb

from ..utils.authorships import ensure_cache
from ..utils.duckdb import derived_dir, get_connection, set_temp_directory

logger = logging.getLogger(__name__)

# 4a — Brand era (Zador-27 + Luppi/Achterberg trainees + named-program faculty).
# These resolve mostly via Pool 1's anchor-signatory query but we also enumerate
# a few extra named-program-faculty by display name.
SEED_4A_NAMES: tuple[str, ...] = (
    "Anthony M. Zador",
    "Blake A. Richards",
    "Bence Ölveczky",
    "Yoshua Bengio",
    "Kwabena Boahen",
    "Matthew Botvinick",
    "Mitya Chklovskii",
    "Anne K. Churchland",
    "Claudia Clopath",
    "James J. DiCarlo",
    "Surya Ganguli",
    "Konrad Körding",
    "Yann LeCun",
    "Timothy P. Lillicrap",
    "Adam H. Marblestone",
    "Bruno A. Olshausen",
    "Alexandre Pouget",
    "Cristina Savin",
    "Terrence J. Sejnowski",
    "Eero P. Simoncelli",
    "Sara Solla",
    "David Sussillo",
    "Andreas S. Tolias",
    "Doris Y. Tsao",
    "Demis Hassabis",
    # named-program faculty
    "SueYeon Chung",
    "Martin Schrimpf",
    "Patrick Mineault",
    "Caswell Barry",
    # 2026-07-31: was "Yamins Daniel", a name-order error that resolved to nothing.
    "Daniel Yamins",
    # 2026-07-31: three Zador-2023 signatories were on the foundation roster but
    # absent from this list, so their output never entered the pool.
    "G. Sean Escola",
    "Jeff Hawkins",
    "Alexei A. Koulakov",
    "Aran Nayebi",
    "Liam Paninski",
    "Jonathan W. Pillow",
    "H. Sebastian Seung",
    "Maneesh Sahani",
    "Tom Mrsic-Flogel",
    "Kenneth D. Harris",
    "Quentin J. M. Huys",
    "Matthias Bethge",
    "Jakob H. Macke",
    "Rui Ponte Costa",
    "Andrew Saxe",
    "Cengiz Pehlevan",
    "Marcel A. J. van Gerven",
)

# 4b — Classical bridges (PDP, Marr, Hopfield).
SEED_4B_NAMES: tuple[str, ...] = (
    "David E. Rumelhart",
    "James L. McClelland",
    "Geoffrey E. Hinton",
    "John J. Hopfield",
    "Stephen Grossberg",
    "Peter Dayan",
    "Larry F. Abbott",
    "Patricia S. Churchland",
    "Paul M. Churchland",
    "Teuvo Kohonen",
    "James A. Anderson",
    "Tomaso A. Poggio",
)

# 4c — Biological cybernetics.
SEED_4C_NAMES: tuple[str, ...] = (
    "Shun-ichi Amari",
    "Christoph von der Malsburg",
    "Günther Palm",
    "Ad Aertsen",
    "Valentin Braitenberg",
    "Kunihiko Fukushima",
    "Heinrich H. Bülthoff",
    "Bernhard Schölkopf",
    "Wolfgang Maass",
    "Robert Legenstein",
    "Herbert Jaeger",
)

# 4d — Theoretical / computational neuroscience.
SEED_4D_NAMES: tuple[str, ...] = (
    "Haim Sompolinsky",
    "Daniel J. Amit",
    "Nicolas Brunel",
    "William Bialek",
    "Fred Rieke",
    "Peter E. Latham",
    "Wulfram Gerstner",
    "Tim P. Vogels",
    "Henning Sprekeler",
    "Cengiz Pehlevan",  # also 4a
    "Ila R. Fiete",
    "Eric Shea-Brown",
    "Stefano Fusi",
    "Xiao-Jing Wang",
    "Kanaka Rajan",
    "Srdjan Ostojic",
    # Bern group + bio-plausible learning
    "Walter Senn",
    "Mihai A. Petrovici",
    "Katharina A. Wilmes",
    "Cristiano Capone",
    "João Sacramento",
    # Continental EU theory
    "Boris S. Gutkin",
    "Carl van Vreeswijk",
    "Magnus J. E. Richardson",
    "Sophie Denève",
    "Mark C. W. van Rossum",
    "Christian K. Machens",
    # Z-supplement
    "Luca Mazzucato",
    "Ashok Litwin-Kumar",
    "Richard Naud",
    "Francesca Mastrogiuseppe",
    "Manuel Beiran",
    "Dean V. Buonomano",
)

# 4e — Skeptics + measured critics (cleaned 13-name roster).
SEED_4E_NAMES: tuple[str, ...] = (
    "Gary F. Marcus",
    "Noam Chomsky",
    "Walid S. Saba",
    "Subbarao Kambhampati",
    "Thomas G. Bever",
    "Sandiway Fong",
    "Massimo Piattelli-Palmarini",
    "Emily M. Bender",
    "Timnit Gebru",
    "Jeffrey S. Bowers",
    "David Poeppel",
    "Melanie Mitchell",
    "Olivia Guest",
    "Andrea E. Martin",
    "Kyle Mahowald",
    "Ida Momennejad",
    "Federico Adolfi",
    "Eric Jonas",
)

# 4f — Safety + interpretability via neuroscience.
SEED_4F_NAMES: tuple[str, ...] = (
    "Patrick J. Mineault",  # also 4a
    "Christopher Olah",
    "Trenton Bricken",
    "Jack Lindsey",
    "Catherine Olsson",
    "Yann LeCun",  # filtered (also 4a; partial only here)
    # 2026-07-31: "Anders Sandberg" removed — never on the foundation 4f roster,
    # and the resolved author (221 works) is the FHI philosopher, not a
    # neuroscience-facing interpretability researcher. Contributed 9 works.
    "Emily Mackevicius",
    "Steven Byrnes",
    "Connor Leahy",
    "Murray Shanahan",
    "Max Tegmark",
    "Julian Jara-Ettinger",
    "Marcelo Mattar",
    # 2026-07-31: "Nathan A. Sanborn" and "Pedro A. Tavares" removed — both are
    # almost certainly mis-rendered Mineault-2024 co-signatories, and neither
    # resolves against the authors table, so both were silent no-ops.
)

SUB_TIERS: dict[str, tuple[str, ...]] = {
    "4a": SEED_4A_NAMES,
    "4b": SEED_4B_NAMES,
    "4c": SEED_4C_NAMES,
    "4d": SEED_4D_NAMES,
    "4e": SEED_4E_NAMES,
    "4f": SEED_4F_NAMES,
}

# Surnames known to have OpenAlex collisions (METHODS §2.4 hard rule).
KNOWN_AMBIGUOUS_SURNAMES = ("Aertsen", "Engel", "Wang", "Anderson", "Wilson", "Smith")

MIN_WORKS_COUNT = 5  # ORCID-less authors below this threshold are filtered.


def _tune(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("PRAGMA threads=12")
    con.execute("PRAGMA memory_limit='30GB'")
    set_temp_directory(con)


def _build_seed_table(con: duckdb.DuckDBPyConnection) -> tuple[int, int]:
    """Build temp table pool4_seed_names(name, sub_tier). Returns (n_inserts, n_unique)."""
    con.execute("CREATE OR REPLACE TEMP TABLE pool4_seed_names (name VARCHAR, sub_tier VARCHAR)")
    rows = []
    for sub, names in SUB_TIERS.items():
        for n in names:
            rows.append((n, sub))
    con.executemany("INSERT INTO pool4_seed_names VALUES (?, ?)", rows)
    n_total = con.execute("SELECT COUNT(*) FROM pool4_seed_names").fetchone()[0]
    n_unique = con.execute("SELECT COUNT(DISTINCT name) FROM pool4_seed_names").fetchone()[0]
    return int(n_total), int(n_unique)


def _resolve_author_ids(con: duckdb.DuckDBPyConnection) -> int:
    """Resolve seed names → author IDs. Multiple matches per name are kept (collisions)."""
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE pool4_authors AS
        WITH matches AS (
            SELECT
                a.id AS author_id,
                a.display_name,
                a.works_count,
                s.name AS seed_name,
                s.sub_tier
            FROM pool4_seed_names s
            JOIN authors a ON lower(a.display_name) = lower(s.name)
            WHERE a.works_count >= {MIN_WORKS_COUNT}
        )
        SELECT
            author_id,
            list_distinct(list(sub_tier)) AS sub_tiers,
            list_distinct(list(seed_name)) AS seed_names,
            -- Disambiguation flag: surname appears in our known-ambiguous list.
            list_has_any(string_split(any_value(display_name), ' '),
                         {list(KNOWN_AMBIGUOUS_SURNAMES)}) AS disambiguation_needed
        FROM matches
        GROUP BY author_id
        """
    )
    n = con.execute("SELECT COUNT(*) FROM pool4_authors").fetchone()[0]
    return int(n)


def build(con: duckdb.DuckDBPyConnection | None = None) -> dict:
    owns_con = con is None
    if owns_con:
        con = get_connection(read_only=True)
    try:
        _tune(con)
        t0 = time.time()
        n_seeds_total, n_seeds_unique = _build_seed_table(con)
        n_authors = _resolve_author_ids(con)
        # Per sub-tier resolution rate
        per_tier_resolved = dict(
            con.execute(
                "SELECT sub, COUNT(DISTINCT a.author_id) FROM pool4_authors a, UNNEST(a.sub_tiers) AS t(sub) GROUP BY sub"
            ).fetchall()
        )
        per_tier_seeds = {
            "4a": len(set(SEED_4A_NAMES)),
            "4b": len(set(SEED_4B_NAMES)),
            "4c": len(set(SEED_4C_NAMES)),
            "4d": len(set(SEED_4D_NAMES)),
            "4e": len(set(SEED_4E_NAMES)),
            "4f": len(set(SEED_4F_NAMES)),
        }
        t_authors = time.time() - t0
        logger.info(
            "Pool 4 authors: %d resolved (from %d seeds → %d unique). Per-tier resolution: %s",
            n_authors,
            n_seeds_total,
            n_seeds_unique,
            per_tier_resolved,
        )

        cache_path = ensure_cache(con, allow_partial=True)
        out_path = derived_dir() / "pool4.parquet"
        t1 = time.time()
        con.execute(
            f"""
            COPY (
              SELECT
                e.work_id,
                TRUE AS in_pool,
                'pool4' AS source_tag,
                list_distinct(flatten(list(p.sub_tiers))) AS sub_pool,
                BOOL_OR(p.disambiguation_needed) AS disambiguation_needed
              FROM read_parquet({cache_path}) e
              JOIN pool4_authors p ON p.author_id = e.author_id
              WHERE e.year BETWEEN 1990 AND 2026
              GROUP BY e.work_id
            )
            TO '{out_path}' (FORMAT 'parquet', COMPRESSION 'snappy')
            """
        )
        t_works = time.time() - t1
        n_works = con.execute(f"SELECT COUNT(*) FROM read_parquet('{out_path}')").fetchone()[0]
        n_amb = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{out_path}') WHERE disambiguation_needed"
        ).fetchone()[0]
        elapsed = time.time() - t0
        logger.info(
            "Pool 4: wrote %s (%d works, %d disambiguation-flagged) total=%.1fs (authors %.1fs, join %.1fs)",
            out_path,
            n_works,
            n_amb,
            elapsed,
            t_authors,
            t_works,
        )
        return {
            "seed_names_total": n_seeds_total,
            "seed_names_unique": n_seeds_unique,
            "pool4_authors": n_authors,
            "per_sub_tier_seeds": per_tier_seeds,
            "per_sub_tier_authors_resolved": {k: int(v) for k, v in per_tier_resolved.items()},
            "pool4_works": int(n_works),
            "pool4_works_disambiguation_flagged": int(n_amb),
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

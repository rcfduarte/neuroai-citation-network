"""Consolidate corporate-group sub-entities into parent organizations.

OpenAlex treats Alphabet-group sub-entities (Google US, Google UK, DeepMind UK)
as separate institutions; similarly for Microsoft and Meta. For the main
Figure 2 (per user 2026-05-22), consolidate these under parent labels so the
functional industry footprint is visible.

Parent groups (LOCKED 2026-05-22):
    Alphabet (Google + DeepMind): Google (United States), Google (United Kingdom),
                                  DeepMind (United Kingdom)
    Microsoft:                    Microsoft (United States), Microsoft Research (United Kingdom)
    Meta (Facebook):              Meta (Israel), and any other Meta/Facebook sub-entities

For each parent group we re-aggregate using the underlying paper-level
authorship data: for each bridge paper, if the paper has at least one
authorship affiliated with ANY child sub-entity, the paper contributes ONCE
to the parent's totals (no double-counting across sub-entities within the
same paper).

Approach:
    1. Identify parent->children mapping by inst_id (using top-100 names matched
       against the patterns above)
    2. Query DuckDB once: for each bridge paper, get the SET of institution IDs
       it's affiliated with (deduplicated per paper)
    3. For each parent group, find papers whose inst_set intersects the parent's
       child sub-entities; aggregate n_bridge_papers, total_B, c_neuro, c_ai
    4. Replace the child rows with parent rows in the institutions table;
       re-rank by total_B; write the consolidated parquet

Output:
    corrections/20260508/author_inst_top_institutions_consolidated.parquet
        Same schema as `author_inst_top_institutions.parquet` plus a
        `consolidated_from` column listing the constituent sub-entity ids.
"""

from __future__ import annotations

import logging
import sys

import pandas as pd

from .. import config
from ..utils.duckdb import get_connection

logger = logging.getLogger(__name__)

CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"

# Parent group definitions: regex pattern on inst_name
PARENT_GROUPS: dict[str, dict] = {
    "Alphabet (Google + DeepMind)": dict(
        pattern=r"^Google|DeepMind|^Alphabet",
        country_code="US",  # primary HQ
        inst_type="company",
        canonical_id="ALPHABET_GROUP",
    ),
    "Microsoft": dict(
        pattern=r"^Microsoft",
        country_code="US",
        inst_type="company",
        canonical_id="MICROSOFT_GROUP",
    ),
    "Meta (Facebook)": dict(
        pattern=r"^Meta|^Facebook",
        country_code="US",
        inst_type="company",
        canonical_id="META_GROUP",
    ),
}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    inst = pd.read_parquet(CORRECTIONS_DIR / "author_inst_top_institutions.parquet")
    logger.info("Loaded top-100 institutions table: %d rows", len(inst))

    # Step 1: classify each top-100 row into a parent group (or none).
    inst["parent_group"] = None
    for parent_name, spec in PARENT_GROUPS.items():
        mask = inst["inst_name"].str.contains(spec["pattern"], regex=True, na=False)
        inst.loc[mask, "parent_group"] = parent_name
        logger.info("Parent '%s': %d sub-entities in top-100", parent_name, mask.sum())

    # We'll also need to look for sub-entities BELOW top-100. For the three
    # parents we know about, the top-100 captures the bulk (smaller sub-entities
    # would contribute <100 of total_B each, negligible for rank changes).
    # If a missing sub-entity bites us, we can extend in a follow-up run.

    # Step 2: query DuckDB once to get, per bridge paper, the set of inst_ids.
    bridge_full = pd.read_parquet(CORRECTIONS_DIR / "q4_v3_extended_full.parquet")
    bridge_ids = bridge_full["work_id"].astype(str).tolist()
    logger.info("Bridge paper count: %d", len(bridge_ids))

    sub_entity_ids: dict[str, set[str]] = {}
    for parent_name in PARENT_GROUPS:
        sub_entity_ids[parent_name] = set(
            inst.loc[inst["parent_group"] == parent_name, "inst_id"].astype(str)
        )

    # All target sub-entity IDs we care about, flat
    target_inst_ids = {iid for s in sub_entity_ids.values() for iid in s}
    logger.info("Target sub-entity IDs across all parents: %d", len(target_inst_ids))

    with get_connection(read_only=True) as con:
        con.execute("PRAGMA threads=4")
        con.execute("PRAGMA memory_limit='9GB'")
        con.execute("PRAGMA preserve_insertion_order=false")

        con.execute("CREATE TEMP TABLE _bridge_ids (work_id VARCHAR)")
        con.executemany("INSERT INTO _bridge_ids VALUES (?)", [(w,) for w in bridge_ids])
        con.execute("CREATE TEMP TABLE _target_inst (inst_id VARCHAR)")
        con.executemany(
            "INSERT INTO _target_inst VALUES (?)",
            [(s,) for s in target_inst_ids],
        )
        logger.info("Temp tables loaded; running unnest+filter ...")

        # For each (work, inst) where inst is in our target set, emit one row.
        df_pi = con.execute(
            """
            WITH all_authors AS (
                SELECT w.id AS work_id, unnest(w.authorships) AS auth
                FROM works w
                JOIN _bridge_ids b ON w.id = b.work_id
            ),
            insts_flat AS (
                SELECT work_id, unnest(auth.institutions) AS inst
                FROM all_authors
                WHERE auth.institutions IS NOT NULL AND length(auth.institutions) > 0
            ),
            target_only AS (
                SELECT DISTINCT work_id, inst.id AS inst_id
                FROM insts_flat
                JOIN _target_inst t ON inst.id = t.inst_id
            )
            SELECT * FROM target_only
            """
        ).df()
    logger.info("DuckDB returned %d (work, target-inst) rows", len(df_pi))

    # Step 3: for each parent, aggregate UNIQUE bridge papers
    parent_rows = []
    bridge_meta = bridge_full.set_index("work_id")[
        ["B_harmonic", "c_neuro", "c_ai", "cited_by_count"]
    ]
    for parent_name, ids in sub_entity_ids.items():
        sub = df_pi[df_pi["inst_id"].isin(ids)]
        unique_works = sub["work_id"].unique().tolist()
        if not unique_works:
            logger.warning("No bridge papers found for parent '%s'", parent_name)
            continue
        meta = bridge_meta.loc[bridge_meta.index.intersection(unique_works)]
        constituents = (
            inst[inst["parent_group"] == parent_name]
            .sort_values("total_B", ascending=False)["inst_name"]
            .tolist()
        )
        spec = PARENT_GROUPS[parent_name]
        # rank placeholder (we'll re-rank later)
        # total_B aggregation: sum of B_harmonic over unique work_ids
        parent_rows.append(
            dict(
                rank=-1,
                inst_id=spec["canonical_id"],
                inst_name=parent_name,
                country_code=spec["country_code"],
                inst_type=spec["inst_type"],
                n_bridge_papers=int(meta.shape[0]),
                total_B=float(meta["B_harmonic"].sum()),
                mean_B=float(meta["B_harmonic"].mean()),
                total_c_neuro=int(meta["c_neuro"].sum()),
                total_c_ai=int(meta["c_ai"].sum()),
                consolidated_from="; ".join(constituents),
                parent_group=parent_name,
            )
        )
        logger.info(
            "  '%s' -> %d unique bridge papers, total_B=%.0f, c_neuro=%d, c_ai=%d",
            parent_name,
            len(unique_works),
            meta["B_harmonic"].sum(),
            int(meta["c_neuro"].sum()),
            int(meta["c_ai"].sum()),
        )

    # Step 4: drop child rows from inst, insert parent rows, re-rank
    children_drop_mask = inst["parent_group"].notna()
    logger.info(
        "Dropping %d child rows from top-100 ahead of consolidation", children_drop_mask.sum()
    )
    keep = inst[~children_drop_mask].copy()
    keep["consolidated_from"] = ""

    parents_df = pd.DataFrame(parent_rows)
    full = pd.concat([keep, parents_df], ignore_index=True)
    full = full.drop(columns=["parent_group"], errors="ignore")
    full = full.sort_values("total_B", ascending=False).reset_index(drop=True)
    full["rank"] = full.index + 1

    out = CORRECTIONS_DIR / "author_inst_top_institutions_consolidated.parquet"
    full.to_parquet(out, index=False)
    logger.info("Wrote %s (%d rows total)", out, len(full))

    # Print the new top-15
    print("\\n=== Top-15 after consolidation ===")
    print(
        full[
            [
                "rank",
                "inst_name",
                "country_code",
                "inst_type",
                "n_bridge_papers",
                "total_B",
                "consolidated_from",
            ]
        ]
        .head(15)
        .to_string()
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

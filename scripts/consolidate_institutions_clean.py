"""Corporate-group consolidation on the field-filtered bridge set, done exhaustively.

Two defects in `audits/institution_consolidation.py` are fixed here.

1. It searched for corporate sub-entities only inside the top-100 institutions
   table, on the stated assumption that anything below would contribute under
   100 of total_B. That assumption is wrong by two orders of magnitude: Meta
   (United States), Google (Canada), Microsoft Research Asia and Google
   (Switzerland) all sit below rank 100 and each contributes thousands.
2. It aggregated corporate rows over the full 133,763-candidate pool while
   university rows came from a narrower ranking, so paper counts were not
   comparable across rows of the same table.

This script streams the work -> institution mapping once for the filtered set,
persists it so no later question needs the 493 GB works table again, then
consolidates by regex over EVERY institution rather than the top 100. Parent
totals deduplicate at paper level: a paper with authors at both Google and
DeepMind contributes once to Alphabet.
"""

from __future__ import annotations

import json
import logging
import re
import time

import pandas as pd

from neuroai_cn import config
from neuroai_cn.utils.duckdb import get_connection

logger = logging.getLogger(__name__)

SRC = config.CORRECTIONS_DIR / "20260508"
OUT = config.CORRECTIONS_DIR / "20260729"
PAIRS = OUT / "work_inst_pairs_v1.parquet"

MIN_PAPERS_INST = 5

PARENT_GROUPS = {
    "Alphabet (Google + DeepMind)": r"^Google|DeepMind|^Alphabet",
    "Microsoft": r"^Microsoft",
    "Meta (Facebook)": r"^Meta\b|^Facebook",
}


def build_pairs(work_ids: list[str]) -> pd.DataFrame:
    if PAIRS.exists():
        logger.info("Reusing cached pairs at %s", PAIRS)
        return pd.read_parquet(PAIRS)
    rows = []
    t0 = time.time()
    with get_connection(read_only=True) as con:
        con.execute("PRAGMA threads=4")
        con.execute("PRAGMA memory_limit='6GB'")
        con.execute("PRAGMA preserve_insertion_order=false")
        con.execute("CREATE TEMP TABLE _b (work_id VARCHAR)")
        con.executemany("INSERT INTO _b VALUES (?)", [(w,) for w in work_ids])
        res = con.execute("SELECT w.id, w.authorships FROM works w JOIN _b b ON w.id = b.work_id")
        total = 0
        while True:
            batch = res.fetchmany(200)
            if not batch:
                break
            for wid, authships in batch:
                if not authships:
                    continue
                for a in authships:
                    for inst in a.get("institutions") or []:
                        rows.append(
                            (
                                wid,
                                inst.get("id"),
                                inst.get("display_name"),
                                inst.get("country_code"),
                                inst.get("type"),
                            )
                        )
            total += len(batch)
            if total % 5000 == 0:
                logger.info("  streamed %d / %d (%.0fs)", total, len(work_ids), time.time() - t0)
    df = pd.DataFrame(
        rows, columns=["work_id", "inst_id", "inst_name", "country_code", "inst_type"]
    )
    df = df.dropna(subset=["inst_id"]).drop_duplicates(["work_id", "inst_id"])
    df.to_parquet(PAIRS, index=False)
    logger.info("Saved %d deduplicated (work, inst) pairs", len(df))
    return df


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    bridge = pd.read_parquet(SRC / "q4_v3_extended_full.parquet")
    bridge["work_id"] = bridge["work_id"].astype(str)
    v1 = bridge[bridge["bridge_paper_field"].isin(["neuro", "ai"])].copy()
    logger.info("Filtered bridge set: %d papers", len(v1))

    pairs = build_pairs(list(v1["work_id"]))
    pairs = pairs.merge(v1[["work_id", "B_harmonic", "c_neuro", "c_ai"]], on="work_id", how="inner")

    # Which institutions belong to which parent, searched over ALL institutions.
    name_by_id = pairs.drop_duplicates("inst_id").set_index("inst_id")["inst_name"].to_dict()
    membership: dict[str, str] = {}
    for parent, pattern in PARENT_GROUPS.items():
        rx = re.compile(pattern)
        kids = [i for i, n in name_by_id.items() if n and rx.search(str(n))]
        membership.update({k: parent for k in kids})
        logger.info(
            "%s: %d sub-entities found -> %s",
            parent,
            len(kids),
            sorted({name_by_id[k] for k in kids}),
        )

    pairs["group"] = pairs["inst_id"].map(membership).fillna(pairs["inst_id"])
    pairs["group_name"] = pairs["inst_id"].map(membership).fillna(pairs["inst_name"])

    consolidated = (
        pairs.drop_duplicates(["work_id", "group"])
        .groupby("group")
        .agg(
            inst_name=("group_name", lambda s: s.mode().iloc[0] if len(s.mode()) else None),
            country_code=("country_code", lambda s: s.mode().iloc[0] if len(s.mode()) else None),
            inst_type=("inst_type", lambda s: s.mode().iloc[0] if len(s.mode()) else None),
            n_bridge_papers=("work_id", "nunique"),
            total_B=("B_harmonic", "sum"),
            total_c_neuro=("c_neuro", "sum"),
            total_c_ai=("c_ai", "sum"),
        )
        .reset_index()
        .query(f"n_bridge_papers >= {MIN_PAPERS_INST}")
        .sort_values("total_B", ascending=False)
        .reset_index(drop=True)
    )
    consolidated["neuro_share"] = consolidated["total_c_neuro"] / (
        consolidated["total_c_neuro"] + consolidated["total_c_ai"]
    )
    consolidated.insert(0, "rank", range(1, len(consolidated) + 1))
    consolidated.to_parquet(OUT / "institutions_consolidated_v1.parquet", index=False)

    # Separated (unconsolidated) view for the transparency figure.
    separated = (
        pairs.drop_duplicates(["work_id", "inst_id"])
        .groupby("inst_id")
        .agg(
            inst_name=("inst_name", lambda s: s.mode().iloc[0] if len(s.mode()) else None),
            country_code=("country_code", lambda s: s.mode().iloc[0] if len(s.mode()) else None),
            inst_type=("inst_type", lambda s: s.mode().iloc[0] if len(s.mode()) else None),
            n_bridge_papers=("work_id", "nunique"),
            total_B=("B_harmonic", "sum"),
        )
        .reset_index()
        .query(f"n_bridge_papers >= {MIN_PAPERS_INST}")
        .sort_values("total_B", ascending=False)
        .reset_index(drop=True)
    )
    separated.insert(0, "rank", range(1, len(separated) + 1))
    separated.to_parquet(OUT / "institutions_separated_v1.parquet", index=False)

    report = {
        "generated": "2026-07-29",
        "n_papers": len(v1),
        "sub_entities": {
            p: sorted({name_by_id[k] for k, v in membership.items() if v == p})
            for p in PARENT_GROUPS
        },
        "top15_consolidated": consolidated.head(15)[
            ["rank", "inst_name", "inst_type", "n_bridge_papers", "total_B", "neuro_share"]
        ]
        .round(4)
        .to_dict("records"),
        "top15_separated": separated.head(15)[
            ["rank", "inst_name", "inst_type", "n_bridge_papers", "total_B"]
        ]
        .round(2)
        .to_dict("records"),
    }
    (OUT / "consolidation_report.json").write_text(json.dumps(report, indent=2, default=str))
    logger.info("DONE\n%s", json.dumps(report["top15_consolidated"], indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

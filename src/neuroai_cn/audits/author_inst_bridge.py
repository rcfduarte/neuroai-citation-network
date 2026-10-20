"""Author + institution-level bridge metrics.

For each top-N bridge paper from Q4 v3 extended, attribute its B(p) to every
author and every institution credited on the work. Aggregate by author and by
institution to produce:

    top_authors.parquet      — top-200 authors by total bridge contribution
    top_institutions.parquet — top-100 institutions by total bridge contribution
    top_countries.parquet    — top-50 countries by total bridge contribution

Bridge contribution: paper p contributes B(p) to every author / institution
that appears on it (no fractional weighting — a paper either bridges or
doesn't, and every author shares the credit). Also reports paper count per
author/institution to spot single-paper anomalies.

Source: q4_v3_extended_full.parquet (133k bridge candidates with c_neuro>=5
AND c_ai>=5). Joins back to works.authorships in the OpenAlex DuckDB index.

Uses two-step pattern: (1) materialise the works subset into a small temp
parquet so subsequent UNNEST does NOT trigger a full scan over all 398M works;
(2) UNNEST the small materialised subset.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import traceback

import pandas as pd

from .. import config
from ..utils.duckdb import get_connection, set_temp_directory

logger = logging.getLogger(__name__)

AUDITS_DIR = config.AUDITS_DIR / "20260508"
CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"
SENTINEL_DONE = AUDITS_DIR / "_author_inst_bridge.done"
SENTINEL_FAIL = AUDITS_DIR / "_author_inst_bridge.failed"

BRIDGE_FULL = CORRECTIONS_DIR / "q4_v3_extended_full.parquet"
TMP_DIR = config.TMP_DIR

TOP_BRIDGE_N = 5000


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    CORRECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    for s in (SENTINEL_DONE, SENTINEL_FAIL):
        if s.exists():
            s.unlink()
    t0 = time.time()
    try:
        if not BRIDGE_FULL.exists():
            raise FileNotFoundError(f"Q4 full table not found: {BRIDGE_FULL}")

        df = pd.read_parquet(BRIDGE_FULL)
        df = df.assign(B_harmonic=df["B_harmonic"].astype(float))
        n_full = len(df)
        # Apply E2 filter (per Block E5 spec): bridge paper must have a
        # neuro/ai field assignment (not 'other') AND c_total < 10000. This
        # excludes the LHD plasma-physics anomaly (Appendix B) and similar
        # high-citation domain works that aren't conceptual NeuroAI bridges.
        before = len(df)
        df = df[
            (df["bridge_paper_field"] != "other")
            & (df["bridge_paper_field"] != "unknown")
            & (df["c_total_classified"] < 10000)
        ].copy()
        logger.info(
            "After E2 filter (field != other/unknown AND c_total < 10000): %d / %d kept",
            len(df),
            before,
        )
        top = df.sort_values("B_harmonic", ascending=False).head(TOP_BRIDGE_N).copy()
        logger.info(
            "Restricting to top-%d of %d (filtered) / %d (raw) bridge candidates by B(p)",
            TOP_BRIDGE_N,
            len(df),
            n_full,
        )

        con = get_connection(read_only=True)
        try:
            con.execute("PRAGMA threads=4")
            con.execute("PRAGMA memory_limit='6GB'")
            set_temp_directory(con)
            con.execute("PRAGMA preserve_insertion_order=false")

            # STEP 1: filter works in batches (single 5000-id JOIN against a
            # 380M-row table without an id index does a full scan; batching
            # keeps each scan small AND reuses the same partition lookups).
            # We fetch in chunks of 500 to amortise the startup cost without
            # hitting the slow row-by-row pattern.
            logger.info("Step 1: fetch authorships in batches of 500 ...")
            t_step1 = time.time()
            id_to_meta = {
                row["work_id"]: (row["B_harmonic"], row["c_neuro"], row["c_ai"])
                for _, row in top.iterrows()
            }
            all_ids = list(id_to_meta.keys())
            batch_size = 500
            works_subset = []
            for i in range(0, len(all_ids), batch_size):
                batch = all_ids[i : i + batch_size]
                ids_quoted = "(" + ",".join("'" + s.replace("'", "''") + "'" for s in batch) + ")"
                rows = con.execute(
                    f"SELECT id, authorships FROM works WHERE id IN {ids_quoted}"
                ).fetchall()
                for wid, authships in rows:
                    b, cn, ca = id_to_meta.get(wid, (None, None, None))
                    works_subset.append((wid, b, cn, ca, authships))
                logger.info(
                    "  batch %d/%d done (cumulative %d, %.1fs)",
                    i // batch_size + 1,
                    (len(all_ids) + batch_size - 1) // batch_size,
                    len(works_subset),
                    time.time() - t_step1,
                )
            logger.info("Step 1 done: %d works, %.1fs", len(works_subset), time.time() - t_step1)

            # STEP 2: in Python, flatten authorships → (work, author, inst) rows.
            logger.info("Step 2: flatten authorships in Python ...")
            t_step2 = time.time()
            rows = []
            for work_id, b, cn, ca, authships in works_subset:
                if not authships:
                    continue
                for auth_struct in authships:
                    author = auth_struct.get("author", {}) or {}
                    auth_id = author.get("id")
                    auth_name = author.get("display_name")
                    insts = auth_struct.get("institutions") or []
                    if not insts:
                        rows.append(
                            {
                                "work_id": work_id,
                                "B_harmonic": b,
                                "c_neuro": cn,
                                "c_ai": ca,
                                "author_id": auth_id,
                                "author_name": auth_name,
                                "inst_id": None,
                                "inst_name": None,
                                "country_code": None,
                                "inst_type": None,
                            }
                        )
                        continue
                    for inst in insts:
                        rows.append(
                            {
                                "work_id": work_id,
                                "B_harmonic": b,
                                "c_neuro": cn,
                                "c_ai": ca,
                                "author_id": auth_id,
                                "author_name": auth_name,
                                "inst_id": inst.get("id"),
                                "inst_name": inst.get("display_name"),
                                "country_code": inst.get("country_code"),
                                "inst_type": inst.get("type"),
                            }
                        )
            wai_df = pd.DataFrame(rows)
            logger.info(
                "Step 2 done: %d (work,author,inst) rows, %.1fs", len(wai_df), time.time() - t_step2
            )

            # AUTHORS aggregate
            authors_df = (
                wai_df.dropna(subset=["author_id"])
                .drop_duplicates(subset=["work_id", "author_id"])
                .groupby("author_id")
                .agg(
                    author_name=(
                        "author_name",
                        lambda s: s.mode().iloc[0] if len(s.mode()) > 0 else None,
                    ),
                    n_bridge_papers=("work_id", "nunique"),
                    total_B=("B_harmonic", "sum"),
                    mean_B=("B_harmonic", "mean"),
                    max_B=("B_harmonic", "max"),
                    total_c_neuro=("c_neuro", "sum"),
                    total_c_ai=("c_ai", "sum"),
                )
                .reset_index()
                .query("n_bridge_papers >= 2")
                .sort_values("total_B", ascending=False)
                .head(200)
            )
            authors_df.insert(0, "rank", range(1, len(authors_df) + 1))
            authors_df.to_parquet(CORRECTIONS_DIR / "author_inst_top_authors.parquet", index=False)
            logger.info("Top authors: %d rows", len(authors_df))

            # INSTITUTIONS aggregate
            inst_df = (
                wai_df.dropna(subset=["inst_id"])
                .drop_duplicates(subset=["work_id", "inst_id"])
                .groupby("inst_id")
                .agg(
                    inst_name=(
                        "inst_name",
                        lambda s: s.mode().iloc[0] if len(s.mode()) > 0 else None,
                    ),
                    country_code=(
                        "country_code",
                        lambda s: s.mode().iloc[0] if len(s.mode()) > 0 else None,
                    ),
                    inst_type=(
                        "inst_type",
                        lambda s: s.mode().iloc[0] if len(s.mode()) > 0 else None,
                    ),
                    n_bridge_papers=("work_id", "nunique"),
                    total_B=("B_harmonic", "sum"),
                    mean_B=("B_harmonic", "mean"),
                    total_c_neuro=("c_neuro", "sum"),
                    total_c_ai=("c_ai", "sum"),
                )
                .reset_index()
                .query("n_bridge_papers >= 5")
                .sort_values("total_B", ascending=False)
                .head(100)
            )
            inst_df.insert(0, "rank", range(1, len(inst_df) + 1))
            inst_df.to_parquet(
                CORRECTIONS_DIR / "author_inst_top_institutions.parquet", index=False
            )
            logger.info("Top institutions: %d rows", len(inst_df))

            # COUNTRIES
            country_df = (
                wai_df.dropna(subset=["country_code"])
                .drop_duplicates(subset=["work_id", "country_code"])
                .groupby("country_code")
                .agg(
                    n_bridge_papers=("work_id", "nunique"),
                    total_B=("B_harmonic", "sum"),
                    mean_B=("B_harmonic", "mean"),
                    total_c_neuro=("c_neuro", "sum"),
                    total_c_ai=("c_ai", "sum"),
                )
                .reset_index()
                .sort_values("total_B", ascending=False)
                .head(50)
            )
            country_df.insert(0, "rank", range(1, len(country_df) + 1))
            country_df.to_parquet(
                CORRECTIONS_DIR / "author_inst_top_countries.parquet", index=False
            )
            logger.info("Top countries: %d rows", len(country_df))

            summary = {
                "source_table": str(BRIDGE_FULL),
                "n_bridge_total": len(df),
                "n_bridge_used": TOP_BRIDGE_N,
                "n_work_author_inst_rows": len(wai_df),
                "n_top_authors": len(authors_df),
                "n_top_institutions": len(inst_df),
                "n_top_countries": len(country_df),
                "elapsed_s": round(time.time() - t0, 1),
            }
            with (AUDITS_DIR / "author_inst_bridge_summary.json").open("w") as fh:
                json.dump(summary, fh, indent=2, default=str)
            logger.info("Summary: %s", summary)
        finally:
            con.close()
        SENTINEL_DONE.write_text(f"author_inst_bridge: DONE — elapsed {time.time() - t0:.1f}s\n")
        return 0
    except Exception as exc:
        tb = traceback.format_exc()
        SENTINEL_FAIL.write_text(
            f"author_inst_bridge: ERROR — {type(exc).__name__}: {exc}\n\n{tb}\n"
        )
        logger.exception("author_inst_bridge errored")
        return 2


if __name__ == "__main__":
    sys.exit(main())

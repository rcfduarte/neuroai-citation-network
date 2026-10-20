"""Q4 v3 — bridge papers under extended classifier; Block E candidate rankings.

Two variants per Block E spec:
    E1 — ubiquity-normalised harmonic mean: B_norm(p) = B(p) / log(c_total + 1)
    E2 — ubiquity-filtered: restrict to bridge_paper_field != 'other' AND c_total < 10000

Both ranked separately; per-era splits (bridge era 1990-2018, brand era 2019-2026).
Plus the utility-paper diagnostic table for {scikit-learn 2012, R citation,
LSTM 1997, Random Forests 2001, Sutton-Barto 1998, Adam 2014, SVM 1995,
Dropout 2014, ResNet 2016}.

Tier 1 surface check: Zador 2023, Richards 2019, Hassabis 2017,
Kriegeskorte-Douglas 2018 must appear in top-50 of BOTH variants
(per E5 locked validation).

Outputs (under data/derived/corrections/20260508/):
    q4_v3_extended_full.parquet               — every bridge paper (c_neuro >=5 AND c_ai >=5)
    q4_v3_extended_normalised.parquet         — top-200 by E1
    q4_v3_extended_filtered.parquet           — top-200 by E2
    q4_v3_extended_normalised_by_era.parquet  — top-25 per era
    q4_v3_extended_filtered_by_era.parquet    — top-25 per era
    q4_v3_extended_utility_diagnostic.parquet — utility-paper rank comparison

Sentinel: _q4v3.done in audits/20260508/.
"""

from __future__ import annotations

import json
import logging
import math
import sys
import time
import traceback
from pathlib import Path

import duckdb
import pandas as pd

from .. import config
from ..utils.duckdb import TIER1_DOIS, get_connection, set_temp_directory
from .extended_classifier import build_extended_field_assignment

logger = logging.getLogger(__name__)

AUDITS_DIR = config.AUDITS_DIR / "20260508"
CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"
SENTINEL_DONE = AUDITS_DIR / "_q4v3.done"
SENTINEL_FAIL = AUDITS_DIR / "_q4v3.failed"

YEAR_MIN = 1990
YEAR_MAX = 2026
MIN_SIDE_CITES = 5
TOP_N = 200

UTILITY_DIAGNOSTIC_DOIS = [
    ("scikit-learn 2011 JMLR", "10.5555/1953048.2078195"),
    ("scikit-learn 2013 arXiv", "10.48550/arxiv.1309.0238"),
    ("R Project (R Core Team 2014)", None),  # no canonical DOI
    ("LSTM 1997", "10.1162/neco.1997.9.8.1735"),
    ("Random Forests 2001", "10.1023/a:1010933404324"),
    ("Sutton-Barto 1998 RL Intro book", None),
    ("Adam 2014", "10.48550/arxiv.1412.6980"),
    ("SVM Cortes-Vapnik 1995", "10.1023/a:1022627411411"),
    ("Dropout 2014 JMLR", "10.5555/2627435.2670313"),
    ("ResNet 2016", "10.1109/cvpr.2016.90"),
]


def build_bridge_table(con: duckdb.DuckDBPyConnection) -> int:
    """Same as q4_bridge_papers.build() but uses extended classifier.

    Memory-friendly: split the aggregation into ai-side and neuro-side,
    each scanning only one slice of the work_field temp table. Then
    inner-join on cited_work_id with the >=5 each-side filter applied
    via JOIN.
    """
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE incoming_ai AS
        SELECT
            e.cited_work_id AS work_id,
            COUNT(*) AS c_ai
        FROM citation_edges e
        JOIN work_field src ON src.work_id = e.citing_work_id
        WHERE src.field = 'ai'
        GROUP BY e.cited_work_id
        HAVING COUNT(*) >= {MIN_SIDE_CITES}
        """
    )
    n_ai = int(con.execute("SELECT COUNT(*) FROM incoming_ai").fetchone()[0])
    logger.info("incoming_ai (>=5 ai cites): %d", n_ai)

    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE incoming_neuro AS
        SELECT
            e.cited_work_id AS work_id,
            COUNT(*) AS c_neuro
        FROM citation_edges e
        JOIN work_field src ON src.work_id = e.citing_work_id
        WHERE src.field = 'neuro'
        GROUP BY e.cited_work_id
        HAVING COUNT(*) >= {MIN_SIDE_CITES}
        """
    )
    n_neuro = int(con.execute("SELECT COUNT(*) FROM incoming_neuro").fetchone()[0])
    logger.info("incoming_neuro (>=5 neuro cites): %d", n_neuro)

    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE incoming AS
        SELECT
            n.work_id AS work_id,
            n.c_neuro AS c_neuro,
            a.c_ai AS c_ai,
            n.c_neuro + a.c_ai AS c_total_classified
        FROM incoming_neuro n
        JOIN incoming_ai a ON a.work_id = n.work_id
        """
    )
    return int(con.execute("SELECT COUNT(*) FROM incoming").fetchone()[0])


def materialize_full(con: duckdb.DuckDBPyConnection, out_path: Path) -> None:
    """Materialize full bridge table with metadata + harmonic-mean B + the
    extended-scheme bridge_paper_field of the cited work."""
    con.execute(
        f"""
        COPY (
            SELECT
                i.work_id,
                w.doi,
                w.title,
                w.publication_year,
                w.cited_by_count,
                COALESCE(wf.field, 'unknown') AS bridge_paper_field,
                i.c_neuro,
                i.c_ai,
                i.c_total_classified,
                CASE
                    WHEN (i.c_neuro + i.c_ai) > 0
                    THEN 2.0 * i.c_neuro * i.c_ai / (i.c_neuro + i.c_ai)
                    ELSE 0
                END AS B_harmonic
            FROM incoming i
            JOIN works w ON w.id = i.work_id
            LEFT JOIN work_field wf ON wf.work_id = i.work_id
            WHERE w.publication_year BETWEEN {YEAR_MIN} AND {YEAR_MAX}
        ) TO '{out_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )


def variant_normalised_top(df: pd.DataFrame, top_n: int = 200) -> pd.DataFrame:
    df = df.copy()
    df["B_norm_E1"] = df["B_harmonic"] / (df["c_total_classified"].apply(math.log1p))
    df = df.sort_values("B_norm_E1", ascending=False).head(top_n).reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))
    return df


def variant_filtered_top(df: pd.DataFrame, top_n: int = 200) -> pd.DataFrame:
    sub = df[(df["bridge_paper_field"] != "other") & (df["c_total_classified"] < 10000)].copy()
    sub = sub.sort_values("B_harmonic", ascending=False).head(top_n).reset_index(drop=True)
    sub.insert(0, "rank", range(1, len(sub) + 1))
    return sub


def by_era_split(top_df: pd.DataFrame, top_per_era: int = 25) -> pd.DataFrame:
    out = []
    for label, lo, hi in (("bridge_era", 1990, 2018), ("brand_era", 2019, 2026)):
        sub = top_df[(top_df["publication_year"] >= lo) & (top_df["publication_year"] <= hi)].copy()
        sub = sub.head(top_per_era).copy()
        sub["era"] = label
        sub["era_year_min"] = lo
        sub["era_year_max"] = hi
        out.append(sub)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def utility_diagnostic(
    con: duckdb.DuckDBPyConnection,
    df_full: pd.DataFrame,
    top_norm: pd.DataFrame,
    top_filt: pd.DataFrame,
) -> pd.DataFrame:
    """Look up each utility paper by DOI and report rank under raw / E1 / E2."""
    rows = []
    for name, doi in UTILITY_DIAGNOSTIC_DOIS:
        if doi is None:
            rows.append(
                {
                    "name": name,
                    "doi": None,
                    "found_in_full": False,
                    "rank_raw": None,
                    "rank_E1": None,
                    "rank_E2": None,
                    "B_harmonic": None,
                    "B_norm_E1": None,
                    "c_total": None,
                }
            )
            continue
        norm_doi = f"https://doi.org/{doi.lower()}"
        match = df_full[df_full["doi"].fillna("").str.lower() == norm_doi]
        if match.empty:
            rows.append(
                {
                    "name": name,
                    "doi": doi,
                    "found_in_full": False,
                    "rank_raw": None,
                    "rank_E1": None,
                    "rank_E2": None,
                    "B_harmonic": None,
                    "B_norm_E1": None,
                    "c_total": None,
                }
            )
            continue
        row = match.iloc[0]
        # rank under raw harmonic mean
        rank_raw = int((df_full["B_harmonic"] >= row["B_harmonic"]).sum())
        # rank under E1
        if "B_norm_E1" not in df_full.columns:
            df_full = df_full.assign(
                B_norm_E1=df_full["B_harmonic"] / df_full["c_total_classified"].apply(math.log1p)
            )
        my_norm = row["B_harmonic"] / math.log1p(row["c_total_classified"])
        rank_e1 = int((df_full["B_norm_E1"] >= my_norm).sum())
        # rank under E2
        e2_match = top_filt[top_filt["work_id"] == row["work_id"]]
        rank_e2 = int(e2_match["rank"].iloc[0]) if not e2_match.empty else None
        rows.append(
            {
                "name": name,
                "doi": doi,
                "found_in_full": True,
                "rank_raw": rank_raw,
                "rank_E1": rank_e1,
                "rank_E2": rank_e2,
                "B_harmonic": float(row["B_harmonic"]),
                "B_norm_E1": float(my_norm),
                "c_total": int(row["c_total_classified"]),
            }
        )
    return pd.DataFrame(rows)


def tier1_surface_check(top_df: pd.DataFrame, label: str) -> dict:
    """Check that all four Tier 1 DOIs are in top-50 of the given ranking."""
    tier1_lower = [d.lower() for d in TIER1_DOIS]
    sub = top_df[top_df["doi"].fillna("").str.lower().isin(tier1_lower)]
    return {
        "variant": label,
        "n_tier1_in_top50": int(
            ((sub["rank"] <= 50) if "rank" in sub.columns else pd.Series([False])).sum()
        )
        if not sub.empty
        else 0,
        "details": [
            {"doi": r["doi"], "title": r["title"], "rank": int(r["rank"]) if "rank" in r else None}
            for _, r in sub.iterrows()
        ],
    }


def spearman_rho(top_norm: pd.DataFrame, top_filt: pd.DataFrame) -> float:
    """Spearman rank correlation between the two top-200 lists (overlap only)."""
    common = pd.merge(
        top_norm[["work_id", "rank"]].rename(columns={"rank": "rank_norm"}),
        top_filt[["work_id", "rank"]].rename(columns={"rank": "rank_filt"}),
        on="work_id",
    )
    if len(common) < 5:
        return float("nan")
    return float(common[["rank_norm", "rank_filt"]].corr(method="spearman").iloc[0, 1])


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    CORRECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    for s in (SENTINEL_DONE, SENTINEL_FAIL):
        if s.exists():
            s.unlink()
    t0 = time.time()
    try:
        con = get_connection(read_only=True)
        try:
            con.execute("PRAGMA threads=6")
            con.execute("PRAGMA memory_limit='20GB'")
            set_temp_directory(con)
            con.execute("PRAGMA preserve_insertion_order=false")

            logger.info("Building extended field assignment...")
            pop = build_extended_field_assignment(con, year_min=YEAR_MIN, year_max=YEAR_MAX)
            logger.info("pop: %s", pop)

            logger.info("Building bridge table...")
            n_bridge = build_bridge_table(con)
            logger.info("Bridge candidates: %d", n_bridge)

            full_path = CORRECTIONS_DIR / "q4_v3_extended_full.parquet"
            materialize_full(con, full_path)
            logger.info("Wrote full bridge table to %s", full_path)

            df_full = pd.read_parquet(full_path)

            top_norm = variant_normalised_top(df_full, top_n=TOP_N)
            top_filt = variant_filtered_top(df_full, top_n=TOP_N)

            top_norm.to_parquet(CORRECTIONS_DIR / "q4_v3_extended_normalised.parquet", index=False)
            top_filt.to_parquet(CORRECTIONS_DIR / "q4_v3_extended_filtered.parquet", index=False)

            era_norm = by_era_split(top_norm, top_per_era=25)
            era_filt = by_era_split(top_filt, top_per_era=25)
            era_norm.to_parquet(
                CORRECTIONS_DIR / "q4_v3_extended_normalised_by_era.parquet", index=False
            )
            era_filt.to_parquet(
                CORRECTIONS_DIR / "q4_v3_extended_filtered_by_era.parquet", index=False
            )

            ud = utility_diagnostic(con, df_full, top_norm, top_filt)
            ud.to_parquet(
                CORRECTIONS_DIR / "q4_v3_extended_utility_diagnostic.parquet", index=False
            )

            t1 = tier1_surface_check(top_norm, "E1_normalised")
            t2 = tier1_surface_check(top_filt, "E2_filtered")
            rho = spearman_rho(top_norm, top_filt)

            summary = {
                "scheme": "extended (subfield 1702 minus BAD + 1707 + T10502)",
                "n_bridge_candidates": n_bridge,
                "tier1_surface_check": [t1, t2],
                "spearman_rho_E1_vs_E2": rho,
                "n_top_norm": len(top_norm),
                "n_top_filt": len(top_filt),
                "elapsed_s": round(time.time() - t0, 1),
            }
            with (AUDITS_DIR / "q4_v3_summary.json").open("w") as fh:
                json.dump(summary, fh, indent=2, default=str)
            logger.info("Summary: %s", summary)
        finally:
            con.close()
        SENTINEL_DONE.write_text(
            f"q4_v3: DONE — {n_bridge} candidates; rho={rho:.3f}; elapsed {time.time() - t0:.1f}s\n"
        )
        return 0
    except Exception as exc:
        tb = traceback.format_exc()
        SENTINEL_FAIL.write_text(f"q4_v3: ERROR — {type(exc).__name__}: {exc}\n\n{tb}\n")
        logger.exception("Q4 v3 errored")
        return 2


if __name__ == "__main__":
    sys.exit(main())

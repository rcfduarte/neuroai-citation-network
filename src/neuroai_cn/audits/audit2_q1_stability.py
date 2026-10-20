"""Block B — Audit 2: Q1 stability across five variants.

Diagnostic only — tests whether the headline asymmetry (AI->neuro rising,
neuro->AI flat) and the 2024 endpoint behaviour are robust under:
    B1 — population-OR as primary (vs restricted-universe)
    B2 — rolling means (3y, 5y centred)
    B3 — coverage-conditional OR (restrict to high-coverage years)
    B4 — citation-cone restriction on cited side (Delta in {0,1,2,3} years)
    B5 — OLS slope test on multiple windows

Outputs:
    corrections/20260508/q1_population_or.parquet
    corrections/20260508/q1_rolling.parquet
    corrections/20260508/q1_coverage_by_year.parquet
    corrections/20260508/q1_coverage_conditional.parquet
    corrections/20260508/q1_citation_cone.parquet
    audits/20260508/audit2_PLOTS.png
    audits/20260508/audit2_REPORT.md

Sentinel: _audit2.done on success.

Notes on locked methodology:
- E2 OR formula is unchanged. We only reuse the existing OR_restricted +
  OR_population columns from q1_or_by_year.parquet (B1, B2, B5).
- For B3 and B4 we rebuild the temp table work_field with the same
  curated AI core scheme that q1 production uses — see q1_cross_citation
  for the canonical implementation.
- The Block A finding (curated AI core misses subfield 1707/2208) propagates
  through this audit. B1-B5 test the stability of the trend UNDER the
  current classifier; they don't fix the classifier.
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
from scipy.stats import t as t_dist

from .. import config
from ..analysis.q1_cross_citation import _ai_core_sql_array
from ..utils.duckdb import NEURO_FIELD_ID, get_connection, set_temp_directory

logger = logging.getLogger(__name__)

AUDITS_DIR = config.AUDITS_DIR / "20260508"
CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"
SENTINEL_DONE = AUDITS_DIR / "_audit2.done"
SENTINEL_FAIL = AUDITS_DIR / "_audit2.failed"

YEAR_MIN = 1990
YEAR_MAX = 2025
COVERAGE_FLOOR = 0.7
DELTAS = (0, 1, 2, 3)


def _odds_ratio(rho: float, rho_null: float) -> float:
    if rho_null <= 0 or rho_null >= 1:
        return float("nan")
    if rho <= 0:
        return 0.0
    if rho >= 1:
        return float("inf")
    return (rho / (1 - rho)) / (rho_null / (1 - rho_null))


def variant_b1_population_or(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """B1 — population-OR as primary curve. Just project the existing parquet."""
    src = str(config.DERIVED_DIR / "q1_or_by_year.parquet")
    df = con.execute(
        f"""
        SELECT
            year,
            direction,
            OR_population AS or_population,
            or_population_lo,
            or_population_hi,
            OR_restricted AS or_restricted,
            or_restricted_lo,
            or_restricted_hi,
            n_to_target,
            n_to_within,
            n_works_source,
            n_works_target
        FROM read_parquet('{src}')
        ORDER BY direction, year
        """
    ).df()
    return df


def variant_b2_rolling(df_b1: pd.DataFrame) -> pd.DataFrame:
    """B2 — 3y and 5y centred rolling means."""
    out = []
    for direction in ("ai_to_neuro", "neuro_to_ai"):
        sub = df_b1[df_b1["direction"] == direction].sort_values("year").copy()
        sub["or_population_3y"] = sub["or_population"].rolling(window=3, center=True).mean()
        sub["or_population_5y"] = sub["or_population"].rolling(window=5, center=True).mean()
        sub["or_restricted_3y"] = sub["or_restricted"].rolling(window=3, center=True).mean()
        sub["or_restricted_5y"] = sub["or_restricted"].rolling(window=5, center=True).mean()
        out.append(sub)
    return pd.concat(out, ignore_index=True)


def variant_b3_coverage_by_year(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """B3 — Coverage-conditional. Compute per (year, label) coverage =
    works_with_primary_topic / works_total restricted to that label.

    Note: 'label' here means 'works that WOULD be neuro-classified if they had
    a primary_topic' is impossible to compute — we don't know what they would
    be. Instead we compute coverage at two levels:
    (a) overall_coverage_year = pct of all works in year y with primary_topic
    (b) per assigned label, coverage of secondary topics presence (proxy for
        OpenAlex topic-classification quality)
    """
    rows = con.execute(
        f"""
        SELECT
            publication_year AS year,
            COUNT(*) AS n_total,
            SUM(CASE WHEN primary_topic IS NOT NULL THEN 1 ELSE 0 END) AS n_with_primary_topic,
            SUM(CASE WHEN primary_topic.field.id = '{NEURO_FIELD_ID}' THEN 1 ELSE 0 END) AS n_neuro
        FROM works
        WHERE publication_year BETWEEN {YEAR_MIN} AND {YEAR_MAX}
        GROUP BY publication_year
        ORDER BY publication_year
        """
    ).fetchall()
    df = pd.DataFrame(rows, columns=["year", "n_total", "n_with_primary_topic", "n_neuro"])
    df["coverage_overall"] = df["n_with_primary_topic"] / df["n_total"]
    df["neuro_density_when_classified"] = df["n_neuro"] / df["n_with_primary_topic"]
    return df


def variant_b3_coverage_conditional(df_b1: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    """B3 — restrict OR series to year-pairs where source-year coverage ≥ floor.

    Since OR is computed PER YEAR, the relevant filter is just per-year coverage
    on the source side.
    """
    cov = coverage.set_index("year")["coverage_overall"].to_dict()
    out = df_b1.copy()
    out["coverage_year"] = out["year"].map(cov)
    out["passes_coverage_floor"] = out["coverage_year"] >= COVERAGE_FLOOR
    out["or_population_filtered"] = out["or_population"].where(out["passes_coverage_floor"])
    out["or_restricted_filtered"] = out["or_restricted"].where(out["passes_coverage_floor"])
    return out


def variant_b4_citation_cone(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """B4 — for each Delta in {0,1,2,3}, restrict cited works to
    publication_year <= citing_year - Delta. Compute OR_restricted +
    OR_population per (year, direction, delta).

    This is the most compute-intensive variant. We do it in one DuckDB query
    that produces all four deltas in a single grouped aggregation, then
    derive ORs in pandas.

    The within-pool denominator (n_to_within) uses the SAME cited-year filter
    so that the citation-cone restriction is consistent across numerator and
    denominator.
    """
    ai_arr = _ai_core_sql_array()
    # First: build work_field temp table (same as q1)
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
    n = con.execute("SELECT COUNT(*) FROM work_field").fetchone()[0]
    logger.info("B4: built work_field with %d rows", n)

    # Aggregate edges with cited_year via JOIN on cited side.
    # We compute ALL deltas in a single query using conditional sums.
    sql_parts = []
    for d in DELTAS:
        for endpoint in ("within", "target", "missing", "other"):
            cond_year = f"(tgt.year IS NOT NULL AND tgt.year <= e.citing_year - {d})"
            cond_year_missing = f"(tgt.year IS NULL OR tgt.year > e.citing_year - {d})"
            if endpoint == "within":
                cond = f"src.field = tgt.field AND {cond_year}"
            elif endpoint == "target":
                cond = (
                    f"src.field IN ('neuro','ai') AND tgt.field IN ('neuro','ai') "
                    f"AND src.field != tgt.field AND {cond_year}"
                )
            elif endpoint == "missing":
                cond = cond_year_missing
            else:  # other
                cond = f"tgt.field = 'other' AND {cond_year}"
            sql_parts.append(f"SUM(CASE WHEN {cond} THEN 1 ELSE 0 END) AS d{d}_to_{endpoint}")
    sums_sql = ",\n        ".join(sql_parts)

    edge_sql = f"""
        SELECT
            e.citing_year AS year,
            src.field AS src_field,
            {sums_sql}
        FROM citation_edges e
        JOIN work_field src ON src.work_id = e.citing_work_id
        LEFT JOIN work_field tgt ON tgt.work_id = e.cited_work_id
        WHERE e.citing_year BETWEEN {YEAR_MIN} AND {YEAR_MAX}
          AND src.field IN ('neuro','ai')
        GROUP BY e.citing_year, src.field
        ORDER BY e.citing_year, src.field
    """
    logger.info("B4: running citation-cone aggregation across deltas %s ...", DELTAS)
    t0 = time.time()
    df = con.execute(edge_sql).df()
    logger.info("B4: aggregation done in %.1fs", time.time() - t0)

    # Per-year per-label population for null model.
    pop = con.execute(
        f"""
        SELECT
            year,
            SUM(CASE WHEN field='neuro' THEN 1 ELSE 0 END) AS n_neuro,
            SUM(CASE WHEN field='ai' THEN 1 ELSE 0 END) AS n_ai,
            SUM(CASE WHEN field='other' THEN 1 ELSE 0 END) AS n_other,
            COUNT(*) AS n_total
        FROM work_field
        WHERE year BETWEEN {YEAR_MIN} AND {YEAR_MAX}
        GROUP BY year
        """
    ).df()

    # Reshape: for each (year, source_field, delta), compute OR_restricted +
    # OR_population.
    long_rows = []
    for _, row in df.iterrows():
        year = int(row["year"])
        src = row["src_field"]
        target_field = "ai" if src == "neuro" else "neuro"
        for d in DELTAS:
            n_within = int(row[f"d{d}_to_within"])
            n_target = int(row[f"d{d}_to_target"])
            n_other = int(row[f"d{d}_to_other"])
            n_missing = int(row[f"d{d}_to_missing"])
            # rho_restricted: within-{neuro,ai} universe
            denom_r = n_within + n_target
            rho_r = n_target / denom_r if denom_r > 0 else float("nan")
            # rho_population: include 'other' in chance pool
            denom_p = n_within + n_target + n_other
            rho_p = n_target / denom_p if denom_p > 0 else float("nan")
            # Null
            pop_year = pop[pop["year"] == year]
            if pop_year.empty:
                continue
            pyr = pop_year.iloc[0]
            n_target_pop = int(pyr[f"n_{target_field}"])
            n_src_pop = int(pyr[f"n_{src}"])
            n_other_pop = int(pyr["n_other"])
            denom_null_r = n_src_pop + n_target_pop
            rho_null_r = n_target_pop / denom_null_r if denom_null_r > 0 else float("nan")
            denom_null_p = n_src_pop + n_target_pop + n_other_pop
            rho_null_p = n_target_pop / denom_null_p if denom_null_p > 0 else float("nan")
            or_r = (
                _odds_ratio(rho_r, rho_null_r)
                if not (math.isnan(rho_r) or math.isnan(rho_null_r))
                else float("nan")
            )
            or_p = (
                _odds_ratio(rho_p, rho_null_p)
                if not (math.isnan(rho_p) or math.isnan(rho_null_p))
                else float("nan")
            )
            long_rows.append(
                {
                    "year": year,
                    "direction": f"{src}_to_{target_field}",
                    "delta_years": d,
                    "n_to_within": n_within,
                    "n_to_target": n_target,
                    "n_to_other": n_other,
                    "n_to_missing": n_missing,
                    "or_restricted": or_r,
                    "or_population": or_p,
                }
            )
    return pd.DataFrame(long_rows)


def variant_b5_ols_slopes(df_b1: pd.DataFrame) -> pd.DataFrame:
    """B5 — OLS slope test on multiple windows. Returns one row per
    (direction, metric, window)."""
    windows = [
        ("2010-2025", 2010, 2025),
        ("2012-2025", 2012, 2025),
        ("2015-2025", 2015, 2025),
        ("2018-2025", 2018, 2025),
        ("2010-2023", 2010, 2023),
    ]
    out = []
    for direction in ("ai_to_neuro", "neuro_to_ai"):
        sub_full = df_b1[df_b1["direction"] == direction]
        for metric in ("or_restricted", "or_population"):
            for label, lo, hi in windows:
                sub = sub_full[(sub_full["year"] >= lo) & (sub_full["year"] <= hi)]
                if sub.empty or sub[metric].isna().all():
                    out.append(
                        {
                            "direction": direction,
                            "metric": metric,
                            "window": label,
                            "n_years": 0,
                            "slope": float("nan"),
                            "intercept": float("nan"),
                            "r2": float("nan"),
                            "se": float("nan"),
                            "t_stat": float("nan"),
                            "p_value_two_tail": float("nan"),
                        }
                    )
                    continue
                x = sub["year"].to_numpy(dtype=float)
                y = sub[metric].to_numpy(dtype=float)
                # Drop NaNs
                mask = ~pd.isna(y)
                x = x[mask]
                y = y[mask]
                if len(x) < 3:
                    continue
                slope, intercept = pd_linregress(x, y)
                yhat = slope * x + intercept
                ss_res = float(((y - yhat) ** 2).sum())
                ss_tot = float(((y - y.mean()) ** 2).sum())
                r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
                # Simple OLS std error
                n = len(x)
                if n > 2:
                    s_err = math.sqrt(ss_res / (n - 2))
                    sxx = float(((x - x.mean()) ** 2).sum())
                    se_slope = s_err / math.sqrt(sxx) if sxx > 0 else float("nan")
                    t_stat = slope / se_slope if se_slope > 0 else float("nan")
                    # Two-tail t-test approximation
                    p_val = (
                        _t_test_two_tail(t_stat, n - 2) if not math.isnan(t_stat) else float("nan")
                    )
                else:
                    se_slope = float("nan")
                    t_stat = float("nan")
                    p_val = float("nan")
                out.append(
                    {
                        "direction": direction,
                        "metric": metric,
                        "window": label,
                        "n_years": int(n),
                        "slope": slope,
                        "intercept": intercept,
                        "r2": r2,
                        "se": se_slope,
                        "t_stat": t_stat,
                        "p_value_two_tail": p_val,
                    }
                )
    return pd.DataFrame(out)


def pd_linregress(x, y):
    """Simple linear regression using numpy primitives."""

    x_mean = x.mean()
    y_mean = y.mean()
    sxy = float(((x - x_mean) * (y - y_mean)).sum())
    sxx = float(((x - x_mean) ** 2).sum())
    if sxx == 0:
        return float("nan"), float("nan")
    slope = sxy / sxx
    intercept = y_mean - slope * x_mean
    return slope, intercept


def _t_test_two_tail(t: float, df: int) -> float:
    """Two-tailed t-test p-value from the t distribution (scipy is a hard dependency)."""
    return 2.0 * (1.0 - float(t_dist.cdf(abs(t), df=df)))


def make_plots(
    df_b1: pd.DataFrame,
    df_rolling: pd.DataFrame,
    df_cov_year: pd.DataFrame,
    df_cov_cond: pd.DataFrame,
    df_cone: pd.DataFrame,
    df_ols: pd.DataFrame,
    out_path: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 2, figsize=(14, 12))

    def _plot_or_lines(ax, df, value_col, label_prefix, ylabel):
        for direction, color in (("ai_to_neuro", "C0"), ("neuro_to_ai", "C3")):
            sub = df[df["direction"] == direction].sort_values("year")
            ax.plot(
                sub["year"], sub[value_col], "o-", color=color, label=f"{label_prefix} {direction}"
            )
        ax.axhline(1.0, color="grey", linestyle="--", linewidth=0.7)
        ax.set_ylabel(ylabel)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

    # Panel 1: Raw + B1 (population OR)
    ax = axes[0, 0]
    _plot_or_lines(ax, df_b1, "or_restricted", "OR_restricted", "Odds Ratio")
    _plot_or_lines(ax, df_b1, "or_population", "OR_population", "Odds Ratio")
    ax.set_title("B1: Raw OR_restricted (solid) + OR_population (overlay)")
    ax.set_xlabel("Year")
    ax.set_yscale("log")

    # Panel 2: B2 rolling
    ax = axes[0, 1]
    for direction, color in (("ai_to_neuro", "C0"), ("neuro_to_ai", "C3")):
        sub = df_rolling[df_rolling["direction"] == direction].sort_values("year")
        ax.plot(sub["year"], sub["or_population"], color=color, alpha=0.3, label=f"raw {direction}")
        ax.plot(
            sub["year"],
            sub["or_population_3y"],
            color=color,
            linestyle="--",
            label=f"3y rolling {direction}",
        )
        ax.plot(
            sub["year"],
            sub["or_population_5y"],
            color=color,
            linewidth=2,
            label=f"5y rolling {direction}",
        )
    ax.axhline(1.0, color="grey", linestyle="--", linewidth=0.7)
    ax.set_title("B2: OR_population rolling means")
    ax.set_xlabel("Year")
    ax.set_ylabel("OR_population")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    # Panel 3: B3 coverage by year
    ax = axes[1, 0]
    ax.plot(df_cov_year["year"], df_cov_year["coverage_overall"], "o-", color="C2")
    ax.axhline(
        COVERAGE_FLOOR, color="grey", linestyle="--", linewidth=0.7, label=f"floor {COVERAGE_FLOOR}"
    )
    ax.set_title("B3: Per-year overall coverage (works with primary_topic)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Coverage fraction")
    ax.legend()
    ax.grid(alpha=0.3)

    # Panel 4: B3 coverage-filtered OR
    ax = axes[1, 1]
    for direction, color in (("ai_to_neuro", "C0"), ("neuro_to_ai", "C3")):
        sub = df_cov_cond[df_cov_cond["direction"] == direction].sort_values("year")
        ax.plot(
            sub["year"],
            sub["or_population"],
            color=color,
            alpha=0.3,
            label=f"unfiltered {direction}",
        )
        ax.plot(
            sub["year"],
            sub["or_population_filtered"],
            color=color,
            linewidth=2,
            label=f"filtered {direction}",
        )
    ax.axhline(1.0, color="grey", linestyle="--", linewidth=0.7)
    ax.set_title("B3: OR_population coverage-filtered")
    ax.set_xlabel("Year")
    ax.set_ylabel("OR_population")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    # Panel 5: B4 citation cone
    ax = axes[2, 0]
    direction = "ai_to_neuro"
    for d, ls in zip(DELTAS, ["-", "--", "-.", ":"], strict=False):
        sub = df_cone[
            (df_cone["direction"] == direction) & (df_cone["delta_years"] == d)
        ].sort_values("year")
        if not sub.empty:
            ax.plot(sub["year"], sub["or_population"], ls, label=f"Delta = {d}y")
    ax.axhline(1.0, color="grey", linestyle="--", linewidth=0.7)
    ax.set_title(f"B4: citation-cone {direction} OR_population by Delta")
    ax.set_xlabel("Year")
    ax.set_ylabel("OR_population")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    # Panel 6: B5 OLS slopes (table-as-text in axes)
    ax = axes[2, 1]
    ax.axis("off")
    text = "B5: OLS slopes (or_population)\n\n"
    sub = df_ols[df_ols["metric"] == "or_population"]
    text += f"{'window':>10s} {'direction':<13s} {'slope':>9s} {'p':>8s} {'r2':>5s}\n"
    for _, row in sub.iterrows():
        text += (
            f"{row['window']:>10s} {row['direction']:<13s} "
            f"{row['slope']:>9.5f} {row['p_value_two_tail']:>8.4f} {row['r2']:>5.2f}\n"
        )
    ax.text(0.0, 1.0, text, family="monospace", verticalalignment="top", fontsize=9)

    fig.suptitle("Audit 2 — Q1 stability across variants B1-B5", fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    logger.info("Wrote plots to %s", out_path)


def write_report(
    df_b1: pd.DataFrame,
    df_rolling: pd.DataFrame,
    df_cov_year: pd.DataFrame,
    df_cov_cond: pd.DataFrame,
    df_cone: pd.DataFrame,
    df_ols: pd.DataFrame,
    out_path: Path,
) -> None:
    lines = []
    lines.append("# Audit 2 — Q1 stability report (Block B)\n")
    lines.append("**Date:** 2026-05-08 (overnight run)")
    lines.append("")
    lines.append("Diagnostic only — five variants exercised. Decision deferred to user.")
    lines.append("")
    lines.append("## B1 — Population-OR endpoints (2020-2025)")
    sub_2020 = df_b1[df_b1["year"] >= 2020].sort_values(["direction", "year"])
    lines.append("")
    lines.append("```")
    lines.append(
        sub_2020[["year", "direction", "or_restricted", "or_population"]].to_string(index=False)
    )
    lines.append("```")
    lines.append("")
    lines.append("## B5 — OLS slopes (or_population)")
    sub_b5 = df_ols[df_ols["metric"] == "or_population"]
    lines.append("")
    lines.append("```")
    lines.append(
        sub_b5[
            ["direction", "window", "n_years", "slope", "se", "t_stat", "p_value_two_tail", "r2"]
        ].to_string(index=False)
    )
    lines.append("```")
    lines.append("")
    lines.append("## B5 — OLS slopes (or_restricted)")
    sub_b5r = df_ols[df_ols["metric"] == "or_restricted"]
    lines.append("")
    lines.append("```")
    lines.append(
        sub_b5r[
            ["direction", "window", "n_years", "slope", "se", "t_stat", "p_value_two_tail", "r2"]
        ].to_string(index=False)
    )
    lines.append("```")
    lines.append("")
    lines.append("## B4 — Citation-cone Delta sweep (2024 + 2025 endpoints)")
    sub_cone_2024 = df_cone[(df_cone["year"] == 2024) | (df_cone["year"] == 2025)].sort_values(
        ["year", "direction", "delta_years"]
    )
    lines.append("")
    lines.append("```")
    lines.append(
        sub_cone_2024[
            [
                "year",
                "direction",
                "delta_years",
                "or_restricted",
                "or_population",
                "n_to_within",
                "n_to_target",
            ]
        ].to_string(index=False)
    )
    lines.append("```")
    lines.append("")
    lines.append("## B3 — Coverage by year (high-water mark + dips)")
    cov = df_cov_year.copy()
    lines.append("")
    lines.append("```")
    lines.append(
        cov[["year", "coverage_overall", "neuro_density_when_classified"]]
        .tail(20)
        .to_string(index=False)
    )
    lines.append("```")
    lines.append("")
    lines.append("## Interpretation hooks (for user decision in the morning)")
    lines.append("")
    lines.append(
        "- **Recommended primary curve.** Compare B1 (population-OR) to OR_restricted; under the user's framing, population-OR includes the 'other' pool in the chance baseline and is the principled headline. The right panel of figure1_v5.png is already the population-OR."
    )
    lines.append(
        "- **Recommended OLS window.** Compare 2010-2023 (de-risked, drops 2024-2025 endpoint) vs 2012-2025 (current). If the slope is robust across both, the headline 'AI-to-neuro rising' claim survives the 2024 endpoint anomaly. If 2010-2023 attenuates the slope, the claim leans on 2024-2025 — flag in the methods note."
    )
    lines.append(
        "- **2024 endpoint diagnosis.** If B4 shows OR_population at year 2024 attenuating as Delta grows from 0 to 3, the 2024 jump is partially driven by recent cited-side topic-label backfill. If OR persists across Delta values, the trend is real."
    )
    lines.append(
        "- **Coverage-conditional caveat.** B3 will show whether the 2025 endpoint (much higher coverage in 2024-2025 due to the OpenAlex 2025-11-06 re-export) is the source of the OR jump. If the coverage-filtered series shows the same trend, the jump survives the artifact concern."
    )
    out_path.write_text("\n".join(lines), encoding="utf-8")


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
            con.execute("PRAGMA threads=10")
            con.execute("PRAGMA memory_limit='24GB'")
            set_temp_directory(con)

            logger.info("B1: extracting population-OR from existing parquet...")
            df_b1 = variant_b1_population_or(con)
            df_b1.to_parquet(CORRECTIONS_DIR / "q1_population_or.parquet", index=False)
            logger.info("B1 done: %d rows", len(df_b1))

            logger.info("B2: rolling means...")
            df_rolling = variant_b2_rolling(df_b1)
            df_rolling.to_parquet(CORRECTIONS_DIR / "q1_rolling.parquet", index=False)
            logger.info("B2 done")

            logger.info("B3: per-year coverage...")
            df_cov_year = variant_b3_coverage_by_year(con)
            df_cov_year.to_parquet(CORRECTIONS_DIR / "q1_coverage_by_year.parquet", index=False)
            logger.info("B3 coverage done: %d rows", len(df_cov_year))

            logger.info("B3: coverage-conditional OR...")
            df_cov_cond = variant_b3_coverage_conditional(df_b1, df_cov_year)
            df_cov_cond.to_parquet(CORRECTIONS_DIR / "q1_coverage_conditional.parquet", index=False)
            logger.info("B3 conditional done")

            logger.info("B4: citation-cone restriction (Delta sweep)...")
            df_cone = variant_b4_citation_cone(con)
            df_cone.to_parquet(CORRECTIONS_DIR / "q1_citation_cone.parquet", index=False)
            logger.info("B4 done: %d rows", len(df_cone))

            logger.info("B5: OLS slopes...")
            df_ols = variant_b5_ols_slopes(df_b1)
            df_ols.to_parquet(CORRECTIONS_DIR / "q1_ols_slopes.parquet", index=False)
            logger.info("B5 done: %d rows", len(df_ols))

            logger.info("Generating plots...")
            try:
                make_plots(
                    df_b1,
                    df_rolling,
                    df_cov_year,
                    df_cov_cond,
                    df_cone,
                    df_ols,
                    AUDITS_DIR / "audit2_PLOTS.png",
                )
            except Exception as e:
                logger.warning("Plot generation failed: %s", e)

            logger.info("Writing report...")
            write_report(
                df_b1,
                df_rolling,
                df_cov_year,
                df_cov_cond,
                df_cone,
                df_ols,
                AUDITS_DIR / "audit2_REPORT.md",
            )
        finally:
            con.close()

        elapsed = time.time() - t0
        SENTINEL_DONE.write_text(
            f"audit2: DONE — B1-B5 variants written to corrections/20260508/; "
            f"see audit2_REPORT.md + audit2_PLOTS.png; elapsed {elapsed:.1f}s\n"
        )
        # Also save a summary JSON
        with (AUDITS_DIR / "audit2_summary.json").open("w") as fh:
            json.dump(
                {
                    "elapsed_s": elapsed,
                    "n_b1_rows": len(df_b1),
                    "n_cone_rows": len(df_cone),
                    "n_ols_rows": len(df_ols),
                    "deltas": list(DELTAS),
                    "coverage_floor": COVERAGE_FLOOR,
                    "year_range": [YEAR_MIN, YEAR_MAX],
                },
                fh,
                indent=2,
            )
        logger.info("Audit 2 DONE in %.1fs", elapsed)
        return 0
    except Exception as exc:
        tb = traceback.format_exc()
        SENTINEL_FAIL.write_text(f"audit2: ERROR — {type(exc).__name__}: {exc}\n\n{tb}\n")
        logger.exception("Audit 2 errored")
        return 2


if __name__ == "__main__":
    sys.exit(main())

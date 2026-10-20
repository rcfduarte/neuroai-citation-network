"""Export the sensitivity analyses of the citation-flow odds ratio to committed CSV files.

Supplement S2 (citation flow) and the methods notes rest on three robustness checks whose inputs live only in the heavy
derived data: the strict-AI counterfactual (the whole odds-ratio table recomputed with the curated
35-topic AI core instead of the extended AI definition), the leave-one-topic-out sweep (the odds
ratio recomputed 27 times, each time re-admitting one topic that the extended definition excludes),
and the October 2026 re-check of 2020-2025 (a fresh OpenAlex sample of 1,500 papers per field and
year, set against the March 2026 snapshot). This script copies the first two parquet tables to CSV
without changing any value, copies the fresh-vintage field sizes, and recomputes the fresh-versus-
snapshot table from committed files only (``results/crosssource/fresh_recheck_20261006_n1500.csv``,
the field sizes and ``results/flow/or_by_year.csv``); when the original working table exists it is
checked against the recomputation and the script stops on any difference. Output is deterministic
(fixed row order, shortest round-trip floats). Run it once on a machine that has the data:

    python -m neuroai_cn.analysis.export_flow_sensitivity
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

from .. import config

STRICT_PARQUET = config.CORRECTIONS_DIR / "20260508" / "strict" / "q1_strict_or_by_year.parquet"
LOTO_PARQUET = config.CORRECTIONS_DIR / "20260508" / "loto_sensitivity.parquet"
CELLS_ROOT = Path(os.environ.get("NEUROAI_CELLS_ROOT", config.REPO_ROOT / "data" / "derived"))
FRESH_DIR = CELLS_ROOT / "_fresh_recheck_20261006"
FRESH_SIZES = FRESH_DIR / "field_sizes_fresh_20261006.csv"
FRESH_TABLE = FRESH_DIR / "tables" / "fresh_vs_snapshot_2020_2025.csv"

FLOW = config.RESULTS_DIR / "flow"
CROSS = config.RESULTS_DIR / "crosssource"
OUT_STRICT = FLOW / "sensitivity_strict_or_by_year.csv"
OUT_LOTO = FLOW / "sensitivity_loto.csv"
OUT_SIZES = FLOW / "fresh_recheck_field_sizes_20261006.csv"
OUT_FRESH = FLOW / "fresh_vs_snapshot_2020_2025.csv"


def export_strict() -> Path:
    """Strict-AI odds-ratio table: same 20 columns as ``or_by_year.csv``, sorted by year, direction."""
    df = pd.read_parquet(STRICT_PARQUET).sort_values(["year", "direction"], ascending=[True, False])
    df.to_csv(OUT_STRICT, index=False)
    return OUT_STRICT


def export_loto() -> Path:
    """Leave-one-topic-out table: one row per re-admitted topic, year and direction."""
    df = pd.read_parquet(LOTO_PARQUET)
    df = df.sort_values(["topic_added", "year", "direction"], ascending=[True, True, False])
    df.to_csv(OUT_LOTO, index=False)
    return OUT_LOTO


def export_fresh_sizes() -> Path:
    """Papers per field and year in the October 2026 vintage (neuroscience, extended AI, strict AI)."""
    df = pd.read_csv(FRESH_SIZES)
    for c in ("neuro", "ai_extended", "ai_strict"):
        df[c] = df[c].round().astype("int64")
    df.to_csv(OUT_SIZES, index=False)
    return OUT_SIZES


def fresh_vs_snapshot() -> pd.DataFrame:
    """Odds ratio of the October 2026 sample next to the snapshot value, 2020-2025, both directions.

    Fresh: share = target / (within + target) among the sampled papers' references, null = the
    cited field's share of the two fields' papers in the fresh vintage (extended AI definition).
    Snapshot: the same quantities from ``or_by_year.csv``.
    """
    cells = pd.read_csv(CROSS / "fresh_recheck_20261006_n1500.csv")
    sizes = pd.read_csv(OUT_SIZES).set_index("year")
    snap = pd.read_csv(FLOW / "or_by_year.csv", float_precision="round_trip")
    snap = snap.set_index(["year", "direction"])
    rows = []
    for direction in ("ai_to_neuro", "neuro_to_ai"):
        for _, c in cells[cells["direction"] == direction].sort_values("year").iterrows():
            y = int(c["year"])
            n_neuro, n_ai = float(sizes.loc[y, "neuro"]), float(sizes.loc[y, "ai_extended"])
            target = n_neuro if direction == "ai_to_neuro" else n_ai
            null = target / (n_neuro + n_ai)
            share = c["target"] / (c["within"] + c["target"])
            s = snap.loc[(y, direction)]
            refs = s["n_to_within"] + s["n_to_target"] + s["n_to_other"]
            rows.append(
                {
                    "year": y,
                    "direction": direction,
                    "fresh_per1000": c["per1000"],
                    "snap_per1000": s["rho_population"] * 1000.0,
                    "fresh_refs_per_paper": c["n_refs_classified"] / c["n_papers"],
                    "snap_refs_per_paper": refs / s["n_works_source"],
                    "fresh_restricted_share": share,
                    "snap_restricted_share": s["rho_restricted"],
                    "fresh_null": null,
                    "snap_null": s["rho_null_restricted"],
                    "fresh_OR": (share / (1 - share)) / (null / (1 - null)),
                    "snap_OR": s["or_restricted"],
                }
            )
    return pd.DataFrame(rows)


def export_fresh() -> Path:
    df = fresh_vs_snapshot()
    if FRESH_TABLE.exists():  # the working table of 2026-10-06: must agree with the recomputation
        ref = pd.read_csv(FRESH_TABLE).set_index(["year", "direction"])
        mine = df.set_index(["year", "direction"]).loc[ref.index, ref.columns]
        if not np.allclose(mine.to_numpy(float), ref.to_numpy(float), rtol=1e-9, atol=0):
            raise SystemExit(f"recomputed table differs from {FRESH_TABLE}")
    df.to_csv(OUT_FRESH, index=False)
    return OUT_FRESH


def main() -> None:
    FLOW.mkdir(parents=True, exist_ok=True)
    for f in (export_strict, export_loto, export_fresh_sizes, export_fresh):
        print(f())


if __name__ == "__main__":
    main()

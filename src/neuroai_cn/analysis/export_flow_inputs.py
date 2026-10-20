"""Export the small inputs of the citation-flow figures to committed CSV files.

The article Figures 1 and 2 and the change-point numbers are drawn from

* one OpenAlex-snapshot table, ``q1_v3_extended_or_by_year.parquet`` (72 rows: 36 years by 2 directions), and
* a few cross-source ``cells.jsonl`` samples (OpenAlex re-download, Semantic Scholar).

Both are tiny, but ``*.parquet`` and ``*.jsonl`` are not tracked, so this script copies them to
``results/flow/or_by_year.csv`` and ``results/crosssource/*.csv`` without touching any value
(floats are written with their shortest round-trip representation). Run it once on a machine that
has the data; everything downstream reads only the CSVs.

    python -m neuroai_cn.analysis.export_flow_inputs

Environment: ``NEUROAI_DATA`` (heavy-data root, see ``config``) for the parquet;
``NEUROAI_CELLS_ROOT`` for the directory that holds ``api_crosscite/`` and ``_fresh_recheck_20261006/``
(default: ``<repo>/data/derived``).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from .. import config

PARQUET = config.DERIVED_DIR / "corrections" / "20260508" / "q1_v3_extended_or_by_year.parquet"
CELLS_ROOT = Path(os.environ.get("NEUROAI_CELLS_ROOT", config.REPO_ROOT / "data" / "derived"))

# output name -> path of the cells.jsonl relative to CELLS_ROOT
CELLS = {
    "openalex_live": "api_crosscite/openalex_live/cells.jsonl",
    "openalex_live_extended": "api_crosscite/openalex_live_extended/cells.jsonl",
    "s2": "api_crosscite/s2/cells.jsonl",
    "fresh_recheck_20261006_n1500": "_fresh_recheck_20261006/sample_extended_n1500/cells.jsonl",
    "fresh_recheck_20261006_n1500_2010_2019": (
        "_fresh_recheck_20261006/sample_extended_n1500_2010_2019/cells.jsonl"
    ),
}


def export_or_by_year(out_dir: Path | None = None) -> Path:
    """Write the snapshot table, all 20 columns, 72 rows, original row order, values unchanged."""
    out = (out_dir or config.RESULTS_DIR / "flow") / "or_by_year.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(PARQUET)
    df.to_csv(out, index=False)  # pandas writes the shortest repr that round-trips
    return out


def export_cells(out_dir: Path | None = None) -> list[Path]:
    """Write one CSV per cells.jsonl with the same fields, one row per line."""
    out_dir = out_dir or config.RESULTS_DIR / "crosssource"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, rel in CELLS.items():
        src = CELLS_ROOT / rel
        rows = [json.loads(ln) for ln in src.read_text().splitlines() if ln.strip()]
        out = out_dir / f"{name}.csv"
        pd.DataFrame(rows).to_csv(out, index=False)
        written.append(out)
    return written


def main() -> None:
    print(export_or_by_year())
    for p in export_cells():
        print(p)


if __name__ == "__main__":
    main()

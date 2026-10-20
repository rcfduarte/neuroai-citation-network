"""Where things live. One place, overridable from the environment.

NEUROAI_DATA   root of the heavy data (OpenAlex snapshot, DuckDB index, large derived tables).
               Default: ~/data/neuroai-citation-network
Everything small enough to commit sits under the repository itself:
    results/   the numbers the figures and supplements are built from (CSV/JSON)
    figures/   the published figure files
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"
FIGURES_DIR = REPO_ROOT / "figures"

DATA_ROOT = Path(os.environ.get("NEUROAI_DATA", Path.home() / "data" / "neuroai-citation-network"))
SNAPSHOT_DIR = DATA_ROOT / "data" / "openalex-snapshot"
PARQUET_DIR = DATA_ROOT / "data" / "parquet"
DUCKDB_PATH = DATA_ROOT / "data" / "openalex.duckdb"
DERIVED_DIR = DATA_ROOT / "data" / "derived"
# Dated working directories under DERIVED_DIR (modules append the date, e.g. CORRECTIONS_DIR / "20260508").
CORRECTIONS_DIR = DERIVED_DIR / "corrections"
AUDITS_DIR = DERIVED_DIR / "audits"
AUTHORSHIPS_PARTS_DIR = DERIVED_DIR / "_authorships_parts"
LOG_DIR = DATA_ROOT / "logs"
TMP_DIR = DATA_ROOT / "tmp"


def openalex_email() -> str:
    """Contact address for the OpenAlex polite pool. Required: set the OPENALEX_EMAIL environment variable."""
    email = os.environ.get("OPENALEX_EMAIL", "").strip()
    if not email:
        raise SystemExit(
            "OPENALEX_EMAIL is not set. OpenAlex asks API users to identify themselves "
            "(polite pool); export OPENALEX_EMAIL=you@example.org and re-run."
        )
    return email


def openalex_user_agent(tool: str = "NeuroAI-CN-research/1.0") -> str:
    """User-Agent string carrying the required polite-pool contact address."""
    return f"{tool} (mailto:{openalex_email()})"

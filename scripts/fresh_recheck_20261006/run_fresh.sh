#!/usr/bin/env bash
# Isolated fresh OpenAlex re-pull (2026-10-06): field sizes + 2020-2025 sample.
# Writes ONLY under data/derived/_fresh_recheck_20261006/. Touches nothing else.
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT=data/derived/_fresh_recheck_20261006
[ -n "${OPENALEX_API_KEY:-}" ] || { echo "Set OPENALEX_API_KEY (free key from openalex.org/settings/api) and re-run."; exit 1; }
export OPENALEX_API_KEY
[ -n "${OPENALEX_EMAIL:-}" ] || { echo "Set OPENALEX_EMAIL (contact address for the OpenAlex polite pool) and re-run."; exit 1; }
export OPENALEX_EMAIL
.venv/bin/python scripts/fresh_recheck_20261006/field_sizes.py "$OUT/field_sizes_fresh_20261006.csv"
.venv/bin/python scripts/api_crosscite/openalex_crosscite_sample.py \
  --years 2020-2025 --fields neuro,ai --n 1500 --seed 7 --ai-def extended --out "$OUT/sample_extended_n1500"

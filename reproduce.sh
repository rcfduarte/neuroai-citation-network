#!/usr/bin/env bash
# Reproduce the article's figures and supplement numbers from a clean checkout.
#
#   ./reproduce.sh setup     create .venv from the pinned lock file (needs uv)
#   ./reproduce.sh check     lint, format check and the test suite (no large data needed)
#   ./reproduce.sh figures   redraw the article figures and the supplement figures from results/
#   ./reproduce.sh numbers   recompute every number quoted in the supplements and compare
#   ./reproduce.sh all       setup if needed, then check, figures, numbers
#   ./reproduce.sh heavy     print the one-time pipeline that rebuilds results/ from the OpenAlex snapshot
#
# Everything except `heavy` runs from the small files committed under results/ and needs no
# OpenAlex data. Figures are written to figures/ and the data bundles next to them to results/;
# after a run, `git status` should show no change in results/ (SVG files carry a date stamp
# and random element ids, so they differ in those details on every run).
set -euo pipefail
cd "$(dirname "$0")"

VENV=".venv"
PY="$VENV/bin/python"

need_venv() {
  if [ ! -x "$PY" ]; then
    echo "No $VENV found: run ./reproduce.sh setup first." >&2
    exit 1
  fi
}

setup() {
  command -v uv >/dev/null 2>&1 || {
    echo "uv is required (https://docs.astral.sh/uv/). Install it, then re-run." >&2
    exit 1
  }
  uv sync --frozen --extra dev
}

check() {
  need_venv
  $VENV/bin/ruff check .
  $VENV/bin/ruff format --check .
  $PY -m pytest -q -m "not heavy"
}

figures() {
  need_venv
  # Article figures (read results/flow and results/bridge).
  $PY -m neuroai_cn.figures.figure1_main_v2 or   # Figure 1: odds ratio, panels A to C (figure1_article)
  $PY -m neuroai_cn.figures.figure2_raw_v2       # Figure 2: raw counts and shares
  $PY -m neuroai_cn.figures.figure2_bridges_v3   # Figure 3: bridge papers, authors, institutions
  # Supplement figures that can be drawn from results/.
  $PY -m neuroai_cn.figures.figure_s1_field_sizes
  $PY -m neuroai_cn.figures.figure_s2             # Figures S2.1 and S2.2
  $PY -m neuroai_cn.figures.figure_s3_dilution
  $PY -m neuroai_cn.figures.figure_s4             # Figures S4.1 to S4.4
  $PY -m neuroai_cn.figures.figure_s5_concentration  # Figure S5.1
  $PY -m neuroai_cn.figures.figure_s5_eras            # Figure S5.2
  $PY -m neuroai_cn.figures.figure_s6             # Figures S6.1 and S6.2
  echo "Figures written to figures/."
}

numbers() {
  need_venv
  # Each headline number in docs/supplements is listed in docs/supplements/claims/ with
  # an expression that recomputes it from results/. The test fails on any mismatch.
  $PY -m pytest -q tests/test_supplement_claims.py
  # Re-derive the citation-age checks from the committed rankings.
  $PY -m neuroai_cn.analysis.citation_age.verify
}

heavy() {
  cat <<'EOF'
Rebuilding results/ from the raw OpenAlex snapshot needs about 364 GB of parquet and a 494 GB
DuckDB index, days of download and conversion, and is not run by this script. Stages, in order
(each script documents its own arguments; set NEUROAI_DATA to the data root first, and run
everything from the repository root with `.venv/bin/python -m ...`):

  1. scripts/download_snapshot.sh works     aws s3 sync of the works snapshot (uv sync --extra snapshot)
  2. scripts/convert_to_parquet.py          gzipped JSON lines to parquet
  3. scripts/build_duckdb_index.py          build openalex.duckdb
  4. scripts/verify_index.py                sanity queries on the index
     neuroai_cn.corpus.pool1 to pool4, then neuroai_cn.corpus.build_corpus   the four pools and their union
     (feeds the pool counts of results/corpus/pool_sizes.csv)
  5. cross-source samples (need OPENALEX_EMAIL): scripts/api_crosscite/openalex_crosscite_sample.py,
     scripts/api_crosscite/s2_crosscite_sample.py, scripts/fresh_recheck_20261006/run_fresh.sh
     (docs/METHODS.md, section 6)
  6. neuroai_cn.audits.q1_v3_extended       yearly cross-citation table (feeds results/flow/or_by_year.csv)
     neuroai_cn.audits.q1_strict            same table under the 35-topic core definition
     neuroai_cn.audits.bootstrap_sensitivity   leave-one-topic-out sweep
  7. neuroai_cn.analysis.export_flow_inputs      flow inputs and cross-source tables -> results/flow, results/crosssource
     neuroai_cn.analysis.export_field_sizes      field sizes, corpus totals, pools, anchor labels -> results/corpus, results/flow
     neuroai_cn.analysis.export_flow_sensitivity sensitivity tables -> results/flow
  8. neuroai_cn.audits.flow_composition --classifier extended, then --classifier strict;
     neuroai_cn.audits.flow_concentration; neuroai_cn.analysis.export_flow_composition
  9. neuroai_cn.analysis.changepoints       change points and segment slopes (reads results/flow only)
 10. neuroai_cn.analysis.citation_age.extract_counts, citing_volume, rankings,
     check_counts_by_year, tables_and_figure       citation-age analysis (about 45 minutes)
 11. bridge works: neuroai_cn.audits.q4_v3_extended, filter_by_era_books_only, author_inst_bridge,
     author_inst_top1000, institution_consolidation, affiliations_overrides, then
     scripts/concentration_filtered.py; export with neuroai_cn.analysis.export_bridge_tables
     and neuroai_cn.analysis.export_bridge_pool
 12. neuroai_cn.analysis.cited_vintage.build --stage labels, edges, cross, refage (one at a time),
     then cited_vintage.vintage, robustness, reference_age
 13. neuroai_cn.analysis.manifesto_citations --recompute   citations of the six NeuroAI papers

With the index built, `NEUROAI_HEAVY=1 .venv/bin/python -m pytest -m heavy` runs the checks that
read it. docs/METHODS.md documents every definition used.
EOF
}

case "${1:-all}" in
  setup)   setup ;;
  check)   check ;;
  figures) figures ;;
  numbers) numbers ;;
  heavy)   heavy ;;
  all)     [ -x "$PY" ] || setup; check; figures; numbers ;;
  *) echo "usage: $0 [setup|check|figures|numbers|all|heavy]" >&2; exit 2 ;;
esac

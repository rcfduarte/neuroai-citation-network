---
title: "Reproducing the cross-source citation crawls"
date: 2026-10-20
author: Renato Duarte
repo: https://github.com/rcfduarte/neuroai-citation-network
---

# Reproducing the cross-source crawls

The frozen OpenAlex snapshot is a single point of failure, so I re-derived the citation-flow series independently from the live OpenAlex API (a fresher classifier vintage of the same graph) and from Semantic Scholar (a different graph, with venue-based field definitions). This document is the operating manual for those crawls. What they show is reported in [S2, section 4.5](supplements/S2-citation-flow.md), and the formal description of the samples is in [methods 03, section 9](methods/03-citation-metric.md). The samples I used are committed, one CSV per crawl, in [`results/crosssource/`](../results/crosssource/), so you need to re-run nothing to check the numbers of the supplement; this document is for drawing new samples.

Method: I draw a random sample of papers per (field, year) cell, pull their references, classify every cited work, and estimate the cross-field share per 1,000 classified references with a 95% cluster bootstrap over papers. Full edge-by-edge replication through an API is not feasible. But a population-share estimate is.

Both crawls are long-running and checkpoint per cell, so re-running an interrupted crawl resumes by skipping completed cells. Run them detached, in tmux or under nohup.

## Read this before interpreting any output

**Levels are not comparable across sources; only shape is.** OpenAlex reclassifies topics between vintages, so absolute cross-citation levels depend on the classifier vintage, and Semantic Scholar uses a venue definition, different again. The May 2026 re-download reproduces the rise of neuroscience papers citing AI at full size when it uses the same AI definition as the snapshot, but for AI papers citing neuroscience it sits below the snapshot in most years, not only at the end ([S2, section 4.5](supplements/S2-citation-flow.md)). Compare shape and trend within a single source and vintage. Never splice snapshot and live series.

**Semantic Scholar elides references for roughly half of neuroscience papers**, by publisher policy: *Nature Neuroscience*, *NeuroImage* and others, intermittently. The sampler detects this (`data: null`) and excludes those papers, logging `elision_rate` per cell, so the Semantic Scholar estimate covers the non-elided subset only. Report the rate. If it trends with year, flag it; if it is high but roughly stable, the shape remains usable. In the run I committed, over the neuroscience cells, I observed a mean of 49%, a range of 26 to 92% and a slope of −0.70 percentage points per year with r = −0.47, hence stable enough for me to use. On the AI side the sampled papers with no reference list average 67%, which is a gap in Semantic Scholar's reference coverage and not publisher elision. A fully un-elided Semantic Scholar replication would need the S2AG bulk citations dataset, which is a much larger download-and-process job that I leave as future work.

**The AI definition is chosen with `--ai-def`.** The default, `strict`, is subfield 1702 only, which is what the API samplers can classify reproducibly. The option `extended` adds subfield 1707 (computer vision). It still deviates from the snapshot's extended definition ([S1](supplements/S1-data-and-classification.md), section 3.1) in two ways: it cannot apply the 26 excluded topics, and it omits topic T10502. The samples I committed contain both: `openalex_live.csv` is the strict run over 1990 to 2025, `openalex_live_extended.csv` the extended run over 2010 to 2025. The Semantic Scholar sample is venue-based and has no AI definition in this sense. My cross-check tests shape, not magnitude, which is definition-dependent: the narrow definition reverses the level ordering of the two lines in the snapshot too ([S2, section 5](supplements/S2-citation-flow.md)).

## Prerequisites

```bash
cd ~/repos/neuroai-citation-network
export OPENALEX_EMAIL=<your address>              # polite pool, required
export OPENALEX_API_KEY=<key>                     # optional; passed as api_key= when set
export SEMANTIC_SCHOLAR_API_KEY=<key>             # optional; see the note below
```

A Semantic Scholar key buys reliability rather than speed: both a valid key and the keyless public pool run at roughly 1 request per second, and the keyless pool answers with 429 errors more often. Keys are requested at https://www.semanticscholar.org/product/api#api-key. Keep keys in the environment and never in the repository.

## 1. OpenAlex live, 1990-2025 (primary cross-check)

Roughly 2 to 4 hours at N=1500, with no elision problem and about 10 requests per second on the polite pool. Run the strict definition over the whole series, then, if you want the extended-definition comparison of S2, the extended one over 2010 to 2025:

```bash
nohup uv run python scripts/api_crosscite/openalex_crosscite_sample.py \
  --years 1990-2025 --fields neuro,ai --n 1500 --seed 7 \
  --out data/derived/api_crosscite/openalex_live > logs/oa_crosscite.log 2>&1 &

nohup uv run python scripts/api_crosscite/openalex_crosscite_sample.py \
  --years 2010-2025 --fields neuro,ai --n 1500 --seed 7 --ai-def extended \
  --out data/derived/api_crosscite/openalex_live_extended > logs/oa_crosscite_ext.log 2>&1 &
```

## 2. Semantic Scholar, 1990-2025 (independent graph)

Roughly 8 hours at N=400 and 16 at N=800, on either a valid key or the keyless pool (the keyless pool is slower and 429-prone). N=400 already gives tight intervals. And it is the size of the sample I committed; use N≥800 only if the rare AI-citing-neuroscience cells need more volume.

```bash
nohup uv run python scripts/api_crosscite/s2_crosscite_sample.py \
  --years 1990-2025 --fields neuro,ai --n 400 \
  --out data/derived/api_crosscite/s2 > logs/s2_crosscite.log 2>&1 &
```

## 3. Aggregate and plot

```bash
uv run python scripts/api_crosscite/plot_crosscite_compare.py
```

This writes `figure1_share_crosscheck` (three sources by two directions, native levels with confidence intervals and the Semantic Scholar elision rate annotated), `figure1_share_crosscheck_overlay` (each curve normalized to its own 2010-2023 mean, so that shapes are directly comparable), `figure1_extended_replication` (if the extended sample exists) and `results_summary.md` with per-source slopes. Figures go to `figures/` by default, which overwrites the committed files of the same names; pass `--figdir` to write elsewhere. The snapshot curves are read from the heavy derived-data tree (see below), so this step needs the built index; the committed `results/flow/or_by_year.csv` holds the same yearly counts for the extended definition and `results/flow/sensitivity_strict_or_by_year.csv` for the strict one.

I ask the same question of each source: does neuroscience citing AI rise, taking off around 2014, and does AI citing neuroscience stay without a distinguishable trend, in every source? If yes, the result is robust across data sources, classifiers and vintages. S2 reports that the first holds in every source and that the second shows no distinguishable trend in any.

## Monitoring and outputs

```bash
tail -f logs/oa_crosscite.log
wc -l data/derived/api_crosscite/*/cells.jsonl    # expect 72 lines for a 1990-2025 run: 36 years x 2 fields
```

Each crawl writes one JSON line per (field, year) cell to `<out>/cells.jsonl`, carrying `per1000`, `ci_lo` and `ci_hi`, the underlying counts, and for Semantic Scholar the `elision_rate`. The metric is cross-field references per 1,000 classified references, `n_to_target / (n_to_within + n_to_target + n_to_other) * 1000`. The working directory `data/derived/` sits under the repository root, is not tracked, and holds only scratch output; the committed copies of the samples are the CSV files in `results/crosssource/`.

Comparison data from the frozen snapshot sit in the heavy derived-data tree outside the repository (`$NEUROAI_DATA/data/derived/corrections/20260508/`, see `src/neuroai_cn/config.py`): `q1_v3_extended_or_by_year.parquet` for the extended AI definition and `strict/q1_strict_or_by_year.parquet` for the strict one.

## 4. The October 2026 re-check

I ran a third, shorter crawl that re-pulled field sizes and a 2020-2025 sample from the live API, so that an odds ratio can be recomputed for a fresher vintage. It is isolated in its own scratch folder and needs both `OPENALEX_EMAIL` and `OPENALEX_API_KEY`:

```bash
scripts/fresh_recheck_20261006/run_fresh.sh
```

Its committed results are `results/crosssource/fresh_recheck_20261006_n1500.csv`, `results/flow/fresh_recheck_field_sizes_20261006.csv` and `results/flow/fresh_vs_snapshot_2020_2025.csv`; [`results/README.md`](../results/README.md) describes the columns, and S2 section 4.5 the findings.

## Validation already performed

I performed these checks already, so do not re-litigate them. The OpenAlex sampler reproduces the snapshot's rise of neuroscience citing AI within confidence intervals (slope +1.06 per 1,000 per year over 2014 to 2023 against +1.11 in the snapshot, extended definition); the gap in the opposite direction is the vintage drift described above. The Semantic Scholar sampler retrieves in-venue papers, classifies cited venues against the frozen venue allow-list, and correctly detects and excludes elided references, which my 2019 smoke test confirmed at roughly 35% elision.

## Optional, lower priority

PubMed/MeSH and DBLP are near-complete for neuroscience and AI respectively, but neither spans both fields. Use them only to sanity-check whether recent-year coverage is better elsewhere than in OpenAlex, never for cross-field shares.

# The citation metric

This file covers how I measure Q1: the restricted-universe odds ratio, its population variant, the confidence intervals, the time axis, the four eras fixed in the code, the two changepoint procedures and the bootstrap. It does not cover which papers count as neuroscience or AI (that is [field classification](02-field-classification.md)), and it does not report the results, which live in the article and in [S2](../supplements/S2-citation-flow.md) (Figure 1) and [S3](../supplements/S3-counts-and-field-sizes.md) (Figure 2).

## 1. What is being counted

For each year *y* and each ordered pair of fields, take every citation edge whose **citing** work falls in the source field and whose citing year is *y*, and bucket it by the field of the **cited** work:

- `n_within`: edges landing in the source field itself
- `n_target`: edges landing in the other field
- `n_other`: edges landing in a work classified `other`
- `n_unknown`: edges landing in a work with no primary topic
- `n_missing`: edges landing in a work absent from the database (committed as `n_to_missing`)

I compute both directions: source `neuro` with target `ai`, and source `ai` with target `neuro`. In the data files these are the values `neuro_to_ai` and `ai_to_neuro` of the column `direction`, named after the citation link. The article names them after where influence lands, which is the reverse; see the direction convention in the [methods README](README.md). The yearly table is committed as [`results/flow/or_by_year.csv`](../../results/flow/or_by_year.csv); its columns are described in [`results/README.md`](../../results/README.md).

Throughout, I count edges over the whole snapshot, not over the four corpus pools. That is why the annual field sizes are in the hundreds of thousands rather than the tens of thousands; they are tabulated year by year in [S1, section 4.1](../supplements/S1-data-and-classification.md).

## 2. The restricted odds ratio

The observed share is the fraction of *classified two-field* outbound citations that crossed the boundary:

```
rho_restricted = n_target / (n_within + n_target)
```

The null share is what that fraction would be if citations were handed out blind to discipline, in proportion to how much each field published that year:

```
rho_null_restricted = n_target_pop / (n_src_pop + n_target_pop)
```

where `n_src_pop` and `n_target_pop` are the counts of works published in year *y* carrying the source-field and target-field labels. The headline metric divides the odds of the first by the odds of the second:

```
OR_restricted = [rho / (1 - rho)] / [rho_null / (1 - rho_null)]
```

A value of 1 means a field crosses the boundary exactly as often as its own size and its neighbor's size predict. Below 1 means it stays home more than chance; above 1 means it reaches out more than chance. Both directions sit well below 1 for the entire series, which is the normal condition of every scientific field: disciplines are assortative, because that is what a discipline is. The quantities that interest me are never the absolute levels but the comparison between the two directions and the change over time.

The word *restricted* is carrying weight. In the denominator I count only citations whose target is labeled neuroscience or AI, and I discard the references that land in some third field (between a third and 44 percent of the references to indexed works, depending on field and year) and the third-field works from the null. Without that restriction the `other` pool, about 97% of the works published in every year, dominates the expected share and both directions collapse toward the same uninformative number.

### What rho_null literally is, and why that matters

`rho_null_restricted` is not an abstraction. For the neuroscience-cites-AI direction it is **AI's share of the combined AI-plus-neuroscience publication pool that year**; for the reverse direction it is **neuroscience's share of that same pool**. I verified that identity against the raw work counts to machine precision.

This has a direct and unavoidable consequence: **a shrinking neuroscience share inflates the AI-informs-neuroscience odds ratio on its own, with no change in anyone's behavior.** Over the analysis window AI grew from 0.84 times the size of neuroscience in 1995 to 2.11 times in 2023 (2.04 in 2025), so neuroscience's share of the two-field pool fell substantially. Any movement in the odds ratio must be read against that. Correcting for target-field size is the entire point of using an odds ratio rather than a raw share; it is what separates "neuroscientists developed an appetite for machine learning" from "neuroscientists cited AI at an unchanged rate while the AI literature grew almost tenfold". But the correction is a division, and a metric that can move because its denominator moved has to be reported as one.

For that reason I report the raw share per 1,000 outbound citations alongside the odds ratio rather than instead of it ([S3](../supplements/S3-counts-and-field-sizes.md), Figure 2). The share and the size-corrected odds ratio answer different questions, and both are valid: the size correction answers whether a field is over- or under-represented in the other's reference lists relative to its size, the raw share answers how much of what a field cites comes from the other ([S3, section 4.6](../supplements/S3-counts-and-field-sizes.md)). Do not set the two side by side as if they shared a denominator. The observed share inside the odds ratio leaves third-field references out, and the raw share of Figure 2B counts them: for AI papers citing neuroscience in 2023 the first is 25.10 per 1,000 and the second 16.51.

## 3. The population variant

The population variant keeps the `other` pool in both the observed and null denominators:

```
rho_population      = n_target / (n_within + n_target + n_other + n_unknown)
rho_null_population = n_target_pop / (n_src_pop + n_target_pop + n_other_pop)
```

with the odds ratio formed the same way. Here I report this as a sensitivity analysis. Under this null both series sit near or above 1 rather than far below it (in 2019, 1.51 for AI papers citing neuroscience and 1.02 for neuroscience papers citing AI), which is what the restriction was hiding: relative to the whole of science, both fields do reach across this particular boundary more than chance. The direction ordering is unchanged, so the central asymmetry does not depend on the choice of denominator. Trends are another matter. Dominated by the 97% of works in neither field, the population metric cannot resolve the trend of AI citing neuroscience (a slope of +0.0032 per year over 1995 to 2023, p = 0.37) although it resolves the other ([S2, section 4.6](../supplements/S2-citation-flow.md)).

## 4. Confidence intervals

Intervals I compute on the underlying **proportion**, not on the odds ratio directly, using the plain **Wilson score interval** at 95% (z = 1.96, no continuity correction; recomputing the bounds without one reproduces the committed values):

```
center = p + z²/(2n)
spread = z · sqrt( p(1-p)/n + z²/(4n²) )
[lo, hi] = (center ∓ spread) / (1 + z²/n),   z = 1.96
```

with *n* the appropriate denominator (restricted or population). The interval endpoints are then pushed through the same odds-ratio formula against the same `rho_null` to give the odds-ratio ribbon. Because it behaves far better when the numerator is small relative to the denominator, which is exactly the regime the early cross-field citations live in, I use Wilson rather than the normal approximation. These intervals express counting noise only; classification error and database drift are not in them ([S2, section 3.4](../supplements/S2-citation-flow.md)).

## 5. The time axis

Every series is indexed by **citing year** (the publication year of the paper doing the citing, `citation_edges.citing_year`), not by the year of the cited work. A point at 1998 answers "what did papers published in 1998 reach for", which is the question about behavior. Indexing by cited year would answer a question about reception instead, and would be badly distorted by the fact that recent papers have had less time to accumulate citations.

The analysis window is 1990 to 2025. Since the snapshot covers only part of 2026, I exclude it. The article's figure starts at 1995: the extended series does run back to 1990, but 1990, 1991 and 1992 rest on a few hundred cross-field citations each against tens of thousands later in the series, and in those three years the direction ordering reverses. And I treat that as a sparse-data regime rather than a finding.

In the figure I plot a **5-year centered rolling mean** of the yearly values, computed over the whole 1990 to 2025 series with at least three points in each window. At **2023** I stop all slope fits, because the 2024 and 2025 cohorts are contaminated by OpenAlex ingestion and reclassification events, and I show them hatched rather than fitted.

## 6. The four eras fixed in the code

I chose the era boundaries from events in AI that nobody disputes, not from the data, and wrote them into the code before I computed the slopes of the figure. They were not registered anywhere outside the code, and one was changed after the first fits, so I do not call them pre-registered ([S2, section 3.5](../supplements/S2-citation-flow.md)). Implementation: `CANONICAL_ERAS` in `src/neuroai_cn/figures/style.py`, the partition every era fit, bootstrap and shaded band in the figure uses. Endpoints are inclusive on both sides.

| Era | Range | Anchor events |
|-|-|-|
| Pre-deep-learning | 1990–2011 | Shallow networks dominant. LeCun et al. 1998; Hinton et al. 2006 deep belief networks |
| Deep-learning emergence | 2012–2015 | AlexNet (Krizhevsky, Sutskever and Hinton 2012); closing with the LeCun-Bengio-Hinton 2015 *Nature* review |
| Deep-learning expansion | 2016–2019 | AlphaGo (Silver et al. 2016); Marblestone, Wayne and Körding 2016 bridge manifesto; the transformer (Vaswani et al. 2017), mid-era |
| NeuroAI era | 2020–2025 | GPT-3 (Brown et al. 2020); Zador et al. 2023 NeuroAI white paper. Richards et al. 2019 and Zador 2019 as immediate precursors |

Every fit is clipped to 1995 to 2023, so the first era is fitted on 1995 to 2011 and the last on 2020 to 2023. Two overlapping sub-eras (ChatGPT era 2023–2025 and BERT-to-GPT-4 2018–2024) exist in the audit module `ERAS` of `src/neuroai_cn/audits/q1_v3_extended.py` for diagnostic panels and are not part of the primary partition.

On 2026-05-14, after the first fits, I widened the expansion era from two years to four so that its ordinary-least-squares fit rests on four points rather than two. But three of the four eras rest on four annual observations after truncation at 2023, and I read their intervals as suggestive rather than decisive. The eighteen-year and fourteen-year segments produced by the changepoint search below are the ones I would defend.

I fit per-era slopes by ordinary least squares in odds-ratio units per year, independently within each era, and report them with the bootstrap interval of section 8 rather than with a t-test.

## 7. Changepoints found by the data

Fixed eras protect against fitting boundaries to a desired result. They also guarantee the boundaries are wrong, because the literature does not turn on the years historians pick. So I run the series a second way and report both. Every procedure below is recomputed from `or_by_year.csv` alone by `python -m neuroai_cn.analysis.changepoints`, which writes [`results/flow/changepoints.csv`](../../results/flow/changepoints.csv) and [`results/flow/segment_slopes.csv`](../../results/flow/segment_slopes.csv). Years are the first year of the new segment.

**Piecewise-OLS exhaustive search, the procedure behind the figure.** For each direction, fit a piecewise-linear model with zero, one or two breakpoints, searching exhaustively over every admissible split of the year series and choosing the split that minimizes total within-segment squared residual. The zero-breakpoint fit is the baseline, so a breakpoint is only adopted if it reduces total squared error. For Figure 1 the search window is **1995 to 2023**, excluding the contaminated years, and each segment must contain **at least four** annual points. Implementation: `detect_all_changepoints`, which calls `detect_changepoints_series`, in `src/neuroai_cn/figures/cross_source.py`. Per-segment R² is reported as goodness of fit. It gives 2002 and 2006 for neuroscience papers citing AI and 2006 and 2020 for AI papers citing neuroscience. The 2002 break coincides with a batch of IEEE records dated 2002 ([S1, section 4.3](../supplements/S1-data-and-classification.md); [S2, section 5](../supplements/S2-citation-flow.md)).

**An earlier audit run of the same search.** The audit module `detect_changepoints` in `src/neuroai_cn/audits/q1_v3_extended.py` runs the same exhaustive search on the full 1990 to 2025 series with a **three-year** minimum segment, which includes the provisional years. It gives 1993 and 2005 for neuroscience papers citing AI and 2005 and 2022 for AI papers citing neuroscience. They are not PELT output, and they are not the figure's numbers ([S2, section 4.3](../supplements/S2-citation-flow.md)).

**PELT cross-check.** Independently, I run Pruned Exact Linear Time (Killick, Fearnhead and Eckley 2012, *JASA* 107(500):1590–1598, [doi:10.1080/01621459.2012.737745](https://doi.org/10.1080/01621459.2012.737745)) through the `ruptures` package. PELT minimizes an L2 cost (within-segment sum of squared residuals) plus a complexity penalty, with a pruning step that makes the exact dynamic-programming search linear in series length. I fixed the settings before running: the series standardized to mean 0 and standard deviation 1 within the window, a minimum segment of three years, and a penalty per breakpoint of c × ln(n) (BIC with c = 1, twice BIC with c = 2) or the constant 2. With the BIC penalty it returns 1993 for neuroscience papers citing AI and 2001 and 2023 for AI papers citing neuroscience on 1990 to 2025, and 2000 and 2015 (gold) and 2001 (teal) on 1995 to 2023.

The two families of procedure answer different questions. The piecewise search looks for changes of slope, PELT with an L2 cost looks for shifts in the average level, so they should not be expected to agree: PELT's 2001 break in the teal line marks the step up to the higher level of the 2000s, and its 2015 break in the gold line marks gold climbing to a new level. The figure's late teal breakpoint also moves with the settings: 2020 in the figure, 2021 with a three-year minimum on the same window, 2022 when 2024 and 2025 are included. What is robust is an upward turn somewhere around 2020 to 2022, not the exact year. **Piecewise-OLS numbers with the four-year minimum are the ones in the figure and in the article.**

Neither procedure produces per-segment p-values or an interval for where a break sits. A bootstrap over segment *locations*, as opposed to over slopes within fixed segments, would be a worthwhile extension, and I have not done it.

## 8. The bootstrap

I take confidence intervals on slopes from a **year-resampling bootstrap** rather than from a t-test. Within each (era or segment, direction) cell, the annual observations are resampled with replacement to the original cell size, the ordinary-least-squares slope is refitted on each resample, and the procedure repeats for **B = 500 replicates**. For the figure the generator is seeded with **20260528**, and the 2.5th and 97.5th percentiles give the 95% interval (the 99% interval uses the 0.5th and 99.5th) alongside the fraction of replicates with a positive and a negative slope. Implementation: `_bootstrap_slope_cis` in `src/neuroai_cn/figures/figure1_main_v2.py`, called by `figure1_article_v3.py`; the results are in [`results/flow/fig1B_era_slopes.csv`](../../results/flow/fig1B_era_slopes.csv) and [`fig1C_segment_slopes.csv`](../../results/flow/fig1C_segment_slopes.csv). An earlier audit implementation, `bootstrap_era_slopes` in `src/neuroai_cn/audits/bootstrap_sensitivity.py`, uses seed 42 and skips cells with fewer than four annual points; earlier versions of this file described that implementation as the figure's.

Significance markers follow the bootstrap, not the t-test: `**` means the 99% interval excludes zero, `*` means the 95% interval does, and `n.s.` means neither. Rather than individual citation edges, I resample years on purpose: the unit of independent observation here is the annual cohort, and edge-level resampling would produce absurdly tight intervals by treating millions of correlated edges as independent draws.

Bootstrap intervals over four points are optimistic: with four values the bootstrap distribution is coarse (for the 2020 to 2023 teal slope the 95% and 99% limits in the file are identical), and the ordinary t interval for that slope includes zero. That caveat applies to three of the four eras, and I state it wherever their markers appear ([S2, section 4.2](../supplements/S2-citation-flow.md)).

## 9. Cross-source replication

A single snapshot of a single database is a single point of failure, so I re-derived both series from two independent vantage points: the **live OpenAlex API**, a fresher classifier vintage of the same graph, and **Semantic Scholar**, a different graph with a venue-based field definition.

Full edge-by-edge replication through an API is not feasible. But a population-share estimate is: for each field and year, I draw a random sample of papers, pull their references, classify every cited work, and estimate the cross-field share with a 95% cluster bootstrap over papers. The metric is cross-field references per 1,000 classified references, a raw share and not the odds ratio. Four samples I committed under [`results/crosssource/`](../../results/crosssource/):

- OpenAlex re-download of May 2026, **strict** AI definition (subfield 1702 only): 1,500 papers per cell, all 72 cells (1990 to 2025, two directions).
- The same re-download with an **extended** AI definition (subfields 1702 and 1707): 1,500 papers per cell, 2010 to 2025. The API cannot apply the snapshot's 26 exclusions or add topic T10502, so this matches the snapshot's definition only approximately.
- Semantic Scholar: 400 papers sampled per cell from a fixed venue allow-list (NeurIPS, ICML, ICLR, CVPR and peers on the AI side; *Neuron*, *Nature Neuroscience*, *Journal of Neuroscience*, *NeuroImage* and peers on the neuroscience side), all 72 cells.
- An October 2026 re-check with the extended definition, 1,500 papers per cell for 2020 to 2025, paired with field sizes of the same fresher vintage so that an odds ratio can be recomputed.

Implementation: `scripts/api_crosscite/`; how to re-run it is in [reproducing the cross-source crawls](../reproducing-cross-source.md), and what the samples show is in [S2, section 4.5](../supplements/S2-citation-flow.md). What they test is *shape*. With the extended definition the re-download reproduces the rise of neuroscience papers citing AI at full size (over 2014 to 2023, +1.06 per 1,000 per year against +1.11 in the snapshot). For AI papers citing neuroscience it sits below the snapshot in most years, and the snapshot's end-of-series climb is absent from it.

Because the sources sit at different absolute levels, overlays normalize each curve to its own 2010–2023 mean. **Each source has its own level; only the shape is comparable, and series are never spliced across sources.**

Two coverage caveats bound the Semantic Scholar arm: it has no reference list for 48.7% of the neuroscience papers sampled and 66.6% of the AI-venue papers, driven mostly by publishers eliding references and by missing reference lists for 1990s conference proceedings. Elided papers are detected and dropped by the sampler, so the estimate covers the non-elided subset; elision falls by about 0.70 percentage points per year (r = −0.47 over the neuroscience cells), so recent coverage is better than early coverage.

## 10. The contaminated endpoint

From every fit I exclude the 2024 and 2025 cohorts, and I hatch them in the figure. The reasoning is a verification exercise reported in full in [S2, section 4.4](../supplements/S2-citation-flow.md), and it is a methods fact rather than a result, so it belongs here in summary: a re-download of the same graph with the same definition eight weeks after the snapshot gives 13.09 cross-field references per 1,000 for AI papers citing neuroscience in 2025 where the snapshot gives 21.37, 39% lower, and the October 2026 re-check gives a teal odds ratio of 0.043 for 2025 against the snapshot's 0.085; within-AI referencing collapses from a two-decade-stable 0.62–0.66 to 0.514 in 2025, which mechanically inflates a cross-field share; OpenAlex's own release notes document a new topics classifier in February 2024, 3.4 million DataCite works in April 2024, **151 million references added retroactively by fuzzy title-author-year matching in May 2024**, four million works reclassified against PubMed in July 2024, a new institution-matching algorithm in December 2024, and a complete platform rewrite in November 2025; and an independent graph sampled by venue shows no spike. My verdict, recorded in May 2026, is that the 2024 to 2025 rise is mostly a database artifact ([S2, section 4.4](../supplements/S2-citation-flow.md)).

Turning points before roughly 2023 are safe. Exact 2024 and 2025 values are not, and I would not defend any of them.

## 11. Where the numbers live

The per-year series behind every Q1 number is a single table with one row per (year, direction), carrying `n_to_within`, `n_to_target`, `n_to_other`, `n_to_unknown`, `n_to_missing`, both observed shares, both null shares, both odds ratios with their Wilson bounds, and the annual work counts for both fields. Given that table, every slope, interval and changepoint can be recomputed in a few lines without touching the pipeline. I committed it as [`results/flow/or_by_year.csv`](../../results/flow/or_by_year.csv) (72 rows). `python -m neuroai_cn.audits.q1_v3_extended` writes it as `q1_v3_extended_or_by_year.parquet` to the heavy derived-data tree (`$NEUROAI_DATA/data/derived/corrections/20260508/`, see `src/neuroai_cn/config.py`), and `python -m neuroai_cn.analysis.export_flow_inputs` exports it unchanged to the CSV. The strict-AI counterfactual table and the leave-one-topic-out table are `results/flow/sensitivity_strict_or_by_year.csv` and `results/flow/sensitivity_loto.csv`.

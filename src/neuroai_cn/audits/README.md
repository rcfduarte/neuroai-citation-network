# audits

These are the analysis modules behind my published numbers. Each is run as `python -m neuroai_cn.audits.<module>` against the OpenAlex DuckDB index and writes parquet/CSV files under `<NEUROAI_DATA>/data/derived/corrections/<date>/` (or `.../audits/<date>/`); I defined those locations in `neuroai_cn/config.py`. I committed the small tables the article and supplements are rebuilt from to `results/`. I mark a module internal when no supplement or methods note names it and no supplement-linked module imports it, and I keep internal modules as the record of checks, counterfactuals and intermediate tables. I derived the supplement column from `docs/supplements/` and `docs/methods/` and from the import graph at the time of writing.

My runs sit in date directories: `20260508` (main run), `20260514` (merged scheme) and `20260729` (field-filtered bridge set, which I built with scripts/concentration_*.py). Modules that call the OpenAlex or Semantic Scholar APIs require the environment variable `OPENALEX_EMAIL`.

| Module | Purpose | Main outputs | Supplement |
|-|-|-|-|
| `anchor_set` | The 70-paper anchor set (expected neuro / ai / bridge labels) used to validate field assignment | none (data module imported by the audit1 and scheme3 modules) | internal |
| `audit1_field_labels` | Audit 1: field-label integrity of the production classifier on the anchor set | `audits/20260508/audit1_field_labels.json`, `anchor_set.csv`, topic heatmap | internal |
| `audit1_extended` | Audit 1 re-run with the extended (v3) classifier | `audit1_extended_field_labels.json`, `audit1_extended_REPORT.md` | internal |
| `audit2_q1_stability` | Audit 2: stability of the Q1 odds-ratio series across five variants (population OR, rolling, coverage) | `q1_population_or.parquet`, `q1_rolling.parquet`, `q1_coverage_*.parquet` | internal |
| `audit3_q2_entities` | Audit 3: diagnosis of the entities that pass the dual-citizen threshold (placeholder names, institutions, superclusters) | `audit3_top100_diagnosis.csv`, `audit3_random100_baseline.csv` | internal |
| `extended_classifier` | Extended (v3) field assignment: subfield 1702 minus mis-clustered topics, plus subfield 1707 and topic T10502 | none (library imported by most modules and by `analysis/citation_age`) | S1 |
| `strict_classifier` | Strict field assignment (curated 35-topic AI core), the counterfactual to the extended scheme | none (library) | methods/02 |
| `q1_v3_extended` | Q1: cross-citation odds ratio by year, rolling slopes, era slopes and change points under the extended classifier | `q1_v3_extended_or_by_year.parquet`, `_rolling_slopes`, `_yoy`, era slopes | S1 (feeds Figure 1 through `python -m neuroai_cn.analysis.changepoints` and `python -m neuroai_cn.figures.cross_source`) |
| `q1_strict` | Q1 counterfactual under the strict classifier | `corrections/20260508/strict/q1_strict_*.parquet` | S1 (sensitivity figure, via `python -m neuroai_cn.figures.sensitivity_fig`) |
| `q1_merged_s1_s2` | Q1 under the merged scheme 1 (topics) plus scheme 2 (venue whitelist) assignment | `q1_merged_s1_s2_or_by_year.parquet`, era slopes, change points | internal |
| `bootstrap_sensitivity` | Bootstrap confidence intervals on era slopes and leave-one-topic-out sensitivity over the excluded AI topics | `bootstrap_era_slopes.parquet`, `bootstrap_era_summary.parquet`, `loto_sensitivity.parquet` | methods/02, methods/03 |
| `flow_composition` | What the AI to neuroscience citation flow is made of, by topic and citing year | `flow_composition_{classifier}.parquet` and `_topics.parquet` | S1 |
| `flow_concentration` | How many distinct AI works carry 50, 80, 90 and 95 percent of the AI to neuroscience citations | printed table and parquet of cumulative shares | internal |
| `scheme2_venues` | Scheme 2: venue-whitelist field assignment | `scheme2_venue_assignments.parquet`, `scheme2_venue_population.parquet` | methods/01, methods/02 |
| `scheme3_s2fos` | Scheme 3: Semantic Scholar field-of-study assignment (API) | `scheme3_s2fos.parquet` | methods/02 |
| `triangulation` | Agreement of the three field schemes on the anchor set | `triangulation_anchors.parquet`, `triangulation_REPORT.md` | S1 |
| `q2_v3_extended` | Q2: dual-citizen authors under the extended classifier with entity-cleaning rules | `q2_v3_named_examples_cleaned.parquet` and `_uncleaned.parquet` | internal |
| `q2_derivatives` | Q2 derivative analyses: balance of the two sides, double counting, permutation test, first cross-field year | `q2_derivatives_per_author.parquet`, `q2_first_crossfield_year.parquet` | internal |
| `q2_coauthorship` | Co-authorship network of the top-1000 bridge authors | `q2_coauthorship_nodes.parquet`, `_edges.parquet` | internal |
| `q4_v3_extended` | Q4: bridge-paper table (B harmonic score) and the ranked candidate lists under the extended classifier | `q4_v3_extended_full.parquet`, `_normalised.parquet`, `_filtered*.parquet` | S3 (feeds the bridge tables) |
| `q4_strict` | Q4 counterfactual under the strict classifier | `corrections/20260508/strict/q4_*.parquet` | internal |
| `filter_by_era_books_only` | Removes books from the locked era-filtered bridge set | `q4_v3_extended_filtered_by_era_no_books.parquet` | S3 (via `analysis/export_bridge_tables`) |
| `filter_papers_only` | Re-ranks bridge papers keeping journal articles and reviews | `q4_v3_extended_filtered_by_era_papers_only.parquet` | methods/05 |
| `clustering_pipeline` | Leiden clustering of the bridge-paper citation subgraph and temporal re-clustering | `clustering_nodes.parquet`, `clustering_edges.parquet`, `clustering_labels.parquet` | S3 |
| `q4_classify` | Paper-type classifier (methods, research, review) and track taxonomy for bridge papers | `q4_classified_nodes.parquet` | internal |
| `q4_reclassify_v2` | Reclassifies the top-1000 bridge papers by OpenAlex subfield | `q4_classified_nodes_v2.parquet`, `q4_reclassify_v2_report.json` | S3 |
| `q4_derivatives` | Q4 derivative analyses: Leiden retune, asymmetric B, era trajectory, anchor density | `q4_leiden_macro.parquet`, `q4_asymmetric_B.parquet` | internal |
| `author_inst_bridge` | Author, institution and country aggregates of the bridge score (top 200, 100, 50) | `author_inst_top_authors.parquet`, `_top_institutions.parquet`, `_top_countries.parquet` | S3 |
| `author_inst_top1000` | The same aggregates extended to the top 1000 authors and institutions, with population totals | `author_inst_top_authors_1000.parquet`, `_top_institutions_1000.parquet`, `author_inst_population_totals.json` | S3 |
| `institution_consolidation` | Merges sub-entities of corporate groups into parent organizations | `author_inst_top_institutions_consolidated.parquet` | S3 |
| `affiliations_overrides` | Current and past affiliations of the top-15 bridge authors, which I verified by hand | `author_current_affiliations_curated.parquet` | S3 |
| `current_affiliations` | Fetches current affiliations of the top-15 bridge authors from the API (superseded by the overrides I curated) | `author_current_affiliations.parquet` | internal |
| `fetch_paper_venues` | Fetches venue names of the top-15 bridge papers (labels for Figure 2 v3) | `top_paper_venues.parquet` | internal |
| `top1000_paper_institutions` | Maps each top-1000 bridge paper to its dominant institution | `top1000_paper_institutions.parquet` | internal |
| `bridge_links` | Paper to author and author to institution link tables for the bridge figures | `bridge_links_paper_author.parquet`, `bridge_links_author_inst.parquet` | internal |
| `authors_vs_institutions` | Whether authors or institutions carry more of the bridge weight: cumulative shares, Gini, within-institution concentration | `figures/figure_supp_authors_vs_inst.{png,svg}` | S3 |

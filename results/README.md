# Results

Small CSV and JSON files that the figures, supplements and tests are built from. I edited nothing by hand except the two "hand-made" inputs in `citation_age/`. I define the columns in [docs/METHODS.md](../docs/METHODS.md) and in the supplement that uses each file. The last column gives the module that writes the files (`python -m neuroai_cn.<module>`).

In every file with a `direction` column I name the citing field first: `ai_to_neuro` is AI papers citing neuroscience (teal), `neuro_to_ai` is neuroscience papers citing AI (gold). I kept `strict` in file and column names as the code name of the 35-topic core definition of AI, for example in `sensitivity_strict_or_by_year.csv`; in the cross-source samples it is the subfield 1702 definition. Files named `table_s1`, `table_s2` and `table_s3` hold Tables S5.1 to S5.3. I keep the citations of the six NeuroAI papers in `manifestos/`.

| Directory | Files | Contents | Written by |
|-|-|-|-|
| `flow/` | `or_by_year.csv` | Yearly counts, field sizes, shares, odds ratios with Wilson intervals, per direction, 1990 to 2025 | `analysis.export_flow_inputs` |
| | `figure1_article_*.csv`, `companion_counts_shares_sizes.csv` | Values plotted in article Figure 1, plus counts, shares and sizes per year | `figures.figure1_main_v2 or` |
| | `figure2_raw_v2_data.csv`, `figure_s3_dilution_data.csv` | Values plotted in article Figure 2 and Figure S3.1 | `figures.figure2_raw_v2`, `figures.figure_s3_dilution` |
| | `changepoints.csv`, `segment_slopes.csv` | Change points and segment slopes | `analysis.changepoints` |
| | `sensitivity_*.csv`, `fresh_*.csv` | Odds ratio under the 35-topic core, leave-one-topic-out sweep, October re-check | `analysis.export_flow_sensitivity` |
| | `field_sizes_by_year.csv`, `ai_topic_sizes_by_year.csv`, `*_2000_2004*.csv` | Works per year by field definition and topic; the 2000 to 2004 breakdown | `analysis.export_field_sizes` |
| | `flow_composition_*.csv`, `flow_concentration.csv` | What neuroscience papers cite when they cite AI | `analysis.export_flow_composition` |
| `crosssource/` | `openalex_live*.csv`, `s2.csv`, `fresh_recheck_*.csv` | Cross-field references per 1,000 in the API samples | `analysis.export_flow_inputs` |
| `corpus/` | `corpus_totals.csv`, `classification_topics.csv`, `pool_sizes.csv`, `anchor_labels.csv` | Corpus totals, topic-to-field assignment, the four pools, the 70-row anchor audit | `analysis.export_field_sizes` |
| `bridge/` | `table_s*.csv`, `author_institution_edges.csv`, `paper_author_links.csv`, `concentration_tiers.csv`, `headline_numbers.csv`, `institution_ranks_top100.csv`, `s1_eligibility_check.csv` | The three top-15 lists of article Figure 3, hand-verified edges, links drawn, concentration, ranks, the 40 best candidates | `analysis.export_bridge_tables` |
| | `pool_numbers.csv`, `eligibility_funnel.csv`, `era_composition.csv`, `ceiling_effect_top40.csv`, `clustered_set_composition.csv`, `unfiltered_top_papers.csv` | Candidate pool and its composition | `analysis.export_bridge_pool` |
| `citation_age/` | `table_s1_reference.csv`, `classification.csv` | Hand-made: the published top-15 table and the coding of the 271 ranked works | none |
| | `ranking_*_top100.csv`, `citing_volume.csv`, `to_classify.csv`, `*.json`, `tables.md` | Top 100 of the 11 rankings, citing volumes, headline numbers, checks | `analysis.citation_age.*` |
| `vintage/` | `matrix_*.csv` | Count matrices behind every vintage and reference-age table | `analysis.cited_vintage.build` |
| | `vintage_*.csv`, `subfield_breakdown.csv`, `claims.json` | Age profile and subfield mix of the cited neuroscience | `analysis.cited_vintage.vintage` |
| | `robustness*.csv`, `removed_works.csv`, `top25_inspection.csv` | Removal of mislabeled cited works | `analysis.cited_vintage.robustness` |
| | `reference_*.csv` | Reference-age profile and reference-list coverage | `analysis.cited_vintage.reference_age` |
| `manifestos/` | `*.csv`, `curve_comparison.json` | Citations of the six NeuroAI papers by year and citing field | `analysis.manifesto_citations` |

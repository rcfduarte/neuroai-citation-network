# Citation-age control for the bridge ranking

This package tests whether the finding that the most recent conceptual bridge work is from 2003 is an artifact of citation age. The published bridge ranking (Table S1) orders papers by the harmonic mean of their all-time neuroscience-side and AI-side citation counts, which favors older papers. I kept the published classification, eligibility rules and score (harmonic mean) unchanged in the scripts here and changed only the counts that enter the score: citations per year to 2023, citations within a fixed window after publication (8, 7 and 5 years), and the same counts weighted by the size of the citing literature. In the analysis note REPORT.md in the vault folder analysis-citation-age I wrote up the question and the results.

All scripts read the local OpenAlex DuckDB mirror (config.DUCKDB_PATH, snapshot 2026-03-30) strictly read-only, with a 16 GB memory limit, and the 133,763-paper candidate pool written by the published pipeline (config.DERIVED_DIR/corrections/20260508/q4_v3_extended_full.parquet). I made two inputs by hand and committed them in results/citation_age: table_s1_reference.csv (Table S1 as printed, the reproduction target) and classification.csv (concept, method, tool, book or artifact coding of the 271 ranked works, with first-publication years for reprints). Step 3 stops if any ranked work is uncoded.

Run the steps in this order from the repository root, one at a time (steps 1 and 1b are heavy DuckDB jobs and should not run together or alongside other jobs on the mirror):

```
python -m neuroai_cn.analysis.citation_age.extract_counts
python -m neuroai_cn.analysis.citation_age.citing_volume
python -m neuroai_cn.analysis.citation_age.rankings
python -m neuroai_cn.analysis.citation_age.check_counts_by_year
python -m neuroai_cn.analysis.citation_age.tables_and_figure
python -m neuroai_cn.analysis.citation_age.verify
```

extract_counts builds the per-year citation counts (citing field, citing year) for every paper in the pool, plus pool metadata. citing_volume counts the works and the references made per citing field and year, used for the growth-normalized variants. rankings checks that the per-year counts re-sum to the published totals, builds every ranking under the published eligibility rules, checks that the top 15 of the published score reproduces Table S1, and writes the guard checks. check_counts_by_year compares the classified per-year counts of the top 25 of the three primary rankings against OpenAlex's own counts_by_year. tables_and_figure applies the hand coding and writes the tables, the summary numbers and the figure. verify recomputes the headline numbers from the committed CSVs alone, with no DuckDB, and exits non-zero if they differ from checks.json and summary.json.

Large intermediate files (per-year counts, pool metadata, the full rankings table, about 70 MB) go to config.DERIVED_DIR/citation_age, and I did not commit them. In results/citation_age I committed checks.json, summary.json, tables.md, citing_volume.csv, check_counts_by_year.json, to_classify.csv (the union of the ranked heads, used for the hand coding) and ranking_<name>_top100.csv (top 100 of each of the 11 rankings). The figure is written to figures/fig_top100_years.svg, .png and -onwhite.png. Logs of a run are in config.LOG_DIR.

Runtimes: in my run of 2026-10-20 extract_counts took 33 minutes and citing_volume 13 minutes (my original run of 2026-09-28 took about 13 and 6 minutes; the mirror may have been under load from other jobs), rankings 104 seconds, check_counts_by_year 18 seconds, tables_and_figure 93 seconds. And verify took a few seconds.

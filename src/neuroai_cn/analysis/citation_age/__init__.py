"""Citation-age control for the bridge ranking (docs/METHODS.md, section 10; supplement S6).

The published ranking orders papers by the harmonic mean of their all-time citation counts from the
two fields. These scripts keep the published eligibility rules and the harmonic-mean score and change
only the counts that enter it: citations per year to 2023, citations in a fixed window after
publication (8, 7 and 5 years), and the same counts weighted by the size of the citing literature.
Two inputs are made by hand and committed in results/citation_age: table_s1_reference.csv (the
published table, the reproduction target) and classification.csv (the coding of the 271 ranked works).

Run from the repository root, one step at a time (the first two are heavy read-only DuckDB jobs; large
intermediates go to config.DERIVED_DIR/citation_age and are not committed):

    python -m neuroai_cn.analysis.citation_age.extract_counts      per-year counts by citing field, pool metadata
    python -m neuroai_cn.analysis.citation_age.citing_volume       works and references per citing field and year
    python -m neuroai_cn.analysis.citation_age.rankings            all rankings; checks Table S5.1 is reproduced
    python -m neuroai_cn.analysis.citation_age.check_counts_by_year   compares with OpenAlex counts_by_year
    python -m neuroai_cn.analysis.citation_age.tables_and_figure   applies the coding; tables and summary (Figure S6.1: neuroai_cn.figures.figure_s6)
    python -m neuroai_cn.analysis.citation_age.verify              recomputes headline numbers from the CSVs
"""

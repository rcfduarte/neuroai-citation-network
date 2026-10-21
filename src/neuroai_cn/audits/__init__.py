"""Pipeline modules that build the yearly tables, classifiers and bridge tables from the DuckDB index.

Run each as `python -m neuroai_cn.audits.<module>`; outputs go to config.DERIVED_DIR (parquet and CSV),
and the small tables the supplements use are exported to results/ by neuroai_cn.analysis. Set
OPENALEX_EMAIL for modules that call the OpenAlex or Semantic Scholar APIs. The module docstrings
describe inputs and outputs.
"""

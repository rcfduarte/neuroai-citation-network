"""Vintage and reference age of the cited literature (docs/METHODS.md, sections 9 and 10; supplement S4).

How old is the neuroscience that AI papers cite, and the AI that neuroscience papers cite. The
definitions are in definitions.py. Run from the repository root, one heavy job at a time (intermediate
parquet goes to config.DERIVED_DIR/vintage and is not committed):

    python -m neuroai_cn.analysis.cited_vintage.build --stage labels   then edges, cross, refage
    python -m neuroai_cn.analysis.cited_vintage.vintage                results/vintage tables
    python -m neuroai_cn.analysis.cited_vintage.robustness
    python -m neuroai_cn.analysis.cited_vintage.reference_age
    python -m neuroai_cn.analysis.manifesto_citations                  the six manifesto papers

`build --years LO HI --out DIR` recomputes a slice, which the heavy test uses.
"""

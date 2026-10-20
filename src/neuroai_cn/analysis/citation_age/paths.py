"""Locations used by the citation-age pipeline, all derived from neuroai_cn.config.

WORK_DIR   large intermediate files (per-year count parquet, metadata, full rankings);
           under config.DERIVED_DIR, outside the repository, never committed.
RESULTS    small committed outputs and the two hand-made inputs
           (table_s1_reference.csv, classification.csv): results/citation_age.
POOL       the 133,763-paper candidate pool written by the published pipeline.
"""

from neuroai_cn.config import DERIVED_DIR, RESULTS_DIR

WORK_DIR = DERIVED_DIR / "citation_age"
RESULTS = RESULTS_DIR / "citation_age"
POOL = DERIVED_DIR / "corrections" / "20260508" / "q4_v3_extended_full.parquet"

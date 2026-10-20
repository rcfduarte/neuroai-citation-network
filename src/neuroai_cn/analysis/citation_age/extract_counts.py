"""Step 1: per-year citation counts for every paper in the bridge candidate pool.

Question (reviewer comment, 2026-09-26): is "the most recent bridge work is from 2003"
an artefact of citation age? To control for age we need, for each candidate paper,
the number of citations it received from neuroscience and from AI papers *in each
citing year*. The published pipeline (q4_v3_extended.py) only stored all-time totals.

Read-only against the frozen OpenAlex DuckDB mirror (snapshot 2026-03-30).

Classification is the extended classifier used by the bridge metric, reproduced here
with the repo's own constants, restricted to the two labels the counts need
('neuro', 'ai'), and restricted to citing works published 1990-2026, exactly as
build_extended_field_assignment(con, year_min=1990, year_max=2026) does in q4_v3.

Outputs (config.DERIVED_DIR / citation_age, outside the repository):
    pool_counts_by_year.parquet   work_id, citing_field, citing_year, n
    pool_metadata.parquet         work_id, doi, title, publication_year,
                                  publication_date, type, venue, source_type
    (first authors for the ranked heads are fetched by index lookup in step 2b)
"""

import time

import duckdb

from neuroai_cn.analysis.citation_age.paths import POOL, WORK_DIR
from neuroai_cn.audits.extended_classifier import (
    AI_SUBFIELD_1702,
    AI_SUBFIELD_1707,
    BAD_1702_TOPIC_IDS,
    NEURAL_MEMORY_TOPIC_2208,
)
from neuroai_cn.config import DUCKDB_PATH, TMP_DIR
from neuroai_cn.utils.duckdb import NEURO_FIELD_ID

OUT = WORK_DIR
SPILL = TMP_DIR  # scratch spill dir, not the mirror


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SPILL.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    con.execute("PRAGMA threads=8")
    con.execute("PRAGMA memory_limit='16GB'")
    con.execute(f"PRAGMA temp_directory='{SPILL}'")
    con.execute("PRAGMA preserve_insertion_order=false")

    bad = "[" + ",".join("'" + t + "'" for t in sorted(BAD_1702_TOPIC_IDS)) + "]"

    con.execute(f"CREATE TEMP TABLE pool AS SELECT work_id FROM read_parquet('{POOL}')")
    print(
        "pool:",
        con.execute("SELECT COUNT(*), COUNT(DISTINCT work_id) FROM pool").fetchone(),
        flush=True,
    )

    t0 = time.time()
    con.execute(f"""
    COPY (
      SELECT w.id AS work_id, w.doi, w.display_name AS title, w.publication_year,
             w.publication_date, w.type,
             w.primary_location.source.display_name AS venue,
             w.primary_location.source.type AS source_type
      FROM works w JOIN pool p ON p.work_id = w.id
    ) TO '{OUT}/pool_metadata.parquet' (FORMAT parquet, COMPRESSION zstd)
    """)
    print("metadata written", round(time.time() - t0, 1), "s", flush=True)

    t0 = time.time()
    # Same CASE expression as build_extended_field_assignment(); only the two labels
    # that enter c_neuro / c_ai are kept, which is what makes the temp table fit in memory.
    con.execute(f"""
    CREATE TEMP TABLE wf AS
    SELECT work_id, year, field FROM (
      SELECT w.id AS work_id, w.publication_year AS year,
        CASE
          WHEN w.primary_topic IS NULL THEN 'unknown'
          WHEN w.primary_topic.field.id = '{NEURO_FIELD_ID}' THEN 'neuro'
          WHEN (w.primary_topic.subfield.id = '{AI_SUBFIELD_1702}'
                AND w.primary_topic.id NOT IN (SELECT unnest({bad})))
            OR w.primary_topic.subfield.id = '{AI_SUBFIELD_1707}'
            OR w.primary_topic.id = '{NEURAL_MEMORY_TOPIC_2208}'
          THEN 'ai'
          ELSE 'other'
        END AS field
      FROM works w
      WHERE w.publication_year BETWEEN 1990 AND 2026
    ) WHERE field IN ('neuro', 'ai')
    """)
    print(
        "wf (neuro+ai citing works):",
        con.execute("SELECT field, COUNT(*) FROM wf GROUP BY 1").fetchall(),
        round(time.time() - t0, 1),
        "s",
        flush=True,
    )

    t0 = time.time()
    con.execute("""
    CREATE TEMP TABLE cnt AS
    SELECT e.cited_work_id AS work_id, src.field AS citing_field, src.year AS citing_year,
           COUNT(*) AS n
    FROM citation_edges e
    JOIN pool p ON p.work_id = e.cited_work_id
    JOIN wf src ON src.work_id = e.citing_work_id
    GROUP BY 1, 2, 3
    """)
    print(
        "counts built",
        con.execute("SELECT COUNT(*), SUM(n) FROM cnt").fetchone(),
        round(time.time() - t0, 1),
        "s",
        flush=True,
    )
    con.execute(
        f"COPY cnt TO '{OUT}/pool_counts_by_year.parquet' (FORMAT parquet, COMPRESSION zstd)"
    )

    con.close()
    print("done", flush=True)


if __name__ == "__main__":
    main()

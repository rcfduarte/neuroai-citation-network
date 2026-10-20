"""Step 1b: size of each field's citing literature per year, for the growth sensitivity.

A fixed citation window equalises exposure time but not the size of the citing
literature: AI and neuroscience produced many more papers (and references) in
2014-2022 than in 1998-2006, so a recent work collects more citations in the same
window at the same share of attention. To test whether that growth drives the
result, step 2 can express each citation as a share of all references made by the
citing field in the citing year.

Read-only against the frozen OpenAlex mirror. Same classifier and 1990-2026 citing
window as step 1.

Output: citing_volume.parquet (config.DERIVED_DIR / citation_age, read by step 2) and
        citing_volume.csv (results/citation_age, committed); columns
        citing_field, citing_year, n_works, n_refs
    n_works = classified works published that year
    n_refs  = citation edges (references) made by those works, to any cited work
"""

import time

import duckdb

from neuroai_cn.analysis.citation_age.paths import RESULTS, WORK_DIR
from neuroai_cn.audits.extended_classifier import (
    AI_SUBFIELD_1702,
    AI_SUBFIELD_1707,
    BAD_1702_TOPIC_IDS,
    NEURAL_MEMORY_TOPIC_2208,
)
from neuroai_cn.config import DUCKDB_PATH, TMP_DIR
from neuroai_cn.utils.duckdb import NEURO_FIELD_ID

OUT = WORK_DIR
SPILL = TMP_DIR


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SPILL.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    con.execute("PRAGMA threads=8")
    con.execute("PRAGMA memory_limit='16GB'")
    con.execute(f"PRAGMA temp_directory='{SPILL}'")
    con.execute("PRAGMA preserve_insertion_order=false")
    bad = "[" + ",".join("'" + t + "'" for t in sorted(BAD_1702_TOPIC_IDS)) + "]"

    t0 = time.time()
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
    print("wf built", round(time.time() - t0, 1), "s", flush=True)

    t0 = time.time()
    con.execute("""
    CREATE TEMP TABLE refs AS
    SELECT src.field AS citing_field, src.year AS citing_year, COUNT(*) AS n_refs
    FROM citation_edges e
    JOIN wf src ON src.work_id = e.citing_work_id
    GROUP BY 1, 2
    """)
    print("refs built", round(time.time() - t0, 1), "s", flush=True)
    con.execute(f"""
    COPY (
      SELECT w.field AS citing_field, w.year AS citing_year, COUNT(*) AS n_works,
             COALESCE(MAX(r.n_refs), 0) AS n_refs
      FROM wf w LEFT JOIN refs r ON r.citing_field = w.field AND r.citing_year = w.year
      GROUP BY 1, 2 ORDER BY 1, 2
    ) TO '{OUT}/citing_volume.parquet' (FORMAT parquet)
    """)
    vol = con.execute(f"SELECT * FROM read_parquet('{OUT}/citing_volume.parquet')").df()
    RESULTS.mkdir(parents=True, exist_ok=True)
    vol.to_csv(RESULTS / "citing_volume.csv", index=False)
    print(vol.to_string(index=False), flush=True)
    con.close()
    print("done", flush=True)


if __name__ == "__main__":
    main()

"""Independent check: classified per-year counts must not exceed OpenAlex's own counts_by_year.

OpenAlex stores, per work, the number of citing works in each year (all fields, 2012 onward
in this snapshot). Our per-year counts from neuroscience plus AI citing works are a subset of
those, so for every work and year n_neuro(t) + n_ai(t) <= counts_by_year(t) must hold, up to
small differences in how OpenAlex aggregates. Run on the top 25 of the three primary
rankings. Read-only point lookups on the works id index. The three summary numbers
are also written to results/citation_age/check_counts_by_year.json.
"""

import json

import duckdb
import pandas as pd

from neuroai_cn.analysis.citation_age.paths import RESULTS, WORK_DIR
from neuroai_cn.config import DUCKDB_PATH


def main() -> None:
    rk = pd.read_parquet(WORK_DIR / "rankings.parquet")
    ids = rk[rk["ranking"].isin(["orig", "rate", "win8"]) & (rk["rank"] <= 25)]["work_id"].unique()
    cnt = pd.read_parquet(WORK_DIR / "pool_counts_by_year.parquet")
    mine = cnt[cnt.work_id.isin(ids)].groupby(["work_id", "citing_year"])["n"].sum()

    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    con.execute("PRAGMA threads=2")
    rows = []
    for w in ids:
        cby = con.execute("SELECT counts_by_year FROM works WHERE id = ?", [w]).fetchone()[0] or []
        for d in cby:
            if 2012 <= d["year"] <= 2023:
                rows.append((w, d["year"], d["cited_by_count"]))
    con.close()
    oa = pd.DataFrame(rows, columns=["work_id", "citing_year", "oa"]).set_index(
        ["work_id", "citing_year"]
    )["oa"]
    j = pd.concat([mine.rename("mine"), oa], axis=1).dropna()
    yrs = j.index.get_level_values("citing_year")
    j = j[(yrs >= 2012) & (yrs <= 2023)]
    viol = j[j["mine"] > j["oa"]]
    n_pairs, n_works = len(j), int(j.index.get_level_values(0).nunique())
    median_share = float((j.mine / j.oa).median())
    worst = int((viol.mine - viol.oa).max()) if len(viol) else 0
    print(f"work-years compared: {n_pairs}; works: {n_works}")
    print(f"classified share of all citations, median {median_share:.2f}")
    print(f"violations (ours > OpenAlex): {len(viol)}; worst excess {worst}")
    print(viol.assign(excess=viol.mine - viol.oa).sort_values("excess").tail(10).to_string())

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "check_counts_by_year.json").write_text(
        json.dumps(
            {
                "work_years_compared": n_pairs,
                "works": n_works,
                "median_classified_share": round(median_share, 4),
                "violations": len(viol),
                "worst_excess": worst,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()

"""Step 2: reproduce Table S5.1, then re-rank the same eligible set with citation age controlled.

Inputs
    q4_v3_extended_full.parquet    the 133,763-paper candidate pool (published pipeline output)
    pool_counts_by_year.parquet    per-work, per-citing-field, per-citing-year counts (step 1)
    pool_metadata.parquet          type, venue, source type, first author (step 1)
    citing_volume.parquet          references made per field and year (step 1b)
    table_s1_reference.csv         Table S5.1 as printed in the supplement (results/citation_age)

Scores (harmonic mean H(a, b) = 2ab / (a + b), as in the published metric)
    orig   H(c_neuro, c_ai), all citing years 1990-2026            -> the published ranking
    rate   H(r_neuro, r_ai), r = citations with citing year in [publication_year - 1, 2023]
           divided by (2023 - publication_year + 1); works published <= 2023
    win8   H(w_neuro, w_ai), w = citations with citing year in [publication_year - 1,
           publication_year + 8]; works published 1990-2015 (every window closes by 2023)

Sensitivity variants
    orig_1990_2015   published score, restricted to the win8 publication years
    win7             window <= publication_year + 7 (the other reading of "first 8 years")
    win5_to2018      window <= publication_year + 5, works 1990-2018 (reaches newer works)
    rate_noceil      rate without the E2 ceiling (c_total_classified < 10,000)
    win8_noceil      win8 without the E2 ceiling
    rate_unknown     rate, also admitting papers whose own field label is 'unknown'
    win8_share       win8 with each citation divided by the references the citing field made
                     that year (per million), removing the growth of the citing literature
    rate_share       rate with the same growth normalisation

Eligibility is the published rule set, identical for every ranking: own field label
'ai' or 'neuro'; all-time c_total_classified < 10,000 (E2); OpenAlex type article or
review; not hosted on an ebook platform or book series; non-empty title; not a
hand-listed known book; title-level deduplication keeping the highest-scoring copy.

Outputs
    results/citation_age/checks.json              every reproduction and guard check, with numbers
    results/citation_age/ranking_<name>_top100.csv  top 100 of every ranking
    results/citation_age/to_classify.csv          union of the heads of all rankings, for coding
    config.DERIVED_DIR/citation_age/rankings.parquet  every eligible work's score and rank
                                                  under every ranking (large, not committed)
"""

import json
import re
import sys

import numpy as np
import pandas as pd

from neuroai_cn.analysis.citation_age.paths import POOL, RESULTS, WORK_DIR
from neuroai_cn.audits.filter_by_era_books_only import KNOWN_BOOK_TITLES

LAST_STABLE_YEAR = 2023  # 2024-2025 OpenAlex data are unstable (re-export window)
CEILING = 10_000  # E2 ubiquity ceiling on all-time classified citations
KEEP_TYPES = {"article", "review"}
BOOK_SOURCES = {"ebook platform", "book series"}
TOP_N_CSV = 100

checks: dict[str, dict] = {}


def check(name: str, ok: bool, **detail) -> None:
    checks[name] = {"pass": bool(ok), **detail}
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail if detail else ''}", flush=True)


def harmonic(a: pd.Series, b: pd.Series) -> pd.Series:
    a = a.astype(float)
    b = b.astype(float)
    s = a + b
    return pd.Series(np.where(s > 0, 2.0 * a * b / s.where(s > 0, 1.0), 0.0), index=a.index)


def norm_title(t: pd.Series) -> pd.Series:
    # identical to filter_papers_only.py
    return t.astype(str).str.lower().str.strip().str.replace(r"\s+", " ", regex=True)


def clean_title(t: str) -> str:
    return re.sub(r"<[^>]+>", "", str(t)).strip()


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    # ----------------------------------------------------------------------------- load
    pool = pd.read_parquet(POOL)
    meta = pd.read_parquet(WORK_DIR / "pool_metadata.parquet")
    cnt = pd.read_parquet(WORK_DIR / "pool_counts_by_year.parquet")
    check("pool_size_133763", len(pool) == 133_763, n=len(pool))
    check(
        "metadata_covers_pool",
        meta.work_id.nunique() == len(pool) and len(meta) == len(pool),
        n_meta=len(meta),
        n_unique=int(meta.work_id.nunique()),
    )

    # ---------------------------------------------- check A: per-year counts re-sum to totals
    tot = cnt.pivot_table(
        index="work_id", columns="citing_field", values="n", aggfunc="sum", fill_value=0
    ).reset_index()
    a = pool[["work_id", "c_neuro", "c_ai"]].merge(tot, on="work_id", how="left").fillna(0)
    mism = a[(a["neuro"] != a["c_neuro"]) | (a["ai"] != a["c_ai"])]
    check(
        "A_per_year_counts_resum_to_published_totals",
        len(mism) == 0,
        n_works=len(a),
        n_mismatch=len(mism),
        examples=mism.head(5).to_dict("records") if len(mism) else [],
    )
    if len(mism):
        sys.exit("Per-year counts do not reproduce c_neuro / c_ai: classifier or edge set differs.")

    # ------------------------------------------------------------ controlled counts per work
    cnt = cnt.merge(pool[["work_id", "publication_year"]], on="work_id")
    cy, py = cnt["citing_year"], cnt["publication_year"]
    # Controlled counts start at publication_year - 1 (one year of grace for online-first
    # versions). Citations dated earlier than that cannot have been received "after
    # publication"; in practice they come from reprints and merged records that absorbed an
    # older work's citations, and admitting them would let such records bank decades.
    EARLY = py - 1
    cnt["n23"] = cnt["n"].where((cy >= EARLY) & (cy <= LAST_STABLE_YEAR), 0)
    for w in (8, 7, 5):
        cnt[f"w{w}"] = cnt["n"].where((cy >= EARLY) & (cy <= py + w), 0)
    cnt["pre_pub"] = cnt["n"].where(cy < py, 0)
    # Growth sensitivity: each citation weighted by the size of the citing literature, i.e.
    # citations per million references made by the citing field in the citing year.
    vol = pd.read_parquet(WORK_DIR / "citing_volume.parquet")
    cnt = cnt.merge(
        vol[["citing_field", "citing_year", "n_refs"]],
        on=["citing_field", "citing_year"],
        how="left",
    )
    check(
        "G_citing_volume_covers_all_count_rows",
        bool(cnt["n_refs"].gt(0).all()),
        n_missing=int((~cnt["n_refs"].gt(0)).sum()),
    )
    share = 1e6 * cnt["n"] / cnt["n_refs"]
    cnt["s23"] = share.where((cy >= EARLY) & (cy <= LAST_STABLE_YEAR), 0)
    cnt["s8"] = share.where((cy >= EARLY) & (cy <= py + 8), 0)
    wide = cnt.pivot_table(
        index="work_id",
        columns="citing_field",
        values=["n23", "w8", "w7", "w5", "pre_pub", "s23", "s8"],
        aggfunc="sum",
        fill_value=0,
    )
    wide.columns = [f"{v}_{f}" for v, f in wide.columns]
    yr = pool[["work_id", "publication_year"]].merge(
        meta[["work_id", "publication_year"]], on="work_id", suffixes=("", "_meta")
    )
    check(
        "metadata_year_matches_pool",
        bool((yr["publication_year"] == yr["publication_year_meta"]).all()),
    )
    df = pool.merge(
        meta.drop(columns=["publication_year", "doi", "title"]), on="work_id", how="left"
    ).merge(wide.reset_index(), on="work_id", how="left")
    df = df.fillna({c: 0 for c in wide.columns})

    y = df["publication_year"]
    df["years_to_2023"] = (LAST_STABLE_YEAR - y + 1).where(y <= LAST_STABLE_YEAR)
    df["r_neuro"] = df["n23_neuro"] / df["years_to_2023"]
    df["r_ai"] = df["n23_ai"] / df["years_to_2023"]
    # Share of a record's classified citations dated before its own publication year. A large
    # share is the signature of a reprint or a record that absorbed another work's citations.
    df["pre_pub_share"] = (df["pre_pub_neuro"] + df["pre_pub_ai"]) / (df["c_neuro"] + df["c_ai"])

    scores = {
        "orig": (df["B_harmonic"], (y >= 1990) & (y <= 2026)),
        "rate": (harmonic(df["r_neuro"].fillna(0), df["r_ai"].fillna(0)), y <= LAST_STABLE_YEAR),
        "win8": (harmonic(df["w8_neuro"], df["w8_ai"]), (y >= 1990) & (y <= 2015)),
        "orig_1990_2015": (df["B_harmonic"], (y >= 1990) & (y <= 2015)),
        "win7": (harmonic(df["w7_neuro"], df["w7_ai"]), (y >= 1990) & (y <= 2015)),
        "win5_to2018": (harmonic(df["w5_neuro"], df["w5_ai"]), (y >= 1990) & (y <= 2018)),
        "win8_share": (harmonic(df["s8_neuro"], df["s8_ai"]), (y >= 1990) & (y <= 2015)),
        "rate_share": (
            harmonic(
                (df["s23_neuro"] / df["years_to_2023"]).fillna(0),
                (df["s23_ai"] / df["years_to_2023"]).fillna(0),
            ),
            y <= LAST_STABLE_YEAR,
        ),
    }
    scores["rate_noceil"] = scores["rate"]
    scores["win8_noceil"] = scores["win8"]
    scores["rate_unknown"] = scores["rate"]

    # ------------------------------------------------------------------------ eligibility
    t_lo = df["title"].fillna("").str.lower().str.strip()
    base = (
        df["type"].isin(KEEP_TYPES)
        & ~df["source_type"].isin(BOOK_SOURCES)
        & (t_lo != "")
        & ~t_lo.apply(lambda t: any(t.startswith(kb) for kb in KNOWN_BOOK_TITLES))
    )
    field_ok = df["bridge_paper_field"].isin(["ai", "neuro"])
    field_ok_unknown = df["bridge_paper_field"].isin(["ai", "neuro", "unknown"])
    ceiling_ok = df["c_total_classified"] < CEILING
    elig = {
        name: base
        & (field_ok_unknown if name == "rate_unknown" else field_ok)
        & (ceiling_ok if "noceil" not in name else True)
        for name in scores
    }
    df["title_norm"] = norm_title(df["title"])

    # ---------------------------------------------------------------------------- ranking
    ranked = {}
    for name, (score, in_years) in scores.items():
        sub = df.loc[elig[name] & in_years].assign(score=score[elig[name] & in_years])
        sub = sub[sub["score"] > 0].sort_values("score", ascending=False, kind="mergesort")
        sub = sub.drop_duplicates(subset="title_norm", keep="first").reset_index(drop=True)
        sub["rank"] = np.arange(1, len(sub) + 1)
        ranked[name] = sub
        print(
            f"{name:16s} eligible={len(sub):6d}  top score={sub.score.iloc[0]:9.2f}  "
            f"score@100={sub.score.iloc[99]:8.2f}",
            flush=True,
        )

    # ------------------------------------------------ check B: reproduce Table S5.1 exactly
    ref = pd.read_csv(RESULTS / "table_s1_reference.csv")
    top15 = ranked["orig"].head(15)
    rows = []
    for (_, r), (_, t) in zip(ref.iterrows(), top15.iterrows(), strict=True):
        rows.append(
            {
                "rank": int(r["rank"]),
                "title_ok": clean_title(t["title"]).lower().startswith(r["title_prefix"]),
                "year_ok": int(t["publication_year"]) == int(r["year"]),
                "c_neuro_ok": int(t["c_neuro"]) == int(r["c_neuro"]),
                "c_ai_ok": int(t["c_ai"]) == int(r["c_ai"]),
                "B_ok": round(float(t["B_harmonic"])) == int(r["B"]),
                "got": f"{clean_title(t['title'])[:50]} ({t['publication_year']})",
            }
        )
    rep = pd.DataFrame(rows)
    all_ok = bool(rep[["title_ok", "year_ok", "c_neuro_ok", "c_ai_ok", "B_ok"]].all().all())
    check(
        "B_top15_reproduces_table_S1",
        all_ok,
        failures=rep[
            ~rep[["title_ok", "year_ok", "c_neuro_ok", "c_ai_ok", "B_ok"]].all(axis=1)
        ].to_dict("records"),
    )
    if not all_ok:
        sys.exit("Top-15 does not match Table S5.1; stopping as instructed.")

    # Also match the pipeline's own figure input (independent file) for ranks 1-15.
    nb = pd.read_parquet(POOL.parent / "q4_v3_extended_filtered_by_era_no_books.parquet")
    nb = nb.sort_values("B_harmonic", ascending=False).head(15)
    check(
        "B2_top15_matches_pipeline_no_books_parquet", list(nb["work_id"]) == list(top15["work_id"])
    )

    # -------------------- check C: the >=5-per-side admission gate cannot hide a top-100 work
    # A work outside the pool has <= 4 citations on some side in all years, hence <= 4 in any
    # window and a rate <= 4; its harmonic mean is then <= 2 * 4 = 8.
    for name in (
        "rate",
        "win8",
        "win7",
        "win5_to2018",
        "rate_noceil",
        "win8_noceil",
    ):  # counts only
        s100 = float(ranked[name]["score"].iloc[99])
        check(f"C_gate_nonbinding_top100_{name}", s100 > 8.0, score_at_rank100=round(s100, 2))

    # ------- check D: the E2 ceiling is on all-time counts; how many works it removes per head
    for name in ("rate", "win8"):
        nc = ranked[f"{name}_noceil"]
        removed = nc[nc["c_total_classified"] >= CEILING]
        check(
            f"D_ceiling_effect_{name}_top50_info",
            True,
            n_ceiling_works_in_noceil_top15=int((removed["rank"] <= 15).sum()),
            n_ceiling_works_in_noceil_top50=int((removed["rank"] <= 50).sum()),
        )

    # ------------- check E: does admitting 'unknown' own-field papers change the rate head?
    same = list(ranked["rate_unknown"].head(50)["work_id"]) == list(
        ranked["rate"].head(50)["work_id"]
    )
    check("E_unknown_field_does_not_change_rate_top50", same)

    # ---------------- info: citations dated before the cited work's own publication year
    pp = (df["pre_pub_neuro"] + df["pre_pub_ai"]).sum() / (df["c_neuro"] + df["c_ai"]).sum()
    checks["info_prepublication_citation_share"] = {"share": round(float(pp), 5)}

    # ------ scanner F: records in any ranked head with >10% of citations predating the record
    heads_f = {
        "orig": 100,
        "rate": 100,
        "win8": 100,
        "win8_share": 100,
        "rate_share": 50,
        "win7": 50,
        "win5_to2018": 50,
        "orig_1990_2015": 50,
    }
    flag = pd.concat([ranked[n].head(k).assign(ranking=n) for n, k in heads_f.items()])
    flag = flag[flag["pre_pub_share"] > 0.10].drop_duplicates("title_norm")
    checks["F_prepublication_citation_flags_top100"] = {
        "pass": True,
        "n_flagged": len(flag),
        "flagged": [
            f"{clean_title(r.title)[:60]} ({r.publication_year}): "
            f"{r.pre_pub_share:.0%} of citations predate the record"
            for r in flag.itertuples()
        ],
    }
    print(
        "[INFO] F flagged:",
        *checks["F_prepublication_citation_flags_top100"]["flagged"],
        sep="\n  ",
        flush=True,
    )

    # ------------------------------------------------------------------------------ write
    long = []
    for name, sub in ranked.items():
        long.append(sub[["work_id", "title_norm", "rank", "score"]].assign(ranking=name))
    long = pd.concat(long, ignore_index=True)
    work_cols = [
        "work_id",
        "doi",
        "title",
        "publication_year",
        "venue",
        "type",
        "bridge_paper_field",
        "c_neuro",
        "c_ai",
        "c_total_classified",
        "B_harmonic",
        "n23_neuro",
        "n23_ai",
        "r_neuro",
        "r_ai",
        "w8_neuro",
        "w8_ai",
        "w7_neuro",
        "w7_ai",
        "w5_neuro",
        "w5_ai",
        "pre_pub_share",
    ]
    long = long.merge(df[work_cols], on="work_id", how="left")
    long.to_parquet(WORK_DIR / "rankings.parquet", index=False, compression="zstd")

    # Committed copy of the heads: top 100 of every ranking, one CSV per ranking.
    for name in ranked:
        (
            long[long["ranking"] == name]
            .sort_values("rank")
            .head(TOP_N_CSV)
            .to_csv(RESULTS / f"ranking_{name}_top100.csv", index=False)
        )

    heads = {
        "orig": 100,
        "rate": 100,
        "win8": 100,
        "orig_1990_2015": 50,
        "win7": 50,
        "win5_to2018": 50,
        "rate_noceil": 25,
        "win8_noceil": 25,
        "rate_unknown": 25,
        "win8_share": 100,
        "rate_share": 50,
    }
    u = long[long.apply(lambda r: r["rank"] <= heads[r["ranking"]], axis=1)]
    u = u.sort_values("rank").drop_duplicates("title_norm")[
        [
            "title_norm",
            "work_id",
            "doi",
            "title",
            "publication_year",
            "venue",
            "bridge_paper_field",
            "c_neuro",
            "c_ai",
        ]
    ]
    u["title"] = u["title"].map(clean_title)
    u.sort_values("publication_year").to_csv(RESULTS / "to_classify.csv", index=False)
    print("works to classify:", len(u), flush=True)

    with open(RESULTS / "checks.json", "w") as fh:
        json.dump(checks, fh, indent=2, default=str)
    n_fail = sum(not v.get("pass", True) for v in checks.values())
    print("checks failed:", n_fail, flush=True)


if __name__ == "__main__":
    main()

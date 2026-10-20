"""Recompute the headline numbers from the committed CSVs only (no DuckDB) and compare.

Reads results/citation_age: ranking_<name>_top100.csv, classification.csv,
table_s1_reference.csv, checks.json and summary.json. Recomputes

    Table S1: the top 15 of the published ranking against the printed table
    the number of conceptual works in the top 15, 25 and 50 of every ranking
    the most recent conceptual work (and concept or method) per ranking and head size
    the publication-year table of the top 100 (median, IQR, bins, classes)
    where the published top 15 land in the other rankings (within the committed top 100)

and exits with status 1 if anything differs from the committed checks.json and summary.json,
or if any check recorded in checks.json is marked as failed.

Run:  python -m neuroai_cn.analysis.citation_age.verify
"""

import json
import re
import sys

import pandas as pd

from neuroai_cn.analysis.citation_age.paths import RESULTS

PRIMARY = ["orig", "rate", "win8"]
SENS = [
    "orig_1990_2015",
    "win7",
    "win5_to2018",
    "win8_share",
    "rate_share",
    "rate_noceil",
    "win8_noceil",
    "rate_unknown",
]
FIG = [*PRIMARY, "win8_share"]
BINS = [0, 1989, 1995, 2000, 2005, 2010, 2015, 2020, 2026]
BIN_LABELS = ["<1990", "1990-95", "1996-00", "2001-05", "2006-10", "2011-15", "2016-20", "2021-26"]

problems: list[str] = []


def expect(name: str, got, want) -> None:
    ok = got == want
    print(f"[{'OK' if ok else 'MISMATCH'}] {name}")
    if not ok:
        problems.append(f"{name}: recomputed {got!r} != committed {want!r}")


def roundtrip(obj):
    """Same serialisation as summary.json, so recomputed values compare like with like."""
    return json.loads(json.dumps(obj, default=str))


def clean_title(t: str) -> str:
    return re.sub(r"<[^>]+>", "", str(t)).strip()


def most_recent(g: pd.DataFrame, k: int, classes: tuple[str, ...] = ("concept",)) -> dict | None:
    h = g[(g["rank"] <= k) & g["cls"].isin(classes)]
    if h.empty:
        return None
    r = h.sort_values(["true_year", "rank"], ascending=[False, True]).iloc[0]
    return {"year": int(r["true_year"]), "rank": int(r["rank"]), "work": r["short"]}


def after2005(g: pd.DataFrame, k: int, cls: str = "concept") -> list[str]:
    h = g[(g["rank"] <= k) & (g["cls"] == cls) & (g["true_year"] > 2005)]
    return [f"{r.short} ({int(r.true_year)}, #{r.rank})" for r in h.itertuples()]


def recency_block(g: pd.DataFrame) -> dict:
    return {
        f"top{k}": {
            "most_recent_concept": most_recent(g, k),
            "most_recent_concept_or_method": most_recent(g, k, ("concept", "method")),
            "n_concepts": int(((g["rank"] <= k) & (g["cls"] == "concept")).sum()),
            "concepts_after_2005": after2005(g, k),
            "methods_after_2005": after2005(g, k, "method"),
        }
        for k in (15, 25, 50)
    }


def main() -> int:
    checks = json.loads((RESULTS / "checks.json").read_text())
    summary = json.loads((RESULTS / "summary.json").read_text())
    cl = pd.read_csv(RESULTS / "classification.csv", comment="#").rename(columns={"class": "cls"})
    ref = pd.read_csv(RESULTS / "table_s1_reference.csv")

    R = {}
    for name in [*PRIMARY, *SENS]:
        g = pd.read_csv(RESULTS / f"ranking_{name}_top100.csv")
        g = g.merge(cl[["title_norm", "cls", "true_year", "short"]], on="title_norm", how="left")
        R[name] = g.sort_values("rank").reset_index(drop=True)
        expect(
            f"{name}: committed CSV has ranks 1..100", list(R[name]["rank"]), list(range(1, 101))
        )

    for name, c in checks.items():
        if "pass" in c:
            expect(f"checks.json: {name} passes", bool(c["pass"]), True)

    # Table S1 reproduction from the committed top 15 of the published ranking.
    top15 = R["orig"].head(15)
    rows = []
    for (_, r), (_, t) in zip(ref.iterrows(), top15.iterrows(), strict=True):
        rows.append(
            clean_title(t["title"]).lower().startswith(r["title_prefix"])
            and int(t["publication_year"]) == int(r["year"])
            and int(t["c_neuro"]) == int(r["c_neuro"])
            and int(t["c_ai"]) == int(r["c_ai"])
            and round(float(t["B_harmonic"])) == int(r["B"])
        )
    expect("Table S1: all 15 rows reproduced", all(rows) and len(rows) == len(ref) == 15, True)

    # Concept counts and most recent concept per ranking.
    for name in [*PRIMARY, *SENS]:
        got = roundtrip(recency_block(R[name]))
        for top in ("top15", "top25", "top50"):
            expect(
                f"{name} {top}: number of concepts",
                got[top]["n_concepts"],
                summary[name][top]["n_concepts"],
            )
            expect(
                f"{name} {top}: most recent concept",
                got[top]["most_recent_concept"],
                summary[name][top]["most_recent_concept"],
            )
        expect(f"{name}: full recency block", got, summary[name])

    # Publication-year table of the top 100.
    dist = {}
    for name in FIG:
        g = R[name].head(100)
        yrs = g["true_year"]
        dist[name] = {
            "median_year": float(yrs.median()),
            "iqr": [float(yrs.quantile(0.25)), float(yrs.quantile(0.75))],
            "n_after_2005": int((yrs > 2005).sum()),
            "n_after_2010": int((yrs > 2010).sum()),
            "by_class": g["cls"].value_counts().to_dict(),
            "concepts_after_2005": int(((g["cls"] == "concept") & (yrs > 2005)).sum()),
            "bins": pd.cut(yrs, BINS, labels=BIN_LABELS).value_counts(sort=False).to_dict(),
        }
    expect("top-100 publication-year table", roundtrip(dist), summary["top100_year_distribution"])

    # Where the published top 15 land (ranks beyond the committed top 100 cannot be recomputed).
    for item in summary["published_top15_landing"]:
        w = top15[top15["short"] == item["work"]]
        expect(f"landing: {item['work']} is in the published top 15", len(w), 1)
        title_norm = w["title_norm"].iloc[0]
        for name in ("orig", "rate", "win8", "win8_share", "rate_share"):
            m = R[name][R[name]["title_norm"] == title_norm]
            want = item[name]
            if len(m):
                expect(f"landing: {item['work']} in {name}", int(m["rank"].iloc[0]), want)
            else:
                expect(
                    f"landing: {item['work']} in {name} (outside top 100 or ineligible)",
                    want is None or want > 100,
                    True,
                )

    if problems:
        print(f"\nFAILED: {len(problems)} difference(s)")
        for p in problems:
            print("  -", p)
        return 1
    print("\nAll recomputed numbers match checks.json and summary.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

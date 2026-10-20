"""The cited-vintage tables, pinned to the committed result files.

Integers are compared exactly and floats with rtol 1e-9, so editing any CSV under
``results/vintage`` makes a test fail. Every derived table is also recomputed from the committed
count matrix and compared with the committed file. The last test recomputes a slice from the DuckDB
mirror and is skipped unless ``NEUROAI_HEAVY=1`` (run ``pytest -m heavy``).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from neuroai_cn import config
from neuroai_cn.analysis.cited_vintage import reference_age as ra
from neuroai_cn.analysis.cited_vintage import robustness, vintage

RTOL = 1e-9
RES = config.RESULTS_DIR / "vintage"
COG = "https://openalex.org/subfields/2805"
CELL = "https://openalex.org/subfields/2804"


@pytest.fixture(scope="module")
def matrix():
    return vintage.load_matrix()


@pytest.fixture(scope="module")
def summary():
    return pd.read_csv(RES / "vintage_summary.csv")


def _same(got: pd.DataFrame, want: pd.DataFrame, skip=()):
    cols = [c for c in want.columns if c in got.columns and c not in skip]
    assert len(got) == len(want)
    for c in cols:
        a, b = got[c].reset_index(drop=True), want[c].reset_index(drop=True)
        if a.dtype.kind in "fc" or b.dtype.kind in "fc":
            np.testing.assert_allclose(a.astype(float), b.astype(float), rtol=RTOL, equal_nan=True)
        else:
            assert a.tolist() == b.tolist(), c


def test_matrix_checksums(matrix):
    assert matrix.shape == (30052, 9)
    assert int(matrix["n"].sum()) == 2063568
    assert matrix.groupby("direction")["n"].sum().to_dict() == {
        "ai_to_neuro": 885149,
        "neuro_to_ai": 1178419,
    }
    assert int((matrix["n"] * matrix["cited_year"]).sum()) == 4145308131
    assert int((matrix["n"] * matrix["citing_year"]).sum()) == 4163256986
    assert matrix.groupby("citing_ar")["n"].sum().to_dict() == {0: 511457, 1: 1552111}
    assert matrix.groupby("cited_dual")["n"].sum().to_dict() == {0: 1549931, 1: 513637}
    assert matrix.groupby("citing_strict")["n"].sum().to_dict() == {0: 1711475, 1: 352093}


def test_summary_is_a_function_of_the_matrix(matrix, summary):
    _same(vintage.summary_table(matrix), summary, skip=("n_cited_works",))


def test_subfield_and_by_year_are_functions_of_the_matrix(matrix):
    sub = pd.read_csv(RES / "subfield_breakdown.csv")
    _same(
        vintage.subfield_table(matrix).reset_index(drop=True),
        sub,
        skip=("n_cited_works", "share_works"),
    )
    _same(vintage.by_year_table(matrix), pd.read_csv(RES / "vintage_by_year.csv"))


# (direction, cited_set, classifier, period): edges, distinct works, median, mean age,
# edges published <= 2005, edges published <= 2004
HEADLINE = {
    ("ai_to_neuro", "exclusive", "extended", "2010-2019"): (224890, 75425, 2007.0, 9.241286851349548, 98391, 88272),
    ("ai_to_neuro", "exclusive", "extended", "2020-2025"): (315457, 117382, 2015.0, 10.067882468926037, 62654, 56191),
    ("ai_to_neuro", "exclusive", "extended", "2020-2023"): (179925, 73438, 2014.0, 10.114553286091429, 41500, 37296),
    ("ai_to_neuro", "unrestricted", "extended", "2010-2019"): (314843, 91616, 2007.0, 8.960389781573673, 133724, 119303),
    ("ai_to_neuro", "unrestricted", "extended", "2020-2025"): (444585, 143922, 2016.0, 9.29146957274762, 79888, 71439),
    ("ai_to_neuro", "unrestricted", "extended", "2020-2023"): (257000, 91599, 2015.0, 9.40811673151751, 53909, 48302),
    ("ai_to_neuro", "unrestricted", "strict35", "2010-2019"): (117363, 46779, 2008.0, 8.549057198606034, 46134, 41021),
    ("ai_to_neuro", "unrestricted", "strict35", "2020-2025"): (179242, 75933, 2015.0, 9.429168386873611, 30256, 26816),
    ("ai_to_neuro", "exclusive", "strict35", "2020-2025"): (139730, 63300, 2015.0, 9.917669791741217, 25105, 22211),
    ("neuro_to_ai", "exclusive", "extended", "2010-2019"): (312935, 75001, 2006.0, 9.79587454263665, 148817, 134143),
    ("neuro_to_ai", "exclusive", "extended", "2020-2025"): (481029, 131291, 2016.0, 9.034182970257511, 83939, 75912),
    ("neuro_to_ai", "unrestricted", "extended", "2020-2023"): (373926, 98739, 2015.0, 9.339703577713236, 76746, 69721),
}  # fmt: skip


@pytest.mark.parametrize("key", list(HEADLINE))
def test_headline_cells(summary, key):
    direction, cited_set, classifier, period = key
    r = summary[
        (summary["direction"] == direction)
        & (summary["cited_set"] == cited_set)
        & (summary["classifier"] == classifier)
        & (summary["citing_def"] == "all")
        & (summary["period"] == period)
    ].iloc[0]
    n, works, med, age, le05, le04 = HEADLINE[key]
    assert int(r["n_edges"]) == n
    assert int(r["n_cited_works"]) == works
    assert r["median_cited_year"] == med
    assert r["mean_age"] == pytest.approx(age, rel=RTOL)
    assert int(r["n_le2005"]) == le05
    assert int(r["n_le2004"]) == le04
    assert r["share_le2005"] == pytest.approx(le05 / n, rel=RTOL)


def test_claim2_replicates_only_with_the_35_topic_definition(summary):
    """A median of 2008 -> 2015 and a share of 35% -> 15% arise only with the 35-topic definition and a <= 2004 boundary."""

    def cell(cls, period):
        return summary[
            (summary["direction"] == "ai_to_neuro")
            & (summary["cited_set"] == "unrestricted")
            & (summary["classifier"] == cls)
            & (summary["citing_def"] == "all")
            & (summary["period"] == period)
        ].iloc[0]

    a, b = cell("strict35", "2010-2019"), cell("strict35", "2020-2025")
    assert (a["median_cited_year"], b["median_cited_year"]) == (2008.0, 2015.0)
    assert round(100 * a["share_le2004"], 1) == 35.0
    assert round(100 * b["share_le2004"], 1) == 15.0
    # the same definition at the boundary the article text states (2005 or earlier)
    assert round(100 * a["share_le2005"], 1) == 39.3
    assert round(100 * b["share_le2005"], 1) == 16.9
    # the extended definition, exclusive cited set: higher old shares
    c, d = cell("extended", "2010-2019"), cell("extended", "2020-2025")
    assert (c["median_cited_year"], d["median_cited_year"]) == (2007.0, 2016.0)


def test_claim1_subfield_shares():
    sb = pd.read_csv(RES / "subfield_breakdown.csv")
    sb = sb[
        (sb["direction"] == "ai_to_neuro")
        & (sb["citing_def"] == "all")
        & (sb["period"] == "2020-2025")
    ]

    def share(classifier, cited_set, sf):
        r = sb[
            (sb["classifier"] == classifier)
            & (sb["cited_set"] == cited_set)
            & (sb["cited_sf_id"] == sf)
        ].iloc[0]
        return int(r["n_edges"]), float(r["share_edges"])

    assert share("extended", "exclusive", COG)[0] == 260868
    assert share("extended", "exclusive", CELL)[0] == 31406
    assert share("extended", "unrestricted", COG)[0] == 346538
    assert share("extended", "unrestricted", CELL)[0] == 37580
    assert share("strict35", "exclusive", COG)[0] == 126193
    assert share("strict35", "exclusive", CELL)[0] == 6957
    assert share("extended", "exclusive", COG)[1] == pytest.approx(260868 / 315457, rel=RTOL)
    # shares over the eight subfields sum to one in every cell
    sums = sb.groupby(["classifier", "cited_set"])["share_edges"].sum()
    np.testing.assert_allclose(sums.to_numpy(), 1.0, rtol=RTOL)
    # the claim "about 90 percent and under 5 percent" is not met by the extended definition
    cog, cell_ = share("extended", "exclusive", COG)[1], share("extended", "exclusive", CELL)[1]
    assert cog < 0.85 and cell_ > 0.09


def test_claims_json_matches_tables(summary):
    claims = json.loads((RES / "claims.json").read_text())
    c2 = claims["claim2"]["extended_exclusive"]["2020-2025"]
    assert c2["n_edges"] == 315457
    assert c2["median_cited_year"] == 2015.0
    assert c2["share_le2005"] == pytest.approx(62654 / 315457, rel=RTOL)
    assert claims["claim1"]["extended_exclusive_2020-2025"][
        "cognitive_neuroscience_share"
    ] == pytest.approx(260868 / 315457, rel=RTOL)


# ---- robustness -----------------------------------------------------------------------------


def test_robustness_table_and_verdict():
    r = pd.read_csv(RES / "robustness.csv")
    assert r.shape == (24, 13)
    assert int(r["fails"].sum()) == 12
    base = r[r["stage"] == "baseline"]
    assert not base["fails"].any()
    last = r[r["stage"] == "regex_plus_clear_plus_borderline"].set_index(["cited_set", "period"])
    assert last.loc[("exclusive", "2020-2025"), "n_edges"] == 278082
    assert last.loc[("unrestricted", "2020-2025"), "n_edges"] == 369782
    assert last.loc[("exclusive", "2020-2025"), "median_cited_year"] == 2014.0
    assert last.loc[("exclusive", "2020-2025"), "share_le2005"] == pytest.approx(0.22087, abs=5e-6)
    assert last.loc[("unrestricted", "2020-2025"), "d_cognitive_share_pp"] > 2.0
    assert last.loc[("exclusive", "2010-2019"), "d_median_years"] == -1.0
    # the between-period shift survives every stage
    s = pd.read_csv(RES / "robustness_shift.csv")
    ex = s[(s["cited_set"] == "exclusive") & (s["comparison"] == "2010-2019 -> 2020-2025")]
    assert ex["median_shift_years"].tolist() == [8.0, 8.0, 8.0, 8.0]
    assert ex["share_le2005_change_pp"].between(-24.0, -23.0).all()


def test_robustness_is_a_function_of_the_committed_removals():
    r = pd.read_csv(RES / "robustness.csv")
    _same(robustness.shift_table(r), pd.read_csv(RES / "robustness_shift.csv"))
    rem = pd.read_csv(RES / "removed_works.csv")
    assert len(rem) == 13946 and rem["id"].is_unique
    assert rem["rule"].str.startswith("manual").sum() == len(robustness.MANUAL_REMOVALS) == 21
    assert int(rem["n_2020-2025"].sum()) == 74803
    assert int(rem["n_2010-2019"].sum()) == 29598
    assert set(robustness.MANUAL_REMOVALS) <= set(rem["id"])
    top = rem.sort_values("n_2020-2025", ascending=False).iloc[0]
    assert top["title"] == "Human-level control through deep reinforcement learning"
    assert int(top["n_2020-2025"]) == 7795


# ---- reference age --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def refmatrix():
    return pd.read_csv(RES / "matrix_reference_age.csv")


def test_reference_age_matrix_checksums(refmatrix):
    assert refmatrix.shape == (11362, 6)
    assert int(refmatrix["n"].sum()) == 120257559
    assert refmatrix.groupby("citing_cls")["n"].sum().to_dict() == {
        "ai": 50055273,
        "neuro": 70202286,
    }
    assert refmatrix.groupby("cited_cls")["n"].sum().to_dict() == {
        "ai": 31840936,
        "neuro": 40657976,
        "other": 47758647,
    }
    assert int((refmatrix["n"] * refmatrix["cited_year"]).sum()) == 241586287138


def test_reference_age_tables_are_functions_of_the_matrix(refmatrix):
    _same(ra.by_year_table(refmatrix), pd.read_csv(RES / "reference_age_by_field.csv"))
    _same(ra.pooled_table(refmatrix), pd.read_csv(RES / "reference_age_pooled.csv"))


def test_reference_age_pooled_values():
    p = pd.read_csv(RES / "reference_age_pooled.csv")
    p = p[(p["types"] == "article_review") & (p["scope"] == "all_references")]
    p = p.set_index(["citing_field", "period"])
    ai, ne = p.loc[("ai", "2020-2023")], p.loc[("neuro", "2020-2023")]
    assert (ai["median_age"], ne["median_age"]) == (4.0, 8.0)
    assert (ai["p90_age"], ne["p90_age"]) == (16, 21)
    assert ai["share_le5"] == pytest.approx(0.585, abs=5e-4)
    assert ne["share_le5"] == pytest.approx(0.362, abs=5e-4)
    assert ai["mean_age"] == pytest.approx(6.638, abs=5e-4)
    assert int(ai["n_refs"]) == 12173300
    assert int(ne["n_refs"]) == 14320543


def test_reference_list_coverage():
    c = pd.read_csv(RES / "reference_list_coverage.csv")
    assert c.shape == (104, 12)
    r = c[(c["types"] == "all") & (c["citing_year"] == 2023)].set_index("citing_field")
    assert int(r.loc["ai", "n_works"]) == 346525
    assert int(r.loc["ai", "n_with_reflist"]) == 159354
    assert int(r.loc["ai", "n_refs_listed"]) == 5491223
    assert int(r.loc["ai", "n_refs_dated"]) == 4416232
    assert int(r.loc["neuro", "n_works"]) == 164016
    assert int(r.loc["neuro", "n_refs_dated"]) == 4647565
    # edges in the mirror are exactly the listed references
    assert (c["n_edges"] == c["n_refs_listed"]).all()


# ---- heavy: recompute a slice from the mirror -------------------------------------------------

YEAR = 2003


@pytest.mark.heavy
@pytest.mark.skipif(os.environ.get("NEUROAI_HEAVY") != "1", reason="set NEUROAI_HEAVY=1")
def test_recompute_slice_matches_committed_matrix(tmp_path):
    """Re-run labels, edges and cross for citing year 2003 (works up to 2003) and compare."""
    base = [sys.executable, "-m", "neuroai_cn.analysis.cited_vintage.build"]
    for stage in ("labels", "edges", "cross"):
        subprocess.run(
            [*base, "--stage", stage, "--years", str(YEAR), str(YEAR), "--out", str(tmp_path)],
            check=True,
        )
    got = vintage.build_matrix(pd.read_parquet(tmp_path / "cross_edges.parquet"))
    committed = vintage.load_matrix()
    want = committed[(committed["citing_year"] == YEAR) & (committed["cited_year"] <= YEAR)]
    pd.testing.assert_frame_equal(
        got.reset_index(drop=True),
        want.sort_values(vintage.KEYS).reset_index(drop=True),
        check_dtype=False,
    )

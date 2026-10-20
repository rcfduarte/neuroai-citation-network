"""The citation-flow numbers quoted in the supplements, pinned to the committed CSVs.

The literals below were read from the data bundles of Figures 1 and 2 of 2026-10-06
(``article-fig1-v3-20261006/`` and ``figure2-raw-20261006/``), not from the repository files, so editing
``results/flow/*.csv`` makes these tests fail. Integers are compared exactly, floats with rtol 1e-9.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from neuroai_cn.analysis import flow_numbers as fn

RTOL = 1e-9


@pytest.fixture(scope="module")
def df():
    return fn.load()


def test_table_shape_and_integer_totals(df):
    # whole-table checksums: any edited count changes one of these
    assert df.shape == (72, 20)
    ints = df.groupby("direction")[["n_to_within", "n_to_target", "n_to_other"]].sum()
    assert ints.loc["neuro_to_ai"].tolist() == [41830025, 1188383, 30596258]
    assert ints.loc["ai_to_neuro"].tolist() == [31242179, 890784, 18838593]
    n = df.pivot(index="year", columns="direction", values="n_works_source")
    assert int(n["neuro_to_ai"].sum()) == 3552562
    assert int(n["ai_to_neuro"].sum()) == 5480569
    # sum of the yearly odds ratios per direction (floats)
    s = df.groupby("direction")["or_restricted"].sum()
    assert s["neuro_to_ai"] == pytest.approx(0.7192495666689908, rel=RTOL)
    assert s["ai_to_neuro"] == pytest.approx(1.5022124618160142, rel=RTOL)


def test_field_sizes(df):
    s = fn.field_sizes((1995, 2025), df)
    assert s[1995]["neuroscience"] == 42049
    assert s[1995]["ai"] == 35135
    assert s[2025]["neuroscience"] == 287415
    assert s[2025]["ai"] == 586892
    assert s[1995]["ratio_ai_to_neuro"] == pytest.approx(0.8355727841327975, rel=RTOL)
    assert s[2025]["ratio_ai_to_neuro"] == pytest.approx(2.041967190299741, rel=RTOL)


def test_size_ratio_by_year(df):
    r = fn.size_ratio_by_year(df)
    assert r.loc[1990] == pytest.approx(0.6724137931034483, rel=RTOL)
    assert r.loc[1995] == pytest.approx(0.8355727841327975, rel=RTOL)
    assert r.loc[2025] == pytest.approx(2.041967190299741, rel=RTOL)
    assert int(r.index[r > 1].min()) == 2001  # first year AI has more works than neuroscience
    assert (r.loc[2001:] > 1).all()


def test_cross_field_citations(df):
    c = fn.cross_field_citations_per_year(df)
    assert c.loc[2023].tolist() == [103054, 72841]
    assert int(c["neuro_to_ai"].sum()) == 1188383
    assert int(c["ai_to_neuro"].sum()) == 890784


def test_count_dominance_every_year(df):
    d = fn.count_dominance(df)
    # neuroscience-citing-AI exceeds AI-citing-neuroscience in the raw COUNT in every year, 1990-2025
    assert d["neuro_exceeds_ai_every_year"] is True
    assert d["years_where_not"] == []
    assert d["n_years"] == 36
    assert d["min_ratio"] == pytest.approx(1.1530191685081452, rel=RTOL)
    assert d["max_ratio"] == pytest.approx(2.5029126213592234, rel=RTOL)


def test_cross_refs_per_1000_figure2_definition(df):
    # own + other + third-field references in the denominator, as in Figure 2B (bundle values)
    p = fn.cross_refs_per_1000(df)
    assert p.loc[2017, "neuro_to_ai"] == pytest.approx(15.233433998529799, rel=RTOL)
    assert p.loc[2017, "ai_to_neuro"] == pytest.approx(17.77571675028027, rel=RTOL)
    assert p.loc[2018, "neuro_to_ai"] == pytest.approx(16.711702647110975, rel=RTOL)
    assert p.loc[2018, "ai_to_neuro"] == pytest.approx(16.33551220722557, rel=RTOL)
    assert p.loc[2023, "neuro_to_ai"] == pytest.approx(22.192618855650423, rel=RTOL)
    assert p.loc[2023, "ai_to_neuro"] == pytest.approx(16.514507355701827, rel=RTOL)


def test_cross_refs_per_1000_companion_definition(df):
    # unknown-field references also in the denominator (rho_population x 1000, companion table)
    p = fn.cross_refs_per_1000(df, include_unknown=True)
    assert p.loc[2017, "neuro_to_ai"] == pytest.approx(15.223904615097902, rel=RTOL)
    assert p.loc[2017, "ai_to_neuro"] == pytest.approx(17.758635947963068, rel=RTOL)
    assert p.loc[2018, "neuro_to_ai"] == pytest.approx(16.701944256924854, rel=RTOL)
    assert p.loc[2018, "ai_to_neuro"] == pytest.approx(16.32028729822483, rel=RTOL)
    assert p.loc[2023, "neuro_to_ai"] == pytest.approx(22.174587381481913, rel=RTOL)
    assert p.loc[2023, "ai_to_neuro"] == pytest.approx(16.494795401901133, rel=RTOL)


def test_share_lines_cross(df):
    y = fn.share_crossing(df, smoothed=False)
    assert y["last_year_ai_citing_neuroscience_higher"] == 2017
    assert y["first_year_neuro_citing_ai_higher_for_good"] == 2018
    assert 2017 < y["crossing_year_interpolated"] < 2018
    m = fn.share_crossing(df, smoothed=True)  # the thick (5-year mean) lines
    assert m["last_year_ai_citing_neuroscience_higher"] == 2018
    assert m["first_year_neuro_citing_ai_higher_for_good"] == 2019
    for sm in (False, True):  # same years with the companion-table denominator
        a, b = fn.share_crossing(df, sm), fn.share_crossing(df, sm, include_unknown=True)
        assert (
            a["first_year_neuro_citing_ai_higher_for_good"]
            == b["first_year_neuro_citing_ai_higher_for_good"]
        )


def test_smoothed_share_matches_figure2_bundle(flow_dir, df):
    t = pd.read_csv(flow_dir / "figure2_raw_v2_data.csv")
    t = t.set_index(["line_in_figure", "year"])
    p = fn.cross_refs_per_1000(df)
    m = p.apply(fn.centred_mean5)
    got = t.loc[("AI papers citing neuroscience", 2018), "B_per_1000_5yr_centred_mean_PLOTTED"]
    assert m.loc[2018, "ai_to_neuro"] == pytest.approx(got, rel=RTOL)
    assert got == pytest.approx(16.76129, rel=1e-6)


@pytest.mark.parametrize(
    ("direction", "values"),
    [
        (
            "neuro_to_ai",
            {
                1995: 0.023171472229978063,
                2006: 0.010486782829408153,
                2019: 0.02009347645732598,
                2023: 0.01954431546742351,
            },
        ),
        (
            "ai_to_neuro",
            {
                1995: 0.028967506173935814,
                2006: 0.049573233778229635,
                2019: 0.041459546660135134,
                2023: 0.05440099126741032,
            },
        ),
    ],
)
def test_odds_ratio_at_years(df, direction, values):
    o = fn.odds_ratio_at((1995, 2006, 2019, 2023), df)
    for year, v in values.items():
        assert o.loc[year, direction] == pytest.approx(v, rel=RTOL)


def test_odds_ratio_growth(df):
    g = fn.odds_ratio_growth(1995, 2023, df)
    assert g["neuro_to_ai"] == pytest.approx(0.01954431546742351 / 0.023171472229978063, rel=RTOL)
    assert g["ai_to_neuro"] == pytest.approx(0.05440099126741032 / 0.028967506173935814, rel=RTOL)
    assert g["neuro_to_ai"] < 1 < g["ai_to_neuro"]


EXPECTED_ERA_SLOPES = {
    ("ai_to_neuro", "Pre-DL"): 0.001166042489079925,
    ("ai_to_neuro", "DL emergence"): -0.0011262227428190546,
    ("ai_to_neuro", "DL expansion"): 0.000645010553404337,
    ("ai_to_neuro", "NeuroAI era"): 0.004929303742652347,
    ("neuro_to_ai", "Pre-DL"): -0.0005908229617586989,
    ("neuro_to_ai", "DL emergence"): 0.0008138470741212795,
    ("neuro_to_ai", "DL expansion"): 0.000843222797868089,
    ("neuro_to_ai", "NeuroAI era"): -0.0002493900777216007,
}


def test_era_slopes(df):
    e = fn.era_slopes(df).set_index(["direction", "era"])
    assert len(e) == 8
    for key, v in EXPECTED_ERA_SLOPES.items():
        assert e.loc[key, "slope_per_year"] == pytest.approx(v, rel=1e-9)
    assert e.loc[("ai_to_neuro", "NeuroAI era"), "n_years"] == 4
    assert e.loc[("ai_to_neuro", "Pre-DL"), "year_start"] == 1995


def test_era_slopes_agree_with_figure_bundle(flow_dir, df):
    b = pd.read_csv(flow_dir / "fig1B_era_slopes.csv").set_index(["direction", "era"])
    e = fn.era_slopes(df).set_index(["direction", "era"])
    assert np.allclose(b["slope"], e.loc[b.index, "slope_per_year"], rtol=1e-9, atol=0)

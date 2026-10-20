"""Change points: the figure's piecewise-OLS search and the old "PELT" numbers.

The article's turning points (first year of the new segment) are 2002 and 2006 for neuroscience papers
citing AI and 2006 and 2020 for AI papers citing neuroscience. The numbers the methods note calls PELT
(1993 and 2005; 2005 and 2022) are what the exhaustive piecewise-OLS search returns on 1990-2025 with
segments of at least 3 years, not what the ``ruptures`` PELT returns.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from neuroai_cn.analysis import changepoints as cp


@pytest.fixture(scope="module")
def tables():
    return cp.run_all(cp.load_or_by_year())


def _first_years(cps, procedure, setting_prefix, direction, series="or_restricted", window=None):
    m = (
        (cps.procedure == procedure)
        & cps.setting.str.startswith(setting_prefix)
        & (cps.direction == direction)
        & (cps.series == series)
    )
    if window:
        m &= cps.window == window
    return [int(v) for v in cps.loc[m, "breakpoint_year_first_of_new_segment"].dropna()]


def test_figure_ols_breakpoints(tables):
    cps, _ = tables
    args = ("piecewise-OLS exhaustive", "figure")
    assert _first_years(cps, *args, "neuro_to_ai") == [2002, 2006]
    assert _first_years(cps, *args, "ai_to_neuro") == [2006, 2020]


def test_figure_ols_last_of_old_convention(tables):
    cps, _ = tables
    m = (cps.procedure == "piecewise-OLS exhaustive") & cps.setting.str.startswith("figure")
    d = cps[m]
    diff = (
        d["breakpoint_year_first_of_new_segment"] - d["breakpoint_year_last_of_old_segment"]
    ).astype(int)
    assert (diff == 1).all()


def test_audit_ols_reproduces_the_numbers_called_pelt(tables):
    cps, _ = tables
    args = ("piecewise-OLS exhaustive", "audit")
    assert _first_years(cps, *args, "neuro_to_ai") == [1993, 2005]
    assert _first_years(cps, *args, "ai_to_neuro") == [2005, 2022]


def test_ruptures_pelt_does_not_return_the_old_numbers(tables):
    cps, _ = tables
    for win in ("1990-2025", "1995-2023"):
        for d, old in (("neuro_to_ai", [1993, 2005]), ("ai_to_neuro", [2005, 2022])):
            m = (
                (cps.procedure == "PELT (ruptures)")
                & (cps.direction == d)
                & (cps.window == win)
                & (cps.series == "or_restricted")
                & cps.declared_in_advance
            )
            for setting, sub in cps[m].groupby("setting"):
                got = [int(v) for v in sub["breakpoint_year_first_of_new_segment"].dropna()]
                assert got != old, (win, d, setting)


def test_pelt_declared_headline_values(tables):
    cps, _ = tables
    b = cps[
        (cps.procedure == "PELT (ruptures)")
        & cps.setting.str.contains(", BIC (", regex=False)
        & (cps.series == "or_restricted")
        & cps.declared_in_advance
    ]
    res = {
        (r.direction, r.window): sorted(
            b[(b.direction == r.direction) & (b.window == r.window)][
                "breakpoint_year_first_of_new_segment"
            ]
            .dropna()
            .astype(int)
            .tolist()
        )
        for r in b.itertuples()
    }
    assert res[("neuro_to_ai", "1990-2025")] == [1993]
    assert res[("ai_to_neuro", "1990-2025")] == [2001, 2023]
    assert res[("neuro_to_ai", "1995-2023")] == [2000, 2015]
    assert res[("ai_to_neuro", "1995-2023")] == [2001]


def test_segment_slopes_match_figure_bundle(flow_dir, tables):
    _, sl = tables
    fig = pd.read_csv(flow_dir / "figure1_article_panelC.csv")
    s = sl[
        (sl.procedure == "piecewise-OLS exhaustive")
        & sl.setting.str.startswith("figure")
        & (sl.series == "or_restricted")
    ]
    for d in ("neuro_to_ai", "ai_to_neuro"):
        a = fig[fig.direction == d].sort_values("segment_index")
        b = s[s.direction == d].sort_values("segment_index")
        assert a.year_start.tolist() == b.year_start.tolist()
        assert a.year_end.tolist() == b.year_end.tolist()
        assert np.allclose(a.slope, b.slope_per_year, rtol=1e-9, atol=0)


def test_committed_csv_equal_to_recomputation(flow_dir, tables):
    cps, sl = tables
    got_cp = pd.read_csv(flow_dir / "changepoints.csv")
    got_sl = pd.read_csv(flow_dir / "segment_slopes.csv")
    pd.testing.assert_frame_equal(
        got_cp, pd.read_csv(pd.io.common.StringIO(cps.to_csv(index=False))), check_exact=False
    )
    pd.testing.assert_frame_equal(
        got_sl, pd.read_csv(pd.io.common.StringIO(sl.to_csv(index=False))), check_exact=False
    )

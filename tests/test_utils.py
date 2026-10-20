"""Known-value tests for the two small statistics helpers in figures.cross_source."""

from __future__ import annotations

import math

import numpy as np
import pytest

from neuroai_cn.figures.cross_source import rolling_mean, wilson_ci


@pytest.mark.parametrize(
    ("k", "n", "lo", "hi"),
    [
        (50, 100, 0.403830, 0.596170),
        (0, 10, 0.0, 0.277540),
        (10, 10, 0.722460, 1.0),
        (5, 20, 0.111860, 0.468705),
    ],
)
def test_wilson_ci_known_values(k, n, lo, hi):
    got_lo, got_hi = wilson_ci(k, n)
    assert got_lo == pytest.approx(lo, abs=1e-6)
    assert got_hi == pytest.approx(hi, abs=1e-6)


def test_wilson_ci_empty_sample_is_zero_interval():
    assert wilson_ci(0, 0) == (0.0, 0.0)


def test_wilson_ci_is_inside_unit_interval_and_brackets_the_proportion():
    for n in (1, 3, 25, 400):
        for k in range(n + 1):
            lo, hi = wilson_ci(k, n)
            assert 0.0 <= lo <= k / n <= hi <= 1.0


def test_wilson_ci_narrows_with_sample_size():
    lo_s, hi_s = wilson_ci(10, 20)
    lo_l, hi_l = wilson_ci(500, 1000)
    assert (hi_l - lo_l) < (hi_s - lo_s)


def test_wilson_ci_z_scales_the_width():
    lo95, hi95 = wilson_ci(30, 100, z=1.96)
    lo99, hi99 = wilson_ci(30, 100, z=2.576)
    assert (hi99 - lo99) > (hi95 - lo95)


def test_rolling_mean_default_window_keeps_edges_with_three_points():
    y = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    np.testing.assert_allclose(rolling_mean(y), [2.0, 2.5, 3.0, 3.5, 4.0])


def test_rolling_mean_window_three_is_nan_where_it_does_not_fit():
    y = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    got = rolling_mean(y, window=3)
    assert math.isnan(got[0]) and math.isnan(got[-1])
    np.testing.assert_allclose(got[1:-1], [2.0, 3.0, 4.0])


def test_rolling_mean_of_constant_series_is_constant():
    got = rolling_mean(np.full(9, 7.0), window=5)
    np.testing.assert_allclose(got, 7.0)


def test_rolling_mean_too_short_series_is_all_nan():
    assert np.isnan(rolling_mean(np.array([1.0, 2.0]))).all()

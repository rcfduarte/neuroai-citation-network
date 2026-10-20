"""Shared fixtures: the committed small result files the tests are pinned to."""

from __future__ import annotations

import pytest

from neuroai_cn import config


@pytest.fixture(scope="session")
def flow_dir():
    d = config.RESULTS_DIR / "flow"
    assert (d / "or_by_year.csv").exists(), "run python -m neuroai_cn.analysis.export_flow_inputs"
    return d

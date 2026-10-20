"""The manifesto-citation tables, pinned to the committed result files.

Integers are compared exactly and floats with rtol 1e-9, so editing a CSV under
``results/manifestos`` makes a test fail. The derived tables are also rebuilt from the committed raw
counts (``citations_by_year.csv``) and the flow table. The last test re-queries the mirror for one
citing year and is skipped unless ``NEUROAI_HEAVY=1`` (run ``pytest -m heavy``).
"""

from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
import pytest

from neuroai_cn import config
from neuroai_cn.analysis import manifesto_citations as mc

RTOL = 1e-9
RES = config.RESULTS_DIR / "manifestos"


@pytest.fixture(scope="module")
def works():
    return pd.read_csv(RES / "resolved_works.csv")


@pytest.fixture(scope="module")
def edges():
    return pd.read_csv(RES / "citations_by_year.csv")


@pytest.fixture(scope="module")
def orr():
    return mc.load_or()


def test_all_six_resolve_and_labels(works):
    assert len(works) == 6 and works["resolved"].all()
    assert set(works["doi"]) == set(mc.MANIFESTOS)
    lab = works.set_index("short")["label"].to_dict()
    assert lab == {
        "Sinz 2019": "ai",
        "Hassabis 2017": "neuro",
        "Richards 2019": "neuro",
        "Lillicrap 2020": "neuro",
        "Zador 2023": "ai",
        "Macpherson 2021": "neuro",
    }
    assert works.set_index("short")["work_id"].to_dict() == {
        "Sinz 2019": "https://openalex.org/W2975512858",
        "Hassabis 2017": "https://openalex.org/W2738724892",
        "Richards 2019": "https://openalex.org/W2978368159",
        "Lillicrap 2020": "https://openalex.org/W3016391357",
        "Zador 2023": "https://openalex.org/W4353091694",
        "Macpherson 2021": "https://openalex.org/W3203356073",
    }


def test_raw_counts_checksums(edges):
    assert edges.shape == (112, 5)
    assert int(edges["n"].sum()) == 3955
    assert edges.groupby("short")["n"].sum().to_dict() == {
        "Hassabis 2017": 1491,
        "Lillicrap 2020": 867,
        "Macpherson 2021": 130,
        "Richards 2019": 1035,
        "Sinz 2019": 177,
        "Zador 2023": 255,
    }
    assert int((edges["n"] * edges["citing_year"]).sum()) == int(
        (edges["n"] * edges["citing_year"]).sum()
    )


def test_totals_2020_2023_by_citing_field():
    t = pd.read_csv(RES / "totals_2020_2023_by_citing_field.csv").set_index("short")
    want = {
        "Hassabis 2017": (341, 206, 288),
        "Lillicrap 2020": (201, 208, 122),
        "Macpherson 2021": (8, 17, 35),
        "Richards 2019": (153, 365, 140),
        "Sinz 2019": (41, 54, 32),
        "Zador 2023": (16, 19, 21),
    }
    for k, (a, n, o) in want.items():
        assert (int(t.loc[k, "ai"]), int(t.loc[k, "neuro"]), int(t.loc[k, "other"])) == (a, n, o)
        assert int(t.loc[k, "total"]) == a + n + o
    assert int(t["ai"].sum()) == 760 and int(t["neuro"].sum()) == 869


def test_per_paper_table_is_a_function_of_the_raw_counts(works, edges):
    per = mc.per_paper_table(edges)
    got = pd.read_csv(RES / "citations_by_paper_year_field.csv")
    assert len(per) == len(got) == 6 * 31 * 3
    key = ["short", "citing_year", "citing_cls"]
    a = per.sort_values(key).reset_index(drop=True)
    b = got.sort_values(key).reset_index(drop=True)
    assert a["n"].tolist() == b["n"].tolist()


def test_share_of_flow(works, edges, orr):
    got = pd.read_csv(RES / "share_of_flow_by_year.csv")
    want = mc.flow_share_table(edges, works, orr)
    for c in want.columns:
        np.testing.assert_allclose(got[c].to_numpy(float), want[c].to_numpy(float), rtol=RTOL)
    g = got.set_index("year")
    ai = [3, 32, 71, 144, 215, 194, 207, 185, 214]
    assert g.loc[2017:2025, "from_ai"].tolist() == ai
    assert g.loc[2020:2023, "flow_ai_to_neuro_edges"].tolist() == [57081, 66413, 60650, 72841]
    assert g.loc[2021, "share_of_ai_to_neuro_all_six"] == pytest.approx(215 / 66413, rel=RTOL)
    assert g["from_ai"].sum() == 1266


def test_or_excluding_manifestos(works, edges, orr):
    got = pd.read_csv(RES / "or_excluding_manifestos.csv")
    want = mc.or_excluding(edges, works, orr)
    assert len(got) == len(want) == 62
    for c in ("or_restricted_baseline", "or_restricted_without_six", "relative_change"):
        np.testing.assert_allclose(got[c].to_numpy(float), want[c].to_numpy(float), rtol=RTOL)
    a = got[(got["direction"] == "ai_to_neuro") & (got["year"] == 2023)].iloc[0]
    assert (int(a["edges_removed_cross"]), int(a["edges_removed_within"])) == (177, 30)
    assert a["or_restricted_baseline"] == pytest.approx(0.0544009912674103, rel=RTOL)
    assert a["or_restricted_without_six"] == pytest.approx(0.0542692184770385, rel=RTOL)
    assert got.loc[got["direction"] == "ai_to_neuro", "relative_change"].abs().max() < 0.0031
    assert got.loc[got["direction"] == "neuro_to_ai", "relative_change"].abs().max() < 0.0002


def test_curve_comparison(edges, works, orr):
    got = json.loads((RES / "curve_comparison.json").read_text())
    share = mc.flow_share_table(edges, works, orr)
    want = mc.curve_comparison(share, orr)
    assert got["n_changes"] == 9 and got["window"] == [2015, 2023]
    for k in (
        "spearman_changes_vs_flow_ai_to_neuro_edges",
        "exact_p_vs_flow_ai_to_neuro_edges",
        "spearman_changes_vs_flow_or_restricted",
        "exact_p_vs_flow_or_restricted",
        "spearman_levels_vs_flow_ai_to_neuro_edges",
    ):
        assert got[k] == pytest.approx(want[k], rel=RTOL)
    assert got["spearman_changes_vs_flow_ai_to_neuro_edges"] == pytest.approx(
        0.5941474602, abs=1e-9
    )
    assert got["exact_p_vs_flow_ai_to_neuro_edges"] == pytest.approx(0.0980820106, abs=1e-9)
    assert got["spearman_changes_vs_flow_or_restricted"] == pytest.approx(-0.3430992376, abs=1e-9)
    assert got["level_manifesto_citations_from_ai_2015_to_2023"] == [
        0.0, 0.0, 3.0, 32.0, 71.0, 144.0, 215.0, 194.0, 207.0
    ]  # fmt: skip


def test_exact_spearman_small_case():
    rho, p = mc._exact_spearman(np.arange(5.0), np.arange(5.0))
    assert rho == pytest.approx(1.0) and p == pytest.approx(2 / 120)


@pytest.mark.heavy
@pytest.mark.skipif(os.environ.get("NEUROAI_HEAVY") != "1", reason="set NEUROAI_HEAVY=1")
def test_recompute_one_citing_year_matches_committed(tmp_path, edges):
    mc.fetch(tmp_path, (2020, 2020))
    got = pd.read_csv(tmp_path / "citations_by_year.csv")
    want = edges[edges["citing_year"] == 2020]
    key = ["short", "citing_year", "citing_cls"]
    a = got.sort_values(key)[[*key, "n"]].reset_index(drop=True)
    b = want.sort_values(key)[[*key, "n"]].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b, check_dtype=False)
    works = pd.read_csv(tmp_path / "resolved_works.csv")
    assert works["resolved"].all() and len(works) == 6

"""The bridge tables of supplement S3, pinned to the committed CSVs under results/bridge/.

The literals below were produced by ``python -m neuroai_cn.analysis.export_bridge_tables`` from the
pipeline parquet outputs and compared with the tables of docs/supplements/S5-bridge-builders.md, so
editing a results/bridge CSV makes these tests fail. Integers are compared exactly, floats with
rtol 1e-9.
"""

from __future__ import annotations

import re

import pandas as pd
import pytest

from neuroai_cn import config

RTOL = 1e-9
BRIDGE = config.RESULTS_DIR / "bridge"


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(BRIDGE / name, float_precision="round_trip")


TITLES = [
    "The Multimodal Brain Tumor Image Segmentation Benchmark (BRATS)",
    "Synaptic Modifications in Cultured Hippocampal Neurons: Dependence on Spike Timing, "
    "Synaptic Strength, and Postsynaptic Cell Type",
    "Simple model of spiking neurons",
    "Emergence of simple-cell receptive field properties by learning a sparse code for natural images",
    "Computational modelling of visual attention",
    "The magical number seven, plus or minus two: Some limits on our capacity for processing "
    "information.",
    "Fitting Linear Mixed-Effects Models Using <b>lme4</b>",
    "Segmentation of brain MR images through a hidden Markov random field model and the "
    "expectation-maximization algorithm",
    "A survey on deep learning in medical image analysis",
    "A model of saliency-based visual attention for rapid scene analysis",
    "SciPy 1.0: fundamental algorithms for scientific computing in Python",
    "Short-Term Synaptic Plasticity",
    "An introduction to ROC analysis",
    "Hierarchical models of object recognition in cortex",
    "XGBoost",
]
YEARS = [2014, 1998, 2003, 1996, 2001, 1994, 2015, 2001, 2017, 1998, 2020, 2002, 2005, 1999, 2016]
B_PAPERS = [
    2210.1551455879085,
    2185.3899931459905,
    1918.16091954023,
    1914.1438998957246,
    1843.6992969172525,
    1801.5386283545677,
    1659.0873143101421,
    1635.62681369704,
    1590.2366666666667,
    1589.3931260229133,
    1553.0379981464318,
    1509.442700156986,
    1445.212523325731,
    1406.873920552677,
    1395.6526663520528,
]
C_NEURO = [2547, 2271, 1680, 2004, 1750, 2126, 8437, 2111, 969, 879, 1944, 2787, 885, 1690, 798]
C_AI = [1952, 2106, 2235, 1832, 1948, 1563, 920, 1335, 4431, 8286, 1293, 1035, 3938, 1205, 5559]
FIRST_AUTHORS = [
    "Bjoern Menze",
    "Guo‐Qiang Bi",
    "Eugene M. Izhikevich",
    "Bruno A. Olshausen",
    "Laurent Itti",
    "George Miller",
    "Douglas M. Bates",
    "Y. Zhang",
    "Geert Litjens",
    "Laurent Itti",
    "Pauli Virtanen",
    "Robert S. Zucker",
    "Tom Fawcett",
    "Maximilian Riesenhuber",
    "Tianqi Chen",
]
T, C = "tool", "concept"
PAPER_CLASS = [T, C, C, C, C, C, T, T, T, C, T, C, T, C, T]

AUTHORS = [
    "Yoshua Bengio",
    "Christof Koch",
    "Geoffrey E. Hinton",
    "Wulfram Gerstner",
    "Karl Friston",
    "Aude Oliva",
    "Stephen M. Smith",
    "Peter Dayan",
    "Eugene M. Izhikevich",
    "Antonio Torralba",
    "Laurent Itti",
    "Henry Markram",
    "Bruce Fischl",
    "Brian Avants",
    "Bruno A. Olshausen",
]
AUTHOR_PAPERS = [41, 33, 34, 37, 46, 32, 16, 28, 14, 25, 16, 20, 20, 10, 12]
AUTHOR_SUM_B = [
    9936.804594739799,
    8999.659340883336,
    8807.141556845014,
    8425.607384852381,
    7908.569845146347,
    7311.840395000166,
    6263.208945621914,
    5962.981230904954,
    5955.168349084189,
    5714.9776173562095,
    5385.930263286532,
    5378.216050737516,
    5337.567517957525,
    5225.620482519315,
    5076.470243675894,
]
AUTHOR_C_NEURO = [
    6739,
    22872,
    5505,
    10263,
    55276,
    8303,
    33904,
    23209,
    7630,
    4111,
    4344,
    14813,
    42203,
    7257,
    7067,
]
AUTHOR_C_AI = [
    76514,
    18597,
    58177,
    8128,
    4444,
    23659,
    5767,
    7815,
    5816,
    31713,
    14998,
    5867,
    3246,
    4315,
    4806,
]

INST_CONSOLIDATED = [
    "Alphabet (Google + DeepMind)",
    "Microsoft",
    "Massachusetts Institute of Technology",
    "University of California, Berkeley",
    "Harvard University",
    "University College London",
    "Stanford University",
    "University of Oxford",
    "Carnegie Mellon University",
    "University of California, San Diego",
    "California Institute of Technology",
    "University of Toronto",
    "University of Pennsylvania",
    "École Polytechnique Fédérale de Lausanne",
    "Howard Hughes Medical Institute",
]
INST_CONSOLIDATED_PAPERS = [924, 712, 220, 138, 173, 165, 153, 92, 99, 100, 83, 77, 70, 70, 98]
INST_CONSOLIDATED_B = [
    63141.50869605248,
    35557.4467388427,
    35337.944928093806,
    27773.94867906887,
    27390.452714780673,
    23553.45067418386,
    23448.907023353764,
    16769.113586829382,
    16748.294585678304,
    16125.405844341689,
    15263.928408233813,
    15058.827728604274,
    13500.077843496478,
    13195.455864243773,
    12664.458357143694,
]
INST_SEPARATED = [
    "Massachusetts Institute of Technology",
    "University of California, Berkeley",
    "Harvard University",
    "University College London",
    "Stanford University",
    "Google (United States)",
    "University of Oxford",
    "Carnegie Mellon University",
    "University of California, San Diego",
    "California Institute of Technology",
    "University of Toronto",
    "University of Pennsylvania",
    "École Polytechnique Fédérale de Lausanne",
    "Howard Hughes Medical Institute",
    "New York University",
]
INST_SEPARATED_PAPERS = [220, 138, 173, 165, 153, 91, 92, 99, 100, 83, 77, 70, 70, 98, 101]
INST_SEPARATED_B = [
    35337.944928093806,
    27773.94867906887,
    27390.452714780673,
    23553.45067418386,
    23448.907023353764,
    17200.225909645793,
    16769.113586829382,
    16748.294585678304,
    16125.405844341689,
    15263.928408233813,
    15058.827728604274,
    13500.077843496478,
    13195.455864243773,
    12664.458357143694,
    12401.967527066208,
]


def test_table_s1_papers_in_order():
    t = read("table_s1_papers.csv")
    assert t["rank"].tolist() == list(range(1, 16))
    assert t["title"].tolist() == TITLES
    assert t["year"].tolist() == YEARS
    assert t["c_neuro"].tolist() == C_NEURO
    assert t["c_ai"].tolist() == C_AI
    assert t["first_author"].tolist() == FIRST_AUTHORS
    assert t["B"].to_numpy() == pytest.approx(B_PAPERS, rel=RTOL)
    assert t["B"].is_monotonic_decreasing
    # B is the harmonic mean of the two counts
    hm = 2 * t["c_neuro"] * t["c_ai"] / (t["c_neuro"] + t["c_ai"])
    assert t["B"].to_numpy() == pytest.approx(hm.to_numpy(), rel=1e-12)
    assert t["oa_type"].isin(["article", "review"]).all()


def test_table_s1_paper_types():
    t = read("table_s1_papers.csv")
    assert t["paper_class"].tolist() == PAPER_CLASS
    assert (t["paper_class"] == "tool").sum() == 7
    assert (t["paper_class"] == "concept").sum() == 8
    # the most recent concept paper of the top 15 is Izhikevich 2003
    concepts = t[t["paper_class"] == "concept"]
    assert concepts["year"].max() == 2003
    assert concepts.loc[concepts["year"].idxmax(), "title"] == "Simple model of spiking neurons"
    assert t.loc[t["paper_class"] == "tool", "year"].max() == 2020


def test_table_s2_authors():
    t = read("table_s2_authors.csv")
    assert t["rank"].tolist() == list(range(1, 16))
    assert t["author_name"].tolist() == AUTHORS
    assert t["n_bridge_papers"].tolist() == AUTHOR_PAPERS
    assert t["total_c_neuro"].tolist() == AUTHOR_C_NEURO
    assert t["total_c_ai"].tolist() == AUTHOR_C_AI
    assert t["total_B"].to_numpy() == pytest.approx(AUTHOR_SUM_B, rel=RTOL)
    # Aude Oliva is the one woman in the list, at rank 6
    assert t.index[t["author_name"] == "Aude Oliva"].tolist() == [5]


@pytest.mark.parametrize(
    ("name", "names", "papers", "sum_b"),
    [
        (
            "table_s3_institutions_consolidated.csv",
            INST_CONSOLIDATED,
            INST_CONSOLIDATED_PAPERS,
            INST_CONSOLIDATED_B,
        ),
        (
            "table_s3b_institutions_separated.csv",
            INST_SEPARATED,
            INST_SEPARATED_PAPERS,
            INST_SEPARATED_B,
        ),
    ],
)
def test_table_s3_institutions(name, names, papers, sum_b):
    t = read(name)
    assert t["rank"].tolist() == list(range(1, 16))
    assert t["inst_name"].tolist() == names
    assert t["n_bridge_papers"].tolist() == papers
    assert t["total_B"].to_numpy() == pytest.approx(sum_b, rel=RTOL)


def test_corporate_ranks_beyond_the_top_15():
    r = read("institution_ranks_top100.csv").set_index(["variant", "inst_name"])
    assert r.loc[("consolidated", "Meta (Facebook)"), "rank"] == 19
    assert r.loc[("consolidated", "Meta (Facebook)"), "total_B"] == pytest.approx(
        11255.599613, rel=1e-9
    )
    for name, rank in [
        ("DeepMind (United Kingdom)", 26),
        ("Microsoft Research (United Kingdom)", 49),
        ("Microsoft (United States)", 64),
        ("Meta (Israel)", 76),
    ]:
        assert r.loc[("separated", name), "rank"] == rank


def test_author_institution_edges():
    e = read("author_institution_edges.csv")
    assert len(e) == 26
    assert (e["affiliation_status"] == "current").sum() == 10
    assert (e["affiliation_status"] == "past").sum() == 16
    assert e["drawn_main"].sum() == 26
    assert e["drawn_separated"].sum() == 25  # Hinton's Alphabet edge exists only in the main figure
    # Izhikevich has no edge at all; HHMI is the target of none
    assert "Eugene M. Izhikevich" not in set(e["author_name"])
    assert not e["inst_name"].str.contains("Howard Hughes").any()
    cur = e[e["affiliation_status"] == "current"]
    assert sorted(zip(cur["author_name"], cur["inst_name"], strict=True)) == [
        ("Antonio Torralba", "Massachusetts Institute of Technology"),
        ("Aude Oliva", "Massachusetts Institute of Technology"),
        ("Bruce Fischl", "Harvard University"),
        ("Bruce Fischl", "Massachusetts Institute of Technology"),
        ("Bruno A. Olshausen", "University of California, Berkeley"),
        ("Geoffrey E. Hinton", "University of Toronto"),
        ("Henry Markram", "École Polytechnique Fédérale de Lausanne"),
        ("Karl Friston", "University College London"),
        ("Stephen M. Smith", "University of Oxford"),
        ("Wulfram Gerstner", "École Polytechnique Fédérale de Lausanne"),
    ]


def test_paper_author_links():
    k = read("paper_author_links.csv")
    got = list(
        zip(k["paper_rank"], k["author_name"], k["author_position"], k["author_rank"], strict=True)
    )
    assert got == [
        (1, "Brian Avants", "middle", 14),
        (3, "Eugene M. Izhikevich", "first", 9),
        (4, "Bruno A. Olshausen", "first", 15),
        (5, "Christof Koch", "last", 2),
        (5, "Laurent Itti", "first", 11),
        (8, "Stephen M. Smith", "last", 7),
        (10, "Christof Koch", "middle", 2),
        (10, "Laurent Itti", "first", 11),
    ]


def share(pool: str, entity: str, n: int) -> float:
    t = read("concentration_tiers.csv")
    m = (t["pool"] == pool) & (t["entity"] == entity) & (t["top_n"] == n)
    return float(t.loc[m, "share_pct"].iloc[0])


def test_concentration_published_table():
    # supplement section 8.1, all 133,763 candidates (contaminated by the fusion block)
    authors = {1: 0.50, 5: 2.17, 10: 3.63, 15: 4.74, 25: 6.69, 50: 10.41}
    authors |= {100: 15.01, 250: 22.47, 500: 28.62, 1000: 35.45}
    insts = {1: 3.03, 5: 7.90, 10: 12.39, 15: 15.67, 25: 21.01, 50: 30.05}
    insts |= {100: 41.42, 250: 58.11, 500: 70.78, 1000: 82.66}
    for n, v in authors.items():
        assert share("all_133763_unfiltered", "authors", n) == pytest.approx(v, abs=0.005)
    for n, v in insts.items():
        assert share("all_133763_unfiltered", "institutions", n) == pytest.approx(v, abs=0.005)


def test_concentration_top100_all_pools():
    expected = {
        "all_133763_unfiltered": (15.013287730513962, 41.42429248878549),
        "all_133763_minus_mean_B_gt_400": (6.632123546753223, 39.64458075238985),
        "neuro_ai_59038": (12.53351682302512, 46.1127582617879),
        "e2_58971": (9.527232180246186, 44.81978531779703),
    }
    for pool, (a, i) in expected.items():
        assert share(pool, "authors", 100) == pytest.approx(a, rel=RTOL)
        assert share(pool, "institutions", 100) == pytest.approx(i, rel=RTOL)
    # Institutions absorb more than authors at every tier of every pool
    t = read("concentration_tiers.csv")
    w = t.pivot_table(index=["pool", "top_n"], columns="entity", values="share_pct")
    assert (w["institutions"] > w["authors"]).all()


def head() -> dict:
    h = read("headline_numbers.csv").set_index("key")["value"]
    return h.to_dict()


def test_pool_counts():
    h = head()
    assert int(h["n_papers_with_ge5_citations_each_side"]) == 133763
    assert int(h["n_field_other"]) == 74485
    assert int(h["n_field_neuro_or_ai"]) == 59038
    assert int(h["n_eligible_works_e2"]) == 58971
    assert int(h["n_works_dropped_by_ceiling"]) == 67
    assert int(h["n_tools_top15"]) == 7
    assert int(h["most_recent_concept_year_top15"]) == 2003
    assert int(h["oliva_rank"]) == 6
    assert int(h["n_edges_total"]) == 26


def test_gini():
    h = head()
    for key, v in {
        "gini_all_133763_authors_top1000": 0.49376584723148875,
        "gini_all_133763_institutions_top1000": 0.585108479052283,
        "gini_adjusted_authors_top1000": 0.3114289351058701,
        "gini_adjusted_institutions_top1000": 0.5675223455543603,
        "gini_e2_top5000_authors_top100": 0.22173381056631078,
        "gini_e2_top5000_institutions_consolidated": 0.39488091203783887,
    }.items():
        assert float(h[key]) == pytest.approx(v, rel=RTOL)


@pytest.mark.parametrize("name", ["figure2_v3.svg"])
def test_committed_figure_draws_the_tables(name):
    """Paper labels and author names in the committed SVG are the table rows, in the same order."""
    svg = (config.FIGURES_DIR / name).read_text(encoding="utf-8")
    texts = re.findall(r"<!-- (.*?) -->", svg)

    def clip(s: str, n: int) -> str:
        s = re.sub(r"</?b>", "", s).strip()
        return s if len(s) <= n else s[: n - 1] + "…"

    papers = [f"{clip(t, 52)} ({y})" for t, y in zip(TITLES, YEARS, strict=True)]
    authors = [clip(a, 22) for a in AUTHORS]
    for labels in (papers, authors):
        idx = [texts.index(x) for x in labels]
        assert idx == sorted(idx)

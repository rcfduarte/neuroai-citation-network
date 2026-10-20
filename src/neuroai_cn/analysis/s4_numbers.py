"""Numbers quoted in supplement S4 (what each field cites in the other), read from committed results.

Small accessors over ``results/vintage/``, ``results/manifestos/`` and the flow-composition tables
in ``results/flow/``, used by ``docs/supplements/claims/S4.yaml`` so that every number printed in S4 is
recomputed from the committed files. Shares are returned in percent. ``age_window`` computes the
age profile of cited work inside a fixed age window (0 to 20 years by default): because the mirror
starts in 1990, a citing paper of 2010 can only reach back 20 years while one of 2025 can reach back
35, so statistics over all ages drift older with the citing year for reasons that have nothing to do
with reading habits; inside a common window both periods are measured on the same footing.
"""

from __future__ import annotations

from functools import cache

import numpy as np
import pandas as pd

from .. import config

V = config.RESULTS_DIR / "vintage"
M = config.RESULTS_DIR / "manifestos"
F = config.RESULTS_DIR / "flow"


@cache
def _csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def _v(name: str) -> pd.DataFrame:
    return _csv(str(V / name))


def _period(p: str) -> tuple[int, int]:
    a, b = p.split("-")
    return int(a), int(b)


# --- subfield composition of what AI cites in neuroscience ---------------------------------


def subfield_share(
    subfield: str,
    period: str = "2020-2025",
    classifier: str = "extended",
    cited_set: str = "exclusive",
    citing_def: str = "all",
    direction: str = "ai_to_neuro",
) -> float:
    s = _v("subfield_breakdown.csv")
    r = s[
        (s.direction == direction)
        & (s.classifier == classifier)
        & (s.cited_set == cited_set)
        & (s.citing_def == citing_def)
        & (s.period == period)
        & (s.cited_sf_name == subfield)
    ]
    return 100 * float(r.share_edges.iloc[0])


def matrix_share(
    subfield: str,
    years: tuple[int, int] = (2020, 2025),
    citing: str = "all",
    cited_set: str = "unrestricted",
    direction: str = "ai_to_neuro",
) -> float:
    """Subfield share from the count matrix; ``citing`` is all, strict (35-topic core) or extended_only."""
    m = _v("matrix_cited_vintage.csv")
    m = m[(m.direction == direction) & m.citing_year.between(*years)]
    if citing == "strict":
        m = m[m.citing_strict == 1]
    elif citing == "extended_only":
        m = m[m.citing_strict == 0]
    if cited_set == "exclusive":
        m = m[m.cited_dual == 0]
    return 100 * m[m.cited_sf_name == subfield].n.sum() / m.n.sum()


def matrix_share_extreme(
    fn: str,
    subfield: str,
    years: tuple[int, int],
    citing: str = "all",
    cited_set: str = "unrestricted",
    what: str = "value",
) -> float:
    """Smallest (``fn='min'``) or largest share over the single citing years in ``years``.

    ``what='year'`` returns the citing year at which it is reached instead of the share.
    """
    by_year = {
        y: matrix_share(subfield, (y, y), citing=citing, cited_set=cited_set)
        for y in range(years[0], years[1] + 1)
    }
    pick = min if fn == "min" else max
    y = pick(by_year, key=by_year.get)
    return float(y if what == "year" else by_year[y])


def matrix_edges(
    years: tuple[int, int],
    citing: str = "all",
    cited_set: str = "unrestricted",
    direction: str = "ai_to_neuro",
) -> int:
    m = _v("matrix_cited_vintage.csv")
    m = m[(m.direction == direction) & m.citing_year.between(*years)]
    if citing == "strict":
        m = m[m.citing_strict == 1]
    elif citing == "extended_only":
        m = m[m.citing_strict == 0]
    if cited_set == "exclusive":
        m = m[m.cited_dual == 0]
    return int(m.n.sum())


# --- vintage --------------------------------------------------------------------------------


def vintage(
    col: str,
    period: str,
    direction: str = "ai_to_neuro",
    cited_set: str = "exclusive",
    classifier: str = "extended",
    citing_def: str = "all",
) -> float:
    s = _v("vintage_summary.csv")
    r = s[
        (s.direction == direction)
        & (s.cited_set == cited_set)
        & (s.classifier == classifier)
        & (s.citing_def == citing_def)
        & (s.period == period)
    ]
    x = float(r[col].iloc[0])
    return 100 * x if col.startswith("share") else x


def age_window(
    stat: str,
    period: str,
    direction: str = "ai_to_neuro",
    cited_set: str = "exclusive",
    max_age: int = 20,
) -> float:
    """Median, mean, or share aged at most 5 or 10 years (percent) of cited work aged 0..max_age."""
    m = _v("matrix_cited_vintage.csv")
    m = m[(m.direction == direction) & m.citing_year.between(*_period(period))]
    if cited_set == "exclusive":
        m = m[m.cited_dual == 0]
    age = m.citing_year - m.cited_year
    a = m.assign(age=age)[age.between(0, max_age)].groupby("age").n.sum()
    if stat == "median":
        c = a.cumsum() / a.sum()
        return float(c[c >= 0.5].index[0])
    if stat == "mean":
        return float((a * a.index).sum() / a.sum())
    k = int(stat.replace("le", ""))
    return 100 * a.loc[:k].sum() / a.sum()


def median_age_by_year(
    year: int, direction: str = "ai_to_neuro", cited_set: str = "exclusive"
) -> float:
    b = _v("vintage_by_year.csv")
    r = b[(b.direction == direction) & (b.cited_set == cited_set) & (b.citing_year == year)]
    return float(year - r.median_cited_year.iloc[0])


def robustness(col: str, stage: str, cited_set: str, period: str) -> float:
    r = _v("robustness.csv")
    r = r[(r.stage == stage) & (r.cited_set == cited_set) & (r.period == period)]
    x = float(r[col].iloc[0])
    return 100 * x if col in ("cognitive_share", "share_le2005") else x


def robustness_range(
    col: str, stage: str = "regex_plus_clear_plus_borderline", periods=("2020-2025",)
) -> tuple:
    r = _v("robustness.csv")
    r = r[(r.stage == stage) & r.period.isin(periods)]
    return float(r[col].min()), float(r[col].max())


def shift(
    col: str, stage: str, cited_set: str = "exclusive", comparison: str = "2010-2019 -> 2020-2025"
) -> float:
    r = _v("robustness_shift.csv")
    r = r[(r.stage == stage) & (r.cited_set == cited_set) & (r.comparison == comparison)]
    return float(r[col].iloc[0])


def removed_count(rule_prefix: str | None = None) -> int:
    r = _v("removed_works.csv")
    if rule_prefix is None:
        return len(r)
    return int(r.rule.str.startswith(rule_prefix).sum())


# --- reference age ----------------------------------------------------------------------------


def refage(
    col: str,
    field: str,
    period: str = "2020-2023",
    types: str = "article_review",
    scope: str = "all_references",
) -> float:
    p = _v("reference_age_pooled.csv")
    r = p[
        (p.citing_field == field) & (p.period == period) & (p.types == types) & (p.scope == scope)
    ]
    x = float(r[col].iloc[0])
    return 100 * x if col.startswith("share") else x


def coverage(col: str, field: str, year: int, types: str = "all") -> float:
    c = _v("reference_list_coverage.csv")
    r = c[(c.citing_field == field) & (c.types == types) & (c.citing_year == year)]
    x = float(r[col].iloc[0])
    return 100 * x if col.startswith("share") else x


def coverage_extreme(fn: str, field: str, years: tuple[int, int], types: str = "all") -> float:
    c = _v("reference_list_coverage.csv")
    r = c[(c.citing_field == field) & (c.types == types) & c.citing_year.between(*years)]
    return 100 * float(getattr(r.share_with_reflist, fn)())


def dated_share(field: str, years: tuple[int, int] = (2020, 2023), types: str = "all") -> float:
    c = _v("reference_list_coverage.csv")
    r = c[(c.citing_field == field) & (c.types == types) & c.citing_year.between(*years)]
    return 100 * r.n_refs_dated.sum() / r.n_refs_listed.sum()


# --- what neuroscience cites in AI --------------------------------------------------------------


def _comp() -> pd.DataFrame:
    return _csv(str(F / "flow_composition_topic_year.csv"))


def comp_total(classifier: str = "extended", years: tuple[int, int] = (1995, 2023)) -> int:
    d = _comp()
    return int(d[(d.classifier == classifier) & d.citing_year.between(*years)].n_cites.sum())


def comp_topics(classifier: str = "extended", years: tuple[int, int] = (1995, 2023)) -> int:
    d = _comp()
    return int(d[(d.classifier == classifier) & d.citing_year.between(*years)].topic.nunique())


def category_share(
    category: str, classifier: str = "extended", years: tuple[int, int] = (1995, 2023)
) -> float:
    d = _comp()
    d = d[(d.classifier == classifier) & d.citing_year.between(*years)]
    return 100 * d[d.category == category].n_cites.sum() / d.n_cites.sum()


def topic_share(
    topic: str, classifier: str = "extended", years: tuple[int, int] = (1995, 2023)
) -> float:
    d = _comp()
    d = d[(d.classifier == classifier) & d.citing_year.between(*years)]
    return 100 * d[d.topic == topic].n_cites.sum() / d.n_cites.sum()


def head(rank: int, col: str = "n_cites"):
    h = _csv(str(F / "flow_composition_head.csv"))
    return h[h["rank"] == rank][col].iloc[0]


def head_category_count(category: str, top: int = 25) -> int:
    h = _csv(str(F / "flow_composition_head.csv"))
    return int((h[h["rank"] <= top].category == category).sum())


def concentration(q: float, col: str = "n_works") -> float:
    c = _csv(str(F / "flow_concentration.csv"))
    x = float(c[np.isclose(c.quantile_of_citations, q)][col].iloc[0])
    return 100 * x if col.startswith("share") else x


# --- the six NeuroAI papers ---------------------------------------------------------------------


def manifesto_share(year: int, col: str = "share_of_ai_to_neuro_all_six") -> float:
    s = _csv(str(M / "share_of_flow_by_year.csv"))
    return 100 * float(s[s.year == year][col].iloc[0])


def manifesto_share_extreme(
    fn: str, years=(2020, 2023), col: str = "share_of_ai_to_neuro_all_six"
) -> float:
    s = _csv(str(M / "share_of_flow_by_year.csv"))
    return 100 * float(getattr(s[s.year.between(*years)][col], fn)())


def or_change_max(direction: str = "ai_to_neuro", years=(2015, 2023)) -> float:
    o = _csv(str(M / "or_excluding_manifestos.csv"))
    o = o[(o.direction == direction) & o.year.between(*years)]
    return 100 * float(o.relative_change.abs().max())

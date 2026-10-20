"""Headline numbers of the citation-flow section, each recomputed from ``results/flow/or_by_year.csv``.

Every number the supplements quote for Figures 1 and 2 comes from one of these functions, so a text
number can be checked (and a changed CSV detected, see ``tests/test_flow_numbers.py``).

Direction names are the data convention:

* ``neuro_to_ai``: neuroscience papers citing AI (gold in the article, which labels this flow AI -> Neuro:
  knowledge moving from AI into neuroscience).
* ``ai_to_neuro``: AI papers citing neuroscience (teal in the article, which labels this flow
  Neuro -> AI: knowledge moving from neuroscience into AI).

Counts are references recorded in the OpenAlex snapshot (March 2026), extended AI definition.
The odds ratio is the ``or_restricted`` column: observed share of cross-field references among
own-field plus cross-field references, relative to the share expected from field sizes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config
from ..figures.style import CANONICAL_ERAS

FLOW_DIR = config.RESULTS_DIR / "flow"
OR_BY_YEAR_CSV = FLOW_DIR / "or_by_year.csv"
DIRECTIONS = ("neuro_to_ai", "ai_to_neuro")
FIELD_OF = {"neuro_to_ai": "neuroscience", "ai_to_neuro": "ai"}
LAST_SOLID_YEAR = 2023  # 2024-25 are provisional
SLOPE_WINDOW = (1995, 2023)  # the window of panels B and C


def load() -> pd.DataFrame:
    """The committed snapshot table, sorted by direction and year."""
    df = pd.read_csv(OR_BY_YEAR_CSV, float_precision="round_trip")
    return df.sort_values(["direction", "year"]).reset_index(drop=True)


def _wide(df: pd.DataFrame, col: str) -> pd.DataFrame:
    return df.pivot(index="year", columns="direction", values=col)[list(DIRECTIONS)]


def field_sizes(years: tuple[int, ...] = (1995, 2025), df: pd.DataFrame | None = None) -> dict:
    """Works per field in the given years: ``{year: {"neuroscience": n, "ai": n, "ratio_ai_to_neuro": r}}``."""
    df = load() if df is None else df
    n = _wide(df, "n_works_source")
    return {
        int(y): {
            "neuroscience": int(n.loc[y, "neuro_to_ai"]),
            "ai": int(n.loc[y, "ai_to_neuro"]),
            "ratio_ai_to_neuro": float(n.loc[y, "ai_to_neuro"] / n.loc[y, "neuro_to_ai"]),
        }
        for y in years
    }


def size_ratio_by_year(df: pd.DataFrame | None = None) -> pd.Series:
    """AI works divided by neuroscience works, per year."""
    df = load() if df is None else df
    n = _wide(df, "n_works_source")
    return (n["ai_to_neuro"] / n["neuro_to_ai"]).rename("ai_over_neuroscience")


def cross_field_citations_per_year(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Raw cross-field citation counts per year (references that cross to the other field)."""
    df = load() if df is None else df
    return _wide(df, "n_to_target").astype(int)


def cross_refs_per_1000(
    df: pd.DataFrame | None = None, include_unknown: bool = False
) -> pd.DataFrame:
    """Cross-field references per 1,000 references recorded.

    Default (Figure 2B): denominator = references to own + other + third fields. With
    ``include_unknown=True`` the references to works of unknown field are added to the denominator,
    which is ``rho_population`` x 1000 in the pipeline and the column of the companion table; it is
    smaller by up to 0.43 percent.
    """
    df = load() if df is None else df
    refs = df["n_to_within"] + df["n_to_target"] + df["n_to_other"]
    if include_unknown:
        refs = refs + df["n_to_unknown"]
    out = df.assign(per1000=df["n_to_target"] / refs * 1000.0)
    return _wide(out, "per1000")


def centred_mean5(s: pd.Series) -> pd.Series:
    """Centred 5-year mean over the full series, at least 3 points (the thick line of the figures)."""
    return s.rolling(5, center=True, min_periods=3).mean()


def share_crossing(
    df: pd.DataFrame | None = None, smoothed: bool = False, include_unknown: bool = False
) -> dict:
    """Where the two raw-share lines (cross-field references per 1,000) cross.

    ``last_year_ai_citing_neuroscience_higher``: last year the AI-citing-neuroscience share is above
    the neuroscience-citing-AI share. ``first_year_neuro_citing_ai_higher_for_good``: first year from
    which the neuroscience share stays above the AI share through 2025. ``crossing_year_interpolated``
    is the linear interpolation of the difference between the two years that bracket the change.
    ``smoothed=True`` applies the centred 5-year mean (the thick lines) instead of the yearly values.
    """
    p = cross_refs_per_1000(df, include_unknown)
    if smoothed:
        p = p.apply(centred_mean5)
    diff = p["neuro_to_ai"] - p["ai_to_neuro"]  # > 0: neuroscience-citing-AI share is higher
    neg = diff[diff < 0]
    last_neg = int(neg.index.max())
    first_for_good = int(diff.index[diff.index > last_neg].min())
    d0, d1 = float(diff.loc[last_neg]), float(diff.loc[first_for_good])
    return {
        "smoothed": smoothed,
        "include_unknown": include_unknown,
        "last_year_ai_citing_neuroscience_higher": last_neg,
        "first_year_neuro_citing_ai_higher_for_good": first_for_good,
        "crossing_year_interpolated": last_neg + (first_for_good - last_neg) * (-d0) / (d1 - d0),
        "difference_at_last_negative": d0,
        "difference_at_first_positive": d1,
    }


def count_dominance(df: pd.DataFrame | None = None) -> dict:
    """Is neuroscience-citing-AI above AI-citing-neuroscience in the raw cross-field COUNT?

    Returns whether it holds in every year of 1990-2025, the years where it does not, and the first
    year from which it holds without exception.
    """
    c = cross_field_citations_per_year(df)
    above = c["neuro_to_ai"] > c["ai_to_neuro"]
    exceptions = [int(y) for y in c.index[~above]]
    first_for_good = int(c.index[0]) if not exceptions else int(max(exceptions) + 1)
    return {
        "neuro_exceeds_ai_every_year": bool(above.all()),
        "years_where_not": exceptions,
        "first_year_from_which_always": first_for_good,
        "n_years": len(c),
        "min_ratio": float((c["neuro_to_ai"] / c["ai_to_neuro"]).min()),
        "max_ratio": float((c["neuro_to_ai"] / c["ai_to_neuro"]).max()),
    }


def odds_ratio_at(
    years: tuple[int, ...] = (1995, 2006, 2019, 2023), df: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Yearly odds ratio (``or_restricted``) per direction at the given years."""
    df = load() if df is None else df
    return _wide(df, "or_restricted").loc[list(years)]


def odds_ratio_growth(
    y0: int = 1995, y1: int = 2023, df: pd.DataFrame | None = None
) -> dict[str, float]:
    """Ratio of the odds ratio in ``y1`` to its value in ``y0``, per direction."""
    o = odds_ratio_at((y0, y1), df)
    return {d: float(o.loc[y1, d] / o.loc[y0, d]) for d in DIRECTIONS}


def era_slopes(
    df: pd.DataFrame | None = None, window: tuple[int, int] = SLOPE_WINDOW
) -> pd.DataFrame:
    """OLS slope of the yearly odds ratio per year inside each of the four pre-defined eras.

    Eras are ``style.CANONICAL_ERAS`` clipped to ``window`` (1995-2023, as in panel B).
    """
    df = load() if df is None else df
    rows = []
    for d in DIRECTIONS:
        s = df[df["direction"] == d]
        for label, lo, hi in CANONICAL_ERAS:
            lo2, hi2 = max(lo, window[0]), min(hi, window[1])
            b = s[s["year"].between(lo2, hi2)]
            x, y = b["year"].to_numpy(dtype=float), b["or_restricted"].to_numpy(dtype=float)
            slope = float(np.polyfit(x, y, 1)[0])
            rows.append(
                {
                    "direction": d,
                    "era": label,
                    "year_start": lo2,
                    "year_end": hi2,
                    "n_years": len(b),
                    "slope_per_year": slope,
                }
            )
    return pd.DataFrame(rows)


def all_headline_numbers() -> dict:
    """Everything above in one dictionary (for printing or for the supplement build)."""
    df = load()
    return {
        "field_sizes": field_sizes((1995, 2025), df),
        "cross_field_citations_2023": cross_field_citations_per_year(df).loc[2023].to_dict(),
        "count_dominance": count_dominance(df),
        "share_crossing_yearly": share_crossing(df, smoothed=False),
        "share_crossing_smoothed": share_crossing(df, smoothed=True),
        "odds_ratio_at": odds_ratio_at(df=df).to_dict(),
        "odds_ratio_growth_1995_to_2023": odds_ratio_growth(df=df),
        "era_slopes": era_slopes(df).to_dict("records"),
    }


if __name__ == "__main__":
    import pprint

    pprint.pprint(all_headline_numbers(), sort_dicts=False)

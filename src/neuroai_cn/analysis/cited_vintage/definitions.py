"""Definitions for the cited-vintage analysis, declared before any result was looked at.

This module is the pre-registration. Every statistic computed in ``vintage.py``,
``robustness.py`` and ``reference_age.py`` uses the constants and SQL fragments below, and
nothing else. The values were fixed before the queries were run.

Statements under test
    (1) Of the neuroscience that AI papers now cite, about 90 percent comes from cognitive
        neuroscience and under 5 percent from cellular and molecular work (2020-2025).
    (2) Comparing the neuroscience cited by AI papers published 2010-2019 with those
        published 2020-2025, the median year of the cited work moves from 2008 to 2015 and
        the share published in 2005 or earlier falls from 35% to 15%.

Citing papers
    * AI: the extended classifier of ``audits/extended_classifier.py`` (OpenAlex subfield 1702
      minus the 26 excluded topics, plus subfield 1707, plus topic T10502), on the primary
      topic only. Neuroscience: OpenAlex field 28 on the primary topic. A work in field 28 is
      never AI (the neuroscience test comes first), so the two labels are disjoint.
    * Year: ``works.publication_year`` of the citing paper. Periods: 2010-2019 and 2020-2025,
      plus 2020-2023 because 2024-2025 are unstable in this snapshot (the OpenAlex rebuild window
      and the growing share of works without a primary topic).
    * Type: PRIMARY analysis uses every OpenAlex work type, which is what the flow analysis
      behind the article's Figure 1 does (restricting to article and review would drop arXiv
      preprints, a large part of AI). SENSITIVITY: citing type article or review only.

Cited works
    * UNRESTRICTED: the primary topic lies in field 28.
    * EXCLUSIVE (primary specification for the headline numbers): field 28 AND none of the
      work's listed OpenAlex topics (``works.topics``, at most three, which include the primary
      topic) is an AI topic under the extended classifier. This removes the AI papers that
      OpenAlex files under neuroscience (the earlier README names the DQN paper, Prioritized
      Experience Replay and others) when their secondary topic is AI. It cannot remove them
      all, which is what ``robustness.py`` is for.
    * Because the neuroscience test comes first, no field-28 work has an AI primary topic;
      the count of such works is zero by construction and is reported as a check.
    * Cited works dated before 1990 are absent from the mirror (the works table starts at
      1990), so every vintage statistic is computed on cited works published 1990 or later.
      This truncates the old tail in every period and is a limitation of the snapshot.

Sub-areas of neuroscience
    The OpenAlex subfields under field 28, taken from the primary topic of the cited work. For
    the two named in the claim: "cognitive neuroscience" means the single subfield named
    Cognitive Neuroscience (2805) and "cellular and molecular" the single subfield named
    Cellular and Molecular Neuroscience (2804); ids are confirmed against the data by
    ``build.py`` and the full breakdown over all subfields is always written next to them.
    Shares are shares of citation edges (one edge = one citing paper citing one work); the
    share of distinct cited works is reported alongside.

Statistics, per period and cited-work set
    number of edges and of distinct cited works; median cited year (mean of the two middle
    order statistics); mean age (citing year minus cited year); share of edges to works published
    in 2005 or earlier (the claim says "2005 or earlier", so the boundary used is <= 2005; the
    earlier working script labelled "pre2005" actually used <= 2004, so <= 2004 is also written
    out, and the two differ by roughly one to two points).

Reverse direction
    Neuroscience papers citing AI works, same periods, same statistics; the cited AI set is
    UNRESTRICTED (extended AI primary topic) and EXCLUSIVE (additionally no listed topic in
    field 28).

Robustness rule (``robustness.py``), declared in advance
    Remove from the cited side (a) every cited work whose title matches ``AI_TITLE_REGEX``
    below, and (b) the 25 most-cited surviving works of each period (2010-2019, 2020-2025)
    that on reading the title are AI or machine-learning methods papers (the list is frozen in
    ``MANUAL_REMOVALS`` in ``robustness.py`` with the reason). Every removed work is written
    to ``results/vintage/removed_works.csv`` with title, year and citation counts. The check
    FAILS (is a finding) if the cognitive-neuroscience share moves by more than 2 percentage
    points, the median year by more than 1 year, or the share published in 2005 or earlier by
    more than 2 percentage points, in either period.
"""

from __future__ import annotations

from ...audits.extended_classifier import (
    AI_SUBFIELD_1702,
    AI_SUBFIELD_1707,
    BAD_1702_TOPIC_IDS,
    NEURAL_MEMORY_TOPIC_2208,
)
from ...utils.duckdb import AI_CORE_TOPIC_IDS, NEURO_FIELD_ID

COGNITIVE_SUBFIELD = "https://openalex.org/subfields/2805"
CELLULAR_SUBFIELD = "https://openalex.org/subfields/2804"

PERIODS: dict[str, tuple[int, int]] = {
    "2010-2019": (2010, 2019),
    "2020-2025": (2020, 2025),
    "2020-2023": (2020, 2023),
}
CITING_YEAR_MIN = 1995
CITING_YEAR_MAX = 2025
BOUNDARY_YEARS = (2005, 2004)  # share published in or before each year; 2005 is the headline

ARTICLE_REVIEW = ("article", "review")

# Title patterns for the robustness check (case-insensitive). Deliberately generous: a
# neuroscience paper with "neural network" in the title is removed too, which can only make the
# check harder to pass for the headline numbers.
AI_TITLE_REGEX = (
    r"deep learning|deep (?:neural|reinforcement|convolutional|belief)|reinforcement learning|"
    r"convolutional|recurrent neural|transformer|language model|machine learning|"
    r"neural network|backpropagation|back-propagation|gradient descent|adversarial|"
    r"autoencoder|attention is all|\bbert\b|imagenet|support vector|random forest|"
    r"artificial intelligence|artificial neural|word2vec|embedding|q-learning|"
    r"temporal.difference|markov decision|bayesian optimi|scikit|tensorflow|pytorch|"
    r"\bkeras\b|\bgpt\b|large language|prioritized|experience replay|dqn|policy gradient|"
    r"actor.critic|monte carlo tree|\balphago\b|\balphazero\b"
)


def _ids(values) -> str:
    return "[" + ",".join("'" + v + "'" for v in sorted(values)) + "]"


def ai_condition(topic: str) -> str:
    """SQL predicate: the topic struct ``topic`` is an AI topic under the extended classifier."""
    return (
        f"(({topic}.subfield.id = '{AI_SUBFIELD_1702}'"
        f" AND NOT list_contains({_ids(BAD_1702_TOPIC_IDS)}, {topic}.id))"
        f" OR {topic}.subfield.id = '{AI_SUBFIELD_1707}'"
        f" OR {topic}.id = '{NEURAL_MEMORY_TOPIC_2208}')"
    )


def neuro_condition(topic: str) -> str:
    return f"{topic}.field.id = '{NEURO_FIELD_ID}'"


def strict_ai_condition(topic: str) -> str:
    """The 35-topic core AI list of the earlier analysis (used only to reproduce its numbers)."""
    return f"list_contains({_ids(AI_CORE_TOPIC_IDS)}, {topic}.id)"

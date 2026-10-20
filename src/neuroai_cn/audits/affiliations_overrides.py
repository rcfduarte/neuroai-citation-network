"""Hand-verified CURRENT + PAST affiliations for the top-15 bridge authors.

REWRITTEN 2026-05-27 (v3). Adds past-affiliation edges (faded in the figure)
alongside current ones (solid). Every row is hand-verified against ORCID
employment records, official university/lab pages, Google Scholar, LinkedIn,
and the researchers' own CVs (research-assistant verification, May 2026; full
source table in the piece supplement / vault note
`bridge-author-affiliations-verified-20260527.md`).

Why this replaces OpenAlex `last_known_institutions`: that field carried
extensive name-collision junk for this set — Brian Avants -> "California
University of Pennsylvania" (a different school), Christof Koch -> "Gere
Foundation", Antonio Torralba -> "Citigroup"/"Dominica State College", Yoshua
Bengio -> "Centre Universitaire de Mila" (Algeria), plus dozens of
co-authorship "affiliations" that were never real employment. None survived
verification. This module is now the SOLE source of author->institution edges.

Edge semantics in figure2_v3:
    affiliation_status == "current"  -> SOLID curve  (active 2025-2026)
    affiliation_status == "past"     -> FADED curve  (former affiliation)

Policy (applied uniformly, flagged for the editor):
    * Include research affiliations only: PhD, postdoc, faculty, director,
      visiting researcher, industry research. EXCLUDE undergraduate / MS-only
      education (e.g. Olshausen's Stanford BS/MS) and non-research clinical
      rotations (e.g. Friston's early Oxford psychiatry training) — these are
      not institutional research affiliations and would overclaim.
    * Only the canonical top-15 bridge institutions can appear; affiliations to
      non-listed institutions (Mila/UdeM, Allen Institute, MPI Tübingen, USC,
      Brain Corp, Weizmann, Salk, UVA, etc.) are intentionally not drawn.
    * No verified HHMI Investigator appointment exists for any of the 15 — the
      HHMI node therefore carries no author edge (it ranks via paper brokerage).
    * Google/DeepMind map to the consolidated "ALPHABET_GROUP" node (main
      figure); this edge is consolidated-only and will not appear in the
      OpenAlex-separated supplementary variant.

Output:
    corrections/20260508/author_current_affiliations_curated.parquet

Run:
    uv run python -m neuroai_cn.audits.affiliations_overrides
"""

from __future__ import annotations

import logging

import pandas as pd

from .. import config

logger = logging.getLogger(__name__)

CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"

# Canonical OpenAlex institution IDs for the consolidated top-15 node set.
INST = {
    "MIT": "https://openalex.org/I63966007",
    "UC Berkeley": "https://openalex.org/I95457486",
    "Harvard": "https://openalex.org/I136199984",
    "UCL": "https://openalex.org/I45129253",
    "Oxford": "https://openalex.org/I40120149",
    "CMU": "https://openalex.org/I74973139",
    "UCSD": "https://openalex.org/I36258959",
    "Caltech": "https://openalex.org/I122411786",
    "Toronto": "https://openalex.org/I185261750",
    "UPenn": "https://openalex.org/I79576946",
    "EPFL": "https://openalex.org/I5124864",
    "Alphabet": "ALPHABET_GROUP",  # consolidated Google + DeepMind node
}

# Hand-verified affiliations. One row per (author, institution) tie.
# Format: (author_rank, author_name, author_id, inst_key, status, role_note)
#   inst_key  -> key into INST (the canonical node)
#   status    -> "current" (solid) | "past" (faded)
CURATED_AFFILIATIONS: list[tuple[int, str, str, str, str, str]] = [
    # 1 Yoshua Bengio — current UdeM/Mila (not a node). Microsoft was advisory only (dropped).
    (
        1,
        "Yoshua Bengio",
        "https://openalex.org/A5086198262",
        "MIT",
        "past",
        "Postdoctoral fellow, 1991–1992 (with M. I. Jordan).",
    ),
    # 2 Christof Koch — current Allen Institute (not a node).
    (
        2,
        "Christof Koch",
        "https://openalex.org/A5084822308",
        "MIT",
        "past",
        "Postdoctoral fellow, AI Lab & BCS, 1982–1986.",
    ),
    (
        2,
        "Christof Koch",
        "https://openalex.org/A5084822308",
        "Caltech",
        "past",
        "Professor, 1986–2013 (~27 years).",
    ),
    # 3 Geoffrey E. Hinton — current Toronto (Emeritus).
    (
        3,
        "Geoffrey E. Hinton",
        "https://openalex.org/A5108093963",
        "Toronto",
        "current",
        "University Professor Emeritus, 1987–present.",
    ),
    (
        3,
        "Geoffrey E. Hinton",
        "https://openalex.org/A5108093963",
        "UCSD",
        "past",
        "Visiting scholar / asst. prof., ~1980–1982 (with Rumelhart).",
    ),
    (
        3,
        "Geoffrey E. Hinton",
        "https://openalex.org/A5108093963",
        "CMU",
        "past",
        "Faculty, Computer Science, 1982–1987.",
    ),
    (
        3,
        "Geoffrey E. Hinton",
        "https://openalex.org/A5108093963",
        "UCL",
        "past",
        "Founding Director, Gatsby Unit, 1998–2001.",
    ),
    (
        3,
        "Geoffrey E. Hinton",
        "https://openalex.org/A5108093963",
        "Alphabet",
        "past",
        "VP & Engineering Fellow, Google Brain, 2013–2023.",
    ),
    # 4 Wulfram Gerstner — current EPFL.
    (
        4,
        "Wulfram Gerstner",
        "https://openalex.org/A5003480477",
        "EPFL",
        "current",
        "Full Professor; Director, LCN, 1996–present.",
    ),
    (
        4,
        "Wulfram Gerstner",
        "https://openalex.org/A5003480477",
        "UC Berkeley",
        "past",
        "Visiting researcher, Bialek group, 1989–1990.",
    ),
    # 5 Karl Friston — current UCL. (Oxford = clinical rotation only, excluded.)
    (
        5,
        "Karl Friston",
        "https://openalex.org/A5086852785",
        "UCL",
        "current",
        "Professor; Scientific Director, Wellcome Centre HN.",
    ),
    # 6 Aude Oliva — current MIT.
    (
        6,
        "Aude Oliva",
        "https://openalex.org/A5021257546",
        "MIT",
        "current",
        "Senior Research Scientist; CSAIL / MIT-IBM Watson, 2004–present.",
    ),
    (
        6,
        "Aude Oliva",
        "https://openalex.org/A5021257546",
        "Harvard",
        "past",
        "Postdoctoral associate, Harvard Medical School / BWH, 2000–2002.",
    ),
    # 7 Stephen M. Smith — current Oxford (lifelong).
    (
        7,
        "Stephen M. Smith",
        "https://openalex.org/A5066553010",
        "Oxford",
        "current",
        "Professor of Biomedical Engineering; FMRIB/WIN, 1986–present.",
    ),
    # 8 Peter Dayan — current MPI Tübingen (not a node).
    (
        8,
        "Peter Dayan",
        "https://openalex.org/A5075063030",
        "UCL",
        "past",
        "Professor & Director, Gatsby Unit, 1998–2017.",
    ),
    (
        8,
        "Peter Dayan",
        "https://openalex.org/A5075063030",
        "MIT",
        "past",
        "Assistant Professor, 1995–1998.",
    ),
    (
        8,
        "Peter Dayan",
        "https://openalex.org/A5075063030",
        "Toronto",
        "past",
        "Postdoc / research associate, ~1994–1995 (with Hinton).",
    ),
    # 9 Eugene M. Izhikevich — current Brain Corp (not a node); no top-15 in history.
    # 10 Antonio Torralba — current MIT.
    (
        10,
        "Antonio Torralba",
        "https://openalex.org/A5085020955",
        "MIT",
        "current",
        "Delta Electronics Professor of EECS; CSAIL, 2000–present.",
    ),
    # 11 Laurent Itti — current USC (not a node).
    (
        11,
        "Laurent Itti",
        "https://openalex.org/A5054494771",
        "Caltech",
        "past",
        "PhD, Computation & Neural Systems, ~1996–2000 (with Koch).",
    ),
    # 12 Henry Markram — current EPFL.
    (
        12,
        "Henry Markram",
        "https://openalex.org/A5069964239",
        "EPFL",
        "current",
        "Full Professor; LNMC, 2002–present.",
    ),
    # 13 Bruce Fischl — current Harvard (HMS) AND MIT (CSAIL).
    (
        13,
        "Bruce Fischl",
        "https://openalex.org/A5022799533",
        "Harvard",
        "current",
        "Professor of Radiology, Harvard Medical School (MGH-Martinos).",
    ),
    (
        13,
        "Bruce Fischl",
        "https://openalex.org/A5022799533",
        "MIT",
        "current",
        "Research affiliate, MIT CSAIL / HST, ~2004–present.",
    ),
    # 14 Brian Avants — current UVA (not a node); Penn = past (now alumni).
    (
        14,
        "Brian Avants",
        "https://openalex.org/A5016551394",
        "UPenn",
        "past",
        "PhD + Assistant Professor of Radiology (PICSL), ~2007–2018; now alumnus.",
    ),
    # 15 Bruno A. Olshausen — current UC Berkeley. (Stanford BS/MS excluded.)
    (
        15,
        "Bruno A. Olshausen",
        "https://openalex.org/A5032674291",
        "UC Berkeley",
        "current",
        "Professor; Director, Redwood Center, 2005–present.",
    ),
    (
        15,
        "Bruno A. Olshausen",
        "https://openalex.org/A5032674291",
        "Caltech",
        "past",
        "PhD, Computation & Neural Systems, ~1990–1994.",
    ),
    (
        15,
        "Bruno A. Olshausen",
        "https://openalex.org/A5032674291",
        "MIT",
        "past",
        "Postdoc, Center for Biological & Computational Learning, ~1994–1996.",
    ),
]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    top_i = pd.read_parquet(CORRECTIONS_DIR / "author_inst_top_institutions_consolidated.parquet")
    top15 = top_i.sort_values("total_B", ascending=False).head(15).reset_index(drop=True)
    top15["inst_rank"] = top15.index + 1
    name_by_id = dict(zip(top15["inst_id"], top15["inst_name"], strict=False))

    rows = []
    for rank, name, aid, inst_key, status, note in CURATED_AFFILIATIONS:
        iid = INST[inst_key]
        rows.append(
            dict(
                author_id=aid,
                author_name=name,
                author_rank=rank,
                inst_id=iid,
                inst_name=name_by_id.get(iid, inst_key),
                affiliation_status=status,  # "current" | "past"
                is_manual_override=False,  # retained for downstream compat
                note=note,
            )
        )
    cur = pd.DataFrame(rows)

    # Diagnostic inst_rank (NOT persisted — figure derives it per institution set).
    diag = cur.merge(top15[["inst_id", "inst_rank"]], on="inst_id", how="left")
    n_unmatched = int(diag["inst_rank"].isna().sum())
    if n_unmatched:
        logger.warning("%d affiliation rows did not match a top-15 node:", n_unmatched)
        print(diag[diag["inst_rank"].isna()][["author_name", "inst_id", "inst_name"]])

    out = CORRECTIONS_DIR / "author_current_affiliations_curated.parquet"
    cur.to_parquet(out, index=False)

    n_cur = int((cur["affiliation_status"] == "current").sum())
    n_past = int((cur["affiliation_status"] == "past").sum())
    logger.info(
        "Wrote %s — %d edges (%d current/solid, %d past/faded) across %d authors",
        out,
        len(cur),
        n_cur,
        n_past,
        cur["author_rank"].nunique(),
    )
    print("\n=== CURRENT (solid) ===")
    print(
        diag[diag["affiliation_status"] == "current"]
        .sort_values("author_rank")[
            ["author_rank", "author_name", "inst_name", "inst_rank", "note"]
        ]
        .to_string(index=False)
    )
    print("\n=== PAST (faded) ===")
    print(
        diag[diag["affiliation_status"] == "past"]
        .sort_values("author_rank")[
            ["author_rank", "author_name", "inst_name", "inst_rank", "note"]
        ]
        .to_string(index=False)
    )
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())

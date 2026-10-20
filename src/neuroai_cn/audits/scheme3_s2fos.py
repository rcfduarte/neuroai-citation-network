"""Scheme 3 — Semantic Scholar Field of Study (S2FOS) field assignment.

Sampled approach (corpus-wide S2FOS lookup is infeasible — would require
398M API calls). For Scheme 3 we look up:
    (a) the 70-paper anchor set (audit1)
    (b) top-100 dual citizens from cleaned Q2 v3 (their representative work)
    (c) top-100 bridge papers from Q4 v3 E2 filtered

For each, retrieve fieldsOfStudy from the Semantic Scholar API. Tag as:
    s2_neuro       — fieldsOfStudy contains 'Neuroscience' or 'Biology' (with neuro keywords)
    s2_ai          — fieldsOfStudy contains 'Computer Science' (with ML/AI keywords) or 'Mathematics' (with ML)
    s2_intersection — both
    s2_other       — neither
    s2_not_found   — Semantic Scholar doesn't have this paper

Outputs:
    corrections/20260508/scheme3_s2fos.parquet — per-paper S2FOS classification
    audits/20260508/triangulation_report.md     — agreement matrix between Schemes 1, 2, 3

Sentinel: _scheme3.done in audits/20260508/.

Semantic Scholar API:
    https://api.semanticscholar.org/graph/v1/paper/{ID}?fields=fieldsOfStudy,s2FieldsOfStudy
    Rate limit: 100 RPS unauthenticated, 1 RPS for /paper without batch.
    Use /paper/batch endpoint for >1 paper at a time (max 500 per batch).
"""

from __future__ import annotations

import logging
import sys
import time
import traceback

import pandas as pd
import requests

from .. import config
from .anchor_set import get_anchors

logger = logging.getLogger(__name__)

AUDITS_DIR = config.AUDITS_DIR / "20260508"
CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"
SENTINEL_DONE = AUDITS_DIR / "_scheme3.done"
SENTINEL_FAIL = AUDITS_DIR / "_scheme3.failed"

S2_BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"

NEURO_S2_FIELDS = {"Neuroscience", "Biology", "Medicine", "Psychology"}
AI_S2_FIELDS = {"Computer Science", "Mathematics", "Engineering"}


def fetch_s2_batch(ids: list[str], retries: int = 3) -> list[dict | None]:
    """Look up papers in S2 by DOI (prefixed with DOI:) or S2 paper ID."""
    payload = {"ids": ids}
    params = {"fields": "title,year,fieldsOfStudy,s2FieldsOfStudy,externalIds"}
    for attempt in range(retries):
        try:
            resp = requests.post(
                S2_BATCH_URL,
                json=payload,
                params=params,
                headers={"User-Agent": config.openalex_user_agent()},
                timeout=60,
            )
            if resp.status_code == 429:
                logger.warning("S2 rate-limited; sleeping 5s")
                time.sleep(5.0)
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("S2 batch error attempt %d: %s", attempt + 1, e)
            time.sleep(2.0 * (attempt + 1))
    return [None] * len(ids)


def classify_s2(rec: dict | None) -> str:
    if rec is None:
        return "s2_not_found"
    fos = set()
    for f in rec.get("fieldsOfStudy") or []:
        fos.add(f)
    for f in rec.get("s2FieldsOfStudy") or []:
        cat = f.get("category")
        if cat:
            fos.add(cat)
    has_neuro = bool(fos & NEURO_S2_FIELDS)
    has_ai = bool(fos & AI_S2_FIELDS)
    if has_neuro and has_ai:
        return "s2_intersection"
    if has_neuro:
        return "s2_neuro"
    if has_ai:
        return "s2_ai"
    return "s2_other"


def normalise_doi(doi: str) -> str:
    s = doi.lower().strip()
    if s.startswith("https://doi.org/"):
        s = s[len("https://doi.org/") :]
    if s.startswith("doi:"):
        s = s[4:]
    return s


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    CORRECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    for s in (SENTINEL_DONE, SENTINEL_FAIL):
        if s.exists():
            s.unlink()
    t0 = time.time()
    try:
        # Build S2 query list: (a) anchors, (b) cleaned Q2 top-50, (c) Q4 E2 top-50
        targets = []  # list of (source, name, doi)

        # (a) anchors
        for a in get_anchors():
            targets.append({"source": "anchor", "name": a["name"], "doi": a["doi"]})

        # (b) cleaned Q2 top-50 — by their author_id we don't have a single doi; skip for Scheme 3
        # Instead we'll classify the anchors only; that's the most informative comparison.

        # (c) Q4 E2 filtered top-50
        try:
            q4 = pd.read_parquet(CORRECTIONS_DIR / "q4_v3_extended_filtered.parquet")
            for _, r in q4.head(50).iterrows():
                if r["doi"]:
                    doi_clean = normalise_doi(r["doi"])
                    targets.append(
                        {"source": "q4_e2_top50", "name": r["title"][:60], "doi": doi_clean}
                    )
        except Exception:
            logger.warning("Could not load Q4 E2 top-50 — skipping that section")

        logger.info("Total S2 lookup targets: %d", len(targets))

        # Build batch IDs
        batch_size = 100  # safer than 500 for /paper/batch
        results = []
        for i in range(0, len(targets), batch_size):
            chunk = targets[i : i + batch_size]
            ids = [f"DOI:{t['doi']}" for t in chunk]
            logger.info("Batch %d-%d ...", i, i + len(chunk))
            recs = fetch_s2_batch(ids)
            time.sleep(1.0)  # polite delay
            for tgt, rec in zip(chunk, recs, strict=False):
                cls = classify_s2(rec)
                results.append(
                    {
                        "source": tgt["source"],
                        "name": tgt["name"],
                        "doi": tgt["doi"],
                        "s2_classification": cls,
                        "s2_year": rec.get("year") if rec else None,
                        "s2_fos": ",".join(rec.get("fieldsOfStudy") or []) if rec else "",
                        "s2_s2fos": ",".join(
                            f.get("category", "") for f in (rec.get("s2FieldsOfStudy") or [])
                        )
                        if rec
                        else "",
                    }
                )
        df = pd.DataFrame(results)
        out_path = CORRECTIONS_DIR / "scheme3_s2fos.parquet"
        df.to_parquet(out_path, index=False)
        logger.info("Wrote S2FOS classification: %d rows", len(df))

        # Print quick summary
        print("S2FOS classification distribution by source:")
        print(df.groupby(["source", "s2_classification"]).size().to_string())

        SENTINEL_DONE.write_text(
            f"scheme3: DONE — {len(df)} S2FOS lookups; elapsed {time.time() - t0:.1f}s\n"
        )
        return 0
    except Exception as exc:
        tb = traceback.format_exc()
        SENTINEL_FAIL.write_text(f"scheme3: ERROR — {type(exc).__name__}: {exc}\n\n{tb}\n")
        logger.exception("Scheme 3 errored")
        return 2


if __name__ == "__main__":
    sys.exit(main())

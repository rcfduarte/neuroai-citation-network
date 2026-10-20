#!/usr/bin/env python3
"""Cross-citation flow between neuroscience and AI via the Semantic Scholar API.

INDEPENDENT cross-check of the OpenAlex analysis: different citation graph,
different field definition. Fields are defined by a VENUE ALLOW-LIST (reusing the
frozen snapshot's Scheme-2 whitelist) — because S2's field-of-study taxonomy is
too coarse to separate AI from CS or neuro from biology/medicine.

NOTE ON LEVELS vs SHAPE: venue-based shares are NOT directly comparable in
absolute level to OpenAlex's topic-based shares (different definitions + different
graph). The interpretable comparison is the *shape/trend* over time. Documented.

Method per (field, year):
    1. S2 bulk search → papers in that field's allow-list venues, that year.
    2. /paper/{id}/references (one call, returns cited papers' venues + years).
    3. Classify each cited paper's venue against BOTH allow-lists → within/target/other/unknown.
    4. Aggregate cross-share (per 1,000) + cluster bootstrap CI over papers.

Auth: export SEMANTIC_SCHOLAR_API_KEY. Resumable via <out>/cells.jsonl.

Usage:
    python s2_crosscite_sample.py --years 1990-2025 --n 800 --out OUTDIR
    python s2_crosscite_sample.py --years 2015,2020 --n 150 --out /tmp/s2val  # validation
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import time
from pathlib import Path

import requests

S2 = "https://api.semanticscholar.org/graph/v1"
KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
HDR = {"x-api-key": KEY} if KEY else {}

# Frozen venue allow-list (snapshot Scheme 2). Regex matched on normalized venue text.
VENUE_PATTERNS = {
    "ai": [
        r"neural information processing",
        r"\bneurips\b",
        r"\bnips\b",
        r"international conference on machine learning",
        r"\bicml\b",
        r"international conference on learning representations",
        r"\biclr\b",
        r"journal of machine learning research",
        r"\bjmlr\b",
        r"advancement of artificial intelligence",
        r"\baaai\b",
        r"joint conference on artificial intelligence",
        r"\bijcai\b",
        r"artificial intelligence and statistics",
        r"\baistats\b",
        r"computer vision and pattern recognition",
        r"\bcvpr\b",
        r"international conference on computer vision",
        r"\biccv\b",
        r"european conference on computer vision",
        r"\beccv\b",
        r"empirical methods in natural language processing",
        r"\bemnlp\b",
        r"association for computational linguistics",
        r"\bacl\b",
        r"nature machine intelligence",
        r"transactions on machine learning research",
        r"conference on learning theory",
        r"\bcolt\b",
    ],
    "neuro": [
        r"^neuron$",
        r"\bneuron\b",
        r"nature neuroscience",
        r"nature reviews neuroscience",
        r"journal of neuroscience",
        r"journal of computational neuroscience",
        r"current opinion in neurobiology",
        r"\belife\b",
        r"plos computational biology",
        r"cerebral cortex",
        r"neuroimage",
        r"^brain$",
        r"trends in neurosciences?",
    ],
}
AI_RE = [re.compile(p) for p in VENUE_PATTERNS["ai"]]
NEU_RE = [re.compile(p) for p in VENUE_PATTERNS["neuro"]]

log = logging.getLogger("s2")


def _norm(v):
    return re.sub(r"\s+", " ", (v or "").lower().strip())


def classify_venue(name):
    n = _norm(name)
    if not n:
        return "unknown"
    if any(r.search(n) for r in AI_RE):
        return "ai"
    if any(r.search(n) for r in NEU_RE):
        return "neuro"
    return "other"


def _get(url, params, tries=6):
    for t in range(tries):
        try:
            r = requests.get(url, params=params, headers=HDR, timeout=60)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 + 2**t)
                continue
            log.warning("HTTP %s %s", r.status_code, r.text[:160])
            time.sleep(2**t)
        except requests.RequestException as e:
            log.warning("req err %s", e)
            time.sleep(2**t)
    raise RuntimeError(f"S2 GET failed: {url} {params}")


def venue_query(field):
    # S2 bulk `venue` filter accepts a comma-separated list of venue names.
    names = {
        "ai": [
            "NeurIPS",
            "Neural Information Processing Systems",
            "ICML",
            "International Conference on Machine Learning",
            "ICLR",
            "Journal of Machine Learning Research",
            "AAAI",
            "IJCAI",
            "AISTATS",
            "Computer Vision and Pattern Recognition",
            "CVPR",
            "ICCV",
            "ECCV",
            "EMNLP",
            "Annual Meeting of the Association for Computational Linguistics",
            "Nature Machine Intelligence",
            "COLT",
        ],
        "neuro": [
            "Neuron",
            "Nature Neuroscience",
            "The Journal of Neuroscience",
            "Nature Reviews Neuroscience",
            "Current Opinion in Neurobiology",
            "eLife",
            "PLoS Computational Biology",
            "Journal of Computational Neuroscience",
            "Cerebral Cortex",
            "NeuroImage",
            "Brain",
            "Trends in Neurosciences",
        ],
    }[field]
    return ",".join(names)


def sample_papers(field, year, n):
    """Bulk-search field venues for `year`; return up to n paperIds (in-venue verified)."""
    ids, token, pulled = [], None, 0
    while len(ids) < n and pulled < 10000:
        params = {
            "venue": venue_query(field),
            "year": str(year),
            "fields": "paperId,year,publicationVenue,venue",
            "limit": 1000,
        }
        if token:
            params["token"] = token
        js = _get(f"{S2}/paper/search/bulk", params)
        data = js.get("data") or []
        for p in data:
            vname = (p.get("publicationVenue") or {}).get("name") or p.get("venue") or ""
            if classify_venue(vname) == field:  # client-side verify in-allow-list
                ids.append(p["paperId"])
        pulled += len(data)
        token = js.get("token")
        if not token or not data:
            break
        time.sleep(1.1)
    random.Random(year).shuffle(ids)
    return ids[:n]


def paper_refs(pid):
    """Return list of cited-paper venue classifications, or None if references are ELIDED.

    S2 returns data=None when the publisher (e.g. Springer Nature, Elsevier for some
    titles) has elided the references field. We must distinguish that from a genuine
    empty list — counting elided as 0 refs would bias the share. Elided -> None -> skip.
    """
    out, offset = [], 0
    while True:
        js = _get(
            f"{S2}/paper/{pid}/references",
            {"fields": "publicationVenue,venue", "limit": 1000, "offset": offset},
        )
        data = js.get("data")
        if data is None:
            return None  # elided by publisher
        for r in data:
            cp = r.get("citedPaper") or {}
            vname = (cp.get("publicationVenue") or {}).get("name") or cp.get("venue") or ""
            out.append(classify_venue(vname))
        if len(data) < 1000:
            break
        offset += 1000
        time.sleep(1.4)
    return out


def cell(field, year, n):
    target = "ai" if field == "neuro" else "neuro"
    pids = sample_papers(field, year, n)
    log.info("  %s %s: %d in-venue papers", field, year, len(pids))
    per_paper = []
    n_elided = 0
    n_failed = 0
    for i, pid in enumerate(pids):
        try:
            cls = paper_refs(pid)
        except RuntimeError as e:
            # Single-paper API failure (S2 sometimes 500s on specific paper IDs after 6 retries).
            # Treat as elided rather than failing the whole cell — preserves the cell's other 399 papers.
            n_failed += 1
            n_elided += 1
            log.warning("    paper %s unreachable -> treating as elided: %s", pid, str(e)[:120])
            time.sleep(1.4)
            continue
        if cls is None:  # publisher-elided references -> exclude, count it
            n_elided += 1
            time.sleep(1.4)
            continue
        w = sum(c == field for c in cls)
        t = sum(c == target for c in cls)
        o = sum(c == "other" for c in cls)
        per_paper.append((w, t, o))
        time.sleep(1.4)
        if (i + 1) % 50 == 0:
            log.info(
                "    %d/%d papers (%d elided, %d unreachable)", i + 1, len(pids), n_elided, n_failed
            )
    W = sum(x[0] for x in per_paper)
    T = sum(x[1] for x in per_paper)
    n_other = sum(x[2] for x in per_paper)
    denom = W + T + n_other
    share = (T / denom * 1000) if denom else float("nan")
    rng = random.Random(year)
    m = len(per_paper)
    boots = []
    for _ in range(500):
        bw = bt = bo = 0
        for _ in range(m):
            x = per_paper[rng.randrange(m)]
            bw += x[0]
            bt += x[1]
            bo += x[2]
        d = bw + bt + bo
        if d:
            boots.append(bt / d * 1000)
    boots.sort()
    lo = boots[int(0.025 * len(boots))] if boots else float("nan")
    hi = boots[int(0.975 * len(boots))] if boots else float("nan")
    n_sampled = len(pids)
    return {
        "source": "semantic_scholar",
        "direction": f"{field}_to_{target}",
        "field": field,
        "year": year,
        "n_papers": m,
        "n_sampled": n_sampled,
        "n_elided": n_elided,
        "n_unreachable": n_failed,
        "elision_rate": round(n_elided / n_sampled, 3) if n_sampled else None,
        "within": W,
        "target": T,
        "other": n_other,
        "per1000": round(share, 3),
        "ci_lo": round(lo, 3),
        "ci_hi": round(hi, 3),
        "n_refs_classified": denom,
    }


def parse_years(s):
    if "-" in s and "," not in s:
        a, b = s.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in s.split(",")]


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="1990-2025")
    ap.add_argument("--fields", default="neuro,ai")
    ap.add_argument("--n", type=int, default=800)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if not KEY:
        log.warning("No SEMANTIC_SCHOLAR_API_KEY set — running on the shared pool (slow, may 429).")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cells_path = out / "cells.jsonl"
    done = set()
    if cells_path.exists():
        for line in cells_path.read_text().splitlines():
            try:
                d = json.loads(line)
                done.add((d["field"], d["year"]))
            except Exception:
                pass
    todo = [
        (f, y)
        for y in parse_years(args.years)
        for f in args.fields.split(",")
        if (f, y) not in done
    ]
    log.info("cells to do: %d (skip %d)", len(todo), len(done))
    with cells_path.open("a") as fh:
        for f, y in todo:
            t0 = time.time()
            try:
                res = cell(f, y, args.n)
                fh.write(json.dumps(res) + "\n")
                fh.flush()
                log.info(
                    "DONE %s %s -> per1000=%.2f [%.2f,%.2f] (%.0fs)",
                    f,
                    y,
                    res["per1000"],
                    res["ci_lo"],
                    res["ci_hi"],
                    time.time() - t0,
                )
            except Exception as e:
                log.error("FAILED %s %s: %s", f, y, e)
    log.info("done -> %s", cells_path)


if __name__ == "__main__":
    main()

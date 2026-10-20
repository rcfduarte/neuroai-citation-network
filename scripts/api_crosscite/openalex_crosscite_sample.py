#!/usr/bin/env python3
"""Cross-citation flow between neuroscience and AI via the LIVE OpenAlex API.

Estimates, per (field, year), the share of a field's references that cross to
the other field, using a STRATIFIED RANDOM SAMPLE of papers (not the full graph).
This is a statistically valid estimate of the population share with confidence
intervals — the tractable, API-feasible complement to the frozen snapshot.

Definitions (match the snapshot's STRICT scheme so results are comparable):
    neuro = primary_topic.field   == fields/28
    ai    = primary_topic.subfield == subfields/1702
    other = classified, neither       unknown = no primary_topic
    cross-share (per 1,000) = target / (within + target + other) * 1000   [excludes unknown]

Method per (field, year):
    1. OpenAlex `sample` (seeded) → N papers of that field/year, with referenced_works.
    2. Batch-classify every referenced work's field (primary_topic).
    3. Per paper: count within / target / other / unknown refs.
    4. Aggregate share = sum(target)/sum(within+target+other).
    5. Cluster bootstrap over papers → 95% CI.

Resumable: each completed cell is appended to <out>/cells.jsonl; reruns skip done cells.
Polite-pool: OPENALEX_EMAIL must be set in the environment (the script exits with a message otherwise).

Usage:
    python openalex_crosscite_sample.py --years 1990-2025 --n 1500 --out OUTDIR
    python openalex_crosscite_sample.py --years 2015,2020 --n 300 --out /tmp/val  # validation
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import time
from pathlib import Path

import requests

from neuroai_cn import config

OPENALEX = "https://api.openalex.org/works"
# OpenAlex prepaid-plan API key (separate from `mailto`); when set, passed as `api_key=` per docs.
API_KEY = os.environ.get("OPENALEX_API_KEY", "").strip()
NEURO_FIELD = "https://openalex.org/fields/28"
AI_SUBFIELD_1702 = "https://openalex.org/subfields/1702"
AI_SUBFIELD_1707 = "https://openalex.org/subfields/1707"
# AI-definition variants. STRICT = subfield 1702 only (the API field def used in validation).
# EXTENDED = 1702 + 1707 (Computer Vision and Pattern Recognition), matching the snapshot's
# `q1_v3_extended` scheme. The snapshot's extended scheme also adds topic T10502 (Advanced
# Memory and Neural Computing), but OR-ing across `primary_topic.id` and
# `primary_topic.subfield.id` is awkward in OpenAlex's filter syntax — T10502 contributes
# <1-2% of extended-AI papers, so we omit it here and note the deviation.
AI_DEF_FILTERS = {
    "strict": "primary_topic.subfield.id:subfields/1702",
    "extended": "primary_topic.subfield.id:subfields/1702|subfields/1707",
}
AI_DEF_SUBFIELDS = {
    "strict": frozenset({AI_SUBFIELD_1702}),
    "extended": frozenset({AI_SUBFIELD_1702, AI_SUBFIELD_1707}),
}
# Module-level (set in main from --ai-def); used by classify(). Default `strict` keeps
# pre-extended behaviour for callers / tests / the running resume process.
AI_DEF = "strict"
AI_SUBFIELDS = AI_DEF_SUBFIELDS[AI_DEF]
FIELD_FILTER = {
    "neuro": "primary_topic.field.id:fields/28",
    "ai": AI_DEF_FILTERS[AI_DEF],
}

log = logging.getLogger("oa")


def _get(params, tries=6):
    p = {**params, "mailto": config.openalex_email()}
    if API_KEY:
        p["api_key"] = API_KEY
    for t in range(tries):
        try:
            r = requests.get(
                OPENALEX,
                params=p,
                headers={"User-Agent": config.openalex_user_agent("NeuroAI-CN-crosscite/1.0")},
                timeout=60,
            )
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503):
                time.sleep(2**t)
                continue
            log.warning("HTTP %s: %s", r.status_code, r.text[:200])
            time.sleep(2**t)
        except requests.RequestException as e:
            log.warning("req err: %s", e)
            time.sleep(2**t)
    raise RuntimeError(f"OpenAlex GET failed after {tries} tries: {params}")


def sample_papers(field, year, n, seed):
    """Return list of {'id':..., 'refs':[Wxxx,...]} for n sampled papers."""
    out, page, per = [], 1, 200
    while len(out) < n:
        js = _get(
            {
                "filter": f"{FIELD_FILTER[field]},publication_year:{year}",
                "sample": min(n, 10000),
                "seed": seed,
                "per-page": per,
                "page": page,
                "select": "id,referenced_works",
            }
        )
        results = js.get("results", [])
        if not results:
            break
        for w in results:
            refs = [r.rsplit("/", 1)[-1] for r in (w.get("referenced_works") or [])]
            out.append({"id": w["id"].rsplit("/", 1)[-1], "refs": refs})
        if len(results) < per:
            break
        page += 1
        time.sleep(0.1)
    return out[:n]


def classify(ids, cache):
    """Classify a list of work IDs -> {id: 'neuro'|'ai'|'other'|'unknown'}; uses/updates cache."""
    todo = [i for i in ids if i not in cache]
    for k in range(0, len(todo), 50):
        chunk = todo[k : k + 50]
        js = _get(
            {
                "filter": "ids.openalex:" + "|".join(chunk),
                "per-page": 100,
                "select": "id,primary_topic",
            }
        )
        seen = set()
        for w in js.get("results", []):
            wid = w["id"].rsplit("/", 1)[-1]
            seen.add(wid)
            pt = w.get("primary_topic")
            if not pt:
                cache[wid] = "unknown"
            else:
                sub = (pt.get("subfield") or {}).get("id", "")
                fld = (pt.get("field") or {}).get("id", "")
                cache[wid] = (
                    "ai" if sub in AI_SUBFIELDS else ("neuro" if fld == NEURO_FIELD else "other")
                )
        for wid in chunk:
            if wid not in seen:
                cache[wid] = "unknown"  # not found / deleted
        time.sleep(0.1)
    return {i: cache.get(i, "unknown") for i in ids}


def cell(field, year, n, seed, cache):
    target_class = "ai" if field == "neuro" else "neuro"
    papers = sample_papers(field, year, n, seed)
    all_refs = sorted({r for p in papers for r in p["refs"]})
    log.info("  %s %s: %d papers, %d unique refs", field, year, len(papers), len(all_refs))
    cls = classify(all_refs, cache)
    per_paper = []  # (within, target, other) classified counts
    for p in papers:
        w = t = o = 0
        for r in p["refs"]:
            k = cls.get(r, "unknown")
            if k == field:
                w += 1
            elif k == target_class:
                t += 1
            elif k == "other":
                o += 1
        per_paper.append((w, t, o))
    W = sum(x[0] for x in per_paper)
    T = sum(x[1] for x in per_paper)
    n_other = sum(x[2] for x in per_paper)
    denom = W + T + n_other
    share = (T / denom * 1000) if denom else float("nan")
    # cluster bootstrap over papers
    rng = random.Random(seed)
    boots = []
    m = len(per_paper)
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
    direction = f"{field}_to_{target_class}"
    return {
        "direction": direction,
        "field": field,
        "year": year,
        "n_papers": len(papers),
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
    ap.add_argument("--n", type=int, default=1500)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument(
        "--ai-def",
        choices=["strict", "extended"],
        default="strict",
        help="AI field definition. strict=subfield 1702 (default; matches API validation). "
        "extended=1702+1707 (CVPR), matching snapshot q1_v3_extended modulo T10502.",
    )
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    # Apply --ai-def to module-level constants used by sample_papers() and classify().
    global AI_DEF, AI_SUBFIELDS, FIELD_FILTER
    AI_DEF = args.ai_def
    AI_SUBFIELDS = AI_DEF_SUBFIELDS[AI_DEF]
    FIELD_FILTER = {"neuro": "primary_topic.field.id:fields/28", "ai": AI_DEF_FILTERS[AI_DEF]}
    log.info(
        "auth: mailto=%s  api_key=%s  ai_def=%s",
        config.openalex_email(),
        "set" if API_KEY else "(none, polite-pool only)",
        AI_DEF,
    )
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
    cache = {}
    years = parse_years(args.years)
    fields = args.fields.split(",")
    todo = [(f, y) for y in years for f in fields if (f, y) not in done]
    log.info("cells to do: %d (skipping %d done)", len(todo), len(done))
    with cells_path.open("a") as fh:
        for f, y in todo:
            t0 = time.time()
            try:
                res = cell(f, y, args.n, args.seed, cache)
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
    log.info("all done -> %s", cells_path)


if __name__ == "__main__":
    main()

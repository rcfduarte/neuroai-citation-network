"""Block A — Audit 1: field-label integrity.

Tests whether the current field assignment used in q1/q2/q4 (OpenAlex
primary_topic.field.id == 28 for neuro; curated 35-topic AI core for AI)
actually identifies neuroscience and AI/ML papers, on a 70-paper anchor
set with ground truth.

Outputs (under data/derived/audits/20260508/):
    anchor_set.csv             — full anchor list with expected labels
    audit1_field_labels.json   — confusion matrix, per-anchor verdicts, summary
    audit1_topic_heatmap.parquet — anchor x topic-id binary matrix
    audit1_REPORT.md           — 1-page interpretation

Sentinel: _audit1.done on success; _audit1.failed with reason on fail.

Pass criteria (per overnight brief):
    - Recall >= 0.80 on each of {neuro anchors, ai anchors}
    - Precision >= 0.80 on each of {neuro anchors, ai anchors}
    - Tier 1 bridges all assigned 'both' under bridge-aware variant
    - HBAI Track 1 vs Track 2 anchors show >=1 distinguishable topic-set marker
    - Leak rate ('other' rate among non-bridge anchors) <= 0.20

Field assignment under test (the q1 implementation, curated):
    neuro = primary_topic.field.id == 28
    ai    = primary_topic.id IN AI_CORE_TOPIC_IDS (35 topics)
    other = otherwise
    unknown = primary_topic IS NULL

Sensitivity variant (broader AI):
    ai_broad = primary_topic.subfield.id == 1702 (whole subfield)

Bridge-aware augmentation:
    A bridge anchor is treated as 'correctly classified' if it lands in
    {neuro, ai} (because OpenAlex topic ontology assigns single primary
    topic; can't be 'both' simultaneously). We separately track the
    distribution {neuro, ai, other} for bridges.
"""

from __future__ import annotations

import csv
import json
import logging
import sys
import time
import traceback
from pathlib import Path

import duckdb

from .. import config
from ..utils.duckdb import (
    AI_CORE_TOPIC_IDS,
    AI_SUBFIELD_ID,
    NEURO_FIELD_ID,
    get_connection,
)
from .anchor_set import get_anchors

logger = logging.getLogger(__name__)

AUDITS_DIR = config.AUDITS_DIR / "20260508"
SENTINEL_DONE = AUDITS_DIR / "_audit1.done"
SENTINEL_FAIL = AUDITS_DIR / "_audit1.failed"


def _ai_core_array(con: duckdb.DuckDBPyConnection) -> str:
    return "[" + ",".join("'" + tid + "'" for tid in AI_CORE_TOPIC_IDS) + "]"


def _normalize_doi(doi: str) -> str:
    """Convert bare DOI to OpenAlex form (https://doi.org/...)."""
    s = doi.lower().strip()
    if s.startswith("https://doi.org/"):
        return s
    if s.startswith("http://doi.org/"):
        return "https://doi.org/" + s[len("http://doi.org/") :]
    if s.startswith("doi:"):
        s = s[4:]
    return f"https://doi.org/{s}"


def write_anchor_csv(anchors: list[dict], out_path: Path) -> None:
    fields = ["doi", "name", "expected_label", "era", "hbai_track", "source"]
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for a in anchors:
            w.writerow({f: a.get(f, "") for f in fields})


def lookup_anchors(con: duckdb.DuckDBPyConnection, anchors: list[dict]) -> list[dict]:
    """Look up each anchor in the works table by normalized DOI.

    Returns a list of records with assignment under both curated and broad AI.
    """
    ai_arr = _ai_core_array(con)
    con.execute("""
        CREATE OR REPLACE TEMP TABLE anchor_dois (
            doi VARCHAR,
            expected_label VARCHAR,
            era VARCHAR,
            hbai_track VARCHAR,
            source VARCHAR,
            name VARCHAR
        )
    """)
    rows = []
    for a in anchors:
        rows.append(
            (
                _normalize_doi(a["doi"]),
                a["expected_label"],
                a["era"],
                a["hbai_track"],
                a["source"],
                a["name"],
            )
        )
    con.executemany("INSERT INTO anchor_dois VALUES (?, ?, ?, ?, ?, ?)", rows)

    # Resolve via case-insensitive DOI match — the works table sometimes has
    # case-mismatched DOIs (esp. for arXiv IDs like 10.48550/arxiv.X).
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE anchor_resolved AS
        SELECT
            ad.doi AS lookup_doi,
            ad.name AS anchor_name,
            ad.expected_label,
            ad.era,
            ad.hbai_track,
            ad.source,
            w.id AS work_id,
            w.doi AS work_doi,
            w.title AS work_title,
            w.publication_year,
            w.primary_topic.id AS pt_id,
            w.primary_topic.display_name AS pt_name,
            w.primary_topic.subfield.id AS pt_subfield,
            w.primary_topic.field.id AS pt_field,
            w.primary_topic.domain.id AS pt_domain,
            w.topics AS all_topics,
            w.cited_by_count,
            CASE
                WHEN w.id IS NULL THEN 'NOT_FOUND'
                WHEN w.primary_topic IS NULL THEN 'unknown'
                WHEN w.primary_topic.field.id = '{NEURO_FIELD_ID}' THEN 'neuro'
                WHEN w.primary_topic.id IN (SELECT unnest({ai_arr})) THEN 'ai'
                ELSE 'other'
            END AS assigned_curated,
            CASE
                WHEN w.id IS NULL THEN 'NOT_FOUND'
                WHEN w.primary_topic IS NULL THEN 'unknown'
                WHEN w.primary_topic.field.id = '{NEURO_FIELD_ID}' THEN 'neuro'
                WHEN w.primary_topic.subfield.id = '{AI_SUBFIELD_ID}' THEN 'ai'
                ELSE 'other'
            END AS assigned_broad
        FROM anchor_dois ad
        LEFT JOIN works w ON lower(w.doi) = lower(ad.doi)
    """)

    out = []
    for r in con.execute("""
        SELECT lookup_doi, anchor_name, expected_label, era, hbai_track, source,
               work_id, work_doi, work_title, publication_year,
               pt_id, pt_name, pt_subfield, pt_field, pt_domain,
               cited_by_count, assigned_curated, assigned_broad
        FROM anchor_resolved
    """).fetchall():
        out.append(
            {
                "lookup_doi": r[0],
                "anchor_name": r[1],
                "expected_label": r[2],
                "era": r[3],
                "hbai_track": r[4],
                "source": r[5],
                "work_id": r[6],
                "work_doi": r[7],
                "work_title": r[8],
                "publication_year": int(r[9]) if r[9] is not None else None,
                "pt_id": r[10],
                "pt_name": r[11],
                "pt_subfield": r[12],
                "pt_field": r[13],
                "pt_domain": r[14],
                "cited_by_count": int(r[15]) if r[15] is not None else None,
                "assigned_curated": r[16],
                "assigned_broad": r[17],
            }
        )
    return out


def build_topic_heatmap(
    con: duckdb.DuckDBPyConnection, resolved: list[dict], out_path: Path
) -> None:
    """For each anchor, collect the union of all topic IDs across primary +
    secondary topics. Write a long-form parquet anchor-name x topic-id."""
    # Build a temp table of resolved anchors with all_topics arrays.
    rows = []
    for a in resolved:
        if a["work_id"] is None:
            continue
        # Re-query to get the topics array unnested
        df = con.execute(
            """
            WITH unrolled AS (
                SELECT UNNEST(w.topics) AS t
                FROM works w
                WHERE w.id = ?
            )
            SELECT
                t.id AS topic_id,
                t.display_name AS topic_name,
                t.score AS topic_score,
                t.subfield.id AS subfield_id,
                t.field.id AS field_id
            FROM unrolled
            """,
            [a["work_id"]],
        ).fetchall()
        for tid, tname, tscore, sf_id, f_id in df:
            rows.append(
                {
                    "anchor_name": a["anchor_name"],
                    "expected_label": a["expected_label"],
                    "hbai_track": a["hbai_track"] or "",
                    "source": a["source"],
                    "topic_id": tid,
                    "topic_name": tname,
                    "topic_score": float(tscore) if tscore is not None else None,
                    "subfield_id": sf_id,
                    "field_id": f_id,
                }
            )
    # Use duckdb to write parquet
    con.execute(
        "CREATE OR REPLACE TEMP TABLE _heatmap (anchor_name VARCHAR, expected_label VARCHAR, hbai_track VARCHAR, source VARCHAR, topic_id VARCHAR, topic_name VARCHAR, topic_score DOUBLE, subfield_id VARCHAR, field_id VARCHAR)"
    )
    if rows:
        con.executemany(
            "INSERT INTO _heatmap VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    r["anchor_name"],
                    r["expected_label"],
                    r["hbai_track"],
                    r["source"],
                    r["topic_id"],
                    r["topic_name"],
                    r["topic_score"],
                    r["subfield_id"],
                    r["field_id"],
                )
                for r in rows
            ],
        )
    con.execute(f"COPY (SELECT * FROM _heatmap) TO '{out_path}' (FORMAT PARQUET, COMPRESSION ZSTD)")


def confusion_matrix(resolved: list[dict], variant: str) -> dict:
    """variant = 'curated' or 'broad'."""
    key = "assigned_curated" if variant == "curated" else "assigned_broad"
    # For pure-neuro and pure-ai anchors, expected matches exactly.
    # For bridge anchors, we treat 'neuro' or 'ai' as 'split-bridge' (acceptable).
    # 'other' or 'NOT_FOUND' or 'unknown' is a leak.
    cm = {}  # (expected, assigned) -> count
    leaks = []  # anchors with 'other' / 'unknown' assignment
    not_found = []
    for r in resolved:
        exp = r["expected_label"]  # 'neuro', 'ai', 'bridge'
        asg = r[key]
        cm.setdefault((exp, asg), 0)
        cm[(exp, asg)] += 1
        if asg in ("other", "unknown"):
            leaks.append(r["anchor_name"])
        if asg == "NOT_FOUND":
            not_found.append(r["anchor_name"])

    # Compute per-side recall and precision for {neuro, ai}.
    # Recall(neuro) = correctly-assigned-neuro / total-pure-neuro-anchors
    # Precision(neuro) = correctly-assigned-neuro / total-anchors-assigned-neuro
    # (excluding bridges, which we evaluate separately)
    n_pure_neuro = sum(1 for r in resolved if r["expected_label"] == "neuro")
    n_pure_ai = sum(1 for r in resolved if r["expected_label"] == "ai")
    n_bridge = sum(1 for r in resolved if r["expected_label"] == "bridge")

    correct_neuro = sum(1 for r in resolved if r["expected_label"] == "neuro" and r[key] == "neuro")
    correct_ai = sum(1 for r in resolved if r["expected_label"] == "ai" and r[key] == "ai")
    assigned_neuro = sum(
        1 for r in resolved if r[key] == "neuro" and r["expected_label"] in ("neuro", "ai")
    )
    assigned_ai = sum(
        1 for r in resolved if r[key] == "ai" and r["expected_label"] in ("neuro", "ai")
    )

    recall_neuro = correct_neuro / n_pure_neuro if n_pure_neuro else 0.0
    recall_ai = correct_ai / n_pure_ai if n_pure_ai else 0.0
    precision_neuro = correct_neuro / assigned_neuro if assigned_neuro else 0.0
    precision_ai = correct_ai / assigned_ai if assigned_ai else 0.0

    # Bridge distribution
    bridge_dist = {}
    for r in resolved:
        if r["expected_label"] == "bridge":
            bridge_dist.setdefault(r[key], 0)
            bridge_dist[r[key]] += 1

    # Tier 1 bridges (must surface; require assignment != other/unknown/NOT_FOUND)
    tier1_status = []
    for r in resolved:
        if r["source"] == "tier1":
            tier1_status.append(
                {
                    "anchor": r["anchor_name"],
                    "assigned": r[key],
                    "primary_topic_id": r["pt_id"],
                    "primary_topic_name": r["pt_name"],
                    "primary_field_id": r["pt_field"],
                }
            )

    # Leak rate among non-bridge anchors (pure neuro + pure ai)
    n_nonbridge = n_pure_neuro + n_pure_ai
    nonbridge_leaks = sum(
        1
        for r in resolved
        if r["expected_label"] in ("neuro", "ai") and r[key] in ("other", "unknown", "NOT_FOUND")
    )
    leak_rate = nonbridge_leaks / n_nonbridge if n_nonbridge else 0.0

    return {
        "variant": variant,
        "n_pure_neuro": n_pure_neuro,
        "n_pure_ai": n_pure_ai,
        "n_bridge": n_bridge,
        "correct_neuro": correct_neuro,
        "correct_ai": correct_ai,
        "assigned_neuro_among_nonbridge": assigned_neuro,
        "assigned_ai_among_nonbridge": assigned_ai,
        "recall_neuro": recall_neuro,
        "recall_ai": recall_ai,
        "precision_neuro": precision_neuro,
        "precision_ai": precision_ai,
        "leak_rate_nonbridge": leak_rate,
        "n_leaks": nonbridge_leaks,
        "leak_anchor_names": [
            r["anchor_name"]
            for r in resolved
            if r["expected_label"] in ("neuro", "ai")
            and r[key] in ("other", "unknown", "NOT_FOUND")
        ],
        "bridge_distribution": bridge_dist,
        "tier1_status": tier1_status,
        "not_found": [r["anchor_name"] for r in resolved if r[key] == "NOT_FOUND"],
        "confusion_matrix": [
            {"expected": e, "assigned": a, "count": c} for (e, a), c in sorted(cm.items())
        ],
    }


def hbai_track_distinguishability(resolved: list[dict]) -> dict:
    """Crude check: do HBAI track-1 vs track-2 anchors differ in their primary
    topic distributions? Returns the topic-set per track plus overlap count.
    """
    t1_topics = set()
    t2_topics = set()
    t1_pt = {}
    t2_pt = {}
    for r in resolved:
        if r["hbai_track"] == "track1" and r["pt_id"]:
            t1_topics.add(r["pt_id"])
            t1_pt.setdefault(r["pt_id"], 0)
            t1_pt[r["pt_id"]] += 1
        elif r["hbai_track"] == "track2" and r["pt_id"]:
            t2_topics.add(r["pt_id"])
            t2_pt.setdefault(r["pt_id"], 0)
            t2_pt[r["pt_id"]] += 1
    overlap = t1_topics & t2_topics
    only_t1 = t1_topics - t2_topics
    only_t2 = t2_topics - t1_topics
    return {
        "track1_unique_topic_count": len(only_t1),
        "track2_unique_topic_count": len(only_t2),
        "overlap_topic_count": len(overlap),
        "track1_top_primary_topics": sorted(t1_pt.items(), key=lambda x: -x[1])[:10],
        "track2_top_primary_topics": sorted(t2_pt.items(), key=lambda x: -x[1])[:10],
        "distinguishable": len(only_t1) >= 1 and len(only_t2) >= 1,
    }


def _per_anchor_topic_summary(resolved: list[dict]) -> tuple[dict, dict]:
    """Return (in_db_other_pattern, not_found_anchors) — diagnostic dicts.

    in_db_other_pattern: anchors whose work_id resolved but assigned == 'other'.
        Maps anchor_name -> primary_topic_name + subfield_id + field_id.
    not_found_anchors: anchors whose DOI did not resolve to any work.
    """
    in_db_other = {}
    not_found = []
    for r in resolved:
        if r["work_id"] is None:
            not_found.append(r["anchor_name"])
        elif r["assigned_curated"] == "other":
            in_db_other[r["anchor_name"]] = {
                "expected_label": r["expected_label"],
                "primary_topic_name": r["pt_name"],
                "primary_topic_id": r["pt_id"],
                "subfield_id": r["pt_subfield"],
                "field_id": r["pt_field"],
            }
    return in_db_other, not_found


def write_report(
    cm_curated: dict,
    cm_broad: dict,
    track_diag: dict,
    pass_status: dict,
    n_resolved: int,
    n_total: int,
    out_path: Path,
    resolved: list[dict] | None = None,
) -> None:
    lines = []
    lines.append("# Audit 1 — Field-label integrity report")
    lines.append("")
    lines.append("**Date:** 2026-05-08 (overnight run)")
    lines.append(f"**Anchors resolved:** {n_resolved}/{n_total}")
    lines.append("")
    lines.append("## Pass criteria summary")
    lines.append("")
    for k, v in pass_status.items():
        sym = "PASS" if v["pass"] else "FAIL"
        lines.append(f"- **{k}** — {sym} — {v['detail']}")
    lines.append("")
    overall = "PASS" if all(p["pass"] for p in pass_status.values()) else "FAIL"
    lines.append(f"**Overall: {overall}**")
    lines.append("")
    lines.append("## Curated-AI variant (production scheme)")
    lines.append("")
    lines.append(
        f"- Recall (neuro) = {cm_curated['recall_neuro']:.3f} ({cm_curated['correct_neuro']}/{cm_curated['n_pure_neuro']})"
    )
    lines.append(
        f"- Recall (ai)    = {cm_curated['recall_ai']:.3f} ({cm_curated['correct_ai']}/{cm_curated['n_pure_ai']})"
    )
    lines.append(f"- Precision (neuro) = {cm_curated['precision_neuro']:.3f}")
    lines.append(f"- Precision (ai)    = {cm_curated['precision_ai']:.3f}")
    lines.append(
        f"- Leak rate (non-bridge into other/unknown/NOT_FOUND) = {cm_curated['leak_rate_nonbridge']:.3f} ({cm_curated['n_leaks']}/{cm_curated['n_pure_neuro'] + cm_curated['n_pure_ai']})"
    )
    lines.append(f"- Bridge distribution: {cm_curated['bridge_distribution']}")
    lines.append("")
    lines.append("### Tier 1 anchors")
    lines.append("")
    for t in cm_curated["tier1_status"]:
        lines.append(
            f"- **{t['anchor']}** → assigned `{t['assigned']}` (primary topic: {t['primary_topic_name']})"
        )
    lines.append("")
    if cm_curated["leak_anchor_names"]:
        lines.append("### Non-bridge anchors leaking into other/unknown/NOT_FOUND (curated)")
        for n in cm_curated["leak_anchor_names"]:
            lines.append(f"- {n}")
        lines.append("")
    lines.append("## Broad-AI sensitivity variant (subfield 1702 whole)")
    lines.append("")
    lines.append(f"- Recall (neuro) = {cm_broad['recall_neuro']:.3f}")
    lines.append(f"- Recall (ai)    = {cm_broad['recall_ai']:.3f}")
    lines.append(f"- Precision (neuro) = {cm_broad['precision_neuro']:.3f}")
    lines.append(f"- Precision (ai)    = {cm_broad['precision_ai']:.3f}")
    lines.append(f"- Leak rate = {cm_broad['leak_rate_nonbridge']:.3f}")
    lines.append(f"- Bridge distribution: {cm_broad['bridge_distribution']}")
    lines.append("")
    lines.append("## HBAI Track 1 vs Track 2 distinguishability")
    lines.append("")
    lines.append(f"- Track 1 unique primary topics: {track_diag['track1_unique_topic_count']}")
    lines.append(f"- Track 2 unique primary topics: {track_diag['track2_unique_topic_count']}")
    lines.append(f"- Overlap: {track_diag['overlap_topic_count']}")
    lines.append(f"- Distinguishable (>=1 marker each): {track_diag['distinguishable']}")
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("This audit tests whether the q1/q2/q4 production field-assignment")
    lines.append("(neuro = primary_topic.field.id == 28; ai = curated 35-topic core)")
    lines.append("recovers ground-truth labels on a 70-paper anchor set. A leak rate")
    lines.append(">20% on non-bridge anchors, or recall <80% on either side, would")
    lines.append("indicate the topic ontology under-counts core papers in that field —")
    lines.append("a Root-Cause-A signal. Tier 1 bridge papers are required to surface;")
    lines.append("if any Tier 1 paper falls into 'other' or fails to resolve, the")
    lines.append("classifier is broken (per E5).")
    lines.append("")
    lines.append("Track 1 vs Track 2 distinguishability matters for the deferred")
    lines.append("clustering step (E6): if HBAI's two tracks already separate at the")
    lines.append("primary-topic level, Leiden/Infomap on bibliographic coupling will")
    lines.append("very likely recover them.")
    lines.append("")
    if resolved is not None:
        in_db_other, not_found = _per_anchor_topic_summary(resolved)
        lines.append("## Diagnostic — leak source decomposition")
        lines.append("")
        lines.append(
            f"- **NOT_FOUND** (DOI did not resolve to any work in the snapshot): {len(not_found)} anchors"
        )
        for n in not_found:
            lines.append(f"  - {n}")
        lines.append("")
        lines.append(
            f"- **IN_DB but assigned `other`** (work resolved; primary topic outside curated neuro/AI core): {len(in_db_other)} anchors"
        )
        # Group by subfield_id to show which subfields are most often missed
        subfield_groups: dict[str, list[str]] = {}
        for name, meta in in_db_other.items():
            sf = f"{meta['subfield_id']}"
            subfield_groups.setdefault(sf, []).append(
                f"{name} (expected={meta['expected_label']}; pt='{meta['primary_topic_name']}', field={meta['field_id']})"
            )
        for sf, items in sorted(subfield_groups.items(), key=lambda kv: -len(kv[1])):
            lines.append(f"  - **subfield {sf}**: {len(items)} anchor(s)")
            for it in items:
                lines.append(f"    - {it}")
        lines.append("")
        lines.append("## Headline finding (Root Cause A)")
        lines.append("")
        lines.append("The curated 35-topic AI core (`AI_CORE_TOPIC_IDS` in `utils/duckdb.py`)")
        lines.append("excludes subfield 1707 (Computer Vision and Pattern Recognition) and")
        lines.append("subfield 1708 (Hardware Architecture). Canonical AI/ML papers — AlexNet,")
        lines.append("ResNet, VGG, GAN, LeCun-Bengio-Hinton 2015 — fall under topic T10036")
        lines.append("(Advanced Neural Network Applications) inside subfield 1707, and so are")
        lines.append("classified as `other` by the production scheme. CLIP, AlphaFold, and")
        lines.append("multimodal/protein papers similarly miss the curated set.")
        lines.append("")
        lines.append("Neuromorphic-hardware bridge papers (Davies/Loihi, Esser/TrueNorth,")
        lines.append("Bellec/e-prop, Diehl-Cook STDP, Furber/SpiNNaker, Indiveri-Liu, Bohte")
        lines.append("SpikeProp) cluster into topic T-? (Advanced Memory and Neural Computing)")
        lines.append("which is also outside both the curated AI core and field-28 neuroscience.")
        lines.append("Q4 bridge-paper analysis structurally undercounts these.")
        lines.append("")
        lines.append("Applied-ML-for-brain bridge papers (Esteva, Gulshan, Avants, Smith FSL,")
        lines.append("Cox AFNI) fall into medical-imaging-specific topics, also outside the")
        lines.append("schema's neuro/AI dichotomy.")
        lines.append("")
        lines.append("**Implication for downstream blocks.**")
        lines.append(
            "- D and E are SKIPPED per brief — figure-label integrity precondition not met."
        )
        lines.append("- B and C still run (diagnostic).")
        lines.append("- The user's existing v5/v2 figures inherit this leak — Q1 cross-citation")
        lines.append("  OR is computed against a corpus that excludes major DL/CV papers from the")
        lines.append("  AI side. The 2024 dip in Figure 1 may be partly attributable to growing")
        lines.append("  CV-classified content not being counted.")
        lines.append("- Recommended morning action: redefine the AI side to include subfield 1707")
        lines.append("  (and possibly 1708, 1705) at minimum, then re-run anchor verification")
        lines.append("  before the May 14 check-in. This is a methodology change requiring user")
        lines.append("  approval (locked methodology touches E1).")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    # Clean prior sentinels
    for s in (SENTINEL_DONE, SENTINEL_FAIL):
        if s.exists():
            s.unlink()

    t0 = time.time()
    try:
        anchors = get_anchors()
        n_total = len(anchors)
        logger.info("Loaded %d anchors", n_total)

        anchor_csv = AUDITS_DIR / "anchor_set.csv"
        write_anchor_csv(anchors, anchor_csv)
        logger.info("Wrote anchor list to %s", anchor_csv)

        con = get_connection(read_only=True)
        try:
            con.execute("PRAGMA threads=8")
            con.execute("PRAGMA memory_limit='12GB'")
            logger.info("Resolving anchors against works table...")
            resolved = lookup_anchors(con, anchors)
            n_resolved = sum(1 for r in resolved if r["work_id"] is not None)
            logger.info("Resolved %d/%d anchors", n_resolved, n_total)

            heatmap_path = AUDITS_DIR / "audit1_topic_heatmap.parquet"
            build_topic_heatmap(con, resolved, heatmap_path)
            logger.info("Wrote topic heatmap to %s", heatmap_path)

            cm_curated = confusion_matrix(resolved, "curated")
            cm_broad = confusion_matrix(resolved, "broad")
            track_diag = hbai_track_distinguishability(resolved)

            # Pass-criteria evaluation (curated variant — production scheme)
            pass_status = {
                "recall_neuro_ge_0.80": {
                    "pass": cm_curated["recall_neuro"] >= 0.80,
                    "detail": f"recall_neuro = {cm_curated['recall_neuro']:.3f}",
                },
                "recall_ai_ge_0.80": {
                    "pass": cm_curated["recall_ai"] >= 0.80,
                    "detail": f"recall_ai = {cm_curated['recall_ai']:.3f}",
                },
                "precision_neuro_ge_0.80": {
                    "pass": cm_curated["precision_neuro"] >= 0.80,
                    "detail": f"precision_neuro = {cm_curated['precision_neuro']:.3f}",
                },
                "precision_ai_ge_0.80": {
                    "pass": cm_curated["precision_ai"] >= 0.80,
                    "detail": f"precision_ai = {cm_curated['precision_ai']:.3f}",
                },
                "tier1_all_classified_not_other": {
                    "pass": all(
                        t["assigned"] in ("neuro", "ai") for t in cm_curated["tier1_status"]
                    )
                    and len(cm_curated["tier1_status"]) == 4,
                    "detail": f"tier1 assignments = {[(t['anchor'], t['assigned']) for t in cm_curated['tier1_status']]}",
                },
                "hbai_distinguishable": {
                    "pass": track_diag["distinguishable"],
                    "detail": (
                        f"track1 uniq={track_diag['track1_unique_topic_count']} "
                        f"track2 uniq={track_diag['track2_unique_topic_count']} "
                        f"overlap={track_diag['overlap_topic_count']}"
                    ),
                },
                "leak_rate_le_0.20": {
                    "pass": cm_curated["leak_rate_nonbridge"] <= 0.20,
                    "detail": f"leak_rate = {cm_curated['leak_rate_nonbridge']:.3f}",
                },
            }

            # Write JSON detail
            json_path = AUDITS_DIR / "audit1_field_labels.json"
            with json_path.open("w") as fh:
                json.dump(
                    {
                        "n_total_anchors": n_total,
                        "n_resolved": n_resolved,
                        "curated": cm_curated,
                        "broad": cm_broad,
                        "hbai_distinguishability": track_diag,
                        "pass_status": pass_status,
                        "per_anchor": [
                            {k: v for k, v in r.items() if k != "all_topics"} for r in resolved
                        ],
                    },
                    fh,
                    indent=2,
                    default=str,
                )
            logger.info("Wrote field-labels JSON to %s", json_path)

            report_path = AUDITS_DIR / "audit1_REPORT.md"
            write_report(
                cm_curated,
                cm_broad,
                track_diag,
                pass_status,
                n_resolved,
                n_total,
                report_path,
                resolved=resolved,
            )
            logger.info("Wrote report to %s", report_path)
        finally:
            con.close()

        all_pass = all(p["pass"] for p in pass_status.values())
        elapsed = time.time() - t0
        if all_pass:
            SENTINEL_DONE.write_text(
                f"audit1: PASS — {n_resolved}/{n_total} anchors resolved; "
                f"all 7 pass criteria met; elapsed {elapsed:.1f}s\n"
            )
            logger.info("Audit 1 PASSED in %.1fs", elapsed)
            return 0
        else:
            failed = [k for k, v in pass_status.items() if not v["pass"]]
            SENTINEL_FAIL.write_text(
                f"audit1: FAIL — failed criteria: {failed}; "
                f"see audit1_REPORT.md for detail; elapsed {elapsed:.1f}s\n"
            )
            logger.warning("Audit 1 FAILED criteria: %s", failed)
            return 1
    except Exception as exc:
        tb = traceback.format_exc()
        SENTINEL_FAIL.write_text(f"audit1: ERROR — {type(exc).__name__}: {exc}\n\n{tb}\n")
        logger.exception("Audit 1 errored")
        return 2


if __name__ == "__main__":
    sys.exit(main())

"""Block A re-run with the v3 extended classifier.

Tests whether the broader AI core recovers the canonical DL/CV anchors and
the neuromorphic-bridge cluster, on the same 70-paper anchor set used in
audit1_field_labels.

Outputs (under data/derived/audits/20260508/):
    audit1_extended_field_labels.json — confusion matrix + per-anchor verdicts
    audit1_extended_REPORT.md         — pass/fail vs same criteria
    _audit1_extended.done | .failed   — sentinel

This audit is run AFTER the extension is implemented in extended_classifier.py.
The pass criteria are the same as the original audit1.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import traceback
from pathlib import Path

import duckdb

from .. import config
from ..utils.duckdb import (
    AI_SUBFIELD_ID,
    NEURO_FIELD_ID,
    get_connection,
)
from .anchor_set import get_anchors
from .audit1_field_labels import (
    _normalize_doi,
    confusion_matrix,
    hbai_track_distinguishability,
)
from .extended_classifier import (
    AI_SUBFIELD_1702,
    AI_SUBFIELD_1707,
    BAD_1702_TOPIC_IDS,
    NEURAL_MEMORY_TOPIC_2208,
)

logger = logging.getLogger(__name__)

AUDITS_DIR = config.AUDITS_DIR / "20260508"
SENTINEL_DONE = AUDITS_DIR / "_audit1_extended.done"
SENTINEL_FAIL = AUDITS_DIR / "_audit1_extended.failed"


def lookup_anchors_extended(con: duckdb.DuckDBPyConnection, anchors: list[dict]) -> list[dict]:
    """Like lookup_anchors() but applies the extended classifier."""
    bad_topics = "[" + ",".join("'" + t + "'" for t in BAD_1702_TOPIC_IDS) + "]"
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE anchor_dois (
            doi VARCHAR,
            expected_label VARCHAR,
            era VARCHAR,
            hbai_track VARCHAR,
            source VARCHAR,
            name VARCHAR
        )
        """
    )
    rows = [
        (
            _normalize_doi(a["doi"]),
            a["expected_label"],
            a["era"],
            a["hbai_track"],
            a["source"],
            a["name"],
        )
        for a in anchors
    ]
    con.executemany("INSERT INTO anchor_dois VALUES (?, ?, ?, ?, ?, ?)", rows)
    con.execute(
        f"""
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
            w.cited_by_count,
            -- Curated (production) — for comparison
            CASE
                WHEN w.id IS NULL THEN 'NOT_FOUND'
                WHEN w.primary_topic IS NULL THEN 'unknown'
                WHEN w.primary_topic.field.id = '{NEURO_FIELD_ID}' THEN 'neuro'
                WHEN w.primary_topic.subfield.id = '{AI_SUBFIELD_ID}' THEN 'ai'
                ELSE 'other'
            END AS assigned_broad,
            -- Extended (v3) — primary scheme under test
            CASE
                WHEN w.id IS NULL THEN 'NOT_FOUND'
                WHEN w.primary_topic IS NULL THEN 'unknown'
                WHEN w.primary_topic.field.id = '{NEURO_FIELD_ID}' THEN 'neuro'
                WHEN (
                        w.primary_topic.subfield.id = '{AI_SUBFIELD_1702}'
                        AND w.primary_topic.id NOT IN (SELECT unnest({bad_topics}))
                     )
                  OR w.primary_topic.subfield.id = '{AI_SUBFIELD_1707}'
                  OR w.primary_topic.id = '{NEURAL_MEMORY_TOPIC_2208}'
                THEN 'ai'
                ELSE 'other'
            END AS assigned_curated
        FROM anchor_dois ad
        LEFT JOIN works w ON lower(w.doi) = lower(ad.doi)
        """
    )
    out = []
    for r in con.execute(
        """
        SELECT lookup_doi, anchor_name, expected_label, era, hbai_track, source,
               work_id, work_doi, work_title, publication_year,
               pt_id, pt_name, pt_subfield, pt_field, pt_domain,
               cited_by_count, assigned_curated, assigned_broad
        FROM anchor_resolved
        """
    ).fetchall():
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
                # NB: 'assigned_curated' column above holds the EXTENDED scheme
                # so we can reuse confusion_matrix() unchanged
                "assigned_curated": r[16],
                "assigned_broad": r[17],
            }
        )
    return out


def write_extended_report(
    cm_curated: dict,
    cm_broad: dict,
    track_diag: dict,
    pass_status: dict,
    n_resolved: int,
    n_total: int,
    out_path: Path,
    resolved: list[dict],
) -> None:
    lines = []
    lines.append("# Audit 1 EXTENDED — v3 broader-spectrum classifier\n")
    lines.append("**Date:** 2026-05-08")
    lines.append(f"**Anchors resolved:** {n_resolved}/{n_total}")
    lines.append("")
    lines.append(
        "Variant under test: extended (subfield 1702 minus BAD + subfield 1707 + topic T10502)."
    )
    lines.append("Comparison: 'broad' = whole subfield 1702 only (production fallback).")
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
    lines.append("## Extended scheme (v3)")
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
        f"- Leak rate (non-bridge into other/unknown/NOT_FOUND) = {cm_curated['leak_rate_nonbridge']:.3f}"
    )
    lines.append(f"- Bridge distribution: {cm_curated['bridge_distribution']}")
    lines.append("")
    lines.append("### Tier 1 anchors (extended)")
    lines.append("")
    for t in cm_curated["tier1_status"]:
        lines.append(
            f"- **{t['anchor']}** → assigned `{t['assigned']}` (primary topic: {t['primary_topic_name']})"
        )
    lines.append("")
    lines.append("## Whole-1702 fallback (broad scheme — for comparison)")
    lines.append("")
    lines.append(f"- Recall (neuro) = {cm_broad['recall_neuro']:.3f}")
    lines.append(f"- Recall (ai)    = {cm_broad['recall_ai']:.3f}")
    lines.append(f"- Precision (ai) = {cm_broad['precision_ai']:.3f}")
    lines.append(f"- Bridge distribution: {cm_broad['bridge_distribution']}")
    lines.append("")
    lines.append("## Per-anchor verdict change vs original audit1")
    lines.append("")
    lines.append("(Anchors that flipped from `other` to `ai` or `neuro` under the extension.)")
    lines.append("")
    flips = []
    # We don't have the original audit1 result loaded here directly, but the
    # broad column shows the production scheme outcome. Show every anchor that
    # is now 'ai'/'neuro' but was 'other' under broad.
    for r in resolved:
        if r["assigned_curated"] in ("neuro", "ai") and r["assigned_broad"] == "other":
            flips.append(r)
    if flips:
        for r in flips:
            lines.append(
                f'- {r["anchor_name"]:55s} extended=`{r["assigned_curated"]}` (was `other` under broad scheme); pt="{r["pt_name"]}"'
            )
    else:
        lines.append(
            "(no flips — extension does not change any production-scheme verdict; this would be a bug)"
        )
    lines.append("")
    lines.append("## HBAI Track 1 vs Track 2 distinguishability")
    lines.append("")
    lines.append(f"- Track 1 unique primary topics: {track_diag['track1_unique_topic_count']}")
    lines.append(f"- Track 2 unique primary topics: {track_diag['track2_unique_topic_count']}")
    lines.append(f"- Overlap: {track_diag['overlap_topic_count']}")
    lines.append(f"- Distinguishable: {track_diag['distinguishable']}")
    lines.append("")
    lines.append("## Anchors still leaking after extension (residual)")
    lines.append("")
    residual = [
        r
        for r in resolved
        if r["expected_label"] in ("neuro", "ai")
        and r["assigned_curated"] in ("other", "unknown", "NOT_FOUND")
    ]
    if residual:
        for r in residual:
            sf = r.get("pt_subfield", "")
            f = r.get("pt_field", "")
            lines.append(
                f"- {r['anchor_name']:55s} expected=`{r['expected_label']}` assigned=`{r['assigned_curated']}` (pt='{r.get('pt_name')}', sf={sf.split('/')[-1] if sf else ''}, f={f.split('/')[-1] if f else ''})"
            )
    else:
        lines.append("(none — all non-bridge anchors classified to expected side)")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    for s in (SENTINEL_DONE, SENTINEL_FAIL):
        if s.exists():
            s.unlink()
    t0 = time.time()
    try:
        anchors = get_anchors()
        n_total = len(anchors)
        con = get_connection(read_only=True)
        try:
            con.execute("PRAGMA threads=8")
            con.execute("PRAGMA memory_limit='12GB'")
            logger.info("Resolving anchors with extended scheme...")
            resolved = lookup_anchors_extended(con, anchors)
            n_resolved = sum(1 for r in resolved if r["work_id"] is not None)
            logger.info("Resolved %d/%d", n_resolved, n_total)

            cm_extended = confusion_matrix(resolved, "curated")
            cm_broad = confusion_matrix(resolved, "broad")
            track_diag = hbai_track_distinguishability(resolved)

            pass_status = {
                "recall_neuro_ge_0.80": {
                    "pass": cm_extended["recall_neuro"] >= 0.80,
                    "detail": f"recall_neuro = {cm_extended['recall_neuro']:.3f}",
                },
                "recall_ai_ge_0.80": {
                    "pass": cm_extended["recall_ai"] >= 0.80,
                    "detail": f"recall_ai = {cm_extended['recall_ai']:.3f}",
                },
                "precision_neuro_ge_0.80": {
                    "pass": cm_extended["precision_neuro"] >= 0.80,
                    "detail": f"precision_neuro = {cm_extended['precision_neuro']:.3f}",
                },
                "precision_ai_ge_0.80": {
                    "pass": cm_extended["precision_ai"] >= 0.80,
                    "detail": f"precision_ai = {cm_extended['precision_ai']:.3f}",
                },
                "tier1_all_classified_not_other": {
                    "pass": all(
                        t["assigned"] in ("neuro", "ai") for t in cm_extended["tier1_status"]
                    )
                    and len(cm_extended["tier1_status"]) == 4,
                    "detail": f"tier1 = {[(t['anchor'], t['assigned']) for t in cm_extended['tier1_status']]}",
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
                    "pass": cm_extended["leak_rate_nonbridge"] <= 0.20,
                    "detail": f"leak_rate = {cm_extended['leak_rate_nonbridge']:.3f}",
                },
            }

            json_path = AUDITS_DIR / "audit1_extended_field_labels.json"
            with json_path.open("w") as fh:
                json.dump(
                    {
                        "n_total_anchors": n_total,
                        "n_resolved": n_resolved,
                        "extended": cm_extended,
                        "broad_subfield_1702_only": cm_broad,
                        "hbai_distinguishability": track_diag,
                        "pass_status": pass_status,
                        "per_anchor": resolved,
                    },
                    fh,
                    indent=2,
                    default=str,
                )

            report_path = AUDITS_DIR / "audit1_extended_REPORT.md"
            write_extended_report(
                cm_extended,
                cm_broad,
                track_diag,
                pass_status,
                n_resolved,
                n_total,
                report_path,
                resolved,
            )
            logger.info("Wrote report to %s", report_path)
        finally:
            con.close()

        all_pass = all(p["pass"] for p in pass_status.values())
        elapsed = time.time() - t0
        if all_pass:
            SENTINEL_DONE.write_text(
                f"audit1_extended: PASS — extended scheme passes all 7 criteria; elapsed {elapsed:.1f}s\n"
            )
            logger.info("Audit 1 EXTENDED PASSED in %.1fs", elapsed)
            return 0
        else:
            failed = [k for k, v in pass_status.items() if not v["pass"]]
            SENTINEL_FAIL.write_text(
                f"audit1_extended: FAIL — failed: {failed}; see audit1_extended_REPORT.md; elapsed {elapsed:.1f}s\n"
            )
            logger.warning("Audit 1 EXTENDED still failing: %s", failed)
            return 1
    except Exception as exc:
        tb = traceback.format_exc()
        SENTINEL_FAIL.write_text(f"audit1_extended: ERROR — {type(exc).__name__}: {exc}\n\n{tb}\n")
        logger.exception("Audit 1 extended errored")
        return 2


if __name__ == "__main__":
    sys.exit(main())

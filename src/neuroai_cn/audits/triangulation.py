"""3-scheme triangulation comparison on the 70-anchor set.

Per E1 locked methodology: report each scheme separately + agreement.
For each anchor we have:
    Scheme 1 (extended Topics) — from audit1_extended_field_labels.json per_anchor
    Scheme 2 (venue whitelist)  — from scheme2_venue_assignments.parquet (joined by work_id)
    Scheme 3 (S2FOS)            — from scheme3_s2fos.parquet (joined by DOI)

Output: corrections/20260508/triangulation_anchors.parquet + audits/20260508/triangulation_REPORT.md
"""

from __future__ import annotations

import json
import logging
import sys
import time
import traceback

import pandas as pd

from .. import config
from ..utils.duckdb import get_connection

logger = logging.getLogger(__name__)

AUDITS_DIR = config.AUDITS_DIR / "20260508"
CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"


def normalise_doi(doi: str) -> str:
    s = doi.lower().strip()
    if s.startswith("https://doi.org/"):
        s = s[len("https://doi.org/") :]
    return s


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    t0 = time.time()
    try:
        # 1. Load anchors with Scheme 1 verdicts
        with (AUDITS_DIR / "audit1_extended_field_labels.json").open() as fh:
            j = json.load(fh)
        anchors = pd.DataFrame(j["per_anchor"])
        # Scheme 1 = assigned_curated (extended scheme is named 'curated' in the column)
        anchors["scheme1_topics_extended"] = anchors["assigned_curated"]
        anchors["doi_norm"] = anchors["lookup_doi"].apply(lambda s: normalise_doi(s) if s else "")

        # 2. Scheme 2 — for each anchor's work_id, look up venue
        con = get_connection(read_only=True)
        try:
            con.execute("PRAGMA threads=4")
            con.execute("PRAGMA memory_limit='8GB'")
            anchors_with_id = anchors[anchors["work_id"].notna()].copy()
            ids_sql = "[" + ",".join("'" + w + "'" for w in anchors_with_id["work_id"]) + "]"
            venue_rows = con.execute(
                f"""
                SELECT
                    w.id AS work_id,
                    w.primary_location.source.display_name AS venue_name
                FROM works w
                WHERE w.id IN (SELECT unnest({ids_sql}))
                """
            ).df()
        finally:
            con.close()
        # Lookup venue via the same lists used in scheme2_venues
        from .scheme2_venues import (
            CORE_AI,
            CORE_NEURO,
            GENERAL_HIGH_IMPACT,
            MIXED_INTERSECTION,
        )

        def classify_venue(name: str | None) -> str:
            if not name:
                return "venue_unknown"
            if name in CORE_NEURO:
                return "venue_neuro"
            if name in CORE_AI:
                return "venue_ai"
            if name in MIXED_INTERSECTION:
                return "venue_intersection"
            if name in GENERAL_HIGH_IMPACT:
                return "venue_general_high"
            return "venue_other"

        venue_rows["scheme2_venue"] = venue_rows["venue_name"].apply(classify_venue)
        anchors = anchors.merge(
            venue_rows[["work_id", "scheme2_venue", "venue_name"]],
            on="work_id",
            how="left",
        )
        anchors["scheme2_venue"] = anchors["scheme2_venue"].fillna("venue_unknown")

        # 3. Scheme 3 — S2FOS by DOI
        s2 = pd.read_parquet(CORRECTIONS_DIR / "scheme3_s2fos.parquet")
        s2["doi_norm"] = s2["doi"].apply(lambda s: normalise_doi(s) if s else "")
        s2_anchors = s2[s2["source"] == "anchor"][
            ["doi_norm", "s2_classification", "s2_fos", "s2_s2fos"]
        ]
        anchors = anchors.merge(s2_anchors, on="doi_norm", how="left")
        anchors["scheme3_s2fos"] = anchors["s2_classification"].fillna("s2_not_found")

        # 4. Compute agreement per anchor + summary
        out_cols = [
            "anchor_name",
            "expected_label",
            "source",
            "hbai_track",
            "doi_norm",
            "work_id",
            "scheme1_topics_extended",
            "scheme2_venue",
            "venue_name",
            "scheme3_s2fos",
            "s2_fos",
            "s2_s2fos",
            "pt_name",
            "pt_subfield",
            "pt_field",
        ]
        out_cols = [c for c in out_cols if c in anchors.columns]
        df_out = anchors[out_cols].copy()

        out_path = CORRECTIONS_DIR / "triangulation_anchors.parquet"
        df_out.to_parquet(out_path, index=False)

        # 5. Agreement matrix — scheme1 vs scheme3 (most comparable axes)
        report_lines = []
        report_lines.append("# 3-scheme triangulation report\n")
        report_lines.append("**Date:** 2026-05-09")
        report_lines.append("")
        report_lines.append("Per E1 locked methodology: report each scheme separately + agreement.")
        report_lines.append("")
        report_lines.append("## Scheme summaries (resolved anchors only)")
        for col, label in (
            ("scheme1_topics_extended", "Scheme 1 — Topics (extended)"),
            ("scheme2_venue", "Scheme 2 — Venue whitelist"),
            ("scheme3_s2fos", "Scheme 3 — Semantic Scholar FOS"),
        ):
            counts = df_out[col].value_counts()
            report_lines.append(f"\n### {label}")
            report_lines.append("")
            for k, v in counts.items():
                report_lines.append(f"- `{k}`: {v}")
        report_lines.append("")
        report_lines.append("## Per-anchor full table")
        report_lines.append("")
        report_lines.append("```")
        # Truncate display
        display = df_out[
            [
                "anchor_name",
                "expected_label",
                "scheme1_topics_extended",
                "scheme2_venue",
                "scheme3_s2fos",
            ]
        ].copy()
        display["anchor_name"] = display["anchor_name"].str[:40]
        report_lines.append(display.to_string(index=False))
        report_lines.append("```")
        report_lines.append("")

        # Pairwise agreement
        report_lines.append("## Pairwise agreement (Scheme 1 vs Scheme 3 on resolved anchors)")
        report_lines.append("")
        # Build a simple cross-tab where matching means S1=neuro and S3=s2_neuro/s2_intersection,
        # or S1=ai and S3=s2_ai/s2_intersection. Treat 'other'/'unknown'/'NOT_FOUND' as DK.

        def agree(s1: str, s3: str) -> str:
            if s1 == "neuro" and s3 in ("s2_neuro", "s2_intersection"):
                return "agree_neuro"
            if s1 == "ai" and s3 in ("s2_ai", "s2_intersection"):
                return "agree_ai"
            if s1 in ("neuro", "ai") and s3 in ("s2_neuro", "s2_ai", "s2_intersection"):
                return "disagree"
            if s3 == "s2_not_found":
                return "s3_not_found"
            return "other"

        df_out["agreement_s1_s3"] = df_out.apply(
            lambda r: agree(r["scheme1_topics_extended"], r["scheme3_s2fos"]),
            axis=1,
        )
        for k, v in df_out["agreement_s1_s3"].value_counts().items():
            report_lines.append(f"- `{k}`: {v}")
        report_lines.append("")

        # Disagreements detail
        disagree = df_out[df_out["agreement_s1_s3"] == "disagree"]
        if not disagree.empty:
            report_lines.append("### Disagreements (S1 vs S3)")
            report_lines.append("")
            for _, r in disagree.iterrows():
                report_lines.append(
                    f"- {r['anchor_name'][:50]} — S1=`{r['scheme1_topics_extended']}` vs S3=`{r['scheme3_s2fos']}`"
                )

        report_path = AUDITS_DIR / "triangulation_REPORT.md"
        report_path.write_text("\n".join(report_lines), encoding="utf-8")
        logger.info("Wrote triangulation report to %s", report_path)
        logger.info("Triangulation done in %.1fs", time.time() - t0)
        return 0
    except Exception:
        logger.exception("Triangulation errored")
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())

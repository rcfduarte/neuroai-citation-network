"""Q4 derivative analyses (Report-14052026 Q4.2, Q4.3, Q4.5, Q4.6).

    Q4.2  Leiden granularity retune — re-run with resolution=0.5 to surface
          ~6–15 macro-clusters (currently 659 fine clusters from 1000 nodes).

    Q4.3  Asymmetric bridge score — B_direction × B_magnitude, distinguishing
          "Neuro→AI bridges" from "AI→Neuro bridges". For each top-N bridge
          paper, compute the directional skew score.

    Q4.5  Era trajectory in raw counts is misleading; normalise by per-era
          top-1000 size for rate comparison.

    Q4.6  Per-cluster anchor density — fraction of anchor papers per cluster.
          High density = "validation-anchored" cluster; low = exploratory.

Inputs:
    corrections/20260508/clustering_edges.parquet
    corrections/20260508/clustering_nodes.parquet
    corrections/20260508/q4_classified_nodes_v2.parquet (the post-cleanup set)
    corrections/20260508/q4_v3_extended_filtered_by_era_no_books.parquet (anchors-ish)

Outputs:
    corrections/20260508/q4_leiden_macro.parquet  — re-clustered nodes
    corrections/20260508/q4_asymmetric_B.parquet  — top papers with directional B
"""

from __future__ import annotations

import logging
import sys

import igraph as ig
import leidenalg as la
import numpy as np
import pandas as pd

from .. import config

logger = logging.getLogger(__name__)

CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"


def main() -> int:
    # ─── Q4.2: Leiden retune with lower resolution ──────────────────────────
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    nodes = pd.read_parquet(CORRECTIONS_DIR / "q4_classified_nodes_v2.parquet")
    edges = pd.read_parquet(CORRECTIONS_DIR / "clustering_edges.parquet")
    logger.info("Nodes (v2): %d, edges: %d", len(nodes), len(edges))

    # Filter edges to v2 nodes
    valid_ids = set(nodes["work_id"].astype(str))
    edges_v2 = edges[
        edges["src"].astype(str).isin(valid_ids) & edges["tgt"].astype(str).isin(valid_ids)
    ].copy()
    logger.info("Edges within v2 nodes: %d", len(edges_v2))

    work_to_idx = {w: i for i, w in enumerate(nodes["work_id"].astype(str).tolist())}
    edge_list = [
        (work_to_idx[str(r.src)], work_to_idx[str(r.tgt)])
        for r in edges_v2.itertuples()
        if str(r.src) in work_to_idx and str(r.tgt) in work_to_idx
    ]
    weights = edges_v2["weight"].astype(float).tolist() if "weight" in edges_v2.columns else None

    g = ig.Graph(n=len(nodes), edges=edge_list, directed=False)
    if weights:
        g.es["weight"] = weights[: len(edge_list)]

    # Re-cluster with lower resolution (coarser)
    if weights and g.es:
        partition = la.find_partition(
            g,
            la.RBConfigurationVertexPartition,
            weights="weight",
            resolution_parameter=0.5,
        )
    else:
        partition = la.find_partition(
            g,
            la.RBConfigurationVertexPartition,
            resolution_parameter=0.5,
        )
    macro_clusters = list(partition)
    modularity = float(partition.quality())
    logger.info("Macro-clusters: %d, modularity: %.3f", len(macro_clusters), modularity)

    macro_assignment = np.zeros(len(nodes), dtype=int)
    for cid, members in enumerate(macro_clusters):
        for m in members:
            macro_assignment[m] = cid
    nodes["macro_cluster"] = macro_assignment

    # Drop tiny clusters (n < 5) — assign to "misc"
    counts = nodes["macro_cluster"].value_counts()
    big_clusters = counts[counts >= 5].index
    nodes["macro_cluster_label"] = nodes["macro_cluster"].apply(
        lambda c: c if c in big_clusters else -1
    )
    big_n = int((nodes["macro_cluster_label"] != -1).sum())
    logger.info(
        "Substantive macro-clusters (n≥5): %d, total nodes covered: %d",
        len(big_clusters),
        big_n,
    )

    nodes.to_parquet(CORRECTIONS_DIR / "q4_leiden_macro.parquet", index=False)

    # ─── Q4.3: Asymmetric bridge score ──────────────────────────────────────
    # B_direction = c_ai / (c_neuro + c_ai)   (0=neuro-leaning, 1=AI-leaning)
    # B_magnitude = B_harmonic   (existing scalar)
    # B_asym_signed = (B_direction - 0.5) * 2 * B_harmonic
    #                  positive ⇒ AI-leaning bridge; negative ⇒ neuro-leaning
    bridge = pd.read_parquet(CORRECTIONS_DIR / "q4_v3_extended_full.parquet")
    bridge["B_direction"] = bridge["c_ai"] / (bridge["c_neuro"] + bridge["c_ai"]).clip(lower=1)
    bridge["B_asym_signed"] = (bridge["B_direction"] - 0.5) * 2 * bridge["B_harmonic"]
    bridge.to_parquet(CORRECTIONS_DIR / "q4_asymmetric_B.parquet", index=False)
    logger.info("Asymmetric B computed for %d papers", len(bridge))

    # ─── Q4.5: Era trajectory normalised ─────────────────────────────────────
    # For each era, count top-1000 papers and normalise by era duration
    canonical_eras = [
        ("Pre-DL", 1990, 2011),
        ("DL emergence", 2012, 2015),
        ("DL expansion", 2016, 2019),
        ("NeuroAI era", 2020, 2025),
    ]
    nodes_eras = nodes.copy()

    def assign_era(y):
        if pd.isna(y):
            return None
        for name, lo, hi in canonical_eras:
            if lo <= int(y) <= hi:
                return name
        return None

    nodes_eras["era"] = nodes_eras["publication_year"].apply(assign_era)
    era_rates = []
    for name, lo, hi in canonical_eras:
        sub = nodes_eras[nodes_eras["era"] == name]
        era_rates.append(
            dict(
                era=name,
                n_papers=len(sub),
                era_length=hi - lo + 1,
                papers_per_year=len(sub) / (hi - lo + 1),
                sum_B=float(sub["B_harmonic"].sum()),
                B_per_year=float(sub["B_harmonic"].sum()) / (hi - lo + 1),
            )
        )
    era_df = pd.DataFrame(era_rates)
    logger.info("Era trajectory:")
    print(era_df.to_string())

    # ─── Q4.6: Per-cluster anchor density ─────────────────────────────────
    # Use the original top-37 by_era papers as anchors
    anchors = pd.read_parquet(CORRECTIONS_DIR / "q4_v3_extended_filtered_by_era_no_books.parquet")
    anchor_ids = set(anchors["work_id"].astype(str))
    nodes["is_anchor"] = nodes["work_id"].astype(str).isin(anchor_ids)
    anchor_density = []
    for c in big_clusters:
        sub = nodes[nodes["macro_cluster"] == c]
        anchor_density.append(
            dict(
                cluster=int(c),
                n_papers=len(sub),
                n_anchors=int(sub["is_anchor"].sum()),
                density=float(sub["is_anchor"].mean()),
                top_titles=sub.sort_values("B_harmonic", ascending=False).head(3)["title"].tolist(),
            )
        )
    anchor_density.sort(key=lambda d: d["density"], reverse=True)
    logger.info("Top-3 anchor-dense clusters: %s", [d["cluster"] for d in anchor_density[:3]])
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Q2.5 — Co-authorship network of top-1000 bridge authors.

Builds:
    Nodes:  top-1000 bridge authors (from author_inst_top_authors_1000.parquet)
    Edges:  (author_i, author_j, n_papers) where they co-authored ≥1 bridge paper
            in the q4_v3_extended_full corpus
    Layout: Leiden clustering on the weighted co-authorship graph + Fruchterman-
            Reingold spatial layout (with same-cluster attraction).

Outputs (corrections/20260508/):
    q2_coauthorship_nodes.parquet  — author_id, author_name, n_papers, total_B,
                                     cluster, x, y, neuro_share
    q2_coauthorship_edges.parquet  — src, tgt, weight (= co-authored papers)
    q2_coauthorship_summary.json   — modularity, n_clusters, n_components

This addresses Report-14052026 Q2.5 ("Co-authorship network of top-1000 dual
citizens → Leiden clustering — reveals labs/lineages").
"""

from __future__ import annotations

import json
import logging
import sys
import time
from itertools import combinations

import igraph as ig
import leidenalg as la
import numpy as np
import pandas as pd

from .. import config
from ..utils.duckdb import get_connection

logger = logging.getLogger(__name__)

CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"

TOP_N = 1000
MIN_EDGE_WEIGHT = 1  # keep edges with ≥1 co-authored paper


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    authors = (
        pd.read_parquet(CORRECTIONS_DIR / "author_inst_top_authors_1000.parquet")
        .sort_values("total_B", ascending=False)
        .head(TOP_N)
        .reset_index(drop=True)
    )
    top_ids = set(authors["author_id"].astype(str))
    logger.info("Top-%d authors: %d unique", TOP_N, len(top_ids))

    bridge = pd.read_parquet(CORRECTIONS_DIR / "q4_v3_extended_full.parquet")
    bridge_ids = bridge["work_id"].astype(str).tolist()
    logger.info("Bridge papers: %d", len(bridge_ids))

    # Build paper -> authors_in_top set from the existing authorships parts.
    authorships_dir = config.AUTHORSHIPS_PARTS_DIR
    glob = str(authorships_dir / "*.parquet")
    with get_connection(read_only=True) as con:
        con.execute("PRAGMA threads=8")
        con.execute("CREATE TEMP TABLE _bid (work_id VARCHAR)")
        con.executemany("INSERT INTO _bid VALUES (?)", [(w,) for w in bridge_ids])
        con.execute("CREATE TEMP TABLE _aid (author_id VARCHAR)")
        con.executemany("INSERT INTO _aid VALUES (?)", [(a,) for a in top_ids])
        t0 = time.time()
        df = con.execute(
            f"""
            SELECT a.work_id, a.author_id
            FROM read_parquet('{glob}') a
            JOIN _bid b ON a.work_id = b.work_id
            JOIN _aid t ON a.author_id = t.author_id
            """
        ).df()
    logger.info("Filtered (work,author) rows: %d in %.0fs", len(df), time.time() - t0)

    # Build co-authorship edges: pairs of authors who appear on the same work
    edges: dict[tuple[str, str], int] = {}
    grouped = df.groupby("work_id")["author_id"].apply(set)
    for _wid, aset in grouped.items():
        if len(aset) < 2:
            continue
        for a, b in combinations(sorted(aset), 2):
            edges[(a, b)] = edges.get((a, b), 0) + 1
    logger.info("Raw co-authorship edges: %d", len(edges))

    edges_df = pd.DataFrame(
        [(s, t, w) for (s, t), w in edges.items() if w >= MIN_EDGE_WEIGHT],
        columns=["src", "tgt", "weight"],
    )
    logger.info("Edges after weight filter (>= %d): %d", MIN_EDGE_WEIGHT, len(edges_df))

    # Build igraph
    all_nodes = list(top_ids)
    idx = {a: i for i, a in enumerate(all_nodes)}
    edge_list = [(idx[r.src], idx[r.tgt]) for r in edges_df.itertuples()]
    edge_weights = edges_df["weight"].astype(float).tolist()

    g = ig.Graph(n=len(all_nodes), edges=edge_list, directed=False)
    g.es["weight"] = edge_weights

    # Leiden clustering
    partition = la.find_partition(
        g,
        la.RBConfigurationVertexPartition,
        weights="weight",
        resolution_parameter=1.0,
    )
    modularity = float(partition.quality())
    clusters = list(partition)
    logger.info("Leiden: %d clusters, modularity = %.3f", len(clusters), modularity)

    cluster_assignment = np.zeros(len(all_nodes), dtype=int)
    for cid, members in enumerate(clusters):
        for m in members:
            cluster_assignment[m] = cid

    # FR layout — quick (1000 nodes)
    try:
        layout = g.layout_fruchterman_reingold(
            weights="weight",
            niter=300,
            grid="nogrid",
        )
        coords = np.array(layout.coords, dtype=float)
    except Exception as exc:
        logger.warning("FR layout fell back to random: %s", exc)
        coords = np.random.RandomState(7).normal(0, 5, (len(all_nodes), 2))

    # Build nodes parquet
    rows = []
    for i, aid in enumerate(all_nodes):
        a = authors[authors["author_id"] == aid]
        if a.empty:
            continue
        r = a.iloc[0]
        rows.append(
            dict(
                author_id=aid,
                author_name=r["author_name"],
                n_bridge_papers=int(r["n_bridge_papers"]),
                total_B=float(r["total_B"]),
                total_c_neuro=int(r["total_c_neuro"]),
                total_c_ai=int(r["total_c_ai"]),
                cluster=int(cluster_assignment[i]),
                x=float(coords[i, 0]),
                y=float(coords[i, 1]),
                degree=int(g.degree(i, mode="all")),
                strength=float(g.strength(i, weights="weight")) if g.es else 0.0,
            )
        )
    nodes_df = pd.DataFrame(rows)
    nodes_df["neuro_share"] = nodes_df["total_c_neuro"] / (
        nodes_df["total_c_neuro"] + nodes_df["total_c_ai"]
    ).clip(lower=1)

    nodes_df.to_parquet(CORRECTIONS_DIR / "q2_coauthorship_nodes.parquet", index=False)
    edges_df.to_parquet(CORRECTIONS_DIR / "q2_coauthorship_edges.parquet", index=False)

    n_components = len(g.connected_components())
    summary = dict(
        n_nodes=len(all_nodes),
        n_edges=len(edges_df),
        n_clusters=len(clusters),
        n_connected_components=n_components,
        modularity=modularity,
        cluster_sizes_top10=[len(c) for c in sorted(clusters, key=len, reverse=True)[:10]],
    )
    (CORRECTIONS_DIR / "q2_coauthorship_summary.json").write_text(json.dumps(summary, indent=2))
    logger.info(
        "Wrote nodes/edges/summary. n=%d, edges=%d, clusters=%d, modularity=%.3f",
        len(all_nodes),
        len(edges_df),
        len(clusters),
        modularity,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

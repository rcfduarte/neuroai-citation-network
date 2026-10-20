"""Leiden clustering of the bridge-paper subgraph + temporal re-clustering.

Build a bibliographic-coupling graph from the top-N bridge papers (default
1000): two papers are linked with weight = #shared references. Apply disparity
filter (alpha=0.05) to extract the multiscale backbone, then run Leiden
community detection. Label each cluster via TF-IDF on cleaned titles.

Per-era variant: re-cluster within four era windows
    pre-2012, 2012-2017, 2017-2022, 2022-2026
to surface emerging communities.

Outputs (under data/derived/corrections/20260508/):
    clustering_nodes.parquet     — work_id, cluster, B(p), c_neuro, c_ai, year, title, doi
    clustering_edges.parquet     — backbone edges (src, tgt, weight, alpha)
    clustering_labels.parquet    — cluster_id, top_terms, n_papers, mean_B
    clustering_per_era.parquet   — same but split by era
    clustering_summary.json      — modularity, n_clusters, n_edges, layout dimensions

Sentinel: _clustering.done in audits/20260508/.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import traceback

import duckdb
import igraph as ig
import leidenalg as la
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from .. import config
from ..utils.duckdb import get_connection, set_temp_directory

logger = logging.getLogger(__name__)

AUDITS_DIR = config.AUDITS_DIR / "20260508"
CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"
SENTINEL_DONE = AUDITS_DIR / "_clustering.done"
SENTINEL_FAIL = AUDITS_DIR / "_clustering.failed"

BRIDGE_FULL = CORRECTIONS_DIR / "q4_v3_extended_full.parquet"

TOP_N = 1000
MIN_COUPLING = 3  # min shared refs to draw an edge
DISPARITY_ALPHA = 0.20  # backbone significance threshold (loosened from 0.05)
MIN_CLUSTER_SIZE = 5  # absorb tiny clusters into 'misc'

ERAS = [
    ("pre-2012", 1990, 2011),
    ("2012-2017", 2012, 2017),
    ("2017-2022", 2017, 2022),
    ("2022-2026", 2022, 2026),
]

STOPWORDS_EXTRA = {
    "based",
    "using",
    "model",
    "models",
    "method",
    "methods",
    "approach",
    "study",
    "analysis",
    "results",
    "novel",
    "new",
    "via",
    "toward",
    "towards",
    "system",
    "systems",
    "data",
    "paper",
    "review",
    "framework",
}


def fetch_top_bridges(n: int = TOP_N) -> pd.DataFrame:
    """Top-N bridges by raw B(p) with title + year + DOI."""
    df = pd.read_parquet(BRIDGE_FULL)
    df = df.assign(B_harmonic=df["B_harmonic"].astype(float))
    df = df.sort_values("B_harmonic", ascending=False).head(n).reset_index(drop=True)
    return df


def build_bibliographic_coupling(
    con: duckdb.DuckDBPyConnection, work_ids: list[str], min_coupling: int = MIN_COUPLING
) -> pd.DataFrame:
    """Compute bibliographic coupling weights among the given works.

    Two papers a, b are coupled with weight = |refs(a) ∩ refs(b)|. We materialize
    (work_id, ref) pairs for the seed set, then self-join on ref to count
    shared refs per pair.
    """
    con.register("seed_works", pd.DataFrame({"work_id": work_ids}))
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE seed_refs AS
        SELECT s.work_id, ref
        FROM seed_works s
        JOIN works w ON w.id = s.work_id
        CROSS JOIN UNNEST(w.referenced_works) AS reftab(ref)
        WHERE ref IS NOT NULL
        """
    )
    n_refs = int(con.execute("SELECT COUNT(*) FROM seed_refs").fetchone()[0])
    logger.info("seed_refs: %d (work, ref) rows", n_refs)
    edges = con.execute(
        f"""
        SELECT
            a.work_id AS src,
            b.work_id AS tgt,
            COUNT(*) AS weight
        FROM seed_refs a
        JOIN seed_refs b ON a.ref = b.ref AND a.work_id < b.work_id
        GROUP BY a.work_id, b.work_id
        HAVING COUNT(*) >= {min_coupling}
        """
    ).fetchdf()
    logger.info("Coupling edges (>=%d shared refs): %d", min_coupling, len(edges))
    return edges


def disparity_filter(edges: pd.DataFrame, alpha: float = DISPARITY_ALPHA) -> pd.DataFrame:
    """Multiscale backbone (Serrano, Boguna, Vespignani 2009).

    For each node i, normalised edge weights p_ij = w_ij / sum_j(w_ij). Edge
    (i,j) is kept iff alpha_ij = (1 - p_ij)^(k_i - 1) < alpha for either node.
    """
    if edges.empty:
        return edges
    # Build symmetric adjacency for degree + strength computation
    sym = pd.concat(
        [
            edges.rename(columns={"src": "u", "tgt": "v"}),
            edges.rename(columns={"src": "v", "tgt": "u"}),
        ],
        ignore_index=True,
    )
    deg = sym.groupby("u").size().rename("k")
    strength = sym.groupby("u")["weight"].sum().rename("s")
    # Compute per-edge alpha from each endpoint's perspective
    e = edges.copy()
    e = e.merge(deg.rename("k_src"), left_on="src", right_index=True)
    e = e.merge(deg.rename("k_tgt"), left_on="tgt", right_index=True)
    e = e.merge(strength.rename("s_src"), left_on="src", right_index=True)
    e = e.merge(strength.rename("s_tgt"), left_on="tgt", right_index=True)
    p_src = e["weight"] / e["s_src"].replace(0, np.nan)
    p_tgt = e["weight"] / e["s_tgt"].replace(0, np.nan)
    alpha_src = np.where(e["k_src"] > 1, (1 - p_src) ** (e["k_src"] - 1), 1.0)
    alpha_tgt = np.where(e["k_tgt"] > 1, (1 - p_tgt) ** (e["k_tgt"] - 1), 1.0)
    e["alpha"] = np.minimum(alpha_src, alpha_tgt)
    keep = e[e["alpha"] < alpha].copy()
    logger.info("Backbone: %d / %d edges (alpha < %.3f)", len(keep), len(e), alpha)
    return keep[["src", "tgt", "weight", "alpha"]]


def run_leiden(nodes: list[str], edges: pd.DataFrame, seed: int = 42) -> dict:
    """Run Leiden on the given graph. Returns dict with cluster assignments
    + modularity + layout coordinates (Fruchterman-Reingold)."""
    if edges.empty:
        return {
            "clusters": dict.fromkeys(nodes, 0),
            "modularity": float("nan"),
            "layout": dict.fromkeys(nodes, (0.0, 0.0)),
        }
    node_idx = {n: i for i, n in enumerate(nodes)}
    edge_list = [
        (node_idx[r["src"]], node_idx[r["tgt"]])
        for _, r in edges.iterrows()
        if r["src"] in node_idx and r["tgt"] in node_idx
    ]
    weights = [
        float(r["weight"])
        for _, r in edges.iterrows()
        if r["src"] in node_idx and r["tgt"] in node_idx
    ]
    g = ig.Graph(n=len(nodes), edges=edge_list, directed=False)
    g.vs["name"] = nodes
    g.es["weight"] = weights
    partition = la.find_partition(g, la.ModularityVertexPartition, weights="weight", seed=seed)
    clusters = dict(zip(nodes, partition.membership, strict=True))
    modularity = float(partition.quality())
    # Layout for the network figure (FR doesn't accept int seed; set numpy/random
    # state via igraph's set_random_number_generator before layout call).
    import random

    random.seed(seed)
    np.random.seed(seed)
    layout = g.layout_fruchterman_reingold(weights="weight", niter=500)
    layout_dict = {nodes[i]: (float(x), float(y)) for i, (x, y) in enumerate(layout.coords)}
    return {"clusters": clusters, "modularity": modularity, "layout": layout_dict}


def label_clusters(
    nodes_df: pd.DataFrame, top_k: int = 8, min_size: int = MIN_CLUSTER_SIZE
) -> pd.DataFrame:
    """Label each cluster with top-K TF-IDF terms from titles."""
    out = []
    sizes = nodes_df.groupby("cluster").size()
    big = sizes[sizes >= min_size].index.tolist()
    for cid in sorted(big):
        sub = nodes_df[nodes_df["cluster"] == cid]
        titles = sub["title"].fillna("").astype(str).tolist()
        if not titles:
            continue
        # Use whole-cluster vs other-clusters TF-IDF: corpus = one doc per cluster
        all_clusters_titles: list[str] = [
            " ".join(nodes_df[nodes_df["cluster"] == c]["title"].fillna("").astype(str))
            for c in sorted(big)
        ]
        vec = TfidfVectorizer(
            stop_words="english",
            max_features=2000,
            ngram_range=(1, 2),
            min_df=1,
            token_pattern=r"(?u)\b[A-Za-z][A-Za-z]+\b",
        )
        try:
            tfidf = vec.fit_transform(all_clusters_titles)
        except ValueError:
            continue
        cluster_idx = sorted(big).index(cid)
        scores = tfidf[cluster_idx].toarray()[0]
        terms = vec.get_feature_names_out()
        # Exclude noise stopwords
        mask = np.array([not any(w in STOPWORDS_EXTRA for w in t.split()) for t in terms])
        scores_filtered = scores * mask.astype(float)
        top_idx = np.argsort(-scores_filtered)[:top_k]
        top_terms = [terms[i] for i in top_idx if scores_filtered[i] > 0]
        out.append(
            {
                "cluster": int(cid),
                "n_papers": len(sub),
                "mean_B": float(sub["B_harmonic"].mean()),
                "median_year": float(sub["publication_year"].median()),
                "top_terms": ", ".join(top_terms),
                "exemplar_titles": " | ".join(
                    sub.sort_values("B_harmonic", ascending=False)["title"]
                    .head(3)
                    .fillna("")
                    .tolist()
                ),
            }
        )
    if not out:
        # No clusters reached min_size — return empty frame with expected schema
        return pd.DataFrame(
            columns=[
                "cluster",
                "n_papers",
                "mean_B",
                "median_year",
                "top_terms",
                "exemplar_titles",
            ]
        )
    return pd.DataFrame(out).sort_values("n_papers", ascending=False).reset_index(drop=True)


def cluster_one(
    con: duckdb.DuckDBPyConnection, df: pd.DataFrame, label: str
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Run the full pipeline (coupling → backbone → Leiden → label) on df."""
    work_ids = df["work_id"].astype(str).tolist()
    edges_full = build_bibliographic_coupling(con, work_ids)
    edges_bb = disparity_filter(edges_full)
    leiden = run_leiden(work_ids, edges_bb)
    nodes_df = df[
        [
            "work_id",
            "doi",
            "title",
            "publication_year",
            "B_harmonic",
            "c_neuro",
            "c_ai",
            "bridge_paper_field",
        ]
    ].copy()
    nodes_df["cluster"] = nodes_df["work_id"].map(leiden["clusters"]).astype(int)
    nodes_df["x"] = nodes_df["work_id"].map(lambda w: leiden["layout"][w][0])
    nodes_df["y"] = nodes_df["work_id"].map(lambda w: leiden["layout"][w][1])
    nodes_df["era"] = label
    labels_df = label_clusters(nodes_df)
    labels_df["era"] = label
    edges_out = edges_bb.copy()
    edges_out["era"] = label
    return (
        nodes_df,
        edges_out,
        labels_df,
        {
            "modularity": leiden["modularity"],
            "n_edges_full": len(edges_full),
            "n_edges_backbone": len(edges_bb),
        },
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    CORRECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    for s in (SENTINEL_DONE, SENTINEL_FAIL):
        if s.exists():
            s.unlink()
    t0 = time.time()
    try:
        if not BRIDGE_FULL.exists():
            raise FileNotFoundError(BRIDGE_FULL)

        df_top = fetch_top_bridges(TOP_N)
        # Drop NA titles to keep TF-IDF healthy
        df_top = df_top.dropna(subset=["title"]).reset_index(drop=True)
        logger.info("Top-%d bridges loaded (after NA-title drop)", len(df_top))

        con = get_connection(read_only=True)
        try:
            con.execute("PRAGMA threads=8")
            con.execute("PRAGMA memory_limit='16GB'")
            set_temp_directory(con)

            # Global clustering
            logger.info("Global clustering ...")
            nodes_g, edges_g, labels_g, summary_g = cluster_one(con, df_top, "global")

            # Per-era clustering
            era_nodes_all = []
            era_labels_all = []
            era_summaries = {}
            for era_label, lo, hi in ERAS:
                sub = df_top[
                    (df_top["publication_year"] >= lo) & (df_top["publication_year"] <= hi)
                ].copy()
                if len(sub) < 30:
                    logger.info("Era %s: only %d papers, skipping", era_label, len(sub))
                    continue
                logger.info("Era %s clustering: %d papers ...", era_label, len(sub))
                nodes_e, _edges_e, labels_e, summ_e = cluster_one(con, sub, era_label)
                era_nodes_all.append(nodes_e)
                era_labels_all.append(labels_e)
                era_summaries[era_label] = summ_e

            # Write outputs
            nodes_g.to_parquet(CORRECTIONS_DIR / "clustering_nodes.parquet", index=False)
            edges_g.to_parquet(CORRECTIONS_DIR / "clustering_edges.parquet", index=False)
            labels_g.to_parquet(CORRECTIONS_DIR / "clustering_labels.parquet", index=False)

            if era_nodes_all:
                pd.concat(era_nodes_all, ignore_index=True).to_parquet(
                    CORRECTIONS_DIR / "clustering_per_era_nodes.parquet", index=False
                )
                pd.concat(era_labels_all, ignore_index=True).to_parquet(
                    CORRECTIONS_DIR / "clustering_per_era_labels.parquet", index=False
                )

            summary = {
                "n_top_bridges_in": len(df_top),
                "min_coupling": MIN_COUPLING,
                "disparity_alpha": DISPARITY_ALPHA,
                "global": {
                    "modularity": summary_g["modularity"],
                    "n_edges_full": summary_g["n_edges_full"],
                    "n_edges_backbone": summary_g["n_edges_backbone"],
                    "n_clusters_total": int(nodes_g["cluster"].nunique()),
                    "n_clusters_min_size": len(labels_g),
                },
                "per_era": era_summaries,
                "elapsed_s": round(time.time() - t0, 1),
            }
            with (AUDITS_DIR / "clustering_summary.json").open("w") as fh:
                json.dump(summary, fh, indent=2, default=str)
            logger.info("Clustering summary: %s", summary)
        finally:
            con.close()
        SENTINEL_DONE.write_text(
            f"clustering: DONE — {summary_g['n_edges_full']} edges, mod={summary_g['modularity']:.3f}; elapsed {time.time() - t0:.1f}s\n"
        )
        return 0
    except Exception as exc:
        tb = traceback.format_exc()
        SENTINEL_FAIL.write_text(f"clustering: ERROR — {type(exc).__name__}: {exc}\n\n{tb}\n")
        logger.exception("Clustering errored")
        return 2


if __name__ == "__main__":
    sys.exit(main())

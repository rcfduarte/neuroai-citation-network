"""DuckDB connection helpers + corpus manifest.

Single entry point for any module that needs to query the OpenAlex index.
Re-reads live state on every call — never caches row counts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb

from . import DUCKDB_PATH, TMP_DIR

NEURO_FIELD_ID = "https://openalex.org/fields/28"
AI_SUBFIELD_ID = "https://openalex.org/subfields/1702"

# Curated "core AI" topic IDs within subfield 1702 (Artificial Intelligence).
#
# Why curate? Subfield 1702 contains 77 topics — only ~half are core AI methods
# (deep learning, RL, NLP, Bayesian methods, search/planning, symbolic AI). The
# rest are "AI applied to X" buckets (medicine, education, geology, services,
# law) plus orthogonal CS-1702 mis-clusters (crypto, quantum, signal processing,
# control theory). Two failure modes if we use the whole subfield:
#
#  (1) Population baseline `rho_null` is inflated by domain-AI papers a
#      neuroscientist would never cite, dragging cross-citation OR below 1.
#  (2) The OpenAlex topic classifier is unstable across snapshot dates: in the
#      ud2025-11-06 bulk re-export, topic T12157 ("Geochemistry and Geologic
#      Mapping" — yes, classified as AI subfield because of ML-for-geology
#      papers) jumped 51k→2.82M works in a single year, accounting for 85% of
#      the 2025 "AI" pool and collapsing OR_neuro→ai from 0.42 to 0.09.
#
# This list is the methods + foundational ML/AI core (35 topics): neural nets,
# RL, NLP, search/planning, Bayesian, evolutionary, fuzzy, ML algorithms,
# clustering, anomaly detection, cognitive computing, symbolic AI/KR.
# Excluded: applied-domain buckets, crypto/security, quantum, control theory,
# signal processing, software engineering, programming languages, and the
# T12157 classification artifact. Documented choices and the full subfield
# listing are in docs/methods/01-corpus-and-pools.md.
AI_CORE_TOPIC_IDS = (
    "https://openalex.org/T10028",  # Topic Modeling
    "https://openalex.org/T10100",  # Metaheuristic Optimization Algorithms Research
    "https://openalex.org/T10181",  # Natural Language Processing Techniques
    "https://openalex.org/T10201",  # Speech Recognition and Synthesis
    "https://openalex.org/T10215",  # Semantic Web and Ontologies
    "https://openalex.org/T10320",  # Neural Networks and Applications
    "https://openalex.org/T10456",  # Multi-Agent Systems and Negotiation
    "https://openalex.org/T10462",  # Reinforcement Learning in Robotics
    "https://openalex.org/T10637",  # Advanced Clustering Algorithms Research
    "https://openalex.org/T10664",  # Sentiment Analysis and Opinion Mining
    "https://openalex.org/T10820",  # Fuzzy Logic and Control Systems
    "https://openalex.org/T10906",  # AI-based Problem Solving and Planning
    "https://openalex.org/T11010",  # Logic, Reasoning, and Knowledge
    "https://openalex.org/T11273",  # Advanced Graph Neural Networks
    "https://openalex.org/T11303",  # Bayesian Modeling and Causal Inference
    "https://openalex.org/T11512",  # Anomaly Detection Techniques and Applications
    "https://openalex.org/T11550",  # Text and Document Classification Technologies
    "https://openalex.org/T11574",  # Artificial Intelligence in Games
    "https://openalex.org/T11612",  # Stochastic Gradient Optimization Techniques
    "https://openalex.org/T11652",  # Imbalanced Data Classification Techniques
    "https://openalex.org/T11689",  # Adversarial Robustness in Machine Learning
    "https://openalex.org/T11901",  # Bayesian Methods and Mixture Models
    "https://openalex.org/T11975",  # Evolutionary Algorithms and Applications
    "https://openalex.org/T12026",  # Explainable Artificial Intelligence (XAI)
    "https://openalex.org/T12031",  # Speech and dialogue systems
    "https://openalex.org/T12072",  # Machine Learning and Algorithms
    "https://openalex.org/T12535",  # Machine Learning and Data Classification
    "https://openalex.org/T12611",  # Neural Networks and Reservoir Computing
    "https://openalex.org/T12676",  # Machine Learning and ELM
    "https://openalex.org/T12761",  # Data Stream Mining Techniques
    "https://openalex.org/T12805",  # Cognitive Science and Mapping
    "https://openalex.org/T12814",  # Gaussian Processes and Bayesian Inference
    "https://openalex.org/T13062",  # Cognitive Computing and Networks
    "https://openalex.org/T13083",  # Advanced Text Analysis Techniques
    "https://openalex.org/T13904",  # Artificial Intelligence Applications
)

TIER1_DOIS = (
    "https://doi.org/10.1038/s41467-023-37180-x",  # Zador 2023
    "https://doi.org/10.1038/s41593-019-0520-2",  # Richards 2019
    "https://doi.org/10.1016/j.neuron.2017.06.011",  # Hassabis 2017
    "https://doi.org/10.1038/s41593-018-0210-5",  # Kriegeskorte-Douglas 2018
)


@dataclass(frozen=True)
class Manifest:
    """Snapshot of the live DuckDB state. Re-fetched on each manifest() call."""

    duckdb_path: str
    duckdb_size_gb: float
    works_total: int
    works_with_primary_topic: int
    works_with_referenced_works: int
    citing_works: int
    citation_edges: int
    authors: int
    sources: int
    institutions: int
    topics: int
    tier1_present_count: int
    tier1_resolved_dois: tuple[str, ...]
    snapshot_year_min: int
    snapshot_year_max: int

    def coverage_fraction(self, full_universe: int = 250_000_000) -> float:
        """Rough fraction of the OpenAlex works universe currently in the snapshot."""
        return self.works_total / full_universe

    def to_dict(self) -> dict:
        return {
            "duckdb_path": self.duckdb_path,
            "duckdb_size_gb": round(self.duckdb_size_gb, 1),
            "works_total": self.works_total,
            "works_with_primary_topic": self.works_with_primary_topic,
            "works_with_referenced_works": self.works_with_referenced_works,
            "citing_works": self.citing_works,
            "citation_edges": self.citation_edges,
            "authors": self.authors,
            "sources": self.sources,
            "institutions": self.institutions,
            "topics": self.topics,
            "tier1_present_count": self.tier1_present_count,
            "tier1_resolved_dois": list(self.tier1_resolved_dois),
            "snapshot_year_min": self.snapshot_year_min,
            "snapshot_year_max": self.snapshot_year_max,
            "coverage_fraction_estimate": round(self.coverage_fraction(), 3),
        }


def get_connection(
    read_only: bool = True, path: str | Path | None = None
) -> duckdb.DuckDBPyConnection:
    """Open the OpenAlex DuckDB. Read-only by default — pass read_only=False only for writes.

    Path can be overridden for tests; production callers should pass nothing.
    """
    target = Path(path) if path is not None else DUCKDB_PATH
    if not target.exists():
        raise FileNotFoundError(
            f"DuckDB not found at {target}. Snapshot pull may not have built it yet."
        )
    return duckdb.connect(str(target), read_only=read_only)


def set_temp_directory(con: duckdb.DuckDBPyConnection) -> None:
    """Point DuckDB's spill-to-disk directory at config.TMP_DIR (<NEUROAI_DATA>/tmp)."""
    con.execute(f"PRAGMA temp_directory='{TMP_DIR}'")


def get_tuned_connection(
    read_only: bool = True,
    threads: int | None = None,
    memory_limit: str | None = None,
    path: str | Path | None = None,
) -> duckdb.DuckDBPyConnection:
    """Open the OpenAlex DuckDB (read-only by default) with threads, memory limit and temp directory set."""
    con = get_connection(read_only=read_only, path=path)
    if threads is not None:
        con.execute(f"PRAGMA threads={int(threads)}")
    if memory_limit is not None:
        con.execute(f"PRAGMA memory_limit='{memory_limit}'")
    set_temp_directory(con)
    return con


def manifest(con: duckdb.DuckDBPyConnection | None = None) -> Manifest:
    """Compute a Manifest of the live DuckDB. Cheap (uses indexed counts)."""
    owns_con = con is None
    if owns_con:
        con = get_connection(read_only=True)
    try:
        works_total = con.execute(
            "SELECT COUNT(*) FROM works WHERE publication_year BETWEEN 1990 AND 2026"
        ).fetchone()[0]
        works_with_pt = con.execute(
            "SELECT COUNT(*) FROM works WHERE primary_topic IS NOT NULL"
        ).fetchone()[0]
        works_with_refs = con.execute(
            "SELECT COUNT(*) FROM works WHERE referenced_works IS NOT NULL AND len(referenced_works) > 0"
        ).fetchone()[0]
        citing_works = con.execute(
            "SELECT COUNT(DISTINCT citing_work_id) FROM citation_edges"
        ).fetchone()[0]
        citation_edges = con.execute("SELECT COUNT(*) FROM citation_edges").fetchone()[0]
        authors = con.execute("SELECT COUNT(*) FROM authors").fetchone()[0]
        sources = con.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        institutions = con.execute("SELECT COUNT(*) FROM institutions").fetchone()[0]
        topics = con.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
        year_range = con.execute(
            "SELECT MIN(publication_year), MAX(publication_year) FROM works WHERE publication_year BETWEEN 1990 AND 2026"
        ).fetchone()
        year_min = int(year_range[0] or 0)
        year_max = int(year_range[1] or 0)

        tier1_dois_lower = [d.lower() for d in TIER1_DOIS]
        tier1_rows = con.execute(
            "SELECT DISTINCT lower(doi) FROM works WHERE lower(doi) IN ?", [tier1_dois_lower]
        ).fetchall()
        tier1_resolved = tuple(r[0] for r in tier1_rows)
    finally:
        if owns_con:
            con.close()

    duck_path = Path(DUCKDB_PATH)
    duck_size_gb = duck_path.stat().st_size / 1e9 if duck_path.exists() else 0.0

    return Manifest(
        duckdb_path=str(duck_path),
        duckdb_size_gb=duck_size_gb,
        works_total=int(works_total),
        works_with_primary_topic=int(works_with_pt),
        works_with_referenced_works=int(works_with_refs),
        citing_works=int(citing_works),
        citation_edges=int(citation_edges),
        authors=int(authors),
        sources=int(sources),
        institutions=int(institutions),
        topics=int(topics),
        tier1_present_count=len(tier1_resolved),
        tier1_resolved_dois=tier1_resolved,
        snapshot_year_min=year_min,
        snapshot_year_max=year_max,
    )


def derived_dir(create: bool = True) -> Path:
    """Where intermediate parquet artifacts live (corpus, pool*, q1_or_by_year, …)."""
    from . import DATA_ROOT

    out = DATA_ROOT / "data" / "derived"
    if create:
        out.mkdir(parents=True, exist_ok=True)
    return out


def figures_dir(create: bool = True) -> Path:
    out = derived_dir(create=create) / "figures"
    if create:
        out.mkdir(parents=True, exist_ok=True)
    return out


def coverage_warning(m: Manifest) -> str | None:
    """Human-readable warning if the snapshot is partial. Returns None if complete enough."""
    msgs = []
    if m.tier1_present_count < 4:
        msgs.append(
            f"Tier 1 incomplete: {m.tier1_present_count}/4 canonical bridges present. "
            "Run scripts/fetch_tier1_via_api.py + rebuild DuckDB."
        )
    cov = m.coverage_fraction()
    if cov < 0.8:
        msgs.append(
            f"Snapshot coverage ≈ {cov:.0%} of OpenAlex universe ({m.works_total:,} works). "
            "Cited-side field assignment is biased toward recently-updated records."
        )
    return "; ".join(msgs) if msgs else None


def _cli() -> None:
    import json

    m = manifest()
    print(json.dumps(m.to_dict(), indent=2))
    warn = coverage_warning(m)
    if warn:
        print(f"\nWARNING: {warn}")


if __name__ == "__main__":
    _cli()

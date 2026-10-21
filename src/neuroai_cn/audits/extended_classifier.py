"""Extended field-assignment scheme (v3) — broader AI core.

Per ``01-extension-design.md`` in the correction-pipeline output folder, the
v3 AI side includes:

    * subfield 1702 (Artificial Intelligence) MINUS BAD_1702_TOPIC_IDS
      (mis-clustered geology/solar/seismology + orthogonal CS subfields like
      crypto, quantum, signal processing, programming languages, education,
      law, business)
    * subfield 1707 (Computer Vision and Pattern Recognition) — whole
    * topic T10502 ("Advanced Memory and Neural Computing", in subfield 2208)

NEURO side is unchanged (field 28).

The function ``build_extended_field_assignment`` mirrors the production
``q1._build_field_assignment`` in shape (creates temp table ``work_field``
with columns ``work_id, year, field``) so every analysis module can opt into
the v3 scheme by calling this instead of the production builder.

The v3 scheme is a methodology change vs the locked E1 spec
("AI = subfield 1702"). It is documented and surfaced for user sign-off,
NOT silently swapped in. Production scripts continue to use the curated 35.
"""

from __future__ import annotations

import logging

import duckdb

from ..utils.duckdb import NEURO_FIELD_ID

logger = logging.getLogger(__name__)

AI_SUBFIELD_1702 = "https://openalex.org/subfields/1702"
AI_SUBFIELD_1707 = "https://openalex.org/subfields/1707"
NEURAL_MEMORY_TOPIC_2208 = "https://openalex.org/T10502"

# Topics inside subfield 1702 that are mis-clustered (geology / solar /
# seismology) or orthogonal to ML/AI (crypto, quantum, signals, programming
# languages, education, law, business). Excluded from the v3 AI side.
# Count = 26 (was originally documented as 27; T11017 removed 2026-05-14
# because it belongs to subfield 1707, not 1702 — the BAD entry was a no-op).
BAD_1702_TOPIC_IDS: frozenset[str] = frozenset(
    [
        # Documented OpenAlex artifact — 51k → 2.82M jump in 2025-11-06 re-export
        "https://openalex.org/T12157",  # Geochemistry and Geologic Mapping
        # Mis-clustered into 1702 — actually solar physics
        "https://openalex.org/T11276",  # Solar Radiation and Photovoltaics
        # Mis-clustered — geophysics
        "https://openalex.org/T13018",  # Seismology and Earthquake Studies
        # Orthogonal CS sub-areas
        "https://openalex.org/T10020",  # Quantum Information and Cryptography
        "https://openalex.org/T10682",  # Quantum Computing Algorithms and Architecture
        "https://openalex.org/T10237",  # Cryptography and Data Security
        "https://openalex.org/T10764",  # Privacy-Preserving Technologies in Data
        "https://openalex.org/T11130",  # Coding theory and cryptography
        "https://openalex.org/T10951",  # Cryptographic Implementations and Security
        "https://openalex.org/T11424",  # Security and Verification in Computing
        "https://openalex.org/T10711",  # Target Tracking and Data Fusion in Sensor Networks
        "https://openalex.org/T11598",  # Internet Traffic Analysis and Secure E-voting
        "https://openalex.org/T12131",  # Wireless Signal Modulation Classification
        # NB: T11017 (Chaos-based Image/Signal Encryption) removed 2026-05-14 —
        # it is a topic of subfield 1707, not 1702. Under the SQL logic, the
        # 1707 branch was already classifying T11017 as `ai`, so the BAD entry
        # was a dead row.
        "https://openalex.org/T10126",  # Logic, programming, and type systems
        "https://openalex.org/T10639",  # Advanced Software Engineering Methodologies
        # Education
        "https://openalex.org/T13567",  # AI and Multimedia in Education
        "https://openalex.org/T13559",  # Educational Technology Systems
        "https://openalex.org/T11902",  # Intelligent Tutoring Systems
        "https://openalex.org/T12260",  # Educational Technology and Pedagogy
        "https://openalex.org/T14335",  # Educational Robotics and Engineering
        # Business / law / policy
        "https://openalex.org/T14064",  # Organizational and Employee Performance
        "https://openalex.org/T13851",  # Law, AI, and Intellectual Property
        "https://openalex.org/T12128",  # AI in Service Interactions
        # Misc orthogonal
        "https://openalex.org/T11269",  # Algorithms and Data Compression (general CS)
        "https://openalex.org/T13935",  # Mathematical Control Systems and Analysis
        "https://openalex.org/T14175",  # Intuitionistic Fuzzy Systems Applications
    ]
)


def build_extended_field_assignment(
    con: duckdb.DuckDBPyConnection,
    year_min: int = 1990,
    year_max: int = 2025,
    table_name: str = "work_field",
) -> dict[str, int]:
    """Build temp table ``work_field(work_id, year, field)`` using the v3
    extended classifier. Returns a dict with population sizes per label.
    """
    bad_topics = "[" + ",".join("'" + t + "'" for t in BAD_1702_TOPIC_IDS) + "]"
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE {table_name} AS
        SELECT
            w.id AS work_id,
            w.publication_year AS year,
            CASE
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
            END AS field
        FROM works w
        WHERE w.publication_year BETWEEN {year_min} AND {year_max}
        """
    )
    rows = con.execute(
        f"""
        SELECT field, COUNT(*) AS n
        FROM {table_name}
        GROUP BY field
        """
    ).fetchall()
    pop = {f: int(n) for f, n in rows}
    logger.info(
        "Extended field assignment: %s",
        ", ".join(f"{k}={v:,}" for k, v in sorted(pop.items())),
    )
    return pop

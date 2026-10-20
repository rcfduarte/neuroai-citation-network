"""Pool 2 — Thematic keywords (operational NeuroAI).

Boolean templates A-E from Prep-2 §5. Each template fires on a title-substring
regex against the works table. Title-only matching is a known limitation:
OpenAlex abstracts (`abstract_inverted_index`) were dropped from our parquet
projection, so any phrase that requires abstract-only context is missed
(reduces recall ~30-50% vs title+abstract).

Exclusion logic (Prep-2 §4 T1-T10) is applied as an `excluded` flag rather
than a hard filter, so downstream code can choose strict vs permissive
modes. Per A3 (foundation): memristor + optical implementations are NOT
excluded — they are real neuromorphic hardware.

Output: data/derived/pool2.parquet with columns
    work_id, in_pool=true, source_tag='pool2',
    sub_pool (list of 'A'..'E' template hits),
    excluded BOOLEAN  (TRUE if a T1-T10 trap fires uncompensated)
"""

from __future__ import annotations

import argparse
import logging
import time

import duckdb

from ..utils.duckdb import derived_dir, get_connection, set_temp_directory

logger = logging.getLogger(__name__)


def _re_or(*phrases: str) -> str:
    """Build an OR regex from phrase strings. Returns SQL-safe regex string.

    Phrases are matched as substrings case-insensitively. Single quotes are
    doubled for SQL embedding; backslashes are doubled for regex escape.
    Special regex meta-chars are NOT escaped — phrases must be plain text
    plus optional hyphens. (No `.`, `*`, `?`, `+`, `[`, `]`, `(`, `)` in
    any template phrase.)
    """
    escaped = [p.replace("\\", "\\\\").replace("'", "''") for p in phrases]
    return "(" + "|".join(escaped) + ")"


# Template A — High-precision core (Prep-2 §5)
TEMPLATE_A_PHRASES = (
    "predictive coding",
    "free energy principle",
    "active inference",
    "feedback alignment",
    "equilibrium propagation",
    "target propagation",
    "biologically plausible backpropagation",
    "credit assignment in the brain",
    "representational similarity analysis",
    "Brain-Score",
    "surrogate gradient",
    "neuromorphic",
    "successor representation",
    "grid cell",
    "place cell",
    "canonical microcircuit",
    "reward prediction error",
    "meta-reinforcement learning",
    "distributional reinforcement learning",
    "thousand brains",
    "HMAX",
    "CORnet",
)

# Template B — Cortex-model conjunction (CNN/RNN/Transformer × cortical region × model/encoding)
TEMPLATE_B_NETS = (
    "convolutional neural network",
    " CNN ",
    " CNNs ",
    "deep neural network",
    "transformer",
    "recurrent neural network",
    " RNN ",
    " RNNs ",
    "LSTM",
)
TEMPLATE_B_REGIONS = (
    "ventral stream",
    " V1 ",
    " V4 ",
    "inferotemporal",
    "IT cortex",
    "auditory cortex",
    "prefrontal cortex",
    "hippocampus",
    "striatum",
    "cerebellum",
    "motor cortex",
    "parietal cortex",
    "entorhinal cortex",
    "brain region",
    "cortical area",
)
TEMPLATE_B_VERBS = (
    "model",
    "prediction",
    "encoding",
    "representation",
    "similarity",
    "alignment",
    "neural response",
    "fMRI",
    "ECoG",
    " MEG ",
    "electrophysiology",
    "single-unit",
)

# Template C — Plausible learning / plasticity
TEMPLATE_C_BIO = (
    "biologically plausible",
    "bio-plausible",
    "biologically motivated",
    "three-factor learning",
    "local learning rule",
    "Hebbian",
    "STDP",
    "spike-timing-dependent",
    "weight transport",
    "credit assignment",
    "backpropagation alternative",
)
TEMPLATE_C_NETS = (
    "deep learning",
    "neural network",
    "gradient",
    "backpropagation",
    "spiking neural network",
    " SNN ",
    "recurrent network",
)

# Template D — LLM / language / brain
TEMPLATE_D_LLM = (
    "large language model",
    " LLM ",
    " LLMs ",
    "transformer",
    " GPT",
    " BERT",
    "language model",
    "self-supervised language",
)
TEMPLATE_D_BRAIN = (
    "fMRI",
    "ECoG",
    " MEG ",
    "brain activity",
    "neural response",
    "cortex",
    "Broca",
    "language network",
    "temporal cortex",
    "encoding model",
    "psycholinguistic",
)

# Template E — Cognitive-map / RL-neuro
TEMPLATE_E_NEURO = (
    "successor representation",
    "hippocampus",
    "entorhinal",
    "grid cell",
    "place cell",
    "Tolman-Eichenbaum",
    "cognitive map",
)
TEMPLATE_E_RL = (
    "reinforcement learning",
    " RL ",
    "deep RL",
    " RNN ",
    "world model",
    "planning",
    "latent dynamics",
    "model-based",
    "neural network",
)


# Exclusion logic (Prep-2 §4). We implement T1, T2, T6 — title-tractable.
# T3, T4, T5, T7, T8, T9, T10 are abstract-dependent and marked but not enforced
# at this stage.
T1_NEURO_TOKENS = (
    "brain",
    "cortex",
    "neuron",
    "neural circuit",
    "cortical",
    "hippocampus",
    "cerebellum",
    "striatum",
    "synaptic",
    "dendritic",
    "neurophysiology",
    "electrophysiology",
    "fMRI",
    "MEG",
    "spike",
    "single-unit",
)
T2_MEDICAL_DL = (
    "deep learning for diagnosis",
    "deep learning for segmentation",
    "deep learning for classification of seizure",
    "Alzheimer's detection",
    "tumour segmentation",
    "tumor segmentation",
    "lesion segmentation",
    "white matter segmentation",
    "MRI artefact",
    "MRI artifact",
)
T2_RESCUE = (
    "model of cortex",
    "neural representation",
    "brain-like",
    "mechanistic",
    "encoding model",
    "ANN-brain alignment",
    "brain alignment",
)
T6_OPTIM = (
    "ant colony",
    "genetic algorithm",
    "particle swarm",
    "firefly algorithm",
    "bee algorithm",
    "grey wolf optimizer",
    "immune system algorithm",
)


def _tune(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("PRAGMA threads=6")
    con.execute("PRAGMA memory_limit='15GB'")
    set_temp_directory(con)


def build(con: duckdb.DuckDBPyConnection | None = None) -> dict:
    """Build pool2.parquet from Boolean keyword templates against title."""
    owns_con = con is None
    if owns_con:
        con = get_connection(read_only=True)
    try:
        _tune(con)
        t0 = time.time()
        out_path = derived_dir() / "pool2.parquet"

        # We score each work against five regex predicates and the exclusion traps.
        # A work is in Pool 2 iff at least one template fires.
        # `title` is the OpenAlex display_name; some works have None.
        # All matches are case-insensitive (regexp_matches with 'i' flag).
        a_re = _re_or(*TEMPLATE_A_PHRASES)
        b_nets = _re_or(*TEMPLATE_B_NETS)
        b_regs = _re_or(*TEMPLATE_B_REGIONS)
        b_verbs = _re_or(*TEMPLATE_B_VERBS)
        c_bio = _re_or(*TEMPLATE_C_BIO)
        c_nets = _re_or(*TEMPLATE_C_NETS)
        d_llm = _re_or(*TEMPLATE_D_LLM)
        d_brain = _re_or(*TEMPLATE_D_BRAIN)
        e_neuro = _re_or(*TEMPLATE_E_NEURO)
        e_rl = _re_or(*TEMPLATE_E_RL)

        t1_neuro = _re_or(*T1_NEURO_TOKENS)
        t2_med = _re_or(*T2_MEDICAL_DL)
        t2_rescue = _re_or(*T2_RESCUE)
        t6_opt = _re_or(*T6_OPTIM)

        sql = f"""
        COPY (
            WITH scored AS (
                SELECT
                    w.id AS work_id,
                    w.publication_year AS year,
                    coalesce(w.title, w.display_name, '') AS hay,
                    regexp_matches(coalesce(w.title, w.display_name, ''), '{a_re}', 'i') AS hit_a,
                    (regexp_matches(coalesce(w.title, w.display_name, ''), '{b_nets}', 'i')
                     AND regexp_matches(coalesce(w.title, w.display_name, ''), '{b_regs}', 'i')
                     AND regexp_matches(coalesce(w.title, w.display_name, ''), '{b_verbs}', 'i')) AS hit_b,
                    (regexp_matches(coalesce(w.title, w.display_name, ''), '{c_bio}', 'i')
                     AND regexp_matches(coalesce(w.title, w.display_name, ''), '{c_nets}', 'i')) AS hit_c,
                    (regexp_matches(coalesce(w.title, w.display_name, ''), '{d_llm}', 'i')
                     AND regexp_matches(coalesce(w.title, w.display_name, ''), '{d_brain}', 'i')) AS hit_d,
                    (regexp_matches(coalesce(w.title, w.display_name, ''), '{e_neuro}', 'i')
                     AND regexp_matches(coalesce(w.title, w.display_name, ''), '{e_rl}', 'i')) AS hit_e
                FROM works w
                WHERE w.publication_year BETWEEN 1990 AND 2026
                  AND coalesce(w.title, w.display_name) IS NOT NULL
            ),
            tagged AS (
                SELECT
                    work_id,
                    year,
                    hay,
                    hit_a, hit_b, hit_c, hit_d, hit_e,
                    list_filter(['A','B','C','D','E'], (x, i) -> CASE i
                        WHEN 1 THEN hit_a WHEN 2 THEN hit_b WHEN 3 THEN hit_c
                        WHEN 4 THEN hit_d WHEN 5 THEN hit_e END
                    ) AS sub_pool,
                    -- T1: generic 'neural network' without neuro tokens.
                    (regexp_matches(hay, '\\bneural network\\b', 'i')
                     AND NOT regexp_matches(hay, '{t1_neuro}', 'i')) AS trap_t1,
                    -- T2: medical-DL, unless rescued.
                    (regexp_matches(hay, '{t2_med}', 'i')
                     AND NOT regexp_matches(hay, '{t2_rescue}', 'i')) AS trap_t2,
                    -- T6: bio-metaphor optimization, unless rescued by neuro tokens.
                    (regexp_matches(hay, '{t6_opt}', 'i')
                     AND NOT regexp_matches(hay, '{t1_neuro}', 'i')) AS trap_t6
                FROM scored
                WHERE hit_a OR hit_b OR hit_c OR hit_d OR hit_e
            )
            SELECT
                work_id,
                TRUE AS in_pool,
                'pool2' AS source_tag,
                sub_pool,
                (trap_t1 OR trap_t2 OR trap_t6) AS excluded
            FROM tagged
        )
        TO '{out_path}' (FORMAT 'parquet', COMPRESSION 'snappy')
        """
        con.execute(sql)
        t_query = time.time() - t0

        # Stats
        stats = con.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN list_contains(sub_pool, 'A') THEN 1 ELSE 0 END) AS hits_a,
                SUM(CASE WHEN list_contains(sub_pool, 'B') THEN 1 ELSE 0 END) AS hits_b,
                SUM(CASE WHEN list_contains(sub_pool, 'C') THEN 1 ELSE 0 END) AS hits_c,
                SUM(CASE WHEN list_contains(sub_pool, 'D') THEN 1 ELSE 0 END) AS hits_d,
                SUM(CASE WHEN list_contains(sub_pool, 'E') THEN 1 ELSE 0 END) AS hits_e,
                SUM(CASE WHEN excluded THEN 1 ELSE 0 END) AS excluded_traps
            FROM read_parquet('{out_path}')
            """
        ).fetchone()
        total, hits_a, hits_b, hits_c, hits_d, hits_e, excl = stats

        elapsed = time.time() - t0
        logger.info(
            "Pool 2: %d works (A=%d, B=%d, C=%d, D=%d, E=%d, traps=%d) in %.1fs",
            total,
            hits_a,
            hits_b,
            hits_c,
            hits_d,
            hits_e,
            excl,
            elapsed,
        )
        return {
            "pool2_works": int(total),
            "hits_template_A": int(hits_a),
            "hits_template_B": int(hits_b),
            "hits_template_C": int(hits_c),
            "hits_template_D": int(hits_d),
            "hits_template_E": int(hits_e),
            "exclusion_traps_fired": int(excl),
            "out_path": str(out_path),
            "elapsed_query_s": round(t_query, 1),
            "elapsed_total_s": round(elapsed, 1),
            "note_title_only": (
                "Title-only matching: OpenAlex abstracts dropped from parquet projection. "
                "Recall ~30-50% lower than title+abstract."
            ),
        }
    finally:
        if owns_con:
            con.close()


def _cli() -> None:
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    summary = build()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    _cli()

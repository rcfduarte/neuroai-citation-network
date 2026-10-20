"""Q4 — paper-type classifier (methods/research/review) + track-based taxonomy.

Two regex-based classifications for the top-1000 bridge papers:

(A) **Paper type**:
    - **methods** — titles naming a specific algorithm/tool/library/benchmark/dataset
    - **review**  — explicit "review", "survey", "perspective", "opinion", "introduction"
    - **research** — everything else (default)

(B) **Track-based taxonomy** (replaces Leiden clusters with a hand-curated 2-track
    structure):
    - **Bio-plausible AI**
        - Neuromorphic hardware
        - Spiking neural networks
        - Bio-plausible learning rules
        - Reservoir / liquid state
    - **Applied ML for brain**
        - Medical imaging methods
        - Neural decoding / encoding models
        - Brain–computer interface
        - Biomedical deep learning
    - **Foundational DL/AI**       (the AlexNet / ResNet / Adam / Transformer axis)
    - **Bridge manifestos & theory** (Hassabis / Richards / Marblestone / Zador / Yamins)
    - **Statistical methods**       (RandomForest / SVM / scikit-learn / R / ROC)
    - **Other / cross-domain**      (default)

Outputs:
    corrections/20260508/q4_classified_nodes.parquet — augments clustering_nodes
        with new columns: paper_type, track, subfield
"""

from __future__ import annotations

import logging
import re
import sys

import pandas as pd

from .. import config

logger = logging.getLogger(__name__)

CORRECTIONS_DIR = config.CORRECTIONS_DIR / "20260508"

# ---------- Paper type classifier ----------
REVIEW_RGX = re.compile(
    r"\b(review|survey|perspective|opinion|introduction\b(?!\s+to\s+the))",
    re.IGNORECASE,
)

# Order matters: methods detector includes named tools, benchmarks, optimizers, datasets
METHODS_PATTERNS = [
    # Generic methods/tools/algorithms language
    r"\b(method|methods|algorithm|toolbox|toolkit|library|software|package|framework|"
    r"benchmark|pipeline|database|dataset)\b",
    # Specific tools / software (case-insensitive)
    r"\b(fsl|spm|ants|afni|brats|scikit-learn|libsvm|imagenet|coco|nipype|nibabel)\b",
    # Architectures / optimizers / techniques (named)
    r"\b(alexnet|vgg\b|resnet|inception|googlenet|densenet|transformer|bert|gpt-?\d|"
    r"clip|dall-?e|stable\s+diffusion|adam\b|dropout|batch\s*norm|attention is all|"
    r"layernorm|gan|generative adversarial|word2vec|glove|elmo)\b",
    # Statistical methods
    r"\b(random\s+forests?|support\s+vector|svm\b|principal\s+component|gradient\s+boost|"
    r"xgboost|elm\b|gaussian\s+process|markov\s+chain|monte\s+carlo|bayesian\s+optimization|"
    r"roc\s+analysis|roc\s+curve)\b",
    # Models / equations / specifications
    r"\b(model\s+of|equation|formal\s+specification|protocol)\b",
]
METHODS_RGX = re.compile("|".join(METHODS_PATTERNS), re.IGNORECASE)


def classify_paper_type(title: str) -> str:
    if not isinstance(title, str) or not title:
        return "research"
    if REVIEW_RGX.search(title):
        return "review"
    if METHODS_RGX.search(title):
        return "methods"
    return "research"


# ---------- Track-based taxonomy ----------

TRACK_RULES: list[tuple[str, str, re.Pattern]] = [
    # (track, subfield, regex)
    # --- Bio-plausible AI ---
    (
        "Bio-plausible AI",
        "Neuromorphic hardware",
        re.compile(
            r"\b(loihi|truenorth|spinnaker|memristor|memristive|neuromorphic\s+(chip|hardware|"
            r"processor|computing)|brain-?inspired\s+(hardware|chip))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Bio-plausible AI",
        "Spiking neural networks",
        re.compile(
            r"\b(spiking\s+neural|spiking\s+neuron|snn\b|integrate-?and-?fire|"
            r"liquid\s+state\s+machine|reservoir\s+computing|izhikevich)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Bio-plausible AI",
        "Bio-plausible learning",
        re.compile(
            r"\b(stdp|spike-?timing|e-?prop|dendritic\s+(backprop|computation)|"
            r"feedback\s+alignment|equilibrium\s+propagation|three-?factor|"
            r"biolog\w+\s+plausible|biolog\w+-?inspired\s+learning|hebbian)\b",
            re.IGNORECASE,
        ),
    ),
    # --- Applied ML for brain ---
    (
        "Applied ML for brain",
        "Medical imaging methods",
        re.compile(
            r"\b(image\s+segmentation|image\s+registration|tumor\s+segmentation|brats|"
            r"diffeomorphic|fsl|spm\b|ants\b|afni|nibabel|nipype|voxel-?based|cortical\s+"
            r"parcellation|atlas-?based|freesurfer)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Applied ML for brain",
        "Neural decoding / encoding",
        re.compile(
            r"\b(neural\s+decoding|brain\s+decoding|encoding\s+model|representational\s+"
            r"similarity|mvpa\b|multi-?voxel|deep\s+\w+\s+(cortex|brain)|hierarchical\s+"
            r"models?\s+of\s+visual|performance-?optimized\s+hierarchical)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Applied ML for brain",
        "Brain–computer interface",
        re.compile(
            r"\b(brain[-\s]computer\s+interface|bci\b|neural\s+prosthe|"
            r"motor\s+cortex\s+decoding|cursor\s+control)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Applied ML for brain",
        "Biomedical deep learning",
        re.compile(
            r"\b(deep\s+learning\s+(in|for)\s+(medical|biomedical|radiology|pathology|"
            r"healthcare|diagnosis)|dermatologist-?level|retinal\s+\w+\s+diabetic|"
            r"breast\s+cancer\s+\w+\s+deep|deep\s+learning\s+for\s+\w+\s+(diagnosis|imaging))\b",
            re.IGNORECASE,
        ),
    ),
    # --- Foundational DL/AI ---
    (
        "Foundational DL/AI",
        "Deep learning architectures",
        re.compile(
            r"\b(deep\s+residual|deep\s+convolutional|imagenet|alexnet|vgg|resnet|"
            r"inception|densenet|going\s+deeper|generative\s+adversarial|"
            r"very\s+deep|wide\s+residual|efficient\w+|mobilenet|squeeze)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Foundational DL/AI",
        "Optimization / regularization",
        re.compile(
            r"\b(adam\b|adamw|momentum|sgd\b|dropout|batch\s+normalization|"
            r"layer\s+normalization|weight\s+decay|gradient\s+clipping|"
            r"early\s+stopping|warm\s+restart)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Foundational DL/AI",
        "Attention / transformers / LLMs",
        re.compile(
            r"\b(attention\s+is\s+all|transformer|bert\b|gpt-?\d|t5|self-?attention|"
            r"vision\s+transformer|vit\b|language\s+model|word2vec|glove|elmo|"
            r"large\s+language|llama|palm|claude)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Foundational DL/AI",
        "Reinforcement learning",
        re.compile(
            r"\b(deep\s+q-?network|reinforcement\s+learning|policy\s+gradient|actor-?critic|"
            r"alpha\s*(go|zero|fold)|atari|mujoco|playing\s+atari|deepmind|td-?learning|"
            r"q-?learning)\b",
            re.IGNORECASE,
        ),
    ),
    # --- Bridge manifestos & theory ---
    (
        "Bridge manifestos & theory",
        "Manifestos / position papers",
        re.compile(
            r"\b(catalyz\w+\s+next-?generation|neuroai|deep\s+learning\s+framework\s+"
            r"for\s+neuroscience|cognitive\s+computational\s+neuroscience|toward\s+\w+\s+"
            r"artificial\s+intelligence|natural\s+intelligence|brain\s+inspires|"
            r"rubric\s+for\s+human-?like)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Bridge manifestos & theory",
        "Theory / computational principles",
        re.compile(
            r"\b(predictive\s+coding|free\s+energy|bayesian\s+brain|hierarchical\s+temporal|"
            r"normative\s+\w+|optimal\s+control|theoretical\s+neuroscience|"
            r"computational\s+principles?\s+of|prefrontal\s+cortex.*meta-?learning)\b",
            re.IGNORECASE,
        ),
    ),
    # --- Statistical methods ---
    (
        "Statistical methods",
        "Classical ML / statistics",
        re.compile(
            r"\b(random\s+forests?|support\s+vector|svm\b|libsvm|scikit-?learn|"
            r"r:\s+a\s+language|principal\s+component|t-?sne|umap|"
            r"hierarchical\s+clustering|markov\s+chain|monte\s+carlo|gradient\s+boost|"
            r"xgboost|extreme\s+learning|gaussian\s+process|roc\s+analysis)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Statistical methods",
        "Complex networks / graph theory",
        re.compile(
            r"\b(small-?world|scale-?free|community\s+structure|graph\s+neural|"
            r"network\s+motif|complex\s+networks?|emergence\s+of\s+scaling|"
            r"betweenness\s+centrality|fast\s+unfolding)\b",
            re.IGNORECASE,
        ),
    ),
]


def classify_track(title: str) -> tuple[str, str]:
    """Return (track, subfield). Default: ('Other / cross-domain', '')."""
    if not isinstance(title, str) or not title:
        return ("Other / cross-domain", "")
    for track, sf, rgx in TRACK_RULES:
        if rgx.search(title):
            return (track, sf)
    return ("Other / cross-domain", "")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    nodes = pd.read_parquet(CORRECTIONS_DIR / "clustering_nodes.parquet")
    nodes["paper_type"] = nodes["title"].apply(classify_paper_type)
    tracks = nodes["title"].apply(classify_track)
    nodes["track"] = [t[0] for t in tracks]
    nodes["subfield"] = [t[1] for t in tracks]

    out = CORRECTIONS_DIR / "q4_classified_nodes.parquet"
    nodes.to_parquet(out, index=False)
    logger.info("Wrote %s (%d rows)", out, len(nodes))
    logger.info(
        "\nPaper-type distribution:\n%s",
        nodes["paper_type"].value_counts().to_string(),
    )
    logger.info(
        "\nTrack distribution:\n%s",
        nodes["track"].value_counts().to_string(),
    )
    logger.info(
        "\nSubfield distribution (top 20):\n%s",
        nodes[nodes["subfield"] != ""]["subfield"].value_counts().head(20).to_string(),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

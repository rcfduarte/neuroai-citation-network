"""Supplement figure: what the AI->Neuro citation flow is made of.

Figure 1's gold line measures how strongly neuroscience reaches into AI. It says
nothing about *what kind* of AI is reached for. This figure decomposes that flow
by the OpenAlex topic of the cited AI work, grouped into six categories, and
draws it under both field classifiers so the reader can see how much of the
picture is definitional.

Panels:
    A  category share of the flow by citing year, extended classifier
    B  the same under the strict 35-topic AI core (subfield 1707 excluded)
    C  overall category share, the two classifiers side by side

Inputs (from ``neuroai_cn.audits.flow_composition``):
    data/derived/flow_composition_{extended,strict}.parquet

Outputs:
    figures/fig_flow_composition.{png,svg}
    data/derived/flow_composition_categories.csv   the grouping, for the supplement

Run:
    python -m neuroai_cn.figures.flow_composition_fig
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from ..utils.duckdb import derived_dir
from .style import TRANSMITTER, apply_style

logger = logging.getLogger(__name__)

YEAR_MIN, YEAR_MAX = 1995, 2023  # 2024-25 excluded: OpenAlex rebuild, unstable.

# ---------------------------------------------------------------------------
# Topic -> category. Hand-assigned over the 87 topics that receive any
# neuroscience citation under the extended classifier. Every topic is assigned;
# nothing is dropped. The mapping is the judgement call in this figure and is
# printed to CSV so a reader can disagree with any single line of it.
# ---------------------------------------------------------------------------

CATEGORIES: dict[str, list[str]] = {
    "Neuroimaging and medical image processing": [
        "Medical Image Segmentation Techniques",
        "AI in cancer detection",
        "Machine Learning in Healthcare",
        "Digital Imaging for Blood Diseases",
        "Image and Signal Denoising Methods",
        "Image Enhancement Techniques",
        "Advanced Image Processing Techniques",
        "Digital Image Processing Techniques",
        "Image Processing and 3D Reconstruction",
    ],
    "General statistics and ML software": [
        "Data Analysis with R",
        "Computational Physics and Python Applications",
        "Bayesian Modeling and Causal Inference",
        "Bayesian Methods and Mixture Models",
        "Gaussian Processes and Bayesian Inference",
        "Machine Learning and Data Classification",
        "Machine Learning and Algorithms",
        "Machine Learning and ELM",
        "Advanced Clustering Algorithms Research",
        "Anomaly Detection Techniques and Applications",
        "Imbalanced Data Classification Techniques",
        "Data Visualization and Analytics",
        "Metaheuristic Optimization Algorithms Research",
        "Evolutionary Algorithms and Applications",
        "Statistical and Computational Modeling",
        "Data Stream Mining Techniques",
        "Graph Theory and Algorithms",
        "Explainable Artificial Intelligence (XAI)",
        "Adversarial Robustness in Machine Learning",
    ],
    "Foundational deep learning and AI": [
        "Neural Networks and Applications",
        "Advanced Neural Network Applications",
        "Advanced Memory and Neural Computing",
        "Natural Language Processing Techniques",
        "Generative Adversarial Networks and Image Synthesis",
        "Reinforcement Learning in Robotics",
        "Domain Adaptation and Few-Shot Learning",
        "Topic Modeling",
        "Speech Recognition and Synthesis",
        "Speech and dialogue systems",
        "Advanced Graph Neural Networks",
        "Neural Networks and Reservoir Computing",
        "Stochastic Gradient Optimization Techniques",
        "Advanced Text Analysis Techniques",
        "Multimodal Machine Learning Applications",
        "Cognitive Computing and Networks",
        "Text and Document Classification Technologies",
        "Sentiment Analysis and Opinion Mining",
        "Artificial Intelligence in Games",
        "Multi-Agent Systems and Negotiation",
        "AI-based Problem Solving and Planning",
        "Logic, Reasoning, and Knowledge",
        "Semantic Web and Ontologies",
        "Fuzzy Logic and Control Systems",
        "Artificial Intelligence Applications",
        "Advanced Computational Techniques and Applications",
    ],
    "Brain-adjacent modelling": [
        "Cognitive Science and Mapping",
        "Visual Attention and Saliency Detection",
        "Psychiatry, Mental Health, Neuroscience",
        "Linguistic Studies and Language Acquisition",
    ],
    "Computer vision applications": [
        "Face and Expression Recognition",
        "Face recognition and analysis",
        "Image Retrieval and Classification Techniques",
        "Advanced Image and Video Retrieval Techniques",
        "Advanced Vision and Imaging",
        "Human Pose and Action Recognition",
        "Video Surveillance and Tracking Methods",
        "Handwritten Text Recognition Techniques",
        "Image and Video Quality Assessment",
        "Image and Object Detection Techniques",
        "Video Analysis and Summarization",
        "Augmented Reality Applications",
        "Optical measurement and interference techniques",
        "Robotic Path Planning Algorithms",
        "Image and Video Stabilization",
    ],
    "Off-topic or misclassified": [
        "Music Technology and Sound Studies",
        "Context-Aware Activity Recognition Systems",
        "Advanced Data Compression Techniques",
        "Advanced Steganography and Watermarking Techniques",
        "Chaos-based Image/Signal Encryption",
        "Digital Media Forensic Detection",
        "Hate Speech and Cyberbullying Detection",
        "Currency Recognition and Detection",
        "Authorship Attribution and Profiling",
        "Text Readability and Simplification",
        "Computer Science and Engineering",
        "Diverse Interdisciplinary Research Studies",
        "Advanced Technologies in Various Fields",
        "Experience-Based Knowledge Management",
    ],
}

ORDER = [
    "Neuroimaging and medical image processing",
    "General statistics and ML software",
    "Computer vision applications",
    "Foundational deep learning and AI",
    "Brain-adjacent modelling",
    "Off-topic or misclassified",
]

COLORS = {
    "Neuroimaging and medical image processing": TRANSMITTER["mustard"],
    "General statistics and ML software": TRANSMITTER["coral"],
    "Computer vision applications": TRANSMITTER["purple"],
    "Foundational deep learning and AI": TRANSMITTER["teal"],
    "Brain-adjacent modelling": TRANSMITTER["navy"],
    "Off-topic or misclassified": TRANSMITTER["gray"],
}

TOPIC_TO_CAT = {t: c for c, ts in CATEGORIES.items() for t in ts}


def load(classifier: str) -> pd.DataFrame:
    path = derived_dir() / f"flow_composition_{classifier}.parquet"
    df = pd.read_parquet(path)
    df = df[(df.citing_year >= YEAR_MIN) & (df.citing_year <= YEAR_MAX)].copy()
    df["category"] = df.topic.map(TOPIC_TO_CAT)
    missing = df[df.category.isna()].topic.unique()
    if len(missing):
        logger.warning(
            "[%s] %d unmapped topics -> 'Off-topic or misclassified': %s",
            classifier,
            len(missing),
            list(missing)[:8],
        )
        df["category"] = df.category.fillna("Off-topic or misclassified")
    return df


def by_year_share(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["citing_year", "category"], as_index=False).n_cites.sum()
    p = g.pivot(index="citing_year", columns="category", values="n_cites").fillna(0.0)
    for c in ORDER:
        if c not in p.columns:
            p[c] = 0.0
    p = p[ORDER]
    return p.div(p.sum(axis=1), axis=0) * 100.0


def overall_share(df: pd.DataFrame) -> pd.Series:
    s = df.groupby("category").n_cites.sum().reindex(ORDER).fillna(0.0)
    return s / s.sum() * 100.0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    apply_style()

    ext, strict = load("extended"), load("strict")
    ext_y, strict_y = by_year_share(ext), by_year_share(strict)
    ext_o, strict_o = overall_share(ext), overall_share(strict)

    fig = plt.figure(figsize=(13.5, 5.4))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 0.75], wspace=0.30)
    axA, axB, axC = (fig.add_subplot(gs[0, i]) for i in range(3))

    for ax, data, title in (
        (axA, ext_y, "A  Published (extended) AI definition"),
        (axB, strict_y, "B  Strict AI core, computer vision excluded"),
    ):
        ax.stackplot(
            data.index,
            [data[c].values for c in ORDER],
            colors=[COLORS[c] for c in ORDER],
            edgecolor="white",
            linewidth=0.4,
        )
        ax.set_xlim(YEAR_MIN, YEAR_MAX)
        ax.set_ylim(0, 100)
        ax.set_title(title, loc="left", fontsize=10.5, pad=9)
        ax.set_xlabel("Year of the citing neuroscience paper")
        ax.set_ylabel("Share of neuroscience's citations into AI (%)")
        ax.grid(axis="y", alpha=0.25)

    idx = range(len(ORDER))
    h = 0.38
    axC.barh(
        [i + h / 2 for i in idx],
        ext_o.values,
        height=h,
        color=[COLORS[c] for c in ORDER],
        alpha=0.95,
        label="extended",
    )
    axC.barh(
        [i - h / 2 for i in idx],
        strict_o.values,
        height=h,
        color=[COLORS[c] for c in ORDER],
        alpha=0.45,
        label="strict core",
    )
    axC.set_yticks(list(idx))
    axC.set_yticklabels([])  # categories are named in the shared legend below
    axC.invert_yaxis()
    for i, c in enumerate(ORDER):
        axC.text(
            1.5,
            i,
            c.replace(" and ", " & "),
            va="center",
            ha="left",
            fontsize=8.5,
            color=TRANSMITTER["navy"],
        )
    axC.set_xlabel("Share of the whole flow, 1995-2023 (%)")
    axC.set_title("C  Overall, both definitions", loc="left", fontsize=10.5, pad=9)
    axC.grid(axis="x", alpha=0.25)
    axC.text(
        0.98,
        0.03,
        "solid = extended\nfaded = strict core",
        transform=axC.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        color=TRANSMITTER["gray"],
    )

    handles = [plt.Rectangle((0, 0), 1, 1, color=COLORS[c]) for c in ORDER]
    fig.legend(
        handles,
        ORDER,
        loc="lower center",
        ncol=3,
        frameon=False,
        fontsize=9,
        bbox_to_anchor=(0.5, -0.10),
    )
    fig.suptitle(
        "What neuroscience is citing when it cites AI",
        x=0.008,
        ha="left",
        fontsize=13,
        color=TRANSMITTER["navy"],
    )
    fig.tight_layout(rect=(0, 0.02, 1, 0.94))

    out = Path(__file__).resolve().parents[3] / "figures"
    out.mkdir(exist_ok=True)
    for ext_name in ("png", "svg"):
        fig.savefig(
            out / f"fig_flow_composition.{ext_name}",
            bbox_inches="tight",
            dpi=200 if ext_name == "png" else None,
            transparent=False,
        )
    logger.info("wrote %s/fig_flow_composition.{png,svg}", out)

    rows = [{"category": c, "topic": t} for c in ORDER for t in CATEGORIES[c]]
    pd.DataFrame(rows).to_csv(derived_dir() / "flow_composition_categories.csv", index=False)

    summary = pd.DataFrame({"extended_pct": ext_o.round(1), "strict_pct": strict_o.round(1)})
    summary.to_csv(derived_dir() / "flow_composition_summary.csv")
    print(summary.to_string())
    print(
        f"\ntotal edges  extended: {int(ext.n_cites.sum()):,}   strict: {int(strict.n_cites.sum()):,}"
    )


if __name__ == "__main__":
    main()

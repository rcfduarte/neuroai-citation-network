"""Topic-to-category grouping of the AI works that neuroscience papers cite.

The gold line of Figure 1 (neuroscience papers citing AI) says nothing about what kind of AI
is cited. ``CATEGORIES`` assigns by hand each of the 87 AI topics that receive any citation from
neuroscience under the extended definition to one of six categories; ``ORDER`` is the display
order and ``TOPIC_TO_CAT`` the inverted lookup. ``analysis.export_flow_composition`` imports
both and writes the topic-by-year table to ``results/flow/``; Figure S4.1 is drawn from there.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Topic -> category. Hand-assigned over the 87 topics that receive any
# neuroscience citation under the extended classifier. Every topic is assigned;
# nothing is dropped. The mapping is the judgement call in this analysis and is
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

TOPIC_TO_CAT = {t: c for c, ts in CATEGORIES.items() for t in ts}

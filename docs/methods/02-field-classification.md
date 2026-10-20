# Field classification

This file covers the single most consequential judgment call in the analysis: what counts as a neuroscience paper and what counts as an AI paper. In it I give the extended classifier in full, name all 26 excluded topics with their reasons, give the strict 35-topic counterfactual in full, report the three-scheme triangulation, and state plainly why the named anchor papers cannot justify the extension and what the strict counterfactual shows instead. It does not cover the citation metric that consumes these labels; that is [the citation metric](03-citation-metric.md). The same material, with the field sizes year by year and the audit of the labels, is in [S1](../supplements/S1-data-and-classification.md).

## 1. The scheme

OpenAlex assigns each work a hierarchical `primary_topic` of the form (topic, subfield, field, domain). Throughout, I use the primary topic only, never the full weighted topic list.

- **Neuroscience** is OpenAlex **field 28**, Neuroscience, unrestricted. Every topic in every subfield of field 28 counts.
- **AI** is subfield **1702** (Artificial Intelligence) minus 26 excluded topics, plus subfield **1707** (Computer Vision and Pattern Recognition) in full, plus topic **T10502**.
- Everything else with a primary topic is `other`. A work with no primary topic is `unknown`.

`unknown` is not a small category and it grows: the fraction of works carrying any primary topic falls from 78.6% in 2021 to 65.9% in 2023 and 53.6% in 2024. Roughly half of 2024's literature is unclassifiable by this scheme.

**T10502 is named "Advanced Memory and Neural Computing"**, and it sits in **subfield 2208, Electrical and Electronic Engineering, under the Engineering field**, not under Computer Science. The topic holds 89,949 works published 1990 to 2025 ([`results/corpus/classification_topics.csv`](../../results/corpus/classification_topics.csv)) and is where essentially every neuromorphic-hardware paper lives.

I deliberately did **not** include subfield **1708** (Hardware Architecture): its topics are parallel computing, embedded systems, VLSI testing, real-time scheduling, hardware security, packet processing, cloud computing and energy efficiency, none of which are relevant here. I did **not** include subfield **2208** whole either: it carries over a hundred topics covering power systems, semiconductors, antennas and batteries. I took only T10502 from it.

Implementation: `build_extended_field_assignment` in `src/neuroai_cn/audits/extended_classifier.py`.

## 2. The 26 excluded topics

Widening the AI boundary lets contamination in, so 26 topics inside subfield 1702 are explicitly excluded. They fall into three reason-groups. I re-resolved the names below against the OpenAlex API in July 2026, and they are the current display names; two differ slightly from the comments in the code, and one (`T13559`) carries a typo that is OpenAlex's, not mine. The same 26 topics, grouped by subject and with their works per topic over 1995 to 2023, are in [S1, section 3.4](../supplements/S1-data-and-classification.md).

### Group 1: documented OpenAlex artifact (1 topic)

| ID | Display name | Reason |
|-|-|-|
| T12157 | Geochemistry and Geologic Mapping | Holds 50,854 works published in 2024 and 2,818,121 published in 2025 inside the one snapshot, a 55-fold jump in a year. I attribute it to OpenAlex's November 2025 re-export, four months before the snapshot was frozen, but I have not re-verified that date from the data, only the jump itself. A geology topic sitting inside the artificial-intelligence subfield at that scale would have swamped the AI corpus ([S1, section 3.5](../supplements/S1-data-and-classification.md)). |

### Group 2: mis-clustered into an AI subfield but belonging to another science (2 topics)

| ID | Display name | Reason |
|-|-|-|
| T11276 | Solar Radiation and Photovoltaics | Solar physics and photovoltaic engineering, clustered into 1702 through machine-learning-for-solar-forecasting papers. |
| T13018 | Seismology and Earthquake Studies | Geophysics, clustered in through machine-learning-for-seismology papers. |

### Group 3: computer science with no machine-learning content (23 topics)

| ID | Display name | Specific reason |
|-|-|-|
| T10020 | Quantum Information and Cryptography | Quantum information, orthogonal to ML |
| T10682 | Quantum Computing Algorithms and Architecture | Quantum computing, orthogonal to ML |
| T10237 | Cryptography and Data Security | Cryptography |
| T10764 | Privacy-Preserving Technologies in Data | Privacy engineering |
| T11130 | Coding theory and cryptography | Coding theory |
| T10951 | Cryptographic Implementations and Security | Cryptographic engineering |
| T11424 | Security and Verification in Computing | Formal verification and security |
| T10711 | Target Tracking and Data Fusion in Sensor Networks | Sensor fusion and signal processing |
| T11598 | Internet Traffic Analysis and Secure E-voting | Networking |
| T12131 | Wireless Signal Modulation Classification | Communications signal processing |
| T10126 | Logic, programming, and type systems | Programming-language theory |
| T10639 | Advanced Software Engineering Methodologies | Software engineering |
| T13567 | AI and Multimedia in Education | Education application bucket |
| T13559 | Edcuational Technology Systems | Education application bucket (name misspelled upstream in OpenAlex) |
| T11902 | Intelligent Tutoring Systems and Adaptive Learning | Education application bucket |
| T12260 | Educational Technology and Pedagogy | Education application bucket |
| T14335 | Educational Robotics and Engineering | Education application bucket |
| T14064 | Organizational and Employee Performance | Management and organizational research |
| T13851 | Law, AI, and Intellectual Property | Law and policy |
| T12128 | AI in Service Interactions | Marketing and service research |
| T11269 | Algorithms and Data Compression | General algorithms and compression |
| T13935 | Mathematical Control Systems and Analysis | Control theory |
| T14175 | Intuitionistic Fuzzy Systems Applications | Fuzzy decision theory |

The excluded set is 26 topics. T11017 (Chaos-based Image/Signal Encryption) is not on it because it belongs to subfield 1707, not 1702, and the classifier's SQL labels it `ai` through the 1707 branch. The code is the record; the table above is the code.

Subfield 1707 is included **whole**, including its medical-imaging-applied topics such as T10052 (Medical Image Segmentation). That was a deliberate choice of mine: an AI definition that admits computer vision cannot then hand-pick which computer vision counts.

### Only one exclusion changes any result

I tested the exclusion list rather than asserting it. A leave-one-topic-out sweep re-ran the full odds-ratio series once per excluded topic, each time adding that topic back into the AI corpus, and recorded the largest relative change it produced in either direction in any year. Implementation: `loto_sensitivity` in `src/neuroai_cn/audits/bootstrap_sensitivity.py`; the committed result is [`results/flow/sensitivity_loto.csv`](../../results/flow/sensitivity_loto.csv), which holds 27 candidate topics (the 26 exclusions and T11017, the dead entry removed on 2026-05-14).

| Topic added back | Largest relative change, any year 1990 to 2025 | Largest relative change, 1995 to 2023 |
|-|-:|-:|
| **T12157 (Geochemistry and Geologic Mapping)** | **5.06** | **0.345** |
| T10126 | 0.097 | 0.090 |
| T14335 | 0.081 | 0.081 |
| T11902 | 0.056 | 0.023 |
| T12128 | 0.048 | 0.026 |
| median across the swept topics | 0.018 | 0.018 |

Over the whole series T12157 matters more than fifty times as much as the next-largest exclusion, but that holds only because 2025 is included; inside the fitted years 1995 to 2023 the factor is about four ([S2, section 4.7](../supplements/S2-citation-flow.md)). The median excluded topic moves the odds ratio by under 2% either way. So the exclusion list is doing one job that matters and 25 cosmetic ones, and no single re-admitted topic reverses the order of the two lines in any year. That is a comfortable place to be: a reader who dislikes my list can reconstruct almost any variant of it and land on the same curves, provided they also drop the geology.

## 3. The extension's justification, and why the anchor argument fails

One could justify the extended AI definition by saying that subfield 1702 on its own exiles **eighteen canonical AI anchors** into neighboring subfields (a count that cannot be reconstructed from any list), citing LeCun, Bengio and Hinton's 2015 *Nature* review, Hassabis and colleagues' 2017 *Neuron* piece, the Loihi and SpiNNaker neuromorphic hardware papers, and Bellec's e-prop. I do not rely on that argument, for the two reasons that follow.

**Most of those examples prove nothing, because they are the objects under study.** Hassabis 2017 is a NeuroAI position piece. Loihi and SpiNNaker are neuromorphic engineering. Bellec's e-prop could be filed under neuroscience as readily as under AI. These are boundary objects, and whether they count as AI is close to the very question this analysis asks. Using them to fix the boundary would have me arguing in a circle. Of the named anchors, only the LeCun-Bengio-Hinton review is uncontroversially AI, in my judgment.

**And the anchors are the motivation, not the content.** In 2023 subfield 1702 taken whole holds **300,319 works**, and **187,603** after the 26 exclusions; the extended definition holds **346,525**. (Other counting rules give other sizes; see [S1, section 4.2](../supplements/S1-data-and-classification.md).) The works the extension adds are 150,559 from computer vision (subfield 1707) and 8,363 from a neuromorphic-hardware topic that sits in Electrical and Electronic Engineering rather than in computer science at all. Together they are 45.9% of the extended corpus in 2023 and 42.6% over 1995 to 2023, and almost none of it is the named anchors. Eighteen papers cannot stand proxy for nearly half a corpus.

**The strict counterfactual is a partial check.** I re-ran the entire pipeline under the narrow 35-topic AI core that I curated by hand, described in section 4. Some results survive that substitution and some do not, as the table shows. The gold rise since 2006 and the teal upturn around 2020 remain. The teal decline from 2006 to 2019 does not, and the **level ordering does not** either.

| Claim | Extended definition | Strict 35-topic core |
|-|-|-|
| AI's chance-corrected pull toward neuroscience exceeds the reverse throughout | holds in every year from 1993 (every year of the plotted series, 1995 to 2025) | fails; reversed in 31 of 36 years |
| That pull declined significantly, 2006 to 2019 | −0.00074/yr, significant at 99% | +0.00011/yr, p = 0.29, not significant |
| Neuroscience's pull toward AI rose steadily from 2006 | +0.00065/yr over 2006 to 2023, significant at 99% | +0.00028/yr over 2006 to 2023, p < 0.0001 |
| The late-series jump is the steepest in the record | +0.00493/yr over 2020 to 2023; bootstrap interval excludes zero, t-test p = 0.056 | +0.00163/yr over 2020 to 2023, p = 0.011 |

On the same segments as Figure 1 I fitted the slopes, and I recomputed them from [`results/flow/sensitivity_strict_or_by_year.csv`](../../results/flow/sensitivity_strict_or_by_year.csv); the dependence of the level ordering on the AI definition is stated in [S2, section 5](../supplements/S2-citation-flow.md).

Under the strict definition, the gold series sits *above* teal in 31 of 36 years (1990 to 2025), with teal edging ahead only in 2002 and 2008 by margins inside the year-to-year noise, and then moving decisively ahead from 2023 (2023, 2024 and 2025), which is inside the region I do not trust for other reasons. Over the 31 years from 1995 to 2025 that Figure 1 shows, teal is above gold in 5 and gold in the other 26, against all 31 for teal under the extended definition.

So the headline asymmetry is **definition-dependent**. It holds under the extended definition used for Figure 1, and it does not hold under a narrower definition that classifies the LeCun-Bengio-Hinton review and the neuromorphic-hardware literature as something other than AI. The extended definition is a choice: I fixed it before I looked at the odds ratios and applied it uniformly. A reader who prefers strict subfield 1702 or the 35-topic core will find the gold rise and the teal upturn intact, the teal decline from 2006 to 2019 not significant, and the level ordering reversed for most years. That is stated in [S2, section 5](../supplements/S2-citation-flow.md) too, and it is listed as a live limitation in [decisions and limitations](06-decisions-and-limitations.md).

## 4. The strict counterfactual: the 35-topic AI core in full

The strict scheme is the "before" classifier: neuroscience is field 28, AI is exactly these 35 topics from subfield 1702, and there is no 1707 branch, no T10502 and no exclusion list. Implementation: `build_strict_field_assignment` in `src/neuroai_cn/audits/strict_classifier.py`, reading `AI_CORE_TOPIC_IDS` from `src/neuroai_cn/utils/duckdb.py`. The same 35 IDs are recorded in the corpus manifest `q1_metadata.json` (under `ai_core_topic_ids`) in the heavy derived-data tree (`$NEUROAI_DATA/data/derived/`, see `src/neuroai_cn/config.py`) and in the `label_strict_core35` column of [`results/corpus/classification_topics.csv`](../../results/corpus/classification_topics.csv); names below were resolved against the OpenAlex API and all 35 sit in subfield 1702, field Computer Science.

| ID | Display name |
|-|-|
| T10028 | Topic Modeling |
| T10100 | Metaheuristic Optimization Algorithms Research |
| T10181 | Natural Language Processing Techniques |
| T10201 | Speech Recognition and Synthesis |
| T10215 | Semantic Web and Ontologies |
| T10320 | Neural Networks and Applications |
| T10456 | Multi-Agent Systems and Negotiation |
| T10462 | Reinforcement Learning in Robotics |
| T10637 | Advanced Clustering Algorithms Research |
| T10664 | Sentiment Analysis and Opinion Mining |
| T10820 | Fuzzy Logic and Control Systems |
| T10906 | AI-based Problem Solving and Planning |
| T11010 | Logic, Reasoning, and Knowledge |
| T11273 | Advanced Graph Neural Networks |
| T11303 | Bayesian Modeling and Causal Inference |
| T11512 | Anomaly Detection Techniques and Applications |
| T11550 | Text and Document Classification Technologies |
| T11574 | Artificial Intelligence in Games |
| T11612 | Stochastic Gradient Optimization Techniques |
| T11652 | Imbalanced Data Classification Techniques |
| T11689 | Adversarial Robustness in Machine Learning |
| T11901 | Bayesian Methods and Mixture Models |
| T11975 | Evolutionary Algorithms and Applications |
| T12026 | Explainable Artificial Intelligence (XAI) |
| T12031 | Speech and dialogue systems |
| T12072 | Machine Learning and Algorithms |
| T12535 | Machine Learning and Data Classification |
| T12611 | Neural Networks and Reservoir Computing |
| T12676 | Machine Learning and ELM |
| T12761 | Data Stream Mining Techniques |
| T12805 | Cognitive Science and Mapping |
| T12814 | Gaussian Processes and Bayesian Inference |
| T13062 | Cognitive Computing and Networks |
| T13083 | Advanced Text Analysis Techniques |
| T13904 | Artificial Intelligence Applications |

Subfield 1702 contains 77 topics in total; this core keeps the methods-and-foundations half: neural networks, reinforcement learning, natural language processing, search and planning, Bayesian methods, evolutionary and fuzzy methods, clustering, anomaly detection, cognitive computing and symbolic knowledge representation. It drops the applied-domain buckets ("AI applied to medicine, education, geology, services, law") and the orthogonal computer-science mis-clusters.

Two reasons why I curated it at all. First, the population baseline that the odds ratio divides by is inflated by domain-AI papers a neuroscientist would never cite, which drags the cross-citation odds ratio below 1 for reasons that have nothing to do with behavior. Second, the topic classifier is unstable across snapshot dates, which the T12157 event demonstrates: its 2025 works (2,818,121 against 50,854 in 2024) would be 85.1% of subfield 1702 in 2025, or 82.8% of the extended AI side, and would raise AI's share of the two fields' combined literature, which is the null against which neuroscience citing AI is measured, from 0.671 to 0.922 ([S1, section 3.5](../supplements/S1-data-and-classification.md)).

## 5. Three-scheme triangulation

Decision E1 requires that field membership be established three independent ways, and I report each separately alongside their agreement. Corpus-wide triangulation is infeasible: Semantic Scholar lookups for 398 million works would need 398 million API calls, so I computed schemes 2 and 3 over a 70-paper anchor set (68 distinct papers) drawn from the validation tiers. The labels of every anchor under the topic scheme, the venue lists and Semantic Scholar are committed in [`results/corpus/anchor_labels.csv`](../../results/corpus/anchor_labels.csv).

**Scheme 1, OpenAlex topics.** The extended classifier described above. This is the primary scheme, and every number I report uses it.

**Scheme 2, venue whitelist.** A work is labeled by its `primary_location.source.display_name` against the four Pool 3 sub-lists: `venue_neuro`, `venue_ai`, `venue_intersection` for the mixed list, `venue_general_high` for the multidisciplinary venues whose field is then resolved by schemes 1 and 3, `venue_other` for anything not listed, and `venue_unknown` where there is no primary location. Matching is exact, not substring. Implementation: `src/neuroai_cn/audits/scheme2_venues.py`; the lists are enumerated in [corpus and pools](01-corpus-and-pools.md), section 5.3.

**Scheme 3, Semantic Scholar fields of study.** Papers are looked up by DOI through the Semantic Scholar batch endpoint and labeled from `fieldsOfStudy` and `s2FieldsOfStudy`: `s2_neuro` where the fields include Neuroscience, Biology, Medicine or Psychology with neuroscience content, `s2_ai` where they include Computer Science, Mathematics or Engineering with machine-learning content, `s2_intersection` where both, `s2_other` where neither, and `s2_not_found` where Semantic Scholar has no record. Implementation: `src/neuroai_cn/audits/scheme3_s2fos.py`.

**Agreement.** I quote no agreement rate between schemes 1 and 3: Semantic Scholar has no record for many anchors and labels most of the rest as belonging to both fields ([S1, section 4.4](../supplements/S1-data-and-classification.md)). Under the topic scheme itself, 64 of the 70 anchor rows are found in the snapshot; of the 15 papers I expected to be neuroscience, 10 are labeled neuroscience, none AI, 2 other and 3 are missing (pre-1990 classics outside the index window). Among the 40 bridge papers, 21 are labeled neuroscience, 15 AI and 4 other. The full per-anchor table is written by `src/neuroai_cn/audits/triangulation.py` to `triangulation_REPORT.md` in the audits tree of the heavy derived data. The conclusion I draw is narrow: the topic labels are right for most anchors and wrong at the boundary, which is where NeuroAI papers are. It says nothing about whether the extended-versus-strict boundary choice is right, and section 3 above is where that choice is adjudicated.

## 6. Known classification failures

Two neuroscience anchors leak out of field 28 because OpenAlex itself mis-clusters them: Bargmann's *C. elegans* work lands in subfield 1302 (Aging) and Buzsáki and Draguhn 2004 lands in subfield 1312 (Molecular Biology). Including either subfield whole would add millions of unrelated works (subfield 1312 alone holds about 8.6 million), so I recorded both anchors as known misses rather than patching around them.

Medical-imaging bridge papers in subfields 2741 and 2730 (Esteva, Gulshan, Smith's FSL) remain labeled `other` under the extended scheme, because I did not add the medical-imaging subfields. This under-counts the applied-machine-learning-for-brain track, a limited but real gap.

AlphaFold lands in subfield 1312 and stays `other`. That is correct here: it is not a NeuroAI paper.

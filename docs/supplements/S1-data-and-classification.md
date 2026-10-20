---
title: "S1. Data, corpus and field classification"
date: 2026-10-20
author: Renato Duarte
repo: https://github.com/rcfduarte/neuroai-citation-network
---

# S1. Data, corpus and field classification

This supplement says where the numbers in the article come from and how I decide whether a paper counts as neuroscience, as AI, or as neither. The short answer to the second question, which a reviewer asked in the form "how do you decide whether a paper is an AI paper using neuro or a neuro paper using AI?", is that I do not look at what a paper cites at all: each paper gets exactly one label, taken from the single primary topic that OpenAlex assigns to it, and its references are then counted by the label of the paper they point to. I worked from one frozen OpenAlex snapshot of March 2026; the field sizes it gives, year by year, are in a new committed table, and two features of that table matter for reading Figure 1: a sudden near-doubling of AI in 2002 that comes from how some records are dated, and a geology topic that would have swamped AI in 2025 had I not excluded it.

## 1. What the article says

Paragraph 4 of the article:

> I analyzed roughly 458 million works from OpenAlex, an open database of publications, and the 2.9 billion links among them, tracing patterns in how the two fields cite each other over time.

The caption of Figure 1 says what the field sizes are for:

> The vertical axis is an odds-ratio against what the field sizes would predict.

Paragraph 11 promises "the locked corpus" in the supplements. In this document I keep that promise for the data and the field definitions; the bridge scoring itself is in [S5](S5-bridge-builders.md).

## 2. Data

### 2.1 The snapshot

Every number in the citation-flow and bridge analyses comes from one copy of OpenAlex, downloaded on 30 March 2026 as 381 daily update files and converted to a local DuckDB database (an embedded analytical database that can be queried with SQL). OpenAlex is an open index of scholarly works, authors, venues and institutions. I hold a frozen copy so that every number can be regenerated; the live database keeps changing, sometimes a lot (section 5).

| Quantity | Value |
|-|-:|
| Work records in the 381 daily files, all publication years | 458,112,708 |
| Works in the DuckDB index, publication years 1990 to 2026 | 398,288,606 |
| of which published 1990 to 2025 | 386,753,369 |
| Works with an OpenAlex primary topic | 311,299,063 |
| Works with a non-empty reference list | 111,676,520 |
| Citation links (one per entry of a reference list) | 2,893,128,636 |
| OpenAlex topics | 4,516 |

All values are in [`results/corpus/corpus_totals.csv`](../../results/corpus/corpus_totals.csv). The article's "roughly 458 million works" is the first row, the size of the snapshot download: every work record in it, of any year. My analyses use the second row, the works of the analysis window from 1990 to 2026. I built the index only for works published from 1990 onward, so the difference of about 60 million is older and undated material that is never analyzed. The "2.9 billion links" is the citation-link count, 2,893,128,636 to be exact, and it counts every reference of every indexed work, including references to works outside the index. Four further records were added by hand for anchor papers missing from the download; they are not part of the 458 million.

### 2.2 How much of the literature can cite

A paper can only appear as a citing paper if OpenAlex holds its reference list. Across the index that is true for 28.0 percent of works, so roughly seven works in ten are invisible as citers, although every one of them can still be cited. Between fields the share differs a lot, and it changes over time:

| Year | All works | Neuroscience | AI (extended definition) |
|-|-:|-:|-:|
| 1995 | 24.7 | 52.7 | 33.0 |
| 2001 | 25.4 | 57.2 | 34.1 |
| 2002 | 29.3 | 58.2 | 58.9 |
| 2010 | 25.7 | 49.8 | 45.5 |
| 2019 | 24.9 | 51.9 | 50.4 |
| 2023 | 24.6 | 55.9 | 46.0 |

*Percent of each year's works whose reference list is present in the snapshot. Data: [`results/flow/field_sizes_by_year.csv`](../../results/flow/field_sizes_by_year.csv), column `n_with_references` divided by `n_works`.*

In my data about half of neuroscience papers carry references throughout. AI starts near a third and approaches neuroscience only after 2002 (section 4.3 explains that year). What this means for the article: before 2002, the AI line of Figure 1 rests on a third of the AI literature, and on a different third than later, so early AI cross-citation rates describe the part of AI whose metadata happened to include references (mostly journal articles). The odds ratio uses shares rather than counts, which protects it against coverage that is low but even. It does not protect it against coverage that differs between kinds of AI paper, and I cannot measure that from inside the data.

A second gap is on the other side of the link: references that point to works not in the index. [S2](S2-citation-flow.md) (section 5) gives those shares; in 2019 they were 10.2 percent of neuroscience references and 18.3 percent of AI references. The same applies to references to works dated 2026: the index holds them, but the yearly cross-field and own-field counts of S2 and S3 treat a cited work as present only if it was published in 2025 or earlier, so a reference to a 2026 work is counted as missing (S2, section 2). Including them would change those counts by under 0.05 percent.

### 2.3 Works without a topic

When a paper has no primary topic I cannot call it neuroscience or AI; I label it unknown and leave it out of both the numerators and the field sizes. Of all works, the share that carry a topic was 92.1 percent in 2010, 80.8 percent in 2019, and then fell to 65.9 percent in 2023 and 53.6 percent in 2024. In consequence I read the last years as describing a shrinking, and possibly unrepresentative, part of the literature, which is one more reason the article treats 2024 and 2025 as provisional.

## 3. Method: how a paper gets its label

### 3.1 One paper, one topic, one label

OpenAlex places every work it can classify into a four-level hierarchy: one of about 4,500 topics, which sits in a subfield, which sits in a field, which sits in a domain. Each work receives several scored topics; the highest-scoring one is its primary topic. OpenAlex assigns topics with a trained classifier that reads a work's title, abstract, venue and citations. I use the primary topic only and ignore the others.

From that single topic I give each paper exactly one of four labels:

| Label | Rule (on the paper's primary topic) | OpenAlex topics | Works, 1990-2025 |
|-|-|-:|-:|
| Neuroscience | field 28, Neuroscience, all eight subfields | 62 | 3,552,562 |
| AI (extended) | subfield 1702 Artificial Intelligence minus 26 listed topics; plus all of subfield 1707 Computer Vision and Pattern Recognition; plus topic T10502 Advanced Memory and Neural Computing (subfield 2208, Electrical and Electronic Engineering) | 51 + 35 + 1 = 87 | 5,480,569 |
| Other (third field) | any other primary topic | the rest | |
| Unknown | no primary topic | none | |

Field 28 has eight subfields: Behavioral Neuroscience, Biological Psychiatry, Cellular and Molecular Neuroscience, Cognitive Neuroscience, Developmental Neuroscience, Endocrine and Autonomic Systems, Neurology and Sensory Systems. By construction the two sides cannot overlap: no topic is in both lists, so no paper is counted on both sides. Every topic involved, with its label and its number of works, is listed in [`results/corpus/classification_topics.csv`](../../results/corpus/classification_topics.csv), written by `python -m neuroai_cn.analysis.export_field_sizes`; the code is `build_extended_field_assignment` in `src/neuroai_cn/audits/extended_classifier.py`.

### 3.2 The reviewer's question: an AI paper using neuroscience, or a neuroscience paper using AI?

The label belongs to the paper, never to the citation. A paper is an AI paper if its own primary topic is on the AI list and a neuroscience paper if its topic is in field 28; what it cites plays no part in my rule. Its references are then sorted by the label of each cited paper. So a deep-learning paper that cites a study of visual cortex adds one AI-to-neuroscience reference to the teal line of Figure 1 (AI papers citing neuroscience, which the article labels Neuro -> AI), and an electrophysiology paper that cites a machine-learning package adds one reference to the gold line (neuroscience papers citing AI, labeled AI -> Neuro). There is no "mixed" category. A NeuroAI paper is whatever OpenAlex's classifier decided its main topic is, and it then contributes, through its references, to one of the two lines.

How that plays out for papers a reader might know (all from [`results/corpus/anchor_labels.csv`](../../results/corpus/anchor_labels.csv), a hand-picked audit set):

| Paper | Its primary topic in OpenAlex | Subfield | Label here |
|-|-|-|-|
| Hassabis et al. 2017, Neuron | EEG and Brain-Computer Interfaces | 2805 Cognitive Neuroscience | neuroscience |
| Richards et al. 2019, Nat. Neurosci. | Neural dynamics and brain function | 2805 | neuroscience |
| Yamins et al. 2014, PNAS | Neural dynamics and brain function | 2805 | neuroscience |
| Zador et al. 2023, Nat. Commun. | Reinforcement Learning in Robotics | 1702 | AI |
| Bellec et al. 2020 (e-prop), Nat. Commun. | Advanced Memory and Neural Computing | 2208 (T10502) | AI |
| LeCun, Bengio and Hinton 2015, Nature | Generative Adversarial Networks and Image Synthesis | 1707 | AI |
| Mnih et al. 2015 (DQN), Nature | Neural dynamics and brain function | 2805 | neuroscience |
| Cox 1996 (AFNI) | Medical Image Segmentation Techniques | 1707 | AI |
| Smith et al. 2004 (FSL) | Advanced MRI Techniques and Applications | 2741 Radiology | other |
| Jumper et al. 2021 (AlphaFold) | Protein Structure and Dynamics | 1312 Molecular Biology | other |

Most of these are labeled as I would expect. Two are not. The DQN paper, a reinforcement-learning paper by any reading, lands in a neuroscience topic, and the AFNI fMRI software lands in AI because medical image segmentation is filed under computer vision. These are the errors a topic classifier makes on boundary papers, and NeuroAI papers are boundary papers almost by definition. [S4](S4-what-ai-cites.md) measures how much such mislabels weigh in the aggregate.

What I deliberately do not count on either side:

- References to third fields. Most of every reference list points at statistics, physics, medicine, psychology and so on. Those references enter neither line of Figure 1; they only enter the unrestricted variant in [S2](S2-citation-flow.md) (section 4.6).
- Psychology. OpenAlex keeps psychology in its own field (32). Its subfield Experimental and Cognitive Psychology holds 1,144,610 works over 1990 to 2025 and Neuropsychology and Physiological Psychology 103,407; neither is neuroscience here. A cognitive-psychology paper cited by AI is a third-field reference.
- Medical imaging and molecular biology. Radiology (2741), where FSL sits, and Molecular Biology (1312) stay in the third field, even though some brain-imaging methods and a few neuroscience classics land there.
- Hardware. Subfield 1708 Hardware and Architecture (396,086 works) is not AI; only the neuromorphic topic T10502 is taken from engineering.
- The 26 excluded topics of subfield 1702 (section 3.4).
- Secondary topics, venues and author affiliations. A Nature Neuroscience paper whose primary topic is in computer vision is an AI paper.

One subtlety. OpenAlex's classifier reads a paper's citations among other things, so a neuroscience paper that cites mostly machine learning can be nudged toward an AI topic. My rule does not use references, but the label it starts from may have. I know of no way to remove that from inside OpenAlex.

### 3.3 Why the AI side is extended

To most readers the obvious definition of AI is OpenAlex subfield 1702, Artificial Intelligence. I did not use it on its own, for a reason I can show in the audit set. Of the 15 papers in it that are plainly AI (AlexNet, ResNet, VGG, the GAN paper, Adam, CLIP, AlphaGo and others), subfield 1702 labels only 4 as AI; six of the others, AlexNet, ResNet and the GAN paper among them, sit in computer vision. The extended definition labels 10 of the 15 as AI; three are missing from the snapshot, DQN lands in neuroscience and AlphaFold in molecular biology. Whole subfield 1702 also leaves every neuromorphic-hardware paper in the set outside AI (TrueNorth, Loihi, SpiNNaker, e-prop and others sit in T10502).

I had defended the extension with a list of eighteen canonical anchors; I can no longer reconstruct that list, and several of the examples I named (Hassabis 2017, Loihi, SpiNNaker, e-prop) are boundary objects whose field is close to the question being asked, so they cannot fix the boundary without circularity. I think the audit set above is a better argument because most of its AI papers are uncontroversially AI.

By volume, the extension is not a detail. In 2023 the extended AI side holds 346,525 works: 187,603 from subfield 1702 after the exclusions, 150,559 from computer vision and 8,363 from the neuromorphic topic. Computer vision and T10502 together make up 45.9 percent of extended AI in 2023 and 42.6 percent over 1995 to 2023. Along with them, the extension keeps some broad buckets inside subfield 1702 that few would call AI research, such as "Data Analysis with R" and "Computational Physics and Python Applications", which is how a statistics package like lme4 comes to count as AI in [S4](S4-what-ai-cites.md) and [S5](S5-bridge-builders.md).

Since my definition is a choice, I carried a narrower one through the whole pipeline as a check: a curated core of 35 topics from subfield 1702 (neural networks, reinforcement learning, language processing, Bayesian methods, planning, and so on; the list is `AI_CORE_TOPIC_IDS` in `src/neuroai_cn/utils/duckdb.py` and the `label_strict_core35` column of the topic table). It is much smaller: 124,748 works in 2023. Under it the rise of the gold line since 2006 and the upturn of the teal line around 2020 remain, the teal slope from 2006 to 2019 is +0.00011 per year (p = 0.29, not significant), and teal lies above gold in 5 of the 31 years from 1995 to 2025, against all 31 under the extended definition ([S2](S2-citation-flow.md), section 5).

### 3.4 The 26 excluded topics

Subfield 1702 is not all AI, as I found when I read its topic list. OpenAlex files there some topics from other sciences that use machine learning, and some computer science that has nothing to do with it. I removed 26 topics, fixed in code as `BAD_1702_TOPIC_IDS`, in three groups. I give counts of works published 1995 to 2023, from [`results/flow/ai_topic_sizes_by_year.csv`](../../results/flow/ai_topic_sizes_by_year.csv); names are OpenAlex's own (the misspelling of T13559 is theirs).

| Group | Topic | Works 1995-2023 |
|-|-|-:|
| OpenAlex artifact | T12157 Geochemistry and Geologic Mapping | 591,088 |
| Other science | T13018 Seismology and Earthquake Studies | 37,479 |
| Other science | T11276 Solar Radiation and Photovoltaics | 37,432 |
| Education | T14335 Educational Robotics and Engineering | 179,489 |
| Education | T13559 Edcuational Technology Systems | 68,489 |
| Education | T12260 Educational Technology and Pedagogy | 35,764 |
| Education | T11902 Intelligent Tutoring Systems and Adaptive Learning | 35,559 |
| Education | T13567 AI and Multimedia in Education | 3,171 |
| Quantum | T10020 Quantum Information and Cryptography | 111,324 |
| Quantum | T10682 Quantum Computing Algorithms and Architecture | 75,462 |
| Security | T10237 Cryptography and Data Security | 67,678 |
| Security | T10764 Privacy-Preserving Technologies in Data | 51,754 |
| Security | T11130 Coding theory and cryptography | 51,001 |
| Security | T10951 Cryptographic Implementations and Security | 35,917 |
| Security | T11424 Security and Verification in Computing | 30,528 |
| Security | T11598 Internet Traffic Analysis and Secure E-voting | 31,285 |
| Signals | T10711 Target Tracking and Data Fusion in Sensor Networks | 46,109 |
| Signals | T12131 Wireless Signal Modulation Classification | 12,128 |
| Software | T10126 Logic, programming, and type systems | 74,279 |
| Software | T10639 Advanced Software Engineering Methodologies | 52,414 |
| Algorithms | T11269 Algorithms and Data Compression | 53,272 |
| Algorithms | T13935 Mathematical Control Systems and Analysis | 9,410 |
| Algorithms | T14175 Intuitionistic Fuzzy Systems Applications | 6,695 |
| Business, law | T14064 Organizational and Employee Performance | 28,535 |
| Business, law | T12128 AI in Service Interactions | 21,943 |
| Business, law | T13851 Law, AI, and Intellectual Property | 21,732 |

Together the 26 topics hold 41.8 percent of all subfield 1702 works published 1995 to 2023, so subfield 1702 taken whole is a poor stand-in for AI. Does my list drive the result? A leave-one-topic-out sweep re-admitted each candidate topic into AI, one at a time, and recomputed every odds ratio. I found that only T12157 matters much, and no single re-admitted topic reverses the order of the two lines in any year; [S2](S2-citation-flow.md), section 4.7, has the numbers.

### 3.5 The T12157 artifact

T12157, "Geochemistry and Geologic Mapping", is filed under artificial intelligence because its papers use machine learning for mineral-prospectivity mapping and remote sensing. In the snapshot it holds 50,854 works published in 2024 and 2,818,121 published in 2025, a 55-fold jump in one year. Left inside subfield 1702, it would be 85.1 percent of that subfield's 3,310,775 works in 2025. Added to the extended definition, it would make up 82.8 percent of AI in 2025 and raise the share of AI in the two fields' combined 2025 literature, which is the expected share against which neuroscience papers citing AI are measured, from 0.671 to 0.922. The odds ratio would then move with no change in what anybody cites. In my working notes I attributed the jump to OpenAlex's November 2025 re-export of its data, four months before the snapshot; I have not re-verified that date from the data, only the jump itself. Even before 2025 the topic was erratic (46,229 works in 2015, 70,878 in 2016, 33,102 in 2017), which is why re-admitting it moves the odds ratio by about a third in 2016 too.

### 3.6 The four pools, and why the odds ratio does not use them

Before the analysis I built a curated NeuroAI corpus of four overlapping pools: (1) works by authors of five NeuroAI anchor publications, or affiliated with one of 21 NeuroAI-related institutes between 2019 and 2026; (2) works whose titles match five keyword templates; (3) works in a list of neuroscience, AI, mixed and general venues; (4) the works of six curated rosters of seed authors. A work enters if any pool admits it. Together the pools hold 2,153,057 distinct works, and Appendix A lists their contents. Pool 1 is almost entirely its institutional half: 1,500,926 of its 1,508,502 works come in only through the institutes, so it is closer to the collected output of those institutes than to self-declared NeuroAI.

I do not run the odds ratio of Figure 1 on the pools, and it could not be run there. Its expected share is each field's share of all papers published that year; the pools are chosen for NeuroAI-ness (people, keywords, venues), so inside them both the cross-field citation rate and the relative size of the fields are inflated by construction. Measuring how often neuroscience and AI cite each other inside a sample selected for the two citing each other would answer a question already decided by the selection. Figure 1 and the field sizes below therefore use every classified paper in the snapshot. Tracing the code, I also found that the bridge ranking of Figure 3 counts citations over the whole snapshot rather than over the pools ([S5](S5-bridge-builders.md)); no published number reads the pool files. They remain the corpus as designed, and a record of the editorial choices made before the data were seen.

## 4. Results

### 4.1 Field sizes per year

![Works per year by field definition, and the share with reference lists](../../figures/figure_s1_field_sizes.png)

*Figure S1.1 (`figure_s1_field_sizes`). A: works per publication year, 1990 to 2025, log scale: neuroscience (field 28, gold), AI under the extended definition used in the article (teal, solid), whole subfield 1702 (teal, dashed) and the curated 35-topic core (teal, dotted). B: percent of those works whose reference list is in the snapshot. The colors follow the citing field of Figure 1: gold for neuroscience papers, teal for AI papers. Dotted vertical line: 2002 (section 4.3). Hatched band: 2024 to 2025, provisional; the dashed line's spike in 2025 is T12157 (section 3.5). Data: `results/flow/field_sizes_by_year.csv`; regenerated by `python -m neuroai_cn.figures.figure_s1_field_sizes`.*

| Year | Neuroscience | AI, extended | AI, whole 1702 | AI, 35-topic core |
|-|-:|-:|-:|-:|
| 1995 | 42,049 | 35,135 | 38,658 | 17,004 |
| 2001 | 54,052 | 55,150 | 61,139 | 23,077 |
| 2002 | 60,118 | 100,726 | 91,808 | 42,133 |
| 2010 | 105,394 | 152,803 | 146,216 | 55,731 |
| 2019 | 149,538 | 245,916 | 226,234 | 95,120 |
| 2023 | 164,016 | 346,525 | 300,319 | 124,748 |
| 2024 (provisional) | 205,145 | 453,546 | 452,522 | 162,574 |
| 2025 (provisional) | 287,415 | 586,892 | 3,310,775 | 227,253 |

These are the field sizes my odds ratio uses: the neuroscience and extended-AI columns equal `n_works_source` and `n_works_target` in `results/flow/or_by_year.csv` for every year, and the core column equals the same columns of the strict sensitivity table. Each counts all works of that publication year whose primary topic falls in the definition, of every work type, with or without a reference list.

Between 1995 and 2023 neuroscience grew 3.9-fold and extended AI 9.9-fold. AI was 0.84 times the size of neuroscience in 1995, overtook it in 2001 and stayed ahead in every later year, and was 2.11 times its size in 2023. This is why the article corrects for field size: a fixed habit of citing AI would produce a rising number of citations simply because there is more AI to cite.

### 4.2 Field sizes under other counting rules

In 2023 the snapshot gives 300,319 for subfield 1702 taken whole, 187,603 for subfield 1702 after the exclusions, 124,748 for the 35-topic core and 346,525 for the extended definition. Other counting rules give other sizes: with reference lists the extended side holds 159,354 works in 2023, and as articles and reviews 183,591. The October 2026 re-check of the live OpenAlex database ([`results/flow/fresh_recheck_field_sizes_20261006.csv`](../../results/flow/fresh_recheck_field_sizes_20261006.csv)), which gives 314,391 for subfields 1702 and 1707 together and 196,514 for subfield 1702 in 2023, because the live database differs from the frozen snapshot. Every computation used the snapshot values above.

### 4.3 The 2002 jump in AI

The companion table of Figure 2 shows AI going from 55,150 works in 2001 to 100,726 in 2002 and back to 88,275 in 2003. Neuroscience shows nothing of the kind. I wanted to know whether this was a real change in the literature, an OpenAlex ingestion effect, or something in my classifier. A breakdown of the AI works of 2000 to 2004 by venue, DOI registrant and record type answers most of that question ([`results/flow/ai_works_2000_2004_breakdown.csv`](../../results/flow/ai_works_2000_2004_breakdown.csv) and [`results/flow/subfield_sizes_2000_2004.csv`](../../results/flow/subfield_sizes_2000_2004.csv)).

Most of the extra works are IEEE records. AI works with an IEEE DOI (prefix 10.1109) go from 1,635 in 2001 to 40,701 in 2002, against a total increase of 45,576. Most of them have no venue recorded: works without a venue go from 15,797 to 54,146. They are journal-style "article" records with reference lists, which is why the share of AI works with references jumps in 2002 (Figure S1.1, B). Among those that do have a venue are proceedings of conferences held years earlier, now dated 2002: the IEEE International Conference on Neural Networks of 1996 and 1997, the 1993 IEEE International Symposium on Circuits and Systems, a 1990 IEEE conference on tools for AI.

Nor is the jump specific to AI. In OpenAlex as a whole, works in computer science grow by a factor of 1.755 from 2001 to 2002 and in engineering by 1.243, against 1.112 in neuroscience, which is in line with ordinary growth. Inside computer science the largest jumps are in Hardware and Architecture, Signal Processing and Computer Vision, all subfields where IEEE conference papers dominate.

My classifier is not the cause either: the same step appears in the October 2026 re-check, which uses plain subfields and a fresher copy of the database (52,230 AI works in 2001 against 101,606 in 2002). And it is not a real change in the literature, since conferences from the 1990s do not hold sessions in 2002. My reading is that a large batch of IEEE conference records, many of them older, carries 2002 as its publication year in the metadata OpenAlex received. I could not check individual records against IEEE, so I cannot say how many of the roughly 39,000 extra IEEE works were actually published in 2002.

What it does to Figure 1. In 2002 AI's share of the two fields' papers, the expected share for neuroscience papers citing AI, jumps from 0.505 to 0.626, while the observed share of neuroscience references going to AI rises a little, from 1.63 to 1.83 percent. The gold odds ratio therefore drops from 0.0163 to 0.0111 in a single year, almost entirely through its denominator. That step coincides with the gold turning point the piecewise search places at 2002 ([S2](S2-citation-flow.md), section 4.3). The teal line barely moves (0.0428 to 0.0441), because the extra AI papers add references to AI and to neuroscience alike. I have not re-dated these records, which the data do not support. The text of the article does not interpret the 2002 break ([S2](S2-citation-flow.md), section 5).

### 4.4 The anchor audit as a check on all three schemes

In May 2026 I checked the 70 papers of the audit set (68 distinct; two appear twice) under three independent schemes: OpenAlex topics, a venue list, and Semantic Scholar's fields of study. Results are in `results/corpus/anchor_labels.csv`. Under the topic scheme I found 64 of the 70 rows in the snapshot. Among the 15 papers I expected to be neuroscience, it labels 10 as neuroscience, none as AI, 2 as other and misses 3 (pre-1990 classics outside the index window, such as Hubel and Wiesel 1962). Among the 40 bridge papers it labels 21 neuroscience, 15 AI and 4 other. I quote no agreement rate between the topic scheme and Semantic Scholar, because Semantic Scholar has no record for many anchors and labels most of the rest as belonging to both fields.

## 5. Caveats and what this does not show

One topic per paper is coarse, and I accept that. A paper on deep networks as models of visual cortex has one primary topic; whichever side it lands on, its other half is invisible. I chose this design because it keeps the two sides disjoint and makes the odds ratio well defined, at the price of flattening exactly the papers the article is about.

Topic labels carry single-paper errors, and those errors concentrate at the boundary (DQN as neuroscience, AFNI as AI, two neuroscience classics in other fields). A classifier error on one heavily cited paper can move a top-15 ranking, while barely moving an aggregate over millions of references; [S4](S4-what-ai-cites.md) tests the aggregate.

The level ordering of the two lines in Figure 1 and the teal slope before 2020 depend on how widely AI is defined. Under the extended definition, AI papers cite neuroscience more than chance relative to the reverse in every year; under the 35-topic core teal is above gold in 5 of the 31 years, and the teal slope from 2006 to 2019 is not significant ([S2](S2-citation-flow.md), section 5). I chose the extended definition before computing any odds ratio, on the grounds in section 3.3; it is a choice, not a measurement.

Reference coverage is uneven. Only 28.0 percent of works can cite, AI coverage changes in 2002, and coverage varies by publisher and decade in ways I cannot bound from inside the data.

Records are sometimes misdated or reclassified in bulk. The 2002 IEEE batch and the 2025 geology topic are the two I found by looking at field sizes. Works dated 2006 are also anomalous in number (10,744,114 against 6,653,425 in 2005), but almost all of the excess has no topic and so does not enter either field. Other events may be smaller and hidden.

I treat recent years as unsettled. Topic coverage falls to about half in 2024, and OpenAlex rebuilt its database during this work ([S2](S2-citation-flow.md), section 4.4).

Work published before 1990 is outside the index, so old foundational papers are never cited works here, and books without identifiers are absent at any date. My counts therefore undercount the classical canon by construction.

## 6. Reproduce

From the committed files (no heavy data needed):

```bash
# Figure S1.1
.venv/bin/python -m neuroai_cn.figures.figure_s1_field_sizes

# every number in this supplement, checked against the results files
.venv/bin/python -m pytest -q tests/test_supplement_claims.py
```

With the local OpenAlex snapshot and its DuckDB index (`NEUROAI_DATA`, see `src/neuroai_cn/config.py`):

```bash
# field sizes, topic table, the 2000-2004 breakdown, corpus totals, pools and anchors
# (two aggregate passes over the works table, about half an hour; 4 GB memory limit)
.venv/bin/python -m neuroai_cn.analysis.export_field_sizes

# rebuild the CSV files from the cached aggregates without touching the database
.venv/bin/python -m neuroai_cn.analysis.export_field_sizes --no-scan

# the pools themselves
.venv/bin/python -m neuroai_cn.corpus.build_corpus
```

The snapshot is 365 GB of parquet and cannot be redistributed; a full rebuild means downloading OpenAlex again, which will not reproduce these counts exactly because the database changes. The per-year tables committed under `results/` are the ones worth checking.

## 7. Related

- [S2. Citation flow](S2-citation-flow.md): the odds ratio of Figure 1, the strict-AI counterfactual, the leave-one-topic-out sweep and the 2024-2025 artifact.
- [S3. Counts, shares and field sizes](S3-counts-and-field-sizes.md): Figure 2 and how field size enters the comparison.
- [S4. What AI cites in neuroscience](S4-what-ai-cites.md): which neuroscience, and how much mislabeled AI sits inside field 28.
- [S5. The bridge builders](S5-bridge-builders.md): the bridge score and its eligibility filters.
- [Methods 01, corpus and pools](../methods/01-corpus-and-pools.md), [methods 02, field classification](../methods/02-field-classification.md) and [methods 06, decisions and limitations](../methods/06-decisions-and-limitations.md): formal definitions and the decision registry.

## Appendix A. The four pools

All counts are from [`results/corpus/pool_sizes.csv`](../../results/corpus/pool_sizes.csv). Pools are restricted to publication years 1990 to 2026, unioned and deduplicated by OpenAlex work identifier; there is no citation expansion.

| Pool | Admits a work if | Works |
|-|-|-:|
| 1 | an author signed one of five anchor publications (1a), or had an affiliation at one of 21 institutes in 2019-2026 (1b) | 1,508,502 |
| 2 | its title matches one of five keyword templates | 37,608 |
| 3 | it appeared in a listed venue | 661,977 |
| 4 | it is by a listed seed author | 23,208 |
| Sum before deduplication | | 2,231,295 |
| Distinct works | | 2,153,057 |

Works in only one pool: 1,435,576 (Pool 1), 598,400 (Pool 3), 34,407 (Pool 2) and 9,269 (Pool 4). The largest pairwise overlap is Pools 1 and 3, with 61,193 works in both.

**Pool 1a, anchor publications.** Zador et al. 2023, Nature Communications ([doi:10.1038/s41467-023-37180-x](https://doi.org/10.1038/s41467-023-37180-x)); its 2022 preprint ([doi:10.48550/arXiv.2210.08340](https://doi.org/10.48550/arXiv.2210.08340)); Luppi, Achterberg et al. 2024, Nature Communications ([doi:10.1038/s41467-024-53375-2](https://doi.org/10.1038/s41467-024-53375-2)); Mineault et al. 2024, NeuroAI for AI Safety ([doi:10.48550/arXiv.2411.18526](https://doi.org/10.48550/arXiv.2411.18526)); Hassabis et al. 2017, Neuron ([doi:10.1016/j.neuron.2017.06.011](https://doi.org/10.1016/j.neuron.2017.06.011)). Constant `ANCHOR_DOIS` in `src/neuroai_cn/corpus/pool1.py`.

**Pool 1b, institutes.** The editorial roster names 41 carriers of the NeuroAI label, but courses, workshops and programs have no OpenAlex identifier, and whole universities would admit everything they publish. The code queries 21 OpenAlex institution identifiers (`NEUROAI_SUB_INSTITUTE_IDS`, probed on 2026-04-29): Flatiron Institute; the National Bernstein Network and the Bernstein Centers in Berlin, Freiburg, Göttingen and Heidelberg-Mannheim; Sainsbury Wellcome Centre; Centro Champalimaud and the Champalimaud Foundation; Mila; the Max Planck Institutes for Biological Cybernetics and for Intelligent Systems; Salk Institute; Allen Institute for Brain Science; Cold Spring Harbor Laboratory; Google DeepMind (UK); Anthropic; RIKEN Center for Brain Science; Neuromatch; and two Donders entities. Kempner, Wu Tsai and ARNI could not be resolved.

**Pool 2, keyword templates.** Case-insensitive matching on titles only, because abstracts were not kept in the local copy; that costs a large but unmeasured share of recall. Template A fires on any of 22 high-precision phrases (predictive coding, free energy principle, active inference, feedback alignment, representational similarity analysis, Brain-Score, surrogate gradient, neuromorphic, successor representation, grid cell, place cell, and others). Templates B to E require one term from each of two or three groups: B, a network architecture plus a brain region plus a modeling or measurement word; C, a biological-plausibility marker plus a learning substrate; D, a language model plus a brain measurement; E, a cognitive-map term plus a reinforcement-learning or modeling term. Three title-based false-positive traps set a flag rather than removing works. The complete term lists are in `src/neuroai_cn/corpus/pool2.py` and [methods 01](../methods/01-corpus-and-pools.md), section 4.

**Pool 3, venues.** Resolved OpenAlex source identifiers in four lists: core neuroscience (17, for example Neuron, Nature Neuroscience, Journal of Neuroscience, NeuroImage), core AI (16, for example NeurIPS, ICML, ICLR, JMLR, AAAI), mixed (18, for example Neural Computation, PLoS Computational Biology, Behavioral and Brain Sciences) and general high-impact (10, for example Science, Nature, PNAS). Some intended venues did not resolve (Nature Reviews Neuroscience, TMLR, COLT, UAI, Biological Cybernetics), and CVPR, ICCV and ICRA resolve only to single years. Full lists in `src/neuroai_cn/corpus/pool3.py` and methods 01, section 5.

**Pool 4, seed authors.** Six rosters matched by exact display name with at least five works: 4a, NeuroAI-era researchers (44 names); 4b, classical bridges such as Rumelhart, McClelland, Hinton, Hopfield and Grossberg (12); 4c, biological cybernetics such as Amari, von der Malsburg and Fukushima (11); 4d, theoretical and computational neuroscience (33); 4e, critics and skeptics (18); 4f, safety and interpretability (16). Works by six surnames that collide in OpenAlex are flagged. Known errors: `Yamins Daniel` is a name-order error that matches nothing, and two 4f entries are probably wrong resolutions. Full rosters in `src/neuroai_cn/corpus/pool4.py` and methods 01, section 6.

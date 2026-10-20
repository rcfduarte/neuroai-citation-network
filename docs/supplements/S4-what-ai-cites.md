---
title: "S4. What AI cites in neuroscience: age, subfield and the NeuroAI papers"
date: 2026-10-20
author: Renato Duarte
repo: https://github.com/rcfduarte/neuroai-citation-network
---

# S4. What AI cites in neuroscience: age, subfield and the NeuroAI papers

This supplement looks inside the two citation flows of Figure 1 and asks what crosses: which parts of neuroscience AI papers cite, which kinds of AI neuroscience papers cite, how old the cited work is, whether the six NeuroAI review papers of the article's sidebar track the flow, and how far back each field's references reach. The answer in two sentences: AI's citations of neuroscience go mostly to cognitive neuroscience (90.3 percent for AI papers of 2020-2025 under the 35-topic core definition) and little to cellular and molecular work (4.98 percent); the median year of the cited neuroscience moved from 2007 to 2015 between 2010-2019 and 2020-2025, while the median age of the cited work, within a fixed window of 0 to 20 years, was 7 years in both periods. The six NeuroAI papers hold well under 1 percent of the flow and stopped growing in 2021 while the flow kept rising, and AI papers do have a shorter citation memory than neuroscience papers (median reference age 4 against 8 years).

## 1. What the article says

Four passages of the article rest on the analyses here. Paragraph 8 ends:

> This is consistent with the timing of the NeuroAI manifestos and the rising interest in understanding and grounding intelligence. Of the neuroscience that AI papers now cite, about 90 percent comes from cognitive neuroscience and under 5 percent from cellular and molecular work.

Paragraph 6 opens with "AI still draws on neuroscience concepts absorbed decades ago", and paragraph 16 says:

> Citation patterns suggest that AI continues to cite newer neuroscience papers. But these papers do not yet qualify as "bridge works"—foundational discoveries highly cited by both fields.

The sidebar lists six NeuroAI review and position papers by DOI: Hassabis et al. 2017 ([doi:10.1016/j.neuron.2017.06.011](https://doi.org/10.1016/j.neuron.2017.06.011)), Zador et al. 2023 ([doi:10.1038/s41467-023-37180-x](https://doi.org/10.1038/s41467-023-37180-x)), Richards et al. 2019 ([doi:10.1038/s41593-019-0520-2](https://doi.org/10.1038/s41593-019-0520-2)), Macpherson et al. 2021 ([doi:10.1016/j.neunet.2021.09.018](https://doi.org/10.1016/j.neunet.2021.09.018)), Sinz et al. 2019 ([doi:10.1016/j.neuron.2019.08.034](https://doi.org/10.1016/j.neuron.2019.08.034)) and Lillicrap et al. 2020 ([doi:10.1038/s41583-020-0277-3](https://doi.org/10.1038/s41583-020-0277-3)).

Two questions raised on drafts get an answer here as well. A reviewer asked whether citations of the manifestos follow the same curve as the flow (section 4.6). A commentator, in a piece published alongside the article, argues that citations understate old foundational influence because machine learning has a short citation memory and absorbed ideas stop being cited; section 4.7 measures the memory part of that argument. I leave the second half of paragraph 16, about bridge works, to [S6](S6-citation-age.md).

## 2. Data

Every number comes from the OpenAlex snapshot of March 2026 that I hold locally ([S1](S1-data-and-classification.md) describes it). Its works table starts in 1990, so a cited work published before 1990 is not in it and cannot be dated or classified. Every age statistic below loses its old tail to this truncation, and I return to it wherever it matters.

Once, on the local mirror, I ran the analyses and committed their small output tables. [`results/vintage/`](../../results/vintage/) holds the subfield, vintage, robustness and reference-age tables, including two count matrices from which every vintage table can be recomputed (`matrix_cited_vintage.csv`, one row per direction, citing year, cited year, cited subfield and a few flags, and `matrix_reference_age.csv`). [`results/manifestos/`](../../results/manifestos/) holds the six papers and their citations by year and citing field. For the composition of the neuroscience-citing-AI flow I exported three small files into [`results/flow/`](../../results/flow/): `flow_composition_topic_year.csv` (citations by cited AI topic and citing year, under two AI definitions), `flow_composition_head.csv` (the 200 AI works most cited by neuroscience) and `flow_concentration.csv`. Their yearly totals equal the cross-field counts of `or_by_year.csv` exactly, and the subfield matrix agrees with them to within 8 citations in any year.

Counts are citation edges: one edge is one citing paper citing one work. Citing years run from 1995 to 2025, with 2024 and 2025 provisional because of the OpenAlex rebuild ([S2](S2-citation-flow.md), section 4.4). Where I quote the periods 2020-2025 I also give 2020-2023 when the two differ.

## 3. Method

### 3.1 Directions, definitions and cited sets

As in [S2](S2-citation-flow.md), the directions are named so:

| Data column | Who cites whom | Article label | Color |
|-|-|-|-|
| `ai_to_neuro` | AI papers citing neuroscience | Neuro -> AI (neuroscience informs AI) | teal |
| `neuro_to_ai` | neuroscience papers citing AI | AI -> Neuro (AI informs neuroscience) | gold |

Most of this supplement is about the teal flow. A paper is neuroscience when its primary OpenAlex topic lies in the field Neuroscience. AI papers I define in one of two ways. The 35-topic core is a narrower, hand-curated list; it leaves out computer vision and much of applied machine learning. The article's sentence on cognitive neuroscience (paragraph 8) was computed for AI papers under this definition and the exclusive cited set described next, so section 4.1 uses it. Extended is the definition behind the figures of the article: the OpenAlex subfield Artificial Intelligence minus 26 topics that are not AI, plus the subfield Computer Vision and Pattern Recognition, plus one neuromorphic-hardware topic. The remaining sections use it unless they say otherwise. Every paper in the 35-topic core is also in the extended set.

On the cited side I use two sets. Unrestricted, the set is every work whose primary topic is in neuroscience; this is what Figure 1 counts. Exclusive, it further drops any work that also carries an AI topic among its listed OpenAlex topics (a work has at most three). I use it because OpenAlex files some AI papers under neuroscience: the DQN paper, "Human-level control through deep reinforcement learning", has a neuroscience primary topic. Exclusion removes such papers when their secondary topic gives them away. I declared the exclusive set the primary specification for the headline numbers before running the queries, and I report both throughout.

### 3.2 Subfields of neuroscience and categories of AI

For the teal flow I break the cited neuroscience down by the OpenAlex subfield of its primary topic. There are eight: Cognitive Neuroscience, Cellular and Molecular Neuroscience, Neurology, Sensory Systems, Behavioral Neuroscience, Developmental Neuroscience, Endocrine and Autonomic Systems, and Biological Psychiatry. "Cognitive neuroscience" in the article means the first of these, and "cellular and molecular work" the second. Each share is the fraction of citation edges going to a subfield; the share of distinct cited works is in the same file and tells the same story.

Next, for the gold flow, I group the cited AI works by topic. I assigned by hand the 87 topics that receive any citation from neuroscience under the extended definition to six categories: foundational deep learning and AI, neuroimaging and medical image processing, general statistics and machine-learning software, computer-vision applications, brain-adjacent modeling, and off-topic or misclassified. Since the assignment is a judgment, I print it in full, topic by topic, in `flow_composition_topic_year.csv`, so that anyone can dispute a single line. I computed the decomposition under both AI definitions because, as section 4.2 shows, the answer depends on it.

### 3.3 Age of the cited work

For each period of citing papers I compute the median publication year of the cited work (with ties split at the mean of the two middle values), the share of citations going to work published in 2005 or earlier, and the mean age, where age is the citing year minus the cited year. Next to the 2005 share I give the share up to 2004, because 2004 is the boundary of a cut at "before 2005". About 1 percent of edges in 2010-2019 point at work dated after the citing paper, an OpenAlex dating error; they are kept and counted.

These calendar statistics move for two reasons that have nothing to do with taste. When the citing papers move forward by ten years, so does everything they cite, even if their reading habits stay the same. And because the mirror starts in 1990, a paper of 2010 can reach back at most 20 years while a paper of 2025 can reach back 35, so the mean age drifts up with the citing year. To separate a change in habits from the passage of time, I also compute the age profile inside a common window: only citations to work aged 0 to 20 years, which every citing year from 2010 on can see in full. I added this window while writing this supplement, after seeing the calendar results, so it was not declared in advance; the code is in `src/neuroai_cn/analysis/s4_numbers.py`.

### 3.4 The robustness check, declared in advance

Exclusion cannot catch every AI paper filed under neuroscience. Before running anything I wrote down a check that could fail: remove from the cited side every work whose title matches a generous AI-method pattern (deep learning, reinforcement learning, neural network, transformer, support vector and about forty other patterns; a neuroscience paper with "neural network" in its title goes too, which makes the check harder to pass), then the clear AI papers among the 25 most-cited surviving works of each period, then the borderline ones. Every removed work is listed in `removed_works.csv`. By that rule the check fails if, in either period, the cognitive share moves by more than 2 percentage points, the median cited year by more than 1 year, or the share published in 2005 or earlier by more than 2 points.

### 3.5 The six NeuroAI papers

I resolved the six DOIs in the mirror and labeled each paper with the same classifier as everything else. For each year I counted the citations each paper received, split by the field of the citing paper (AI, neuroscience, neither). I set the citations from AI papers against the whole AI-to-neuroscience flow of that year, and I recomputed the teal odds ratio of Figure 1 with the six removed as cited works. To compare curves I correlated year-over-year changes, not levels: two series that both rise over a decade correlate highly whatever their relation. My statistic is the Spearman rank correlation (the ordinary correlation computed on ranks, which ignores the scale of the changes) between changes in log(1 + count), over the nine changes from 2014-2015 to 2022-2023, with an exact p-value from all 9! orderings. All of this was fixed before I looked at the numbers.

### 3.6 Reference age

To test the short-memory argument, I took every reference of every AI and neuroscience paper that resolves to a dated work in the mirror, not only references to the other field, and computed its age. For the primary comparison I use OpenAlex types article and review, because the argument compares conference papers with journal papers and those two types carry most of each; the all-types version is in the same files. I report the median, the 90th percentile (the age that 90 percent of references do not exceed) and the share aged five years or less, and alongside them how many papers have any reference list and how many listed references resolve to a dated work. A reference whose cited work is dated after the citing paper would have a negative age, and I drop these references before any statistic is computed. The counts in the table below hold under that rule: 12,173,300 references for AI and 14,320,543 for neuroscience, against 12,261,289 and 14,335,868 if the 87,989 and 15,325 dropped references were kept.

## 4. Results

![Composition of the two flows](../../figures/figure_s4_composition.png)

*Figure S4.1 (`figure_s4_composition`). A: AI papers citing neuroscience (teal flow), share of citations by subfield of the cited neuroscience work, per citing year 1995 to 2025, 35-topic core, exclusive cited set; neurology and cellular and molecular are drawn separately, the five small subfields together. B: share of cognitive neuroscience and of cellular and molecular neuroscience among AI papers' citations of neuroscience, citing years 2020 to 2025, under the 35-topic core and the two cited sets; dotted lines at 90 and 5 percent, the values in the article. C and D: neuroscience papers citing AI (gold flow), share by category of the cited AI topic, per citing year, extended definition (C) and 35-topic core (D). Hatched: 2024 and 2025, provisional. Data: `results/vintage/matrix_cited_vintage.csv`, `results/vintage/subfield_breakdown.csv`, `results/flow/flow_composition_topic_year.csv`.*

### 4.1 Which neuroscience AI cites: the 90 percent sentence

| AI papers 2020-2025 citing neuroscience, 35-topic core | Cognitive | Cellular and molecular | Neurology | Citations |
|-|-:|-:|-:|-:|
| Exclusive set (the article's basis) | 90.3 | 5.0 | 2.6 | 139,730 |
| Unrestricted set | 88.3 | 4.3 | 5.7 | 179,242 |

Shares are percent of citation edges, as I count them. AI papers of 2020-2025, under the 35-topic core definition, send 90.3 percent of their citations of (exclusive) neuroscience to cognitive neuroscience and 4.98 percent to cellular and molecular neuroscience. These are the article's "about 90 percent" and "under 5 percent". Under the extended definition used for Figure 1, which adds computer vision and medical imaging papers to the AI side, the same two shares for the exclusive set in 2020-2025 are 82.7 percent and 9.96 percent (`results/vintage/matrix_cited_vintage.csv`), so the two values depend on the definition of AI. Counting the unrestricted cited set instead, the shares are 88.3 and 4.3 percent, and neurology takes 5.7 percent. Restricting to 2020-2023, because the last two years are provisional, gives 91.2 and 4.41 percent for the exclusive set.

Over time the shares are stable. The cognitive share was 91.7 percent in 2010-2019 and 90.3 percent in 2020-2025, and in every citing year from 2010 to 2024 it lies between 90.1 percent (2015) and 92.5 percent (2021), as panel A shows. Some of what OpenAlex calls cognitive neuroscience is psycholinguistics and cognitive science, and some is visual perception and attention.

### 4.2 What neuroscience cites in AI

An odds ratio says how strongly neuroscience reaches into AI, not for what. Whether neuroscience imports ideas or software from AI is what my tools-versus-concepts argument in the article turns on, so I decomposed the gold flow by the topic of the cited AI work. Between 1995 and 2023 neuroscience papers cited AI works 951,900 times under the extended definition, spread over 87 topics; under the 35-topic core the same flow is 436,326 citations over 35 topics.

| Category of cited AI topic | Extended (%) | 35-topic core (%) |
|-|-:|-:|
| Foundational deep learning and AI | 41.1 | 64.5 |
| Neuroimaging and medical image processing | 15.1 | 0.0 |
| General statistics and ML software | 14.5 | 21.8 |
| Computer-vision applications | 13.9 | 0.0 |
| Brain-adjacent modeling | 10.6 | 13.7 |
| Off-topic or misclassified | 4.9 | 0.0 |

Citing years 1995 to 2023. From this table I draw three results and one non-result.

Largest under both definitions, in my grouping, is foundational deep learning and AI. Its largest topic, "Neural Networks and Applications", alone takes 14.3 percent of the extended flow.

Statistics and machine-learning methods are a large and growing part of the flow under both definitions, but what they contain differs. Under the extended definition the category takes 14.5 percent of the flow over 1995 to 2023, rising from 4.4 percent of the 1995 citations to a peak of 18.4 percent in 2021. Within the core it takes 21.8 percent, rising from 3.2 percent in 1995 to 32.1 percent in 2022 and 30.9 percent in 2023. Its software, though, belongs to the extended definition only. Its two software topics, "Data Analysis with R" (1.8 percent of the extended flow) and "Computational Physics and Python Applications", are not in the 35-topic core, so the core version of the category consists of Bayesian modeling, mixture models, classification and optimization methods. What I find under both definitions is that general-purpose statistical and machine-learning methods make up a growing share, between a seventh and a fifth of the flow overall. That software in particular does so is true only of the extended definition.

Brain-adjacent modeling has shrunk. These are the cognitive-science and visual-attention topics that OpenAlex files under AI. Extended, they took 20.0 percent of neuroscience's AI citations in 1995 and 6.2 percent in 2023; under the core, 26.2 and 6.7 percent. Less and less of the AI that neuroscience cites today resembles cognitive modeling.

My non-result concerns imaging. Under the extended definition, neuroimaging and medical image processing takes 15.1 percent and computer-vision applications another 13.9 percent. Under the 35-topic core both are exactly zero, because the core admits no computer-vision topic and the extended definition admits all of them. Here the definition decides, not the data. Neither definition is neutral: the extended one sweeps in the fMRI preprocessing stack, which few people would call artificial intelligence, and the core leaves out deep-learning vision work that plainly is AI. How much of neuroscience's AI citation is tools and how much is theory therefore cannot be settled from topic labels alone.

Reading the head of the flow shows me what the categories hide. Over citing years 1990 to 2025 the extended gold flow holds 1,188,383 citations to 217,988 distinct AI works, and half of the citations go to just 4,379 of them, 2.0 percent of the cited works. At the top sits lme4, the R package for mixed-effects models, the single most-cited AI work, with 8,094 citations from neuroscience papers. Of the 25 most-cited works, 10 are neuroimaging tools of the medical image segmentation topic (AFNI, FSL's registration and brain-extraction programs, SPM's unified segmentation, the DARTEL registration algorithm, the BRATS benchmark and others); scikit-learn is 12th and LIBSVM 13th. Among the rest of the 25 are deep-learning landmarks (ResNet at 4th, the 2015 deep-learning review, AlexNet, LSTM, Sutton and Barto's textbook in two editions), mixed with works that are not AI at all.

Those are misclassifications, and they inflate the flow. In 11th place among the most-cited "AI" works sits a 2014 paper on the false-alarm rate of fall sensors for the elderly. Miller's 1956 "magical number seven", in its 1994 reprint, is filed under "Cognitive Science and Mapping" and ranks 23rd. Latora and Marchiori's "Efficient behavior of small-world networks", Rieke and colleagues' book "Spikes: exploring the neural code" and Cohen's "Analyzing neural time series data" all carry the topic "Neural Networks and Applications"; Fuster's "The prefrontal cortex" and "Attention and brain function" sit in "Cognitive Science and Mapping"; and "MizAR 60 for Mizar 50", a 2023 paper on automated theorem proving, collects 1,680 citations from neuroscience papers, which can only be a reference-matching error. Several of these are neuroscience works labeled AI, so part of what registers as neuroscience citing AI is neuroscience citing itself. I read the off-topic category's 4.9 percent as a floor on the problem, not an estimate of it.

One strand cannot be seen here at all: AI used as a model of the brain, such as deep networks compared with cortex or representational similarity analysis. Those papers appear in neuroscience journals and OpenAlex files them as neuroscience, so they are never cited AI works and never enter this flow. My "brain-adjacent modeling" category is not that literature, and nothing in this project measures its size.

At a coarser grain, here is the composition of the gold flow by cited subfield: of neuroscience's citations of (exclusive) AI works, 57.5 percent went to the AI subfield and 42.0 percent to computer vision in 2010-2019, and 54.3 and 44.7 percent in 2020-2025.

### 4.3 The age of the neuroscience AI cites

![Vintage of the cited work](../../figures/figure_s4_vintage.png)

*Figure S4.2 (`figure_s4_vintage`). A: AI papers citing neuroscience; share of citations by publication year of the cited work, for citing papers of 2010 to 2019 (dashed) and 2020 to 2025 (solid), exclusive cited set, extended AI definition, every work type; vertical lines at the medians and a dotted line at the 2005 boundary. B: the same for neuroscience papers citing AI. C: median publication year of the cited work by citing year, both directions; hatched: provisional years. The curves end at 1990 because the mirror holds no earlier works. Data: `results/vintage/matrix_cited_vintage.csv`, `vintage_summary.csv`, `vintage_by_year.csv`.*

| AI papers citing neuroscience | 2010-2019 | 2020-2025 | 2020-2023 |
|-|-:|-:|-:|
| Citations, exclusive set | 224,890 | 315,457 | 179,925 |
| Median cited year | 2007 | 2015 | 2014 |
| Share published 2005 or earlier (%) | 43.8 | 19.9 | 23.1 |
| Share published 2004 or earlier (%) | 39.3 | 17.8 | 20.7 |
| Mean age (years) | 9.2 | 10.1 | 10.1 |
| Within ages 0-20: median age (years) | 7 | 7 | 7 |
| Within ages 0-20: share aged 5 or less (%) | 38.0 | 43.1 | 42.4 |

Extended AI definition, every work type, exclusive cited set. In calendar terms the cited neuroscience got newer by eight years: the median cited year moved from 2007 to 2015, and the share published in 2005 or earlier fell from 43.8 to 19.9 percent. Using the unrestricted set, I find the median moves from 2007 to 2016 and the share falls from 42.5 to 18.0 percent; restricted to articles and reviews, the median again moves from 2007 to 2015. So the shift of the median cited year holds under every variant.

What that shift is made of shows in the bottom rows. Inside the common 0-to-20-year window, the median age of the neuroscience that AI cites was 7 years in both periods, and the share of citations going to work at most five years old rose modestly, from 38.0 to 43.1 percent. Panel C shows the same thing year by year: the median cited year climbs almost in step with the citing year, eight years behind it in every year from 2012 to 2025. Most of the eight-year shift between the two decades, I conclude, is the decade itself. AI papers cite neuroscience that is about as old, relative to them, as it was ten years ago, and a little younger at the recent end. Over all ages, the mean age rises from 9.2 to 10.1 years only because later papers can see further back into the mirror.

The article's statement in paragraph 16 that AI continues to cite newer neuroscience papers rests on the median cited year, 2007 in 2010-2019 and 2015 in 2020-2025 (second row of the table). The fixed-age medians of the bottom rows are the further check: at a fixed age of the cited work the median is the same in both periods, so the cited neuroscience is newer in calendar terms and cited at about the same lag. The neuroscience AI cites keeps pace with the calendar and has not frozen at an old canon. For paragraph 6, a fifth of AI's citations of neuroscience in 2020-2025 still go to work published in 2005 or earlier (19.9 percent), with works before 1990 not even counted. Individual works confirm it: the three neuroscience works most cited by AI papers in 2020-2025 are Izhikevich's spiking-neuron model (2003), Bi and Poo's spike-timing plasticity paper (1998) and Zucker and Regehr's review of short-term plasticity (2002) (`top25_inspection.csv`).

### 4.4 Robustness: AI papers inside the neuroscience label

My removal rule of section 3.4 took out 13,946 cited works: 13,925 by the title pattern, 11 clear AI papers and 10 borderline ones from the two top-25 lists (for example "MetaFormer is actually what you need for vision", filed under visual perception, and two neural style-transfer papers filed under aesthetic perception).

| Extended AI, exclusive set, after all removals | 2010-2019 | 2020-2025 | 2020-2023 |
|-|-:|-:|-:|
| Cognitive share (%) | 86.1 | 82.4 | 82.9 |
| Median cited year | 2006 | 2014 | 2013 |
| Share published 2005 or earlier (%) | 45.6 | 22.1 | 25.7 |
| Fails the declared thresholds | no | yes | yes |

It fails in part, and it fails where I designed it to look. Exclusive, the cognitive share holds within 0.7 points, which passes. Unrestricted, it moves by up to 2.2 points for 2020-2025, over the 2-point threshold. Median cited years of the recent period drop by one year in most cells, and by two in the unrestricted set for 2020-2023, which fails. Old-work shares (published in 2005 or earlier) for 2020-2025 rise by 2.2 to 2.8 points across the cells, over the threshold everywhere. Most removed works are recent AI papers, so taking them out makes the recent period look older. Levels I quote for 2020-2025 are therefore about one year and two to three points softer than the baseline suggests.

Between the periods, the shift does not depend on them. In the exclusive set the median moves by 8 years at every stage of removal, and the fall in the share published in 2005 or earlier stays between 23.3 and 23.9 points (`robustness_shift.csv`). Neither the eight-year shift nor the subfield ranking rests on mislabeled AI papers.

### 4.5 The opposite direction: how old is the AI that neuroscience cites

| Neuroscience papers citing AI (exclusive) | 2010-2019 | 2020-2025 | 2020-2023 |
|-|-:|-:|-:|
| Median cited year | 2006 | 2016 | 2015 |
| Share published 2005 or earlier (%) | 47.6 | 17.4 | 20.8 |
| Within ages 0-20: median age (years) | 8 | 6 | 6 |
| Within ages 0-20: share aged 5 or less (%) | 35.5 | 49.0 | 46.4 |

Here, unlike the teal flow, the cited work got younger in age, not only in calendar years. During 2010-2019 neuroscience papers cited older AI than AI papers cited neuroscience (median cited year 2006, 47.6 percent published in 2005 or earlier). By 2020-2025 the median age inside the common window had fallen from 8 to 6 years, and nearly half of neuroscience's AI citations went to work five years old or less. In 2025 alone the median AI work cited by neuroscience dates from 2019 and the median neuroscience work cited by AI from 2017. That fits the adoption of deep-learning tools in neuroscience after 2015 that the gold line of Figure 1 records ([S2](S2-citation-flow.md)). In the last decade, then, the change of habit happened on the neuroscience side.

### 4.6 The six NeuroAI papers

![Citations of the six NeuroAI papers](../../figures/figure_s4_manifestos.png)

*Figure S4.3 (`figure_s4_manifestos`). A: citations received from AI papers (extended definition) by the six NeuroAI review papers of the article's sidebar, per citing year 2015 to 2025, stacked by paper. B: the same citations as a percentage of all AI-to-neuroscience citation edges that year (left axis), and the number of those edges in thousands (dashed, right axis). Hatched: 2024 and 2025, provisional. Data: `results/manifestos/citations_by_paper_year_field.csv`, `share_of_flow_by_year.csv`.*

All six papers resolve in the mirror. The classifier labels four of them neuroscience (Hassabis 2017, Richards 2019, Lillicrap 2020, Macpherson 2021) and two AI (Sinz 2019, Zador 2023, which carry the topics anomaly detection and reinforcement learning in robotics).

| Citations received 2020-2023 | from AI | from neuroscience | from neither | total |
|-|-:|-:|-:|-:|
| Hassabis et al. 2017 | 341 | 206 | 288 | 835 |
| Richards et al. 2019 | 153 | 365 | 140 | 658 |
| Lillicrap et al. 2020 | 201 | 208 | 122 | 531 |
| Sinz et al. 2019 | 41 | 54 | 32 | 127 |
| Macpherson et al. 2021 | 8 | 17 | 35 | 60 |
| Zador et al. 2023 | 16 | 19 | 21 | 56 |
| All six | 760 | 869 | 638 | 2,267 |

AI and neuroscience papers cite the six about equally (760 against 869 citations in 2020-2023), and Hassabis et al. is the only one with a clear AI majority. Per year, citations from AI papers to the six rose from 3 in 2017 to 144 in 2020 and 215 in 2021, then held near 200: 194 in 2022, 207 in 2023, 185 in 2024 and 214 in 2025. Over the same years the AI-to-neuroscience flow kept growing, from 57,081 edges in 2020 to 72,841 in 2023 and 97,295 in 2025. Together the six therefore account for 0.25 to 0.32 percent of the flow in 2020-2023, with the peak in 2021, and for about 0.2 percent in 2024-2025. Counting only the four papers that sit inside the flow's denominator, the share is 0.24 to 0.31 percent.

Removing the six as cited works changes the teal odds ratio of Figure 1 by at most 0.31 percent in any year from 2015 to 2023 (2023: 0.0544 before, 0.0543 after), and the gold one by at most 0.02 percent. Those papers do not move the curve.

On shape: year-over-year changes in citations of the six from AI papers correlate with changes in the number of AI-to-neuroscience edges at a Spearman coefficient of 0.59 (exact p = 0.098), and with changes in the odds ratio at -0.34 (p = 0.36). Levels correlate at 0.98, which only says that both rose.

So the answer to the reviewer's question is: not really, at least not in this window. AI authors picked up the six papers quickly up to 2021 and then their citations from AI papers reached a plateau of about 200 a year, while the flow and the odds ratio kept climbing through 2023. Their changes move loosely together with the flow's volume, which may simply reflect that both depend on how much AI is published, and not at all with the odds ratio. Nine changes and six papers cannot support a test of whether two curves are the same, and the p-values do not claim one. Nor is a citation from an AI paper evidence that the author was persuaded: reviews are cited to frame, to justify and to disagree. What the data allow me to say about paragraph 8 is that the teal rise and the manifestos are contemporaneous, as the article says ("consistent with the timing"), and that the rise is not made of citations to the manifestos. Whether the manifestos express a wider change or helped cause one is not something these counts can tell.

### 4.7 Reference age: AI's short citation memory

![Reference age by field](../../figures/figure_s4_reference_age.png)

*Figure S4.4 (`figure_s4_reference_age`). A: distribution of reference age (citing year minus publication year of the cited work) for AI and neuroscience papers of 2020 to 2023, OpenAlex types article and review, all references that resolve to a dated work; dashed lines at the medians. B: median (solid) and 90th percentile (dashed) of reference age by citing year. C: share of papers with any reference list in the mirror, every work type (solid) and articles and reviews (dashed). Hatched: provisional years. Data: `results/vintage/matrix_reference_age.csv`, `reference_age_by_field.csv`, `reference_list_coverage.csv`.*

| Articles and reviews, 2020-2023 | AI papers | Neuroscience papers |
|-|-:|-:|
| References with a dated cited work | 12,173,300 | 14,320,543 |
| Median age (years) | 4 | 8 |
| Mean age (years) | 6.6 | 9.7 |
| 90th percentile (years) | 16 | 21 |
| Share aged 5 or less (%) | 58.5 | 36.2 |
| Share aged 10 or less (%) | 80.1 | 62.2 |

The commentator's argument has two parts: machine learning has a short citation memory, and old ideas that have been absorbed stop being cited ("obliteration by incorporation"), so citation counts understate foundational influence. His spot check found about two thirds of the references of contemporary AI conference papers aged five years or less, a median of three years, and a median of eight years for neuroscience journal papers.

On the whole corpus, I find the first part holds. For AI articles and reviews of 2020-2023 the median reference is 4 years old and 58.5 percent of references are five years old or less; for neuroscience the median is 8 years and the share 36.2 percent. His neuroscience median reproduces exactly. His AI values are close to mine, a little older and a little less concentrated on recent work than his sample, which is what I would expect when journal articles are mixed in with conference papers (OpenAlex does not separate the two reliably). Including every work type, I get an AI median of 5 years and a share of 58.2 percent. AI's memory has also shortened: the AI median was 6 years for papers of 2010-2019 and 4 for 2020-2023, while the neuroscience median went from 7 to 8. Truncation at 1990 cannot produce this, because later papers can see further back, which pushes their ages up, not down.

Cross-field references sit in between. When AI papers of 2020-2023 cite neuroscience, the median cited work is 7 years old and 43.4 percent are five years old or less; when neuroscience papers cite AI, the median is also 7 years and the share 41.9 percent. AI reaches further back when it cites neuroscience than it does in its reference lists overall.

Plainly, the second part is beyond any citation count. An idea absorbed so thoroughly that it is no longer cited leaves no edge in the graph, and a citation analysis can neither confirm nor rule out such debt. Tracing the lineage of attention mechanisms or of convolution from ideas about the visual system, for example, is not possible from who cited whom in 2023. Tracing the people who carried ideas across, as the commentator suggests, is a complementary method; [S5](S5-bridge-builders.md) lists the authors and institutions whose work both fields cite, which is a start on that route, not a substitute for it. What these numbers do say is that AI's short memory is real and large, so a citation-based measure will understate neuroscience's older contributions to AI more than it understates contributions in the other direction. That strengthens the caveat in [S2](S2-citation-flow.md), section 5, and it means the 19.9 percent of section 4.3 is a lower bound on how much of what AI owes neuroscience is old.

Coverage limits what any of this covers, and I checked it. Only 41.7 to 57.0 percent of AI works of 2020-2025 have any reference list in the mirror (every work type; 52.1 percent in 2020, 46.0 percent in 2023, 41.7 percent in 2025), against 55.5 to 59.3 percent of neuroscience works in 2020-2024. Among articles and reviews the AI coverage is higher, 60.3 percent in 2020 and 70.7 percent in 2023. Of the references that are listed in 2020-2023, 80.6 percent of AI references and 91.1 percent of neuroscience references resolve to a dated work; the rest point at works missing from the mirror, including everything before 1990. Since the unresolved fraction is twice as large for AI, and plausibly older, the AI tail is the more understated of the two. Under-indexed conference reference lists are a real possibility, and papers without lists are simply not in the sample.

## 5. Caveats and what this does not show

Citations record use, not intellectual debt. Citing lme4 and citing a theory of plasticity count the same in my tables. Section 4.7 adds that some debts are never recorded at all.

My mirror starts in 1990. Every share of "old" work is a lower bound, because work published before 1990 cannot be counted, and every age statistic over all ages drifts upward with the citing year. A common 0-to-20-year window removes the drift but ignores older work by design.

Classification decides the subfield shares. The 90 and 5 percent of the cognitive-neuroscience sentence were computed for AI papers under the 35-topic core definition (section 4.1). A wider definition that adds computer vision and medical imaging papers shifts the shares, to 82.7 and 9.96 percent for the extended definition (section 4.1), so the values belong to the definition used. The imaging half of the gold-flow composition exists under the extended definition only (section 4.2). OpenAlex classifies on the primary topic, its "cognitive neuroscience" is broad (psycholinguistics, perception, attention and cognitive science sit inside it), and its labels carry errors on single papers, some of them heavily cited (section 4.2). The share of works with any primary topic falls in 2024 and 2025.

The exclusive set and the robustness removals reduce, but cannot eliminate, AI papers filed under neuroscience, and the title pattern also removes some genuine neuroscience. The check of section 3.4 failed for the levels of the recent period; I report those levels with that qualification.

Over the 87 topic names, the category assignment of section 3.2 is mine, made by hand. Someone else would draw some lines differently; the file lets them.

Only after seeing the calendar results did I add the common age window of section 3.3. Its conclusion (the shift is mostly the calendar) also follows directly from panel C of Figure S4.2, which uses the pre-declared statistics.

Six papers are six papers, and I treat them so. My manifesto analysis describes their citation curves; it cannot test influence, and the 2024 and 2025 values are provisional.

Reference lists are missing for about half of the papers in both fields, more so for AI, and conference papers may be under-indexed. My reference-age results describe papers with lists.

## 6. Reproduce

From the committed files, without the OpenAlex data:

```bash
# the four figures of this supplement (read results/ only)
.venv/bin/python -m neuroai_cn.figures.figure_s4_vintage

# rebuild the manifesto tables from the committed counts
.venv/bin/python -m neuroai_cn.analysis.manifesto_citations

# every number in this supplement, checked against the results files
.venv/bin/python -m pytest -q tests/test_supplement_claims.py tests/test_vintage.py tests/test_manifestos.py
```

All numbers I quote here are read by `src/neuroai_cn/analysis/s4_numbers.py`, which is what the claims in `docs/supplements/claims/S4.yaml` call.

Given the local OpenAlex mirror (`NEUROAI_DATA`, see `src/neuroai_cn/config.py`), one heavy job at a time:

```bash
# cited-vintage pipeline: labels, edges, cross-field edges, reference ages, then the tables
.venv/bin/python -m neuroai_cn.analysis.cited_vintage.build --stage labels
.venv/bin/python -m neuroai_cn.analysis.cited_vintage.build --stage edges
.venv/bin/python -m neuroai_cn.analysis.cited_vintage.build --stage cross
.venv/bin/python -m neuroai_cn.analysis.cited_vintage.build --stage refage
.venv/bin/python -m neuroai_cn.analysis.cited_vintage.vintage
.venv/bin/python -m neuroai_cn.analysis.cited_vintage.robustness
.venv/bin/python -m neuroai_cn.analysis.cited_vintage.reference_age

# the six NeuroAI papers, re-queried from the mirror
.venv/bin/python -m neuroai_cn.analysis.manifesto_citations --recompute

# composition and head of the neuroscience-citing-AI flow, then the small export
.venv/bin/python -m neuroai_cn.audits.flow_composition --classifier extended
.venv/bin/python -m neuroai_cn.audits.flow_composition --classifier strict
.venv/bin/python -m neuroai_cn.audits.flow_concentration
.venv/bin/python -m neuroai_cn.analysis.export_flow_composition
```

The design of the vintage analysis, with the definitions declared before the queries, is in `src/neuroai_cn/analysis/cited_vintage/definitions.py` and its README; the manifesto definitions are in the docstring of `src/neuroai_cn/analysis/manifesto_citations.py`. An older figure, `fig_flow_composition`, draws the same composition as panels C and D of Figure S4.1 from the heavy files (`python -m neuroai_cn.figures.flow_composition_fig`).

## 7. Related

- [S1. Data, corpus and field classification](S1-data-and-classification.md): the snapshot, the two AI definitions, the topic labels and their errors.
- [S2. Citation flow](S2-citation-flow.md): the odds ratio of Figure 1, whose two flows are decomposed here.
- [S3. Counts, shares and field sizes](S3-counts-and-field-sizes.md): the raw counts behind the flows.
- [S5. The bridge builders](S5-bridge-builders.md): the papers, authors and institutions that both fields cite.
- [S6. Does citation age explain the bridge canon?](S6-citation-age.md): the second half of paragraph 16, newer papers and the bridge ranking.
- [Methods 02, field classification](../methods/02-field-classification.md) and [methods 06, decisions and limitations](../methods/06-decisions-and-limitations.md): formal definitions.

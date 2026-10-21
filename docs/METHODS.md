# Methods

This document defines every quantity behind the article "Examining the bridge between neuroscience and AI" (*The Transmitter*) and its six supplements: the data, the field labels, the odds ratio and its trends, the cross-source checks, the raw counts and shares, the bridge score and its aggregates, the composition of what AI cites, and the citation-age controls. Each supplement carries the short version of the methods it uses and links here for the full definition. Behind every formula I name the module and function in backticks. My reference is the code under `src/neuroai_cn/` and the committed tables under `results/`, and I read every constant below from them.

- [1. Terms and labels](#1-terms-and-labels)
- [2. Data](#2-data)
- [3. Field definitions](#3-field-definitions)
- [4. Citation flow and the odds ratio](#4-citation-flow-and-the-odds-ratio)
- [5. Trends and change points](#5-trends-and-change-points)
- [6. Cross-source replication](#6-cross-source-replication)
- [7. Counts, shares and field sizes](#7-counts-shares-and-field-sizes)
- [8. Bridge works](#8-bridge-works)
- [9. What AI cites in neuroscience](#9-what-ai-cites-in-neuroscience)
- [10. Citation-age controls](#10-citation-age-controls)
- [11. Statistical conventions and reproducibility](#11-statistical-conventions-and-reproducibility)

## 1. Terms and labels

I use these labels in the same sense in the article, the supplements, the figures and the result files.

| Term | Meaning | Name in code and data |
|-|-|-|
| OpenAlex snapshot of 30 March 2026 | the single copy of OpenAlex every number comes from, 458,112,708 work records (section 2) | `NEUROAI_DATA`, `config.py` |
| neuroscience | a paper whose OpenAlex primary topic lies in field 28, Neuroscience | `neuro` |
| AI | a paper whose primary topic satisfies the extended definition, unless the 35-topic core definition is named | `ai` |
| extended definition | subfield 1702 (Artificial Intelligence) minus 26 topics, plus all of subfield 1707 (Computer Vision and Pattern Recognition), plus topic T10502; the definition of Figure 1 (section 3.2) | `build_extended_field_assignment` |
| 35-topic core definition | a hand-curated set of 35 topics of subfield 1702, a proper subset of the extended definition (section 3.3) | `AI_CORE_TOPIC_IDS`; `strict35`, `label_strict_core35`, `ai_strict_core35` and file names with `strict` |
| subfield 1702 definition | every topic of subfield 1702, with no exclusion and without subfield 1707; used only in the cross-source samples (section 6) | `strict` and `ai_strict` in the samplers |
| third field | a paper with a primary topic in neither field | `other` |
| unknown | a paper with no primary topic | `unknown` |
| gold line | neuroscience papers citing AI, which measures the influence of AI on neuroscience; color `#D4A521` | `neuro_to_ai` |
| teal line | AI papers citing neuroscience, which measures the influence of neuroscience on AI; color `#277E8A` | `ai_to_neuro` |
| count | cross-field references per citing year (Figure 2A) | `n_to_target` |
| share | cross-field references per 1,000 references to works of known field (Figure 2B) | section 7 |
| odds ratio | the restricted odds ratio of Figure 1's vertical axis: the observed cross-field share against the share expected from the sizes of the two fields, among references to and papers of known field in either field | `or_restricted` |
| unrestricted odds ratio | the same with third-field references and papers kept in both shares | `or_population` |
| provisional years | 2024 and 2025; shown, never fitted; every fit stops at 2023 | `LAST_SOLID_YEAR = 2023` |
| bridge score B | harmonic mean of the citations a paper receives from neuroscience papers and from AI papers | `B_harmonic` |
| bridge papers | the 133,763 papers with at least 5 citations from each field | `q4_v3_extended_full` |
| eligible papers | the 58,971 bridge papers that carry a neuroscience or AI label and have under 10,000 citations from the two fields | `eligible_pool` |
| sum of B | the bridge weight of an author or institution, B summed over its papers (section 8.4) | `total_B` |
| top 15 | the papers, authors and institutions shown in Figure 3 | Tables S5.1 to S5.3 (`table_s1`, `table_s2`, `table_s3`) |

In code and data files the teal line is `ai_to_neuro` and the gold line `neuro_to_ai`, named after the citation link while the colors follow the citing field (`style.DIRECTION_COLORS`); arrows appear nowhere else in these documents.

## 2. Data

### 2.1 The snapshot

Except for the cross-source samples of section 6, all my numbers come from the OpenAlex snapshot of 30 March 2026, which I downloaded as 381 daily update files, converted to year-partitioned parquet (about 364 GB) and indexed in DuckDB (`scripts/download_snapshot.sh`, `convert_to_parquet.py`, `build_duckdb_index.py`). Values: `results/corpus/corpus_totals.csv`.

| Quantity | Value |
|-|-:|
| Work records in the snapshot, all publication years | 458,112,708 |
| Works in the DuckDB index, publication years 1990 to 2026 | 398,288,606 |
| of which published 1990 to 2025 | 386,753,369 |
| Works with a primary topic | 311,299,063 |
| Works with a non-empty reference list | 111,676,520 |
| Citation edges (one per entry of a reference list) | 2,893,128,636 |
| OpenAlex topics | 4,516 |

My index holds only works published from 1990 on, so a cited work published earlier is never a node, and references to it count as pointing to a missing work. I added by hand four records for anchor papers absent from the download; they are not among the 458,112,708. Since the year 2026 is incomplete, I exclude it from every series.

### 2.2 Edges and scope rules

By a citation edge I mean one entry in the reference list of a citing work. Its year is the publication year of the citing work (`citation_edges.citing_year`), so every series is indexed by citing year: a point at 1998 describes what papers published in 1998 cited. I classify the cited work by its own label (section 3.1). In the yearly flow tables of sections 4 and 7 the field labels cover works published 1990 to 2025, so a reference to a work dated 2026 counts as missing; in the bridge counts of section 8 the labels cover 1990 to 2026.

Just 28.0 percent of indexed works carry a reference list, and the share differs by field and year (`results/flow/field_sizes_by_year.csv`, column `n_with_references`). A paper without a reference list can be cited but cannot cite. And the share of works with any primary topic falls in the most recent years, which is one reason 2024 and 2025 are provisional.

### 2.3 The curated pools

Before the analysis I built a curated corpus of four overlapping pools (`src/neuroai_cn/corpus/`): works by authors of five NeuroAI anchor publications or affiliated with one of 21 OpenAlex institutions between 2019 and 2026 (`pool1.py`); works whose titles match one of five keyword templates (`pool2.py`); works in curated venue lists (`pool3.py`); and works by six rosters of seed authors (`pool4.py`). Deduplicated by work identifier, the union holds 2,153,057 works (`results/corpus/pool_sizes.csv`). Pool 2 matches titles only, and three of its ten false-positive traps set a flag rather than remove a work; the other seven need abstracts, and I do not apply them. **No published number reads the pools.** I define the odds ratio against field sizes over the whole literature, and a sample selected for neuroscience and AI citing each other would inflate both the observed and the expected share by construction, so in sections 4 to 10 I count over every classified work of the snapshot.

## 3. Field definitions

### 3.1 One paper, one label

In OpenAlex, each classifiable work sits in a hierarchy of topic, subfield, field and domain and carries several scored topics, the highest of which is its primary topic. I label each work from its primary topic only, in this order (`extended_classifier.build_extended_field_assignment`):

```math
L(w)=\begin{cases}\mathrm{unknown} & \mathrm{if}\ w\ \mathrm{has\ no\ primary\ topic}\\ \mathrm{neuroscience} & \mathrm{if\ its\ field\ is}\ 28\\ \mathrm{AI} & \mathrm{if\ its\ topic\ is\ in}\ (S_{1702}\setminus X_{26})\cup S_{1707}\cup\lbrace T10502\rbrace\\ \mathrm{other} & \mathrm{otherwise}\end{cases}
```

where $S_{1702}$ and $S_{1707}$ are the topics of the two subfields and $X_{26}$ the excluded topics of section 3.2. My neuroscience covers the 62 topics of the eight subfields of field 28 (Behavioral Neuroscience, Biological Psychiatry, Cellular and Molecular Neuroscience, Cognitive Neuroscience, Developmental Neuroscience, Endocrine and Autonomic Systems, Neurology, Sensory Systems). No topic belongs to both label sets, so no paper counts on both sides. A paper's references play no part in my rule, although OpenAlex's own topic classifier reads a work's title, abstract, venue and citations. Every topic with its labels and work count is in `results/corpus/classification_topics.csv`, written by `analysis.export_field_sizes`.

### 3.2 The extended definition and how it was selected

Subfield 1702 holds 77 topics. I read the list and removed the 26 topics that are either not computer science or computer science without machine-learning content (`extended_classifier.BAD_1702_TOPIC_IDS`). I give OpenAlex's own names; the misspelling of T13559 is theirs.

| Reason for exclusion | Topics |
|-|-|
| OpenAlex artifact: 50,854 works in 2024 and 2,818,121 in 2025 | T12157 Geochemistry and Geologic Mapping |
| Another science, clustered into 1702 through machine-learning applications | T11276 Solar Radiation and Photovoltaics; T13018 Seismology and Earthquake Studies |
| Quantum computing and cryptography | T10020 Quantum Information and Cryptography; T10682 Quantum Computing Algorithms and Architecture; T10237 Cryptography and Data Security; T10764 Privacy-Preserving Technologies in Data; T11130 Coding theory and cryptography; T10951 Cryptographic Implementations and Security; T11424 Security and Verification in Computing |
| Signal processing and networking | T10711 Target Tracking and Data Fusion in Sensor Networks; T11598 Internet Traffic Analysis and Secure E-voting; T12131 Wireless Signal Modulation Classification |
| Software and programming languages | T10126 Logic, programming, and type systems; T10639 Advanced Software Engineering Methodologies |
| Education | T13567 AI and Multimedia in Education; T13559 Edcuational Technology Systems; T11902 Intelligent Tutoring Systems and Adaptive Learning; T12260 Educational Technology and Pedagogy; T14335 Educational Robotics and Engineering |
| Business, law and management | T14064 Organizational and Employee Performance; T13851 Law, AI, and Intellectual Property; T12128 AI in Service Interactions |
| General algorithms and control | T11269 Algorithms and Data Compression; T13935 Mathematical Control Systems and Analysis; T14175 Intuitionistic Fuzzy Systems Applications |

I keep the remaining 51 topics of 1702 as AI. Then I added subfield 1707 whole (35 topics), because in the hand-picked audit set of `results/corpus/anchor_labels.csv` subfield 1702 alone labels only 4 of the 15 plainly AI papers as AI, with AlexNet, ResNet and the GAN paper in computer vision, while the extended definition labels 10 of them as AI; and because a definition that admits computer vision cannot choose which computer vision counts, the medical-imaging topics of 1707 stay in. Last, I added one topic from subfield 2208 (Electrical and Electronic Engineering), T10502 Advanced Memory and Neural Computing, which holds the neuromorphic-hardware literature (TrueNorth, Loihi, SpiNNaker, e-prop). I did not take subfield 1708 (Hardware and Architecture) or the rest of 2208 (power systems, semiconductors, antennas). My extended definition therefore has 51 + 35 + 1 = 87 topics. In 2023 it holds 346,525 works: 187,603 from subfield 1702 after the exclusions, 150,559 from subfield 1707 and 8,363 from T10502 (`field_sizes_by_year.csv`). I fixed this definition before computing any odds ratio and applied it uniformly. It is a choice. Section 3.3 defines the narrower alternative that I carried through the whole pipeline.

### 3.3 The 35-topic core definition and how it was selected

From the 77 topics of subfield 1702, I kept in the core those whose subject is an AI method or foundation: neural networks and learning, reinforcement learning and planning, language and speech processing, probabilistic and Bayesian methods, search and evolutionary methods, knowledge representation and reasoning. I dropped the 26 exclusions of section 3.2 and 16 further topics. AI under the core has no subfield 1707 and no T10502 (`strict_classifier.build_strict_field_assignment`, reading `utils.duckdb.AI_CORE_TOPIC_IDS`). All 35 topics lie in the extended definition, so every core AI paper is also an extended AI paper.

| Theme | Topics of the core |
|-|-|
| Neural networks and learning | T10320 Neural Networks and Applications; T12611 Neural Networks and Reservoir Computing; T11273 Advanced Graph Neural Networks; T11612 Stochastic Gradient Optimization Techniques; T11689 Adversarial Robustness in Machine Learning; T12676 Machine Learning and ELM; T12072 Machine Learning and Algorithms; T12535 Machine Learning and Data Classification; T11652 Imbalanced Data Classification Techniques; T12026 Explainable Artificial Intelligence (XAI) |
| Reinforcement learning, agents and planning | T10462 Reinforcement Learning in Robotics; T10456 Multi-Agent Systems and Negotiation; T10906 AI-based Problem Solving and Planning; T11574 Artificial Intelligence in Games |
| Language and speech | T10181 Natural Language Processing Techniques; T10201 Speech Recognition and Synthesis; T12031 Speech and dialogue systems; T10664 Sentiment Analysis and Opinion Mining; T11550 Text and Document Classification Technologies; T13083 Advanced Text Analysis Techniques; T10028 Topic Modeling |
| Probabilistic and Bayesian methods | T11303 Bayesian Modeling and Causal Inference; T11901 Bayesian Methods and Mixture Models; T12814 Gaussian Processes and Bayesian Inference |
| Data mining | T10637 Advanced Clustering Algorithms Research; T11512 Anomaly Detection Techniques and Applications; T12761 Data Stream Mining Techniques |
| Search, evolutionary and fuzzy methods | T10100 Metaheuristic Optimization Algorithms Research; T11975 Evolutionary Algorithms and Applications; T10820 Fuzzy Logic and Control Systems |
| Knowledge, reasoning and cognition | T10215 Semantic Web and Ontologies; T11010 Logic, Reasoning, and Knowledge; T12805 Cognitive Science and Mapping; T13062 Cognitive Computing and Networks; T13904 Artificial Intelligence Applications |

Sixteen topics of subfield 1702 are AI under the extended definition but fall outside the core: applied-domain buckets (T10862 AI in cancer detection; T13702 Machine Learning in Healthcare; T12262 Hate Speech and Cyberbullying Detection; T12380 Authorship Attribution and Profiling; T13629 Text Readability and Simplification; T13514 Experience-Based Knowledge Management), broad catch-alls (T13398 Data Analysis with R; T13650 Computational Physics and Python Applications; T13674 Computer Science and Engineering; T13734 Advanced Computational Techniques and Applications; T13898 Diverse Interdisciplinary Research Studies; T14351 Statistical and Computational Modeling; T14413 Advanced Technologies in Various Fields), linguistics (T13623 Linguistic Studies and Language Acquisition), psychiatry (T14381 Psychiatry, Mental Health, Neuroscience), and one methods topic, T11307 Domain Adaptation and Few-Shot Learning. I use the core for the counterfactual series of section 4.6, for the headline subfield shares of section 9.2 and as a column of `classification_topics.csv`.

### 3.4 Leave-one-topic-out

To test whether the exclusion list drives the odds ratio, I recomputed the whole yearly series once per candidate topic with that topic re-admitted to AI (`audits.bootstrap_sensitivity.loto_sensitivity`, results in `results/flow/sensitivity_loto.csv`). Twenty-seven candidates are in the file: the 26 exclusions and T11017, a topic of subfield 1707 that is already AI and therefore changes nothing. As the measure for topic $k$ I take the largest relative change in any year $y$ and either direction $d$:

$$
\Delta_k=\max_{y,d}\left|\frac{\mathrm{OR}^{(k)}_{y,d}}{\mathrm{OR}_{y,d}}-1\right|
$$

and I report it over 1990 to 2025 and over the fitted years 1995 to 2023. S2 gives the values.

### 3.5 The anchor audit and the other two schemes

Seventy rows (68 distinct papers) make up the audit set of `results/corpus/anchor_labels.csv`: papers I expected to be neuroscience, papers I expected to be AI, and bridge papers. I labeled each under three schemes: the topic scheme above (the only one any published number uses); a venue scheme that matches `primary_location.source.display_name` exactly against four lists (core neuroscience, core AI, mixed, general high-impact; `audits/scheme2_venues.py`); and Semantic Scholar's fields of study looked up by DOI (`audits/scheme3_s2fos.py`). I compute no agreement rate between schemes 1 and 3, because Semantic Scholar has no record for many anchors and labels most others as both fields. Errors of the topic scheme concentrate at the boundary: the DQN paper is labeled neuroscience, the AFNI software is labeled AI (medical image segmentation sits in 1707), FSL sits in Radiology (2741) and AlphaFold in Molecular Biology (1312), both third field, and two neuroscience classics fall outside field 28 (Bargmann's *C. elegans* work in 1302, Buzsáki and Draguhn 2004 in 1312).

## 4. Citation flow and the odds ratio

### 4.1 What is counted

For citing year $y$, citing field $s$ and the other field $t$, I count every edge whose citing work has label $s$ by the label of the cited work (`audits.q1_v3_extended.compute_or_by_year`):

| Symbol | Column | Cited work |
|-|-|-|
| $W$ | `n_to_within` | in the citing field |
| $T$ | `n_to_target` | in the other field |
| $O$ | `n_to_other` | in a third field |
| $U$ | `n_to_unknown` | in the index, no primary topic |
| $M$ | `n_to_missing` | not in the index (or dated outside 1990 to 2025) |
| $N_s$, $N_t$, $N_o$ | `n_works_source`, `n_works_target`, `n_works_other` | works published in year $y$ with each label, of every type, with or without a reference list |

I compute both directions: $s$ = neuroscience gives the gold line (`neuro_to_ai`), $s$ = AI the teal line (`ai_to_neuro`). I committed the table as `results/flow/or_by_year.csv` (72 rows, 1990 to 2025); `analysis.export_flow_inputs` exports it from the pipeline unchanged.

### 4.2 The restricted odds ratio

Of the citing field's references to either field, the observed share is the fraction that go to the other field; the expected share is the other field's fraction of the two fields' papers in the citing year, which is what the observed share would be if references were handed out in proportion to field size:

$$
\rho=\frac{T}{W+T},\qquad \rho_0=\frac{N_t}{N_s+N_t}
$$

Dividing the odds of the first by the odds of the second gives the odds ratio (`q1_v3_extended._odds_ratio`):

$$
\mathrm{OR}=\frac{\rho/(1-\rho)}{\rho_0/(1-\rho_0)}=\frac{T}{W}\cdot\frac{N_s}{N_t}
$$

The right-hand form follows because $\rho/(1-\rho)=T/W$ and $\rho_0/(1-\rho_0)=N_t/N_s$; I checked that it holds to machine precision on the committed table. At a value of 1 the field crosses into the other exactly as often as the two sizes predict; below 1 it cites itself more than that. Since $\rho_0$ is the cited field's share of the two-field literature, a change in relative field size moves the odds ratio with no change in citing behavior; section 7.3 decomposes that effect. By "restricted" I mean that third-field and unknown references are left out of $\rho$ and third-field papers out of $\rho_0$.

### 4.3 The unrestricted odds ratio

Keeping the third field in both shares gives the unrestricted variant:

$$
\rho^{\mathrm{pop}}=\frac{T}{W+T+O+U},\qquad \rho_0^{\mathrm{pop}}=\frac{N_t}{N_s+N_t+N_o}
$$

with the odds ratio formed in the same way (`or_population`). Note the asymmetry. References to works without a topic enter the observed denominator; works without a topic do not enter the expected one.

### 4.4 Wilson intervals

Pale bands in Figure 1 are 95 percent Wilson score intervals for the proportion $\rho$, without continuity correction (`q1_v3_extended._wilson`), with $n=W+T$ for the restricted ratio and $n=W+T+O+U$ for the unrestricted one and $z=1.96$:

$$
\rho_{\pm}=\frac{\rho+\dfrac{z^2}{2n}\pm z\sqrt{\dfrac{\rho(1-\rho)}{n}+\dfrac{z^2}{4n^2}}}{1+\dfrac{z^2}{n}}
$$

I pass each endpoint through the odds-ratio formula with the same $\rho_0$, giving `or_restricted_lo` and `or_restricted_hi`. These intervals express counting noise only. Classification error and database drift are not in them.

### 4.5 Window

I compute the series for 1990 to 2025. Figure 1 plots 1995 to 2025, because 1990 to 1992 rest on a few hundred cross-field references per direction and year. Every fit (sections 5.2 to 5.5) uses 1995 to 2023. In a hatched band I draw the provisional years 2024 and 2025.

### 4.6 The 35-topic core counterfactual

Running the same computation with the labels of section 3.3 gives `results/flow/sensitivity_strict_or_by_year.csv` (`audits/q1_strict.py`, exported by `analysis.export_flow_sensitivity`). Its slopes use the same segments and conventions as Figure 1.

## 5. Trends and change points

I compute every trend statistic on the yearly restricted odds ratio $y_t$ (the center of the pale band), never on the smoothed line.

### 5.1 The rolling mean

Thick lines in Figure 1 are centered 5-year means with at least three values per window (`figures.cross_source.rolling_mean`, a pandas rolling window with `center=True, min_periods=3`):

$$
\bar y_t=\frac{1}{|K_t|}\sum_{k\in K_t}y_k,\qquad K_t=\lbrace k: |k-t|\le 2,\ 1995\le k\le 2025\rbrace,\qquad |K_t|\ge 3
$$

At 1995 and 2025 the mean covers three years, at 1996 and 2024 four. Consequently, the point at 2023 averages 2021 to 2025 and so includes both provisional years. For Figure 2 I apply the same mean to the whole series from 1990 (section 7.1). Plotted values: `results/flow/figure1_article_panelA.csv`.

### 5.2 Slopes

Slopes are ordinary least-squares coefficients of $y_t$ on the year inside a segment $S$, in odds-ratio units per year:

$$
\hat b=\frac{\sum_{t\in S}(t-\bar t)(y_t-\bar y)}{\sum_{t\in S}(t-\bar t)^2},\qquad \mathrm{SE}(\hat b)=\sqrt{\frac{\sum_{t\in S}\hat e_t^{2}}{(n-2)\sum_{t\in S}(t-\bar t)^2}}
$$

where $\hat e_t$ are the residuals and $n=|S|$. The t interval is $\hat b \pm t_{0.975,n-2} \mathrm{SE}$ and the p-value is two-sided with $n-2$ degrees of freedom (`analysis.changepoints.segment_stats`, `results/flow/segment_slopes.csv`). But the figure's whiskers use the bootstrap of section 5.4.

### 5.3 The four eras of panel B

I fixed the eras in code as `style.CANONICAL_ERAS`, inclusive at both ends, and clip every fit to 1995 to 2023 (`figure1_main_v2.panel_b_canonical`):

| Era | Range in code | Fitted years | Points |
|-|-|-|-:|
| Pre-DL (before deep learning) | 1990 to 2011 | 1995 to 2011 | 17 |
| DL emergence | 2012 to 2015 | 2012 to 2015 | 4 |
| DL expansion | 2016 to 2019 | 2016 to 2019 | 4 |
| NeuroAI era | 2020 to 2025 | 2020 to 2023 | 4 |

Their boundaries come from events in AI (AlexNet in 2012; AlphaGo and the NeuroAI papers from 2016; GPT-3 in 2020), not from the data. With the panel title "Pre-registered eras" I mean that I wrote the boundaries into the code before computing the slopes in the figure; they were not lodged with an outside registry, and S2 records the one change made to them. The six labeled papers of panel A (`style.TIER1_BRIDGES`) are annotations only; no statistic uses them.

### 5.4 The bootstrap and the significance marks

Whiskers in panels B and C come from a bootstrap over years (`figure1_main_v2._bootstrap_slope_cis`). Within a cell (one era or segment, one line) I draw the $n$ pairs $(t, y_t)$ $n$ times with replacement, refit the OLS slope, and repeat this $B=500$ times with a NumPy generator seeded with 20260528 at the start of every cell. Should all drawn years be equal, the replicate has no slope, and I drop it. The 95 percent interval is the 2.5th to 97.5th percentile of the replicate slopes and the 99 percent interval the 0.5th to 99.5th. With $\pi_{+}$ and $\pi_{-}$ the fractions of replicates with a positive and a negative slope, the mark above each bar is (`figure1_main_v2._sig_marker`):

```math
\mathrm{mark}=\begin{cases}\ast\ast & \max(\pi_{+},\pi_{-})\ge 0.995\\ \ast & \max(\pi_{+},\pi_{-})\ge 0.975\\ \mathrm{n.s.} & \mathrm{otherwise}\end{cases}
```

which says that the 99 or 95 percent percentile interval excludes zero. I resample years, not edges, because the annual cohort is the unit that varies; resampling millions of correlated edges would give intervals that look precise and mean nothing. With four points the bootstrap distribution is coarse (the 95 and 99 percent limits can coincide), so `segment_slopes.csv` also carries the t interval of section 5.2. Values are in `results/flow/figure1_article_panelB.csv` and `figure1_article_panelC.csv`.

### 5.5 The piecewise-OLS change-point search

Dashed lines in Figure 1 and the segments of panel C come from an exhaustive search over piecewise-linear fits (`figures.cross_source.detect_changepoints_series`, called by `detect_all_changepoints` for the figure and by `analysis.changepoints.ols_breakpoints` for the committed tables). For each line separately, with the years of the window split into $k+1$ consecutive segments $S_0,\dots,S_k$ by $k$ breakpoints, each segment fitted by its own OLS line, the search returns

$$
\hat\tau=\arg\min_{k\in\lbrace 0,1,2\rbrace,\ \tau_1\lt\tau_2}\ \sum_{j=0}^{k}\sum_{t\in S_j}\left(y_t-\hat a_j-\hat b_j t\right)^2\quad\mathrm{subject\ to}\quad |S_j|\ge m
$$

I try every admissible placement. There is no penalty term: the zero-breakpoint fit is the starting point, a placement with more breakpoints replaces the current best only if it has strictly smaller total squared error, and the cap of two breakpoints with the minimum segment length $m$ is the only control on complexity. I report a breakpoint as the first year of the new segment. Settings, all in `results/flow/changepoints.csv`:

| Setting | Window | $m$ | Use |
|-|-|-:|-|
| figure | 1995 to 2023 | 4 | Figure 1, panel C and the article |
| audit | 1990 to 2025 | 3 | the same search on the whole series |
| neighbor | 1995 to 2023 | 3 | exploratory, flagged `declared_in_advance = False` |

### 5.6 PELT

As a procedure of a different kind I run PELT (Killick, Fearnhead and Eckley 2012, [doi:10.1080/01621459.2012.737745](https://doi.org/10.1080/01621459.2012.737745)) through the `ruptures` package (`analysis.changepoints.pelt_breakpoints`). PELT works on the series standardized within the window, $z_t=(y_t-\bar y)/\sigma_y$ with the population standard deviation, and finds the segmentation that minimizes

$$
\sum_{j=0}^{k}\sum_{t\in S_j}\left(z_t-\bar z_{S_j}\right)^2+\beta k
$$

with an `l2` cost (shifts in mean level, not in slope), `min_size` 3 and `jump` 1. The penalty per breakpoint is $\beta = c \sigma^2 \ln n$ with $\sigma^2=1$, $n$ the number of years in the window, and $c=1$ (BIC) or $c=2$ (twice BIC), plus a constant $\beta=2$. Windows are 1990 to 2025 ($n=36$, BIC penalty 3.5835) and 1995 to 2023 ($n=29$, BIC penalty 3.3673). I declared these settings before running them; runs on other series (the unrestricted ratio, the log ratio) or windows are labeled exploratory in the same file. Neither procedure gives an interval for where a break sits, and I have not bootstrapped breakpoint locations.

## 6. Cross-source replication

### 6.1 Design

A full edge-by-edge replication through an API is not feasible, so I estimate the cross-field share from samples (`scripts/api_crosscite/`). For each field and year I draw a sample of $m$ papers and classify every reference of each paper; paper $i$ contributes counts $W_i$, $T_i$, $O_i$ (references to unknown or missing works are dropped). The estimate is the share per 1,000 of section 7.1,

$$
\hat s=1000\cdot\frac{\sum_i T_i}{\sum_i\left(W_i+T_i+O_i\right)}
$$

with a 95 percent cluster bootstrap over papers: I draw the $m$ papers with replacement 500 times, recompute $\hat s$, and the interval runs between the replicate values at positions $\lfloor 0.025R\rfloor$ and $\lfloor 0.975R\rfloor$ of the sorted $R$ valid replicates.

| Sample | Classifier | Citing years | Papers per cell | File in `results/crosssource/` |
|-|-|-|-:|-|
| OpenAlex API, May 2026, subfield 1702 definition | primary topic: field 28; AI = subfield 1702 | 1990 to 2025 | 1,500 | `openalex_live.csv` |
| OpenAlex API, May 2026, extended | AI = subfields 1702 and 1707 | 2010 to 2025 | 1,500 | `openalex_live_extended.csv` |
| Semantic Scholar | venue allow-lists | 1990 to 2025 | 400 | `s2.csv` |
| OpenAlex API, October 2026 re-check | AI = subfields 1702 and 1707 | 2020 to 2025 (and 2010 to 2019) | 1,500 | `fresh_recheck_20261006_n1500.csv`, `..._2010_2019.csv` |

OpenAlex's sampler uses the API's `sample` parameter with seed 7 and classifies each cited work by its current primary topic; the API cannot apply the 26 exclusions or add T10502, so its "extended" definition approximates the snapshot's. Semantic Scholar's sampler collects up to 10,000 bulk-search hits from the venues of `VENUE_PATTERNS` for the field and year, keeps those whose venue matches the allow-list, shuffles them with a generator seeded by the year and keeps 400; each cited work is classified by its venue against the same lists. Papers whose references Semantic Scholar elides (`data: null`), or that fail after six retries, are dropped and counted in `elision_rate`, so its estimate covers papers with reference lists. Field sizes of the same fresher vintage come, for the October re-check, from the API's `group_by` (`scripts/fresh_recheck_20261006/field_sizes.py`), and `results/flow/fresh_vs_snapshot_2020_2025.csv` recomputes the odds ratio of section 4.2 with them.

### 6.2 The open circles of Figure 1

Inside the provisional band, the four open circles are odds ratios computed from the May 2026 extended sample in 2024 and 2025. A sample gives no field sizes, so each circle borrows the snapshot's expected share for the same year and line (`cross_source.load_cells_or_implied`):

$$
\mathrm{OR}_{\mathrm{circle}}=\frac{\hat\rho/(1-\hat\rho)}{\rho_0/(1-\rho_0)},\qquad\hat\rho=\frac{\sum_i T_i}{\sum_i\left(W_i+T_i\right)}
$$

Values and the comparison with the snapshot are in `results/flow/figure1_article_circles.csv`.

### 6.3 What is compared

The sources differ in graph, classifier and vintage, so their levels differ, and I never compare or splice them. What I compare is shape: the direction of each series and its OLS slope of the per-1,000 share on the year over 2014 to 2023, each source on its own axis (Figures S2.2 and S2.3, drawn from the committed CSV files by `python -m neuroai_cn.figures.figure_s2`).

### 6.4 Drawing new samples

No one needs new samples to check a number; the committed ones suffice. To draw new ones (the API keys stay in the environment, never in the repository; both crawls checkpoint per cell in `<out>/cells.jsonl` and resume by skipping completed cells; OpenAlex runs at about 2 to 4 hours per run at $m$ = 1,500, Semantic Scholar about 8 hours at $m$ = 400):

```bash
mkdir -p logs
export OPENALEX_EMAIL=<your address>              # polite pool, required
export OPENALEX_API_KEY=<key>                     # optional; passed as api_key= when set
export SEMANTIC_SCHOLAR_API_KEY=<key>             # optional

nohup uv run python scripts/api_crosscite/openalex_crosscite_sample.py \
  --years 1990-2025 --fields neuro,ai --n 1500 --seed 7 \
  --out data/derived/api_crosscite/openalex_live > logs/oa_crosscite.log 2>&1 &

nohup uv run python scripts/api_crosscite/openalex_crosscite_sample.py \
  --years 2010-2025 --fields neuro,ai --n 1500 --seed 7 --ai-def extended \
  --out data/derived/api_crosscite/openalex_live_extended > logs/oa_crosscite_ext.log 2>&1 &

nohup uv run python scripts/api_crosscite/s2_crosscite_sample.py \
  --years 1990-2025 --fields neuro,ai --n 400 \
  --out data/derived/api_crosscite/s2 > logs/s2_crosscite.log 2>&1 &

# October 2026 re-check: fresh field sizes and a 2020-2025 sample (needs both OpenAlex variables)
scripts/fresh_recheck_20261006/run_fresh.sh

# copy the cells files to results/crosssource/*.csv (NEUROAI_CELLS_ROOT defaults to data/derived)
uv run python -m neuroai_cn.analysis.export_flow_inputs
```

A re-run against the live API will not reproduce the committed counts exactly, because the database keeps changing.

## 7. Counts, shares and field sizes

### 7.1 Definitions

With the symbols of section 4.1, for each citing year and line:

| Quantity | Formula | Where |
|-|-|-|
| count | $C=T$ | Figure 2A, `figure2_raw_v2_data.csv` |
| share, Figure 2B | $s=1000\cdot T/(W+T+O)$ | Figure 2B, `flow_numbers.cross_refs_per_1000` |
| share, companion table | $1000 \cdot T/(W+T+O+U) = 1000 \rho^{\mathrm{pop}}$ | `companion_counts_shares_sizes.csv` |
| observed share inside the odds ratio | $1000 \cdot T/(W+T) = 1000 \rho$ | Figure 1 |
| references per paper | $r=(W+T+O)/N_s$ | companion table |
| field size | $N_s$, all works of the year with the label | `field_sizes_by_year.csv` |

Only the few references to works of unknown field separate the first two shares. Figure 2 draws the yearly values and a centered 5-year mean with at least three values, computed over the whole series from 1990 (`figures.figure2_raw_v2.table`), so the thick line at 1995 averages 1993 to 1997. `results/flow/field_sizes_by_year.csv` holds the yearly sizes under every definition used (extended, 35-topic core, whole subfield 1702, 1702 after the exclusions, 1707, T10502, the 26 excluded topics), each with the number of works that have references and the number of articles and reviews.

### 7.2 Identities

Any count factors exactly into the size of the citing field, its references per paper and its share:

$$
C=N_s\cdot r\cdot\frac{s}{1000}
$$

With it I separate the growth of a count into its three factors between any two years. Writing the odds ratio as in section 4.2, with $\omega=T/W$ the observed odds, gives for the two lines

$$
\mathrm{OR}_{\mathrm{teal}}=\omega_{\mathrm{teal}}\cdot\frac{N_{\mathrm{AI}}}{N_{\mathrm{neuro}}},\qquad \mathrm{OR}_{\mathrm{gold}}=\omega_{\mathrm{gold}}\cdot\frac{N_{\mathrm{neuro}}}{N_{\mathrm{AI}}},\qquad \frac{\mathrm{OR}_{\mathrm{teal}}}{\mathrm{OR}_{\mathrm{gold}}}=\frac{\omega_{\mathrm{teal}}}{\omega_{\mathrm{gold}}}\left(\frac{N_{\mathrm{AI}}}{N_{\mathrm{neuro}}}\right)^2
$$

so the teal odds ratio exceeds the gold one exactly when the ratio of observed odds exceeds the squared ratio of neuroscience to AI papers. Because the size ratio enters squared, the field-size correction can reverse the order of two raw lines.

### 7.3 Decomposition of a change

For one line between years $y_0$ and $y_1$, with $F=N_s/N_t$ the field-size factor, the log change of the odds ratio splits exactly into a share term and a size term (`figures.figure_s3_dilution.table`):

$$
\ln\frac{\mathrm{OR}_{y_1}}{\mathrm{OR}_{y_0}}=\ln\frac{\omega_{y_1}}{\omega_{y_0}}+\ln\frac{F_{y_1}}{F_{y_0}}
$$

Each term divided by the left-hand side is its fraction of the change. I fixed the years at $y_0=2020$, the start of the last era, and $y_1=2023$, the last fitted year, and tried no other pair. Holding sizes at their 2020 values, $\omega_{2023}F_{2020}$, shows what the odds ratio would have done without the change in field sizes. Figure S3.1 draws $\mathrm{OR}$, $\omega$ and $F$ each indexed to 2020 = 100 for 2015 to 2025 (`results/flow/figure_s3_dilution_data.csv`).

### 7.4 Where the share lines cross

With $D_y=s_{\mathrm{gold},y}-s_{\mathrm{teal},y}$, let $y_a$ be the last year with $D_y\lt 0$ and $y_b$ the next year (from which $D_y\gt 0$ through 2025). I place the crossing by linear interpolation (`flow_numbers.share_crossing`):

$$
y^{\ast}=y_a+(y_b-y_a)\frac{-D_{y_a}}{D_{y_b}-D_{y_a}}
$$

once on the yearly values and once on the centered 5-year means.

## 8. Bridge works

### 8.1 The bridge score

For each cited work $p$, $c_N(p)$ and $c_A(p)$ are the numbers of citing works labeled neuroscience and AI (extended definition) that cite it, over all citing years; citations from third-field or unknown papers are ignored (`audits.q4_v3_extended.build_bridge_table`). Their harmonic mean is the bridge score (`materialize_full`):

$$
B(p)=\frac{2 c_N(p) c_A(p)}{c_N(p)+c_A(p)}
$$

It satisfies $\min(c_N,c_A)\le B\le 2\min(c_N,c_A)$, so a paper cannot score well on one field's attention alone: a paper cited 1,000 times by AI and twice by neuroscience scores 3.99, one cited 100 times by each scores 100. I compute B on raw counts, so its unit is citations and it is not corrected for the sizes of the two fields. A ubiquity-normalized variant, $B(p)/\ln(1+c_N+c_A)$, exists in the code (`variant_normalised_top`) as a diagnostic; no published number uses it. Bar color in Figure 3 is the neuroscience share $c_N/(c_N+c_A)$, from teal at 0 (cited almost only by AI papers) through beige at 0.5 to gold at 1 (cited almost only by neuroscience papers).

### 8.2 Gate and eligibility

| Step | Rule | Papers |
|-|-|-:|
| gate | $c_N\ge 5$ and $c_A\ge 5$, and the cited work has a record in the index published 1990 to 2026 | 133,763 |
| own label | the cited work is itself labeled neuroscience or AI (drops 74,485 third-field and 240 unknown) | 59,038 |
| ceiling (`E2` in the code) | $c_N+c_A\lt 10{,}000$ (drops 66 AI and 1 neuroscience paper) | 58,971 |

Together the last two steps define the eligible papers (`analysis.export_bridge_tables.eligible_pool`; funnel in `results/bridge/eligibility_funnel.csv`). Among others, the own-label rule removes a block of plasma-physics papers from the Large Helical Device fusion experiment that collect thousands of citations from papers labeled neuroscience and AI; it also removes some wanted work labeled third field, such as the R language and the U-Net network. Nor can the gate affect the top of the ranking: since $B\le 2\min(c_N,c_A)$, any paper with $B\gt 1{,}396$ (the fifteenth paper of Table S5.1) has more than 698 citations from each field. Both thresholds, 5 and 10,000, are fixed; I did not vary them.

### 8.3 The top-15 list and its coding

For Table S5.1 and the papers column of Figure 3 I take the 40 eligible papers with the highest B, apply display filters in this order, and keep the first 15 (`export_bridge_tables.build_s1`, which stops if the result differs from the figure's input): OpenAlex type article or review; source type not "ebook platform" or "book series"; a non-empty title; a title not starting with one of three book titles listed in `audits/filter_by_era_books_only.py` ("Reinforcement learning: an introduction", "Pattern classification", the NeurIPS proceedings volumes); and, among records with the same normalized title, the one with the highest B. Of the 40 candidates, 7 are removed (5 books, 1 book chapter, 1 listed title; `results/bridge/s1_eligibility_check.csv`).

I coded each of the 15 papers by hand as a tool (software, a benchmark, an analysis method or a methods survey that both fields cite because they run it) or a concept (a claim about brains or minds), by what the paper offers a reader (`export_bridge_tables.PAPER_CLASS`, column `paper_class`).

### 8.4 Authors and institutions

An author's bridge weight is the sum of B over the papers on which the author appears; an institution's is the sum over the papers with at least one authorship affiliated to it (`audits/author_inst_bridge.py`):

$$
\Sigma B(e)=\sum_{p\in P:\ e\in E(p)}B(p)
$$

where $P$ is a set of bridge papers and $E(p)$ the distinct authors or institutions of $p$. Each paper counts once and in full for every author and every institution on it; I do not divide credit, and a paper with several authors at one institution counts once for it. For the columns of Figure 3, $P$ is the 5,000 eligible papers with the highest B, authors need at least 2 papers in $P$ and institutions at least 5, and the persisted tables keep the top 200 authors and top 100 institutions with paper counts, mean and maximum B and the summed $c_N$ and $c_A$. The color of an author or institution is $\sum c_N/\sum(c_N+c_A)$ over its papers in $P$. Author identity is OpenAlex's `author_id`, institution identity the `institution_id` printed in each paper's authorships, so a researcher who moved is credited where the paper was written; the OpenAlex field `last_known_institutions` is used nowhere. In the drawing, an author bar has the length $\Sigma B/\max\Sigma B$ of the longest author bar but never less than 55 percent of it (`figure2_bridges_v3`), so that names fit inside; the bars of ranks 11 to 15 sit at that minimum and do not show their values. Beside each institution bar, a badge gives its OpenAlex type (EDU education, IND industry (OpenAlex type company), FAC facility, GOV government, HC healthcare, NP nonprofit).

### 8.5 Corporate consolidation

OpenAlex lists sub-entities of one company as separate institutions. For the main figure I merge into a parent the sub-entities of the top-100 institution table whose names match a pattern (`audits.institution_consolidation.PARENT_GROUPS`):

| Parent | Pattern on the institution name | Identifier |
|-|-|-|
| Alphabet (Google + DeepMind) | `^Google`, `DeepMind`, `^Alphabet` | `ALPHABET_GROUP` |
| Microsoft | `^Microsoft` | `MICROSOFT_GROUP` |
| Meta (Facebook) | `^Meta`, `^Facebook` | `META_GROUP` |

For each parent, every paper among the 133,763 bridge papers with at least one authorship at any of its sub-entities contributes its B once, and the sub-entity rows are replaced by the parent row. The institutions column of Figure 3 therefore mixes two bases: company rows are summed over all 133,763 papers that pass the gate, including third-field papers and papers above the ceiling, and university and other rows over the top 5,000 eligible papers. I do not merge subsidiaries without the group name (LinkedIn, GitHub, Waymo, Verily), and I keep the unconsolidated ranking as a separate figure and in `results/bridge/table_s3b_institutions_separated.csv`.

### 8.6 Author-to-institution lines and affiliation verification

The lines between authors and institutions in Figure 3 do not come from OpenAlex, whose author-level affiliations produced name collisions and co-authorship artifacts. I verified every line by hand against sources in a fixed order of priority: ORCID employment records; official university, laboratory or institute pages; Google Scholar verified affiliations; the researcher's homepage or CV; LinkedIn, for industry roles and dates; Wikipedia only as a cross-check. Each drawn line rests on at least one authoritative source, with roles and dates recorded per line. I applied four rules to everyone alike:

1. Only research affiliations count (PhD, postdoc, faculty, director, visiting researcher, industry research); taught degrees and non-research clinical training do not.
2. Only the 15 institutions shown can be linked, so some current employers are absent by design.
3. An institution is linked to an author only through a verified appointment; the Howard Hughes Medical Institute has none for any of the 15 authors and therefore no line.
4. Genuine dual current affiliations are drawn as two current lines.

Solid lines are current affiliations, faded lines past ones. Altogether this gives 26 lines, 10 current and 16 past (`audits/affiliations_overrides.py`, `results/bridge/author_institution_edges.csv`). I computed the lines between papers and authors from the OpenAlex authorship lists of the 15 papers (`export_bridge_tables.build_links`; 8 lines in `paper_author_links.csv`), and their thickness encodes authorship position with weights 2.0 (last), 1.5 (first) and 1.0 (middle); this affects the drawing only. Institution rank comes from paper affiliations, not from where the 15 authors work, so an institution can rank without any author line.

### 8.7 Concentration

The share of total bridge weight held by the top $N$ entities of a pool, with entities ranked by $\Sigma B$, is (`export_bridge_tables._tiers`)

$$
S_N=100\cdot\frac{\sum_{r=1}^{N}\Sigma B_{(r)}}{\sum_{e\in\mathcal{E}}\Sigma B(e)}
$$

where $\mathcal{E}$ is every author with at least 2 papers, or every institution with at least 5 papers, in the pool. Here I do not consolidate institutions. Tiers are $N$ = 1, 5, 10, 15, 25, 50, 100, 250, 500 and 1,000 (`results/bridge/concentration_tiers.csv`). I compute four pools:

| Pool | Papers summed over | Numerator table |
|-|-|-|
| all bridge papers | the 133,763 papers that pass the gate | top 1,000 entities (`audits/author_inst_top1000.py`) |
| sensitivity bound (the article's values) | the same, after dropping every entity of the top-1,000 tables whose mean B per paper exceeds 400 and subtracting its weight from the denominator (298 authors, 17 institutions dropped) | the remaining top-1,000 entities |
| own label | the 59,038 papers labeled neuroscience or AI | full distribution (`scripts/concentration_filtered.py`) |
| eligible | the 58,971 eligible papers | full distribution |

Why a bound? The gate pool contains the fusion-physics block of section 8.2, whose authors and institute have very high B per paper; the threshold 400 is `ADJUST_MEAN_B`. To summarize inequality I use the Gini coefficient of the sorted weights $v_{(1)}\le\dots\le v_{(n)}$ (`export_bridge_tables.gini`):

$$
G=\frac{2\sum_{i=1}^{n} i v_{(i)}-(n+1)\sum_{i=1}^{n}v_{(i)}}{n\sum_{i=1}^{n}v_{(i)}}
$$

### 8.8 The wider bridge set

Era composition of the eligible pool counts papers by publication year in the bins before 2012, 2012 to 2015, 2016 to 2019 and 2020 onward, for the top 100, the top 1,000 and the whole pool ranked by B, before display filters (`analysis.export_bridge_pool`, `results/bridge/era_composition.csv`). A separate classification covers the top 1,000 papers of the unfiltered gate pool. I clustered them with the Leiden algorithm (modularity partition, seed 42) on a bibliographic-coupling graph, two papers being linked when they share at least 3 references, reduced to its backbone by a disparity filter at $\alpha=0.20$ (`DISPARITY_ALPHA` in `audits/clustering_pipeline.py`, loosened from 0.05). Each paper went to one of ten tracks by rules I wrote by hand: title patterns first (`audits/q4_classify.py`), then a mapping of OpenAlex subfields onto tracks for the papers the patterns leave unassigned (`audits/q4_reclassify_v2.py`). That step also drops 140 papers in nuclear and high-energy physics subfields, leaving 860, and a paper type (research, methods, review) comes from title patterns. This set keeps third-field papers and papers above the ceiling, so it is not the eligible pool; `results/bridge/clustered_set_composition.csv` recounts its labels. The persisted backbone holds 800 edges, 665 of them with a significance value of 0.05 or more and none of 0.20 or more, so the run used 0.20; the track, paper-type and era counts follow from the top 1,000 papers by B and the hand rules, not from the clusters, so they do not depend on $\alpha$.

### 8.9 Validation anchors

Before the analysis I named four NeuroAI papers as validation anchors expected in the top 50 of the bridge ranking (`utils.duckdb.TIER1_DOIS`): Zador et al. 2023, Richards et al. 2019, Hassabis et al. 2017 and Kriegeskorte and Douglas 2018. All four are in the snapshot. None is in the top 100 of the published ranking (`results/citation_age/ranking_orig_top100.csv`); Hassabis 2017 and Richards 2019 enter the top 100 under some of the age controls of section 10.

## 9. What AI cites in neuroscience

### 9.1 Citing and cited sets

Here I look inside the two flows of Figure 1 (`analysis/cited_vintage/`, constants in `definitions.py`, fixed before the queries were run). I label citing papers by the extended definition or, where stated, the 35-topic core; their year is the publication year, over 1995 to 2025, in the periods 2010 to 2019, 2020 to 2025 and 2020 to 2023. My primary analysis uses every OpenAlex work type, and the sensitivity analysis articles and reviews only. On the cited side there are two sets: the all-neuroscience set (`unrestricted` in the data files), every work whose primary topic is in field 28 (what Figure 1 counts), and the exclusive set, which further drops any work with an AI topic of the extended definition among its listed OpenAlex topics (at most three). The exclusive set is the primary specification for the headline numbers; it removes AI papers that OpenAlex files under neuroscience when a secondary topic gives them away. Counts are citation edges, one per citing paper and cited work. Cited works published before 1990 are not in the index, so every age statistic loses its oldest tail.

### 9.2 Subfield shares and categories of AI

For the teal flow, the share of a neuroscience subfield $g$ in a period is the fraction of citation edges that land in it:

$$
\pi_g=\frac{\sum_{e}\mathbf{1}\left[\mathrm{subfield}(e)=g\right]}{\sum_{e}1}
$$

over the edges $e$ that citing AI papers of the period send to the cited set. "Cognitive neuroscience" is subfield 2805 and "cellular and molecular" subfield 2804 (`COGNITIVE_SUBFIELD`, `CELLULAR_SUBFIELD`). The article's shares use citing AI papers under the 35-topic core, the exclusive cited set, every work type and 2020 to 2025; the file gives every other combination (`results/vintage/subfield_breakdown.csv`), including the share of distinct cited works. For the gold flow, I assigned by hand each of the 87 AI topics cited by neuroscience under the extended definition to one of six categories (foundational deep learning and AI; neuroimaging and medical image processing; general statistics and machine-learning software; computer-vision applications; brain-adjacent modeling; off-topic or misclassified), printed topic by topic in `results/flow/flow_composition_topic_year.csv` and computed under both AI definitions (counts by `audits/flow_composition.py`, categories from `CATEGORIES` in `figures/flow_composition_fig.py`, export by `analysis.export_flow_composition`).

### 9.3 Age of the cited work

The age of an edge is $a=y_{\mathrm{citing}}-y_{\mathrm{cited}}$. Per period and set I compute the median cited year (the mean of the two middle order statistics), the share of edges to work published in 2005 or earlier and in 2004 or earlier, and the mean age (`vintage.stats_from_counts`). I keep in these calendar statistics the edges to work dated after the citing paper, an OpenAlex dating error of about 1 percent. Because the index starts in 1990, a paper of 2010 can reach back at most 20 years and one of 2025 35 years, so I also compute the age profile inside a common window, $0\le a\le 20$, which every citing year from 2010 sees in full (`analysis.s4_numbers.age_window`): the median age is the smallest $a$ at which the cumulative share reaches 0.5, and the share aged 5 years or less is reported beside it. I added this window after seeing the calendar results.

### 9.4 The declared removal check

Declared before running: remove from the cited side every work whose title matches `definitions.AI_TITLE_REGEX` (deep learning, reinforcement learning, neural network, transformer, support vector and about forty other patterns), then the clear AI papers among the 25 most-cited surviving works of each period, then the borderline ones (`robustness.py`; every removed work in `results/vintage/removed_works.csv`). Failure means that, in either period, the cognitive share moves by more than 2 percentage points, the median cited year by more than 1 year, or the share published in 2005 or earlier by more than 2 percentage points.

### 9.5 The six NeuroAI papers

I resolved the six NeuroAI papers of the article's sidebar by DOI and labeled them with the same classifier (code and result names say `manifesto`: `analysis/manifesto_citations.py`, `results/manifestos/`). For each citing year I count their citations by citing field, their share of the citations of neuroscience by AI papers, and the teal odds ratio recomputed with the six removed as cited works. To compare curves I use year-over-year changes, $\Delta_y=\ln(1+x_y)-\ln(1+x_{y-1})$ for counts and $\ln\mathrm{OR}_y-\ln\mathrm{OR}_{y-1}$ for the odds ratio, over the nine changes from 2014 to 2015 through 2022 to 2023, and the Spearman rank correlation between them with an exact two-sided p-value from all $9!$ orderings (`_exact_spearman`): the fraction of permutations whose absolute correlation is at least the observed one.

### 9.6 Reference age

For the short-memory comparison I take every reference of every AI and neuroscience paper that resolves to a dated work in the index, not only cross-field references (`reference_age.py`). My primary comparison uses OpenAlex types article and review, citing years 2020 to 2023; I drop and count references with a negative age. Statistics are the median (mean of the two middle order statistics), the mean, the 90th percentile (the smallest age $a$ with at least $\lceil 0.9N\rceil$ of the $N$ references at age $a$ or less) and the shares aged 5 and 10 years or less, with reference-list coverage by year in `results/vintage/reference_list_coverage.csv`.

## 10. Citation-age controls

### 10.1 What changes

My controls change the score and nothing else (`analysis.citation_age.rankings`). The candidate pool (the 133,763 bridge papers), the labels, the eligibility rules of section 8.2 and the display filters of section 8.3 are applied identically to every ranking, with the ceiling defined on all-time counts. For a paper published in year $y_p$, with per-year citation counts $n_f(y)$ from field $f$, every control replaces $c_N$ and $c_A$ in the harmonic mean by an age-controlled pair $(a_N,a_A)$:

$$
H(a_N,a_A)=\frac{2 a_N a_A}{a_N+a_A}
$$

Windows start in the year before publication, $y_p-1$, so that online-first versions are not penalized. Citations dated earlier come from reprints and merged records, and I exclude them. Every window stops at citing year 2023. And the published ranking, by contrast, counts all citing years.

| Ranking | $a_f$ | Works admitted |
|-|-|-|
| published (`orig`) | $c_f$, all citing years | 1990 to 2026 |
| published, restricted (`orig_1990_2015`) | $c_f$ | 1990 to 2015 |
| citations per year (`rate`) | $\sum_{y=y_p-1}^{2023} n_f(y) / (2023-y_p+1)$ | up to 2023 |
| 8-year window (`win8`) | $\sum_{y=y_p-1}^{y_p+8}n_f(y)$ | 1990 to 2015 |
| 7-year window (`win7`) | $\sum_{y=y_p-1}^{y_p+7}n_f(y)$ | 1990 to 2015 |
| 5-year window (`win5_to2018`) | $\sum_{y=y_p-1}^{y_p+5}n_f(y)$ | 1990 to 2018 |
| growth-normalized (`rate_share`, `win8_share`) | as `rate` and `win8` with each $n_f(y)$ replaced by $10^6 n_f(y)/R_f(y)$ | as `rate` and `win8` |

Here $R_f(y)$ is the number of references made by papers of field $f$ in year $y$ (`citation_age/citing_volume.py`, `results/citation_age/citing_volume.csv`), so a citation counts as the share of its field's references that year. Four guard variants complete my set: `rate` and `win8` without the ceiling (`rate_noceil`, `win8_noceil`), `rate` with papers labeled unknown admitted (`rate_unknown`), and the 1996-onward re-rank. The last takes the growth-normalized 8-year ranking (`win8_share`), drops the works whose first publication year is before 1996 (years in which the indexed citing literature was small and early citations carry the largest weights), keeps the order of the rest and numbers them from 1 (`tables_and_figure`, `summary.json` key `win8_share_from_1996`); the committed top-100 file holds 49 such works, so ranks 1 to 49 can be read from it. Where several records share a normalized title I keep the highest-scoring one, as in section 8.3.

### 10.2 Checks built into the code

Per-year counts of every candidate must sum to its published $c_N$ and $c_A$; the top 15 of `orig` must reproduce Table S5.1 work by work and match the figure's input (`results/citation_age/table_s1_reference.csv`); and the gate cannot hide a top-100 work under the count-based controls, because a work outside the pool has at most 4 citations from one field in every window (and a rate of at most 4), so its harmonic mean is at most 8, below the 100th score of each of those rankings. Results of these checks are in `results/citation_age/checks.json`, and `python -m neuroai_cn.analysis.citation_age.verify` recomputes the headline numbers from the committed top-100 files.

### 10.3 Classes of ranked works

To ask which ranked works are conceptual, I coded by hand every work in the heads of the 11 rankings (271 works) into five classes (`results/citation_age/classification.csv`): concept, a claim about brains or minds, including cognitive science; method, a new machine-learning model, algorithm or architecture, or a review of such methods; tool, as in section 8.3; book, a textbook or handbook typed as an article; and artifact (`artefact` in the file), a merged or generic record or a whole proceedings volume. Applied to the top 15 this reproduces the 8 concepts and 7 tools of section 8.3. For recency I use the first publication year, which differs from OpenAlex's year for 24 of the 271 works (mostly reprints). I note borderline calls in the file. Recoding all of them as non-concepts is a declared sensitivity check.

## 11. Statistical conventions and reproducibility

### 11.1 Conventions

| Quantity | Interval or test | Seed |
|-|-|-|
| yearly odds ratio | Wilson 95 percent, $z=1.96$, no continuity correction (section 4.4) | none |
| era and segment slopes | bootstrap over years, $B=500$, percentile 95 and 99 percent (section 5.4); t interval and two-sided t-test with $n-2$ degrees of freedom (section 5.2) | 20260528 |
| cross-source shares | cluster bootstrap over papers, 500 replicates, 95 percent (section 6.1) | OpenAlex sample and bootstrap: 7; Semantic Scholar shuffle and bootstrap: the citing year |
| curve comparison | Spearman correlation, exact permutation p-value (section 9.5) | none |
| clustering | Leiden, modularity partition (section 8.8) | 42 |

Significance marks in Figure 1 are `**` (99 percent interval excludes zero), `*` (95 percent) and `n.s.` (neither), from the bootstrap. Every slope, interval and change point uses 1995 to 2023; the provisional years 2024 and 2025 are shown and never fitted. Breakpoint years are the first year of the new segment. Numbers in the documents are rounded from the committed files.

### 11.2 Reproducibility

In the repository I ship the code, the small result tables under `results/` and the figures. But the snapshot (about 364 GB of parquet and a 494 GB DuckDB index) cannot be redistributed. Paths to it come from `src/neuroai_cn/config.py` and the `NEUROAI_DATA` environment variable.

- `reproduce.sh`: `setup` (environment from the lock file), `check` (lint and the tests that need no large data), `figures` (every figure from `results/`), `numbers` (the claims test and `citation_age.verify`) and `all` run from the committed files; `heavy` prints the pipeline that rebuilds `results/` from the snapshot, stage by stage.
- Tests under `tests/` recompute the flow numbers, the change points, the bridge tables, the vintage and six-NeuroAI-paper tables and the module imports from the committed files, and check that no tracked code contains machine-specific paths. Tests marked `heavy` read the DuckDB index and run only with `NEUROAI_HEAVY=1`.
- Claims files: every headline number of a supplement is listed in `docs/supplements/claims/S<n>.yaml` with the fields `id`, `file`, `context` (a sentence that must occur verbatim in the supplement), `shown` (the number as printed, inside the context) and `expr` (a Python expression that recomputes it from `results/`). `tests/test_supplement_claims.py` fails if the sentence is gone, if the printed number is not in it, or if the recomputed value rounds to anything else.
- Every committed table is written by a named module (`analysis.export_*`, `analysis.changepoints`, `analysis.citation_age.*`, `analysis.cited_vintage.*`), so a reader with the snapshot can regenerate it, and a reader without it can recompute every derived number from the tables alone.

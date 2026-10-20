# Corpus and pools

This file covers the data source (a single frozen OpenAlex snapshot), and the four pools that define the working corpus, with every anchor publication, institution, Boolean template, venue and seed author enumerated in full. I also cover how the pools combine and what their overlap looks like. It does not cover how a paper is assigned to neuroscience or to AI; that is [field classification](02-field-classification.md). The pools are the corpus as I designed it before the data were seen. They are not what the published numbers are computed on: the odds ratios in [the citation metric](03-citation-metric.md) and the bridge ranking in [the bridge metric](05-bridge-metric.md) both count citations over the whole snapshot, and no published number reads the pool files ([S1, section 3.6](../supplements/S1-data-and-classification.md)).

## 1. The snapshot

I run everything except the cross-source samples against one OpenAlex snapshot, which I downloaded on **30 March 2026** and hold locally as year-partitioned parquet with a DuckDB index over it, so that every number can be regenerated from a fixed corpus. The pipeline's own manifest records the values below; I also committed the first five rows in [`results/corpus/corpus_totals.csv`](../../results/corpus/corpus_totals.csv) and I discuss them in [S1, section 2.1](../supplements/S1-data-and-classification.md).

| Quantity | Value |
|-|-:|
| Works total | 398,288,606 |
| Citation edges | 2,893,128,636 |
| Works carrying a `primary_topic` | 311,299,063 |
| Works carrying a non-empty `referenced_works` list | 111,676,520 |
| Distinct citing works | 111,676,520 |
| Authors | 113,641,286 |
| Sources (venues) | 280,687 |
| Institutions | 121,512 |
| Topics | 4,516 |
| On-disk DuckDB size | 493.6 GB |

The citing population is 111,676,520 rather than the corpus total, because OpenAlex holds a reference list for only about 28% of indexed works. That coverage gap is uneven by publisher, era and field, and it is a limitation I cannot bound from inside the dataset.

One clarification about corpus size, because two figures circulate and both are real. The parquet holds **458,112,708** distinct work identifiers across all 381 partitions and all publication years. The DuckDB index built over it is restricted to publication years 1990 to 2026, and holds **398,288,606** works; this is the manifest's `works_total` and the corpus every number in this analysis is computed against. The gap of roughly 59.8 million is pre-1990 and undated material outside the analysis window. They are different quantities, and either may be quoted provided its scope is stated. The article quotes the larger one ("roughly 458 million works"); every analysis of mine uses the smaller. The edge count is 2,893,128,636.

The snapshot's `coverage_fraction_estimate` of 1.593 in the manifest is an artifact of a hard-coded 250-million-work denominator that predates OpenAlex's November 2025 platform rewrite. It is a diagnostic field, not a claim, and I use it nowhere downstream.

## 2. How the pools combine

A work enters the corpus if it satisfies **any** pool. I **union the pools and then deduplicate** by OpenAlex `work_id`. I do **not** nest them and there is no citation-expansion step.

I **report pool overlap and do not collapse it**, because where NeuroAI work shows up across pools is itself evidence about the field.

| Pool | Definition in one line | Works |
|-|-|-:|
| Pool 1 | Self-proclaimed NeuroAI: anchor signatories and named-program faculty | 1,508,502 |
| Pool 2 | Thematic keywords: five Boolean templates over titles | 37,608 |
| Pool 3 | Venue whitelist: four curated sub-pools | 661,977 |
| Pool 4 | Seed authors: six lineage sub-rosters | 23,208 |
| **Sum before deduplication** | | **2,231,295** |
| **Unique works after deduplication** | | **2,153,057** |

Pairwise and higher-order intersections, derived from the exact overlap partition in [`results/corpus/pool_sizes.csv`](../../results/corpus/pool_sizes.csv) (the partition sums to the 2,153,057 unique works):

| Intersection | Works |
|-|-:|
| Pool 1 ∩ Pool 2 | 1,858 |
| Pool 1 ∩ Pool 3 | 61,193 |
| Pool 1 ∩ Pool 4 | 12,681 |
| Pool 2 ∩ Pool 3 | 1,604 |
| Pool 2 ∩ Pool 4 | 322 |
| Pool 3 ∩ Pool 4 | 3,477 |
| Pool 1 ∩ Pool 2 ∩ Pool 3 | 356 |
| Pool 1 ∩ Pool 2 ∩ Pool 4 | 200 |
| Pool 1 ∩ Pool 3 ∩ Pool 4 | 2,314 |
| Pool 2 ∩ Pool 3 ∩ Pool 4 | 91 |
| All four | 64 |

Works exclusive to a single pool: 1,435,576 (Pool 1), 598,400 (Pool 3), 34,407 (Pool 2), 9,269 (Pool 4). I find the overlap small relative to the pools: the self-proclaimed brand and the venue whitelist are largely disjoint populations, and the curated seed-author roster barely intersects either.

I restricted every pool to `publication_year` between 1990 and 2026 at build time.

## 3. Pool 1: self-proclaimed NeuroAI (1,508,502 works)

A work enters Pool 1 if any of its authors is a signatory on one of five anchor publications (Pool 1a), or was affiliated with a named NeuroAI program during the brand-era window 2019–2026 (Pool 1b). In practice Pool 1 is its institutional half: 1,500,926 of its 1,508,502 works come in only through the institutes, 1,673 only through the anchor signatories and 5,903 through both ([`results/corpus/pool_sizes.csv`](../../results/corpus/pool_sizes.csv)), so I read it as closer to the collected output of those institutes than to self-declared NeuroAI.

### 3.1 The five anchor publications

| Publication | Identifier |
|-|-|
| Zador et al. 2023, *Nature Communications* 14:1597, "Catalyzing next-generation Artificial Intelligence through NeuroAI" (27 signatories) | [10.1038/s41467-023-37180-x](https://doi.org/10.1038/s41467-023-37180-x) |
| Zador et al. 2022, arXiv preprint (precursor to the above) | [10.48550/arXiv.2210.08340](https://doi.org/10.48550/arXiv.2210.08340) |
| Luppi, Achterberg et al. 2024, *Nature Communications* 15:9152 (the trainee response) | [10.1038/s41467-024-53375-2](https://doi.org/10.1038/s41467-024-53375-2) |
| Mineault et al. 2024, *NeuroAI for AI Safety* (15 signatories) | [10.48550/arXiv.2411.18526](https://doi.org/10.48550/arXiv.2411.18526) |
| Hassabis et al. 2017, *Neuron*, "Neuroscience-Inspired Artificial Intelligence" (the precursor manifesto, term: "neuroscience-inspired AI") | [10.1016/j.neuron.2017.06.011](https://doi.org/10.1016/j.neuron.2017.06.011) |

Every author on any of these five papers is a Pool 1a author. The DOIs are hard-coded as `ANCHOR_DOIS` in `src/neuroai_cn/corpus/pool1.py`.

### 3.2 The named institutional carriers

The foundation document names these institutional carriers of the NeuroAI label, and refers to them collectively as "35 institutions". That headline number is a nominal label rather than a count: I count 42 entries in the roster as written, one of which (the CAJAL NeuroAI Course at Champalimaud) appears twice, giving 41 distinct carriers. I am naming all of them rather than repeating the round number.

**North America**

1. Kempner Institute for the Study of Natural and Artificial Intelligence, Harvard (founded on a $500M Chan Zuckerberg gift, 2021)
2. Flatiron Institute Center for Computational Neuroscience (Simons Foundation)
3. NSF AI Institute for Artificial and Natural Intelligence (ARNI), Columbia-led, 2023
4. Princeton NeuroAI track (2023)
5. Stanford NeuroAILab, with the Wu Tsai Neurosciences Institute
6. Cold Spring Harbor Laboratory NeuroAI Program
7. NYU Center for Neural Science
8. Columbia Zuckerman Institute
9. Mila (Quebec AI Institute)
10. MIT Brain and Cognitive Sciences, CBMM, and the Quest for Intelligence
11. Salk Institute Computational Neurobiology Laboratory (Sejnowski)
12. Allen Institute for Brain Science (researcher-level NeuroAI, via Arkhipov)

**Europe**

13. UCL NeuroAI domain, with its six annual conferences (2020–2025)
14. Sainsbury Wellcome Centre and the Gatsby Computational Neuroscience Unit, UCL
15. EPFL NeuroAI Lab (Schrimpf, from June 2023)
16. Max Planck Institute for Biological Cybernetics, Tübingen (Dayan as director from 2018)
17. Max Planck Institute for Intelligent Systems, Tübingen
18. Bernstein Centers for Computational Neuroscience (six centers, plus Bonn)
19. Champalimaud Foundation, CAJAL NeuroAI Course, Lisbon (2024 and 2025; directors Sinz, Isik, Toneva, Turaga; faculty including Tolias, Mineault, Krakauer, Schrimpf, Memming Park, Rui Ponte Costa)
20. Helsinki HiLIFE / Neuroscience Center
21. CAJAL Advanced Neuroscience Training Program

**Asia and Pacific**

22. RIKEN Center for Brain Science, Wako (Toyoizumi; Amari emeritus; Doya cross-affiliated)
23. Okinawa Institute of Science and Technology (Doya, Fukai)
24. ATR Computational Neuroscience Laboratories, Kyoto (Kawato, Kamitani)
25. Tsinghua CBICR and Institute for AI, Beijing
26. BrainCog Lab, Institute of Automation, Chinese Academy of Sciences, Beijing (Yi Zeng)
27. Peking University Institute for AI

**Industry, focused research organizations, and safety**

28. DeepMind Neuroscience team (Botvinick, Lillicrap)
29. Amaranth Foundation, New York (Mineault as NeuroAI Lead; $50M+; Fickel founder)
30. Forest Neurotech, Cambridge MA (ultrasound brain-computer interfaces)
31. E11 Bio, Bay Area (PRISM connectomics)
32. Basis, New York (Tavares)
33. Convergent Research, Cambridge MA (Marblestone)
34. Numenta and the Thousand Brains Project (2024)
35. Conjecture / CoEm, London (2022)
36. Astera Institute, Berkeley (Byrnes, brain-like AGI safety)
37. Anthropic (mechanistic-interpretability circuits program; neuroscience-PhD core: Bricken, Lindsey, Olsson)

**Training and education**

38. Neuromatch Academy NeuroAI Course (Pitkow, 2024)
39. SfN NeuroOnline NeuroAI training
40. Dartmouth NeuroAI Workshop 2024
41. NIH BRAIN NeuroAI Workshop 2024
42. NeurIPS NeuroAI Workshop (annual since 2024)

(Entry 19, the CAJAL NeuroAI Course at Champalimaud, is listed again under training and education in the source roster; I count it once.)

### 3.3 What the code actually queries, and why it is a shorter list

The roster above is the editorial definition. The implementation cannot use it directly, because most of those entities either have no OpenAlex institution ID at all (a course, a workshop, a track inside a department) or exist only as a whole-university ID that would drag in every unrelated paper from that university. I could not include "Stanford University" wholesale without making Pool 1 meaningless.

So I resolve Pool 1b against a curated list of **21 OpenAlex sub-institute IDs**, which I probed on 2026-04-29 and which are the entities from the roster that OpenAlex represents at the right granularity. I deliberately exclude whole-university IDs. This is a real narrowing relative to the prose roster, and anyone comparing the two should know it. The list, from `NEUROAI_SUB_INSTITUTE_IDS` in `src/neuroai_cn/corpus/pool1.py`:

| OpenAlex ID | Institution |
|-|-|
| I4387153999 | Flatiron Institute |
| I4210092532 | National Bernstein Network Computational Neuroscience |
| I4210152641 | Bernstein Center for Computational Neuroscience Berlin |
| I4210098324 | Bernstein Center for Computational Neuroscience Freiburg |
| I4210087171 | Bernstein Center for Computational Neuroscience Göttingen |
| I4210109659 | Bernstein Center for Computational Neuroscience Heidelberg-Mannheim |
| I4396570676 | Sainsbury Wellcome Centre |
| I4405252512 | Centro Champalimaud |
| I113358080 | Champalimaud Foundation |
| I4210164802 | Mila — Quebec AI Institute |
| I4210112925 | Max Planck Institute for Biological Cybernetics |
| I4210135521 | Max Planck Institute for Intelligent Systems |
| I1307098950 | Salk Institute |
| I1314596251 | Allen Institute for Brain Science |
| I2750212522 | Cold Spring Harbor Laboratory |
| I4210090411 | Google DeepMind (UK) |
| I4387930290 | Anthropic |
| I2800939219 | RIKEN Center for Brain Science |
| I4387153830 | Neuromatch |
| I4405261313 | Donders Institute for Brain, Cognition and Behavior |
| I4405259014 | Donders Center for Cognitive Neuroimaging |

I could not resolve Kempner, Wu Tsai and ARNI as distinct OpenAlex entities at probe time. The two Donders entries are not on the prose roster; I added them at implementation as the institutional home of van Gerven's NeuroAI overview work. An author qualifies for Pool 1b if any entry in their OpenAlex `affiliations` list matches one of these IDs with an associated year between 2019 and 2026 inclusive.

I fixed faculty rosters as of April 2026 and preserved multi-institutional affiliations rather than reducing them to a primary. Moves after that date are not captured; Tolias moving Baylor to Stanford in 2024 is captured, later moves are not.

## 4. Pool 2: thematic keywords (37,608 works)

Pool 2 is where the merger-versus-branding question is actually decided, because it catches papers doing brain-and-AI work whether or not their authors use the label. A work enters Pool 2 if **any one** of five Boolean templates fires against its title.

**Title-only matching is a hard limitation of this pool.** I dropped OpenAlex's `abstract_inverted_index` field from the parquet projection to keep the local index tractable, so any phrase that only appears in an abstract is missed. Recall is roughly 30–50% lower than a title-plus-abstract match would give. Pool 2 is small for this reason, and I do not read its size as a measurement of how much operational NeuroAI exists.

I do all matching case-insensitively by substring, built as alternation regexes. I wrote phrases with leading and trailing spaces (` CNN `, ` V1 `, ` RL `) that way deliberately, to force a crude token boundary and avoid matching inside longer words. The templates below are verbatim from `src/neuroai_cn/corpus/pool2.py`; the code is the only complete record of them and this is it.

### Template A: high-precision core

Fires if the title contains **any** of:

`predictive coding` · `free energy principle` · `active inference` · `feedback alignment` · `equilibrium propagation` · `target propagation` · `biologically plausible backpropagation` · `credit assignment in the brain` · `representational similarity analysis` · `Brain-Score` · `surrogate gradient` · `neuromorphic` · `successor representation` · `grid cell` · `place cell` · `canonical microcircuit` · `reward prediction error` · `meta-reinforcement learning` · `distributional reinforcement learning` · `thousand brains` · `HMAX` · `CORnet`

### Template B: cortex-model conjunction

Fires if the title contains at least one term from **each** of three groups.

*Network architecture:* `convolutional neural network` · ` CNN ` · ` CNNs ` · `deep neural network` · `transformer` · `recurrent neural network` · ` RNN ` · ` RNNs ` · `LSTM`

*Brain region:* `ventral stream` · ` V1 ` · ` V4 ` · `inferotemporal` · `IT cortex` · `auditory cortex` · `prefrontal cortex` · `hippocampus` · `striatum` · `cerebellum` · `motor cortex` · `parietal cortex` · `entorhinal cortex` · `brain region` · `cortical area`

*Modeling or measurement verb:* `model` · `prediction` · `encoding` · `representation` · `similarity` · `alignment` · `neural response` · `fMRI` · `ECoG` · ` MEG ` · `electrophysiology` · `single-unit`

### Template C: plausible learning and plasticity

Fires if the title contains at least one term from **each** of two groups.

*Biological-plausibility marker:* `biologically plausible` · `bio-plausible` · `biologically motivated` · `three-factor learning` · `local learning rule` · `Hebbian` · `STDP` · `spike-timing-dependent` · `weight transport` · `credit assignment` · `backpropagation alternative`

*Network or learning substrate:* `deep learning` · `neural network` · `gradient` · `backpropagation` · `spiking neural network` · ` SNN ` · `recurrent network`

### Template D: language models and brain

Fires if the title contains at least one term from **each** of two groups.

*Language model:* `large language model` · ` LLM ` · ` LLMs ` · `transformer` · ` GPT` · ` BERT` · `language model` · `self-supervised language`

*Brain measurement or region:* `fMRI` · `ECoG` · ` MEG ` · `brain activity` · `neural response` · `cortex` · `Broca` · `language network` · `temporal cortex` · `encoding model` · `psycholinguistic`

### Template E: cognitive maps and RL-neuroscience

Fires if the title contains at least one term from **each** of two groups.

*Neuroscience term:* `successor representation` · `hippocampus` · `entorhinal` · `grid cell` · `place cell` · `Tolman-Eichenbaum` · `cognitive map`

*RL or modeling term:* `reinforcement learning` · ` RL ` · `deep RL` · ` RNN ` · `world model` · `planning` · `latent dynamics` · `model-based` · `neural network`

### Exclusion traps

The foundation document specifies ten false-positive traps, T1 to T10. Seven of them are abstract-dependent and therefore unenforceable against a title-only index, so I document them but do not apply them. Three are title-tractable, and I implemented those as a boolean `excluded` flag on each Pool 2 row rather than as a hard filter, so downstream code can choose strict or permissive behavior.

**T1: generic "neural network".** Fires when the title contains `neural network` but **no** neuroscience token from: `brain` · `cortex` · `neuron` · `neural circuit` · `cortical` · `hippocampus` · `cerebellum` · `striatum` · `synaptic` · `dendritic` · `neurophysiology` · `electrophysiology` · `fMRI` · `MEG` · `spike` · `single-unit`.

**T2: medical deep learning without architectural novelty.** Fires when the title contains any of `deep learning for diagnosis` · `deep learning for segmentation` · `deep learning for classification of seizure` · `Alzheimer's detection` · `tumour segmentation` · `tumor segmentation` · `lesion segmentation` · `white matter segmentation` · `MRI artefact` · `MRI artifact`, **unless** rescued by any of `model of cortex` · `neural representation` · `brain-like` · `mechanistic` · `encoding model` · `ANN-brain alignment` · `brain alignment`.

**T6: biological-metaphor optimization.** Fires when the title contains any of `ant colony` · `genetic algorithm` · `particle swarm` · `firefly algorithm` · `bee algorithm` · `grey wolf optimizer` · `immune system algorithm`, **unless** rescued by a T1 neuroscience token.

Per decision A3, I removed memristor and optical implementations from the T6 false-positive list: they are real neuromorphic hardware, not a metaphor, and they are inside the field the analysis is about.

## 5. Pool 3: venue whitelist (661,977 works)

A work enters Pool 3 if its `primary_location.source` is on a curated venue list. There are four sub-pools plus a separate conference list. Per decision A4 I renamed the third sub-pool from "ambiguous" to "mixed/intersection" and added a fourth general-high-impact sub-pool with *Science*, *Nature* and PNAS named explicitly.

There are **two** venue lists in this repository and they are not identical, so I am giving both. `src/neuroai_cn/corpus/pool3.py` holds the list used to *build the corpus*, expressed as resolved OpenAlex source IDs; several intended venues did not resolve at probe time and are marked in the source as unresolved. `src/neuroai_cn/audits/scheme2_venues.py` holds the list used for the *venue-based field-assignment scheme*, expressed as display-name strings, which is closer to the foundation document's editorial list. Where they differ, neither is wrong, because they answer different questions, but I would not want a reader comparing them to be surprised.

### 5.1 The editorial venue lists

**Core neuroscience.** *Neuron* · *Nature Neuroscience* · *Journal of Neuroscience* · *Nature Reviews Neuroscience* · *Current Opinion in Neurobiology* · *eLife* (neuroscience section) · *Journal of Computational Neuroscience* · *Cerebral Cortex* · *NeuroImage* · *Brain* · *Trends in Neurosciences* · *Annual Review of Neuroscience* · *Journal of Neurophysiology* · *Journal of Physiology* · *Journal of Neuroscience Methods* · *eNeuro* · *Network Neuroscience* · *Brain Structure and Function* · *Hippocampus* · *Neuroreport* · *Cell Reports* (neuroscience section) · *Cell*

**Core AI.** NeurIPS · ICML · ICLR · JMLR · AAAI · IJCAI · AISTATS · COLT · TMLR · CVPR / ICCV / ECCV · EMNLP / ACL · *Nature Machine Intelligence* · ACL Findings · NAACL · EACL · AAMAS · IROS · ICRA · KDD · WSDM · RecSys · UAI · RLC (inaugural, August 2024, UMass) · ICAPS

**Mixed / intersection.** *Neural Computation* (1989, MIT Press) · *Biological Cybernetics* (founded 1961 as *Kybernetik*) · *PLoS Computational Biology* · *Frontiers in Computational Neuroscience* · *Frontiers in Neuroscience* · *Frontiers in Neurorobotics* · *Cognitive Computation* · *IEEE Transactions on Neural Networks and Learning Systems* · *Neural Networks* (INNS, 1988) · *Neurocomputing* · *Network: Computation in Neural Systems* → *Network Neuroscience* · *Psychological Review* · *Cognition* · *Cognitive Science* · *Trends in Cognitive Sciences* · *Behavioral and Brain Sciences* · *Computational Brain & Behavior* · *Synthese* · *Philosophy of Science* · *WIREs Cognitive Science* · *Philosophical Transactions of the Royal Society B* · *Interface Focus*

I deliberately put *Behavioral and Brain Sciences* on the mixed list rather than splitting it: it is simultaneously a NeuroAI venue and the main venue of the critical faction (Bowers 2023, Bever and Chomsky 2023, Brette 2019, Lake 2017). Collapsing that would erase something I am trying to see.

**General high-impact.** *Science* · *Nature* · PNAS · *Nature Communications* · *eLife* · *iScience* · *Communications Biology* · *Cell*

These are multidisciplinary venues, so venue membership carries no field information for them; in the venue-based classification scheme they are labeled `venue_general_high` and their field is resolved by the topic and Semantic Scholar schemes instead.

**Conferences, with founding years.** Cosyne (2004) · CCN (2017) · Bernstein Conference (2005) · CNS (1992) · AREADNE (2006) · ICONN (2007) · NICE (2013) · ICONS (2018) · NeurIPS NeuroAI Workshop (2024+) · NIH BRAIN NeuroAI Workshop (2024+) · Dartmouth NeuroAI Workshop (2024) · RLC (2024+) · SVRHM (2019+) · NeurReps (2022+) · InfoCog (2023+) · UniReps (2023+) · ICLR Re-Align (2024+) · NeurIPS Mechanistic Interpretability Workshop (2024+) · AAAI SafeAI Workshop · SfN Annual Meeting · FENS Forum

### 5.2 The resolved OpenAlex source IDs used to build Pool 3

`core_neuro` (17): S45757444 *Neuron* · S2298632 *Nature Neuroscience* · S5555990 *Journal of Neuroscience* · S120775027 *Current Opinion in Neurobiology* · S114966740 *Trends in Neurosciences* · S131371711 *Annual Review of Neuroscience* · S142952003 *Journal of Neurophysiology* · S103225281 *NeuroImage* · S117898428 *Cerebral Cortex* · S118357697 *Brain* · S172319488 *Brain Structure and Function* · S55111660 *Hippocampus* · S4210172947 *eNeuro* · S4210225821 *Network Neuroscience* · S27455496 *Journal of Computational Neuroscience* · S115201632 *Frontiers in Neuroscience* · S96638545 *Brain Research*. Unresolved at probe time: *Nature Reviews Neuroscience*.

`core_ai` (16): S4306420609 NeurIPS · S4306419644 ICML · S4306419637 ICLR · S4306419999 IJCAI · S4210191458 AAAI Proceedings · S4306419146 AISTATS · S2912241403 *Nature Machine Intelligence* · S118988714 JMLR · S4306420508 ACL · S4306418267 EMNLP · S4306418318 ECCV · S4363607701 CVPR 2022 · S4363607764 ICCV 2021 · S4306420424 ACM SIGKDD · S4363607759 ICRA 2022 · S2729999759 *Transactions of the ACL*. Unresolved at probe time: TMLR, EACL, RLC, the canonical NAACL entry, COLT, UAI, the canonical AAMAS entry.

`mixed` (18): S207023548 *Neural Computation* · S86033158 *PLoS Computational Biology* · S19778766 *Frontiers in Computational Neuroscience* · S115606517 *Frontiers in Neurorobotics* · S133078663 *Cognitive Computation* · S123019304 *Neural Networks* · S4210175523 *IEEE TNNLS* · S78735424 *Cognitive Science* · S192051125 *Trends in Cognitive Sciences* · S59628311 *Behavioral and Brain Sciences* · S4210221739 *Computational Brain & Behavior* · S255146 *Synthese* · S147691735 *Philosophy of Science* · S91660768 *Phil Trans R Soc B* · S4306498462 CCN 2019 · S4363607991 CCN 2022 · S4306498296 CCN 2018 · S4306419727 ICONIP. Unresolved at probe time: *WIREs Cognitive Science*, *Biological Cybernetics*.

`general_high` (10): S4393913764 *Science* · S137773608 *Nature* · S4306524276 PNAS · S64187185 *Nature Communications* · S1336409049 *eLife* · S2898358376 *iScience* · S4210225776 *Communications Biology* · S110447773 *Cell* · S169236886 *Cell Reports* · S4220651275 *PNAS Nexus*.

The CVPR, ICCV and ICRA entries resolve to single-year conference instances rather than to a venue series, because that is how OpenAlex represents them. This under-counts those conferences substantially and is a weakness of Pool 3 that I know about.

### 5.3 The display-name lists used for venue-based field assignment

`CORE_NEURO` (23 strings, allowing for title variants): Neuron · Nature Neuroscience · Journal of Neuroscience · The Journal of Neuroscience · Nature Reviews Neuroscience · Current Opinion in Neurobiology · eLife · Journal of Computational Neuroscience · Cerebral Cortex · NeuroImage · Brain · Trends in Neurosciences · Annual Review of Neuroscience · Journal of Neurophysiology · The Journal of Physiology · Journal of Neuroscience Methods · eNeuro · Network Neuroscience · Brain Structure & Function · Brain Structure and Function · Hippocampus · Neuroreport · Cell Reports

`CORE_AI` (31): Advances in Neural Information Processing Systems · Neural Information Processing Systems · International Conference on Machine Learning · International Conference on Learning Representations · Journal of Machine Learning Research · AAAI · Proceedings of the AAAI Conference on Artificial Intelligence · International Joint Conference on Artificial Intelligence · AISTATS · International Conference on Artificial Intelligence and Statistics · Conference on Learning Theory · Transactions on Machine Learning Research · IEEE Conference on Computer Vision and Pattern Recognition · Conference on Computer Vision and Pattern Recognition · IEEE International Conference on Computer Vision · European Conference on Computer Vision · Empirical Methods in Natural Language Processing · Annual Meeting of the Association for Computational Linguistics · Nature Machine Intelligence · Findings of the Association for Computational Linguistics · North American Chapter of the Association for Computational Linguistics · Conference of the European Chapter of the Association for Computational Linguistics · AAMAS · International Conference on Intelligent Robots and Systems · International Conference on Robotics and Automation · Knowledge Discovery and Data Mining · Web Search and Data Mining · Recommender Systems · Uncertainty in Artificial Intelligence · Reinforcement Learning Conference · International Conference on Automated Planning and Scheduling

`MIXED_INTERSECTION` (26): Neural Computation · Biological Cybernetics · Kybernetik · PLoS Computational Biology · PLOS Computational Biology · Frontiers in Computational Neuroscience · Frontiers in Neuroscience · Frontiers in Neurorobotics · Cognitive Computation · IEEE Transactions on Neural Networks and Learning Systems · Neural Networks · Neurocomputing · Network: Computation in Neural Systems · Psychological Review · Cognition · Cognitive Science · Trends in Cognitive Sciences · Behavioral and Brain Sciences · Computational Brain & Behavior · Computational Brain and Behavior · Synthese · Philosophy of Science · WIREs Cognitive Science · Philosophical Transactions of the Royal Society B Biological Sciences · Phil Trans R Soc B · Interface Focus

`GENERAL_HIGH_IMPACT` (7): Science · Nature · Proceedings of the National Academy of Sciences · Nature Communications · iScience · Communications Biology · Cell

I match exactly on `primary_location.source.display_name`, not by substring, which is why I list several venues more than once under alternate titles. Anything not on a list is `venue_other`; a work with no primary location is `venue_unknown`.

## 6. Pool 4: seed authors (23,208 works)

Pool 4 admits the entire publication output of a curated set of lineage-anchor authors, in six sub-rosters. It is the smallest pool by a wide margin, and deliberately so: I built it to guarantee that the classical lineages are represented in the corpus at all, not to characterize their volume.

**Resolution method.** I match seed names case-insensitively against OpenAlex `authors.display_name`, exactly, with a floor of five works to filter out name-alike junior authors. I keep all OpenAlex author records matching the same name, and I flag works as `disambiguation_needed` if the matched display name contains any of six surnames known to collide: **Aertsen, Engel, Wang, Anderson, Wilson, Smith**. I carry the flag into the output rather than using it to drop rows. Exact-display-name matching is brittle in the other direction too: a seed author whose OpenAlex record spells the name differently from the roster resolves to nothing at all, silently.

**The cross-pool hard rule.** Any seed author drawn from classical molecular, cellular or circuits neuroscience must have demonstrated functional work connecting to computation, learning or cognition. Pure-anatomy figures are filtered out. I applied this when I compiled the rosters, not in code.

The names below are the seed lists as implemented in `src/neuroai_cn/corpus/pool4.py`. Where the foundation document names someone the code does not resolve, I say so, because the difference is the difference between the design and the data.

### 4a: brand era, post-2019 (44 names as implemented)

Anthony M. Zador · Blake A. Richards · Bence Ölveczky · Yoshua Bengio · Kwabena Boahen · Matthew Botvinick · Mitya Chklovskii · Anne K. Churchland · Claudia Clopath · James J. DiCarlo · Surya Ganguli · Konrad Körding · Yann LeCun · Timothy P. Lillicrap · Adam H. Marblestone · Bruno A. Olshausen · Alexandre Pouget · Cristina Savin · Terrence J. Sejnowski · Eero P. Simoncelli · Sara Solla · David Sussillo · Andreas S. Tolias · Doris Y. Tsao · Demis Hassabis · SueYeon Chung · Martin Schrimpf · Patrick Mineault · Caswell Barry · Yamins Daniel · Aran Nayebi · Liam Paninski · Jonathan W. Pillow · H. Sebastian Seung · Maneesh Sahani · Tom Mrsic-Flogel · Kenneth D. Harris · Quentin J. M. Huys · Matthias Bethge · Jakob H. Macke · Rui Ponte Costa · Andrew Saxe · Cengiz Pehlevan · Marcel A. J. van Gerven

The foundation specifies "all 27 Zador 2023 signatories" as the canonical core of 4a. Twenty-four of them are in the list above. **Escola, Hawkins and Koulakov are named in the foundation and absent from the code.** In practice this matters less than it looks, because all 27 signatories enter Pool 1a through the anchor-DOI route regardless; the omission affects only the Pool 4 sub-tier tag. The entry `Yamins Daniel` is a name-order error for Daniel L. K. Yamins and will not resolve against OpenAlex; that is a genuine miss. The foundation also names, among the program faculty, Sham Kakade, Bernardo Sabatini, Jonathan Cohen, Nathaniel Daw, Erin Grant, Kevin Miller, Venkatesh Murthy and Armin Lak, none of whom I included in the implemented list.

### 4b: classical bridges: PDP, connectionism, Marr, Hopfield (12 names)

David E. Rumelhart · James L. McClelland · Geoffrey E. Hinton · John J. Hopfield · Stephen Grossberg · Peter Dayan · Larry F. Abbott · Patricia S. Churchland · Paul M. Churchland · Teuvo Kohonen · James A. Anderson · Tomaso A. Poggio

The foundation additionally names Marr, Sejnowski (also 4a), Varela and Maturana in this tier. Marr, Varela and Maturana are absent from the implemented list; Marr's exclusion is consistent with decision D2, since his work enters the citation graph only through citing works.

### 4c: biological cybernetics (11 names)

Shun-ichi Amari · Christoph von der Malsburg · Günther Palm · Ad Aertsen · Valentin Braitenberg · Kunihiko Fukushima · Heinrich H. Bülthoff · Bernhard Schölkopf · Wolfgang Maass · Robert Legenstein · Herbert Jaeger

The foundation additionally names Wiener, McCulloch, Pitts, Lettvin, Hebb, Rosenblatt and Ashby. All seven are absent from the implemented list, and all seven are pre-1990 or pre-DOI figures whose work enters the citation graph only through citing works under decision D2, so their absence from a publication-based seed list is consistent rather than accidental.

### 4d: theoretical and computational neuroscience (33 names)

Haim Sompolinsky · Daniel J. Amit · Nicolas Brunel · William Bialek · Fred Rieke · Peter E. Latham · Wulfram Gerstner · Tim P. Vogels · Henning Sprekeler · Cengiz Pehlevan (also 4a) · Ila R. Fiete · Eric Shea-Brown · Stefano Fusi · Xiao-Jing Wang · Kanaka Rajan · Srdjan Ostojic · Walter Senn · Mihai A. Petrovici · Katharina A. Wilmes · Cristiano Capone · João Sacramento · Boris S. Gutkin · Carl van Vreeswijk · Magnus J. E. Richardson · Sophie Denève · Mark C. W. van Rossum · Christian K. Machens · Luca Mazzucato · Ashok Litwin-Kumar · Richard Naud · Francesca Mastrogiuseppe · Manuel Beiran · Dean V. Buonomano

The Bern group (Senn, Petrovici, Wilmes, Capone, Sacramento, and Rui Ponte Costa via 4a) is present in full. The foundation also names Nirenberg, Engel, Boerlin, Calaim, Pezon, Schmutz, Bicknell, Stern, Kilpatrick, Recanatesi, Whittington, Bogacz and J. Murray in this tier; I did not implement any of them. Engel's omission is defensible given the surname-collision flag; the others are simple gaps.

### 4e: skeptics and measured critics (18 names)

The foundation's cleaned Faction 13 roster is thirteen *entries* in four sub-tiers, one of which is the Bever/Fong/Piattelli-Palmarini trio counted as one. Expanded to individuals, that is 18 names, which is what the code holds.

*Sub-tier A, polemicists:* Gary F. Marcus · Noam Chomsky · Walid S. Saba · Subbarao Kambhampati · Thomas G. Bever · Sandiway Fong · Massimo Piattelli-Palmarini

*Sub-tier B, polemicist-adjacent and not NeuroAI-engaged:* Emily M. Bender · Timnit Gebru

*Sub-tier C, measured external:* Jeffrey S. Bowers · David Poeppel · Melanie Mitchell · Olivia Guest · Andrea E. Martin · Kyle Mahowald

*Sub-tier D, measured internal and methodological anchor:* Ida Momennejad · Federico Adolfi · Eric Jonas

Bender and Gebru carry an explicit AI-ethics flag: their critique targets scale and FAccT concerns, not NeuroAI as a research program, and I retain them with that qualification rather than treating them as NeuroAI critics.

After review I reassigned eight names originally on the skeptic list out of it, preserving cross-references as a safety net: Krakauer and Pessoa and Cisek to cognitive neuroscience, Fedorenko to the cognitive neuroscience of LLMs, Gershman and Lake to computational cognitive science, Brette to theoretical neuroscience with a cybernetics cross-tag, and Hawkins to the brand wing with a constructive-alternative flag. I dropped Buckner, Millière and Deacon entirely as philosophers rather than citation-cluster members, and I discuss them qualitatively only.

### 4f: safety and interpretability via neuroscience (16 names)

Patrick J. Mineault (also 4a) · Christopher Olah · Trenton Bricken · Jack Lindsey · Catherine Olsson · Yann LeCun (also 4a) · Anders Sandberg · Emily Mackevicius · Steven Byrnes · Connor Leahy · Murray Shanahan · Max Tegmark · Julian Jara-Ettinger · Marcelo Mattar · Nathan A. Sanborn · Pedro A. Tavares

Three problems in this sub-roster that a reader should know about. **`Anders Sandberg` is not on the foundation's 4f roster** and appears to have been introduced at implementation. **`Nathan A. Sanborn` and `Pedro A. Tavares` are almost certainly wrong resolutions** of the Mineault 2024 co-signatories the foundation intends, and will either match nothing or match the wrong person. And the foundation's 4f also names Zanichelli, Peng, Arkhipov, Bingham, Amodei, Payne and Schroeder, none of whom are implemented. Because all Mineault 2024 signatories enter Pool 1a through the anchor-DOI route, the practical damage is limited to the sub-tier tag, but the entries should be fixed before anyone reuses this list.

### 4g: cortical chemoarchitecture: not a pool

Per decision B5, chemoarchitecture is not a pool and not a faction. Most chemoarchitecture work is anatomy without a functional, computational or learning connection, so it fails the cross-pool hard rule. The Kording et al. 2026 function-to-molecular-microarchitecture paper is the only seedling of a substantive bridge, and it is discussed in the article as a gap rather than represented as a corpus row.

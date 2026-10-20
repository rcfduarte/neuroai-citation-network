---
title: "S5. The bridge builders: papers, authors and institutions (Figure 3)"
date: 2026-10-20
author: Renato Duarte
repo: https://github.com/rcfduarte/neuroai-citation-network
---

# S5. The bridge builders: papers, authors and institutions (Figure 3)

This supplement explains the third figure of the article: how I score a paper as a bridge between neuroscience and AI, which papers I let into the ranking and why, how the scores of papers become scores of authors and institutions, how I checked every author-to-institution link by hand, and what the ranking does and does not measure. In short, the strongest bridges are an old canon plus general-purpose software, the authors mix AI-leaning and neuroscience-leaning researchers, and the institutions column is led by two industry groups, Alphabet and Microsoft, followed by elite universities (section 4.5). Bridge weight concentrates more by place than by person (section 4.7).

## 1. What the article says

Figure 3 shows three ranked columns, papers, authors and institutions, with lines joining them; the caption says that papers were ranked on the harmonic mean and authors and institutions on the sum of those scores across the bridge papers they are credited on. (The file is called `figure2_v3` in the repository for historical reasons.) Paragraph 11 introduces the score:

> I ranked publications according to the harmonic mean of each paper's citations from each field. (The harmonic mean is applied here to punish imbalance instead of smoothing it over: a paper cited 1,000 times by AI and twice by neuroscience will have a very low score, whereas one cited 100 times by each side will score high.) I considered roughly 59,000 papers with at least 5 citations from each side. The full scoring, the locked corpus, a hand-verification of every affiliation drawn here, and a more thorough analysis beyond the top 15 are in the supplements.

Paragraph 12 reads the papers column: "about half of the strongest bridges are not concepts or ideas, but tools", the rest are "a classical canon of foundational neuroscience work", and "the most recent of these bridgeworks is from 2003". Paragraph 13 names the authors and says "Affiliations were hand-verified against ORCID, institutional pages and CVs; solid links mark current affiliations, faded links mark past affiliations". Paragraph 14 makes the claim about institutions:

> Two industry labs, Alphabet (Google + DeepMind) and Microsoft, top the ranking [...]. Bridge work concentrates far more by place than by person: the top 100 institutions absorb nearly 40 percent of all bridge weight, in contrast, the top 100 authors remain below 7 percent.

In section 3.2 I give the funnel behind the "roughly 59,000 papers", in section 3.3 the paper sets over which authors and institutions are summed, in section 4.5 the institutions column and in section 4.7 the concentration figures.

## 2. Data

Everything comes from the March 2026 OpenAlex snapshot described in [S1](S1-data-and-classification.md), with the field labels of that supplement: a paper is neuroscience or AI according to its primary OpenAlex topic, under the extended AI definition. A citation is "classified" when the citing paper carries one of those two labels; citations from papers in other fields, or with no label, are ignored by the score. For each cited paper I count the classified citations it receives from neuroscience papers (`c_neuro`) and from AI papers (`c_ai`). I only count who cites a paper, so the direction naming of [S2](S2-citation-flow.md) does not matter here. In Figure 3 the color of a bar shows `neuro_share = c_neuro / (c_neuro + c_ai)`, on a scale with teal at 0 (almost all citations come from AI papers) and gold at 1 (almost all come from neuroscience papers). Color describes who reads the work, not what field the work belongs to.

Candidates, by my definition, are all papers with at least five classified citations from each side, 133,763 papers. A cited identifier becomes a candidate only if my index also holds a record for that work, published between 1990 and 2026, so that it has a title, a year and a label; identifiers that reach five citations from each side but have no work record are not counted among the 133,763. Author and institution identities come from OpenAlex (`author_id`, `institution_id`) with no consolidation of my own, except for the corporate groups of section 3.5. All tables of this supplement, the 26 hand-verified affiliation edges and the eight paper-to-author links of the figure are committed in [`results/bridge/`](../../results/bridge/README.md).

## 3. Method

### 3.1 The bridge score and why a harmonic mean

For a paper p, the bridge score is the harmonic mean of the two counts:

```
B(p) = 2 * c_neuro(p) * c_ai(p) / (c_neuro(p) + c_ai(p))
```

The harmonic mean of two numbers is the reciprocal of the average of their reciprocals. Why do I use it? Because it is never larger than twice the smaller of the two numbers, so a paper cannot score well on one side's attention alone, whereas the arithmetic mean is dominated by the larger count. Take the first row of the top-15 table below. BRATS has 2,547 citations from neuroscience and 1,952 from AI, so B = 2 x 2,547 x 1,952 / (2,547 + 1,952) = 2,210.16, close to the arithmetic mean of 2,249.5 because the two counts are close. As the counts become more unequal, the two means separate:

| Paper | Cited by neuroscience | Cited by AI | Arithmetic mean | Harmonic mean (B) |
|-|-:|-:|-:|-:|
| Balanced: Bi and Poo (1998) | 2,271 | 2,106 | 2,188.5 | 2,185.39 |
| Skewed toward neuroscience: lme4 (2015) | 8,437 | 920 | 4,678.5 | 1,659.09 |
| Skewed toward AI: XGBoost (2016) | 798 | 5,559 | 3,178.5 | 1,395.65 |
| Extreme, AI side: Probabilistic roadmaps for path planning (1996) | 6 | 4,790 | 2,398.0 | 11.98 |
| Extreme, neuroscience side: Autism Diagnostic Interview-Revised (1994) | 7,379 | 7 | 3,693.0 | 13.99 |

In the article's own illustration, a paper cited 1,000 times by AI and twice by neuroscience, scores 3.99 on this scale, against 100 for one cited 100 times by each side; the arithmetic mean would give 501 and 100. Both extreme rows are real papers of the pool: a path-planning paper cited 4,790 times by AI and 6 times by neuroscience scores 11.98, and a diagnostic interview for autism cited 7,379 times by neuroscience and 7 by AI scores 13.99.

B is a count, not a share: I compute it on raw citation counts, so its unit is citations. It is not corrected for the sizes of the two fields (AI is much the larger literature in recent years, see [S1](S1-data-and-classification.md) and [S3](S3-counts-and-field-sizes.md)); the ranking therefore rewards works that are cited a lot by both sides in absolute terms. A variant that normalizes each side's count exists in the code as a diagnostic; I did not re-run it for this version, so I report no number for it.

### 3.2 Which papers are eligible, and what each filter removes

The article considers "roughly 59,000 papers with at least 5 citations from each side". In the snapshot, 133,763 papers pass the gate of five classified citations from each side, and 58,971 remain after the eligibility filters; these 58,971 are the papers the article's "roughly 59,000" refers to. Three rules decide which of the candidate papers can be ranked, applied in this order:

| Step | Papers remaining | Removed |
|-|-:|-:|
| gate: at least 5 classified citations from each side | 133,763 | 0 |
| own field label neuro or ai (drops other and unknown) | 59,038 | 74,725 |
| classified citations under the 10,000 ceiling (E2) | 58,971 | 67 |

The gate admits 133,763 papers. For the top of the ranking it is irrelevant: because B can never exceed twice the smaller count, any paper with B above 1,396 (the score of the fifteenth paper in Table S1) has at least 698 citations from each side, and the smallest count among the top fifteen is 798. Five is a fixed threshold that I did not vary.

Under the second rule I keep papers whose own field label is neuroscience or AI, which removes 74,485 papers labeled as another field and 240 with no label. It is the paper's own label that excludes, for example, a large block of plasma-physics papers from the Large Helical Device (LHD) fusion experiment, which receive thousands of citations from papers that OpenAlex labels neuroscience and AI. They are plainly not bridge works. Yet I do not know why the labels come out this way. Without this rule they take six of the top ten places of the whole pool (the first rows of [`unfiltered_top_papers.csv`](../../results/bridge/unfiltered_top_papers.csv) show them). This rule has a cost, because the label "other" also covers some work I would want. Among the highest-scoring papers of the unfiltered pool, the R language (11,739 neuroscience and 4,085 AI citations, rank 2) and the U-Net segmentation network (rank 10) carry the label "other", so they cannot enter.

In the third rule, which I call the E2 ceiling, I drop papers with 10,000 or more classified citations in total. E2 is the second of two alternative filter variants in my decision log (E1 divides B by the logarithm of total citations); the article uses E2. It removes 67 papers, 66 labeled AI and one neuroscience. In section 4.2 I show what they are and what the top 15 would look like without the ceiling. Fusion papers go out under the second rule, not under the ceiling, which in my pipeline removes only papers already labeled neuroscience or AI.

After these three rules 58,971 papers remain. Last come filters that I apply to the displayed ranking, not the pool. Table S1 keeps only OpenAlex types article and review, drops ebook-platform and book-series sources, empty titles, duplicate titles and three book titles I listed by hand (reinforcement learning, pattern classification, the NeurIPS proceedings volumes), and takes the first fifteen. Among the 40 best eligible candidates, 7 are removed by these rules (1 of OpenAlex type book chapter, 1 listed by hand, 5 of type book), and the table keeps the first fifteen of the 33 that remain. These rules matter: without them, Duda, Hart and Stork's *Pattern Classification* would take the fourth place of the eligible ranking.

### 3.3 Summing paper scores over authors and institutions

An author's bridge weight is the sum of B over the bridge papers on which the author is credited, and an institution's is the sum over the bridge papers that carry an affiliation to it. A paper counts in full for every author and every institution on it, once per institution however many of its authors share it; I do not divide credit. Next to each sum I report the paper count, so that one blockbuster inflating a total stays visible.

The columns of Figure 3 are summed over these paper sets:

- Authors: the top 5,000 eligible papers by B, with at least two papers for an author. That is a compromise of computing time and can leave out authors whose contribution is spread over many mid-ranked papers.
- Institutions other than the corporate groups (universities, institutes, hospitals and the like): the same top 5,000 eligible papers, with at least five papers for an institution.
- The three corporate groups (Alphabet, Microsoft and Meta, section 3.5): every paper that passes the 5-and-5 gate, 133,763 papers, so including papers labeled other and papers above the ceiling. A paper counts once for a group when any of its authors lists one of the group's sub-entities.

The institutions column of Figure 3 therefore sums company rows over every paper passing the 5-and-5 gate and university rows over the top 5,000 eligible papers. Concentration figures (section 4.7) rest on a third set, which I describe in section 3.7. Institution credit follows the affiliations printed on each paper, so a researcher who moved is credited to the place where the paper was written. No ranking uses the OpenAlex field `last_known_institutions` (section 3.4 says why).

### 3.4 How the affiliations were verified

Because the figure names fifteen living researchers and asserts employment relationships between them and the institutions on the right, I checked every one of those relationships.

My first version drew the lines from the OpenAlex field `last_known_institutions`, and the result was unusable in two ways. Name collisions gave confident nonsense: Brian Avants resolved to the California University of Pennsylvania, a real school unrelated to his Penn affiliations; Christof Koch to the Gere Foundation; Antonio Torralba to Citigroup; Yoshua Bengio to a "Centre Universitaire de Mila" in Algeria. Co-authorship gave plausible nonsense, which is worse: Peter Dayan acquired an HHMI affiliation inherited from joint papers with Terry Sejnowski, and Stephen Smith acquired "Harvard 1950", a parse error. None of these survived. And the rejected candidates and their reasons are in my per-edge audit notes.

In May 2026 I replaced all of them with hand-verified affiliations, using a fixed order of sources: ORCID employment records, then official university, lab or institute pages, then Google Scholar verified affiliations, then the researcher's homepage or CV, then LinkedIn (author-curated and reliable for industry roles and dates), with Wikipedia only as a cross-check. I ran the verification as five parallel research passes and used Claude Code as an aid; the general rule that model output was treated as unvetted material is in [`docs/GAI-DISCLOSURE.md`](../GAI-DISCLOSURE.md). Every drawn edge rests on at least one authoritative source. Roles and dates are committed in [`author_institution_edges.csv`](../../results/bridge/author_institution_edges.csv) and in `src/neuroai_cn/audits/affiliations_overrides.py`; the source URLs are in a working document outside this repository. That gives 26 edges, 10 current and 16 past. Three details remain the least certain, all dates and not institutions: Hinton's start year at San Diego, whether Fischl's MIT role is current or tapering, and the end of Avants's Penn appointment.

My editorial policy on current and past affiliations has four rules, applied uniformly so that nobody gains or loses an edge through inconsistency. Only research affiliations count (PhD, postdoc, faculty, director, visiting researcher, industry research); taught degrees do not, which removed Olshausen's Stanford BS and MS, and neither does non-research clinical training, which removed Friston's early Oxford psychiatry rotation. Only institutions among the 15 shown can appear, so some current employers (Mila and the Université de Montréal, the Allen Institute, the Max Planck Institute in Tübingen, USC, Brain Corp) are absent by design. HHMI carries no author edge because I could not verify an Investigator appointment there for any of the fifteen. Genuine dual current affiliations are drawn as dual: Fischl's Harvard Medical School and MIT CSAIL positions are both solid. A solid line means the researcher holds the affiliation now; a faded line means held in the past. Past lines stay because a career crosses several places and the bridge was built over time.

I checked the eight lines between papers and authors against Crossref and OpenAlex publisher metadata, and all eight author positions (first, middle, last) are correct, including the two cases most likely to be wrong: Avants is fifteenth of sixty-eight authors on the BRATS paper (middle), and Koch is last on the 2001 attention review and middle on the 1998 saliency paper. Line thickness on those links encodes position (last 2.0, first 1.5, middle 1.0) and affects only the drawing. Because the pipeline's own link file stops after 100 rows and has no rows for SciPy or XGBoost, I recomputed the eight drawn links from the authorship lists of the fifteen papers; they match.

One thing the figure does not say: institution rank comes from paper affiliations, not from where the fifteen authors work. An institution can rank on volume alone and have no author line. HHMI is the clear case, with no line at all; the University of Pennsylvania has only a faded one, from Avants. Readers have taken this for a drawing error, so I state it here.

### 3.5 Corporate consolidation

OpenAlex treats Google (United States), Google (United Kingdom) and DeepMind (United Kingdom) as separate institutions, Microsoft (United States) and Microsoft Research (United Kingdom) as two more, and Meta (Israel) as another; those were the entities I found in the top-100 table. For the main figure I merged them into three parent groups, Alphabet (Google + DeepMind), Microsoft and Meta, counting a paper once for a group even when its authors sit at several sub-entities. The sub-entities of each group are those whose names match the group in the top-100 institution table (`neuroai_cn.audits.institution_consolidation`), and the group rows are summed over every paper that passes the 5-and-5 gate (section 3.3). On 22 May 2026 I made the choice, and I kept the unconsolidated variant as a second figure, because this is the decision that most changes what a reader sees.

My argument for merging is that splitting one company's research organization across national registrations hides the answer to a plain question, how much of the bridge work happens in industry. Against merging, it imposes a judgment on a database that does not encode it, and universities are not merged the same way although several have separately listed hospitals and institutes. I do not merge subsidiaries that carry no group name (LinkedIn, GitHub, Waymo, Verily).

### 3.6 Tools and concepts

To describe what the top fifteen are made of, I coded each paper by hand. A tool is software, a benchmark, an analysis method or a methods survey that both fields cite because they run it. A concept is a claim about brains or minds: how neurons learn, how vision or attention work, how memory is limited. What counts is what the paper offers a reader, not how it is written. I record the coding in the `paper_class` column of [`table_s1_papers.csv`](../../results/bridge/table_s1_papers.csv). It agrees with the separate hand coding of [S6](S6-citation-age.md) (`results/citation_age/classification.csv`) for all 14 papers that file matches by title; the fifteenth, lme4, is coded as a tool there too, but its title carries HTML markup that breaks the match. That second file has a third class, "method" (a new machine-learning model or algorithm), which no paper of the top fifteen needs.

Some calls are arguable. Izhikevich's spiking-neuron model is a claim about neuron dynamics and also a component people run in simulations. Itti, Koch and Niebur's saliency model has 8,286 AI citations against 879 from neuroscience, probably because AI researchers use it as an algorithm. Hierarchical object-recognition models are cited both as theory and as architecture. Recoding those three as tools would give ten tools of fifteen instead of seven, and the article would then say "most" and not "about half".

### 3.7 Concentration

To ask whether bridge work is carried by exceptional individuals or by exceptional environments, I summed B over every author and institution credited on the 133,763 papers that pass the 5-and-5 gate and computed which share of the total the top N hold. Numerators come from the persisted tables of the top 1,000 authors and the top 1,000 institutions, and I take the denominators from the total weight of every author and every institution in the pool. Because this pool still holds the block of fusion-experiment papers described in section 3.2, I bound its effect: every author and institution that averages more than 400 units of B per paper is dropped from the top-1,000 tables, and its weight is subtracted from the total. That removes 298 authors and 17 institutions. I call the result the sensitivity bound, and the concentration figures of the article are its values (section 4.7). Besides the shares I report the Gini coefficient, a number between 0 (everyone holds the same) and 1 (one holds everything) that summarizes inequality in a distribution.

## 4. Results

![Figure 3 of the article](../../figures/figure2_v3.png)

*Figure 3 (`figure2_v3`), as published. Left: the 15 strongest bridge papers, bar length B (the harmonic mean of citations from neuroscience and AI papers). Middle: the 15 authors with the largest sum of B over their bridge papers. Right: the 15 institutions with the largest sum of B, with Alphabet and Microsoft consolidated from their sub-entities. Bar color is the share of citations from neuroscience papers: teal means almost all from AI, gold almost all from neuroscience. Lines link each paper with its authors (thickness by authorship position) and each author with institutions (solid current, faded past). Data: `results/bridge/table_s1_papers.csv`, `table_s2_authors.csv`, `table_s3_institutions_consolidated.csv`, `author_institution_edges.csv`, `paper_author_links.csv`; regenerated by `python -m neuroai_cn.figures.figure2_bridges_v3`. The corporate bars sum over every paper that passes the 5-and-5 gate, the other institution bars and the author bars over the top 5,000 eligible papers (section 3.3).*

### 4.1 The papers

| # | Paper | Year | Cited by neuroscience | Cited by AI | B | Share from neuroscience | Class |
|-:|-|-:|-:|-:|-:|-:|-|
| 1 | Multimodal Brain Tumor Image Segmentation Benchmark (BRATS), Menze et al. | 2014 | 2,547 | 1,952 | 2,210 | 0.57 | tool |
| 2 | Synaptic modifications in cultured hippocampal neurons (spike-timing plasticity), Bi and Poo | 1998 | 2,271 | 2,106 | 2,185 | 0.52 | concept |
| 3 | Simple model of spiking neurons, Izhikevich | 2003 | 1,680 | 2,235 | 1,918 | 0.43 | concept |
| 4 | Emergence of simple-cell receptive field properties by learning a sparse code, Olshausen and Field | 1996 | 2,004 | 1,832 | 1,914 | 0.52 | concept |
| 5 | Computational modeling of visual attention, Itti and Koch | 2001 | 1,750 | 1,948 | 1,844 | 0.47 | concept |
| 6 | The magical number seven, plus or minus two, Miller | 1994 | 2,126 | 1,563 | 1,802 | 0.58 | concept |
| 7 | Fitting linear mixed-effects models using lme4, Bates et al. | 2015 | 8,437 | 920 | 1,659 | 0.90 | tool |
| 8 | Segmentation of brain MR images by hidden Markov random field and EM, Zhang et al. | 2001 | 2,111 | 1,335 | 1,636 | 0.61 | tool |
| 9 | A survey on deep learning in medical image analysis, Litjens et al. | 2017 | 969 | 4,431 | 1,590 | 0.18 | tool |
| 10 | A model of saliency-based visual attention, Itti, Koch and Niebur | 1998 | 879 | 8,286 | 1,589 | 0.10 | concept |
| 11 | SciPy 1.0, Virtanen et al. | 2020 | 1,944 | 1,293 | 1,553 | 0.60 | tool |
| 12 | Short-term synaptic plasticity, Zucker and Regehr | 2002 | 2,787 | 1,035 | 1,509 | 0.73 | concept |
| 13 | An introduction to ROC analysis, Fawcett | 2005 | 885 | 3,938 | 1,445 | 0.18 | tool |
| 14 | Hierarchical models of object recognition in cortex, Riesenhuber and Poggio | 1999 | 1,690 | 1,205 | 1,407 | 0.58 | concept |
| 15 | XGBoost, Chen and Guestrin | 2016 | 798 | 5,559 | 1,396 | 0.13 | tool |

In the class column I give the hand coding of section 3.6. Of the 15 papers, 7 are tools and 8 are concepts. Those 8 concepts date from 1994 to 2003, with the caveat that OpenAlex dates Miller's paper by a 1994 reprint of the 1956 original, so the true span begins earlier. Izhikevich's spiking-neuron model of 2003 is the most recent concept, and SciPy 1.0 of 2020 the most recent tool. The median publication year of the top 15 of Table S1 is 2002 on OpenAlex's dates. Scores fall in a narrow band, from 2,210 to 1,396, and the share of citations from neuroscience runs from 0.10 (the Itti, Koch and Niebur saliency model) to 0.90 (lme4).

Behind the fifteen the distribution is steep. Among the 58,971 eligible papers, 48 have a B of at least 1,000, 2,150 have at least 100, and 1,108 have at least 100 citations from each side.

I list the 40 best eligible candidates, with the reason each excluded one was dropped, in [`s1_eligibility_check.csv`](../../results/bridge/s1_eligibility_check.csv). After the fifteen come a survey on transfer learning, a 1997 paper on synaptic efficacy and the timing of postsynaptic action potentials, Matplotlib, a tutorial on support vector machines and Hinton and Salakhutdinov's paper on reducing the dimensionality of data with neural networks, so I find that the margin below the top fifteen includes both software and neuroscience concepts.

### 4.2 What the E2 ceiling does

What the ceiling removes are works that everyone cites. Without it, the ranking of the neuroscience-or-AI pool looks like this, with the works removed by the ceiling marked:

| Rank without ceiling | Work | Year | Cited by neuroscience | Cited by AI | B | Removed by ceiling |
|-:|-|-:|-:|-:|-:|-|
| 1 | Deep Residual Learning for Image Recognition | 2016 | 4,671 | 112,475 | 8,970 | yes |
| 2 | Deep learning | 2015 | 3,099 | 20,569 | 5,386 | yes |
| 3 | LIBSVM | 2011 | 2,724 | 15,546 | 4,636 | yes |
| 4 | ImageNet classification with deep convolutional neural networks | 2017 | 2,456 | 38,936 | 4,621 | yes |
| 5 | Scikit-learn: Machine Learning in Python | 2012 | 2,793 | 11,757 | 4,514 | yes |
| 6 | Long Short-Term Memory | 1997 | 2,212 | 34,318 | 4,156 | yes |
| 7 | Random Forests | 2001 | 2,241 | 14,983 | 3,899 | yes |
| 8 | Reinforcement Learning: An Introduction | 1998 | 2,502 | 7,607 | 3,765 | yes |
| 9 | Reinforcement Learning: An Introduction | 2005 | 2,302 | 10,040 | 3,745 | yes |
| 10 | Adam: A Method for Stochastic Optimization | 2014 | 1,932 | 39,228 | 3,683 | yes |
| 11 | Very Deep Convolutional Networks for Large-Scale Image Recognition | 2014 | 1,817 | 42,664 | 3,486 | yes |
| 12 | MizAR 60 for Mizar 50 | 2023 | 1,702 | 35,419 | 3,248 | yes |
| 13 | Support-vector networks | 1995 | 1,763 | 9,578 | 2,978 | yes |
| 14 | Gradient-based learning applied to document recognition | 1998 | 1,461 | 28,913 | 2,781 | yes |
| 15 | ImageNet: A large-scale hierarchical image database | 2009 | 1,361 | 37,872 | 2,628 | yes |
| 16 | Visualizing Data using t-SNE | 2008 | 1,407 | 15,122 | 2,574 | yes |
| 17 | Going deeper with convolutions | 2015 | 1,261 | 23,512 | 2,394 | yes |
| 18 | Densely Connected Convolutional Networks | 2017 | 1,259 | 20,119 | 2,370 | yes |
| 19 | Support-Vector Networks | 1995 | 1,294 | 10,061 | 2,293 | yes |
| 20 | The Multimodal Brain Tumor Image Segmentation Benchmark (BRATS) | 2014 | 2,547 | 1,952 | 2,210 | no |
| 21 | Synaptic Modifications in Cultured Hippocampal Neurons: Dependence ... | 1998 | 2,271 | 2,106 | 2,185 | no |
| 22 | Dropout: a simple way to prevent neural networks from overfitting | 2014 | 1,154 | 14,395 | 2,137 | yes |

All 19 highest-scoring papers of that pool are removed by the ceiling, and the first Table S1 paper, BRATS, would rank 20th. Of the 67 removed papers, 26 score above the fifteenth paper of Table S1 (B of 1,396), so before the paper-type and book filters, which I could not apply without a database lookup, they would fill the whole top 15. They are the best-known general-purpose machine-learning references: ResNet, scikit-learn, LIBSVM, LSTM, Adam, dropout, random forests. Two pairs of entries are records of the same work under different OpenAlex identifiers (the reinforcement-learning textbook in two editions and the support-vector paper), and one, MizAR 60 for Mizar 50 with 35,419 AI citations, looks like a mis-resolved record and not a real paper. For every removed paper among the first 19, the share of citations from neuroscience lies between 0.03 and 0.25: their neuroscience counts are large, but their AI counts are much larger.

I see two consequences of the ceiling. It makes the ranking better balanced by removing works that dominate the score through AI-side volume (ResNet has 4,671 citations from neuroscience, more than BRATS, and 112,475 from AI, so its B of 8,970 is the highest of the pool). And it hides the machine-learning software and architectures that neuroscience cites because it uses them in practice. Without the ceiling, the top of the list would be machine-learning libraries, architectures and textbooks, none of them a claim about brains. So I think the article's finding that about half of the strongest bridges are tools, not concepts about the brain, is, if anything, conservative with respect to this choice. I chose 10,000 as a round number, not an estimate. But I did not test other thresholds.

### 4.3 The authors

| # | Author | Bridge papers | Sum of B | Cited by neuroscience | Cited by AI | Share from neuroscience |
|-:|-|-:|-:|-:|-:|-:|
| 1 | Yoshua Bengio | 41 | 9,937 | 6,739 | 76,514 | 0.08 |
| 2 | Christof Koch | 33 | 9,000 | 22,872 | 18,597 | 0.55 |
| 3 | Geoffrey E. Hinton | 34 | 8,807 | 5,505 | 58,177 | 0.09 |
| 4 | Wulfram Gerstner | 37 | 8,426 | 10,263 | 8,128 | 0.56 |
| 5 | Karl Friston | 46 | 7,909 | 55,276 | 4,444 | 0.93 |
| 6 | Aude Oliva | 32 | 7,312 | 8,303 | 23,659 | 0.26 |
| 7 | Stephen M. Smith | 16 | 6,263 | 33,904 | 5,767 | 0.85 |
| 8 | Peter Dayan | 28 | 5,963 | 23,209 | 7,815 | 0.75 |
| 9 | Eugene M. Izhikevich | 14 | 5,955 | 7,630 | 5,816 | 0.57 |
| 10 | Antonio Torralba | 25 | 5,715 | 4,111 | 31,713 | 0.11 |
| 11 | Laurent Itti | 16 | 5,386 | 4,344 | 14,998 | 0.22 |
| 12 | Henry Markram | 20 | 5,378 | 14,813 | 5,867 | 0.72 |
| 13 | Bruce Fischl | 20 | 5,338 | 42,203 | 3,246 | 0.93 |
| 14 | Brian Avants | 10 | 5,226 | 7,257 | 4,315 | 0.63 |
| 15 | Bruno A. Olshausen | 12 | 5,076 | 7,067 | 4,806 | 0.60 |

Authors are ranked by the sum of B over their bridge papers in the top 5,000 eligible papers, with at least two papers each. In my reading, the share-from-neuroscience column shows how wide the spread is. Bengio, Hinton and Torralba sit at 0.08 to 0.11, with roughly eight to eleven AI citations for every neuroscience citation. Friston and Fischl sit at 0.93 in the other direction. Koch, Gerstner, Izhikevich and Olshausen, at 0.55 to 0.60, are the closest to balance. A high bridge weight therefore does not require a balanced personal profile; it requires having written individual papers that both fields read.

Neighboring ranks are close. Between the author in tenth place (5,715) and the fifteenth (5,076) the sums differ by 11 percent, and the full-credit rule helps authors on large collaborations: Avants reaches rank 14 with 10 papers, and the 68-author BRATS paper alone contributes 2,210 of his 5,226. A fractional-credit variant, in which a paper's score is divided among its authors, is something I did not compute. Still, the order would change under it.

### 4.4 Where Aude Oliva sits

A reviewer asked about Aude Oliva, and the question has two parts. By the sum of bridge scores she ranks 6th of 15, with 32 bridge papers and a sum of 7,312, ahead of Stephen Smith (6,263) and behind Karl Friston (7,909). Her papers have been cited 8,303 times by neuroscience papers and 23,659 times by AI papers, a neuroscience share of 0.26, which puts her 5th from the AI-leaning end of the fifteen, between Itti (0.22) and Koch (0.55) and closer to the AI end.

Paragraph 13 lists her among the "prominent computational neuroscientists", which describes her field of research. Shares in the table describe something else, who cites her bridge papers (section 2), and by that measure I read her profile as nearer the AI-leaning end of the fifteen.

She is the only woman among the fifteen, by my reading of the names. That is a fact I do not want to explain away, and I want to be exact about what these data can say. This ranking reflects a canon in which the median publication year of the top 1,000 eligible papers is 2005 (section 4.8), and a citation-weighted ranking of a historically male-dominated field reproduces that composition with a lag. It cannot say whether the people doing bridge work now differ from those who did it in 1998; that needs a measure aimed at recent authorship and not at accumulated citation.

### 4.5 The institutions

The institutions column of Figure 3 is Table S3, with the corporate groups consolidated (section 3.5). The three corporate groups are summed over every paper that passes the 5-and-5 gate (133,763 papers), and every other institution over the top 5,000 eligible papers (section 3.3):

| # | Institution | Type | Bridge papers | Sum of B | Share from neuroscience |
|-:|-|-|-:|-:|-:|
| 1 | Alphabet (Google + DeepMind) | company | 924 | 63,142 | 0.09 |
| 2 | Microsoft | company | 712 | 35,557 | 0.05 |
| 3 | Massachusetts Institute of Technology | education | 220 | 35,338 | 0.55 |
| 4 | University of California, Berkeley | education | 138 | 27,774 | 0.23 |
| 5 | Harvard University | education | 173 | 27,390 | 0.80 |
| 6 | University College London | education | 165 | 23,553 | 0.79 |
| 7 | Stanford University | education | 153 | 23,449 | 0.33 |
| 8 | University of Oxford | education | 92 | 16,769 | 0.50 |
| 9 | Carnegie Mellon University | education | 99 | 16,748 | 0.25 |
| 10 | University of California, San Diego | education | 100 | 16,125 | 0.75 |
| 11 | California Institute of Technology | education | 83 | 15,264 | 0.49 |
| 12 | University of Toronto | education | 77 | 15,059 | 0.18 |
| 13 | University of Pennsylvania | education | 70 | 13,500 | 0.62 |
| 14 | École Polytechnique Fédérale de Lausanne | education | 70 | 13,195 | 0.46 |
| 15 | Howard Hughes Medical Institute | facility | 98 | 12,664 | 0.89 |

Alphabet (Google + DeepMind) and Microsoft hold the first two places, with a summed B of 63,142 over 924 bridge papers and 35,557 over 712. MIT, Berkeley, Harvard, UCL and Stanford follow in places 3 to 7. The two companies are also the most AI-leaning institutions of the column: 0.09 of Alphabet's citations and 0.05 of Microsoft's come from neuroscience, against 0.18 for the University of Toronto, the next lowest. Across all 45 bars of Figure 3, Microsoft (0.046) has the lowest neuroscience share, followed by Bengio (0.081), Alphabet (0.085) and Hinton (0.086). Because the corporate rows and the other rows count different sets of papers, paper counts in this table should be read within a row, not compared across the two kinds of row.

Separated, with the institutions as OpenAlex ships them (all rows over the top 5,000 eligible papers):

| # | Institution | Type | Bridge papers | Sum of B | Share from neuroscience |
|-:|-|-|-:|-:|-:|
| 1 | Massachusetts Institute of Technology | education | 220 | 35,338 | 0.55 |
| 2 | University of California, Berkeley | education | 138 | 27,774 | 0.23 |
| 3 | Harvard University | education | 173 | 27,390 | 0.80 |
| 4 | University College London | education | 165 | 23,553 | 0.79 |
| 5 | Stanford University | education | 153 | 23,449 | 0.33 |
| 6 | Google (United States) | company | 91 | 17,200 | 0.07 |
| 7 | University of Oxford | education | 92 | 16,769 | 0.50 |
| 8 | Carnegie Mellon University | education | 99 | 16,748 | 0.25 |
| 9 | University of California, San Diego | education | 100 | 16,125 | 0.75 |
| 10 | California Institute of Technology | education | 83 | 15,264 | 0.49 |
| 11 | University of Toronto | education | 77 | 15,059 | 0.18 |
| 12 | University of Pennsylvania | education | 70 | 13,500 | 0.62 |
| 13 | École Polytechnique Fédérale de Lausanne | education | 70 | 13,195 | 0.46 |
| 14 | Howard Hughes Medical Institute | facility | 98 | 12,664 | 0.89 |
| 15 | New York University | education | 101 | 12,402 | 0.51 |

Without consolidation, MIT is first and Google (United States) is sixth; DeepMind (United Kingdom) is at rank 26, Microsoft Research (United Kingdom) at 49, Microsoft (United States) at 64 and Meta (Israel) at 76, while consolidated Meta (Facebook) is 19th. Merging of sub-entities and the paper set of the corporate rows are the two choices that separate the tables, and I keep both figures so that a reader can see each.

![The same figure with institutions left separated](../../figures/figure2_v3_openalex_separated.png)

*Figure S5.1 (`figure2_v3_openalex_separated`). Figure 3 with the OpenAlex institutions left as shipped, so Google appears as Google (United States). Same conventions as Figure 3; every institution bar sums over the top 5,000 eligible papers. Data: `results/bridge/table_s3b_institutions_separated.csv`, `author_institution_edges.csv` (25 of the 26 edges are drawn, because Hinton's Alphabet edge has no node here); regenerated by `python -m neuroai_cn.figures.figure2_bridges_v3`.*

### 4.6 The author-to-institution and paper-to-author lines

| # | Author | Current, drawn solid | Past, drawn faded |
|-:|-|-|-|
| 1 | Yoshua Bengio | none | MIT |
| 2 | Christof Koch | none | MIT, Caltech |
| 3 | Geoffrey E. Hinton | U Toronto | UC San Diego, CMU, UCL, Alphabet |
| 4 | Wulfram Gerstner | EPFL | UC Berkeley |
| 5 | Karl Friston | UCL | none |
| 6 | Aude Oliva | MIT | Harvard |
| 7 | Stephen M. Smith | Oxford | none |
| 8 | Peter Dayan | none | UCL, MIT, U Toronto |
| 9 | Eugene M. Izhikevich | none | none |
| 10 | Antonio Torralba | MIT | none |
| 11 | Laurent Itti | none | Caltech |
| 12 | Henry Markram | EPFL | none |
| 13 | Bruce Fischl | Harvard, MIT | none |
| 14 | Brian Avants | none | U Penn |
| 15 | Bruno A. Olshausen | UC Berkeley | Caltech, MIT |

I list only the institutions that appear among the fifteen shown. Ten edges are current. Sixteen are past. None comes from OpenAlex. Several authors' current employers are not among the fifteen, which is why Bengio, Koch, Dayan, Itti and Avants have no solid line, and Izhikevich no line at all. Izhikevich's career ran through Moscow State, Michigan State, Arizona State, the Neurosciences Institute and Brain Corp, and none of them is a top-15 institution, which is a small argument against reading the institution column as a map of where a bridge researcher has to be.

The eight paper-to-author lines of the figure, with the author position that I checked against publisher metadata:

| Paper (rank in Table S1) | Author (rank in Table S2) | Position on the paper | DOI of the paper |
|-|-|-|-|
| Multimodal Brain Tumor Image Segmentation Benchmark (BRATS) (1) | Brian Avants (14) | middle | 10.1109/tmi.2014.2377694 |
| Simple model of spiking neurons (3) | Eugene M. Izhikevich (9) | first | 10.1109/tnn.2003.820440 |
| Emergence of simple-cell receptive field properties by learning a sparse code (4) | Bruno A. Olshausen (15) | first | 10.1038/381607a0 |
| Computational modeling of visual attention (5) | Christof Koch (2) | last | 10.1038/35058500 |
| Computational modeling of visual attention (5) | Laurent Itti (11) | first | 10.1038/35058500 |
| Segmentation of brain MR images by hidden Markov random field and EM (8) | Stephen M. Smith (7) | last | 10.1109/42.906424 |
| A model of saliency-based visual attention (10) | Christof Koch (2) | middle | 10.1109/34.730558 |
| A model of saliency-based visual attention (10) | Laurent Itti (11) | first | 10.1109/34.730558 |

### 4.7 The concentration of bridge weight

Each entry of the next table is the percentage of all bridge weight held by the top N authors or institutions in the sensitivity bound of section 3.7, the 133,763 papers that pass the 5-and-5 gate after the entities averaging more than 400 units of B per paper are dropped. Institutions are not consolidated.

| Top N | Authors | Institutions |
|-:|-:|-:|
| 1 | 0.27 | 1.41 |
| 5 | 0.94 | 6.30 |
| 10 | 1.52 | 10.43 |
| 15 | 1.98 | 13.72 |
| 25 | 2.72 | 18.96 |
| 50 | 4.28 | 28.08 |
| 100 | 6.63 | 39.64 |
| 250 | 11.04 | 56.52 |
| 500 | 15.88 | 69.48 |
| Entities in pool | 80,898 | 5,641 |

The top 100 institutions hold 39.64 percent of all bridge weight and the top 100 authors 6.63 percent; these are the article's "nearly 40 percent" and "below 7 percent". At every tier the institutions hold several times the share of the same number of authors, and within the top 1,000 of each the Gini coefficient is 0.311 for authors and 0.568 for institutions. I have no value at the top 1,000, because dropping 298 authors or 17 institutions from the persisted top-1,000 tables leaves fewer than 1,000 entries.

The top-100 shares depend on which pool of papers they are computed over. The sensitivity bound gives the headline values above; the other pools of `results/bridge/concentration_tiers.csv` give higher ones, because the bound subtracts the weight of the highest-average entities:

| Pool of papers | Papers | Top 100 authors (%) | Top 100 institutions (%) | Institutions : authors |
|-|-:|-:|-:|-:|
| Sensitivity bound (headline) | 133,763 minus entities above 400 B per paper | 6.63 | 39.64 | 6.0 |
| Eligible papers | 58,971 | 9.53 | 44.82 | 4.7 |
| Papers with a neuroscience or AI label | 59,038 | 12.53 | 46.11 | 3.7 |
| Every paper passing the gate | 133,763 | 15.01 | 41.42 | 2.8 |

In every pool the top 100 institutions hold between 2.8 and 6.0 times the share of the top 100 authors, so the difference between the two levels of concentration does not depend on the pool, while the values themselves do.

The bound is needed because the pool of 133,763 papers holds the fusion block: before the high-average entities are dropped, one institute holds the top institution place with 3.03 percent of all weight (the National Institute for Fusion Science, according to my earlier audit, which also found that 14 of the top 15 authors were plasma physicists there; I did not recompute that here).

### 4.8 What the wider bridge set is made of

Fifteen papers make a figure, not a field. For the analysis behind the article I also looked at how the strongest thousand bridge papers divide by topic and era. Era composition, at least, I can recompute directly. Among the 1,000 strongest eligible papers, 701 (70.1 percent) were published before 2012, 115 from 2012 to 2015, 133 from 2016 to 2019 and 51 (5.1 percent) in 2020 or later; the median year is 2005. Across the eligible pool as a whole the median is 2011, so the top of the ranking is older than the pool. These counts refer to the eligible pool before the display filters of section 3.2; the top 100 of the display-filtered ranking, counted in [S6](S6-citation-age.md) section 4.5, has a median of 2002 and 3 papers from 2020 onward:

| Tier of the 58,971 eligible papers, ranked by B (no display filters) | Papers | Median year | Before 2012 | 2012 to 2015 | 2016 to 2019 | 2020 onward |
|-|-:|-:|-:|-:|-:|-:|
| Top 100 | 100 | 2002 | 75 (75.0%) | 9 (9.0%) | 10 (10.0%) | 6 (6.0%) |
| Top 1,000 | 1,000 | 2005 | 701 (70.1%) | 115 (11.5%) | 133 (13.3%) | 51 (5.1%) |
| All eligible papers | 58,971 | 2011 | 31,459 (53.3%) | 8,412 (14.3%) | 10,449 (17.7%) | 8,651 (14.7%) |

My earlier analysis went further. I clustered the top 1,000 papers of the unfiltered pool on a co-citation graph with a community-detection algorithm, removed 140 papers in physics subfields (I read their titles as fusion-experiment diagnostics) and labeled the clusters by hand into ten tracks. Here I recounted the persisted labels and did not repeat the clustering. This set is not the eligible pool: it keeps 324 papers labeled other and 76 above the ceiling, so it contains works such as ResNet and the R language that the ranking above excludes.

| Track | Papers | Share (percent) | Mean B |
|-|-:|-:|-:|
| Foundational DL/AI | 350 | 40.7 | 723 |
| Cognitive neuroscience | 157 | 18.3 | 461 |
| Statistical methods | 115 | 13.4 | 771 |
| Other | 103 | 12.0 | 759 |
| Neuroengineering / hardware | 54 | 6.3 | 603 |
| Applied ML for brain | 38 | 4.4 | 750 |
| Bio-plausible AI | 15 | 1.7 | 532 |
| Molecular / cellular neuro | 13 | 1.5 | 753 |
| Medical imaging methods | 11 | 1.3 | 508 |
| Bridge manifestos & theory | 4 | 0.5 | 602 |

| Paper type | Papers | Share (percent) |
|-|-:|-:|
| research | 713 | 82.9 |
| methods | 109 | 12.7 |
| review | 38 | 4.4 |

| Era of publication | Papers | Share (percent) | Mean B |
|-|-:|-:|-:|
| Before 2012 | 604 | 70.2 | 651 |
| 2012 to 2015 | 97 | 11.3 | 822 |
| 2016 to 2019 | 116 | 13.5 | 651 |
| 2020 onward | 43 | 5.0 | 720 |

Because the track labels are hand labels on automatically found clusters, only the counts mean anything, and other boundaries would give other counts. In my reading two statements survive in both sets of figures. The canon is old, with about 70 percent of the strongest papers predating 2012 and 5 percent from 2020 or later. And papers that announce or theorize the merger are a handful: four in the 860, with publication years 1999, 2001, 2004 and 2019 (predictive coding in visual cortex by Rao and Ballard, Dayan and Abbott's *Theoretical Neuroscience*, the Bayesian brain review by Knill and Pouget, and Richards and colleagues' deep-learning framework for neuroscience).

## 5. Caveats and what this does not show

Citation is not influence. My score rewards a paper for being cited by both fields and cannot separate the paper that gave a field an idea from the one that gave it a function call. A tool-heavy top fifteen is partly a reading of that limit and partly a fact about the world; my defense is that the difference between citing a paper for its idea and for its software is what the figure is meant to expose.

What the ranking measures is works that both fields cite heavily. It does not measure what AI takes from neuroscience: a paper that AI cites often and neuroscience seldom scores low however much it shaped AI, and a concept absorbed so thoroughly that nobody cites it any more does not appear. What flows from neuroscience into AI, and which neuroscience it is, are in [S4](S4-what-ai-cites.md). [S6](S6-citation-age.md) takes up the objection that old papers lead because citations take time to accumulate; the age controls and their results are in S6.

Author disambiguation is inherited from OpenAlex. Authors are identified by its `author_id`, with no manual consolidation. Spot checks on the canonical names came out right, and I did not audit the rest systematically; a split identity lowers an author's sum and a merged one raises it. Institution assignment follows the affiliation strings printed on each paper and OpenAlex's matching of them. I checked the lines between authors and institutions by hand, and not the institution bars.

Corporate groups are the rows I am least sure of, because the grouping matches names in the top-100 institution table: subsidiaries without a group name (LinkedIn, GitHub, Waymo, Verily) are not merged, and a sub-entity that ranks below the top 100 or an affiliation printed under another name is not counted. Companies count in full for a paper when any author lists them, so large collaborations inflate a group as they inflate a university. The institutions column mixes two bases, with the company rows summed over every paper that passes the 5-and-5 gate and the university rows over the top 5,000 eligible papers, so the order across the two kinds of row depends on that choice. The concentration figures (39.64 and 6.63 percent) are the values of the sensitivity bound described in section 3.7, and section 4.7 gives the shares in the other pools.

Full credit goes to every author and institution on a paper, so large collaborations inflate their authors and institutions; a fractional variant would give a different and equally defensible order, and I did not compute one. Gini coefficients within the top 1,000 measure inequality among the already successful, not across everyone who bridged. An all-time ranking is insensitive to the unstable 2024 to 2025 records, but any statement about recent bridge papers is not. Finally, the thresholds (five citations per side, 10,000 for the ceiling), the paper-type filter, the affiliation rules and the tool and concept coding are choices. They are documented. But another analyst applying different rules would get a different figure from the same data.

## 6. Reproduce

Every table and figure of this supplement, and every number in its text, runs from the CSV files I committed under `results/bridge/`:

```bash
# Figure 3 and its separated variant (read only results/bridge)
.venv/bin/python -m neuroai_cn.figures.figure2_bridges_v3

# every number in this supplement, checked against the results files
.venv/bin/python -m pytest -q tests/test_supplement_claims.py tests/test_bridge_tables.py
```

These steps need the heavy data (the local OpenAlex snapshot and its derived tables under `NEUROAI_DATA`, see `src/neuroai_cn/config.py`):

```bash
# Tables S1 to S3, edges, links, concentration tiers (re-exports results/bridge/)
.venv/bin/python -m neuroai_cn.analysis.export_bridge_tables

# eligibility funnel, ceiling effect, era composition, clustered-set composition, worked examples
.venv/bin/python -m neuroai_cn.analysis.export_bridge_pool
```

The persisted inputs of those exports come from `neuroai_cn.audits.q4_v3_extended` (scoring), `author_inst_bridge` and `author_inst_top1000` (aggregation), `institution_consolidation`, `clustering_pipeline`, `q4_reclassify_v2` and `authors_vs_institutions`. Affiliations live in the table `neuroai_cn/audits/affiliations_overrides.py`. Since the snapshot is frozen, a re-run should reproduce these numbers exactly.

## 7. Related

- [S1. Data, corpus and field classification](S1-data-and-classification.md): the snapshot and the labels that decide which citations count as neuroscience or AI.
- [S2. Citation flow](S2-citation-flow.md) and [S3. Counts, shares and field sizes](S3-counts-and-field-sizes.md): the aggregate direction that this supplement opens up.
- [S4. What AI cites in neuroscience](S4-what-ai-cites.md): what AI takes from neuroscience, which the bridge ranking does not measure.
- [S6. Does citation age explain the bridge canon?](S6-citation-age.md): the same ranking by citations per year, in an equal window and normalized for growth, with its own tool and concept coding.
- [Methods 05, the bridge metric](../methods/05-bridge-metric.md): the formal definitions, validation tiers and decision log.

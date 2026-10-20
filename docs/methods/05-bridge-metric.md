# The bridge metric

This file covers Q4: how an individual paper's standing as a bridge between neuroscience and AI is scored, which papers are admitted and filtered, how scores are aggregated to authors and institutions, and how I verified the author-to-institution relationships in the figure. It does not report the resulting rankings, which are in the article and in [S5](../supplements/S5-bridge-builders.md); the question of whether citation age explains the old canon at the top of the ranking is [S6](../supplements/S6-citation-age.md).

## 1. The score

For each paper *p*, take `c_neuro(p)` and `c_ai(p)`, the counts of citations it receives from neuroscience-labeled and AI-labeled works under the extended classifier described in [field classification](02-field-classification.md), and score it by their harmonic mean:

```
B(p) = 2 · c_neuro(p) · c_ai(p) / (c_neuro(p) + c_ai(p))
```

Harmonic means punish imbalance brutally, which is exactly the wanted property. A paper cited 1,000 times by AI and twice by neuroscience scores 3.99, whereas one cited 100 times by each side scores 100. Field superstardom buys nothing; only legibility to both audiences does.

**The score is computed over raw counts, not normalized shares.** The implementation (`materialize_full()` in `src/neuroai_cn/audits/q4_v3_extended.py`, SQL expression `2.0 * c_neuro * c_ai / (c_neuro + c_ai)`) uses raw counts, and every published B value is a raw-count harmonic mean, so the units are citations rather than shares. The normalized variant exists in the code as a separate diagnostic. I did not re-run it for the current supplements, so I quote no agreement between its ordering and the published one ([S5, section 3.1](../supplements/S5-bridge-builders.md)).

## 2. The admission gate

A paper enters the candidate pool if it has **at least five classified citations from each side**: `c_neuro ≥ 5` **and** `c_ai ≥ 5`. There is no year-span condition. That gate yields **133,763 papers** under the extended classifier, a count I verified by loading the pipeline output and counting rows. The production run under the strict 35-topic core yields 128,956 candidates, and the two numbers should not be confused. The gate hardly matters for the top of the ranking: B can never exceed twice the smaller of the two counts, so any paper with B above 1,396 (the fifteenth paper of the published table) has at least 698 citations from each side ([S5, section 3.2](../supplements/S5-bridge-builders.md)).

An earlier methods note attached the number 133,763 to a filter description it does not belong to, saying that "the E2 filter" requires ten citations on both sides plus distribution across five calendar years. Neither half is right. The gate is five per side with no year condition; E2 is a separate, later step described in section 3.

## 3. Two filter variants

The variants are **alternatives, not a sequence**, and each is ranked separately.

**E1, ubiquity-normalized.** Divide the score by the log of the paper's total classified citations, discounting papers that are simply cited by everyone:

```
B_norm_E1(p) = B(p) / log(1 + c_total_classified(p))
```

Reported in the outputs as `B_norm_E1`.

**E2, ubiquity-filtered.** Two rules, applied in this order, define the eligible pool:

| Step | Papers remaining | Removed |
|-|-:|-:|
| gate: at least 5 classified citations from each side | 133,763 | 0 |
| own field label neuroscience or AI (drops `other` and unknown) | 59,038 | 74,725 (74,485 `other`, 240 unlabeled) |
| total classified citations under 10,000 (the E2 ceiling) | 58,971 | 67 (66 AI, 1 neuroscience) |

Running E2 on the candidate pool leaves **58,971 papers**, the number to use; an earlier note reported 59,211. Of the candidates, 133,763 pass the gate and these 58,971 remain after the eligibility filters; the article's "roughly 59,000" refers to them ([S5, section 3.2](../supplements/S5-bridge-builders.md)).

The two rules do different jobs. The field-label rule is the one that removes the cluster of plasma-physics papers from the Large Helical Device fusion experiment, which acquire high harmonic scores through sheer citation volume in a literature unrelated to either field under study: the `other` bucket alone holds 74,485 of the 133,763 candidates, mostly physics and general-science papers whose harmonic mean is incidentally high. Only papers already labeled neuroscience or AI fall to the ceiling, mostly general machine-learning works such as ResNet, scikit-learn, LIBSVM, LSTM, Adam and random forests; 26 of the 67 score above the fifteenth paper of the published table. It is a round number, not an estimate, and I did not test other thresholds ([S5, section 4.2](../supplements/S5-bridge-builders.md)). The label rule has a cost as well, because the label `other` also covers work I would want, such as the R language and the U-Net network.

For the top bridge papers in the article's figure I use the E2-filtered ranking by raw `B_harmonic`, subject to the paper-type filter of section 4.

## 4. The paper-type filter

My audit of 2026-05-22 found `book-chapter` entries in the top-15 ranked bridge papers (among them Duda, Hart and Stork's *Pattern Classification*), which the methodology was always supposed to exclude, since books and pre-DOI works are out of the citation graph per decision D2. I therefore restrict the top-N panel to OpenAlex `type ∈ {article, review}`, that is, peer-reviewed scientific output. Books, book chapters, datasets, dissertations, paratext and everything else I drop. The displayed ranking also drops ebook-platform and book-series sources, empty titles, duplicate titles and three book titles I listed by hand; among the 40 best eligible candidates, 7 are removed by these rules and the table keeps the first fifteen of the 33 that remain ([`results/bridge/s1_eligibility_check.csv`](../../results/bridge/s1_eligibility_check.csv)). Implementation: `src/neuroai_cn/audits/filter_papers_only.py`, with the committed table built by `python -m neuroai_cn.analysis.export_bridge_tables`.

Papers whose own field label is `other` are excluded from the panel for the same reason they are excluded by E2. Title-level deduplication keeps the highest-B representative where OpenAlex emits several `work_id`s for the same work.

## 5. Aggregating to people and places

An author's bridge weight is the **sum of B over the bridge papers they co-authored**. An institution's is the sum over the bridge papers carrying an affiliation to it. I fractionalize neither: a paper contributes its full B to every author and institution credited on it. Alongside the sums I report paper counts, so a single blockbuster inflating someone's total stays visible.

I compute the figure's author and institution columns over the **top 5,000 eligible bridge papers** rather than over the whole pool, which is a computational compromise rather than a principled choice. The one exception is the corporate rows of the consolidated institution table, which were summed over the whole 133,763-paper pool (section 6). The persisted outputs are the top 200 authors and top 100 institutions, each carrying: number of E2-filtered bridge papers, ∑B, mean B, max B, and total citations from each field.

Author identity is OpenAlex's disambiguated `author_id`, with no further consolidation. Institution identity is OpenAlex's `institution_id`, with the single deliberate exception in section 6. `institution.type` (one of `education`, `company`, `facility`, `healthcare`, `government`, `nonprofit`, `funder`, `other`) is carried through and drawn as a badge beside each institution bar in the figure (EDU education, IND industry, which is the OpenAlex `company`, FAC facility, GOV government, HC healthcare, NP nonprofit), so industry and private-sector institutions are explicitly visible rather than filtered out.

Institution rank is computed from **paper affiliations**, not from where the named top authors work. An institution can therefore rank highly on brokerage alone while carrying little or no author edge, and two do exactly that in the published figure: the Howard Hughes Medical Institute has no author line at all, and the University of Pennsylvania has only a faded one, from Avants.

Color encoding everywhere is `neuro_share = c_neuro / (c_neuro + c_ai)`; for an author or an institution the two counts are first summed over its bridge papers, so the share is the sum of the neuroscience citations over the sum of the citations from both fields. The scale diverges from teal at 0, meaning read almost entirely by AI, through a neutral middle, to gold at 1, meaning read almost entirely by neuroscience.

## 6. Corporate-group consolidation

OpenAlex treats Alphabet-group sub-entities as separate institutions, namely Google (United States), Google (United Kingdom) and DeepMind (United Kingdom), and does the same for Microsoft and Meta. For the main figure these are consolidated into parent groups, a choice I locked on 2026-05-22.

| Parent group | Matching pattern on institution name | Canonical ID |
|-|-|-|
| Alphabet (Google + DeepMind) | `^Google` · `DeepMind` · `^Alphabet` | `ALPHABET_GROUP` |
| Microsoft | `^Microsoft` | `MICROSOFT_GROUP` |
| Meta (Facebook) | `^Meta` · `^Facebook` | `META_GROUP` |

I consolidate at the **paper level**, not by summing child rows: for each bridge paper, the set of institution IDs it is affiliated with is deduplicated, and a paper contributes **once** to a parent's totals even when it carries authors at several sub-entities of that parent. The consolidated totals are therefore not double-counts. Implementation: `src/neuroai_cn/audits/institution_consolidation.py`.

Consolidation is an editorial choice and it changes the headline, so I preserve the **OpenAlex-separated view as a supplementary figure** in full. Under separation, MIT remains first and Google (United States) sits at sixth, with DeepMind (UK), Microsoft Research, AT&T and Meta elsewhere in the top 100. Under consolidation the top three become Alphabet (∑B = 63,142, n = 924), Microsoft (∑B = 35,557, n = 712) and MIT (∑B = 35,338, n = 220). The two kinds of row are summed over different paper sets: the corporate groups over all 133,763 papers that pass the 5-and-5 gate, including papers labeled `other` and papers over the ceiling, and every other institution over the top 5,000 eligible papers ([S5, sections 3.3 and 4.5](../supplements/S5-bridge-builders.md)). The sub-entities of each group are those that match its pattern in the top-100 institution table.

## 7. Affiliation verification

The bridge figure names fifteen living researchers and fifteen institutions and asserts employment relationships between them. That is the most reputationally exposed thing in the piece, so it received the most scrutiny.

### 7.1 Why the OpenAlex affiliations were discarded

My first version drew author-to-institution edges from OpenAlex `last_known_institutions`. The result was unusable, and it failed in two distinct ways.

**Name collisions produced confident nonsense.** Brian Avants resolved to "California University of Pennsylvania", a real but entirely unrelated school whose name happens to contain the same string his genuine Penn affiliations contain. Christof Koch resolved to the "Gere Foundation". Antonio Torralba resolved to Citigroup and to Dominica State College. Yoshua Bengio resolved to a "Centre Universitaire de Mila" in Algeria, which shares a name with the Montreal institute and nothing else.

**Co-authorship pseudo-affiliations produced plausible nonsense, which is worse.** Peter Dayan picked up an HHMI affiliation inherited from Terry Sejnowski through Salk-era joint papers. Stephen Smith picked up "Harvard 1950", a parse error. A spurious Avants-and-Markram edge to the University of Pennsylvania appeared in an intermediate render and is not in the final table.

None of these survived checking. Every one is listed with its rejection reason in the per-edge audit record. `last_known_institutions` is not used anywhere in the published figure.

### 7.2 What replaced them

I verified all fifteen authors by hand in May 2026 through a five-way research fan-out with a fixed source priority: **ORCID employment records first, then official university, lab or institute pages, then Google Scholar verified affiliations, then the researcher's own homepage or CV, then LinkedIn** (which is author-curated and genuinely reliable for industry roles and dates), with Wikipedia as cross-check only. Every drawn edge is backed by at least one authoritative source, with dates, roles and source URLs recorded per edge.

That produced **26 edges: 10 current and 16 past**, a count confirmed against the curated data file rather than against prose. Current affiliations are drawn as solid curves, past affiliations as faded ones, so a single researcher's career can be traced across several nodes. Implementation: `CURATED_AFFILIATIONS` in `src/neuroai_cn/audits/affiliations_overrides.py`, written to `author_current_affiliations_curated.parquet`. I retain an alternative cumulative author-institution co-occurrence table as a sensitivity check.

### 7.3 Editorial policy on affiliations

I applied four rules uniformly so that nobody gains or loses an edge through inconsistency.

1. **Research affiliations only.** PhD, postdoc, faculty, director, visiting researcher and industry research all qualify. Taught degrees do not, which removed Bruno Olshausen's Stanford BS and MS. Non-research clinical training does not, which removed Karl Friston's early Oxford psychiatry rotation. Either would have added an edge that overclaims the connection.
2. **Only the canonical top-15 institutions can appear.** Affiliations to institutions outside that node set (Mila and Université de Montréal, the Allen Institute, MPI Tübingen, USC, Brain Corp, Weizmann, Salk, the University of Virginia) are deliberately not drawn. Several of the named authors' *current* employers are therefore absent from the figure, by design.
3. **HHMI carries no author edge**, because no HHMI Investigator appointment could be verified for any of the fifteen. It ranks on paper brokerage alone.
4. **Genuine dual current affiliations are drawn as such**, so Bruce Fischl's Harvard Medical School and MIT CSAIL positions are both solid. Hinton's Google position is drawn to the consolidated Alphabet node and therefore appears in the main figure only, not in the separated variant.

### 7.4 Paper-to-author links

The pipeline's own link file holds 100 paper-to-author rows and has none for SciPy or XGBoost, so I recomputed the links from the OpenAlex authorship lists of the fifteen papers ([`results/bridge/paper_author_links.csv`](../../results/bridge/paper_author_links.csv)). Eight connect a top-15 paper to a top-15 author, and those eight are the ones the figure draws; they agree with the pipeline's file. I checked all eight position assertions against Crossref and OpenAlex publisher metadata, and all eight are correct, including the two high-risk cases, where Avants is genuinely fifteenth of sixty-eight on the BRATS consortium paper and correctly typed as middle, and Koch is genuinely last on the 2001 review but middle on the 1998 saliency paper, so his two curves correctly differ in thickness.

Curve thickness encodes authorship position as a multiplicative weight: **last or corresponding 2.0, first 1.5, middle 1.0**. This affects the drawing only and never the ranking.

## 8. Clustering the bridge corpus

The clustering is a separate analysis that does not feed the figure. It took the top 1,000 papers of the **unfiltered** pool, removed 140 papers in physics subfields (I read their titles as fusion-experiment diagnostics), and clustered the remaining 860 with a community-detection algorithm (Leiden; Traag, Waltman and van Eck 2019) on a citation-similarity graph derived from co-citation patterns; the modularity was 0.76, which I have not re-checked. I used UMAP for two-dimensional layout **only** and clustered on the citation graph, not on the UMAP coordinates. After inspecting the top-cited works in each cluster I assigned the cluster labels by hand, yielding ten tracks: Foundational DL/AI, Cognitive neuroscience, Statistical methods, Other, Neuroengineering / hardware, Applied ML for brain, Bio-plausible AI, Molecular / cellular neuro, Medical imaging methods, and Bridge manifestos & theory. The set is not the eligible pool: it keeps 324 papers labeled `other` and 76 above the ceiling. I recounted the persisted labels for [S5, section 4.8](../supplements/S5-bridge-builders.md) and did not repeat the clustering, so only the counts mean anything.

## 9. Validation tiers

Decision E5 fixes a two-tier validation set. I defined failure at Tier 1 in advance as a stop condition.

**Tier 1: required in the top 50 bridge papers. Failure means the classifier is broken.**

| Paper | DOI |
|-|-|
| Zador et al. 2023, *Nature Communications* | [10.1038/s41467-023-37180-x](https://doi.org/10.1038/s41467-023-37180-x) |
| Richards et al. 2019, *Nature Neuroscience* | [10.1038/s41593-019-0520-2](https://doi.org/10.1038/s41593-019-0520-2) |
| Hassabis et al. 2017, *Neuron* | [10.1016/j.neuron.2017.06.011](https://doi.org/10.1016/j.neuron.2017.06.011) |
| Kriegeskorte and Douglas 2018, *Nature Neuroscience* | [10.1038/s41593-018-0210-5](https://doi.org/10.1038/s41593-018-0210-5) |

All four are present in the snapshot. The fifteenth paper of the published ranking scores 1,396 and the hundredth 558.59. In the committed ranking ([`results/citation_age/ranking_orig_top100.csv`](../../results/citation_age/ranking_orig_top100.csv)) none of the four is in the top 100: Hassabis 2017 scores 463.22 (393 citations from neuroscience, 564 from AI) and Richards 2019 scores 334.45 (568 and 237), and they reach the top 100 only under some of the age controls of [S6](../supplements/S6-citation-age.md). By the criterion as I wrote it, which required all four in the top 50, the Tier-1 check is not met on the published ranking. Either the criterion referred to a different ranking or the stop condition I defined in advance should have fired; I have not resolved which, and I flag it as an open item. It bears on the S6 question of whether bridge works of the last two decades are missing for reasons of age.

**Tier 2: desired in the top 200. Failure is acceptable and flagged as a caveat.** Yamins et al. 2014 *PNAS*; Marblestone, Wayne and Körding 2016 *Frontiers in Computational Neuroscience*; Doerig et al. 2023 *Nature Reviews Neuroscience*; Schultz, Dayan and Montague 1997 *Science*; Bowers et al. 2023 *BBS*; Mante, Sussillo, Shenoy and Newsome 2013 *Nature*; Hopfield 1982 *PNAS*; Rumelhart, Hinton and Williams 1986 *Nature*; Marr 1982 *Vision*; McCulloch and Pitts 1943; Lillicrap et al. 2016 *Nature Communications*; Wang et al. 2018 *Nature Neuroscience*. The last four enter the citation graph only through citing works, per decision D2.

A separate utility-paper diagnostic tracks where generic tools rank under each variant (scikit-learn, the R citation, LSTM 1997, Random Forests 2001, Sutton and Barto 1998, Adam 2014, the Cortes-Vapnik SVM 1995, Dropout 2014 and ResNet 2016) because a bridge metric that puts software citations at the top is measuring ubiquity rather than brokerage. That table is what motivated the E1 and E2 variants.

## 10. What the metric cannot see

A citation records acknowledgement, not debt, and cannot distinguish a foundational idea from a software citation. I did not remove self-citations. Author and institution identity rest entirely on OpenAlex's upstream disambiguation, which is why I had to rebuild the affiliation edges in the figure by hand. Aggregating over the top 5,000 papers rather than the full E2 pool is a compromise that could in principle change the tail of the author and institution rankings, though not the head. And the whole construction rewards papers that are *cited* by both fields, which is not the same as papers that *do* work in both fields: a paper can be a bridge in the citation graph while making no claim about the other field at all.

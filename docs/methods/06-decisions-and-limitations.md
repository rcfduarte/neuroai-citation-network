# Decisions and limitations

This file is the decision registry: every choice that was locked before the corpus was pulled, stated with its rationale, followed by the scope of the analysis, the gaps I know about, and the limitations I would want a critic to start from. It does not repeat the operational detail of those decisions: that is in the other four files, and each entry points at the right one. The six supplements are indexed in [`../supplements/README.md`](../supplements/README.md).

I locked the decisions on **2026-04-29** in a versioned foundation document, before I built any corpus and before I computed any odds ratio. The revision policy was that material contradictions produce a new version rather than an in-place edit, so where implementation later diverged from a locked decision the divergence is recorded rather than hidden. Every such divergence is marked below.

## Group A — structural confirmations

**A1. I reframed predictive coding and the free energy principle as theories of cortical processing, not merely theories of learning.** They make claims about how cortex represents and infers, which is broader than a learning rule, and treating them as learning theories would have mis-scoped the keyword templates that target them.

**A2. I restructured Pool 2's super-families** into: A, cortical processing theories plus plasticity and learning theory; B, representational and sensory-cortex modeling; C-decision, reinforcement learning and world models; C-language, the cognitive neuroscience of large language models; C-higher-cognition, cognitive maps and Bayesian program induction and planning; D, hardware and substrate. The original single "C" family conflated decision-theoretic work with language work with higher cognition, three literatures with different vocabularies and different citation neighborhoods. I moved cognitive maps out of C-decision and into the representational and higher-cognition family, because grid and place cell work is read as representation rather than as decision-making.

**A3. Memristor and optical implementations are real neuromorphic hardware, so they are not on the false-positive exclusion list.** Ant-colony and particle-swarm methods are bio-metaphor optimization and are excluded; memristor and optical implementations are the physical substrate of a research program this analysis is directly about. Consequence: the T6 trap in [Pool 2](01-corpus-and-pools.md) no longer excludes them.

**A4. I renamed Pool 3's third sub-pool from "ambiguous" to "mixed/intersection", added a fourth general-high-impact sub-pool with *Science*, *Nature* and PNAS named explicitly, expanded both core lists, and split conferences into their own sub-list with founding years.** "Ambiguous" implied a defect in the venue; the venues in question are genuinely intersectional and that is a property worth naming correctly. Multidisciplinary venues needed their own bucket because venue membership carries no field information for them; they are resolved by the topic and Semantic Scholar schemes instead.

**A5. Computational cognitive science and the Bayesian brain are separate factions (F8 and F8b), and I extended the sensory-hierarchy faction beyond vision to audition and hierarchical composition.** Lumping Tenenbaum-Griffiths Bayesian cognition with Gershman-Lake computational cognitive science would have merged two communities that cite each other much less than the shared label suggests. The vision-only framing of sensory hierarchies excluded the auditory work (Kell 2018) and the hierarchical-timescale work, which belong to the same program.

## Group B — faction-level taxonomy

**B1. I treat skeptics and measured critics as a single faction with four internal sub-tiers**: polemicists, polemicist-adjacent, measured external, and measured internal plus methodological anchor. Thirteen roster entries, eighteen individuals. Splitting them into separate factions would have implied more coherence among critics than exists; collapsing the sub-tiers would have equated a Substack polemic with a peer-reviewed formal argument. The full roster and the sub-tier assignments are in [corpus and pools](01-corpus-and-pools.md), section 6.

**B2. I treat AI safety and interpretability via neuroscience as its own faction**, not a sub-branch of the brand wing. Its methods — representational similarity, population manifolds, sparse coding, attribution graphs — come from systems neuroscience, and several of its practitioners hold neuroscience PhDs, so it is a genuine methodological transfer rather than a rhetorical one.

**B3. I include Anthropic's mechanistic-interpretability program, with an analogy-versus-methodology subscore.** The distinction being scored is whether a researcher is importing neuroscience *methods* or neuroscience *metaphors*. Bricken, Lindsey and Olsson, with neuroscience or brain-and-cognitive-sciences training, are clearly methodology. Olah, Jermyn and Elhage, without neuroscience backgrounds, are clearly analogy. Borderline cases are flagged rather than forced. The methodology spectrum tracked is: representational similarity analysis and centered kernel alignment, population manifolds, dynamical-systems decomposition, sparse coding to sparse autoencoders (the Olshausen-Field to Bricken line), attribution graphs, probing and encoding models, kernel comparisons, information-theoretic decomposition, persistent-activity and attractor analyses, and neural-tangent-kernel comparisons.

**B4. I place Hawkins in the brand wing with an alternative-architecture flag**, dual-tagged into Pool 1 by signature. He signed the anchor whitepaper, so he is inside the brand by his own act, but Thousand Brains and HTM are a genuinely different architectural proposal and flattening that would lose information.

**B5. I do not treat cortical chemoarchitecture as a faction.** Most chemoarchitecture work is anatomy without a functional, computational or learning connection, and so fails the cross-pool hard rule that seed authors from classical neuroscience must have demonstrated functional work. The Kording et al. 2026 function-to-molecular-microarchitecture paper is the only seedling of a substantive bridge. It is discussed in the article as a gap in the field rather than represented as a corpus row.

## Group C — authorial position

These are disclosure decisions rather than methodological ones. I am not a neutral observer of this field, and stating where I sit seems better than pretending otherwise.

**C1. My own position in the taxonomy** is theoretical and computational neuroscience, plus biologically-plausible learning, plus a lighter weighting on the cybernetics lineage. That is a "disciplined NeuroAI" position, distinct from both the booster wing and the polemical skeptics, and it is a position with stakes in the outcome.

**C2. A separate research project of mine that touches this territory was ruled off-record** and is not surfaced in the piece, because its relevance is task-specific rather than argumentative.

**C3. An earlier long-form opinion piece of mine on machine intelligence is repurposed with a caveat**: the argument that we need to explain the brain stands, but it is qualified by acknowledging that NeuroAI is also applied machine learning, which does not strictly require explanatory power to be worth doing.

**C4. The AI-safety wing is curated thoroughly rather than sampled**, including a careful reading of the Mineault et al. 2024 whitepaper and its relation to whole-brain-emulation arguments and to alignment-via-representational-similarity claims.

**C5. The "fundability versus biological truth" sociology is in the piece**, because it bears directly on the explanatory-power argument and on the difference between understanding biology and reproducing surface statistics.

## Group D — scope

**D1. Time window: 1990 to May 2026 by publication date.** 1990 is early enough to cover the connectionist aftermath and the whole of the modern era while staying inside the range where OpenAlex indexing is dense. In the analyses I report 1990–2025 and exclude 2026 everywhere as incomplete. The article's Q1 figure starts at 1995 because 1990–92 rest on a few hundred cross-field citations each.

**D2. I exclude books and pre-DOI works from the citation graph and include them in qualitative discussion.** They have no stable identifier in OpenAlex and would be counted inconsistently. Lineage still enters, through post-1990 papers by the same authors and through works that cite the books. This is why Marr 1982, the PDP volumes, Wiener 1948, Hebb 1949, McCulloch and Pitts 1943 and Braitenberg 1984 appear in the validation tiers as "via citing works" rather than as graph nodes, and why several classical figures are absent from the Pool 4 seed lists.

**D3. I seeded Asian and German classical NeuroAI explicitly** (Amari, Doya, Kawato, Bethge, Macke as authors; Bernstein, Tübingen, RIKEN, OIST and ATR as institutional and venue anchors), because an English-language corpus built without deliberate seeding would have under-represented both traditions relative to their actual contribution.

**D4. I limit the language scope to English-indexed works** and flag it as a limitation. Estimated 5–15% of Asian and East-European NeuroAI is under-counted. D3's seeding partly mitigates it for the institutions and authors named; Asian-language-only papers are simply excluded.

**D5. I set the brand-era cutoff at 2019 by default**, with the label first counted in 2018 and sensitivity checks at 2020 and 2022. 2019 is when the label starts appearing in program names and job adverts rather than only in individual papers.

## Group E — method

**E1. I establish field membership three ways and report each separately with their agreement**: OpenAlex topics as the primary scheme, the Pool 3 venue whitelist, and Semantic Scholar fields of study. One scheme alone would make the whole analysis hostage to one classifier's idiosyncrasies. See [field classification](02-field-classification.md), section 5. **Divergence from the locked text:** E1 as locked specifies "AI = subfield 1702". The implemented primary scheme is the extended classifier: 1702 minus 26 topics, plus 1707, plus T10502. That is a methodology change. But it was surfaced for sign-off rather than swapped in silently, and the strict 35-topic core is carried through the whole pipeline as a counterfactual. I also computed schemes 2 and 3 on a validation anchor set rather than corpus-wide, because corpus-wide Semantic Scholar lookup would need 398 million API calls.

**E2. I normalize cross-citation as a per-field per-year outbound-citation fraction against a null model proportional to field size**, in the Rafols and Leydesdorff tradition, reported as an odds ratio. Raw cross-citation counts cannot separate "a field developed an appetite" from "the target field grew almost tenfold". See [the citation metric](03-citation-metric.md) and, for the raw view and why the share and the odds ratio answer different questions, [S3, section 4.6](../supplements/S3-counts-and-field-sizes.md).

**E3. The dual-citizen threshold is not a single number.** The primary reading is an empirical heavy-tail break in the publication-count distribution; robustness comes from a percentile sweep and from co-authorship brokerage with no fixed threshold. All three are reported. Committing to one threshold a priori would have made the headcount an artifact of the threshold. **As implemented**, the census reports three explicit thresholds: A, at least one paper in each field ever in any author position, 418,409 authors; B, the headline, at least three first- or last-author papers in each field inside a ten-year rolling window, 19,226 authors; C, at least five under the same conditions, 6,680 authors. No sentence of the article and no supplement uses the dual-citizen census, and its counts come from `q2_summary.json` in the heavy derived-data tree (`$NEUROAI_DATA/data/derived/`), not from a committed result file. Author identity is OpenAlex `author_id`, and the surname-collision flags from Pool 4 are propagated. I apply three cleaning rules in the v3 pipeline: I reject placeholder author IDs, I reject non-human entities (journals, presses, universities matched by regex), and I demote superclusters (over 1,000 papers across more than five distinct institutions, which are almost always disambiguation failures) rather than dropping them.

**E4. I define the bridge-paper metric as the harmonic mean of neuroscience-side and AI-side citation counts**, reported as a top-10 overall plus top-5 per era. **As published:** the figure shows the top 15 papers, authors and institutions, there is no per-era top 5, and the era composition of the eligible pool is a table in [S5, section 4.8](../supplements/S5-bridge-builders.md). The harmonic mean penalizes imbalance, which is precisely the property a bridge score needs. See [the bridge metric](05-bridge-metric.md).

**E5. I validate in two tiers**, with four Tier-1 papers whose absence from the top 50 I defined in advance as a stop condition. **Open item:** none of the four is in the top 100 of the committed ranking; see [the bridge metric](05-bridge-metric.md), section 9, which also has the full list.

**E6. I cluster with Leiden on a bibliographic-coupling graph as primary, with Infomap as a robustness check on a different theoretical basis, and normalized mutual information between the two partitions as a stability indicator.** The direct-citation graph is used separately for the Q1 field-level flow, because clustering is a paper-level question and flow is a field-level one. **Divergence from the locked text:** the shipped analysis clusters the top 1,000 papers of the unfiltered pool, less 140 fusion-physics papers, with Leiden on a co-citation-derived similarity graph (modularity 0.76, not re-checked), does not feed the figure ([the bridge metric](05-bridge-metric.md), section 8), and the Infomap robustness run and the sixteen-faction validation were not carried through to any published number. The sixteen *a priori* factions remain an interpretive scaffold and an input to roster construction; they are not an input to any reported statistic, and no reader should treat them as a validated community structure.

**E7. Data strategy: I use a full local OpenAlex snapshot, converted to year-partitioned parquet with a DuckDB index, and I reserve API access for top-N lookups and triangulation.** Rate limits make corpus-scale API work impossible, and a frozen local copy is what makes every number regenerable. I use Semantic Scholar only for the triangulation and the cross-source replication.

## Cross-pool hard rules

**Functional-connection rule.** Any seed author drawn from classical molecular, cellular or circuits neuroscience must have demonstrated functional work connecting to computation, learning or cognition. Pure-anatomy figures are filtered out. This is what removes chemoarchitecture from the pools, and I applied it when I compiled the rosters, not in code.

**Disambiguation rule.** Surnames with known OpenAlex collisions require ORCID, institution or DOI verification before their publication counts are trusted. Six surnames are flagged in code: Aertsen, Engel, Wang, Anderson, Wilson, Smith. Raw surname matches inflate counts substantially.

**Overlap rule.** I report pool membership overlap and never collapse it. Where NeuroAI work shows up across pools is itself evidence.

## Limitations

### Live limitations that matter most

**The level ordering of the two lines in Figure 1 and the teal slope before 2020 depend on how widely AI is defined.** This is the most serious methodological issue in the analysis and it is treated at length in [field classification](02-field-classification.md), section 3, and in [S2, section 5](../supplements/S2-citation-flow.md). In short: the extended classifier cannot be justified by saying subfield 1702 exiles eighteen canonical AI anchors, naming LeCun-Bengio-Hinton 2015, Hassabis 2017, Loihi, SpiNNaker and e-prop. That argument is partly circular, because Hassabis 2017 is a NeuroAI position piece, Loihi and SpiNNaker are neuromorphic engineering, and e-prop could be filed as neuroscience — these are boundary objects whose field membership is precisely what the analysis is measuring, so they cannot be used to fix the boundary. Only the LeCun review is uncontroversially AI. The anchors are also not the content: in 2023 subfield 1702 taken whole holds 300,319 works (187,603 after the 26 exclusions) against the extended definition's 346,525, so the extension adds about 159,000 works a year that are overwhelmingly computer vision and neuromorphic hardware, 45.9% of the extended corpus, almost none of them the named anchors ([S1, section 3.3](../supplements/S1-data-and-classification.md)). Eighteen papers cannot stand proxy for nearly half a corpus. Under the strict 35-topic core the gold rise since 2006 and the teal upturn around 2020 remain, the teal slope from 2006 to 2019 is +0.00011 per year (p = 0.29, not significant), and teal is above gold in 5 of the 31 years from 1995 to 2025, against all 31 under the extended definition.

**The last two years of the series are contaminated, and I exclude them from every fit.** OpenAlex ingestion, reference-matching and reclassification events between February 2024 and November 2025 corrupt the 2024 and 2025 cohorts; a re-download eight weeks after the snapshot gives 39% less than the snapshot on one 2025 number and does not show the snapshot's end-of-series climb ([S2, section 4.4](../supplements/S2-citation-flow.md)). My verdict is that the 2024 to 2025 rise is mostly a database artifact. Turning points before roughly 2023 are safe. Exact 2024 and 2025 values are not, and I would not defend any of them.

**Topic classification degrades badly in recent years.** The fraction of works carrying any primary topic falls from 78.6% in 2021 to 65.9% in 2023 and 53.6% in 2024. Roughly half of 2024's literature is unclassifiable by this scheme, so the final years describe a shrinking and possibly unrepresentative slice.

**Reference coverage is incomplete and uneven.** OpenAlex holds a reference list for 111.7 million of 398.3 million indexed works (28.0%). Within the extended AI definition the share is about a third in 1995 and 2001 and 58.9% in 2002, against about half throughout for neuroscience ([S1, section 2.2](../supplements/S1-data-and-classification.md)). Coverage varies by publisher, era and field, and the direction of that bias cannot be bounded from inside the dataset.

**Citations are not influence.** A reference records acknowledgement, not debt, and cannot distinguish a foundational idea from a software citation. This analysis measures the volume and direction of acknowledged intellectual traffic, which is a weaker thing than influence.

**Three of the four eras fixed in the code rest on four annual observations** after truncation at 2023. Bootstrap intervals over four points are optimistic, and I read the significance markers on those bars as suggestive. The eighteen-year and fourteen-year segments from the changepoint search are the ones I would defend. The eras were fixed in the code, not registered anywhere outside it, and the expansion era was widened after the first fits.

**I did not remove self-citation.** Every edge is counted, including citations to a paper's own authors. Removing them would change the levels, probably in the same direction for both fields; the metric compares directions rather than levels, which is why I left this alone rather than because it does not matter.

**Both fields have internal structure that has been flattened.** "Neuroscience" here spans molecular, systems, clinical and cognitive work; "AI" spans computer vision, machine-learning theory and neuromorphic hardware. Traffic almost certainly concentrates in a few subdisciplines on each side. A decomposition is the natural next analysis. But I have not done it.

### Corpus and roster gaps

**English-indexed only** (D4). An estimated 5–15% of Asian and East-European NeuroAI is under-counted. Institutional and venue seeding mitigates this partially for RIKEN, OIST, ATR Kyoto, the Bernstein Centers and Tübingen; Asian-language-only papers are excluded outright.

**Books and pre-DOI works are absent from the graph** (D2). Marr 1982, the PDP volumes, Wiener 1948, Hebb 1949, McCulloch and Pitts 1943 and Braitenberg 1984 enter only through citing works. The risk is under-weighting the classical bridges.

**Pool 2 is title-only** and therefore small. OpenAlex abstracts were dropped from the local parquet projection, so any phrase that only appears in an abstract is missed, and recall is roughly 30–50% below what title-plus-abstract matching would give. Pool 2's size is not a measurement of how much operational NeuroAI exists.

**Pool 1's operational institution list is 21 OpenAlex sub-institute IDs, not the 41 named carriers on the editorial roster.** Most named carriers are courses, workshops, tracks or programs that OpenAlex does not represent at the right granularity, and using whole-university IDs instead would have made the pool meaningless. Kempner, Wu Tsai and ARNI were not resolvable at probe time. This is a real narrowing, and I enumerate it in [corpus and pools](01-corpus-and-pools.md), section 3.3.

**Pool 4's implemented seed lists diverge from the foundation's rosters** in several places, all of which I enumerate in [corpus and pools](01-corpus-and-pools.md), section 6. The material ones: three Zador 2023 signatories (Escola, Hawkins, Koulakov) are missing from sub-tier 4a; `Yamins Daniel` is a name-order error that resolves to nothing; and sub-tier 4f contains one name not on the roster (`Anders Sandberg`) and two that appear to be wrong resolutions of Mineault 2024 co-signatories (`Nathan A. Sanborn`, `Pedro A. Tavares`). Anchor signatories enter Pool 1a through the DOI route regardless. So the practical effect is mostly on the sub-tier tags rather than on corpus membership, but the entries should be fixed before the lists are reused.

**Pool 3's resolved venue IDs under-cover the AI conferences.** CVPR, ICCV and ICRA resolve to single-year conference instances rather than to venue series, and TMLR, EACL, RLC, COLT, UAI, the canonical NAACL entry and the canonical AAMAS entry did not resolve at all at probe time. *Nature Reviews Neuroscience*, *Biological Cybernetics* and *WIREs Cognitive Science* also failed to resolve.

**I fixed the Pool 1 rosters at April 2026.** Moves after that date are not captured; Tolias moving from Baylor to Stanford in 2024 is captured, later moves are not.

**Surname collisions inflate Pool 4 counts** for six flagged surnames. I carry the flag through the outputs rather than using it to drop rows, so any downstream count over Pool 4 that ignores it will be too high.

### Classification and taxonomy caveats

**Two neuroscience anchors leak out of field 28** because OpenAlex mis-clusters them: Bargmann's *C. elegans* work into subfield 1302 (Aging) and Buzsáki and Draguhn 2004 into subfield 1312 (Molecular Biology). Patching this by admitting either subfield whole would add millions of unrelated works, so I recorded both as known misses.

**Medical-imaging bridge papers remain labeled `other`.** I did not add subfields 2741 and 2730 to the AI side, so Esteva, Gulshan and Smith's FSL fall outside it. This under-counts the applied-machine-learning-for-brain track.

**Faction 13's boundary cases may be partly wrong.** I reassigned eight names out of the skeptic roster after deeper review: Krakauer, Fedorenko, Gershman, Lake, Pessoa, Cisek, Brette and Hawkins. I preserved cross-references as a safety net, but the reassignments are judgment calls.

**The analogy-versus-methodology subscore is unavoidably subjective** (B3). The clear cases at either end are clear; the borderline cases are flagged rather than resolved.

**Lake's 2023 *Nature* meta-learning-for-compositionality paper resolves his own earlier critique.** Author trajectory is not the same thing as position change, and the roster treats it carefully rather than reclassifying him.

### Metric caveats

**The odds ratio can move because its denominator moved.** `rho_null` is literally the target field's share of the combined two-field publication pool, so a shrinking neuroscience share inflates one direction's odds ratio with no behavioral change at all. This is why I report the raw share beside the odds ratio rather than instead of it. See [the citation metric](03-citation-metric.md), section 2.

**A batch of misdated records sits at one of the turning points.** AI works with an IEEE DOI go from 1,635 in 2001 to 40,701 in 2002, which nearly doubles the AI side in that year and coincides with the 2002 turning point of the gold line ([S1, section 4.3](../supplements/S1-data-and-classification.md)). The expected share of the gold line is built from that count, so the jump can by itself produce a break, and the figure's change-point search cannot tell the two apart ([S2, section 5](../supplements/S2-citation-flow.md)).

**Changepoint locations carry no confidence interval.** Both the piecewise-OLS search and PELT return deterministic segment boundaries. A bootstrap over segment locations would be a worthwhile robustness check, and I have not run it.

**Bridge-score aggregates are computed over the top 5,000 E2-filtered papers**, not the full pool of 58,971, except for the corporate rows of the consolidated institution table, which were summed over all 133,763 papers that pass the 5-and-5 gate. That is a computational compromise which could change the tail of the author and institution rankings, and it means the order across the corporate rows and the other institution rows depends on the choice of paper set ([S5, sections 3.3 and 4.5](../supplements/S5-bridge-builders.md)). The concentration figures quoted in the article (39.64% for the top 100 institutions and 6.63% for the top 100 authors) are the values of a sensitivity bound that drops the entities averaging more than 400 units of B per paper ([S5, sections 3.7 and 4.7](../supplements/S5-bridge-builders.md)).


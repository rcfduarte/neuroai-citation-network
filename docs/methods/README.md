# Extended methods

This directory is the formal methods record for the citation-network analysis behind my article "Examining the bridge between neuroscience and AI" in *The Transmitter*. It covers how the corpus was assembled, how every paper was assigned to a field, how each analytical question was operationalized, and every decision I made along the way with its rationale. It does not contain the results, the figures or the article's interpretation; those are in the six supplements, indexed in [`../supplements/README.md`](../supplements/README.md). It also does not restate the code. Where a list is hard-coded, I name the module so you can check my prose against the implementation.

I recomputed every number in these files against the committed tables, and the supplements link to the sections that hold them. Where a number in these files and a number in a supplement disagree, the supplement is right, because the supplements are checked against the committed tables in [`../../results/`](../../results/README.md).

## What the analysis asks

The claim under test is the NeuroAI premise itself: that neuroscience and artificial intelligence now feed each other, and that the feeding runs both ways. A genuine two-way intellectual merger has to leave a trace in the citation graph, because ideas travel through references. So the analysis asks the narrowest quantitative version of that question that I could construct, over every annual cohort of publications from 1990 to 2025, against a single frozen snapshot of OpenAlex.

## The analytical questions, and where each one ended up

I framed the work as four questions, Q1 to Q4. Q3, on the vocabulary of the merger, was cut with the article section it served and is not part of this repository. Of the other three, two carry the published article and one is a working question that no published sentence uses.

**Q1, citation flow (Figures 1 and 2 of the article).** For each year and each direction, how much more likely is a paper in one field to reach into the other than its size and its neighbor's size would predict? Measured as a restricted-universe odds ratio per year per direction, with Wilson intervals, four eras fixed in the code, turning points found in the data by a piecewise-OLS search (with PELT as a cross-check), and a year-resampling bootstrap. This is the article's headline figure. Definitions are in [the citation metric](03-citation-metric.md); results, checks and the strict-AI counterfactual in [S2](../supplements/S2-citation-flow.md); the raw counts and shares of Figure 2 in [S3](../supplements/S3-counts-and-field-sizes.md).

**Q2, dual citizens (not in the published article).** How many researchers publish substantively in both fields, and is that population growing? Measured as a census over OpenAlex disambiguated author identities at three thresholds: (A) at least one paper in each field ever, in any author position, giving 418,409 authors; (B, the headline of the working analysis) at least three first- or last-author papers in each field inside a ten-year rolling window, giving 19,226 authors; (C) at least five, same window and positions, giving 6,680 authors. A co-authorship-brokerage variant with no fixed threshold is computed as a robustness check. Sixteen *a priori* factions were specified before the corpus pull as candidate communities for clustering; they are an interpretive scaffold, not an input to any number reported anywhere. No sentence of the article and no supplement uses the census, and its counts come from the heavy derived-data tree, not from a committed result file, so I record the thresholds and counts here for the record only. Q2's decisions are recorded under E3 and E6 in [decisions and limitations](06-decisions-and-limitations.md); its field assignment and corpus are shared with Q1 and documented here.

**Q4, bridge papers (Figure 3 of the article).** Which individual papers, authors and institutions are legible to both fields at once? Measured as the harmonic mean of a paper's neuroscience-side and AI-side incoming citation counts, then aggregated to people and places. See [the bridge metric](05-bridge-metric.md) for the definitions, [S5](../supplements/S5-bridge-builders.md) for the figure, the hand-verified affiliations and the concentration analysis, and [S6](../supplements/S6-citation-age.md) for the objection that the old canon at the top of the ranking is an effect of citation age.

Two analyses in the supplements have no file in this directory, because I designed and documented them in the supplements themselves: [S4](../supplements/S4-what-ai-cites.md) (which neuroscience AI cites, how old it is, the six NeuroAI papers, and how short AI's citation memory is) and the age controls of S6. Their methods are in section 3 of each.

## The direction convention

This is the single easiest thing in the analysis to invert, and I inverted it myself at one point during preparation, so I am pedantic about it everywhere.

A citation points **from the citing paper to the cited paper**, which is the opposite of the direction the idea traveled. If an AI paper lists a neuroscience paper in its references, the neuroscience came first and the AI paper picked it up: knowledge moved from neuroscience into AI. Article labels follow where the influence *lands*.

| Article label | What it means | What is counted in the graph | Value of `direction` in the data files | Figure color |
|-|-|-|-|-|
| **Neuro→AI** | neuroscience informs AI | AI papers citing neuroscience papers | `ai_to_neuro` | teal |
| **AI→Neuro** | AI informs neuroscience | neuroscience papers citing AI papers | `neuro_to_ai` | gold |

The value names in the data files are the *citation-link* names, which are the reverse of the article's *influence* labels. The mapping happens at plotting time (`style.DISPLAY_LABELS_INFLUENCE`); the underlying data is never renamed. But anyone reading the files under `results/` directly needs the table above. Anyone reading working notes dated before 2026-05-28 needs it twice, because those notes predate the convention and use the citation-link names throughout.

## Contents

| File | Covers |
|-|-|
| [01, corpus and pools](01-corpus-and-pools.md) | The OpenAlex snapshot and its manifest; the four curated corpus pools in full, with every anchor publication, institution, Boolean template, venue and seed author named; the union-and-deduplicate rule and the exact overlap table. The pools are the corpus as designed; no published number reads them |
| [02, field classification](02-field-classification.md) | What counts as neuroscience and what counts as AI; the extended classifier and its 26 excluded topics; the strict 35-topic core definition in full; the three-scheme triangulation; and what the extension does and does not justify |
| [03, the citation metric](03-citation-metric.md) | The restricted odds ratio and its population variant; Wilson intervals; the citing-year axis; the four eras fixed in the code; the piecewise-OLS search behind the figure's turning points and how it differs from PELT; the bootstrap; the cross-source samples |
| [05, the bridge metric](05-bridge-metric.md) | The Q4 harmonic-mean bridge score, its admission gate and two filter variants (and which rule removes what), the paper-type filter, why the OpenAlex affiliations were discarded, corporate-group consolidation, and author and institution aggregation |
| [06, decisions and limitations](06-decisions-and-limitations.md) | The locked decision registry A1–A5, B1–B5, C1–C5, D1–D5, E1–E7, each with its rationale; scope; known gaps; and the limitations I would want a critic to start from |

The supplements these files feed, and the parts of the article each supports, are listed in [`../supplements/README.md`](../supplements/README.md): S1 (data, corpus and field classification), S2 (citation flow, Figure 1), S3 (counts and shares, Figure 2), S4 (what AI cites in neuroscience), S5 (the bridge builders, Figure 3) and S6 (does citation age explain the bridge canon). A short plain-language account of the method for readers who want neither is [`../methods-note-public.md`](../methods-note-public.md). How to re-run the cross-source samples is in [`../reproducing-cross-source.md`](../reproducing-cross-source.md).

## Where the authority sits

The definitional foundation document (`definitional-foundation-v1.md`, locked 2026-04-29, kept outside this repository) fixed every pool definition, roster and decision before I pulled the corpus. These files are its public translation, with the points where the shipped code diverges from the locked prose noted in place. Where prose and code disagree, I report the code, because the code is what produced the numbers. Where these files and the committed tables disagree, I report the tables.

# Generative AI use: disclosure

This repository and the article it supports were produced with generative AI assistance. This document says where, for what, and how the output was checked. It is the public counterpart of the full per-interaction log that the commissioning contract requires me to keep for three years.

## Standing rule

I treated every generative AI output as unvetted source material. A number in the article or in a supplement is there because it was recomputed from the OpenAlex data or from a named paper, never because a model said it. Where a model produced a figure or a claim that I could not trace to such a source, I dropped it. And a model's confidence counted for nothing.

## Where it was used

| Task | Tool | How the output was checked |
|-|-|-|
| Literature scoping: earlier bibliometric work on NeuroAI, field taxonomy, how the field is discussed | Claude (Claude Code) | Cross-checked against OpenAlex and Google Scholar; used to structure the inquiry, never as a fact |
| Scoping of brand history, keywords, cybernetics lineage, skeptics and critics, safety and interpretability | Claude (Claude Code) | Every claim re-derived from primary sources before use |
| Venue, institution and reference-library lists | Claude (Claude Code) | Checked against OpenAlex records and the publications themselves |
| Adversarial stress-testing of the thesis | Claude (Claude Code) | Used to generate counter-arguments to my own position |
| Analysis code: local OpenAlex copy in DuckDB, odds-ratio citation flow, change-point search, bridge ranking | Claude (Claude Code) | Code reviewed by me; results reproducible from this repository; the October 2026 revision added automated tests and independent re-computation, described below |
| Figures | Claude (Claude Code) writing matplotlib code | Every figure is plotted by code from the data tables; no image model was used |
| Structural drafting and copy-editing of the article | Claude (Claude Code) | The article text is mine; suggestions were edited or rejected by me |
| Re-analysis after reviewer and editor comments (September to October 2026): the citation-age control, the cited-vintage and subfield analysis, the NeuroAI-paper citation curves, the reference-age profile | Claude (Claude Code), several sub-agents | Each analysis pre-declared its definitions in code, wrote its results to committed tables, and has tests that fail when the tables change; an independent verification pass recomputed the numbers from raw outputs |
| Rewrite of the supplements S1 to S6 and the methods documents (October 2026) | Claude (Claude Code), sub-agents of the Sonnet and Opus models | Drafted by the model from the committed result tables. Every headline number (more than 1,000 of them) is listed in `docs/supplements/claims/` with the sentence it appears in and the expression that recomputes it, and a test fails if either changes. The text was then read and edited by me |
| Pre-submission AI-detection scan | heuristic and perplexity scanners | Internal quality-assurance step |

## What was not used

- No image generation. Every figure in the article and the supplements is plotted from the data by the code in this repository.
- No generated references. Every reference was resolved against Crossref, OpenAlex or the publisher; a script (`verify_citations.py`) checks each DOI before text leaves my vault.
- No asserted facts. A model's numerical or factual claim was either recomputed from the data or removed.
- No confidential material was pasted into a hosted model: no peer-review text, no unpublished manuscripts, no contact details of sources.

## What the checks found

Recomputing was not a formality. The October 2026 revision recomputed every number from the committed result tables, and where a working number from an earlier draft did not survive, the supplements carry the recomputed value. Each supplement states the definitions and paper sets behind the article's numbers in its method section, and its limits in its caveats section.

## Reproducing it

The analysis is reproducible from this repository: see [`../reproduce.sh`](../reproduce.sh), [`../results/README.md`](../results/README.md) and [`methods/`](methods/).

## Disclosure paragraph, as supplied to the editor

> I used Claude (via Claude Code) during research and scoping for literature discovery, taxonomy-building and adversarial testing of the thesis; to write and revise the analysis code (a local OpenAlex copy in DuckDB and the citation-flow, change-point, bridge-ranking and control analyses); to draft early structure and copy-editing suggestions for the article, which I edited; and to draft the technical supplements and repository documentation from the committed result tables, which I then read and edited. No claim rests on a model's assertion: every number in the article and the supplements is recomputed from OpenAlex data by code that is in the repository, and automated tests fail if a quoted number drifts from its source table. All figures are plotted from the data; no images were generated or altered with an image model. A full interaction log is retained for the contract's three-year requirement.

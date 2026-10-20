---
title: "Supplements to the Transmitter article on neuroscience and AI"
date: 2026-10-20
author: Renato Duarte
repo: https://github.com/rcfduarte/neuroai-citation-network
---

# Supplements

These six documents back up the article "Examining the bridge between neuroscience and AI" in *The Transmitter*. The article makes claims in three places: a figure of how often each field cites the other (Figure 1), a figure of the raw numbers behind it (Figure 2), and a figure of the papers, people and institutions that both fields cite (Figure 3). In each supplement I take one part of that argument, say which sentences of the article it supports, and give the data, the method, the results, the limits and the commands that reproduce it. You need none of them to read the article.

| | Title | Supports | What it adds |
|-|-|-|-|
| [S1](S1-data-and-classification.md) | Data, corpus and field classification | the data description; how a paper counts as neuroscience or AI | The snapshot and its coverage, the exact rule that assigns a paper to a field, the 26 excluded topics, annual field sizes, the four curated pools and why the main analysis does not use them |
| [S2](S2-citation-flow.md) | Citation flow: the odds ratio behind Figure 1 | Figure 1 and the paragraphs around it | What the vertical axis means, bands, shaded periods, turning points, the labeled papers, trends with intervals, cross-source replication, the 2024-25 database problem, and the checks the figure rests on |
| [S3](S3-counts-and-field-sizes.md) | Counts, shares and field sizes | Figure 2 and the technical note | The raw numbers, where the two raw-share lines cross, how they relate to the odds ratio, and how much of the post-2020 rise is dilution |
| [S4](S4-what-ai-cites.md) | What AI cites in neuroscience | the sentence on cognitive neuroscience, the sidebar of NeuroAI papers, and the claim that AI cites newer work | Subfield breakdown, age of the cited work, a robustness check, the six NeuroAI papers' citation curves, and how short AI's citation memory is |
| [S5](S5-bridge-builders.md) | The bridge builders | Figure 3 and the bridge paragraphs | The bridge score, eligibility filters, the top 15 papers, authors and institutions, how affiliations were verified, the paper sets behind each column, and concentration |
| [S6](S6-citation-age.md) | Does citation age explain the bridge canon? | the claim that no new bridge work has appeared since 2003 | Re-rankings that control for age |

The formal definitions behind these documents (corpus construction, field classification, the citation metric, the bridge metric, decisions and limitations) are in [`../methods/`](../methods/). My two-page summary of the method is in [`../methods-note-public.md`](../methods-note-public.md). I describe how generative AI was used in [`../GAI-DISCLOSURE.md`](../GAI-DISCLOSURE.md).

## Conventions used in all of them

**Direction.** `Neuro→AI` means neuroscience informs AI, which shows up in the data as AI papers citing neuroscience papers; the article draws it in teal. `AI→Neuro` means AI informs neuroscience, measured as neuroscience papers citing AI papers; the article draws it in gold. The arrow follows where the influence lands, not where the citation points. In the code and in the files under `results/` the two directions carry the opposite names, because there they are named after the citation link: the column value `ai_to_neuro` holds AI papers citing neuroscience. I repeat this in each supplement where a table or figure could be misread.

**Data vintages.** For the citation, bridge and age analyses I use one frozen OpenAlex snapshot of 30 March 2026, so that every number can be regenerated from a fixed corpus. The cross-source samples in S2 (section 4.5) query live sources instead, and live counts drift over time, so the two should not be mixed.

**The last two years are not settled.** OpenAlex was rebuilding its records while I worked, and the values for 2024 and 2025 are unstable in every analysis. I stop all fits at 2023. Turning points before about 2023 are safe.

**Where the numbers come from.** I recomputed every number quoted in a supplement from the small files committed under [`../../results/`](../../results/). The file [`claims/`](claims/) lists each headline number with the sentence it appears in and the expression that recomputes it, and `tests/test_supplement_claims.py` fails if a sentence is edited or a result file changes. Run `./reproduce.sh numbers` to check them all.

**Code and data.** https://github.com/rcfduarte/neuroai-citation-network

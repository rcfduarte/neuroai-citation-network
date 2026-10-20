---
title: "How this was done: a short methods note"
piece: "Examining the bridge between neuroscience and AI"
publication: The Transmitter
author: Renato Duarte
date: 2026-10-20
repo: https://github.com/rcfduarte/neuroai-citation-network
status: public
tags: [transmitter, neuroai, methods, public]
---

# How this was done

In this note I describe the data and the measurements behind the article. You can read it without any of the technical documents. I wrote up the full tables and every judgment call in six supplements, listed in the [supplements index](supplements/README.md), and the formal definitions are in [`methods/`](methods/README.md).

## The data

Everything runs against a local copy of [OpenAlex](https://openalex.org), an open catalog of the scholarly literature, in a snapshot dated 30 March 2026. The download holds about 458 million work records, the number the article quotes, and 2.9 billion citation links. My analyses use the 398 million works published from 1990 on, because I built the working index only from that year ([S1](supplements/S1-data-and-classification.md)).

Every work in OpenAlex has one main topic, and I use it to label each paper as neuroscience, AI, neither, or unknown. Neuroscience is the OpenAlex field of that name. AI is the OpenAlex artificial-intelligence subfield minus 26 topics that are not AI (cryptography, geology and the like), plus computer vision and one neuromorphic-hardware topic. No paper counts on both sides, and what a paper cites plays no part in its label. When a neuroscience paper cites an AI paper, that is one unit of traffic in the AI→Neuro direction (AI informing neuroscience); the reverse is Neuro→AI. The arrow follows where the influence lands, not where the citation points. It is easy to invert.

## What the article measures

**1. Direction and rate of citation flow (Figure 1, with the raw counts in Figure 2).** For each year I ask: when a paper in one field cites work in either field, how much more likely is it to cite the other field than chance alone would predict? The answer is an odds ratio. Chance matters here. The two fields have grown at very different rates. AI's literature has grown almost tenfold since 1995, and neuroscience's about fourfold. Raw cross-citation counts would mostly measure that growth. The raw-share lines of Figure 2B cross in 2017 to 2018 (the yearly lines at 2017.87, the thick 5-year lines at 2018.04), while the raw counts of Figure 2A never cross, and the crossing has reasons that have little to do with intellectual exchange. Figure 2 shows both views, and the supplements argue that each answers a different question ([S2](supplements/S2-citation-flow.md), [S3](supplements/S3-counts-and-field-sizes.md)).

**2. Bridge papers, authors and institutions (Figure 3).** To find work that crosses the boundary rather than merely being popular on one side, I score each paper by the harmonic mean of the citations it receives from each field. The harmonic mean punishes imbalance. A paper cited a thousand times by AI and twice by neuroscience scores near zero, while one cited a hundred times by each scores high. A paper is eligible with at least five classified citations from each side, which gives 133,763 papers. Removing papers that belong to neither field, plus 67 papers with 10,000 or more classified citations, mostly general machine-learning works, leaves 58,971, the "roughly 59,000" of the article. Authors and institutions are ranked by summing the score over the papers they are credited on. Author-to-institution links in the figure do not come from OpenAlex, whose affiliations were full of name collisions. I checked all 26 links by hand against ORCID, institutional pages and CVs ([S5](supplements/S5-bridge-builders.md)).

**3. What AI cites, and whether age explains the canon.** Two supplements go beyond the figures. One breaks down which neuroscience AI papers cite and how old it is ([S4](supplements/S4-what-ai-cites.md)). The other tests whether the bridge ranking is dominated by old papers simply because old papers have had time to collect citations ([S6](supplements/S6-citation-age.md)).

A vocabulary section was cut from the article, and this repository covers only the analysis behind the published text.

## What to distrust

Three caveats travel with these results. They limit what the numbers can carry.

**The 2024 and 2025 values are unreliable.** OpenAlex was rebuilding its records while I worked, so citation counts for those two years are not stable. And so every fit stops at 2023. Still, the upturn discussed in the article starts before those years. Its size is not established, and its statistical support is modest.

**Where you draw the boundary of "AI" changes some results.** With a narrower definition (a 35-topic core), the gold rise since 2006 and the teal upturn around 2020 remain, but the teal decline from 2006 to 2019 is not significant (+0.00011 per year, p = 0.29), and neuroscience citing AI comes out higher than AI citing neuroscience in 26 of the 31 years from 1995 to 2025, against none under the definition used for Figure 1. In the supplements I state which sentence of the article depends on the choice ([S2](supplements/S2-citation-flow.md), section 5).

**Two numbers in the bridge paragraphs rest on specific paper sets.** The "roughly 59,000" papers are the 58,971 that remain after the eligibility filters; 133,763 pass the first gate of five citations from each side. The concentration figures (the top 100 institutions holding nearly 40 percent, the top 100 authors below 7 percent) are the values of a sensitivity bound that drops the authors and institutions averaging more than 400 units of score per paper, and the institutions column sums the company rows and the university rows over different paper sets ([S5](supplements/S5-bridge-builders.md), sections 3.2, 3.3 and 3.7).

## Reproducing it

In the repository I keep the pipeline, the figure code and a `reproduce.sh` script. The script redraws the figures and recomputes every number quoted in the supplements from small result tables committed in the repository, so it needs no OpenAlex data and no network access. I do not ship the OpenAlex snapshot. It runs to several hundred gigabytes. But the steps that rebuild the tables from it are scripted and listed by `./reproduce.sh heavy`.

I used generative AI in this project for literature scoping, for writing the analysis code and for structural editing. I never used it to generate a fact, a citation or an image. The full disclosure is in [`GAI-DISCLOSURE.md`](GAI-DISCLOSURE.md).

## Going deeper

The [supplements index](supplements/README.md) says which sentences of the article each supplement supports and what it adds. The formal definitions, with every list of topics, venues, institutions, authors and keywords written out, are in [`methods/`](methods/README.md).

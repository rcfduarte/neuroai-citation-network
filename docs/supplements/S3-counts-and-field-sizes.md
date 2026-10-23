# S3. Counts, shares and field sizes (Figure 2)

In this supplement I set the raw numbers behind Figure 2 beside the odds ratio of Figure 1 and say what each answers. I find that neuroscience papers cite AI more often than AI papers cite neuroscience in every year, mostly because their reference lists are longer. As a share of what each field cites, AI papers' citing of neuroscience led until 2017 and the reverse has held since 2018; corrected for field size, AI papers' citing of neuroscience is ahead in every year. About two thirds of the post-2020 rise of the teal line of Figure 1 comes from neuroscience shrinking as a share of the two fields. Gold is always neuroscience papers citing AI, teal always AI papers citing neuroscience.

**What this supplement covers**

- Figure 2 caption, panels A and B: sections 1.1, 2.1 and 2.2.
- "More modestly than depicted in the odds ratio" and "a relative dilution" (paragraph 9): 15.26 to 16.51 per 1,000 (+8.2 percent) against +37.8 percent for the odds ratio, section 2.4.
- "Led since 2018, when the lines cross" and "there is simply more AI work to cite" (paragraph 10): the lines cross between 2017 and 2018, section 2.2.
- "Correcting for field size is the more honest view" (paragraph 10): sections 2.3 and 2.5.
- "AI is now citing more neuroscience than ever before" (paragraph 12): section 2.1.

## 1. Methods

### 1.1 Counts, shares and the odds ratio

I take everything from the OpenAlex snapshot of 30 March 2026 and the extended AI definition of Figure 1 ([S1](S1-data-and-classification.md)), from [`results/flow/or_by_year.csv`](../../results/flow/or_by_year.csv). Gold is the `neuro_to_ai` column, teal `ai_to_neuro`. References to missing works, works dated 2026 included, are left out of every numerator and denominator (8.5 percent of the references of neuroscience papers in 2023 and 19.6 percent of those of AI papers).

The count (panel A) is the number of cross-field references per year, in thousands. The share (panel B) is that count divided by all references to works of known field, third fields included, times 1,000. Thin lines are yearly values; thick lines are centered 5-year means over the series from 1990, dashed over the hatched provisional years 2024 and 2025. The odds ratio of Figure 1 uses a different observed share, as I explain here: the cross-field references divided by the references to the two fields only. I find that third fields take many references (34.2 percent of AI papers' recorded references in 2023, 44.0 percent of neuroscience papers'), so that observed share is larger than the share of panel B: in 2023, 25.10 per 1,000 for AI papers citing neuroscience against 16.51 in panel B, and 39.65 against 22.19 for neuroscience papers citing AI. Formulas: [METHODS section 7](../METHODS.md#7-counts-shares-and-field-sizes).

With $\omega$ the odds of the observed share and $N$ the papers of each field in the citing year, the expected share is the cited field's fraction of the two fields' papers, so

$$\mathrm{OR}_{\mathrm{teal}}=\omega_{\mathrm{teal}}\,\frac{N_{\mathrm{AI}}}{N_{\mathrm{neuro}}},\qquad \mathrm{OR}_{\mathrm{gold}}=\omega_{\mathrm{gold}}\,\frac{N_{\mathrm{neuro}}}{N_{\mathrm{AI}}},\qquad \frac{\mathrm{OR}_{\mathrm{teal}}}{\mathrm{OR}_{\mathrm{gold}}}=\frac{\omega_{\mathrm{teal}}}{\omega_{\mathrm{gold}}}\left(\frac{N_{\mathrm{AI}}}{N_{\mathrm{neuro}}}\right)^2 .$$

The size ratio enters squared, so I expect a size correction to be able to reverse the order of two raw lines; the logarithm splits a change between two years into a share term and a size term ([METHODS sections 7.2 and 7.3](../METHODS.md#7-counts-shares-and-field-sizes); the odds ratio itself: [S2, section 1.1](S2-citation-flow.md#11-the-odds-ratio)). I fixed the two years in advance, 2020 (the start of the last era of Figure 1) and 2023 (the last year of the fits), and tried no other pair.

## 2. Results

![Article Figure 2](../../figures/figure2_raw_v2.png)

*Article Figure 2, as published (`figure2_raw_v2`). A: cross-field references per year, in thousands. B: the same count per 1,000 references the citing field's papers make to works of known field. Gold: neuroscience papers citing AI. Teal: AI papers citing neuroscience. Thin lines are yearly values, thick lines centered 5-year means; the hatched band marks 2024 and 2025, provisional. Data: `results/flow/figure2_raw_v2_data.csv`.*

### 2.1 Panel A: counts

| Year | Neuroscience citing AI (gold) | AI citing neuroscience (teal) | Gold / teal |
|-|-:|-:|-:|
| 1995 | 4,439 | 1,886 | 2.35 |
| 2019 | 69,308 | 51,938 | 1.33 |
| 2023 | 103,054 | 72,841 | 1.41 |
| 2025 (provisional) | 112,183 | 97,295 | 1.15 |

I find that neuroscience papers cite AI more often than AI papers cite neuroscience in every year, 1990 to 2025. The count ratio never falls below 1.15 (in 2025) and, from 1995 on, never exceeds 2.35 (in 1995).

From 1995 to 2023 the gold count grew 23.2-fold and the teal count 38.6-fold. A count is the papers in the citing field times the references recorded per paper times the share that cross. For teal the share fell, so the growth in its count between 1995 and 2023 reflects the growing number and reference lists of AI papers rather than a larger share of references going to neuroscience. In 2023 AI published 2.11 times as many papers as neuroscience, yet the gold count is 1.41 times the teal one, because a neuroscience paper recorded 2.22 times as many references.

On "AI is now citing more neuroscience than ever before" (paragraph 12), the teal count reaches its highest solid-year value in 2023, 72,841 references, and the provisional years are higher still (90,282 in 2024, 97,295 in 2025). I also find the teal odds ratio highest in 2023 among the solid years, 0.0544. The teal share, however, is 16.51 per 1,000 in 2023, below its value in 2000, 20.95.

### 2.2 Panel B: shares, and where the lines cross

| Year | Neuroscience citing AI (gold) | AI citing neuroscience (teal) |
|-|-:|-:|
| 1995 | 11.05 | 19.33 |
| 2000 | 8.30 | 20.95 |
| 2017 | 15.23 | 17.78 |
| 2018 | 16.71 | 16.34 |
| 2020 | 19.24 | 15.26 |
| 2023 | 22.19 | 16.51 |

*Cross-field references per 1,000 references, as in Figure 2B.*

In my data the gold share falls from 11.05 per 1,000 in 1995 to its lowest value, 8.30, in 2000 and then rises to 22.19 in 2023. Teal begins at 19.33, stays between 16.2 and 18.7 from 2002 to 2019, falls to 15.26 in 2020, and is back at 16.51 in 2023. Between 2017 and 2018 the two yearly lines cross: teal was higher in 2017 (17.78 against 15.23), gold has been higher in every year since 2018, and the crossing by linear interpolation is at 2017.87. The thick 5-year means cross later (2018.04), so "led since 2018" is exact for the yearly values and at most a year early for the thick lines.

Paragraph 10 ties the crossing to the growth of AI, which I checked against the sizes: AI went from 1.64 times the size of neuroscience in 2019 to 2.11 times in 2023 while the gold share went from 18.54 to 22.19.

### 2.3 How panel B relates to the odds ratio: a worked year

For 2023, the last year I treat as solid, the observed odds are 0.0413 for gold and 0.0257 for teal, and the expected odds from field sizes are 2.113 and 0.473, so the odds ratios are 0.0195 and 0.0544. In raw terms gold is higher, its observed odds being 1.6 times the teal ones. After the size correction the teal line is 2.78 times the gold line: the teal observed odds are 0.624 times the gold ones, the squared AI-to-neuroscience size ratio is 4.46, and 0.624 x 4.46 is 2.78.

### 2.4 The dilution reading of the post-2020 rise

Between 2020 and 2023 neuroscience went from 152,180 to 164,016 papers per year and AI from 261,340 to 346,525, so AI went from 1.72 to 2.11 times its size. Applying the identity of section 1.1 to those two years:

| | AI citing neuroscience (teal) | Neuroscience citing AI (gold) |
|-|-:|-:|
| expected share of the cited field | 0.368 to 0.321 | 0.632 to 0.679 |
| observed share, per 1,000 (own + other) | 22.48 to 25.10 | 34.01 to 39.65 |
| odds ratio | 0.0395 to 0.0544 | 0.0205 to 0.0195 |
| change in odds ratio | x 1.38 | x 0.95 |
| of which, observed odds | x 1.12 | x 1.17 |
| of which, field-size factor | x 1.23 | x 0.81 |

I find that between 2020 and 2023 the teal odds ratio rose by 37.8 percent. Its observed odds rose by 12.0 percent and the field-size factor by 23.0 percent; in logarithms, about 35 percent of the rise is the raw share and about 65 percent the shrinking share of neuroscience among the two fields. Had I held the field sizes at their 2020 values, the teal odds ratio would have reached 0.0442 in 2023 instead of 0.0544. On the figure's own scale the teal share in panel B went from 15.26 to 16.51 per 1,000, a rise of 8.2 percent, against the 37.8 percent of the odds ratio. This is the contrast drawn in paragraph 9, and the "relative dilution" is the size term. For gold the arithmetic runs the other way: its raw share rose by 15.3 percent while its odds ratio fell by 4.7 percent, because the size change that inflates teal deflates gold by the reciprocal, 0.81.

![Raw share and field-size factor for each line](../../figures/figure_s3_dilution.png)

*Figure S3.1. For each line, 2015 to 2025, the odds ratio of Figure 1 (thick), the odds of the observed share (dashed) and the field-size factor, the citing field's papers over the cited field's (dotted gray), each indexed to 2020 = 100 (the first is the product of the other two). Left, teal: AI papers citing neuroscience. Right, gold: neuroscience papers citing AI. Hatched band: 2024 and 2025, provisional. Data: `results/flow/figure_s3_dilution_data.csv`.*

### 2.5 What each view says about influence

Three views give three orderings of the two lines from one classification.

| View | What it measures | Ordering of the two lines (gold: neuroscience citing AI; teal: AI citing neuroscience) |
|-|-|-|
| Count (Figure 2A) | how many citations land on the cited field's papers each year | gold above teal in every year, 1990 to 2025 |
| Share (Figure 2B) | what fraction of the citing field's references go to the other field | teal above gold in every year from 1995 to 2017, gold above teal from 2018 |
| Odds ratio (Figure 1) | the share against what field sizes predict | teal above gold in every year, 1995 to 2025 (smallest ratio 1.25, in 1995), under the extended AI definition |

I read the count as how much the cited field receives; the share says how much of what a field reads comes from the other; and the odds ratio says whether the other field is over- or under-represented compared with its size, which removes the effect of a growing denominator: when AI doubles in relative size, a neuroscientist citing it at an unchanged rate has more AI to choose from. Both views are valid and answer different questions. After 2020 the rise of the teal odds ratio is in the data and mostly a size effect (section 2.4).

## 3. Caveats

My size null uses the sizes of the two fields in the citing year, but references point backward, and AI was smaller relative to neuroscience in the years being cited (0.84 times in 1995, 2.11 in 2023). A benchmark built on the cited paper's year would shift the levels of both lines, and I have not computed it. I treat 2024 and 2025 as provisional: the teal count jumps in those years while recorded references per paper fall to 57 percent (neuroscience) and 61 percent (AI) of their 2023 values, and I stop every trend at 2023.

A citation here is a recorded reference, not influence: counts and shares treat a reference to a statistics library and one to a founding theory alike ([S4](S4-what-ai-cites.md) and [S5](S5-bridge-builders.md) look at what crosses). My decomposition is bookkeeping, not a causal model, and rests on two yearly values; I quote 35 and 65 percent only for 2020 and 2023 and treat the direction as the finding.

## 4. Reproduce

```bash
./reproduce.sh figures          # redraws Figure 2 and Figure S3.1 (and the other figures) from results/flow/
.venv/bin/python -m neuroai_cn.figures.figure2_raw_v2        # Figure 2 and results/flow/figure2_raw_v2_data.csv
.venv/bin/python -m neuroai_cn.figures.figure_s3_dilution    # Figure S3.1 and results/flow/figure_s3_dilution_data.csv
.venv/bin/python -m pytest -q tests/test_supplement_claims.py tests/test_flow_numbers.py
```

These read the committed `results/flow/or_by_year.csv`, exported by `.venv/bin/python -m neuroai_cn.analysis.export_flow_inputs` (needs the snapshot, [S1](S1-data-and-classification.md)); `neuroai_cn.analysis.flow_numbers` recomputes counts, shares and crossing years.

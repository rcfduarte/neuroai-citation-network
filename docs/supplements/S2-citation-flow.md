# S2. Citation flow: the odds ratio behind Figure 1

In this supplement I explain Figure 1 of the article element by element and give the numbers behind it: what the vertical axis measures, what each element shows, and how the levels, trends and change points come out. Gold is always neuroscience papers citing AI, teal always AI papers citing neuroscience. Under the AI definition the article uses, I find that AI papers cited neuroscience more often, relative to chance, than neuroscience papers cited AI in every year from 1995 to 2025.

**What this supplement covers**

- "The (chance-corrected) likelihood of AI papers citing neuroscience papers is higher than the reverse, across the range of time examined, 1995 to 2025" (paragraph 7): section 2.1.
- "Growing to about double its 1995 level" and "an odds-ratio against what the field sizes would predict" (Figure 1 caption): sections 1.2 and 2.1.
- Dashed lines, shaded eras, thin lines, panels B and C (caption): sections 1.3, 2.2 and 2.3.
- The teal line "leveled off, slightly decaying until 2019" and the "steepest slope of the entire series"; the gold line "risen significantly and steadily since 2006" (caption, paragraph 8): section 2.2.
- "Data from 2024 and 2025 is somewhat unreliable [...] the upturn predates those years" (paragraph 9) and the open circles: section 2.4.

## 1. Methods

I use the OpenAlex snapshot of 30 March 2026 and the field labels of [S1](S1-data-and-classification.md): a paper is neuroscience by its primary topic, and AI under the extended definition. For each citing year from 1990 to 2025, [`results/flow/or_by_year.csv`](../../results/flow/or_by_year.csv) holds the references each field's papers make to their own field, to the other field, to third fields and to works of unknown field, and the papers each field published that year. Because 1990 to 1992 rest on few cross-field references, I plot 1995 to 2025. In the data files, the lines are named by the citation link (`neuro_to_ai` is gold, `ai_to_neuro` is teal). Every definition, equation and procedure below is in [METHODS sections 4 to 6](../METHODS.md#4-citation-flow-and-the-odds-ratio).

### 1.1 The odds ratio

For each year and line, the observed share is the fraction of a field's references to the two fields that go to the other field. Its counterpart, the expected share, is what that fraction would be if references were handed out blind to discipline, in proportion to the number of papers each field published that year. The odds ratio divides the odds of the observed share by the odds of the expected share:

```
observed   = refs_to_other_field / (refs_to_own_field + refs_to_other_field)
expected   = papers_other_field / (papers_own_field + papers_other_field)
odds ratio = [observed / (1 - observed)] / [expected / (1 - expected)]
```

A value of 1 means a field crosses into the other exactly as often as the two sizes predict. Both lines sit far below 1 (between about 0.01 and 0.09), because every discipline cites itself far more than a size-blind null predicts. What I look at is the comparison between the lines and their change over time, not the absolute level. I draw panel A on a logarithmic axis from 0.005 to 0.3, so the chance level of 1 lies above the plotted range.

Worked example for 2019, from the 2019 rows of `or_by_year.csv`:

| | Neuroscience papers citing AI (gold) | AI papers citing neuroscience (teal) |
|-|-:|-:|
| references to own field | 2,097,457 | 2,060,136 |
| references to the other field | 69,308 | 51,938 |
| observed share crossing over | 0.0320 | 0.0246 |
| papers in the citing field | 149,538 | 245,916 |
| expected share from field sizes | 0.622 | 0.378 |
| odds ratio | 0.0201 | 0.0415 |

In 2019 a neuroscience paper choosing blindly would land on AI 62.2 percent of the time; neuroscience papers did so 3.20 percent of the time. Their odds are 0.033, the odds of 62.2 percent are 1.64, and the ratio is 0.0201. AI was the larger field, so a random neuroscience reference would often land on AI, which makes a given amount of citing of AI count for less; the same logic in reverse makes the teal line sit about twice as high.

### 1.2 What each element of Figure 1 is

| Element | What it is |
|-|-|
| Vertical axis of A | "likelihood of cross-field citation (odds ratio vs chance)", log scale. |
| Thick line | Centered 5-year rolling mean of the yearly odds ratio (at least three years per window); near the end it includes 2024 and 2025. |
| Pale band | Wilson 95 percent interval of the yearly value. It shows counting noise only and is narrow: in 2019 the teal interval runs from 0.0411 to 0.0418. |
| Shaded eras | Four eras fixed in the code before any slope was computed: Pre-DL (to 2011), DL emergence (2012 to 2015), DL expansion (2016 to 2019) and NeuroAI era (from 2020). |
| Dashed vertical lines | Turning points found with a piecewise regression, per line in its color and labeled by the first year of the new segment: gold 2002 and 2006, teal 2006 and 2020. |
| Thin gray lines | Six milestone papers added as annotations (AlexNet 2012, Hassabis 2017, Kriegeskorte 2018, Richards 2019, GPT-3 2020, Zador 2023); no statistic is computed at them. |
| Hatched band | The provisional years 2024 and 2025, which no slope uses. |
| Open circles | One per line in 2024 and 2025: the same odds ratio from a sample of a May 2026 re-download (section 2.4). |
| Panel B | OLS slope of the yearly odds ratio against year within each pre-defined era, fitted on 1995 to 2023, with bootstrap 95 percent whiskers. |
| Panel C | OLS slope within each segment between turning points. |

I draw the whiskers as bootstrap intervals over the years of an era or segment (500 resamples); two stars mean the 99 percent interval excludes zero, one star the 95 percent interval, and "n.s." neither. I found the turning points with an exhaustive piecewise-OLS search over zero, one or two breakpoints in 1995 to 2023, each segment at least four years long, run separately on each line; the cap of two breakpoints and the four-year minimum are my choices, not findings ([METHODS section 5](../METHODS.md#5-trends-and-change-points)). Every element's values are in `results/flow/figure1_article_panelA.csv`, `panelB.csv`, `panelC.csv`, `circles.csv` and `markers.csv`.

## 2. Results

![Article Figure 1](../../figures/figure1_article.png)

*Article Figure 1, as published (`figure1_article`). A: yearly odds ratio of cross-field citation against the field-size expectation, log scale. Gold: neuroscience papers citing AI. Teal: AI papers citing neuroscience. Pale bands: Wilson 95 percent intervals; thick lines: centered 5-year means; hatched band: provisional years 2024 and 2025; open circles: May 2026 re-download. B: OLS slope per era. C: OLS slope per segment between turning points.*

### 2.1 Levels: teal above gold in every year shown

| Year | AI papers citing neuroscience (teal) | Neuroscience papers citing AI (gold) | Teal / gold |
|-|-:|-:|-:|
| 1995 | 0.0290 | 0.0232 | 1.25 |
| 2006 | 0.0496 | 0.0105 | 4.73 |
| 2019 | 0.0415 | 0.0201 | 2.06 |
| 2023 | 0.0544 | 0.0195 | 2.78 |

In my data the teal line is above the gold one in all 31 years from 1995 to 2025. At 4.73 times, the gap is widest in 2006. The thick teal line stands at 0.0302 in 1995 and 0.0605 in 2023, 2.00 times as high, which is the caption's "about double" (the yearly value of 2023 is 1.88 times that of 1995). Its 2023 point averages 2021 to 2025, so it includes the two provisional years.

### 2.2 Trends

Panel B, the four eras fixed in advance (odds ratio per year; bootstrap 95 percent interval; ** the 99 percent interval excludes zero):

| Era | Teal slope | 95% interval | | Gold slope | 95% interval | |
|-|-:|-|-|-:|-|-|
| Before deep learning, 1995-2011 | +0.00117 | +0.00080 to +0.00166 | ** | −0.00059 | −0.00089 to −0.00032 | ** |
| Deep-learning emergence, 2012-2015 | −0.00113 | −0.00275 to +0.00021 | n.s. | +0.00081 | −0.00012 to +0.00147 | n.s. |
| Deep-learning expansion, 2016-2019 | +0.00065 | −0.00091 to +0.00221 | n.s. | +0.00084 | +0.00030 to +0.00137 | ** |
| NeuroAI era, 2020-2023 | +0.00493 | +0.00133 to +0.00903 | ** | −0.00025 | −0.00147 to +0.00038 | n.s. |

Panel C, the segments between turning points (bootstrap 95 percent interval; R2 is the share of year-to-year variance the straight line explains):

| Line | Segment | Slope | Bootstrap 95% | R2 |
|-|-|-:|-|-:|
| Gold | 1995-2001 | −0.00130 | −0.00190 to −0.00066 | 0.86 |
| Gold | 2002-2005 | +0.00012 | −0.00060 to +0.00079 | 0.12 |
| Gold | 2006-2023 | +0.00065 | +0.00057 to +0.00073 | 0.96 |
| Teal | 1995-2005 | +0.00140 | +0.00076 to +0.00230 | 0.57 |
| Teal | 2006-2019 | −0.00074 | −0.00099 to −0.00046 | 0.75 |
| Teal | 2020-2023 | +0.00493 | +0.00133 to +0.00903 | 0.89 |

I find gold the cleanest result. It fell until about 2006 and then rose at +0.00065 per year (bootstrap 95 percent interval +0.00057 to +0.00073) for eighteen consecutive years, with a straight line explaining 0.96 of the variation: the "risen significantly and steadily since 2006" of paragraph 8. Inside it, the 2016-2019 era slope is +0.00084 (interval +0.00030 to +0.00137). Teal rose between 1995 and 2005, declined in 2006 to 2019 (both intervals exclude zero; over 14 years a slope of −0.00074 adds up to a fall of about 0.01 against a level near 0.045, which I read as the caption's "slightly decaying"), and rose steeply after 2020.

I regard the 2020 to 2023 teal slope as the largest in either panel and the least secure. It is the slope behind the "steepest slope of the entire series" of paragraph 8, and it rests on four yearly values because 2024 and 2025 are provisional: its ordinary t interval, −0.00032 to +0.01018, includes zero (p = 0.056), so I read its size with caution and its direction as the finding. Likewise, the three four-year eras each rest on four values.

### 2.3 Change points

In my search Figure 1 turns at 2002 and 2006 for the gold line and at 2006 and 2020 for the teal line, as marked in Figure S2.1. Other procedures and settings return other years ([`results/flow/changepoints.csv`](../../results/flow/changepoints.csv)):

| Procedure | Window | Min. segment | Neuroscience citing AI (gold) | AI citing neuroscience (teal) |
|-|-|-:|-|-|
| Piecewise OLS, as in Figure 1 | 1995-2023 | 4 years | 2002, 2006 | 2006, 2020 |
| Piecewise OLS, wider window | 1990-2025 | 3 years | 1993, 2005 | 2005, 2022 |
| PELT (l2 cost, BIC penalty) | 1990-2025 | 3 years | 1993 | 2001, 2023 |
| PELT (l2 cost, BIC penalty) | 1995-2023 | 3 years | 2000, 2015 | 2001 |

I give every breakpoint as the first year of the new segment. The figure (2006) and the wider-window row (2005) place the mid-2000s turn one year apart, which I read as the same turn. I find that the late teal breakpoint moves with the settings: 2020 in the figure, 2021 with a three-year minimum on the same window (an exploratory run in `changepoints.csv`) and 2022 when 2024 and 2025 are included, so what is robust is an upward turn around 2020 to 2022, not the exact year. PELT with an l2 cost looks for shifts in the average level, not in slope, so it returns other years, and I give no interval for any breakpoint year.

![Segment fits, rolling slopes and change points](../../figures/figure_s2_trends.png)

*Figure S2.1 (`figure_s2_trends`). A: yearly odds ratio (dots, 1995 to 2025) with the OLS fit of each segment of Figure 1C (thick lines) and the change points (dashed vertical lines, in the color of the line). Gold: neuroscience papers citing AI. Teal: AI papers citing neuroscience. B: OLS slope in a centered 5-year (solid) and 7-year (dashed) window inside 1995 to 2023; the two window lengths have the same sign in 21 of the 23 window centers for teal and in 22 of 23 for gold. Gray: provisional years. Data: `results/flow/or_by_year.csv`, `segment_slopes.csv`, `changepoints.csv`.*

### 2.4 Why the fits stop at 2023, and the open circles

Toward the end of the series both lines rise, teal sharply, from 0.0544 in 2023 to 0.0849 in 2025. I treat 2024 and 2025 as provisional for three reasons. First, the composition of AI's references changed abruptly: the share of AI papers' references that point at other AI papers held between 0.63 and 0.66 in 2016 to 2023 and then fell to 0.550 in 2024 and 0.514 in 2025, mechanically raising the cross-field share. Second, fresher copies of the same database disagree with the snapshot, as the open circles show. Third, OpenAlex was rebuilding its database through 2024 and 2025 (new topic classifier, retroactive reference matching, a platform rewrite), which can shift recent cohorts. Hence every fit stops at 2023. The 2020 to 2023 rise is in the snapshot, so I take the teal upturn to begin before the provisional years, but I cannot establish its size.

Each open circle is the odds ratio that I computed from a sample of 1,500 papers per field and year drawn from the OpenAlex API in May 2026, with the expected share taken from the snapshot for the same year and line ([METHODS section 6](../METHODS.md#6-cross-source-replication)). I read a circle as the direction and rough size of the disagreement between the two downloads, not as a corrected value.

| Year | Line | Circle (May 2026 re-download) | Snapshot, yearly value | Circle / snapshot | Snapshot, thick line |
|-|-|-:|-:|-:|-:|
| 2024 | teal | 0.0594 | 0.0770 | 0.77 | 0.0654 |
| 2025 | teal | 0.0475 | 0.0849 | 0.56 | 0.0721 |
| 2024 | gold | 0.0208 | 0.0209 | 0.99 | 0.0213 |
| 2025 | gold | 0.0233 | 0.0235 | 0.99 | 0.0213 |

For neuroscience papers citing AI I find that the circles fall within 1 percent of the snapshot's yearly values. For AI papers citing neuroscience they sit below the snapshot, 23 percent lower in 2024 and 44 percent lower in 2025, which is why I do not trust the size of the end of the teal series ([`results/flow/figure1_article_circles.csv`](../../results/flow/figure1_article_circles.csv)).

### 2.5 The unrestricted odds ratio and leave-one-topic-out

The unrestricted variant keeps references to third fields and papers in third fields in both the observed and the expected share, so it asks how often a field cites the other compared with the whole of science. In my data both lines sit near or above 1 (in 2019, 1.51 for teal and 1.02 for gold), and teal is above gold in every year from 1995 to 2025, so the ordering does not depend on the choice of null. I find the trends weaker: over 1995 to 2023 the gold slope is +0.0122 per year (p = 0.0002) and the teal slope +0.0032 per year (p = 0.37). Third-field references dominate this variant, so it cannot resolve the teal trend.

The extended definition excludes 26 topics. For this check, the series was recomputed 27 times (the 26 exclusions and one topic that is already AI), each time re-admitting one candidate topic into AI ([`results/flow/sensitivity_loto.csv`](../../results/flow/sensitivity_loto.csv)), and took the largest relative change of the odds ratio in any year. Re-admitting T12157 ("Geochemistry and Geologic Mapping") changes the 2025 teal odds ratio by 506 percent, because the topic swelled in a 2025 OpenAlex re-export ([S1](S1-data-and-classification.md)); inside 1995 to 2023 its largest effect is 34.5 percent. Next, T10126 moves the series by at most 9.0 percent in 1995 to 2023, and the median of the 27 topics is 1.8 percent. In my check no single re-admitted topic reverses the order of the two lines in any year; the smallest teal-to-gold ratio across all 27 variants in 1995 to 2023 is 1.20.

![Sensitivity analyses](../../figures/figure_s2_sensitivity.png)

*Figure S2.2 (`figure_s2_sensitivity`). A: restricted (solid) and unrestricted (dashed) odds ratio, log scale. Gold: neuroscience papers citing AI. Teal: AI papers citing neuroscience. Gray: provisional years. B: leave-one-topic-out, the largest change in the odds ratio over 1995 to 2025 when each of the twelve most influential excluded topics is re-admitted, in percent on a log axis; T12157 (506 percent) in red. Data: `results/flow/or_by_year.csv`, `sensitivity_loto.csv`.*

## 3. Caveats

The level ordering of the two lines in Figure 1 depends on how widely AI is defined. I find that it holds under the extended definition used here, which includes computer vision; a narrower definition of AI brings the two lines closer together ([S1](S1-data-and-classification.md) describes both definitions and `results/flow/sensitivity_strict_or_by_year.csv` holds the narrower series).

The 2002 break of the gold line coincides with a batch of records dated 2002 from one publisher (IEEE), which raises the number of AI works in that year ([S1](S1-data-and-classification.md)). Since the expected share of the gold line is built from that count, a jump in the count can by itself produce a break, and my search cannot tell the two apart. Nothing in the article interprets the 2002 break.

## 4. Reproduce

```bash
./reproduce.sh figures          # redraws Figure 1, Figures S2.1 and S2.2 and the other figures from results/
.venv/bin/python -m neuroai_cn.figures.figure1_main_v2 or    # Figure 1 and results/flow/figure1_article_*.csv
.venv/bin/python -m neuroai_cn.figures.figure_s2             # Figures S2.1 and S2.2
.venv/bin/python -m neuroai_cn.analysis.changepoints         # changepoints.csv, segment_slopes.csv
.venv/bin/python -m pytest -q tests/test_supplement_claims.py -k "s2-"
```

These read only the committed `results/` files; new samples are described in [METHODS section 6](../METHODS.md#6-cross-source-replication), and a re-run against a newer database reproduces shapes, not exact counts.

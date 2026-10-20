# neuroai-citation-network

Code, data tables and supplementary documents behind the article "Examining the bridge between neuroscience and AI" by Renato Duarte, commissioned by *The Transmitter*. The article asks whether neuroscience and AI really feed each other, as the NeuroAI premise says, by measuring three things in the published record: how often each field cites the other, and which papers, authors and institutions both fields cite heavily.

You can read the article without any of this. Nothing here is required. I put the repository together so that you can check the numbers, disagree with a judgment call, or reuse the method.

## Where to start

The readable part is the six supplements in [`docs/supplements/`](docs/supplements/), which start at an [index](docs/supplements/README.md). Each supports a specific part of the article. It says what I did, with which data, what I found and what the result cannot show.

| | |
|-|-|
| [S1](docs/supplements/S1-data-and-classification.md) | Data, corpus and how a paper counts as neuroscience or AI |
| [S2](docs/supplements/S2-citation-flow.md) | Citation flow and the odds ratio behind Figure 1 |
| [S3](docs/supplements/S3-counts-and-field-sizes.md) | Raw counts and shares behind Figure 2 |
| [S4](docs/supplements/S4-what-ai-cites.md) | What AI cites in neuroscience: age, subfield, the NeuroAI papers |
| [S5](docs/supplements/S5-bridge-builders.md) | The bridge builders behind Figure 3 |
| [S6](docs/supplements/S6-citation-age.md) | Whether citation age explains the bridge canon |

[`docs/methods/`](docs/methods/) holds the formal definitions, [`docs/methods-note-public.md`](docs/methods-note-public.md) a short plain-language account of the method, and [`docs/GAI-DISCLOSURE.md`](docs/GAI-DISCLOSURE.md) a statement of how generative AI was used.

## Reproduce it

```bash
./reproduce.sh setup     # create .venv from the pinned lock file (needs uv)
./reproduce.sh check     # ruff, format check and the test suite
./reproduce.sh figures   # redraw the figures from results/
./reproduce.sh numbers   # recompute every number quoted in the supplements and compare
./reproduce.sh all       # all of the above
```

None of it needs OpenAlex data, a network connection or an API key, because it runs from the small files committed under [`results/`](results/). A clean run leaves `git status` unchanged under `results/`. SVG figures differ in a date stamp and random element ids on every run, while the PNGs are identical when the environment is the pinned one.

Rebuilding `results/` from scratch is a different order of work, and I do not run it from the script. It starts from the full OpenAlex snapshot, about 364 GB of parquet and a 494 GB DuckDB index. `./reproduce.sh heavy` prints the stages in order, and each stage's script documents its own arguments. The path to the heavy data is set with `NEUROAI_DATA` (default `~/data/neuroai-citation-network`). The cross-source samplers need `OPENALEX_EMAIL`, and optionally `OPENALEX_API_KEY`, in the environment; nothing secret is stored in the repository.

### What the tests check

I wrote the suite to fail when something is wrong, not to pass by construction. The headline numbers of every supplement are listed in [`docs/supplements/claims/`](docs/supplements/claims/), each with the sentence it appears in and the expression that recomputes it from `results/`; a test fails if the sentence is edited or the value drifts. Other tests pin the committed result tables (flow, bridge, vintage, manifestos, citation age), the change points, the statistics helpers, that every module imports without side effects, and that no file under `src/`, `scripts/` or `tests/` contains a local path. A few checks that need the DuckDB index are marked `heavy` and run only with `NEUROAI_HEAVY=1`. But the default run is the one that matters for reproducing the published numbers.

## Data and provenance

I ran all citation and bridge analyses on one frozen [OpenAlex](https://openalex.org) snapshot dated 30 March 2026, held locally so that every number can be regenerated from a fixed corpus. The snapshot download holds 458,112,708 records of all years; the analysis window, 1990 to 2026, holds 398,288,606 works with 2,893,128,636 citation edges ([S1](docs/supplements/S1-data-and-classification.md) explains the difference and how much of the literature carries reference lists). To check the main result I also sampled two independent sources, the live OpenAlex API and Semantic Scholar ([S2](docs/supplements/S2-citation-flow.md), section 4.5). Live counts drift over time and should not be mixed with the snapshot counts.

OpenAlex data are released under CC0. The 2024 and 2025 values were unstable while OpenAlex rebuilt its records, so I stopped every fit in the supplements at 2023.

### One convention that is easy to invert

`Neuro→AI` means neuroscience informs AI and appears in the data as AI papers citing neuroscience papers. `AI→Neuro` means AI informs neuroscience, measured as neuroscience papers citing AI. The arrow follows where the influence lands, not where the citation points. In the code and in the files under `results/` the two directions carry the opposite names, because there they are named after the citation link: the value `ai_to_neuro` holds AI papers citing neuroscience, which the article draws in teal and labels `Neuro→AI`.

## Layout

```
docs/supplements/   S1 to S6, the claims files and the index
docs/methods/       formal definitions: corpus, classification, metrics, decisions
results/            small committed tables that figures, supplements and tests are built from
figures/            the article and supplement figures (PNG and SVG)
src/neuroai_cn/
  config.py         where things live (NEUROAI_DATA, results/, figures/)
  analysis/         the computations behind the supplements, one module per analysis
  audits/           the pipeline that builds the yearly tables, classifiers and checks (see its README)
  corpus/           the four curated pools
  figures/          figure modules; each reads results/ and writes figures/
  utils/            DuckDB helpers
scripts/            one-time snapshot build, live-API samplers
tests/              the test suite
```

## License

MIT, see [LICENSE](LICENSE). The license covers the code, the documents and the figures in this repository; the underlying OpenAlex data are CC0.

## Citing

If you use the method or the numbers, I would be grateful if you cited the article and this repository (`CITATION.cff`).

# neuroai-citation-network

Code, data and supplements for the article "Examining the bridge between neuroscience and AI" (Renato Duarte, *The Transmitter*). The question: do neuroscience and AI cite each other more than the sizes of the two fields would predict, and which papers, authors and institutions do both fields cite heavily?

## Layout

I keep the analysis, figure and pipeline code in `src/neuroai_cn/`, the snapshot download and API samplers in `scripts/`, the tests in `tests/`, the small tables behind every figure and number in `results/` ([results/README.md](results/README.md)), and the figures in `figures/`.

The six supplements are self-contained: each states the methods I used, the results, the caveats and the commands to reproduce it. [docs/METHODS.md](docs/METHODS.md) has the full equations and selection procedures.

- [S1](docs/supplements/S1-data-and-classification.md): data and field definitions
- [S2](docs/supplements/S2-citation-flow.md): citation flow, article Figure 1
- [S3](docs/supplements/S3-counts-and-field-sizes.md): counts, shares and field sizes, article Figure 2
- [S4](docs/supplements/S4-what-ai-cites.md): what AI cites in neuroscience
- [S5](docs/supplements/S5-bridge-builders.md): bridge builders, article Figure 3
- [S6](docs/supplements/S6-citation-age.md): citation age of bridge works

## Data

I ran all analyses on one frozen [OpenAlex](https://openalex.org) snapshot of 30 March 2026 (458,112,708 records; OpenAlex data are CC0). The snapshot is not in the repository. But the committed tables under `results/` are enough to redraw every figure and recompute every number in the supplements. Rebuilding `results/` from scratch needs the full snapshot, about 364 GB of parquet and a 494 GB DuckDB index. `scripts/download_snapshot.sh <partition>` downloads it with the AWS CLI (`uv sync --extra snapshot`), and `./reproduce.sh heavy` prints the stages in order. Set `NEUROAI_DATA` to the data root (default `~/data/neuroai-citation-network`) and `OPENALEX_EMAIL` for the API samplers.

## Reproduce

You need Python 3.11 or newer and [uv](https://docs.astral.sh/uv/). From the repository root:

```bash
./reproduce.sh setup     # create .venv from the lock file
./reproduce.sh check     # ruff, format check, tests
./reproduce.sh figures   # redraw the figures from results/
./reproduce.sh numbers   # recompute the supplements' numbers
./reproduce.sh all       # all of the above (the default)
./reproduce.sh heavy     # print the snapshot pipeline
```

All modes except `heavy` run from `results/` alone. No snapshot, no network. I pinned the dependencies and the figure font (DejaVu Sans, shipped with matplotlib), so a clean run reproduces the PNGs exactly. SVG files differ in a date stamp and element ids. `tests/test_supplement_claims.py` checks every number listed in `docs/supplements/claims/` and fails if one drifts. Tests marked `heavy` need the DuckDB index and run only with `NEUROAI_HEAVY=1`.

## AI assistance

Generative AI assistants (Claude, Anthropic) were used in writing and refactoring the code and in producing the plots.

## Citation and license

Please cite the article and this repository ([CITATION.cff](CITATION.cff)). If a number does not reproduce for you, I would like to hear about it. MIT license, see [LICENSE](LICENSE).

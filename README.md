# NeuroAI citation network analysis

This repository contains code, data and supplements for the article "Examining the bridge between neuroscience and AI" (Renato Duarte, *The Transmitter*).

>**The central question:** How do neuroscience and AI influence each other? Is there a genuine intellectual exchange?


## Repository structure

I keep the complete analysis, figures and pipeline code in `src/neuroai_cn/`; I provide the snapshot download and the API samplers that gather OpenAlex data in `scripts/`, accompanied by a test battery in `tests/`. I provide the small tables behind every figure and number as compact `csv` files in `results/` ([results/README.md](results/README.md)), and all the figures generated in the analysis are in `figures/`.

The supplements are self-contained documents: each states the methods I used, the results, the caveats and the commands needed to reproduce. [docs/METHODS.md](docs/METHODS.md) expands on the formal methodologies and metrics employed, as well as the complete selection procedures. I provide 6 independent supplements as companions to the main article:

- [S1](docs/supplements/S1-data-and-classification.md): data and field definitions
- [S2](docs/supplements/S2-citation-flow.md): citation flow, article Figure 1
- [S3](docs/supplements/S3-counts-and-field-sizes.md): counts, shares and field sizes, article Figure 2
- [S4](docs/supplements/S4-what-ai-cites.md): what AI cites in neuroscience
- [S5](docs/supplements/S5-bridge-builders.md): bridge builders, article Figure 3
- [S6](docs/supplements/S6-citation-age.md): citation age of bridge works

## Data

All analyses were run on a frozen [OpenAlex](https://openalex.org) snapshot obtained on 30 March 2026 (458,112,708 records; OpenAlex data are CC0). The snapshot is not in the repository. But the committed tables under `results/` are enough to redraw every figure and recompute every number in the supplements. Rebuilding `results/` from scratch needs the full snapshot, about 364 GB of parquet and a 494 GB DuckDB index. `scripts/download_snapshot.sh <partition>` downloads it with the AWS CLI (`uv sync --extra snapshot`), and `./reproduce.sh heavy` prints the stages in order. Set `NEUROAI_DATA` to the data root (default `~/data/neuroai-citation-network`) and `OPENALEX_EMAIL` for the API samplers.

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

Generative AI assistants (Claude Opus 4.6, Claude Opus 5.5 and Claude Sonnet 5.5, by Anthropic) were used in writing, refactoring, testing and documenting the code and in producing the plots. All data, methodologies and results were directed and carefully scrutinized by the author and the interpretation and article text was written solely by the author, with no AI assistance. The author assumes full responsibility for the output.

## Citation and license

Please cite the article and this repository ([CITATION.cff](CITATION.cff)). If a number does not reproduce for you, please reach out. MIT license, see [LICENSE](LICENSE).

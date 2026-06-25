# Pipeline `ville_ideale`

Self-contained data pipeline for **ville-ideale.fr** city reviews, organised as one
folder per data source with the four standard stages.

```
download.py   →  scrape the site          →  data/raw/ville_ideale/{cities,reviews}.jsonl
preprocess.py →  clean / dedup / reshape   →  data/processed/ville_ideale/communes.jsonl
process.py    →  word-cloud enrichment     →  data/processed/ville_ideale/communes_enriched.jsonl
load.py       →  upsert into PostgreSQL    →  table city_reviews (JSONB)
```

Each stage reads the previous stage's output and writes its own, so any stage can be run
on its own and the chain can be resumed at any point.

## Run

```bash
# One department end to end:
python -m src.pipelines.ville_ideale.download --depts 35
python -m src.pipelines.ville_ideale.preprocess
python -m src.pipelines.ville_ideale.process
python -m src.pipelines.ville_ideale.load
```

`download.py` also accepts `--codes 35238` (specific communes) and `--jobdir <dir>`
(resumable crawl). `load.py` validates each `code_commune` against the `communes`
reference table (foreign key) and skips/logs the unknown ones.

## Stage contracts

| Stage | Input | Output | DB? | Key functions |
|-------|-------|--------|-----|----------------|
| download | — (the web) | raw JSONL | no | `run()` |
| preprocess | raw JSONL | `communes.jsonl` | no | `group_reviews`, `build_records` |
| process | `communes.jsonl` | `communes_enriched.jsonl` | no | `tokenize`, `word_cloud`, `enrich` |
| load | `communes_enriched.jsonl` | `city_reviews` | yes | `filter_known_communes`, `load` |

## Assumptions (to confirm against the final refactor)

The team's new "one folder per data type" convention was not yet shared when this was
written, so the following choices are provisional and easy to change:

- **Location**: `src/pipelines/<source>/`. Move the folder if the agreed root differs.
- **No base class**: each stage is a plain module with a `run()` and a `main()`
  (`python -m src.pipelines.ville_ideale.<stage>`). If a shared `Pipeline` base /
  interface is introduced, the `run()` functions are the natural adapt points.
- **Self-contained**: the NLP (`process.py`) and the DB load + table DDL (`load.py`)
  are kept inside this folder and do **not** import the (separately refactored)
  `src/processing` or `src/database` modules. The earlier copies there
  (`reviews_wordcloud.py`, `load_city_reviews` in `postgres_loader.py`, the
  `city_reviews` table in `postgres_schema.sql`) are now superseded by this folder and
  can be removed once the refactor lands.

The Scrapy spider itself still lives in `src/scraping/ville_ideale/`; `download.py` drives
it. It can be moved under this folder later without changing the stage contracts.

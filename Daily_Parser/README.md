# AI Daily Brief Engine

**Language / 语言**: [English](README.md) · [中文](README.zh.md)

A **Daily Brief** product for AI practitioners: automatically fetches TLDR AI, Techmeme, and similar sources, then cleans, filters, translates, and tags items for a static reading site.

**Production URL**: https://koalafionagao-ai.github.io/cursor/ai_daily/

---

## Repository layout

```
Daily_Parser/
├── README.md                 # This file (English)
├── README.zh.md              # 使用说明（中文）
├── docs/
│   ├── PROJECT.md / PROJECT.zh.md   # Product & technical spec
│   ├── TAGS.md / TAGS.zh.md         # Tag taxonomy
│   └── reference-design.html        # Early UI mock (not deployed)
├── common/                   # Shared modules (taxonomy, LLM, schema)
├── Techmeme/                 # Agent1 raw fetch JSON
├── TLDR/                     # Agent1 raw fetch JSON
├── Processed/                # Agent2–4 artifacts & publish JSON
├── logs/pipeline/            # Structured English pipeline run logs (Markdown)
├── site/                     # Static frontend + built data/
│   ├── index.html
│   ├── assets/
│   └── data/
│       ├── manifest.json
│       ├── daily/
│       ├── monthly/
│       └── filter-report/
├── techmeme_fetcher.py       # Fetch Techmeme
├── tldr_fetcher.py           # Fetch TLDR AI
├── merge_cleaner.py          # Agent2: merge & dedupe
├── filter_scorer.py          # Agent3: LLM filter scoring
├── enrich.py                 # Agent4: translate + category + tags
├── build_site_data.py        # Agent5: sync site/data
├── finalize_pipeline_log.py  # Finalize run log + print English summary
├── regenerate_pipeline_log.py # Rebuild Markdown logs from legacy JSON/state
├── backfill_processed.py     # Batch backfill utility
└── requirements.txt
```

---

## Local development

```bash
cd Daily_Parser
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GH_MODELS_TOKEN=your_token   # GitHub Models

DATE=2026-06-02
python3 techmeme_fetcher.py --date $DATE
python3 tldr_fetcher.py --date $DATE
python3 merge_cleaner.py --date $DATE
python3 filter_scorer.py --date $DATE
python3 enrich.py --date $DATE
python3 build_site_data.py --date $DATE
python3 finalize_pipeline_log.py --date $DATE
```

Preview the site locally (needs an HTTP server; adjust `base-path` in `site/index.html` if needed):

```bash
cd site && python3 -m http.server 8765
# For production-like paths, serve under /cursor/ai_daily/ (nginx, etc.)
# Asset paths follow meta base-path
```

---

## GitHub Actions

| Workflow | Description |
|----------|-------------|
| `AI Daily Pipeline` | Daily schedule (~09:00 Beijing) or manual: fetch → process → commit `Daily_Parser/site/data` and pipeline logs |

**Monitoring**: after each run, check `Daily_Parser/logs/pipeline/index.md` (rollup table) or `Daily_Parser/logs/pipeline/YYYY-MM/YYYY-MM-DD.md` (per-step tables with GitHub workflow/step, scripts, I/O files, timing, metrics, status, errors). Warnings fire when published items fall below 15.
| `Deploy AI Daily to GitHub Pages` | Publishes `Daily_Parser/site` under **`/cursor/ai_daily/`** |

Repo **Settings → Pages → Source**: **GitHub Actions**.

---

## Configuration

- **Base path**: `/cursor/ai_daily/` (written by `build_site_data.py` to `manifest.json`; matches frontend `meta base-path`)
- **Filter threshold**: default `score >= 7`; see `filter_scorer.py` and [docs/TAGS.md](docs/TAGS.md)
- **Tags**: fixed vocabulary in `common/taxonomy.py`

---

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/PROJECT.md](docs/PROJECT.md) | Product logic, architecture, data pipeline, frontend features |
| [docs/TAGS.md](docs/TAGS.md) | Category and entity tags |

---

## Legacy URL

If you used `https://koalafionagao-ai.github.io/cursor/#/…` (site at repo root), switch to:

**https://koalafionagao-ai.github.io/cursor/ai_daily/#/2026-06**

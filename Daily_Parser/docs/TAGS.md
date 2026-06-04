# AI Daily fixed tag taxonomy

**Language / 语言**: [English](TAGS.md) · [中文](TAGS.zh.md)

## Category tags (exactly one per item)

| Tag | Meaning | UI label (English) |
|-----|---------|-------------------|
| `cat:model` | Model releases, upgrades, capability breakthroughs | **Models** |
| `cat:tech` | Infrastructure, tools, algorithms, security | **Technology** |
| `cat:app` | Products, features, use cases | **Applications** |
| `cat:business` | Funding, M&A, policy, market, people moves | **Business** |
| `cat:other` | Everything else | **Other** |

Chinese UI labels: 新模型、新技术、新应用、新商业、其它 (`manifest.json` → `categories[].zh`).

## Entity tags (0–4 per item)

Full list and alias mapping: `Daily_Parser/common/taxonomy.py`.

- **Companies**: anthropic, openai, google, meta, nvidia, bytedance, mistral, …
- **Products / models**: claude, gpt, gemini, llama, copilot, deepseek, …
- **People**: sam-altman, dario-amodei, demis-hassabis, …
- **Topics**: agent, rag, chip, regulation, funding, multimodal, …

LLM output is normalized via `normalize_tags()`; candidates outside the allowlist are dropped.

## Filter score

In `filter_*.json`, `score` is 0–10 (LLM + rules). Default: `keep = score >= 7`. Tune density via `filter_scorer.py --threshold` or the workflow.

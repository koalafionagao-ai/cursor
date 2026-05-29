# AI Daily

全 GitHub 闭环的 AI 日报引擎：RSS 抓取 → 清洗 → 筛选打分 → LLM 翻译打标签 → 静态站点（GitHub Pages）。

## 目录

- `Daily_Parser/` — 数据流水线（Python）
- `site/` — 静态前端（视觉对标 `reference.html`）
- `reference.html` — 设计参考，勿直接部署

## 本地运行

```bash
cd Daily_Parser
pip install -r requirements.txt
export GH_MODELS_TOKEN=...   # GitHub Models

DATE=2026-05-28
python3 techmeme_fetcher.py --date $DATE
python3 tldr_fetcher.py --date $DATE
python3 merge_cleaner.py --date $DATE
python3 filter_scorer.py --date $DATE      # 产出 filter_*.json 供调阈值
python3 enrich.py --date $DATE
python3 build_site_data.py --date $DATE
```

筛选报告：`Daily_Parser/Processed/YYYY-MM/filter_YYYY-MM-DD.json`（含每条 `score` / `keep` / `reason`）。

## GitHub Pages

1. 仓库 **Settings → Pages → Build and deployment → GitHub Actions**
2. 推荐将仓库改名为 **`ai-daily`**，站点即为 `https://<user>.github.io/ai-daily/`
3. 在改名前，前端会自动识别 `/cursor/` 或 `/ai-daily/` 路径

## 固定标签

见 `Daily_Parser/common/taxonomy.py`：`cat:*` 分类 + 公司/产品/人物/主题实体标签，LLM 仅可从允许列表选取。

## Actions

- `daily-pipeline.yml` — 每日流水线（北京时间默认「昨日」简报日）
- `deploy-pages.yml` — 部署 `site/` 到 Pages

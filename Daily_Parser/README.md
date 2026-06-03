# AI Daily 简报引擎

面向 AI 从业者的**每日简报（Daily Brief）**产品：自动抓取 TLDR AI、Techmeme 等源站，经清洗、筛选、翻译与打标后，发布为可浏览的静态站点。

**线上地址（Production URL）**：https://koalafionagao-ai.github.io/cursor/ai_daily/

---

## 目录结构（Repository layout）

```
Daily_Parser/
├── README.md                 # 本文件：使用说明
├── docs/
│   ├── PROJECT.md            # 产品逻辑、架构、数据流（完整说明）
│   ├── TAGS.md               # 标签体系
│   └── reference-design.html # 早期 UI 参考（不部署）
├── common/                   # 共享模块（taxonomy、LLM、schema）
├── Techmeme/                 # Agent1 原始抓取 JSON
├── TLDR/                     # Agent1 原始抓取 JSON
├── Processed/                # Agent2–4 中间产物与发布稿
├── site/                     # 静态前端 + 构建后的 data/
│   ├── index.html
│   ├── assets/
│   └── data/
│       ├── manifest.json
│       ├── daily/
│       ├── monthly/
│       └── filter-report/
├── techmeme_fetcher.py       # 抓取 Techmeme
├── tldr_fetcher.py           # 抓取 TLDR AI
├── merge_cleaner.py          # Agent2：合并去重
├── filter_scorer.py          # Agent3：LLM 打分筛选
├── enrich.py                 # Agent4：翻译 + 分类 + 标签
├── build_site_data.py        # Agent5：同步 site/data
├── backfill_processed.py     # 批量补跑工具
└── requirements.txt
```

---

## 本地开发（Local development）

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
```

本地预览站点（需 HTTP 服务，且 base 与线上一致时可改 `site/index.html` 的 `base-path`）：

```bash
cd site && python3 -m http.server 8765
# 浏览器访问路径需包含 /cursor/ai_daily/ 前缀时，可用 nginx 或：
# npx serve -l 8765 --cors  （仅开发；资产路径以 meta base-path 为准）
```

---

## GitHub Actions

| Workflow | 说明 |
|----------|------|
| `AI Daily Pipeline` | 每日定时（北京时间约 09:00）或手动：抓取 → 处理 → 提交 `Daily_Parser/site/data` |
| `Deploy AI Daily to GitHub Pages` | 将 `Daily_Parser/site` 发布到 **`/cursor/ai_daily/`** 子路径 |

仓库 Settings → Pages → Source：**GitHub Actions**。

---

## 配置要点

- **站点根路径（Base path）**：`/cursor/ai_daily/`（由 `build_site_data.py` 写入 `manifest.json`，前端 `meta base-path` 一致）
- **筛选阈值（Filter threshold）**：默认 `score >= 7`，见 `filter_scorer.py` 与 `docs/TAGS.md`
- **标签（Tags）**：固定词表，见 `common/taxonomy.py`

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [docs/PROJECT.md](docs/PROJECT.md) | 产品逻辑、技术架构、数据处理全流程、前端功能 |
| [docs/TAGS.md](docs/TAGS.md) | 分类与实体标签说明 |

---

## 历史 URL 说明

若曾使用 `https://koalafionagao-ai.github.io/cursor/#/…`（站点在仓库根路径），请改用：

**https://koalafionagao-ai.github.io/cursor/ai_daily/#/2026-06**

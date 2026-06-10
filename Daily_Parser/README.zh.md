# AI Daily 简报引擎

**Language / 语言**: [English](README.md) · [中文](README.zh.md)

面向 AI 从业者的**每日简报（Daily Brief）**产品：自动抓取 TLDR AI、Techmeme 等源站，经清洗、筛选、翻译与打标后，发布为可浏览的静态站点。

**线上地址（Production URL）**：https://koalafionagao-ai.github.io/cursor/ai_daily/

---

## 目录结构（Repository layout）

```
Daily_Parser/
├── README.md                 # 使用说明（English）
├── README.zh.md              # 使用说明（中文）
├── docs/
│   ├── PROJECT.md / PROJECT.zh.md   # 产品与技术说明
│   ├── TAGS.md / TAGS.zh.md         # 标签体系
│   └── reference-design.html # 早期 UI 参考（不部署）
├── common/                   # 共享模块（taxonomy、LLM、schema）
├── Techmeme/                 # Agent1 原始抓取 JSON
├── TLDR/                     # Agent1 原始抓取 JSON
├── Processed/                # Agent2–4 中间产物与发布稿
├── logs/pipeline/            # 流水线运行日志（Markdown）
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
├── finalize_pipeline_log.py  # 收尾日志并打印摘要
├── regenerate_pipeline_log.py # 从 state/旧 JSON 重建 Markdown 日志
├── backfill_processed.py     # 批量补跑工具
└── requirements.txt
```

---

## 本地开发（Local development）

```bash
cd Daily_Parser
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Agent3–4 需 LLM：按 common/llm.py 配置 API（本地环境或 CI）

DATE=2026-06-02
python3 techmeme_fetcher.py --date $DATE
python3 tldr_fetcher.py --date $DATE
python3 merge_cleaner.py --date $DATE
python3 filter_scorer.py --date $DATE
python3 enrich.py --date $DATE
python3 build_site_data.py --date $DATE
python3 finalize_pipeline_log.py --date $DATE
```

本地预览站点（需 HTTP 服务，且 base 与线上一致时可改 `site/index.html` 的 `base-path`）：

```bash
cd site && python3 -m http.server 8765
# 浏览器访问路径需包含 /cursor/ai_daily/ 前缀时，可用 nginx 或：
# npx serve -l 8765 --cors  （仅开发；资产路径以 meta base-path 为准）
```

---

## GitHub Actions

| Workflow | 何时运行 | 说明 |
|----------|----------|------|
| `AI Daily Pipeline` | **Cron** `0 1 * * *` UTC（北京时间约 09:00）或手动 | 对某一简报日（默认可设为北京时间昨日）跑 Agent1–5、写日志、提交产物 |
| `Deploy AI Daily to GitHub Pages` | Pipeline 完成后 / 推送 `main` / 手动（**无 cron**） | 发布 `Daily_Parser/site` 到 **`/cursor/ai_daily/`** |

仓库 Settings → Pages → Source：**GitHub Actions**。

步骤顺序、脚本与文件对照：[docs/PROJECT.zh.md §4.0](docs/PROJECT.zh.md#40-github-actions--定时与步骤顺序)。

---

## 流水线日志（Pipeline logging）

**是什么**：`common/pipeline_log.py` 在 `logs/pipeline/` 下生成英文 Markdown 运行日志。

**作用**：记录各 Agent 步骤的顺序、耗时、数据量、结果与异常，便于尽早发现「某天条数过少、某步失败」等问题。

**怎么做**：

1. 各 Agent 脚本通过 `PipelineLogger(...).step(...)` 记录 metrics 与状态；
2. CI 在 Agent5 之后执行 `finalize_pipeline_log.py`，提交 `logs/pipeline/YYYY-MM/YYYY-MM-DD.md` 与 `index.md`；
3. 日常先看 **index** 汇总表，有问题再打开对应日期的 **日志文件**（含定时说明、步骤顺序表、异常、Step summary）。

**命令**：

```bash
python3 finalize_pipeline_log.py --date YYYY-MM-DD    # 收尾并打印日志
python3 regenerate_pipeline_log.py --date YYYY-MM-DD  # 从 state/旧 JSON 重建 .md
```

详见 [docs/PROJECT.zh.md §4.1](docs/PROJECT.zh.md#41-流水线日志模块pipeline-logging)。

---

## 配置要点

- **站点根路径（Base path）**：`/cursor/ai_daily/`（由 `build_site_data.py` 写入 `manifest.json`，前端 `meta base-path` 一致）
- **筛选阈值（Filter threshold）**：默认 `score >= 7`，见 `filter_scorer.py` 与 [docs/TAGS.zh.md](docs/TAGS.zh.md)
- **标签（Tags）**：固定词表，见 `common/taxonomy.py`

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [docs/PROJECT.zh.md](docs/PROJECT.zh.md) | 产品逻辑、技术架构、数据处理全流程、前端功能 |
| [docs/TAGS.zh.md](docs/TAGS.zh.md) | 分类与实体标签说明 |

---

## 历史 URL 说明

若曾使用 `https://koalafionagao-ai.github.io/cursor/#/…`（站点在仓库根路径），请改用：

**https://koalafionagao-ai.github.io/cursor/ai_daily/#/2026-06**

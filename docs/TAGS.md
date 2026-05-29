# AI Daily 固定标签体系

## 分类标签（每条必选 1 个）

| 标签 | 含义 |
|------|------|
| `cat:model` | 新模型：发布、升级、能力突破 |
| `cat:tech` | 新技术：基础设施、工具、算法、安全 |
| `cat:app` | 新应用：产品、功能、场景 |
| `cat:business` | 新商业：融资、并购、政策、市场、人事 |
| `cat:other` | 其它 |

## 实体标签（每条 0–4 个）

完整列表与别名映射见 `Daily_Parser/common/taxonomy.py`。

- **公司**：anthropic, openai, google, meta, nvidia, bytedance, mistral, …
- **产品/模型**：claude, gpt, gemini, llama, copilot, deepseek, …
- **人物**：sam-altman, dario-amodei, demis-hassabis, …
- **主题**：agent, rag, chip, regulation, funding, multimodal, …

LLM 输出经 `normalize_tags()` 归一化；未命中允许列表的候选会被丢弃。

## 筛选分数

`filter_*.json` 中 `score` 为 0–10（LLM + 规则）。默认 `keep = score >= 6`。请根据实际日报密度在 `filter_scorer.py --threshold` 或 workflow 中调整。

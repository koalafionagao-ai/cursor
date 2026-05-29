"""
固定标签体系：分类标签 + AI 主体/产品/人物/主题标签。
LLM 只能从 ALLOWED_TAGS 中选择；归一化将别名映射到 canonical。
"""

from __future__ import annotations

import re

# ── 分类（并入标签，每条至少 1 个 cat:*）────────────────────────────
CATEGORY_TAGS: dict[str, str] = {
    "cat:model": "新模型",
    "cat:tech": "新技术",
    "cat:app": "新应用",
    "cat:business": "新商业",
    "cat:other": "其它",
}

CATEGORY_ID_TO_TAG = {
    1: "cat:model",
    2: "cat:tech",
    3: "cat:app",
    4: "cat:business",
    5: "cat:other",
}

# ── 公司与机构 ────────────────────────────────────────────────────
COMPANY_TAGS = [
    "anthropic",
    "openai",
    "google",
    "deepmind",
    "meta",
    "microsoft",
    "apple",
    "amazon",
    "nvidia",
    "amd",
    "intel",
    "qualcomm",
    "ibm",
    "oracle",
    "salesforce",
    "stripe",
    "visa",
    "bytedance",
    "alibaba",
    "tencent",
    "baidu",
    "huawei",
    "mistral",
    "xai",
    "cohere",
    "huggingface",
    "stability-ai",
    "midjourney",
    "runway",
    "perplexity",
    "databricks",
    "snowflake",
    "palantir",
    "tesla",
    "uber",
    "airbnb",
    "reddit",
    "snap",
    "spotify",
    "adobe",
    "notion",
    "figma",
    "shopify",
    "tiktok",
    "jd",
    "samsung",
    "sony",
    "softbank",
    "openrouter",
    "replit",
    "cursor",
    "github",
    "gitlab",
    "cloudflare",
    "coreweave",
    "lambda-labs",
]

# ── 产品与模型系列 ────────────────────────────────────────────────
PRODUCT_TAGS = [
    "claude",
    "gpt",
    "chatgpt",
    "gemini",
    "llama",
    "copilot",
    "sora",
    "grok",
    "deepseek",
    "qwen",
    "ernie",
    "mixtral",
    "opus",
    "sonnet",
    "haiku",
    "o-series",
    "stable-diffusion",
    "dall-e",
    "midjourney",
    "whisper",
    "codex",
    "claude-code",
    "github-copilot",
    "azure-openai",
    "vertex-ai",
    "bedrock",
    "wandb",
    "langchain",
    "llamaindex",
]

# ── 关键人物（高频出现在 AI 资讯）────────────────────────────────
PEOPLE_TAGS = [
    "sam-altman",
    "dario-amodei",
    "demis-hassabis",
    "sundar-pichai",
    "satya-nadella",
    "jensen-huang",
    "elon-musk",
    "mark-zuckerberg",
    "tim-cook",
    "yann-lecun",
    "andrej-karpathy",
    "ilya-sutskever",
    "fei-fei-li",
    "jensen-huang",
]

# ── 技术/主题（跨公司）──────────────────────────────────────────
TOPIC_TAGS = [
    "agent",
    "rag",
    "fine-tuning",
    "open-source",
    "safety",
    "alignment",
    "regulation",
    "policy",
    "chip",
    "gpu",
    "inference",
    "training",
    "multimodal",
    "coding",
    "robotics",
    "autonomous-driving",
    "quantum",
    "enterprise",
    "startup",
    "funding",
    "ipo",
    "acquisition",
    "benchmark",
    "reasoning",
    "video-gen",
    "image-gen",
    "voice",
    "search",
    "browser",
    "ide",
    "api",
    "pricing",
    "open-weights",
    "data-center",
    "energy",
]

ENTITY_TAGS = sorted(set(COMPANY_TAGS + PRODUCT_TAGS + PEOPLE_TAGS + TOPIC_TAGS))

ALLOWED_TAGS: frozenset[str] = frozenset(
    list(CATEGORY_TAGS.keys()) + ENTITY_TAGS
)

# 别名 → canonical（小写、去空格）
ALIASES: dict[str, str] = {
    # 公司
    "open ai": "openai",
    "open-ai": "openai",
    "anthropic inc": "anthropic",
    "google deepmind": "deepmind",
    "deep mind": "deepmind",
    "alphabet": "google",
    "facebook": "meta",
    "fb": "meta",
    "msft": "microsoft",
    "amzn": "amazon",
    "nvda": "nvidia",
    "byte dance": "bytedance",
    "tik tok": "tiktok",
    "stability": "stability-ai",
    "stability ai": "stability-ai",
    "hf": "huggingface",
    "hugging face": "huggingface",
    "x.ai": "xai",
    # 产品
    "gpt-4": "gpt",
    "gpt-4o": "gpt",
    "gpt-5": "gpt",
    "gpt4": "gpt",
    "chat gpt": "chatgpt",
    "claude 3": "claude",
    "claude-3": "claude",
    "claude 4": "claude",
    "claude-4": "claude",
    "opus 4": "opus",
    "sonnet 4": "sonnet",
    "gemini 2": "gemini",
    "gemini-2": "gemini",
    "llama 3": "llama",
    "llama-3": "llama",
    "llama 4": "llama",
    "o1": "o-series",
    "o3": "o-series",
    "o4": "o-series",
    "deep seek": "deepseek",
    "stable diffusion": "stable-diffusion",
    "dalle": "dall-e",
    "dall·e": "dall-e",
    "claude code": "claude-code",
    "github copilot": "github-copilot",
    # 人物
    "sam altman": "sam-altman",
    "dario amodei": "dario-amodei",
    "demis hassabis": "demis-hassabis",
    # 主题
    "ai agent": "agent",
    "ai agents": "agent",
    "agents": "agent",
    "retrieval": "rag",
    "finetuning": "fine-tuning",
    "fine tuning": "fine-tuning",
    "open source": "open-source",
    "open weights": "open-weights",
    "regulations": "regulation",
    "gpu": "chip",
    "gpus": "chip",
    "semiconductor": "chip",
    "venture": "funding",
    "series a": "funding",
    "series b": "funding",
    # 分类口语
    "新模型": "cat:model",
    "模型": "cat:model",
    "新技术": "cat:tech",
    "技术": "cat:tech",
    "新应用": "cat:app",
    "应用": "cat:app",
    "新商业": "cat:business",
    "商业": "cat:business",
    "其它": "cat:other",
    "其他": "cat:other",
}


def _slug(text: str) -> str:
    t = text.strip().lower()
    t = re.sub(r"[^\w\s\-·.]", "", t)
    t = t.replace("·", "").replace(".", "")
    t = re.sub(r"\s+", "-", t)
    return t


def normalize_tag(raw: str) -> str | None:
    if not raw:
        return None
    key = raw.strip().lower()
    if key in ALLOWED_TAGS:
        return key
    if key in ALIASES:
        return ALIASES[key]
    slug = _slug(key)
    if slug in ALLOWED_TAGS:
        return slug
    if slug in ALIASES:
        return ALIASES[slug]
    # 尝试去掉 Inc/Ltd 等
    for suffix in ("-inc", "-ltd", "-corp", "-ai"):
        if slug.endswith(suffix):
            base = slug[: -len(suffix)]
            if base in ALLOWED_TAGS:
                return base
            if base in ALIASES:
                return ALIASES[base]
    return None


def normalize_tags(
    raw_tags: list[str],
    *,
    category_id: int | None = None,
) -> list[str]:
    out: list[str] = []
    if category_id is not None:
        cat = CATEGORY_ID_TO_TAG.get(category_id, "cat:other")
        out.append(cat)
    for t in raw_tags or []:
        n = normalize_tag(t)
        if n and n not in out:
            out.append(n)
    if not any(t.startswith("cat:") for t in out):
        out.insert(0, "cat:other")
    return out


def tags_for_prompt() -> str:
    """供 LLM system prompt 使用的标签清单摘要。"""
    lines = [
        "【分类标签，每条必选且仅选 1 个】",
        ", ".join(f"{k}({v})" for k, v in CATEGORY_TAGS.items()),
        "",
        "【主体/产品/人物/主题标签，每条选 0–4 个，必须从下列列表中选，不要自造】",
        "公司: " + ", ".join(COMPANY_TAGS[:40]) + ", ...",
        "产品: " + ", ".join(PRODUCT_TAGS[:30]) + ", ...",
        "人物: " + ", ".join(PEOPLE_TAGS),
        "主题: " + ", ".join(TOPIC_TAGS),
    ]
    return "\n".join(lines)


def category_label(tag: str, lang: str = "zh") -> str:
    if tag in CATEGORY_TAGS:
        return CATEGORY_TAGS[tag] if lang == "zh" else tag.replace("cat:", "").replace("-", " ").title()
    return tag

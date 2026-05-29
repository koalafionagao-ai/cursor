/**
 * 标签分组（PM 阅读视角）：覆盖 taxonomy 实体标签，未命中归入「其它」。
 */
window.AI_DAILY_TAG_GROUPS = [
  {
    id: "labs",
    label: { zh: "AI 公司与生态", en: "AI companies" },
    tags: [
      "anthropic", "openai", "google", "deepmind", "meta", "microsoft", "apple", "amazon",
      "mistral", "xai", "cohere", "huggingface", "ibm", "bytedance", "alibaba", "tencent",
      "baidu", "huawei", "nvidia", "amd", "intel", "qualcomm", "databricks", "snowflake",
      "palantir", "salesforce", "oracle", "perplexity", "runway", "stability-ai", "midjourney",
      "stripe", "visa", "replit", "github", "gitlab", "cloudflare", "coreweave", "lambda-labs",
      "openrouter", "cursor", "tesla", "softbank", "samsung", "sony",
    ],
  },
  {
    id: "models",
    label: { zh: "模型与助手", en: "Models & assistants" },
    tags: [
      "claude", "gpt", "chatgpt", "gemini", "llama", "copilot", "grok", "deepseek", "qwen",
      "ernie", "mixtral", "opus", "sonnet", "haiku", "o-series", "stable-diffusion", "dall-e", "sora",
      "claude-code", "github-copilot", "azure-openai", "vertex-ai", "bedrock", "codex", "whisper",
      "langchain", "llamaindex", "wandb",
    ],
  },
  {
    id: "infra",
    label: { zh: "算力与基础设施", en: "Compute & infra" },
    tags: [
      "chip", "gpu", "data-center", "energy", "inference", "training", "quantum",
          ],
  },
  {
    id: "business",
    label: { zh: "融资、市场与政策", en: "Business & policy" },
    tags: [
      "startup", "funding", "ipo", "acquisition", "enterprise", "pricing", "regulation", "policy",
      "benchmark", "reasoning",
    ],
  },
  {
    id: "tech",
    label: { zh: "技术与应用方向", en: "Tech & applications" },
    tags: [
      "agent", "rag", "coding", "multimodal", "video-gen", "image-gen", "voice", "search",
      "browser", "ide", "api", "open-source", "open-weights", "safety", "alignment",
      "fine-tuning", "robotics", "autonomous-driving",
    ],
  },
  {
    id: "people",
    label: { zh: "人物", en: "People" },
    tags: [
      "sam-altman", "dario-amodei", "demis-hassabis", "sundar-pichai", "satya-nadella",
      "jensen-huang", "elon-musk", "mark-zuckerberg", "tim-cook", "yann-lecun",
      "andrej-karpathy", "ilya-sutskever", "fei-fei-li",
    ],
  },
  {
    id: "other",
    label: { zh: "其它公司与场景", en: "Other" },
    tags: [
      "adobe", "notion", "figma", "shopify", "tiktok", "jd", "uber", "airbnb", "reddit",
      "snap", "spotify",
    ],
  },
];

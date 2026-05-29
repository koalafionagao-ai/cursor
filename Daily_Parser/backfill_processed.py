#!/usr/bin/env python3
"""从既有 AI_Brief_*.md 回填 processed_*.json（迁移用，一次性）。"""

import json
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CAT_MAP = {
    "1 新模型": 1,
    "2 新技术": 2,
    "3 新应用": 3,
    "4 新商业": 4,
    "5 其它": 5,
}


def parse_brief(md_path: Path) -> dict | None:
    text = md_path.read_text(encoding="utf-8")
    m = re.search(r"# AI 简报 \| (\d{4}-\d{2}-\d{2})", text)
    if not m:
        return None
    date = m.group(1)
    items = []
    current_cat = 5
    for line in text.splitlines():
        if line.startswith("# ") and line[2:3].isdigit():
            head = line[2:].split("\n")[0].strip()
            for key, cid in CAT_MAP.items():
                if head.startswith(key):
                    current_cat = cid
                    break
        hm = re.match(r"^### \(\d+\) (.+)$", line)
        if hm:
            items.append(
                {
                    "id": f"LEGACY-{len(items)+1:03d}",
                    "category_id": current_cat,
                    "source": "Techmeme",
                    "url": "",
                    "title": {"zh": hm.group(1).strip(), "en": ""},
                    "summary": {"zh": "", "en": ""},
                    "tags": [f"cat:{['model','tech','app','business','other'][current_cat-1]}"],
                    "tweets": [],
                }
            )
            continue
        if items and line.startswith("**原文链接**:"):
            link = re.search(r"\[([^\]]+)\]\(([^)]+)\)", line)
            if link:
                items[-1]["title"]["en"] = link.group(1)
                items[-1]["url"] = link.group(2)
        if items and line.startswith("**摘要**:"):
            items[-1]["summary"]["zh"] = line.replace("**摘要**:", "").strip()

    return {
        "date": date,
        "sources": ["Techmeme"],
        "stats": {"total": len(items), "by_category": {}},
        "items": items,
    }


def main():
    for md in sorted(SCRIPT_DIR.glob("Processed/**/AI_Brief_*.md")):
        data = parse_brief(md)
        if not data:
            continue
        out = md.parent / f"processed_{data['date']}.json"
        if out.exists():
            continue
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"backfill {out.name} ({data['stats']['total']} items)")


if __name__ == "__main__":
    main()

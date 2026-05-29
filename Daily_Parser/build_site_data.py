#!/usr/bin/env python3
"""Agent5: 将 processed_*.json 同步到 site/data/，并生成 manifest。"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SITE_DATA = REPO_ROOT / "site" / "data"
DAILY_DIR = SITE_DATA / "daily"
FILTER_DIR = SITE_DATA / "filter-report"

sys.path.insert(0, str(SCRIPT_DIR))

from common.dates import parse_date_list  # noqa: E402
from common.taxonomy import CATEGORY_TAGS  # noqa: E402


def collect_all_processed() -> list[Path]:
    processed_dir = SCRIPT_DIR / "Processed"
    return sorted(processed_dir.glob("**/processed_*.json"))


def build_manifest(files: list[Path]) -> dict:
    days = []
    for p in files:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        date = data.get("date", p.stem.replace("processed_", ""))
        stats = data.get("stats", {})
        title_zh = f"AI 简报 {date}"
        title_en = f"AI Daily {date}"
        days.append(
            {
                "date": date,
                "title_zh": title_zh,
                "title_en": title_en,
                "total": stats.get("total", len(data.get("items", []))),
                "sources": data.get("sources", []),
                "path": f"data/daily/{date}.json",
            }
        )
    days.sort(key=lambda x: x["date"], reverse=True)
    return {
        "site_name": "AI Daily",
        "base_path": "/ai-daily/",
        "categories": [
            {"id": "cat:model", "zh": "新模型", "en": "Models", "emoji": "🧠"},
            {"id": "cat:tech", "zh": "新技术", "en": "Technology", "emoji": "⚙️"},
            {"id": "cat:app", "zh": "新应用", "en": "Applications", "emoji": "📱"},
            {"id": "cat:business", "zh": "新商业", "en": "Business", "emoji": "💼"},
            {"id": "cat:other", "zh": "其它", "en": "Other", "emoji": "📌"},
        ],
        "days": days,
        "category_labels": CATEGORY_TAGS,
    }


def sync_date(date_str: str) -> None:
    month = date_str[:7]
    src = SCRIPT_DIR / "Processed" / month / f"processed_{date_str}.json"
    if not src.exists():
        print(f"⚠️ 无 processed_{date_str}.json")
        return
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, DAILY_DIR / f"{date_str}.json")

    filter_src = SCRIPT_DIR / "Processed" / month / f"filter_{date_str}.json"
    if filter_src.exists():
        FILTER_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(filter_src, FILTER_DIR / f"{date_str}.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", nargs="*", default=[], help="仅同步指定日期；默认全量")
    args = parser.parse_args()

    SITE_DATA.mkdir(parents=True, exist_ok=True)
    DAILY_DIR.mkdir(parents=True, exist_ok=True)

    if args.date:
        for d in parse_date_list(args.date):
            sync_date(d)
        files = [DAILY_DIR / f"{d}.json" for d in parse_date_list(args.date) if (DAILY_DIR / f"{d}.json").exists()]
    else:
        for p in collect_all_processed():
            date = p.stem.replace("processed_", "")
            sync_date(date)
        files = list(DAILY_DIR.glob("*.json"))

    manifest = build_manifest([Path(f) for f in files if Path(f).exists()])
    with open(SITE_DATA / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"✅ manifest: {len(manifest['days'])} 天")


if __name__ == "__main__":
    main()

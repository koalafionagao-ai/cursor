#!/usr/bin/env python3
"""Agent5: 同步 daily + 生成按月聚合与 manifest。"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SITE_DATA = SCRIPT_DIR / "site" / "data"
SITE_BASE_PATH = "/cursor/ai_daily/"
DAILY_DIR = SITE_DATA / "daily"
MONTHLY_DIR = SITE_DATA / "monthly"
FILTER_DIR = SITE_DATA / "filter-report"

sys.path.insert(0, str(SCRIPT_DIR))

from common.dates import parse_date_list  # noqa: E402
from common.taxonomy import CATEGORY_TAGS  # noqa: E402
from common.text_utils import is_duplicate, pick_summary  # noqa: E402


def collect_all_processed() -> list[Path]:
    return sorted((SCRIPT_DIR / "Processed").glob("**/processed_*.json"))


def normalize_item(item: dict, date: str) -> dict:
    """发布前裁剪重复摘要；英文始终用原文。"""
    title = item.get("title") or {}
    summary = item.get("summary") or {}
    en_t = (title.get("en") or "").strip()
    zh_t = (title.get("zh") or "").strip()
    en_s = pick_summary(en_t, (summary.get("en") or "").strip())
    zh_s = (summary.get("zh") or "").strip()
    if is_duplicate(zh_t, zh_s):
        zh_s = ""
    out = {**item, "date": date, "title": {"zh": zh_t, "en": en_t}, "summary": {"zh": zh_s, "en": en_s}}
    entity = [t for t in (item.get("tags") or []) if not str(t).startswith("cat:")]
    out["entity_tags"] = entity
    out["category_tag"] = next((t for t in (item.get("tags") or []) if str(t).startswith("cat:")), "cat:other")
    return out


def build_monthly(month: str, daily_files: dict[str, Path]) -> dict:
    days = sorted([d for d in daily_files if d.startswith(month)], reverse=True)
    items: list[dict] = []
    tag_index: dict[str, list[str]] = defaultdict(list)
    cat_index: dict[str, list[str]] = defaultdict(list)
    day_summaries = []

    for day in sorted(days):
        with open(daily_files[day], encoding="utf-8") as f:
            brief = json.load(f)
        for raw in brief.get("items", []):
            it = normalize_item(raw, day)
            key = f"{day}:{it['id']}"
            items.append(it)
            cat_index[it["category_tag"]].append(key)
            for tag in it["entity_tags"]:
                tag_index[tag].append(key)
        day_summaries.append(
            {
                "date": day,
                "total": len(brief.get("items", [])),
                "sources": brief.get("sources", []),
            }
        )

    tag_stats = [
        {"tag": t, "count": len(keys)}
        for t, keys in sorted(tag_index.items(), key=lambda x: -len(x[1]))
    ]
    cat_stats = [
        {"tag": c, "count": len(keys), "label_zh": CATEGORY_TAGS.get(c, c)}
        for c, keys in sorted(cat_index.items(), key=lambda x: -len(x[1]))
    ]

    return {
        "month": month,
        "days": day_summaries,
        "item_count": len(items),
        "items": items,
        "tag_index": dict(tag_index),
        "category_index": dict(cat_index),
        "tag_stats": tag_stats,
        "category_stats": cat_stats,
    }


def build_manifest(daily_files: dict[str, Path], months_data: dict[str, dict]) -> dict:
    days = []
    for date, path in sorted(daily_files.items(), reverse=True):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        stats = data.get("stats", {})
        days.append(
            {
                "date": date,
                "title_zh": f"AI 简报 {date}",
                "title_en": f"AI Daily {date}",
                "total": stats.get("total", len(data.get("items", []))),
                "sources": data.get("sources", []),
                "path": f"data/daily/{date}.json",
                "month": date[:7],
            }
        )

    months = []
    for month, md in sorted(months_data.items(), reverse=True):
        y, m = month.split("-")
        months.append(
            {
                "id": month,
                "year": y,
                "month": m,
                "label_zh": f"{y}年{int(m)}月",
                "label_en": f"{y} / {month_name_en(m)}",
                "day_count": len(md["days"]),
                "item_count": md["item_count"],
                "latest_date": md["days"][0]["date"] if md["days"] else "",
                "path": f"data/monthly/{month}.json",
            }
        )

    latest = days[0]["date"] if days else ""

    return {
        "site_name": "AI Daily",
        "blog_url": "../",
        "base_path": SITE_BASE_PATH,
        "latest_date": latest,
        "categories": [
            {"id": "cat:model", "zh": "新模型", "en": "Models", "emoji": "🧠"},
            {"id": "cat:tech", "zh": "新技术", "en": "Technology", "emoji": "⚙️"},
            {"id": "cat:app", "zh": "新应用", "en": "Applications", "emoji": "📱"},
            {"id": "cat:business", "zh": "新商业", "en": "Business", "emoji": "💼"},
            {"id": "cat:other", "zh": "其它", "en": "Other", "emoji": "📌"},
        ],
        "days": days,
        "months": months,
        "category_labels": CATEGORY_TAGS,
    }


def month_name_en(m: str) -> str:
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return names[int(m) - 1] if m.isdigit() else m


def sync_date(date_str: str) -> None:
    month = date_str[:7]
    src = SCRIPT_DIR / "Processed" / month / f"processed_{date_str}.json"
    if not src.exists():
        print(f"⚠️ 无 processed_{date_str}.json")
        return
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    with open(src, encoding="utf-8") as f:
        brief = json.load(f)

    items = [normalize_item(it, date_str) for it in brief.get("items", [])]
    brief["items"] = [{k: v for k, v in it.items() if k != "date"} for it in items]
    with open(DAILY_DIR / f"{date_str}.json", "w", encoding="utf-8") as f:
        json.dump(brief, f, ensure_ascii=False, indent=2)

    filter_src = SCRIPT_DIR / "Processed" / month / f"filter_{date_str}.json"
    if filter_src.exists():
        FILTER_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(filter_src, FILTER_DIR / f"{date_str}.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", nargs="*", default=[])
    args = parser.parse_args()

    SITE_DATA.mkdir(parents=True, exist_ok=True)
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    MONTHLY_DIR.mkdir(parents=True, exist_ok=True)

    if args.date:
        for d in parse_date_list(args.date):
            sync_date(d)

    for p in collect_all_processed():
        sync_date(p.stem.replace("processed_", ""))

    daily_files = {p.stem: p for p in DAILY_DIR.glob("*.json")}
    months = sorted({d[:7] for d in daily_files})
    months_data = {}
    for month in months:
        md = build_monthly(month, daily_files)
        months_data[month] = md
        with open(MONTHLY_DIR / f"{month}.json", "w", encoding="utf-8") as f:
            json.dump(md, f, ensure_ascii=False, indent=2)

    manifest = build_manifest(daily_files, months_data)
    with open(SITE_DATA / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"✅ manifest: {len(manifest['days'])} 天, {len(manifest['months'])} 月")


if __name__ == "__main__":
    main()

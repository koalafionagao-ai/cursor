#!/usr/bin/env python3
"""Agent2: 合并 Techmeme + TLDR，输出 prompt / mapping / blocks JSON。"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from common.dates import default_brief_date, parse_date_list  # noqa: E402
from common.pipeline_log import PipelineLogger  # noqa: E402
from common.schema import BlocksFile, RawBlock  # noqa: E402


def load_json(file_path):
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def get_news_count(data):
    if not data or "sections" not in data:
        return 0
    return sum(len(items) for items in data["sections"].values())


def write_merge_log(date_str, status):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday_str = weekdays[dt.weekday()]
    except ValueError:
        weekday_str = "未知"

    log_file = SCRIPT_DIR / "merge_status_log.txt"
    log_line = f"[Merge] 日期{date_str}，{weekday_str}，内容：{status}\n"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_line)
    print(f"  📝 [Merge] 日志已追加: {date_str} -> {status}")


def process_single_date(date_str):
    logger = PipelineLogger(date_str)
    with logger.step(
        "agent2",
        "Merge Techmeme and TLDR sources, dedupe, and write blocks/mapping/prompt",
        "merge_cleaner",
    ) as step:
        tm_path = SCRIPT_DIR / "Techmeme" / f"techmeme_{date_str}.json"
        tl_path = SCRIPT_DIR / "TLDR" / f"tldr_ai_{date_str}.json"

        tm_data = load_json(tm_path)
        tl_data = load_json(tl_path)

        tm_count = get_news_count(tm_data)
        tl_count = get_news_count(tl_data)
        step.set_metrics(techmeme_items=tm_count, tldr_items=tl_count)

        if tm_count == 0:
            print(f"  ⚠️ {date_str}：未检测到 Techmeme 数据")
        if tl_count == 0:
            print(f"  ⚠️ {date_str}：未检测到 TLDR 数据")

        if tm_count == 0 and tl_count == 0:
            print(f"🛑 {date_str}：所有源均无数据，中止清洗。")
            write_merge_log(date_str, "源数据全空，未生成合并任务")
            step.skip("Both Techmeme and TLDR sources empty; merge aborted")
            return

        print(f"✅ {date_str}：开始提取完整多层级结构数据...")

        url_mapping = {}
        clean_text_lines = []
        raw_blocks: list[RawBlock] = []

        if tm_count > 0:
            clean_text_lines.append("=== SOURCE: TECHMEME ===")
            tm_counter = 1
            for section_name, items in tm_data.get("sections", {}).items():
                if not items:
                    continue
                clean_text_lines.append(f"\n[CATEGORY: {section_name.upper()}]")
                for item in items:
                    item_id = f"TM-{tm_counter:02d}"
                    if item.get("url"):
                        url_mapping[item_id] = item["url"]
                    title = item.get("title", "")
                    excerpt = (item.get("excerpt") or "").strip()
                    raw_blocks.append(
                        RawBlock(
                            id=item_id,
                            source="techmeme",
                            title=title,
                            excerpt=excerpt,
                            url=item.get("url", ""),
                            section=section_name,
                        )
                    )
                    clean_text_lines.append(f"ID: {item_id}")
                    clean_text_lines.append(f"Title: {title}")
                    if excerpt:
                        clean_text_lines.append(f"Excerpt: {excerpt}")

                    if item.get("tweets"):
                        clean_text_lines.append("Tweets:")
                        for tw_idx, tw in enumerate(item["tweets"], 1):
                            tw_id = f"{item_id}-TW-{tw_idx:02d}"
                            if tw.get("url"):
                                url_mapping[tw_id] = tw["url"]
                            clean_text_lines.append(f"  - Author: {tw.get('author', '')}")
                            clean_text_lines.append(f"    Text: {tw.get('text', '')}")
                            if tw.get("url"):
                                clean_text_lines.append(f"    Link ID: {tw_id}")

                    if item.get("sub_items"):
                        clean_text_lines.append("Sub Items:")
                        for sub_idx, sub in enumerate(item["sub_items"], 1):
                            sub_id = f"{item_id}-SUB-{sub_idx:02d}"
                            if sub.get("url"):
                                url_mapping[sub_id] = sub["url"]
                            clean_text_lines.append(f"  - Title: {sub.get('title', '')}")
                            if sub.get("url"):
                                clean_text_lines.append(f"    Link ID: {sub_id}")

                    clean_text_lines.append("---")
                    tm_counter += 1

        if tl_count > 0:
            clean_text_lines.append("\n=== SOURCE: TLDR AI ===")
            tl_counter = 1
            for section_name, items in tl_data.get("sections", {}).items():
                if not items:
                    continue
                clean_text_lines.append(f"\n[CATEGORY: {section_name.upper()}]")
                for item in items:
                    item_id = f"TL-{tl_counter:02d}"
                    if item.get("url"):
                        url_mapping[item_id] = item["url"]
                    title = item.get("title", "")
                    excerpt = (item.get("excerpt") or "").strip()
                    raw_blocks.append(
                        RawBlock(
                            id=item_id,
                            source="tldr",
                            title=title,
                            excerpt=excerpt,
                            url=item.get("url", ""),
                            section=section_name,
                        )
                    )
                    clean_text_lines.append(f"ID: {item_id}")
                    clean_text_lines.append(f"Title: {title}")
                    if excerpt:
                        clean_text_lines.append(f"Excerpt: {excerpt}")
                    clean_text_lines.append("---")
                    tl_counter += 1

        month_folder = date_str[:7]
        output_dir = SCRIPT_DIR / "Processed" / month_folder
        output_dir.mkdir(parents=True, exist_ok=True)

        prompt_file = output_dir / f"prompt_{date_str}.txt"
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write("\n".join(clean_text_lines))

        mapping_file = output_dir / f"mapping_{date_str}.json"
        with open(mapping_file, "w", encoding="utf-8") as f:
            json.dump(url_mapping, f, ensure_ascii=False, indent=2)

        blocks_file = output_dir / f"blocks_{date_str}.json"
        with open(blocks_file, "w", encoding="utf-8") as f:
            json.dump(
                BlocksFile(date=date_str, items=raw_blocks).model_dump(),
                f,
                ensure_ascii=False,
                indent=2,
            )

        print(
            f"🎉 {date_str} 清洗完成。Techmeme({tm_count}) + TLDR({tl_count}) → blocks({len(raw_blocks)})"
        )
        write_merge_log(date_str, f"清洗成功 ({len(raw_blocks)} 条)")
        step.set_metrics(
            blocks_count=len(raw_blocks),
            mapping_links=len(url_mapping),
            prompt_lines=len(clean_text_lines),
        )
        if len(raw_blocks) == 0:
            step.warn("Merge completed but produced zero blocks")
        elif tm_count == 0 or tl_count == 0:
            step.warn(
                f"Merge produced {len(raw_blocks)} blocks with partial sources "
                f"(techmeme={tm_count}, tldr={tl_count})"
            )
        else:
            step.success(f"Wrote blocks_{date_str}.json with {len(raw_blocks)} items")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", nargs="*", default=[], help="目标日期 YYYY-MM-DD")
    args = parser.parse_args()
    target_dates = parse_date_list(args.date)

    for date_str in target_dates:
        print("-" * 50)
        print(f"⏳ 正在执行合并任务: {date_str}")
        process_single_date(date_str)


if __name__ == "__main__":
    main()

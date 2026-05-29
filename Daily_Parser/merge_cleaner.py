#!/usr/bin/env python3
import json
import argparse
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

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
    tm_path = SCRIPT_DIR / "Techmeme" / f"techmeme_{date_str}.json"
    tl_path = SCRIPT_DIR / "TLDR" / f"tldr_ai_{date_str}.json"
    
    tm_data = load_json(tm_path)
    tl_data = load_json(tl_path)

    tm_count = get_news_count(tm_data)
    tl_count = get_news_count(tl_data)

    if tm_count == 0:
        print(f"  ⚠️ {date_str}：未检测到 Techmeme 数据")
    if tl_count == 0:
        print(f"  ⚠️ {date_str}：未检测到 TLDR 数据")

    if tm_count == 0 and tl_count == 0:
        print(f"🛑 {date_str}：所有源均无数据，中止清洗。")
        write_merge_log(date_str, "源数据全空，未生成合并任务")
        return

    print(f"✅ {date_str}：开始提取完整多层级结构数据...")

    url_mapping = {}
    clean_text_lines = []
    
    # --- 处理 Techmeme ---
    if tm_count > 0:
        clean_text_lines.append("=== SOURCE: TECHMEME ===")
        tm_counter = 1
        for section_name, items in tm_data.get("sections", {}).items():
            if not items: continue
            clean_text_lines.append(f"\n[CATEGORY: {section_name.upper()}]")
            for item in items:
                item_id = f"TM-{tm_counter:02d}"
                if item.get("url"): 
                    url_mapping[item_id] = item["url"]
                
                clean_text_lines.append(f"ID: {item_id}")
                clean_text_lines.append(f"Title: {item.get('title', '')}")
                
                if item.get("excerpt") and item["excerpt"].strip():
                    clean_text_lines.append(f"Excerpt: {item['excerpt'].strip()}")
                
                # 恢复推文提取逻辑
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
                
                # 恢复子新闻提取逻辑
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

    # --- 处理 TLDR AI ---
    if tl_count > 0:
        clean_text_lines.append("\n=== SOURCE: TLDR AI ===")
        tl_counter = 1
        for section_name, items in tl_data.get("sections", {}).items():
            if not items: continue
            clean_text_lines.append(f"\n[CATEGORY: {section_name.upper()}]")
            for item in items:
                item_id = f"TL-{tl_counter:02d}"
                if item.get("url"): 
                    url_mapping[item_id] = item["url"]
                
                clean_text_lines.append(f"ID: {item_id}")
                clean_text_lines.append(f"Title: {item.get('title', '')}")
                
                if item.get("excerpt") and item["excerpt"].strip():
                    clean_text_lines.append(f"Excerpt: {item['excerpt'].strip()}")
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

    print(f"🎉 {date_str} 纯净结构化数据提取完成。包含 Techmeme({tm_count}) + TLDR({tl_count})")
    write_merge_log(date_str, f"清洗成功 ({tm_count + tl_count} 条)")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", nargs='*', default=[], help="目标日期")
    args = parser.parse_args()

    target_dates = []
    if args.date:
        for d in args.date:
            target_dates.extend(d.split())
    else:
        target_dates = [(datetime.now(timezone.utc)-timedelta(days=1)).strftime('%Y-%m-%d')]

    for date_str in target_dates:
        print("-" * 50)
        print(f"⏳ 正在执行合并任务: {date_str}")
        process_single_date(date_str)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
TLDR AI Newsletter RSS Fetcher (稳定版)
基于社区提供的 RSS 源，彻底解决网页反爬和结构突变问题。
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import feedparser
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                           "feedparser", "beautifulsoup4", "requests", "--break-system-packages", "-q"])
    import feedparser
    from bs4 import BeautifulSoup

# ─── 核心修改：动态获取脚本所在的绝对路径，彻底消灭套娃 ─────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(SCRIPT_DIR))
from common.dates import default_brief_date, parse_date_list
from common.pipeline_log import PipelineLogger

# ─── 配置 ───────────────────────────────────────────────────────────────
RSS_URL = "https://bullrich.dev/tldr-rss/ai.rss"

def write_status_log(date_str: str, status: str):
    """追加写入标准化状态日志"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    weekday_str = weekdays[dt.weekday()]
    
    # 日志强制写在脚本同级的 status_log.txt 中
    log_file = SCRIPT_DIR / "status_log.txt"
    log_line = f"[TLDR] 日期{date_str}，{weekday_str}，内容：{status}\n"
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_line)
    print(f"  📝 [TLDR] 日志已追加: {date_str} -> {status}")

def fetch_feed(url: str = RSS_URL) -> feedparser.FeedParserDict:
    feed = feedparser.parse(url)
    if feed.bozo and not feed.entries:
        raise RuntimeError(f"RSS 解析失败: {feed.bozo_exception}")
    return feed

def filter_entries_by_date(feed, target_date: datetime) -> list:
    """根据目标日期筛选 RSS 条目"""
    target_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    target_end = target_start + timedelta(days=1)
    matched = []
    
    for entry in feed.entries:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            # 解析 RSS 里的时间
            pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            if target_start <= pub_dt < target_end:
                matched.append((pub_dt, entry))
                
    matched.sort(key=lambda x: x[0])
    return [entry for _, entry in matched]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", nargs='*', default=[], help="目标日期，支持输入多个")
    args = parser.parse_args()
    
    # 强制输出目录为脚本所在位置下的 TLDR 文件夹
    output_dir = SCRIPT_DIR / "TLDR"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 处理日期参数
    target_dates_str = []
    if args.date:
        target_dates_str = parse_date_list(args.date)
    else:
        target_dates_str = [default_brief_date()]
        
    print(f"📥 准备拉取 TLDR RSS 数据流...")
    try:
        feed = fetch_feed()
        print(f"✅ RSS 数据流拉取成功，即将处理 {len(target_dates_str)} 个日期。\n")
    except Exception as e:
        print(f"⚠️ 获取 RSS 失败: {e}")
        for d in target_dates_str:
            write_status_log(d, "获取源失败")
        sys.exit(1)
        
    # 探针逻辑：打印出 RSS 源里真实存在的所有日期
    available_dates = []
    for entry in feed.entries:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            available_dates.append(pub_dt.strftime('%Y-%m-%d'))
    unique_dates = sorted(list(set(available_dates)))
    print(f"📡 当前 TLDR RSS 源中包含的日期为: {unique_dates}\n")

    for date_str in target_dates_str:
        logger = PipelineLogger(date_str)
        with logger.step(
            "agent1",
            "Fetch TLDR AI RSS feed and extract news items",
            "tldr_fetcher",
        ) as step:
            print("-" * 50)
            print(f"⏳ 正在处理 TLDR 目标日期: {date_str}")

            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                print(f"  ⚠️ 日期格式错误，跳过: {date_str}")
                step.skip(f"Invalid date format: {date_str}")
                continue

            entries = filter_entries_by_date(feed, target_date)

            if not entries:
                print(f"  ⚠️ 当天 TLDR 未更新，或该日期的数据已被挤出 RSS 队列。")
                write_status_log(date_str, "空/无匹配数据")
                step.warn("No TLDR RSS entries matched for target date")
                continue

            news_items = []
            for entry in entries:
                title = entry.title if hasattr(entry, "title") else "No Title"
                url = entry.link if hasattr(entry, "link") else (entry.guid if hasattr(entry, "guid") else "")

                desc_html = entry.description if hasattr(entry, "description") else ""
                soup = BeautifulSoup(desc_html, "html.parser")
                excerpt = soup.get_text(separator=" ", strip=True)

                if "(Sponsor)" in title:
                    continue

                news_items.append({
                    "title": title,
                    "url": url,
                    "excerpt": excerpt
                })

            sections = {"TLDR News": news_items}

            if not news_items:
                print(f"  ⚠️ 找到了数据，但全都是广告被过滤掉了。")
                write_status_log(date_str, "解析到空数据")
                step.warn("TLDR entries found but all items filtered out (e.g. sponsors)")
                continue

            out_path = output_dir / f"tldr_ai_{date_str}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"date": date_str, "sections": sections}, f, ensure_ascii=False, indent=2)
            step.set_metrics(news_count=len(news_items), output_file=out_path.name)
            step.success(f"Saved {out_path.name} with {len(news_items)} news items")
            print(f"  ✅ 成功提取 {len(news_items)} 条新闻，已保存至: {out_path.name}")
            write_status_log(date_str, "已获取")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Techmeme Daily Newsletter RSS Fetcher (北京时间早8点精准对齐版)
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

SCRIPT_DIR = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(SCRIPT_DIR))
from common.dates import default_brief_date, parse_date_list
RSS_URL = "https://us14.campaign-archive.com/feed?u=94ccd3ae223561415b05892ab&id=976a1cbc1f"
SKIP_SECTIONS = {"sponsor"}

def write_status_log(date_str: str, status: str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    weekday_str = weekdays[dt.weekday()]
    
    log_file = SCRIPT_DIR / "status_log.txt"
    log_line = f"[Techmeme] 日期{date_str}，{weekday_str}，内容：{status}\n"
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_line)
    print(f"  📝 [Techmeme] 日志已追加: {date_str} -> {status}")

def fetch_feed(url: str = RSS_URL) -> feedparser.FeedParserDict:
    feed = feedparser.parse(url)
    if feed.bozo and not feed.entries:
        raise RuntimeError(f"RSS 解析失败: {feed.bozo_exception}")
    return feed

def filter_entries_by_date(feed, target_date: datetime) -> list:
    """
    核心逻辑：北京时间早 8:00 (UTC 0:00) 左右发布前一天的邮件
    """
    # 1. 优先使用标题硬匹配 (例如抓 5月24日，邮件标题必定含有 "May 24")
    month_name = target_date.strftime('%B')
    day_num = str(target_date.day)
    date_str_en = f"{month_name} {day_num}" # 格式如 "May 24"
    
    matched = []
    for entry in feed.entries:
        title = getattr(entry, 'title', '')
        if date_str_en.lower() in title.lower():
            matched.append(entry)
            
    if matched:
        print(f"  🔍 标题匹配成功: 找到了包含 '{date_str_en}' 的邮件")
        return matched
        
    # 2. 如果标题匹配失败，使用北京时间早 8 点的物理时间窗作为备用
    # 目标日期 (如 5月24日) 的下一天 (5月25日)
    next_day = target_date + timedelta(days=1)
    
    # 构建时间窗：UTC 5月24日 22:00 到 UTC 5月25日 06:00
    # 这等同于：北京时间 5月25日 06:00 到 14:00 (完美覆盖早8点左右的发布时间)
    window_start = datetime(target_date.year, target_date.month, target_date.day, 22, 0, tzinfo=timezone.utc)
    window_end = datetime(next_day.year, next_day.month, next_day.day, 6, 0, tzinfo=timezone.utc)
    
    for entry in feed.entries:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            if window_start <= pub_dt < window_end:
                matched.append(entry)
                
    if matched:
        print(f"  🕒 时间窗匹配成功: 捕获了北京时间早8点发布的邮件")
                
    return matched

def extract_news_from_html(html_content: str) -> dict:
    soup = BeautifulSoup(html_content, "html.parser")
    sections = {}
    section_containers = soup.find_all("div", class_=["first_section", "section"])
    
    for container in section_containers:
        header = container.find("div", class_="section_header")
        if not header:
            continue
            
        section_name = header.get_text(strip=True).lower()
        if section_name in SKIP_SECTIONS:
            continue

        story_divs = container.find_all("div", class_=["story", "big_story"])
        items = []
        
        for story_div in story_divs:
            classes = story_div.get("class", [])
            if isinstance(classes, str):
                classes = classes.split()
            if "sponsor" in classes:
                continue
                
            news_item = parse_story_block(story_div)
            if news_item:
                items.append(news_item)
                
        if items:
            sections[section_name] = items
            
    return sections

def parse_story_block(story_div) -> dict | None:
    leading_table = story_div.find("table", class_="leading_item")
    if not leading_table:
        return None
        
    title_span = leading_table.find("span", class_="title")
    if not title_span or not title_span.find("a"):
        return None
        
    link = title_span.find("a")
    full_text = link.get_text(strip=True) 
    url = link.get("href", "")

    tweets = []
    tweet_divs = story_div.find_all("div", class_="tweet")
    for td in tweet_divs:
        t_cite = td.find("a", class_="tweet_cite")
        t_body = td.find("a", class_="tweet_body")
        if t_cite and t_body:
            tweets.append({
                "author": t_cite.get_text(strip=True).replace(":", ""),
                "text": t_body.get_text(strip=True),
                "url": t_body.get("href", "")
            })

    sub_items = []
    sub_lis = story_div.find_all("li", class_="sub_item")
    for sub in sub_lis:
        s_title_span = sub.find("span", class_="title")
        if s_title_span and s_title_span.find("a"):
            s_link = s_title_span.find("a")
            sub_items.append({
                "title": s_link.get_text(strip=True),
                "url": s_link.get("href", "")
            })

    return {
        "title": full_text,
        "excerpt": "",
        "url": url,
        "tweets": tweets,
        "sub_items": sub_items
    }

def main():
    parser = argparse.ArgumentParser(description="Techmeme Full Data Fetcher")
    parser.add_argument("--date", type=str, nargs='*', default=[], help="目标日期 YYYY-MM-DD，支持多个")
    args = parser.parse_args()

    output_dir = SCRIPT_DIR / "Techmeme"
    output_dir.mkdir(parents=True, exist_ok=True)

    target_dates_str = []
    if args.date:
        target_dates_str = parse_date_list(args.date)
    else:
        # 如果没有指定日期，默认抓取昨天的数据
        yesterday_str = default_brief_date()
        target_dates_str = [yesterday_str]

    print(f"📥 准备拉取 Mailchimp 邮件汇总 RSS 数据流...")
    feed = fetch_feed() 
    print(f"✅ RSS 拉取成功，即将处理 {len(target_dates_str)} 个日期。\n")

    for date_str in target_dates_str:
        print("-" * 50)
        print(f"⏳ 正在处理目标日期: {date_str} (预期寻找北京时间次日早8点的邮件)")
        
        target_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        entries = filter_entries_by_date(feed, target_date)

        if not entries:
            print(f"  ⚠️ 未能匹配到该日期的邮件，请检查 RSS 源是否已更新。")
            write_status_log(date_str, "空")
            continue

        all_sections = {}
        for entry in entries:
            html_content = entry.content[0].value if hasattr(entry, 'content') else entry.summary
            sections = extract_news_from_html(html_content)
            for name, items in sections.items():
                if name not in all_sections:
                    all_sections[name] = []
                all_sections[name].extend(items)

        total_news = sum(len(items) for items in all_sections.values())
        
        output = {
            "date": date_str,
            "sections": all_sections,
            "stats": {
                "section_count": len(all_sections),
                "news_count": total_news,
            }
        }

        output_file = output_dir / f"techmeme_{date_str}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"  ✅ 成功提取 {total_news} 条新闻，已保存至: {output_file.name}")
        write_status_log(date_str, "已获取")

if __name__ == "__main__":
    main()

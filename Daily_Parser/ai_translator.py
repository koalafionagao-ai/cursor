#!/usr/bin/env python3
import json
import argparse
import sys
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 自动检查并安装 requests 库
try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

SCRIPT_DIR = Path(__file__).resolve().parent

def load_file(file_path, is_json=False):
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f) if is_json else f.read()
    return None

def write_merge_log(date_str, status):
    log_file = SCRIPT_DIR / "merge_status_log.txt"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[Merge] 日期{date_str}，内容：{status}\n")

def parse_source_to_blocks(source_text):
    raw_blocks = source_text.split("---")
    blocks = []
    for b in raw_blocks:
        b = b.strip()
        if b and "ID:" in b:
            blocks.append(b)
    return blocks

def clean_json_response(text):
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

def process_translation(target_date, source_data, url_mapping, token):
    blocks = parse_source_to_blocks(source_data)
    total_items = len(blocks)
    if total_items == 0:
        print(f"🛑 {target_date} 数据为空，跳过翻译。", flush=True)
        return False
        
    print(f"🚀 {target_date} 共有 {total_items} 条新闻，准备串行执行 JSON 结构化翻译...", flush=True)

    system_prompt = """
你是资深的 AI 产品经理。请将用户提供的英文新闻翻译为中文，并进行分类。
你必须严格输出合法的 JSON 格式。

【分类标准】
1 新模型：模型发布、升级、能力突破
2 新技术：基础设施、开发工具、算法、安全技术
3 新应用：产品发布、功能更新、场景拓展
4 新商业：融资、并购、上市、合作、政策、市场分析、人事
5 其它：不属于以上分类

【JSON 输出格式范例】
{
  "results": [
    {
      "id": "输入数据中的 ID (如 TM-01)",
      "category_id": "填入数字 1 到 5",
      "en_title": "直接复制输入数据中的原英文标题，不可省略",
      "zh_title": "中文翻译标题",
      "zh_summary": "请综合提炼出一段精简流畅的中文摘要，不要啰嗦",
      "tweets": [
        {"author": "推文作者", "text": "推文中文翻译"}
      ],
      "source": "如果 ID 以 TM 开头填 Techmeme，TL 开头填 TLDR"
    }
  ]
}
注意：如果原文包含 Tweets 或 Sub Items 请一并翻译。不要输出任何 Markdown，只返回纯 JSON 对象。必须处理所有条目，绝不遗漏！
"""

    headers = {
        "Authorization": f"Bearer {token}", 
        "Content-Type": "application/json"
    }
    
    batch_size = 10 
    all_translated_items = []
    
    # 退回稳妥的串行模式，绝不触发 429 报错
    for i in range(0, total_items, batch_size):
        batch_blocks = blocks[i:i + batch_size]
        batch_text = "\n\n---\n\n".join(batch_blocks)
        current_batch = (i // batch_size) + 1
        total_batches = (total_items + batch_size - 1) // batch_size
        
        print(f"🔄 正在请求第 {current_batch}/{total_batches} 批次...", flush=True)
        
        payload = {
            "model": "gpt-4o", 
            "temperature": 0.1,
            "max_tokens": 4096,
            "response_format": { "type": "json_object" }, 
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请翻译以下条目并返回指定的 JSON 格式：\n\n{batch_text}"}
            ]
        }
        
        retries = 3
        while retries > 0:
            try:
                response = requests.post(
                    "https://models.inference.ai.azure.com/chat/completions", 
                    headers=headers, 
                    json=payload, 
                    timeout=90
                )
                response.raise_for_status()
                
                response_text = response.json()["choices"][0]["message"]["content"]
                clean_json_str = clean_json_response(response_text)
                batch_result = json.loads(clean_json_str)
                
                parsed_count = len(batch_result.get('results', []))
                all_translated_items.extend(batch_result.get("results", []))
                print(f"✅ 第 {current_batch}/{total_batches} 批次成功解析 {parsed_count} 条！", flush=True)
                break 
                
            except Exception as e:
                print(f"⚠️ 第 {current_batch}/{total_batches} 批次请求失败 ({e})。剩余重试次数: {retries-1}", flush=True)
                retries -= 1
                time.sleep(3)
                
        # 串行批次间严格休眠 4 秒，确保重置 API 窗口，避免 429
        time.sleep(4)

    if not all_translated_items:
        print("🛑 所有批次翻译均失败，无法生成简报。", flush=True)
        return False

    print(f"📊 翻译全部结束！共回收 {len(all_translated_items)} 条。正在聚合分类并生成排版...", flush=True)
    
    categories_map = {
        1: ("1 新模型", "新发布的AI模型、模型升级、模型能力突破"),
        2: ("2 新技术", "基础设施、开发工具、算法、安全技术"),
        3: ("3 新应用", "产品发布、功能更新、场景拓展"),
        4: ("4 新商业", "融资、并购、上市、合作、政策、市场分析、人才"),
        5: ("5 其它", "其它AI相关资讯")
    }
    
    grouped_data = {1: [], 2: [], 3: [], 4: [], 5: []}
    for item in all_translated_items:
        try:
            cat_id = int(item.get("category_id", 5))
            if cat_id not in grouped_data: cat_id = 5
        except:
            cat_id = 5
        grouped_data[cat_id].append(item)

    actual_sources = []
    if any(item.get("source", "") == "TLDR" for item in all_translated_items): actual_sources.append("TLDR AI")
    if any(item.get("source", "") == "Techmeme" for item in all_translated_items): actual_sources.append("Techmeme")
    source_str = " + ".join(actual_sources) if actual_sources else "综合资讯"
    
    total_valid_items = len(all_translated_items)

    # 渲染带有百分比的统计表格
    final_md = f"# AI 简报 | {target_date}\n\n> **数据源**: {source_str}\n\n---\n\n## 📊 统计\n\n| 维度 | 数量 | 占比 |\n|---|---|---|\n"
    for cat_id in range(1, 6):
        cat_count = len(grouped_data[cat_id])
        pct = (cat_count / total_valid_items * 100) if total_valid_items > 0 else 0
        final_md += f"| {categories_map[cat_id][0]} | {cat_count} | {pct:.1f}% |\n"
    final_md += f"| **总计** | **{total_valid_items}** | **100%** |\n\n---\n\n"

    # 全局序号计数器 (解决序号没有全文连续的问题)
    global_idx = 1

    for cat_id in range(1, 6):
        items = grouped_data[cat_id]
        if not items: continue
        
        cat_name, cat_desc = categories_map[cat_id]
        final_md += f"# {cat_name}\n> {cat_desc}\n---\n"
        
        for item in items:
            item_id = item.get("id", "")
            en_title = item.get("en_title", item_id)
            zh_title = item.get("zh_title", "")
            summary = item.get("zh_summary", "")
            source = item.get("source", "Web")
            
            # 使用 URL 映射
            original_url = url_mapping.get(item_id, item_id)
            
            # 排版精简：去掉多余的“中文标题”、“中文摘要”等冗余标签
            final_md += f"### ({global_idx}) {zh_title}\n\n"
            final_md += f"**原文链接**: [{en_title}]({original_url})\n\n"
            
            if summary:
                final_md += f"**摘要**: {summary}\n\n"
            
            tweets = item.get("tweets", [])
            if tweets:
                final_md += "**推文**:\n"
                for tw in tweets:
                    author = tw.get("author", "")
                    text = tw.get("text", "")
                    final_md += f"- {author}: {text}\n"
                final_md += "\n"
                
            final_md += f"**来源**: {source} | **日期**: {target_date}\n\n---\n"
            
            global_idx += 1 # 序号递增

    month_folder = target_date[:7]
    processed_dir = SCRIPT_DIR / "Processed" / month_folder
    final_file = processed_dir / f"AI_Brief_{target_date}.md"
    
    with open(final_file, "w", encoding="utf-8") as f:
        f.write(final_md)
    
    print(f"🎉 完美组装完成，生成的简报已保存至: {final_file}", flush=True)
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", nargs='*', default=[(datetime.now(timezone.utc)-timedelta(days=1)).strftime('%Y-%m-%d')])
    args = parser.parse_args()
    
    github_token = os.environ.get("GH_MODELS_TOKEN")
    if not github_token:
        print("🛑 缺少 GH_MODELS_TOKEN 环境变量，请检查 YML 配置。", flush=True)
        sys.exit(1)
        
    for d in args.date:
        prompt_file = SCRIPT_DIR / "Processed" / d[:7] / f"prompt_{d}.txt"
        mapping_file = SCRIPT_DIR / "Processed" / d[:7] / f"mapping_{d}.json"
        
        data = load_file(prompt_file)
        mapping = load_file(mapping_file, is_json=True)
        
        if not data or not mapping:
            print(f"⚠️ 找不到 {d} 的清洗数据，已跳过。", flush=True)
            continue
            
        if process_translation(d, data, mapping, github_token):
            write_merge_log(d, "结构化串行翻译与简报生成成功")
        else:
            write_merge_log(d, "翻译失败")

if __name__ == "__main__":
    main()

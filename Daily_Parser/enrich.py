#!/usr/bin/env python3
"""
Agent4: 中文翻译 + 分类 + 标签；英文保留原文。
输出 processed_YYYY-MM-DD.json（不再生成 MD）。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from common.dates import parse_date_list  # noqa: E402
from common.llm import DEFAULT_MODEL, run_batches  # noqa: E402
from common.pipeline_log import EXPECTED_MIN_PUBLISHED_ITEMS, PipelineLogger  # noqa: E402
from common.schema import BlocksFile, ProcessedBrief, ProcessedItem, TweetItem  # noqa: E402
from common.taxonomy import CATEGORY_ID_TO_TAG, infer_entity_tags_from_text, normalize_tags, tags_for_prompt  # noqa: E402
from common.text_utils import is_duplicate, pick_summary  # noqa: E402

BATCH_SIZE = 10


def load_filter_keep_ids(month: str, date_str: str) -> set[str] | None:
    path = SCRIPT_DIR / "Processed" / month / f"filter_{date_str}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {x["id"] for x in data.get("items", []) if x.get("keep")}


def block_to_prompt_text(item) -> str:
    lines = [f"ID: {item.id}", f"Title: {item.title}"]
    if item.excerpt:
        lines.append(f"Excerpt: {item.excerpt}")
    return "\n".join(lines)


def build_system_prompt() -> str:
    return f"""你是资深 AI 产品经理。仅需输出中文标题/摘要与标签；英文原文由系统保留，不要翻译英文。

{tags_for_prompt()}

【分类 category_id】1=新模型 2=新技术 3=新应用 4=新商业 5=其它（须与 cat:* 一致）

【摘要规则】若中文摘要与中文标题信息重复，zh_summary 必须留空字符串 ""，以节省篇幅。

严格输出 JSON：
{{
  "results": [
    {{
      "id": "TM-01",
      "category_id": 1,
      "tags": ["cat:model", "anthropic", "claude"],
      "zh_title": "中文标题",
      "zh_summary": "仅在与标题不重复时填写，否则 \"\"",
      "source": "Techmeme 或 TLDR",
      "tweets": [{{"author":"@x","text_zh":"推文中文"}}]
    }}
  ]
}}
tags 必须从允许列表选择。不要 Markdown，只返回 JSON。"""


def write_log(date_str: str, status: str) -> None:
    log_file = SCRIPT_DIR / "merge_status_log.txt"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[Enrich] 日期{date_str}，内容：{status}\n")


def process_date(date_str: str) -> bool:
    logger = PipelineLogger(date_str)
    with logger.step(
        "agent4",
        "Translate, categorize, and tag filtered items via LLM",
        "enrich",
    ) as step:
        month = date_str[:7]
        blocks_path = SCRIPT_DIR / "Processed" / month / f"blocks_{date_str}.json"
        mapping_path = SCRIPT_DIR / "Processed" / month / f"mapping_{date_str}.json"

        if not blocks_path.exists():
            print(f"⚠️ 缺少 blocks，跳过 {date_str}")
            step.skip(f"Missing blocks file for {date_str}")
            return False

        with open(blocks_path, encoding="utf-8") as f:
            blocks = BlocksFile.model_validate(json.load(f))
        url_mapping = {}
        if mapping_path.exists():
            with open(mapping_path, encoding="utf-8") as f:
                url_mapping = json.load(f)

        keep_ids = load_filter_keep_ids(month, date_str)
        items = blocks.items
        if keep_ids is not None:
            items = [it for it in items if it.id in keep_ids]
            print(f"🔎 筛选后 {len(items)}/{len(blocks.items)} 条进入翻译")

        step.set_metrics(blocks_total=len(blocks.items), items_to_enrich=len(items))

        if not items:
            print(f"🛑 {date_str} 无待翻译条目")
            write_log(date_str, "无条目")
            step.skip("No items passed filter for enrichment")
            return False

        text_blocks = [block_to_prompt_text(it) for it in items]
        id_to_block = {it.id: it for it in items}

        rows = run_batches(
            text_blocks,
            batch_size=BATCH_SIZE,
            build_user=lambda batch: "请处理以下条目：\n\n---\n\n".join(batch),
            system=build_system_prompt(),
            model=DEFAULT_MODEL,
            sleep_between_batches=4.0,
        )

        processed: list[ProcessedItem] = []
        for row in rows:
            item_id = row.get("id")
            if not item_id or item_id not in id_to_block:
                continue
            block = id_to_block[item_id]
            try:
                cat_id = int(row.get("category_id", 5))
            except (TypeError, ValueError):
                cat_id = 5
            raw_tags = row.get("tags") or []
            if isinstance(raw_tags, str):
                raw_tags = [raw_tags]
            tags = normalize_tags(list(raw_tags), category_id=cat_id)
            if not any(not t.startswith("cat:") for t in tags):
                hint = f"{block.title} {(row.get('zh_title') or '')} {block.excerpt or ''}"
                for t in infer_entity_tags_from_text(hint):
                    if t not in tags:
                        tags.append(t)

            src = row.get("source") or ("Techmeme" if item_id.startswith("TM") else "TLDR")
            url = url_mapping.get(item_id, block.url or "")

            en_title = block.title
            zh_title = (row.get("zh_title") or "").strip()
            zh_summary = (row.get("zh_summary") or "").strip()
            if is_duplicate(zh_title, zh_summary):
                zh_summary = ""

            en_summary = pick_summary(en_title, "", block.excerpt or "")

            tweets = []
            for tw in row.get("tweets") or []:
                tweets.append(
                    TweetItem(
                        author=tw.get("author", ""),
                        text=(tw.get("text_zh") or tw.get("text", "")).strip(),
                        text_en=tw.get("text_en", "").strip(),
                    )
                )

            processed.append(
                ProcessedItem(
                    id=item_id,
                    category_id=cat_id,
                    source=src,
                    url=str(url),
                    title={"zh": zh_title, "en": en_title},
                    summary={"zh": zh_summary, "en": en_summary},
                    tags=tags,
                    tweets=tweets,
                )
            )

        if not processed:
            write_log(date_str, "翻译失败")
            step.warn("LLM enrichment returned zero processed items")
            return False

        cat_counts = Counter(CATEGORY_ID_TO_TAG.get(it.category_id, "cat:other") for it in processed)
        sources = sorted({it.source for it in processed})

        brief = ProcessedBrief(
            date=date_str,
            sources=sources,
            stats={"total": len(processed), "by_category": dict(cat_counts)},
            items=processed,
        )

        out_path = SCRIPT_DIR / "Processed" / month / f"processed_{date_str}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(brief.model_dump(), f, ensure_ascii=False, indent=2)

        step.set_metrics(published_items=len(processed), llm_rows=len(rows))
        print(f"🎉 processed → {out_path}")
        write_log(date_str, f"成功 {len(processed)} 条")
        if len(processed) < EXPECTED_MIN_PUBLISHED_ITEMS:
            step.warn(
                f"Published {len(processed)} items (expected >= {EXPECTED_MIN_PUBLISHED_ITEMS})"
            )
        else:
            step.success(f"Wrote processed_{date_str}.json with {len(processed)} items")
        return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", nargs="*", default=[])
    args = parser.parse_args()
    for d in parse_date_list(args.date):
        print("-" * 50)
        process_date(d)


if __name__ == "__main__":
    main()

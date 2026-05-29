#!/usr/bin/env python3
"""
Agent3: 对条目打分筛选。score 0–10，默认 keep 当 score >= threshold。
输出 filter_YYYY-MM-DD.json 供人工调参；仅 keep=true 的 ID 进入翻译。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from common.dates import parse_date_list  # noqa: E402
from common.llm import MINI_MODEL, run_batches  # noqa: E402
from common.schema import BlocksFile, FilterEntry, FilterReport  # noqa: E402

DEFAULT_THRESHOLD = 7.0
BATCH_SIZE = 25

FILTER_SYSTEM = """你是资深 AI 产品经理，负责从大量英文 AI 资讯中筛选「对从业者有价值」的条目。

评分标准（0–10）：
- 9–10：重磅模型发布、行业格局变化、重要政策、头部公司战略级动作
- 7–8：有产品洞察的技术/应用更新、值得关注的融资或合作
- 5–6：有一定信息量但偏常规、或重复性报道
- 0–4：赞助、招聘、纯股价波动、与 AI 弱相关、信息过少

只根据标题和摘要判断。严格输出 JSON：
{"results":[{"id":"TM-01","score":7.5,"reason":"一句话中文理由"}]}
"""


def block_to_text(item) -> str:
    lines = [f"ID: {item.id}", f"Title: {item.title}"]
    if item.excerpt:
        lines.append(f"Excerpt: {item.excerpt}")
    return "\n".join(lines)


def rule_prefilter(items: list) -> dict[str, float]:
    penalties: dict[str, float] = {}
    for it in items:
        t = (it.title or "").strip()
        if not t or len(t) < 12:
            penalties[it.id] = -3.0
        elif "(Sponsor)" in t or "sponsor" in t.lower():
            penalties[it.id] = -5.0
    return penalties


def process_date(date_str: str, threshold: float, dry_run: bool) -> None:
    month = date_str[:7]
    blocks_path = SCRIPT_DIR / "Processed" / month / f"blocks_{date_str}.json"
    if not blocks_path.exists():
        print(f"⚠️ 缺少 {blocks_path.name}，跳过")
        return

    with open(blocks_path, encoding="utf-8") as f:
        blocks = BlocksFile.model_validate(json.load(f))

    if not blocks.items:
        print(f"🛑 {date_str} 无条目")
        return

    penalties = rule_prefilter(blocks.items)
    text_blocks = [block_to_text(it) for it in blocks.items]
    entries: list[FilterEntry] = []

    if dry_run:
        for it in blocks.items:
            base = 5.0 + penalties.get(it.id, 0)
            entries.append(
                FilterEntry(
                    id=it.id,
                    score=max(0, min(10, base)),
                    keep=max(0, min(10, base)) >= threshold,
                    reason="dry-run（未调用 LLM）",
                )
            )
    else:

        def build_user(batch: list[str]) -> str:
            return "请为以下每条新闻打分：\n\n---\n\n".join(batch)

        rows = run_batches(
            text_blocks,
            batch_size=BATCH_SIZE,
            build_user=build_user,
            system=FILTER_SYSTEM,
            model=MINI_MODEL,
            sleep_between_batches=2.0,
        )
        by_id = {r.get("id"): r for r in rows if r.get("id")}
        for it in blocks.items:
            row = by_id.get(it.id, {})
            try:
                score = float(row.get("score", 5))
            except (TypeError, ValueError):
                score = 5.0
            score += penalties.get(it.id, 0)
            score = max(0.0, min(10.0, score))
            entries.append(
                FilterEntry(
                    id=it.id,
                    score=round(score, 1),
                    keep=score >= threshold,
                    reason=str(row.get("reason", ""))[:200],
                )
            )

    kept = sum(1 for e in entries if e.keep)
    report = FilterReport(
        date=date_str,
        threshold=threshold,
        total=len(entries),
        kept=kept,
        items=entries,
    )

    out_path = SCRIPT_DIR / "Processed" / month / f"filter_{date_str}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, ensure_ascii=False, indent=2)

    print(
        f"📊 {date_str} 筛选完成: {kept}/{len(entries)} 条保留 (threshold={threshold}) → {out_path.name}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", nargs="*", default=[])
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for d in parse_date_list(args.date):
        print("-" * 50)
        process_date(d, args.threshold, args.dry_run)


if __name__ == "__main__":
    main()

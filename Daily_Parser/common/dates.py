"""Beijing-time helpers aligned with fetcher semantics."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

BEIJING = timezone(timedelta(hours=8))


def now_beijing() -> datetime:
    return datetime.now(BEIJING)


def default_brief_date() -> str:
    """
    Default 简报日期：北京时间当日早上跑流水线时，整合的是「前一日」简报。

    - Techmeme：D+1 日早上发布，内容为 D 日
    - TLDR：D 日深夜发布，内容为 D 日
    """
    return (now_beijing().date() - timedelta(days=1)).isoformat()


def parse_date_list(argv: list[str] | None) -> list[str]:
    if not argv:
        return [default_brief_date()]
    out: list[str] = []
    for chunk in argv:
        out.extend(chunk.split())
    return out

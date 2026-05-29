"""文本去重与摘要裁剪。"""

from __future__ import annotations

import re
from difflib import SequenceMatcher


def _norm(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip().lower())
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", s)


def is_duplicate(a: str, b: str, *, ratio: float = 0.82) -> bool:
    """标题与摘要高度重复则视为无需展示摘要。"""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= ratio


def pick_summary(title: str, summary: str, excerpt: str = "") -> str:
    """英文用原文；若摘要与标题重复则返回空。"""
    candidate = (summary or excerpt or "").strip()
    if not candidate or is_duplicate(title, candidate):
        return ""
    return candidate

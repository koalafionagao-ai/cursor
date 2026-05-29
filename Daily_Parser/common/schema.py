"""Pydantic models for pipeline JSON artifacts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class RawBlock(BaseModel):
    id: str
    source: Literal["techmeme", "tldr"]
    title: str
    excerpt: str = ""
    url: str = ""
    section: str = ""


class BlocksFile(BaseModel):
    date: str
    items: list[RawBlock]


class FilterEntry(BaseModel):
    id: str
    score: float = Field(ge=0, le=10)
    keep: bool
    reason: str = ""


class FilterReport(BaseModel):
    date: str
    threshold: float
    total: int
    kept: int
    items: list[FilterEntry]


class TweetItem(BaseModel):
    author: str = ""
    text: str = ""
    text_en: str = ""


class ProcessedItem(BaseModel):
    id: str
    category_id: int = 5
    source: str
    url: str
    title: dict[str, str]
    summary: dict[str, str]
    tags: list[str] = Field(default_factory=list)
    tweets: list[TweetItem] = Field(default_factory=list)
    score: float | None = None


class ProcessedBrief(BaseModel):
    date: str
    sources: list[str] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)
    items: list[ProcessedItem]

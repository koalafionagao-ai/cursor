"""GitHub Models API client with batching and retries."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable

import requests

API_URL = "https://models.inference.ai.azure.com/chat/completions"
DEFAULT_MODEL = "gpt-4o"
MINI_MODEL = "gpt-4o-mini"


def get_token() -> str:
    token = os.environ.get("GH_MODELS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("缺少 GH_MODELS_TOKEN 或 GITHUB_TOKEN")
    return token


def clean_json_response(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def chat_json(
    *,
    system: str,
    user: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    retries: int = 3,
    sleep_between: float = 4.0,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.post(API_URL, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            return json.loads(clean_json_response(raw))
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(3)
    raise RuntimeError(f"LLM 请求失败: {last_err}") from last_err


def run_batches(
    blocks: list[str],
    *,
    batch_size: int,
    build_user: Callable[[list[str]], str],
    system: str,
    model: str = DEFAULT_MODEL,
    sleep_between_batches: float = 4.0,
    results_key: str = "results",
) -> list[dict[str, Any]]:
    all_rows: list[dict[str, Any]] = []
    total = len(blocks)
    for i in range(0, total, batch_size):
        batch = blocks[i : i + batch_size]
        batch_no = (i // batch_size) + 1
        total_batches = (total + batch_size - 1) // batch_size
        print(f"🔄 LLM 批次 {batch_no}/{total_batches} ({model})...", flush=True)
        data = chat_json(
            system=system,
            user=build_user(batch),
            model=model,
            sleep_between=0,
        )
        rows = data.get(results_key, data if isinstance(data, list) else [])
        if isinstance(rows, list):
            all_rows.extend(rows)
        if sleep_between_batches and i + batch_size < total:
            time.sleep(sleep_between_batches)
    return all_rows

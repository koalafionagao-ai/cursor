#!/usr/bin/env python3
"""Regenerate Markdown pipeline logs from legacy JSON or in-run state files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from common.dates import parse_date_list  # noqa: E402
from common.pipeline_log import LOG_ROOT, load_log_data, write_log_from_data  # noqa: E402


def regenerate(brief_date: str) -> bool:
    month = brief_date[:7]
    legacy = LOG_ROOT / month / f"{brief_date}.json"
    state = LOG_ROOT / month / f"{brief_date}.pipeline.json"
    data = None
    if legacy.exists():
        data = json.loads(legacy.read_text(encoding="utf-8"))
    else:
        data = load_log_data(brief_date)
    if not data:
        print(f"No log data found for {brief_date}", file=sys.stderr)
        return False
    if state.exists() and legacy.exists():
        state.unlink()
    path = write_log_from_data(data)
    if legacy.exists():
        legacy.unlink()
        print(f"Removed legacy JSON: {legacy}")
    print(f"Wrote {path}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate pipeline Markdown logs")
    parser.add_argument("--date", nargs="+", required=True, help="Brief date YYYY-MM-DD")
    args = parser.parse_args()
    dates = parse_date_list(args.date)
    ok = all(regenerate(d) for d in dates)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

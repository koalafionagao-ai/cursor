#!/usr/bin/env python3
"""Finalize pipeline run log and print English summary."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from common.dates import default_brief_date, parse_date_list  # noqa: E402
from common.pipeline_log import finalize_pipeline_log  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", nargs="*", default=[], help="Brief date YYYY-MM-DD")
    args = parser.parse_args()
    dates = parse_date_list(args.date) if args.date else [default_brief_date()]
    code = 0
    for d in dates:
        rc = finalize_pipeline_log(d)
        code = max(code, rc)
    sys.exit(code)


if __name__ == "__main__":
    main()

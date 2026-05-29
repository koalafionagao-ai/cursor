#!/usr/bin/env python3
"""已弃用：请使用 enrich.py。保留入口以兼容旧 workflow。"""

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    script = Path(__file__).resolve().parent / "enrich.py"
    sys.exit(subprocess.call([sys.executable, str(script)] + sys.argv[1:]))

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.gemini_client import print_available_models


if __name__ == "__main__":
    try:
        print_available_models()
    except Exception as exc:
        print(f"ERROR - {exc}")
        raise SystemExit(1) from exc

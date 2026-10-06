#!/usr/bin/env python3
"""Thin wrapper so `python main.py` works even without the package installed."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from txt2epub import main  # noqa: E402

if __name__ == "__main__":
    main()

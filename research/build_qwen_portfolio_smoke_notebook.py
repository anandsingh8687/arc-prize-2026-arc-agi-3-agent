#!/usr/bin/env python3
"""Rebuild notebooks/qwen-portfolio-smoke from Gate-1 v7.

This file is a thin entrypoint: the checked-in notebook is authoritative for the
Kaggle push. Re-create by running the executor build script logic (patches are
recorded in git history for notebooks/qwen-portfolio-smoke/).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "qwen-portfolio-smoke" / "arc3-qwen-portfolio-smoke.ipynb"

def main() -> int:
    if not OUT.is_file():
        print(f"missing {OUT}; restore from git or re-run the portfolio smoke builder", file=sys.stderr)
        return 1
    print(f"present: {OUT} ({OUT.stat().st_size} bytes)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

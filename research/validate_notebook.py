#!/usr/bin/env python3
"""Validate a notebook before it is uploaded: code parses, attachments resolve.

Two failures reached Kaggle that a local check would have caught for free.

Version 9 died in 10.8 s with an IndentationError at line 46, before the model
started -- nothing had parsed the generated notebook locally.

Version 10 was worse to diagnose: the agent lifecycle *succeeded* (GATE1_SMOKE_OK,
11 actions, clean teardown, exit 0) and Kaggle still marked the notebook failed,
during HTML export, on a markdown cell referencing a missing attachment
`tufa_labs.png` inherited from the forked Duck notebook. A presentation-layer
defect discarded a passing run.

    python research/validate_notebook.py notebooks/submission.ipynb

Exits non-zero on the first cell that will not parse, naming the cell index and
the line, so it can gate an upload:

    python research/validate_notebook.py nb.ipynb && make submit
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

# ![alt](attachment:name.png) -- nbconvert raises InvalidNotebook if `name.png`
# is not in that cell's own `attachments` map.
ATTACHMENT_REF = re.compile(r"attachment:([^\s)\"\']+)")


def code_cells(notebook: dict) -> list[tuple[int, str]]:
    """(index, source) for every code cell, indexed as the notebook displays."""
    out = []
    for i, cell in enumerate(notebook.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        out.append((i, source))
    return out


def markdown_cells(notebook: dict) -> list[tuple[int, str, dict]]:
    """(index, source, attachments) for every markdown cell."""
    out = []
    for i, cell in enumerate(notebook.get("cells", [])):
        if cell.get("cell_type") != "markdown":
            continue
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        out.append((i, source, cell.get("attachments") or {}))
    return out


def check_attachments(notebook: dict) -> int:
    """Every attachment: reference must resolve inside its own cell."""
    failures = 0
    for index, source, attachments in markdown_cells(notebook):
        for name in ATTACHMENT_REF.findall(source):
            if name not in attachments:
                failures += 1
                print(f"FAIL cell {index}: missing attachment {name!r}")
                print(f"     this cell provides: {sorted(attachments) or 'none'}")
                print("     nbconvert fails the whole notebook on HTML export,")
                print("     discarding an otherwise successful run.")
    return failures


def check(path: Path) -> int:
    try:
        raw = path.read_text()
    except OSError as exc:
        print(f"FAIL {path}: cannot read -- {exc.strerror}")
        return 1
    try:
        notebook = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"FAIL {path}: not valid JSON -- {exc}")
        return 1

    cells = code_cells(notebook)
    failures = 0

    for index, source in cells:
        # IPython magics and shell escapes are not Python; blank them out rather
        # than rejecting them, so a cell using !pip or %timeit still gets its
        # actual Python parsed.
        cleaned = "\n".join(
            "" if line.lstrip().startswith(("!", "%", "?")) else line
            for line in source.splitlines()
        )
        try:
            ast.parse(cleaned)
        except SyntaxError as exc:
            failures += 1
            line = exc.lineno or 0
            print(f"FAIL cell {index}, line {line}: {exc.msg}")
            for offset, text in enumerate(cleaned.splitlines()[max(0, line - 3):line + 1],
                                          start=max(1, line - 2)):
                marker = ">>" if offset == line else "  "
                print(f"  {marker} {offset:>4} | {text}")

    attachment_failures = check_attachments(notebook)

    if failures or attachment_failures:
        if failures:
            print(f"\n{failures} of {len(cells)} code cells will not parse.")
        if attachment_failures:
            print(f"{attachment_failures} unresolved markdown attachment reference(s).")
        print("Do not upload.")
        return 1

    md = len(markdown_cells(notebook))
    print(f"OK  {len(cells)} code cells parse, {md} markdown cells resolve: {path}")
    return 0


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    sys.exit(max(check(Path(p)) for p in sys.argv[1:]))


if __name__ == "__main__":
    main()

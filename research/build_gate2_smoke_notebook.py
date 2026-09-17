#!/usr/bin/env python3
"""Build the Gate 2 response-cap smoke notebook from immutable Version 7.

The browser draft is deliberately not an input.  Every edit is an exact-one
replacement against the committed Version 7 source, so a changed base or an
ambiguous match fails before a notebook can be uploaded.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "notebooks" / "arc3-gate1-v7-source.ipynb"
OUTPUT = ROOT / "notebooks" / "arc3-gate2-cap1024-smoke.ipynb"


def source_text(cell: dict) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else source


def set_source(cell: dict, source: str) -> None:
    cell["source"] = source.splitlines(keepends=True)


def replace_once(notebook: dict, old: str, new: str, label: str) -> None:
    matches: list[int] = []
    for index, cell in enumerate(notebook.get("cells", [])):
        if cell.get("cell_type") == "code" and old in source_text(cell):
            matches.append(index)
    if len(matches) != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {matches}")
    index = matches[0]
    source = source_text(notebook["cells"][index])
    if source.count(old) != 1:
        raise RuntimeError(f"{label}: cell {index} contains {source.count(old)} matches")
    set_source(notebook["cells"][index], source.replace(old, new, 1))
    print(f"EDIT {label}: cell {index}")


def validate_python(notebook: dict) -> None:
    failures: list[str] = []
    count = 0
    for index, cell in enumerate(notebook.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        count += 1
        source = source_text(cell)
        cleaned = "\n".join(
            "" if line.lstrip().startswith(("!", "%", "?")) else line
            for line in source.splitlines()
        )
        try:
            ast.parse(cleaned)
        except SyntaxError as exc:
            failures.append(f"cell {index}, line {exc.lineno}: {exc.msg}")
    if failures:
        raise RuntimeError("generated notebook does not parse: " + "; ".join(failures))
    print(f"PARSE OK: {count} code cells")


def strip_inherited_markdown(notebook: dict) -> None:
    """Keep one functional summary and remove fork presentation dependencies."""
    code = [
        cell for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "code"
    ]
    notebook["cells"] = [
        {
            "cell_type": "markdown",
            "id": "gate2-smoke-scope",
            "metadata": {},
            "source": [
                "# ARC-AGI-3 Gate 2 response-cap smoke\n",
                "\n",
                "Generated from immutable Gate 1 Version 7. This notebook changes "
                "only the analyzer response cap and runs one 60-second lifecycle "
                "smoke from the server-ready timestamp.\n",
            ],
        },
        *code,
    ]
    print(f"MARKDOWN stripped to one dependency-free summary; retained {len(code)} code cells")


def main() -> None:
    notebook = json.loads(SOURCE.read_text())

    replace_once(
        notebook,
        'os.environ["TAAF_MINIMAL_DIAGNOSTICS"] = "1"\n',
        'os.environ["TAAF_MINIMAL_DIAGNOSTICS"] = "1"\n\n'
        '# Gate 2 response-cap ablation. This is the only policy change from immutable Version 7.\n'
        'GATE2_RESPONSE_TOKEN_CAP = 1024\n'
        'os.environ["LOCAL_ANALYZER_MAX_OUTPUT"] = str(GATE2_RESPONSE_TOKEN_CAP)\n'
        'print(f"GATE2_RESPONSE_TOKEN_CAP={GATE2_RESPONSE_TOKEN_CAP}", flush=True)\n',
        "response cap",
    )
    replace_once(
        notebook,
        "# Honour any PYTHONPATH a setup command exported.\n"
        "for entry in reversed([e for e in os.environ.get(\"PYTHONPATH\", \"\").split(os.pathsep) if e]):\n"
        "    if entry not in sys.path:\n"
        "        sys.path.insert(0, entry)",
        "# Honour any PYTHONPATH a setup command exported.\n"
        "for entry in reversed([e for e in os.environ.get(\"PYTHONPATH\", \"\").split(os.pathsep) if e]):\n"
        "    if entry not in sys.path:\n"
        "        sys.path.insert(0, entry)\n\n"
        "# Setup returns only after the production vLLM endpoint is ready.\n"
        "GATE1_SERVER_READY_EPOCH = time.time()\n"
        "GATE1_SERVER_STARTUP_SECONDS = GATE1_SERVER_READY_EPOCH - NOTEBOOK_START_EPOCH\n"
        "print(\n"
        "    f\"GATE1_SERVER_READY epoch={GATE1_SERVER_READY_EPOCH} \"\n"
        "    f\"startup_seconds={GATE1_SERVER_STARTUP_SECONDS}\",\n"
        "    flush=True,\n"
        ")",
        "server-ready timestamp",
    )
    replace_once(
        notebook,
        "GATE1_SMOKE_MODE = False\n"
        "GATE1_SMOKE_GAME_SECONDS = 60.0\n"
        "GATE1_SMOKE_NOTEBOOK_LIMIT_SECONDS = 600.0\n",
        "GATE1_SMOKE_MODE = True\n"
        "GATE1_SMOKE_GAME_SECONDS = 60.0\n"
        "GATE1_SMOKE_STARTUP_LIMIT_SECONDS = 900.0\n",
        "smoke configuration",
    )
    replace_once(
        notebook,
        'if GATE1_SAFETY_MARGIN_SECONDS < 0.15 * float(target.max_runtime_s):\n'
        '    raise RuntimeError("Gate 1 safety margin is below 15% of the notebook budget.")\n',
        'if GATE1_SAFETY_MARGIN_SECONDS < 0.15 * float(target.max_runtime_s):\n'
        '    raise RuntimeError("Gate 1 safety margin is below 15% of the notebook budget.")\n'
        'if GATE1_SMOKE_MODE:\n'
        '    if GATE1_SERVER_READY_EPOCH <= NOTEBOOK_START_EPOCH:\n'
        '        raise RuntimeError("Server-ready timestamp must follow notebook start.")\n'
        '    if GATE1_SERVER_STARTUP_SECONDS > GATE1_SMOKE_STARTUP_LIMIT_SECONDS:\n'
        '        raise TimeoutError(\n'
        '            f"vLLM startup exceeded {GATE1_SMOKE_STARTUP_LIMIT_SECONDS}s: "\n'
        '            f"{GATE1_SERVER_STARTUP_SECONDS}s."\n'
        '        )\n',
        "startup assertions",
    )
    replace_once(
        notebook,
        "if GATE1_SMOKE_MODE:\n"
        "    hard_end_epoch = NOTEBOOK_START_EPOCH + GATE1_SMOKE_NOTEBOOK_LIMIT_SECONDS\n"
        "    soft_end_epoch = hard_end_epoch - 30.0\n",
        "if GATE1_SMOKE_MODE:\n"
        "    hard_end_epoch = GATE1_SERVER_READY_EPOCH + GATE1_SMOKE_GAME_SECONDS + 30.0\n"
        "    soft_end_epoch = hard_end_epoch - 30.0\n",
        "server-ready game deadline",
    )
    replace_once(
        notebook,
        '    f"hard_end_epoch={hard_end_epoch}",\n',
        '    f"hard_end_epoch={hard_end_epoch} "\n'
        '    f"server_ready_epoch={GATE1_SERVER_READY_EPOCH} "\n'
        '    f"startup_seconds={GATE1_SERVER_STARTUP_SECONDS}",\n',
        "deadline diagnostics",
    )

    strip_inherited_markdown(notebook)
    validate_python(notebook)
    OUTPUT.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n")
    print(f"WROTE {OUTPUT}")


if __name__ == "__main__":
    main()

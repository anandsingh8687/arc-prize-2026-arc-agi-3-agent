#!/usr/bin/env python3
"""Build an unsubmitted W/A/W-repeat test from the pinned Duck lifecycle."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    True: (ROOT / "notebooks/arc3-memory-screen-smoke.ipynb",
           "d30bf6733e0d933344c492463960609cde9f5bb21b4c3acaf77058d1911a5e77"),
    False: (ROOT / "notebooks/arc3-memory-screen.ipynb",
            "010cb69e88fb04b7dab9722ff0cf0a00be301394bebe6397c72e351b5d80a1b9"),
}
OUTPUTS = {
    True: ROOT / "notebooks/affordance-smoke/arc3-affordance-smoke.ipynb",
    False: ROOT / "notebooks/affordance-screen/arc3-affordance-screen.ipynb",
}


def source(cell: dict) -> str:
    value = cell.get("source", "")
    return "".join(value) if isinstance(value, list) else value


def replace_once(value: str, old: str, new: str) -> str:
    count = value.count(old)
    if count != 1:
        raise RuntimeError(f"expected one occurrence of {old[:65]!r}, found {count}")
    return value.replace(old, new, 1)


def set_source(cell: dict, value: str) -> None:
    cell["source"] = value.splitlines(keepends=True)


def build(smoke: bool) -> Path:
    input_path, expected_hash = SOURCES[smoke]
    actual_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        raise RuntimeError(f"pinned source changed: {input_path} {actual_hash}")
    notebook = json.loads(input_path.read_text())

    package = notebook["cells"][6]
    text = source(package)
    contents = (ROOT / "arc3/duck_affordance_adapter.py").read_text()
    text += (
        "\n# State-dependent affordance prompt treatment.\n"
        f"(_memory_package / 'duck_affordance_adapter.py').write_text({contents!r})\n"
        "from arc3.duck_affordance_adapter import add_affordance_instruction\n"
        "print('AFFORDANCE_ADAPTER_IMPORTED', flush=True)\n"
    )
    set_source(package, text)

    settings = notebook["cells"][7]
    text = source(settings)
    text = replace_once(
        text, "GATE2_CONCURRENCY = 1 if GATE2_COMPARISON_SMOKE else 2",
        "GATE2_CONCURRENCY = 1 if GATE2_COMPARISON_SMOKE else 3",
    )
    set_source(settings, text)

    experiment = notebook["cells"][8]
    text = source(experiment)
    text = replace_once(
        text,
        'GATE2_GAME_IDS = ("cd82-fb555c5d", "ka59-38d34dbb")',
        'GATE2_GAME_IDS = ("tn36-ef4dde99", "cd82-fb555c5d", "ka59-38d34dbb")',
    )
    text = replace_once(
        text, '{"trial_id": "M", "replicate": 0, "arm": "M",',
        '{"trial_id": "A", "replicate": 0, "arm": "A",',
    )
    text = replace_once(
        text, "analyzer_cls = _MemoryToolAgent if spec['arm'] == 'M' else _Gate2ToolAgent",
        "analyzer_cls = _AffordanceToolAgent if spec['arm'] == 'A' else _Gate2ToolAgent",
    )
    text = replace_once(
        text, "def _gate2_make_analyzer_factory(spec, solver):",
        "class _AffordanceToolAgent(_Gate2ToolAgent):\n"
        "    def __init__(self, *args, **kwargs):\n"
        "        super().__init__(*args, **kwargs)\n"
        "        add_affordance_instruction(self)\n\n\n"
        "def _gate2_make_analyzer_factory(spec, solver):",
    )
    set_source(experiment, text)

    audit = notebook["cells"][9]
    text = source(audit)
    text = replace_once(text, 'for arm in ("W", "W-repeat", "M")',
                        'for arm in ("W", "W-repeat", "A")')
    text = text.replace("MEMORY_", "AFFORDANCE_")
    set_source(audit, text)
    notebook["cells"][0]["source"] = [
        "# ARC-AGI-3 state-dependent affordance screen\n",
        "Private development benchmark; no competition submission.\n",
    ]

    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        cleaned = "\n".join(
            "" if line.lstrip().startswith(("!", "%", "?")) else line
            for line in source(cell).splitlines()
        )
        try:
            ast.parse(cleaned)
        except SyntaxError as exc:
            raise RuntimeError(f"cell {index} does not parse: {exc}") from exc
    output = OUTPUTS[smoke]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(notebook, indent=1) + "\n")
    print(f"BUILT {output} smoke={smoke} code_cells=9")
    return output


if __name__ == "__main__":
    build(True)
    build(False)

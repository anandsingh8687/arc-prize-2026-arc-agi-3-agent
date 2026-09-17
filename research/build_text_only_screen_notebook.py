#!/usr/bin/env python3
"""Build a matched image-vs-text screen from the pinned Duck notebook.

The treatment changes only Duck's MULTIMODAL_CONTEXT flag.  Both arms retain
the same Python inspection tool (`current_frame.ascii` and `.segmentation`),
checkpoint, sampling seed, action budget, and uncapped response length.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    True: (
        ROOT / "notebooks/arc3-memory-screen-smoke.ipynb",
        "d30bf6733e0d933344c492463960609cde9f5bb21b4c3acaf77058d1911a5e77",
    ),
    False: (
        ROOT / "notebooks/arc3-memory-screen.ipynb",
        "010cb69e88fb04b7dab9722ff0cf0a00be301394bebe6397c72e351b5d80a1b9",
    ),
}
OUTPUTS = {
    True: ROOT / "notebooks/text-only-smoke/arc3-text-only-smoke.ipynb",
    False: ROOT / "notebooks/text-only-screen/arc3-text-only-screen.ipynb",
}


def _source(cell: dict) -> str:
    value = cell.get("source", "")
    return "".join(value) if isinstance(value, list) else value


def _replace_once(value: str, old: str, new: str) -> str:
    count = value.count(old)
    if count != 1:
        raise RuntimeError(f"expected one occurrence of {old[:70]!r}, found {count}")
    return value.replace(old, new, 1)


def _set_source(cell: dict, value: str) -> None:
    cell["source"] = value.splitlines(keepends=True)


def build(smoke: bool) -> Path:
    source_path, pinned_hash = SOURCES[smoke]
    actual_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if actual_hash != pinned_hash:
        raise RuntimeError(f"pinned source changed: {source_path} {actual_hash}")
    notebook = json.loads(source_path.read_text())

    settings = notebook["cells"][7]
    settings_text = _source(settings)
    settings_text = _replace_once(
        settings_text, "GATE2_TRIAL_SECONDS = 900.0", "GATE2_TRIAL_SECONDS = 600.0"
    )
    settings_text = _replace_once(
        settings_text,
        "GATE2_CONCURRENCY = 1 if GATE2_COMPARISON_SMOKE else 2",
        "GATE2_CONCURRENCY = 1 if GATE2_COMPARISON_SMOKE else 3",
    )
    _set_source(settings, settings_text)

    experiment = notebook["cells"][8]
    experiment_text = _source(experiment)
    experiment_text = _replace_once(
        experiment_text,
        'GATE2_GAME_IDS = ("cd82-fb555c5d", "ka59-38d34dbb")',
        'GATE2_GAME_IDS = ("cd82-fb555c5d", "ka59-38d34dbb", "g50t-5849a774")',
    )
    experiment_text = _replace_once(
        experiment_text,
        '{"trial_id": "M", "replicate": 0, "arm": "M",',
        '{"trial_id": "T", "replicate": 0, "arm": "T",',
    )
    experiment_text = _replace_once(
        experiment_text,
        "analyzer_cls = _MemoryToolAgent if spec['arm'] == 'M' else _Gate2ToolAgent",
        "analyzer_cls = _Gate2ToolAgent",
    )
    experiment_text = _replace_once(
        experiment_text,
        '    trial_id = spec["trial_id"]\n    _gate2_tool_agent_module._LOCAL_ANALYZER_MAX_OUTPUT',
        '    trial_id = spec["trial_id"]\n'
        '    _gate2_os.environ["MULTIMODAL_CONTEXT"] = '
        '("" if spec["arm"] == "T" else "current_grid")\n'
        '    print(f"TEXT_MODE_ACTIVE arm={spec[\'arm\']} '
        'image={spec[\'arm\'] != \'T\'}", flush=True)\n'
        '    _gate2_tool_agent_module._LOCAL_ANALYZER_MAX_OUTPUT',
    )
    _set_source(experiment, experiment_text)

    audit = notebook["cells"][9]
    audit_text = _source(audit)
    audit_text = _replace_once(
        audit_text, 'for arm in ("W", "W-repeat", "M")',
        'for arm in ("W", "W-repeat", "T")',
    )
    audit_text = audit_text.replace("MEMORY_", "TEXT_")
    _set_source(audit, audit_text)

    notebook["cells"][0]["source"] = [
        "# ARC-AGI-3 text-only modality screen\n",
        "Private local-only test: W/image, T/text-only, W-repeat/image. "
        "No competition submission.\n",
    ]

    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        cleaned = "\n".join(
            "" if line.lstrip().startswith(("!", "%", "?")) else line
            for line in _source(cell).splitlines()
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

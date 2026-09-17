#!/usr/bin/env python3
"""Build a matched short screen of Qwen's native medium reasoning effort.

The source notebooks are pinned.  W, E, and W-repeat share one vLLM server;
only E changes the chat-template reasoning instruction.  No output is cut off.
"""

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
    True: ROOT / "notebooks/reasoning-smoke/arc3-reasoning-smoke.ipynb",
    False: ROOT / "notebooks/reasoning-screen/arc3-reasoning-screen.ipynb",
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

    settings = notebook["cells"][7]
    text = source(settings)
    text = replace_once(text, "GATE2_TRIAL_SECONDS = 900.0", "GATE2_TRIAL_SECONDS = 600.0")
    text = replace_once(
        text, "GATE2_CONCURRENCY = 1 if GATE2_COMPARISON_SMOKE else 2",
        "GATE2_CONCURRENCY = 1 if GATE2_COMPARISON_SMOKE else 3",
    )
    set_source(settings, text)

    experiment = notebook["cells"][8]
    text = source(experiment)
    text = replace_once(
        text, 'GATE2_GAME_IDS = ("cd82-fb555c5d", "ka59-38d34dbb")',
        'GATE2_GAME_IDS = ("lf52-271a04aa", "ar25-0c556536", "re86-8af5384d")',
    )
    text = replace_once(
        text, '{"trial_id": "M", "replicate": 0, "arm": "M",',
        '{"trial_id": "E", "replicate": 0, "arm": "E",',
    )
    text = replace_once(
        text, "analyzer_cls = _MemoryToolAgent if spec['arm'] == 'M' else _Gate2ToolAgent",
        "analyzer_cls = _Gate2ToolAgent",
    )
    text = replace_once(
        text,
        "def _gate2_make_analyzer_factory(spec, solver):",
        "_GATE2_ORIGINAL_BUILD_PAYLOAD = _gate2_tool_agent_module.build_chat_payload\n"
        "_GATE2_EFFORT_PAYLOAD_COUNT = 0\n\n"
        "def _gate2_medium_payload(*args, **kwargs):\n"
        "    global _GATE2_EFFORT_PAYLOAD_COUNT\n"
        "    payload = _GATE2_ORIGINAL_BUILD_PAYLOAD(*args, **kwargs)\n"
        "    if 'chat_template_kwargs' not in payload:\n"
        "        raise RuntimeError('Medium effort requires the vLLM chat template payload.')\n"
        "    payload['chat_template_kwargs']['reasoning_effort'] = 'medium'\n"
        "    _GATE2_EFFORT_PAYLOAD_COUNT += 1\n"
        "    return payload\n\n\n"
        "def _gate2_make_analyzer_factory(spec, solver):",
    )
    text = replace_once(
        text,
        '    trial_id = spec["trial_id"]\n    _gate2_tool_agent_module._LOCAL_ANALYZER_MAX_OUTPUT',
        '    trial_id = spec["trial_id"]\n'
        '    _gate2_tool_agent_module.build_chat_payload = (\n'
        '        _gate2_medium_payload if spec["arm"] == "E" else _GATE2_ORIGINAL_BUILD_PAYLOAD\n'
        '    )\n'
        '    print(f"REASONING_EFFORT_ACTIVE arm={spec[\'arm\']} setting={\'medium\' if spec[\'arm\'] == \'E\' else \'default\'}", flush=True)\n'
        '    _gate2_tool_agent_module._LOCAL_ANALYZER_MAX_OUTPUT',
    )
    text = replace_once(
        text,
        "    summary = _gate2_summarize_trial(spec, rows, gpu_seconds)\n",
        "    summary = _gate2_summarize_trial(spec, rows, gpu_seconds)\n"
        "    summary['medium_payloads_total'] = _GATE2_EFFORT_PAYLOAD_COUNT\n"
        "    if spec['arm'] == 'E' and _GATE2_EFFORT_PAYLOAD_COUNT == 0:\n"
        "        problems.append('medium effort sent zero requests')\n",
    )
    set_source(experiment, text)

    audit = notebook["cells"][9]
    text = source(audit)
    text = replace_once(text, 'for arm in ("W", "W-repeat", "M")',
                        'for arm in ("W", "W-repeat", "E")')
    text = text.replace("MEMORY_", "REASONING_")
    set_source(audit, text)
    notebook["cells"][0]["source"] = [
        "# ARC-AGI-3 native reasoning-effort screen\n",
        "Private local-only test: W/default, E/medium, W-repeat/default. "
        "No competition submission.\n",
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

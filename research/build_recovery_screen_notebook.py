#!/usr/bin/env python3
"""Build private, local-only Duck W/W-repeat/recovery Kaggle notebooks.

The two known-good memory notebooks are pinned inputs. No scored submission is
made by this builder or by the notebooks it produces.
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
    True: ROOT / "notebooks/recovery-smoke/arc3-recovery-smoke.ipynb",
    False: ROOT / "notebooks/recovery-screen/arc3-recovery-screen.ipynb",
}
REPEAT_OUTPUTS = {
    True: ROOT / "notebooks/recovery-repeat-smoke/arc3-recovery-repeat-smoke.ipynb",
    False: ROOT / "notebooks/recovery-repeat-screen/arc3-recovery-repeat-screen.ipynb",
}


def cell_source(cell: dict) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else source


def set_source(cell: dict, source: str) -> None:
    cell["source"] = source.splitlines(keepends=True)


def replace_once(source: str, old: str, new: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"expected one occurrence of {old[:72]!r}; found {count}")
    return source.replace(old, new, 1)


def build(smoke: bool, variant: str = "timer") -> Path:
    if variant not in ("timer", "repeat"):
        raise ValueError(f"unknown recovery variant: {variant}")
    input_path, expected_hash = SOURCES[smoke]
    actual_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        raise RuntimeError(f"pinned source changed: {input_path} {actual_hash}")
    notebook = json.loads(input_path.read_text())
    package = notebook["cells"][6]
    text = cell_source(package)
    additions = ["# Recovery experiment; treatment inherits plain Duck, not the memory arm.\n"]
    for name in ("recovery.py", "duck_recovery_adapter.py"):
        contents = (ROOT / "arc3" / name).read_text()
        additions.append(f"(_memory_package / {name!r}).write_text({contents!r})\n")
    additions.append(
        "from arc3.duck_recovery_adapter import RecoveryToolAgent as _RecoveryToolAgent\n"
    )
    additions.append("print('RECOVERY_ADAPTER_IMPORTED', flush=True)\n")
    set_source(package, text + "\n" + "".join(additions))

    settings = notebook["cells"][7]
    text = cell_source(settings)
    wall_seconds = "0" if smoke else ("180" if variant == "timer" else "inf")
    text = replace_once(
        text, f"GATE2_COMPARISON_SMOKE = {smoke}",
        f"GATE2_COMPARISON_SMOKE = {smoke}\n"
        f"os.environ['ARC3_RECOVERY_WALL_SECONDS'] = {wall_seconds!r}\n"
        f"os.environ['ARC3_RECOVERY_ACTION_LIMIT'] = {'0' if variant == 'repeat' else '80'!r}",
    )
    text = replace_once(
        text, "GATE2_CONCURRENCY = 1 if GATE2_COMPARISON_SMOKE else 2",
        "GATE2_CONCURRENCY = 1 if GATE2_COMPARISON_SMOKE else 3",
    )
    text = replace_once(
        text,
        '                "memory_transitions": int(getattr(self.analyzer, "_memory_transitions", 0)),',
        '                "memory_transitions": int(getattr(self.analyzer, "_memory_transitions", 0)),\n'
        '                "recovery_prompt_count": int(getattr(self.analyzer, "_recovery_prompt_count", 0)),\n'
        '                "recovery_probe_count": int(getattr(self.analyzer, "_recovery_probe_count", 0)),\n'
        '                "recovery_rejections": int(getattr(self.analyzer, "_recovery_rejections", 0)),',
    )
    set_source(settings, text)

    experiment = notebook["cells"][8]
    text = cell_source(experiment)
    text = replace_once(
        text,
        'GATE2_GAME_IDS = ("cd82-fb555c5d", "ka59-38d34dbb")',
        'GATE2_GAME_IDS = ("cd82-fb555c5d", "tn36-ef4dde99", "ka59-38d34dbb")',
    )
    text = replace_once(text, '{"trial_id": "M", "replicate": 0, "arm": "M",',
                        '{"trial_id": "S", "replicate": 0, "arm": "S",')
    text = replace_once(
        text,
        "analyzer_cls = _MemoryToolAgent if spec['arm'] == 'M' else _Gate2ToolAgent",
        "analyzer_cls = _RecoveryToolAgent if spec['arm'] == 'S' else _Gate2ToolAgent",
    )
    text = replace_once(text,
        '        "memory_transitions": int(session.get("memory_transitions", 0)),',
        '        "memory_transitions": int(session.get("memory_transitions", 0)),\n'
        '        "recovery_prompt_count": int(session.get("recovery_prompt_count", 0)),\n'
        '        "recovery_probe_count": int(session.get("recovery_probe_count", 0)),\n'
        '        "recovery_rejections": int(session.get("recovery_rejections", 0)),')
    text = replace_once(text,
        '        "memory_transitions": sum(int(row["memory_transitions"]) for row in rows),',
        '        "memory_transitions": sum(int(row["memory_transitions"]) for row in rows),\n'
        '        "recovery_prompt_count": sum(int(row["recovery_prompt_count"]) for row in rows),\n'
        '        "recovery_probe_count": sum(int(row["recovery_probe_count"]) for row in rows),\n'
        '        "recovery_rejections": sum(int(row["recovery_rejections"]) for row in rows),')
    set_source(experiment, text)

    audit = notebook["cells"][9]
    text = cell_source(audit)
    text = replace_once(text, 'for arm in ("W", "W-repeat", "M")',
                        'for arm in ("W", "W-repeat", "S")')
    text = text.replace("MEMORY_", "RECOVERY_")
    text = replace_once(
        text,
        '    and all(row.get("terminal") for row in _mem_rows)',
        '    and all(row.get("terminal") for row in _mem_rows)\n'
        '    and (not GATE2_COMPARISON_SMOKE or any(\n'
        '        row.get("trial_id") == "S" and int(row.get("recovery_probe_count", 0)) > 0\n'
        '        for row in _mem_rows\n'
        '    ))',
    )
    set_source(audit, text)
    notebook["cells"][0]["source"] = [
        f"# ARC-AGI-3 {variant} conditional-recovery screen\n",
        "Private development benchmark; never a competition submission.\n",
    ]
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        source = cell_source(cell)
        cleaned = "\n".join("" if line.lstrip().startswith(("!", "%", "?")) else line
                            for line in source.splitlines())
        try:
            ast.parse(cleaned)
        except SyntaxError as exc:
            raise RuntimeError(f"cell {index} does not parse: {exc}") from exc
    output = (OUTPUTS if variant == "timer" else REPEAT_OUTPUTS)[smoke]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(notebook, indent=1) + "\n")
    print(f"BUILT {output} smoke={smoke} variant={variant} code_cells=9")
    return output


if __name__ == "__main__":
    build(True)
    build(False)

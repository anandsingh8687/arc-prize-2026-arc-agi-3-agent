#!/usr/bin/env python3
"""Build a local-only Duck W / W-repeat / memory screen from the passing lifecycle.

Smoke is two 60-second one-game trials.  The screen is three matched-seed
15-minute trials over cd82 and ka59.  No submission is authorized or attempted.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "notebooks" / "arc3-gate2-comparison-smoke.ipynb"
SOURCE_SHA256 = "6e44078559da75ef2c7ae114b980fc96fe10ef9278c65c0ee50447076e6bf68c"
OUTPUT_SMOKE = ROOT / "notebooks" / "arc3-memory-screen-smoke.ipynb"
OUTPUT_SCREEN = ROOT / "notebooks" / "arc3-memory-screen.ipynb"


def source(cell: dict) -> str:
    value = cell.get("source", "")
    return "".join(value) if isinstance(value, list) else value


def replace_once(value: str, old: str, new: str) -> str:
    if value.count(old) != 1:
        raise RuntimeError(f"expected exactly one occurrence of {old[:70]!r}")
    return value.replace(old, new, 1)


def set_source(cell: dict, value: str) -> None:
    cell["source"] = value.splitlines(keepends=True)


def package_cell() -> dict:
    lines = [
        "# Exact tested memory adapter embedded for offline Kaggle execution.\n",
        "from pathlib import Path as _memory_Path\n",
        "import sys as _memory_sys\n",
        "_memory_package = WORKING_DIR / 'arc3'\n",
        "_memory_package.mkdir(parents=True, exist_ok=True)\n",
    ]
    for name in ("__init__.py", "effects.py", "memory.py", "duck_memory_adapter.py"):
        path = ROOT / "arc3" / name
        content = path.read_text()
        lines.append(f"(_memory_package / {name!r}).write_text({content!r})\n")
    lines.extend([
        "if str(WORKING_DIR) not in _memory_sys.path:\n",
        "    _memory_sys.path.insert(0, str(WORKING_DIR))\n",
        "from arc3.duck_memory_adapter import MemoryToolAgent as _MemoryToolAgent\n",
        "print('MEMORY_ADAPTER_IMPORTED', flush=True)\n",
    ])
    return {
        "cell_type": "code", "execution_count": None, "metadata": {},
        "outputs": [], "source": lines,
    }


def audit_cell() -> str:
    return '''# Local-only result audit: the final answer is levels, not token savings.
import json as _mem_json

_mem_lifecycle = _mem_json.loads((_GATE2_ROOT / "lifecycle.json").read_text())
_mem_rows = _gate2_write_progress_index()
_mem_summaries = []
for _mem_spec in _gate2_trial_specs:
    _mem_summary_path = _GATE2_ROOT / _mem_spec["trial_id"] / "summary.json"
    if _mem_summary_path.exists():
        _mem_summaries.append(_mem_json.loads(_mem_summary_path.read_text()))
for _mem_row in _mem_rows:
    print("MEMORY_GAME " + _mem_json.dumps(_mem_row, sort_keys=True), flush=True)
for _mem_summary in _mem_summaries:
    print("MEMORY_ARM " + _mem_json.dumps(_mem_summary, sort_keys=True), flush=True)

_mem_by_trial = {spec["trial_id"]: {
    row["game_id"]: row for row in _gate2_trial_rows(spec["trial_id"])
} for spec in _gate2_trial_specs}
_mem_pairs = {}
for _mem_game in _gate2_expected_ids:
    _mem_pairs[_mem_game] = {
        arm: _mem_by_trial.get(arm, {}).get(_mem_game, {}).get("levels_completed")
        for arm in ("W", "W-repeat", "M")
    }
print("MEMORY_PAIRED_LEVELS " + _mem_json.dumps(_mem_pairs, sort_keys=True), flush=True)

_mem_expected = [spec["trial_id"] for spec in _gate2_trial_specs]
_mem_clean = bool(
    _mem_lifecycle.get("benchmark_ok")
    and _mem_lifecycle.get("teardown_ok")
    and not _mem_lifecycle.get("hard_guard_triggered")
    and _mem_lifecycle.get("completed_trials") == _mem_expected
    and len(_mem_rows) == len(_mem_expected) * len(_gate2_expected_ids)
    and all(row.get("terminal") for row in _mem_rows)
    and not _mem_lifecycle.get("post_teardown_gpu_rows")
)
print("MEMORY_SCREEN_FINAL " + _mem_json.dumps({
    "smoke": GATE2_COMPARISON_SMOKE,
    "clean": _mem_clean,
    "benchmark_ok": _mem_lifecycle.get("benchmark_ok"),
    "teardown_ok": _mem_lifecycle.get("teardown_ok"),
    "completed_trials": _mem_lifecycle.get("completed_trials"),
}, sort_keys=True), flush=True)
print("MEMORY_SMOKE_OK" if GATE2_COMPARISON_SMOKE and _mem_clean else
      "MEMORY_SCREEN_OK" if _mem_clean else "MEMORY_SCREEN_FAILED", flush=True)
'''


def build(smoke: bool, output: Path) -> None:
    actual = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if actual != SOURCE_SHA256:
        raise RuntimeError(f"passing notebook changed: {actual}")
    notebook = json.loads(SOURCE.read_text())
    notebook["cells"].insert(6, package_cell())
    settings = notebook["cells"][7]
    text = source(settings)
    text = replace_once(text, "GATE2_COMPARISON_SMOKE = True", f"GATE2_COMPARISON_SMOKE = {smoke}")
    text = replace_once(text, "GATE2_TRIAL_SECONDS = 6600.0", "GATE2_TRIAL_SECONDS = 900.0")
    text = replace_once(text, "GATE2_CANDIDATE_CAP = 1024", "GATE2_CANDIDATE_CAP = 0")
    text = replace_once(text, "GATE2_CONCURRENCY = 1 if GATE2_COMPARISON_SMOKE else 8",
                        "GATE2_CONCURRENCY = 1 if GATE2_COMPARISON_SMOKE else 2")
    text = replace_once(text,
        '"instrumented_actions": int(getattr(self, "_gate2_executed_actions", 0)),',
        '"instrumented_actions": int(getattr(self, "_gate2_executed_actions", 0)),\n'
        '                "memory_commits": int(getattr(self.analyzer, "_memory_commits", 0)),\n'
        '                "memory_rejections": int(getattr(self.analyzer, "_memory_rejections", 0)),\n'
        '                "memory_missing_updates": int(getattr(self.analyzer, "_memory_missing_updates", 0)),\n'
        '                "memory_empty_updates": int(getattr(self.analyzer, "_memory_empty_updates", 0)),\n'
        '                "memory_transitions": int(getattr(self.analyzer, "_memory_transitions", 0)),')
    set_source(settings, text)

    experiment = notebook["cells"][8]
    text = source(experiment)
    ids_start = text.index("GATE2_GAME_IDS = (")
    ids_end = text.index("\n\ncompetition_env_files", ids_start)
    text = text[:ids_start] + (
        'GATE2_GAME_IDS = ("cd82-fb555c5d", "ka59-38d34dbb")'
    ) + text[ids_end:]
    specs_start = text.index("_gate2_trial_specs = [")
    specs_end = text.index("\n\nprint(\n    \"GATE2_PROTOCOL", specs_start)
    text = text[:specs_start] + '''_gate2_trial_specs = [
    {"trial_id": "W", "replicate": 0, "arm": "W", "cap": 0, "seed": GATE2_SEEDS[0]},
    {"trial_id": "M", "replicate": 0, "arm": "M", "cap": 0, "seed": GATE2_SEEDS[0]},
]
if not GATE2_COMPARISON_SMOKE:
    _gate2_trial_specs.append(
        {"trial_id": "W-repeat", "replicate": 0, "arm": "W-repeat", "cap": 0,
         "seed": GATE2_SEEDS[0]}
    )''' + text[specs_end:]
    text = replace_once(text,
        "analyzer = _Gate2ToolAgent(\n            model=solver.model,",
        "analyzer_cls = _MemoryToolAgent if spec['arm'] == 'M' else _Gate2ToolAgent\n"
        "        analyzer = analyzer_cls(\n            model=solver.model,")
    text = replace_once(text,
        '"instrumented_actions": int(session.get("instrumented_actions", 0)),',
        '"instrumented_actions": int(session.get("instrumented_actions", 0)),\n'
        '        "memory_commits": int(session.get("memory_commits", 0)),\n'
        '        "memory_rejections": int(session.get("memory_rejections", 0)),\n'
        '        "memory_missing_updates": int(session.get("memory_missing_updates", 0)),\n'
        '        "memory_empty_updates": int(session.get("memory_empty_updates", 0)),\n'
        '        "memory_transitions": int(session.get("memory_transitions", 0)),')
    text = replace_once(text,
        '"finish_reason_length_count": length_count,',
        '"finish_reason_length_count": length_count,\n'
        '        "memory_commits": sum(int(row["memory_commits"]) for row in rows),\n'
        '        "memory_rejections": sum(int(row["memory_rejections"]) for row in rows),\n'
        '        "memory_missing_updates": sum(int(row["memory_missing_updates"]) for row in rows),\n'
        '        "memory_empty_updates": sum(int(row["memory_empty_updates"]) for row in rows),\n'
        '        "memory_transitions": sum(int(row["memory_transitions"]) for row in rows),')
    text = replace_once(text,
        'trial_bm.solver.analyzer_timeout = 60.0 if GATE2_COMPARISON_SMOKE else 900.0',
        'trial_bm.solver.analyzer_timeout = 60.0 if GATE2_COMPARISON_SMOKE else 180.0')
    # nvidia-smi can briefly retain an exited worker without /proc start ticks.
    # Treat that unresolved GPU row as still owned until a fresh query removes it.
    text = replace_once(text,
        'return expected_ticks is None or actual_ticks == expected_ticks',
        'return expected_ticks is None or actual_ticks is None or actual_ticks == expected_ticks')
    text = replace_once(text,
        'owned_identity[row["pid"]] is None\n'
        '                or row.get("start_ticks") == owned_identity[row["pid"]]',
        'owned_identity[row["pid"]] is None\n'
        '                or row.get("start_ticks") is None\n'
        '                or row.get("start_ticks") == owned_identity[row["pid"]]')
    set_source(experiment, text)
    set_source(notebook["cells"][9], audit_cell())
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        cleaned = "\n".join("" if line.lstrip().startswith(("!", "%", "?")) else line
                            for line in source(cell).splitlines())
        try:
            ast.parse(cleaned)
        except SyntaxError as exc:
            raise RuntimeError(f"cell {index} does not parse: {exc}") from exc
    notebook["cells"][0]["source"] = [
        "# ARC-AGI-3 structured-memory screen\n",
        "Local-only Duck comparison. No competition submission.\n",
    ]
    output.write_text(json.dumps(notebook, indent=1) + "\n")
    print(f"BUILT {output} smoke={smoke} code_cells=9")


if __name__ == "__main__":
    build(True, OUTPUT_SMOKE)
    build(False, OUTPUT_SCREEN)

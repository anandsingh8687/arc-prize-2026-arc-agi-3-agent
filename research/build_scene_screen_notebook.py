#!/usr/bin/env python3
"""Generate the complete-scene W/C/T/W-repeat short experiment."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from build_text_only_screen_notebook import SOURCES, _source, _replace_once, _set_source


ROOT = Path(__file__).resolve().parents[1]


def build(smoke: bool) -> Path:
    src, expected = SOURCES[smoke]
    if hashlib.sha256(src.read_bytes()).hexdigest() != expected:
        raise RuntimeError("Pinned baseline changed")
    nb = json.loads(src.read_text())
    package = _source(nb["cells"][6])
    for name in ("scene.py", "duck_scene_adapter.py"):
        package += f"\n(_memory_package / {name!r}).write_text({(ROOT / 'arc3' / name).read_text()!r})\n"
    package += "from arc3.duck_scene_adapter import SceneObservationMixin, scene_delivery_problems\n"
    _set_source(nb["cells"][6], package)

    settings = _source(nb["cells"][7])
    settings = _replace_once(settings, "GATE2_TRIAL_SECONDS = 900.0", "GATE2_TRIAL_SECONDS = 600.0")
    settings = _replace_once(settings, "GATE2_CONCURRENCY = 1 if GATE2_COMPARISON_SMOKE else 2", "GATE2_CONCURRENCY = 1 if GATE2_COMPARISON_SMOKE else 3")
    # Renderer telemetry is separate from model-side token usage.
    settings = _replace_once(settings,
        '"memory_commits": int(getattr(self.analyzer, "_memory_commits", 0)),',
        '"scene_observations": int(getattr(self.analyzer, "_scene_observations", 0)),\n'
        '                "scene_chars": int(getattr(self.analyzer, "_scene_chars", 0)),\n'
        '                "scene_delivered_messages": int(getattr(self.analyzer, "_scene_delivered_messages", 0)),\n'
        '                "scene_image_messages": int(getattr(self.analyzer, "_scene_image_messages", 0)),\n'
        '                "scene_text_only_messages": int(getattr(self.analyzer, "_scene_text_only_messages", 0)),\n'
        '                "memory_commits": int(getattr(self.analyzer, "_memory_commits", 0)),')
    settings += '''
# Observe actual message shape at the provider boundary for every arm.
_scene_original_build_message = _Gate2ToolAgent._build_user_message
def _scene_counted_build_message(self, user_prompt, current_frame):
    message = _scene_original_build_message(self, user_prompt, current_frame)
    content = message.get("content", "")
    parts = content if isinstance(content, list) else [{"type": "text", "text": content}]
    has_image = any(p.get("type") == "image_url" for p in parts)
    has_scene = any(p.get("type") == "text" and "SCENE_V1" in str(p.get("text", "")) for p in parts)
    counter = "_scene_image_messages" if has_image else "_scene_text_only_messages"
    setattr(self, counter, int(getattr(self, counter, 0)) + 1)
    if has_scene:
        self._scene_delivered_messages = int(getattr(self, "_scene_delivered_messages", 0)) + 1
    return message
_Gate2ToolAgent._build_user_message = _scene_counted_build_message
'''
    _set_source(nb["cells"][7], settings)

    exp = _source(nb["cells"][8])
    # Resolve the full ID from the pinned public metadata.
    public_ids = ast.literal_eval(exp.split("PUBLIC_GAME_IDS = ", 1)[1].split("\nGATE2_GAME_IDS", 1)[0].strip())
    re86 = [gid for gid in public_ids if gid.startswith("re86-")]
    if len(re86) != 1:
        raise RuntimeError("Cannot resolve re86 from pinned public metadata")
    exp = _replace_once(exp, 'GATE2_GAME_IDS = ("cd82-fb555c5d", "ka59-38d34dbb")',
        f'GATE2_GAME_IDS = ("cd82-fb555c5d", "ka59-38d34dbb", {re86[0]!r})')
    exp = _replace_once(exp,
        '{"trial_id": "M", "replicate": 0, "arm": "M", "cap": 0, "seed": GATE2_SEEDS[0]},',
        '{"trial_id": "C", "replicate": 0, "arm": "C", "cap": 0, "seed": GATE2_SEEDS[0]},\n'
        '    {"trial_id": "T", "replicate": 0, "arm": "T", "cap": 0, "seed": GATE2_SEEDS[0]},')
    exp = _replace_once(exp, "def _gate2_make_analyzer_factory(spec, solver):",
        "class _SceneToolAgent(SceneObservationMixin, _Gate2ToolAgent):\n    pass\n\n\n"
        "def _gate2_make_analyzer_factory(spec, solver):")
    exp = _replace_once(exp, "analyzer_cls = _MemoryToolAgent if spec['arm'] == 'M' else _Gate2ToolAgent",
        "analyzer_cls = _SceneToolAgent if spec['arm'] in ('C', 'T') else _Gate2ToolAgent")
    exp = _replace_once(exp,
        '    trial_id = spec["trial_id"]\n    _gate2_tool_agent_module._LOCAL_ANALYZER_MAX_OUTPUT',
        '    trial_id = spec["trial_id"]\n'
        '    _gate2_os.environ["MULTIMODAL_CONTEXT"] = "" if spec["arm"] == "T" else "current_grid"\n'
        '    print(f"SCENE_MODE_ACTIVE arm={spec[\'arm\']} image={spec[\'arm\'] != \'T\'} scene={spec[\'arm\'] in (\'C\', \'T\')}", flush=True)\n'
        '    _gate2_tool_agent_module._LOCAL_ANALYZER_MAX_OUTPUT')
    exp = _replace_once(exp,
        '"memory_commits": int(session.get("memory_commits", 0)),',
        '"scene_observations": int(session.get("scene_observations", 0)),\n'
        '        "scene_chars": int(session.get("scene_chars", 0)),\n'
        '        "scene_delivered_messages": int(session.get("scene_delivered_messages", 0)),\n'
        '        "scene_image_messages": int(session.get("scene_image_messages", 0)),\n'
        '        "scene_text_only_messages": int(session.get("scene_text_only_messages", 0)),\n'
        '        "memory_commits": int(session.get("memory_commits", 0)),')
    _set_source(nb["cells"][8], exp)

    audit = _source(nb["cells"][9])
    audit = _replace_once(audit, 'for arm in ("W", "W-repeat", "M")', 'for arm in ("W", "W-repeat", "C", "T")')
    audit = _replace_once(audit, '_mem_clean = bool(',
        '_scene_delivery_errors = scene_delivery_problems(_mem_rows)\n'
        'print("SCENE_DELIVERY_ERRORS " + _mem_json.dumps(_scene_delivery_errors), flush=True)\n'
        '_mem_clean = bool(\n    not _scene_delivery_errors and')
    _set_source(nb["cells"][9], audit.replace("MEMORY_", "SCENE_"))
    nb["cells"][0]["source"] = ["# ARC3 complete scene screen\n", "Private development run. W/image, C/image+scene, T/scene-only, W-repeat/image.\n"]
    for i, cell in enumerate(nb["cells"]):
        if cell["cell_type"] == "code":
            clean = "\n".join("" if line.lstrip().startswith(("!", "%", "?")) else line for line in _source(cell).splitlines())
            ast.parse(clean, filename=f"cell_{i}")
    kind = "smoke" if smoke else "screen"
    out = ROOT / f"notebooks/scene-{kind}/arc3-scene-{kind}.ipynb"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(nb, indent=1) + "\n")
    meta = json.loads((ROOT / "notebooks/text-only-screen/kernel-metadata.json").read_text())
    meta.update(id=f"anandsingh8687/arc3-scene-{kind}-20260917", title=f"ARC3 Scene {kind.title()} 20260917", code_file=out.name)
    (out.parent / "kernel-metadata.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"BUILT {out}")
    return out


if __name__ == "__main__":
    build(True)
    build(False)

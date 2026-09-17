#!/usr/bin/env python3
"""Build one private GPT-OSS lifecycle smoke from the tested scene chassis.

This is not a scored submission or a capability comparison. It deliberately
generates no long-run notebook.
"""
from __future__ import annotations

import ast
import gzip
import hashlib
import json
from pathlib import Path

from build_text_only_screen_notebook import _source, _set_source, _replace_once

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "notebooks/scene-smoke/arc3-scene-smoke.ipynb"
SOURCE_SHA256 = "05171df4c872cbb251b998f0221fab2cdd8e4318b36021a8e2814e2b43ea3adf"
HARMONY_VOCAB = ROOT / "research/assets/gptoss/o200k_base.tiktoken.gz"
HARMONY_VOCAB_SHA256 = "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"
HARMONY_CACHE_KEY = "fb374d419588a4632f3f557e76b4b70aebbca790"
HARMONY_DATASET = "anandsingh8687/arc3-harmony-vocab-20260917"


def vocab_bootstrap_source() -> str:
    """Load the hash-pinned vocabulary from a private offline Kaggle input.

    SaveKernel rejects source >= 1 MB, so the vocabulary must not be inlined.
    The content hash, rather than the dataset's mutable latest pointer, pins it.
    """
    compressed = HARMONY_VOCAB.read_bytes()
    raw = gzip.decompress(compressed)
    if len(raw) != 3613922 or hashlib.sha256(raw).hexdigest() != HARMONY_VOCAB_SHA256:
        raise RuntimeError("Pinned Harmony vocabulary changed")
    return f'''
# Harmony's Rust tokenizer has its own cache, separate from Hugging Face.
import gzip as _vocab_gzip, hashlib as _vocab_hashlib
_gptoss_vocab_input_paths = _dataset_mount_candidates({HARMONY_DATASET!r})
_gptoss_vocab_source = next((p / name for p in _gptoss_vocab_input_paths
                            for name in ("o200k_base.tiktoken", "o200k_base.tiktoken.gz")
                            if (p / name).is_file()), None)
if _gptoss_vocab_source is None:
    raise RuntimeError("Pinned offline Harmony vocabulary input is missing")
_gptoss_vocab_bytes = _gptoss_vocab_source.read_bytes()
if _gptoss_vocab_source.suffix == ".gz":
    _gptoss_vocab_bytes = _vocab_gzip.decompress(_gptoss_vocab_bytes)
if (len(_gptoss_vocab_bytes) != 3613922 or
    _vocab_hashlib.sha256(_gptoss_vocab_bytes).hexdigest() != {HARMONY_VOCAB_SHA256!r}):
    raise RuntimeError("Offline Harmony vocabulary failed checksum")
_gptoss_vocab_dir = WORKING_DIR / "gptoss-harmony-cache"
_gptoss_vocab_dir.mkdir(parents=True, exist_ok=True)
(_gptoss_vocab_dir / {HARMONY_CACHE_KEY!r}).write_bytes(_gptoss_vocab_bytes)
del _gptoss_vocab_bytes
'''


def build() -> Path:
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("Pinned scene smoke changed")
    nb = json.loads(SOURCE.read_text())
    nb["cells"][0]["source"] = [
        "# GPT-OSS-120B native-tool lifecycle smoke\n",
        "Private development only. One game, 60 seconds after model readiness. No competition submission.\n",
    ]

    setup = _source(nb["cells"][1])
    start = setup.index("# Gate 1 safe baseline:")
    end = setup.index("# Pin arc_agi", start)
    setup = setup[:start] + '''# Model identity is checked by the offline runtime helper.
if TRUE_SUBMISSION:
    raise RuntimeError("Private GPT-OSS smoke must never be submitted")
os.environ["MULTIMODAL_CONTEXT"] = ""
''' + setup[end:]
    _set_source(nb["cells"][1], setup)

    bootstrap = _source(nb["cells"][4])
    start = bootstrap.index("# Solver setup commands")
    bootstrap = bootstrap[:start] + vocab_bootstrap_source() + f'''
# Reuse the pinned offline runtime extraction, not Qwen's model launcher.
_gptoss_module_dir = WORKING_DIR / "gptoss-runtime"
_gptoss_module_dir.mkdir(exist_ok=True)
(_gptoss_module_dir / "gptoss_runtime.py").write_text({(ROOT / 'research/gptoss_runtime.py').read_text()!r})
sys.path.insert(0, str(_gptoss_module_dir))
import gptoss_runtime
_gptoss_start = gptoss_runtime.start_server(BUNDLE_DIR, WORKING_DIR, timeout_seconds=900)
os.environ.update(_gptoss_start["environment"])
GATE1_SERVER_READY_EPOCH = float(_gptoss_start["server_ready_epoch"])
GATE1_SERVER_STARTUP_SECONDS = GATE1_SERVER_READY_EPOCH - NOTEBOOK_START_EPOCH
# In-process cleanup for later cell failures; Kaggle's 1200s run limit is the
# external bound if the notebook kernel itself disappears.
_gptoss_watchdog = gptoss_runtime.arm_shutdown_watchdog(
    WORKING_DIR, GATE1_SERVER_READY_EPOCH + 300.0)
print("GATE1_SERVER_READY " + json.dumps({{
    "epoch": GATE1_SERVER_READY_EPOCH,
    "startup_seconds": GATE1_SERVER_STARTUP_SECONDS,
    "model": os.environ["LOCAL_ANALYZER_MODEL_ID"],
}}), flush=True)
'''
    _set_source(nb["cells"][4], bootstrap)

    package = _source(nb["cells"][6])
    package += f"\n(_memory_package / 'duck_gptoss_adapter.py').write_text({(ROOT / 'arc3/duck_gptoss_adapter.py').read_text()!r})\n"
    package += "from arc3.duck_gptoss_adapter import GPTOSSNativeFunctionMixin\n"
    _set_source(nb["cells"][6], package)

    settings = _source(nb["cells"][7])
    settings = _replace_once(settings,
        'from inference.agent.tool_agent import ToolAgent as _Gate2ToolAgent',
        'from inference.agent.tool_agent import ToolAgent as _Gate2ToolAgent\n\n'
        'class _GptOssToolAgent(GPTOSSNativeFunctionMixin, SceneObservationMixin, _Gate2ToolAgent):\n'
        '    pass\n')
    # Instrument the concrete override, not the base method it bypasses.
    settings = settings.replace('_Gate2ToolAgent._chat_completion', '_GptOssToolAgent._chat_completion')
    settings = settings.replace('getattr(_Gate2ToolAgent, "_gate2_call_counter_installed"',
                                'getattr(_GptOssToolAgent, "_gate2_call_counter_installed"')
    settings = settings.replace('_Gate2ToolAgent._gate2_call_counter_installed',
                                '_GptOssToolAgent._gate2_call_counter_installed')
    settings = settings.replace('_Gate2ToolAgent._build_user_message', '_GptOssToolAgent._build_user_message')
    settings = settings.replace('# Gate 2 paired response-cap experiment. Serving is unchanged from passing Version 11.',
                                '# GPT-OSS lifecycle smoke; all previous Qwen smoke approvals are invalid for this model.')
    _set_source(nb["cells"][7], settings)

    exp = _source(nb["cells"][8])
    exp = _replace_once(exp,
        'GATE2_GAME_IDS = ("cd82-fb555c5d", "ka59-38d34dbb", \'re86-8af5384d\')',
        'GATE2_GAME_IDS = ("r11l-495a7899",)')
    start = exp.index('_gate2_trial_specs = [')
    end = exp.index('\nprint(', start)
    exp = exp[:start] + '''_gate2_trial_specs = [
    {"trial_id": "G", "replicate": 0, "arm": "G", "cap": 0, "seed": GATE2_SEEDS[0]},
]
''' + exp[end:]
    exp = _replace_once(exp,
        "analyzer_cls = _SceneToolAgent if spec['arm'] in ('C', 'T') else _Gate2ToolAgent",
        "analyzer_cls = _GptOssToolAgent")
    exp = _replace_once(exp, 'model=solver.model,', 'model=os.environ["LOCAL_ANALYZER_MODEL_ID"],')
    exp = _replace_once(exp,
        '        analyzer._gate2_game_id = getattr(game, "env_name", str(index))',
        '        analyzer._gate2_game_id = getattr(game, "env_name", str(index))\n'
        '        analyzer._gptoss_audit_path = (_GATE2_ROOT / trial_id / "http" / f"{analyzer._gate2_game_id}.jsonl")')
    exp = _replace_once(exp,
        '_gate2_os.environ["MULTIMODAL_CONTEXT"] = "" if spec["arm"] == "T" else "current_grid"',
        '_gate2_os.environ["MULTIMODAL_CONTEXT"] = ""')
    exp = _replace_once(exp,
        'print(f"SCENE_MODE_ACTIVE arm={spec[\'arm\']} image={spec[\'arm\'] != \'T\'} scene={spec[\'arm\'] in (\'C\', \'T\')}", flush=True)',
        'print("GPTOSS_MODE_ACTIVE image=false scene=true native_tools=true", flush=True)')
    # The Qwen watchdog must not restart this model with Qwen flags.
    start = exp.index('if str(BUNDLE_DIR) not in sys.path:')
    end = exp.index('\nif GATE2_COMPARISON_SMOKE:', start)
    exp = exp[:start] + exp[end:]
    start = exp.index('def _gate2_proc_start_ticks(pid):')
    end = exp.index('def _gate2_make_trial_benchmark(spec):', start)
    exp = exp[:start] + '''def _gate2_teardown_with_recovery():
    result = gptoss_runtime.stop_server(WORKING_DIR)
    _gate2_teardown_attempts.append(result)
    return bool(result.get("shutdown_ok")), result, result.get("post_gpu_rows", [])


def _gate2_gpu_rows():
    # Error means unknown, never silently clean.
    return gptoss_runtime.gpu_rows()


''' + exp[end:]
    start = exp.index('try:\n    vllm_watchdog.stop_background')
    end = exp.index('\ntry:\n    _gate2_teardown_ok', start)
    exp = exp[:start] + exp[end:]
    # Never manufacture a competition file for a pure development smoke.
    start = exp.index('        import pandas as pd')
    end = exp.index('        _gate2_benchmark_ok = True', start)
    exp = exp[:start] + exp[end:]
    _set_source(nb["cells"][8], exp)

    audit = '''# A lifecycle pass does not measure an improvement in ARC score.
rows = _gate2_write_progress_index()
problems = []
request_count = response_count = 0
for row in rows:
    label = row["game_id"]
    counts = [int(row.get(k, 0)) for k in (
        "scene_observations", "scene_delivered_messages", "scene_text_only_messages")]
    if not (counts[0] > 0 and counts[0] == counts[1] == counts[2]):
        problems.append(f"{label}: incomplete scene/text delivery {counts}")
    if int(row.get("scene_image_messages", 0)) != 0:
        problems.append(f"{label}: unexpected image payload")
    if int(row.get("llm_calls", 0)) <= 0 or int(row.get("actions_taken", 0)) <= 0:
        problems.append(f"{label}: no instrumented model calls or real actions")
    audit_path = _GATE2_ROOT / "G" / "http" / f"{label}.jsonl"
    events = [json.loads(line) for line in audit_path.read_text().splitlines()] if audit_path.exists() else []
    requests = [e for e in events if e["event"] == "request"]
    responses = [e for e in events if e["event"] == "response"]
    request_count += len(requests)
    response_count += len(responses)
    if len(requests) != int(row.get("llm_calls", 0)) or not responses:
        problems.append(f"{label}: missing provider-boundary request/response evidence")
    for event in requests:
        payload = event["payload"]
        messages = payload.get("messages", [])
        text_only = all(m.get("content") is None or isinstance(m.get("content"), str) for m in messages)
        scene_present = any(m.get("role") == "user" and "SCENE_V1" in (m.get("content") or "") for m in messages)
        tools = [t.get("function", {}).get("name") for t in payload.get("tools", [])]
        if not (text_only and scene_present and "python" in tools
                and payload.get("model") == os.environ["LOCAL_ANALYZER_MODEL_ID"]
                and payload.get("seed") == GATE2_SEEDS[0]
                and payload.get("reasoning_effort") == "high"
                and payload.get("tool_choice") == "auto"
                and payload.get("ignore_eos") is False
                and "top_k" not in payload and "chat_template_kwargs" not in payload):
            problems.append(f"{label}: invalid native provider request {event['sequence']}")
    print("GPTOSS_GAME " + json.dumps(row, sort_keys=True), flush=True)
clean = bool(not problems and _gate2_benchmark_ok and _gate2_teardown_ok
             and not _gate2_hard_guard_triggered and _gate2_completed_trials == ["G"]
             and len(rows) == 1 and all(r.get("terminal") for r in rows)
             and not _gate2_post_gpu_rows)
final = {"smoke": True, "clean": clean, "problems": problems,
         "http_requests": request_count, "http_responses": response_count,
         "benchmark_ok": _gate2_benchmark_ok, "teardown_ok": _gate2_teardown_ok,
         "completed_trials": _gate2_completed_trials, "score_claim": None}
_gate2_atomic_json(WORKING_DIR / "gptoss-smoke-final.json", final)
print("GPTOSS_SMOKE_FINAL " + json.dumps(final, sort_keys=True), flush=True)
print("GPTOSS_SMOKE_OK" if clean else "GPTOSS_SMOKE_FAILED", flush=True)
if not clean:
    raise RuntimeError("GPT-OSS lifecycle smoke failed; results preserved")
'''
    _set_source(nb["cells"][9], audit)
    for index, cell in enumerate(nb["cells"]):
        if cell["cell_type"] == "code":
            ast.parse(_source(cell), filename=f"cell_{index}")
            cell["outputs"] = []
            cell["execution_count"] = None
    out = ROOT / "notebooks/gptoss-smoke/arc3-gptoss-smoke.ipynb"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(nb, indent=1) + "\n")
    if out.stat().st_size >= 1_000_000:
        raise RuntimeError("Kaggle notebook source must be below the 1 MB upload limit")
    meta = json.loads((SOURCE.parent / "kernel-metadata.json").read_text())
    meta.update(id="anandsingh8687/arc3-gptoss-smoke-20260917",
                title="ARC3 GPTOSS Smoke 20260917", code_file=out.name,
                model_sources=["danielhanchen/gpt-oss-120b/Transformers/default/1"])
    meta["dataset_sources"] = list(dict.fromkeys(meta["dataset_sources"] + [HARMONY_DATASET]))
    (out.parent / "kernel-metadata.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"BUILT {out}")
    return out


if __name__ == "__main__":
    build()

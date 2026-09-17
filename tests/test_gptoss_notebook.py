"""Generated notebook gates: validate the concrete wiring, not just the mixin."""
import ast
import hashlib
import importlib.util
import json
import shutil
import sys
import pytest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _build():
    research = ROOT / "research"
    sys.path.insert(0, str(research))
    try:
        spec = importlib.util.spec_from_file_location(
            "gptoss_builder_test", research / "build_gptoss_smoke_notebook.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.build()
    finally:
        sys.path.remove(str(research))


def test_generated_smoke_has_native_model_and_no_qwen_lifecycle():
    path = _build()
    nb = json.loads(path.read_text())
    code = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    for i, source in enumerate(code):
        ast.parse(source, filename=f"cell_{i}")
    setup, settings, run, audit = code[0], code[6], code[7], code[8]
    assert "must never be submitted" in setup
    assert "PUBLIC25_VLLM_PROFILE" not in setup
    assert "_GptOssToolAgent._chat_completion = _gate2_counted_chat_completion" in settings
    assert "_GptOssToolAgent._build_user_message = _scene_counted_build_message" in settings
    assert "analyzer_cls = _GptOssToolAgent" in run
    assert 'model=os.environ["LOCAL_ANALYZER_MODEL_ID"]' in run
    assert "vllm_watchdog" not in run
    assert "teardown_commands.json" not in run
    assert "submission.parquet" not in run
    assert '"r11l-495a7899",)' in run
    assert "gptoss_runtime.stop_server(WORKING_DIR)" in run
    assert "raise RuntimeError" in audit
    assert '"score_claim": None' in audit
    assert 'payload.get("tool_choice") == "auto"' in audit
    assert 'payload.get("ignore_eos") is False' in audit
    assert "counts[0] == counts[1] == counts[2]" in audit
    assert "GATE2_COMPARISON_SMOKE = True" in settings
    assert "GATE2_SMOKE_GAME_SECONDS = 60.0" in settings
    meta = json.loads((path.parent / "kernel-metadata.json").read_text())
    assert meta["is_private"] is True
    assert meta["enable_internet"] is False
    assert meta["model_sources"] == ["danielhanchen/gpt-oss-120b/Transformers/default/1"]
    assert "anandsingh8687/arc3-harmony-vocab-20260917" in meta["dataset_sources"]
    assert path.stat().st_size < 1_000_000
    bootstrap = "".join(nb["cells"][4]["source"])
    assert bootstrap.index('gptoss-harmony-cache') < bootstrap.index('gptoss_runtime.start_server(')


def test_smoke_has_exactly_one_trial_and_no_result_dependent_expansion():
    path = _build()
    nb = json.loads(path.read_text())
    run = "".join(nb["cells"][8]["source"])
    tree = ast.parse(run)
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "_gate2_trial_specs"
                           for t in node.targets)]
    assert len(assignments) == 1
    value = assignments[0].value
    assert isinstance(value, ast.List) and len(value.elts) == 1
    assert "_gate2_trial_specs.append" not in run


def _vocab_source():
    path = _build()
    nb = json.loads(path.read_text())
    bootstrap = "".join(nb["cells"][4]["source"])
    start = bootstrap.index("# Harmony's Rust tokenizer")
    end = bootstrap.index("# Reuse the pinned offline runtime extraction", start)
    return compile(bootstrap[start:end], "vocab-bootstrap", "exec")


@pytest.mark.parametrize("compressed", [True, False])
def test_offline_vocab_roundtrips_to_exact_official_cache_file(tmp_path, compressed):
    import gzip
    inputs = tmp_path / "input"
    inputs.mkdir()
    asset = ROOT / "research/assets/gptoss/o200k_base.tiktoken.gz"
    if compressed:
        shutil.copyfile(asset, inputs / "o200k_base.tiktoken.gz")
    else:
        (inputs / "o200k_base.tiktoken").write_bytes(gzip.decompress(asset.read_bytes()))
    exec(_vocab_source(), {"WORKING_DIR": tmp_path,
                          "_dataset_mount_candidates": lambda ref: [inputs]})
    cached = tmp_path / "gptoss-harmony-cache/fb374d419588a4632f3f557e76b4b70aebbca790"
    raw = cached.read_bytes()
    assert len(raw) == 3613922
    assert hashlib.sha256(raw).hexdigest() == "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"


def test_offline_vocab_missing_fails_before_startup(tmp_path):
    with pytest.raises(RuntimeError, match="input is missing"):
        exec(_vocab_source(), {"WORKING_DIR": tmp_path,
                              "_dataset_mount_candidates": lambda ref: [tmp_path / "missing"]})
    assert not (tmp_path / "gptoss-harmony-cache").exists()


def test_offline_vocab_corrupt_fails_before_cache_write(tmp_path):
    import gzip
    (tmp_path / "o200k_base.tiktoken.gz").write_bytes(gzip.compress(b"wrong vocabulary"))
    with pytest.raises(RuntimeError, match="failed checksum"):
        exec(_vocab_source(), {"WORKING_DIR": tmp_path,
                              "_dataset_mount_candidates": lambda ref: [tmp_path]})
    assert not (tmp_path / "gptoss-harmony-cache").exists()

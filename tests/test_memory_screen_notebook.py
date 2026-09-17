"""Pin the Kaggle smoke's process-drain and attached-model contracts."""

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _experiment_source() -> str:
    notebook = json.loads((ROOT / "notebooks/arc3-memory-screen-smoke.ipynb").read_text())
    matches = [
        "".join(cell["source"])
        for cell in notebook["cells"]
        if "_gate2_terminal_gate_after_drain" in "".join(cell["source"])
    ]
    assert len(matches) == 1
    return matches[0]


def test_unresolved_nvidia_row_is_not_treated_as_a_clean_exit():
    source = _experiment_source()
    function = next(
        node for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_gate2_terminal_gate_after_drain"
    )
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "<teardown>", "exec"), namespace)
    evidence = {
        "identity_valid": True,
        "final_metrics_preserved": True,
        "required_artifacts_preserved": True,
        "vllm_gpu_rows_after": [{"pid": 238, "start_ticks": 46754}],
    }
    process = {"port_closed": True, "process_scan_final_gate": {}}

    ok, details = namespace["_gate2_terminal_gate_after_drain"](
        evidence, process, [{"pid": 238, "start_ticks": None}]
    )

    assert ok is False
    assert details["checks"]["no_owned_gpu_survivors"] is False
    assert "or row.get(\"start_ticks\") is None" in source


def test_smoke_metadata_attaches_the_checkpoint_required_by_serving_setup():
    metadata = json.loads((ROOT / "notebooks/kernel-metadata.json").read_text())
    assert metadata["is_private"] is True
    assert metadata["machine_shape"] == "NvidiaRtxPro6000"
    assert metadata["competition_sources"] == ["arc-prize-2026-arc-agi-3"]
    assert metadata["model_sources"] == [
        "keithtyser/qwen3-8-flash-next-nvfp4/PyTorch/radixark-modelopt-fp4/1"
    ]


def test_depth_screen_is_private_and_uses_the_same_model_and_runtime():
    smoke = json.loads((ROOT / "notebooks/kernel-metadata.json").read_text())
    screen = json.loads((ROOT / "notebooks/memory-screen-kernel-metadata.json").read_text())
    assert screen["id"] != smoke["id"]
    assert screen["code_file"] == "arc3-memory-screen.ipynb"
    for field in ("is_private", "machine_shape", "docker_image", "model_sources",
                  "dataset_sources", "competition_sources", "enable_internet"):
        assert screen[field] == smoke[field]

    notebook = json.loads((ROOT / "notebooks/arc3-memory-screen.ipynb").read_text())
    sources = ["".join(cell["source"]) for cell in notebook["cells"]]
    assert "GATE2_COMPARISON_SMOKE = False" in sources[7]
    assert "GATE2_TRIAL_SECONDS = 900.0" in sources[7]
    assert 'GATE2_GAME_IDS = ("cd82-fb555c5d", "ka59-38d34dbb")' in sources[8]
    assert '"trial_id": "W-repeat"' in sources[8]
    assert "MEMORY_SCREEN_OK" in sources[9]

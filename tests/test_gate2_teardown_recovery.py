import ast
import importlib.util
import json
from pathlib import Path


_BUILDER_PATH = (
    Path(__file__).resolve().parents[1] / "research" / "build_gate2_comparison_notebook.py"
)
_SPEC = importlib.util.spec_from_file_location("gate2_notebook_builder", _BUILDER_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BUILDER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BUILDER)
SOURCE = _BUILDER.SOURCE
_gate2_terminal_gate_after_drain = _BUILDER._gate2_terminal_gate_after_drain
teardown_helpers = _BUILDER.teardown_helpers


def _evidence(**overrides):
    value = {
        "identity_valid": True,
        "final_metrics_preserved": True,
        "required_artifacts_preserved": True,
        "port_closed": True,
        "vllm_gpu_rows_after": [{"pid": 238, "start_ticks": 764474}],
        "process_scan_final_gate": {
            "root_conflict": False,
            "saved_conflicts": [],
            "authorized_records": [],
            "suspect_records": [],
        },
        "full_proc_marker_survivors": [],
        "cpu_only_vllm_ple_marker_survivors": [],
    }
    value.update(overrides)
    return value


def test_accepts_preserved_evidence_after_owned_gpu_process_drains():
    evidence = _evidence()

    ok, details = _gate2_terminal_gate_after_drain(evidence, evidence, [])

    assert ok is True
    assert details["owned_pids"] == [238]
    assert details["post_owned"] == []
    assert all(details["checks"].values())


def test_rejects_missing_live_metrics_even_after_process_drains():
    evidence = _evidence(final_metrics_preserved=False)

    ok, details = _gate2_terminal_gate_after_drain(evidence, evidence, [])

    assert ok is False
    assert details["checks"]["final_metrics_preserved"] is False


def test_rejects_cpu_or_exact_gpu_survivors():
    evidence = _evidence()
    cpu_process = _evidence(
        process_scan_final_gate={
            "root_conflict": False,
            "saved_conflicts": [],
            "authorized_records": [{"pid": 238}],
            "suspect_records": [],
        }
    )

    cpu_ok, cpu_details = _gate2_terminal_gate_after_drain(evidence, cpu_process, [])
    gpu_ok, gpu_details = _gate2_terminal_gate_after_drain(
        evidence,
        evidence,
        [{"pid": 238, "start_ticks": 764474}],
    )

    assert cpu_ok is False
    assert cpu_details["checks"]["no_cpu_survivors"] is False
    assert gpu_ok is False
    assert gpu_details["checks"]["no_owned_gpu_survivors"] is False


def test_rejects_gpu_query_errors():
    evidence = _evidence()

    ok, details = _gate2_terminal_gate_after_drain(
        evidence,
        evidence,
        [{"query_error": "nvidia-smi timed out"}],
    )

    assert ok is False
    assert details["checks"]["gpu_query_succeeded"] is False


def test_generated_helpers_replace_the_stale_second_teardown_gate():
    notebook = json.loads(SOURCE.read_text())

    source = teardown_helpers(notebook)

    ast.parse(source)
    assert source.count("def _gate2_teardown_with_recovery") == 1
    assert "GATE2_TEARDOWN_RECOVERED" in source
    assert "terminal_gate_recovered_after_gpu_drain" in source
    assert "GATE1_GPU_DRAIN" not in source

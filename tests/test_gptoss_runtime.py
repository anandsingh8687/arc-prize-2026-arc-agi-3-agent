import io
import json
import os
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

from research import gptoss_runtime as runtime


def _identity(pid=54321, ticks=87654):
    return {
        "schema_version": 1,
        "backend": "vllm",
        "model_name": runtime.MODEL_NAME,
        "boot_id": "boot",
        "host": runtime.HOST,
        "port": runtime.PORT,
        "pid": pid,
        "start_ticks": ticks,
        "pgid": pid,
        "sid": pid,
        "argv": ["python"],
        "argv_sha256": "argv",
        "started_epoch": 1.0,
        "phase": "ready",
        "server_ready_epoch": 2.0,
    }


def _worker(pid, ticks, pgid, sid, argv_sha256):
    return {"pid": pid, "start_ticks": ticks, "pgid": pgid, "sid": sid, "argv_sha256": argv_sha256}


def _identity_with_child():
    identity = _identity(pid=100, ticks=10)
    identity.update({"boot_id": "boot", "pgid": 100, "sid": 100, "argv_sha256": "root", "workers": [_worker(100, 10, 100, 100, "root"), _worker(200, 20, 100, 100, "child")], "worker_snapshot_epoch": 3.0})
    return identity


def test_command_is_native_gptoss_without_qwen_or_quantization_overrides():
    command = runtime.server_command(Path("/model"))

    assert ["--tool-call-parser", "openai"] == command[command.index("--tool-call-parser") : command.index("--tool-call-parser") + 2]
    assert "--enable-auto-tool-choice" in command
    assert "--enforce-eager" in command
    assert "--enable-prefix-caching" in command
    assert "--quantization" not in command
    assert "--chat-template" not in command
    assert "--speculative-config" not in command
    assert not any("qwen" in item.lower() or "mtp" in item.lower() for item in command)


def test_model_attachment_requires_exact_path_and_model_type(tmp_path):
    model = tmp_path / "gpt-oss-120b" / "Transformers" / "default" / "1"
    model.mkdir(parents=True)
    (model / "config.json").write_text(json.dumps({"model_type": "gpt_oss"}), encoding="utf-8")

    provenance = runtime._validate_model_dir(model)

    assert provenance["model_type"] == "gpt_oss"
    (model / "config.json").write_text(json.dumps({"model_type": "qwen3"}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="model_type"):
        runtime._validate_model_dir(model)


def test_model_candidates_include_kaggle_lowercase_transformers_mount():
    candidates = [str(path) for path in runtime._model_candidates()]

    assert any(path.endswith("/gpt-oss-120b/transformers/default/1") for path in candidates)


def test_derived_environment_removes_qwen_ple_and_prioritizes_cuda13_libcudart(tmp_path, monkeypatch):
    root = tmp_path / "runtime"
    site = root / "usr/local/lib/python3.12/dist-packages"
    cuda = root / "usr/local/cuda-13.0"
    cutlass = site / "nvidia_cutlass_dsl/dsl_packages"
    for path in (site / "vllm", site / "torch", cuda / "bin", cuda / "targets/x86_64-linux/lib", cutlass / "cutlass"):
        path.mkdir(parents=True, exist_ok=True)
    for path in (site / "vllm/__init__.py", site / "torch/__init__.py", cuda / "bin/nvcc", cuda / "targets/x86_64-linux/lib/libcudart.so", cutlass / "cutlass/__init__.py"):
        path.write_text("", encoding="utf-8")
    monkeypatch.setenv("VLLM_RADIXARK_QWEN38_NVFP4_PLE_FP8", "1")
    monkeypatch.setenv("SOME_QWEN_SETTING", "bad")

    env, provenance = runtime._runtime_environment(root, tmp_path / "working")

    assert not any("QWEN" in key or "PLE" in key or "RADIXARK" in key for key in env)
    assert env["MODEL_NAME"] == runtime.MODEL_NAME
    assert env["LOCAL_ANALYZER_MODEL_ID"] == runtime.MODEL_NAME
    assert env["LD_LIBRARY_PATH"].split(os.pathsep)[0] == str(cuda / "targets/x86_64-linux/lib")
    assert env["LIBRARY_PATH"].split(os.pathsep)[0] == str(cuda / "targets/x86_64-linux/lib")
    assert env["PYTHONPATH"].split(os.pathsep)[:2] == [str(cutlass), str(site)]
    assert provenance["cuda13_libcudart"].endswith("libcudart.so")


@pytest.mark.parametrize("contents, error", [(None, FileNotFoundError), (b"wrong", RuntimeError)])
def test_harmony_cache_requires_exact_offline_asset(tmp_path, monkeypatch, contents, error):
    cache = tmp_path / runtime.HARMONY_CACHE_DIRNAME
    cache.mkdir()
    if contents is not None:
        (cache / runtime.HARMONY_TIKTOKEN_CACHE_KEY).write_bytes(contents)
    monkeypatch.setattr(runtime, "HARMONY_VOCAB_BYTES", 5)
    monkeypatch.setattr(runtime, "HARMONY_VOCAB_SHA256", "0" * 64)
    env = {"TIKTOKEN_ENCODINGS_BASE": "/stale"}

    with pytest.raises(error):
        runtime._prepare_harmony_cache(tmp_path, env)

    assert "TIKTOKEN_RS_CACHE_DIR" not in env


def test_harmony_cpu_preflight_uses_runtime_env_and_remaining_bounded_timeout(tmp_path, monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(stdout=json.dumps({"harmony_version": "0.0.8", "token_count": 14}))

    monkeypatch.setattr(runtime.subprocess, "run", run)
    monkeypatch.setattr(runtime.time, "monotonic", lambda: 100.0)
    env = {"TIKTOKEN_RS_CACHE_DIR": "/exact-cache", "PYTHONPATH": "/runtime/site"}

    report = runtime._run_harmony_preflight(env, tmp_path / "preflight.json", deadline=150.0)

    assert calls[0][0] == [runtime.sys.executable, "-c", runtime._HARMONY_PREFLIGHT_SOURCE]
    assert calls[0][1]["env"] is env
    assert calls[0][1]["timeout"] == runtime.HARMONY_PREFLIGHT_MAX_SECONDS
    assert report == {"phase": "passed", "timeout_seconds": 20.0, "harmony_version": "0.0.8", "token_count": 14}
    assert runtime._json_read(tmp_path / "preflight.json") == report


@pytest.mark.parametrize("contents, error", [(None, FileNotFoundError), (b"wrong", RuntimeError)])
def test_invalid_harmony_asset_fails_before_popen_and_keeps_failure_evidence(tmp_path, monkeypatch, contents, error):
    class Setup:
        VLLM_RUNTIME_MANIFEST_SHA256 = runtime.BOOTSTRAP_RUNTIME_MANIFEST_SHA256
        VLLM_VERSION = runtime.BOOTSTRAP_VLLM_VERSION
        RUNTIME_ROOT = tmp_path / "runtime"

        @staticmethod
        def resolve_runtime_dir():
            return tmp_path / "payload"

        @staticmethod
        def verify_and_extract_runtime(*args, **kwargs):
            return {"ok": True}

    popen_calls = []
    if contents is not None:
        cache = tmp_path / "working" / runtime.HARMONY_CACHE_DIRNAME
        cache.mkdir(parents=True)
        (cache / runtime.HARMONY_TIKTOKEN_CACHE_KEY).write_bytes(contents)
        monkeypatch.setattr(runtime, "HARMONY_VOCAB_BYTES", len(contents))
        monkeypatch.setattr(runtime, "HARMONY_VOCAB_SHA256", "0" * 64)
    monkeypatch.setattr(runtime, "stop_server", lambda working_dir: {"shutdown_ok": True})
    monkeypatch.setattr(runtime, "_load_bootstrap", lambda bundle, working: (Setup(), tmp_path / "serving_setup.py"))
    monkeypatch.setattr(runtime, "resolve_model_dir", lambda: (tmp_path / "model", {"model_type": "gpt_oss"}))
    monkeypatch.setattr(runtime, "_runtime_environment", lambda root, working: ({}, {"runtime": "verified"}))
    monkeypatch.setattr(runtime.socket, "create_connection", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("closed")))
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *args, **kwargs: popen_calls.append((args, kwargs)))

    with pytest.raises(error, match="Pinned Harmony vocabulary"):
        runtime.start_server(tmp_path, tmp_path / "working")

    assert popen_calls == []
    failure = runtime._json_read(tmp_path / "working" / runtime.STARTUP_FAILURE_FILENAME)
    assert failure["exception_type"] == error.__name__
    assert failure["teardown"] == {"attempted": False, "reason": "process_not_started"}
    assert runtime._json_read(tmp_path / "working" / runtime.PROVENANCE_FILENAME)["phase"] == "failed"


def test_tool_smoke_saves_first_http_failure_without_request_headers(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "_http_bytes", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("HTTP 500")))
    monkeypatch.setattr(runtime.time, "monotonic", lambda: 0.0)

    with pytest.raises(RuntimeError, match="HTTP 500"):
        runtime._tool_smoke(10.0, tmp_path / "tool-smoke.json")

    saved = runtime._json_read(tmp_path / "tool-smoke.json")
    assert saved["first_request"]["model"] == runtime.MODEL_NAME
    assert saved["first_error"] == {"type": "RuntimeError", "message": "HTTP 500"}
    assert "headers" not in saved


def test_tool_smoke_uses_auto_eos_and_preserves_reasoning_content(tmp_path, monkeypatch):
    calls = []
    responses = [
        {"choices": [{"message": {"reasoning": "inspect", "reasoning_content": "inspect details", "tool_calls": [{"id": "call-4", "type": "function", "function": {"name": "submit_number", "arguments": "{\"value\": 4}"}}]}}]},
        {"choices": [{"message": {"content": "accepted"}}]},
    ]

    def http_bytes(url, timeout, payload):
        calls.append(payload)
        return json.dumps(responses.pop(0)).encode("utf-8")

    monkeypatch.setattr(runtime, "_http_bytes", http_bytes)
    runtime._tool_smoke(10.0, tmp_path / "tool-smoke.json")

    assert [payload["tool_choice"] for payload in calls] == ["auto", "auto"]
    assert all(payload["ignore_eos"] is False for payload in calls)
    assert calls[1]["tools"] == calls[0]["tools"]
    assert calls[1]["messages"][1]["reasoning"] == "inspect"
    assert calls[1]["messages"][1]["reasoning_content"] == "inspect details"


@pytest.mark.parametrize(
    ("tool_call", "match"),
    [
        ({"id": "call-4", "function": {"name": "other", "arguments": "{\"value\": 4}"}}, "no submit_number"),
        ({"id": "call-4", "function": {"name": "submit_number", "arguments": "{\"value\": 3}"}}, "wrong arguments"),
        ({"id": "", "function": {"name": "submit_number", "arguments": "{\"value\": 4}"}}, "invalid call ID"),
    ],
)
def test_tool_smoke_rejects_invalid_native_call(tmp_path, monkeypatch, tool_call, match):
    response = {"choices": [{"message": {"tool_calls": [tool_call]}}]}
    monkeypatch.setattr(runtime, "_http_bytes", lambda *args, **kwargs: json.dumps(response).encode("utf-8"))

    with pytest.raises(RuntimeError, match=match):
        runtime._tool_smoke(10.0, tmp_path / "tool-smoke.json")


def test_http_500_body_is_bounded_and_headers_are_not_retained(monkeypatch):
    body = b"server detail " + b"x" * 5000
    error = urllib.error.HTTPError("http://test", 500, "Internal Server Error", {"Authorization": "secret"}, io.BytesIO(body))
    monkeypatch.setattr(runtime.urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(error))

    with pytest.raises(RuntimeError) as raised:
        runtime._http_bytes("http://test", 1.0, {"message": "safe"})

    message = str(raised.value)
    assert "HTTP 500: server detail" in message
    assert "Authorization" not in message
    assert len(message) < 4200


def test_stop_rejects_changed_identity_without_signalling(tmp_path, monkeypatch):
    paths = runtime._server_paths(tmp_path)
    identity = _identity(pid=os.getpid(), ticks=1)  # Deliberately not this process's ticks.
    runtime._json_write(paths["identity"], identity)
    paths["metrics"].write_text("metric 1\n", encoding="utf-8")
    calls = []
    monkeypatch.setattr(runtime.os, "killpg", lambda *args: calls.append(args))
    monkeypatch.setattr(runtime, "_gpu_rows", lambda: ([], True))
    monkeypatch.setattr(runtime, "_boot_id", lambda: "boot")

    result = runtime.stop_server(tmp_path)

    assert result["shutdown_ok"] is False
    assert any(error.startswith("identity_rejected:") for error in result["errors"])
    assert calls == []


def test_stop_fails_closed_when_fresh_gpu_query_fails(tmp_path, monkeypatch):
    paths = runtime._server_paths(tmp_path)
    runtime._json_write(paths["identity"], _identity())
    paths["metrics"].write_text("metric 1\n", encoding="utf-8")
    monkeypatch.setattr(runtime, "_identity_matches", lambda identity: (True, None))
    monkeypatch.setattr(runtime, "_alive_identity", lambda identity: False)
    monkeypatch.setattr(runtime, "_gpu_rows", lambda: ([{"query_error": "timeout"}], False))
    monkeypatch.setattr(runtime.os, "killpg", lambda *args: None)

    result = runtime.stop_server(tmp_path)

    assert result["shutdown_ok"] is False
    assert result["gpu_query_ok"] is False
    assert result["post_gpu_rows"] == [{"query_error": "timeout"}]


def test_repeat_stop_does_not_overwrite_first_success(tmp_path, monkeypatch):
    paths = runtime._server_paths(tmp_path)
    runtime._json_write(paths["identity"], _identity())
    paths["metrics"].write_text("metric 1\n", encoding="utf-8")
    runtime._json_write(paths["teardown"], {"shutdown_ok": True, "metrics_preserved": True, "marker": "first"})
    monkeypatch.setattr(runtime, "_identity_matches", lambda identity: (True, None))
    monkeypatch.setattr(runtime, "_alive_identity", lambda identity: False)
    monkeypatch.setattr(runtime, "_gpu_rows", lambda: ([], True))
    monkeypatch.setattr(runtime.os, "killpg", lambda *args: None)

    result = runtime.stop_server(tmp_path)

    assert result["first_success_preserved"] is True
    assert result["repeated"] is True
    assert runtime._json_read(paths["teardown"])["marker"] == "first"


def test_watchdog_requires_a_short_future_deadline(tmp_path):
    paths = runtime._server_paths(tmp_path)
    runtime._json_write(paths["identity"], _identity())

    with pytest.raises(ValueError, match="within"):
        runtime.arm_shutdown_watchdog(tmp_path, runtime.time.time() + runtime.MAX_WATCHDOG_SECONDS + 1)


def test_start_timeout_budget_includes_runtime_extraction(tmp_path, monkeypatch):
    class Setup:
        VLLM_RUNTIME_MANIFEST_SHA256 = runtime.BOOTSTRAP_RUNTIME_MANIFEST_SHA256
        VLLM_VERSION = runtime.BOOTSTRAP_VLLM_VERSION
        RUNTIME_ROOT = tmp_path / "runtime"

        @staticmethod
        def resolve_runtime_dir():
            return tmp_path / "payload"

        @staticmethod
        def verify_and_extract_runtime(*args, **kwargs):
            return {"ok": True}

    ticks = iter([0.0, 2.0])
    monkeypatch.setattr(runtime, "stop_server", lambda working_dir: {"shutdown_ok": True})
    monkeypatch.setattr(runtime, "_load_bootstrap", lambda bundle, working: (Setup(), tmp_path / "serving_setup.py"))
    monkeypatch.setattr(runtime, "resolve_model_dir", lambda: (tmp_path / "model", {"model_type": "gpt_oss"}))
    monkeypatch.setattr(runtime.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(runtime.socket, "create_connection", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("closed")))

    with pytest.raises(TimeoutError, match="extraction"):
        runtime.start_server(tmp_path, tmp_path / "working", timeout_seconds=1)


def test_root_dead_exact_saved_child_is_terminated_then_killed(tmp_path, monkeypatch):
    paths = runtime._server_paths(tmp_path)
    identity = _identity_with_child()
    runtime._json_write(paths["identity"], identity)
    paths["metrics"].write_text("metric 1\n", encoding="utf-8")
    records = {100: None, 200: dict(_worker(200, 20, 100, 100, "child"), state="S", ppid=100)}
    signals = []

    def record(pid):
        return records.get(pid)

    def kill(pid, signal):
        signals.append((pid, signal))
        if signal == runtime.signal.SIGKILL:
            records[pid] = None

    monkeypatch.setattr(runtime, "_boot_id", lambda: "boot")
    monkeypatch.setattr(runtime, "_proc_record", record)
    monkeypatch.setattr(runtime.os, "kill", kill)
    monkeypatch.setattr(runtime.os, "killpg", lambda *args: pytest.fail("root-dead teardown must not kill a process group"))
    monkeypatch.setattr(runtime, "_gpu_rows", lambda: ([], True))
    monkeypatch.setattr(runtime, "TERM_GRACE_SECONDS", 0.0)
    monkeypatch.setattr(runtime, "KILL_GRACE_SECONDS", 0.0)

    result = runtime.stop_server(tmp_path)

    assert result["shutdown_ok"] is True
    assert signals == [(200, runtime.signal.SIGTERM), (200, runtime.signal.SIGKILL)]


def test_root_dead_child_pid_reuse_is_never_signalled_and_fails_closed(tmp_path, monkeypatch):
    paths = runtime._server_paths(tmp_path)
    identity = _identity_with_child()
    runtime._json_write(paths["identity"], identity)
    paths["metrics"].write_text("metric 1\n", encoding="utf-8")
    records = {100: None, 200: dict(_worker(200, 99, 100, 100, "new-child"), state="S", ppid=1)}
    signals = []
    monkeypatch.setattr(runtime, "_boot_id", lambda: "boot")
    monkeypatch.setattr(runtime, "_proc_record", lambda pid: records.get(pid))
    monkeypatch.setattr(runtime.os, "kill", lambda *args: signals.append(args))
    monkeypatch.setattr(runtime, "_gpu_rows", lambda: ([], True))

    result = runtime.stop_server(tmp_path)

    assert result["shutdown_ok"] is False
    assert "saved_child_identity_changed:200" in result["errors"]
    assert signals == []


def test_root_identity_conflict_rejects_saved_child_cleanup(tmp_path, monkeypatch):
    paths = runtime._server_paths(tmp_path)
    identity = _identity_with_child()
    runtime._json_write(paths["identity"], identity)
    paths["metrics"].write_text("metric 1\n", encoding="utf-8")
    records = {100: dict(_worker(100, 11, 100, 100, "root"), state="S", ppid=1), 200: dict(_worker(200, 20, 100, 100, "child"), state="S", ppid=100)}
    signals = []
    monkeypatch.setattr(runtime, "_boot_id", lambda: "boot")
    monkeypatch.setattr(runtime, "_proc_record", lambda pid: records.get(pid))
    monkeypatch.setattr(runtime.os, "kill", lambda *args: signals.append(args))
    monkeypatch.setattr(runtime.os, "killpg", lambda *args: signals.append(args))
    monkeypatch.setattr(runtime, "_gpu_rows", lambda: ([], True))

    result = runtime.stop_server(tmp_path)

    assert result["shutdown_ok"] is False
    assert "identity_rejected:pid_identity_changed" in result["errors"]
    assert signals == []


def test_vanished_root_does_not_overwrite_prior_worker_snapshot(tmp_path, monkeypatch):
    paths = runtime._server_paths(tmp_path)
    identity = _identity_with_child()
    runtime._json_write(paths["identity"], identity)
    root = dict(_worker(100, 10, 100, 100, "root"), state="S", ppid=1)
    monkeypatch.setattr(runtime, "_proc_record", lambda pid: root if pid == 100 else None)
    monkeypatch.setattr(runtime, "_snapshot_owned_workers", lambda identity: (_ for _ in ()).throw(RuntimeError("root vanished")))
    monkeypatch.setattr(runtime.time, "monotonic", lambda: 0.0)

    with pytest.raises(RuntimeError, match="root vanished"):
        runtime._wait_ready(identity, paths, 1.0)

    assert runtime._json_read(paths["identity"])["workers"] == identity["workers"]

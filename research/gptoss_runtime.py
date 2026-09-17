"""Bounded offline lifecycle helper for the Kaggle GPT-OSS-120B candidate.

The attached runtime was originally prepared for another model.  This module
uses only its pinned *resolver* and *extractor*, then derives a clean GPT-OSS
environment from the verified filesystem.  In particular, it never invokes
the Qwen PLE patch, runtime-environment, probe, or main functions.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


HOST = "127.0.0.1"
PORT = 1234
BASE_URL = f"http://{HOST}:{PORT}/v1"
MODEL_NAME = "gpt-oss-120b"
MODEL_DATASET = "danielhanchen/gpt-oss-120b"
RUNTIME_DATASET = "keithtyser/qwen38-flash-next-vllm-nvfp4-runtime-v1"
BOOTSTRAP_SHA256 = "037c041c9bd9dcffa9084b32f47af9cf1bf35849d5eaf2e1a3422daac098b2e2"
BOOTSTRAP_RUNTIME_MANIFEST_SHA256 = (
    "e9453f8d0e9c5eb2e14712e0f8563aaa96752ddc1705f245cac327537502baad"
)
BOOTSTRAP_VLLM_VERSION = "0.1.dev20073+g8e685d198"
MODEL_TYPE = "gpt_oss"
MAX_MODEL_LEN = 32_768
MAX_NUM_SEQS = 16
GPU_MEMORY_UTILIZATION = "0.90"
METRICS_TIMEOUT_SECONDS = 10.0
TERM_GRACE_SECONDS = 30.0
KILL_GRACE_SECONDS = 15.0
MAX_WATCHDOG_SECONDS = 20 * 60

IDENTITY_FILENAME = "gptoss-server-identity.json"
PROVENANCE_FILENAME = "gptoss-runtime-provenance.json"
LOG_FILENAME = "gptoss-vllm.log"
METRICS_FILENAME = "gptoss-vllm-metrics-final.prom"
TEARDOWN_FILENAME = "gptoss-server-teardown.json"
TOOL_SMOKE_FILENAME = "gptoss-tool-smoke.json"
HARMONY_PREFLIGHT_FILENAME = "gptoss-harmony-preflight.json"
STARTUP_FAILURE_FILENAME = "gptoss-startup-failure.json"
HARMONY_CACHE_DIRNAME = "gptoss-harmony-cache"
# openai-harmony 0.0.8 resolves the GPT-OSS vocabulary through tiktoken-rs
# using this content-addressed cache key.  The notebook builder places this
# exact official blob in the working directory before startup.
HARMONY_TIKTOKEN_CACHE_KEY = "fb374d419588a4632f3f557e76b4b70aebbca790"
HARMONY_VOCAB_BYTES = 3_613_922
HARMONY_VOCAB_SHA256 = "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"
HARMONY_PREFLIGHT_MAX_SECONDS = 20.0
_ATEXIT_GUARDS: set[str] = set()


def _json_write(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _json_read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object in {path}.")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _boot_id() -> str:
    return Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()


def _proc_record(pid: int) -> dict[str, Any] | None:
    """Return a PID-reuse-resistant fingerprint, or ``None`` when it exited."""
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        close = raw.rfind(")")
        fields = raw[close + 2 :].split()
        argv_bytes = Path(f"/proc/{pid}/cmdline").read_bytes()
        return {
            "pid": pid,
            "state": fields[0],
            "ppid": int(fields[1]),
            "pgid": int(fields[2]),
            "sid": int(fields[3]),
            "start_ticks": int(fields[19]),
            "argv_sha256": hashlib.sha256(
                json.dumps(
                    [part.decode("utf-8", errors="replace") for part in argv_bytes.split(b"\0") if part],
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        }
    except (FileNotFoundError, IndexError, OSError, ValueError):
        return None


def _server_paths(working_dir: Path) -> dict[str, Path]:
    return {
        "identity": working_dir / IDENTITY_FILENAME,
        "provenance": working_dir / PROVENANCE_FILENAME,
        "log": working_dir / LOG_FILENAME,
        "metrics": working_dir / METRICS_FILENAME,
        "teardown": working_dir / TEARDOWN_FILENAME,
        "tool_smoke": working_dir / TOOL_SMOKE_FILENAME,
        "harmony_preflight": working_dir / HARMONY_PREFLIGHT_FILENAME,
        "startup_failure": working_dir / STARTUP_FAILURE_FILENAME,
    }


def _bootstrap_path(bundle_dir: Path) -> Path:
    candidates = [bundle_dir / "serving_setup.py", Path("/tmp/arc3-gptoss-source.yNkUMhA1/serving_setup.py")]
    for candidate in candidates:
        if candidate.is_file() and _sha256(candidate) == BOOTSTRAP_SHA256:
            return candidate
    raise RuntimeError("The pinned serving_setup.py bootstrap was not available with its approved SHA-256.")


def _load_bootstrap(bundle_dir: Path, working_dir: Path) -> tuple[Any, Path]:
    """Load the pinned bootstrap without executing its Qwen entry point."""
    source = _bootstrap_path(bundle_dir)
    saved = {name: os.environ.get(name) for name in ("TAAF_KAGGLE_BUNDLE_DIR", "TAAF_KAGGLE_WORKING_DIR", "TAAF_KAGGLE_SETUP_ENV")}
    try:
        os.environ["TAAF_KAGGLE_BUNDLE_DIR"] = str(bundle_dir)
        os.environ["TAAF_KAGGLE_WORKING_DIR"] = str(working_dir)
        os.environ["TAAF_KAGGLE_SETUP_ENV"] = str(working_dir / "gptoss-ignored-setup-env.json")
        module_name = f"arc3_pinned_runtime_{hashlib.sha256(str(source).encode()).hexdigest()[:16]}"
        spec = importlib.util.spec_from_file_location(module_name, source)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load pinned bootstrap: {source}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, source
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _model_candidates() -> list[Path]:
    configured = os.environ.get("ARC3_GPTOSS_MODEL_DIR", "").strip()
    candidates = [Path(configured)] if configured else []
    candidates.extend(
        [
            Path("/kaggle/input/models/danielhanchen/gpt-oss-120b/transformers/default/1"),
            Path("/kaggle/input/models/danielhanchen/gpt-oss-120b/Transformers/default/1"),
        ]
    )
    return candidates


def _validate_model_dir(model_dir: Path) -> dict[str, Any]:
    config_path = model_dir / "config.json"
    if not config_path.is_file() or model_dir.is_symlink():
        raise FileNotFoundError(f"GPT-OSS attachment is missing a regular config.json: {model_dir}")
    # The Kaggle attachment is intentionally exact: .../gpt-oss-120b/Transformers/default/1.
    parts = [part.lower() for part in model_dir.parts]
    if len(parts) < 4 or parts[-3:] != ["transformers", "default", "1"] or "gpt-oss-120b" not in parts:
        raise RuntimeError(f"Unexpected GPT-OSS attachment path: {model_dir}")
    config = _json_read(config_path)
    if config.get("model_type") != MODEL_TYPE:
        raise RuntimeError(f"Expected model_type={MODEL_TYPE!r}, got {config.get('model_type')!r}.")
    return {"path": str(model_dir), "config_sha256": _sha256(config_path), "model_type": MODEL_TYPE}


def resolve_model_dir() -> tuple[Path, dict[str, Any]]:
    errors: list[str] = []
    for candidate in _model_candidates():
        try:
            return candidate, _validate_model_dir(candidate)
        except (FileNotFoundError, RuntimeError) as exc:
            errors.append(str(exc))
    raise FileNotFoundError("Could not resolve the exact GPT-OSS attachment. " + " | ".join(errors))


def _runtime_environment(runtime_root: Path, working_dir: Path) -> tuple[dict[str, str], dict[str, Any]]:
    """Derive paths only; do not call the Qwen-only runtime_environment helper."""
    site = runtime_root / "usr/local/lib/python3.12/dist-packages"
    cuda_home = runtime_root / "usr/local/cuda-13.0"
    cuda_lib = cuda_home / "targets/x86_64-linux/lib"
    cutlass_nested = site / "nvidia_cutlass_dsl/dsl_packages"
    required = [site / "vllm/__init__.py", site / "torch/__init__.py", cuda_home / "bin/nvcc", cuda_lib / "libcudart.so", cutlass_nested / "cutlass/__init__.py"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("Verified runtime lacks GPT-OSS serving prerequisites: " + ", ".join(missing))

    cache_root = working_dir / "gptoss-cache"
    compile_root = working_dir / "gptoss-compile-cache"
    temp_root = working_dir / "gptoss-tmp"
    for path in (cache_root, compile_root, temp_root):
        path.mkdir(parents=True, exist_ok=True)
    nvidia_libs = sorted(str(path) for path in (site / "nvidia").glob("*/lib") if path.is_dir())
    library_dirs = [str(cuda_lib), str(cuda_home / "lib64"), str(site / "torch/lib"), *nvidia_libs,
                    "/usr/local/nvidia/lib64", "/usr/lib/x86_64-linux-gnu"]
    env = os.environ.copy()
    for key in list(env):
        if key == "PYTORCH_ALLOC_CONF" or "QWEN" in key or "RADIXARK" in key or "PLE" in key:
            env.pop(key, None)
    # PYTHONPATH does not execute the runtime's .pth file that adds CUTLASS DSL.
    env["PYTHONPATH"] = os.pathsep.join([str(cutlass_nested), str(site), env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    env["PATH"] = os.pathsep.join([str(cuda_home / "bin"), env.get("PATH", "")]).rstrip(os.pathsep)
    # CUDA 13's unversioned libcudart linker name lives in cuda_lib.  Keeping it
    # first prevents the historical host -lcudart lookup failure.
    env["LD_LIBRARY_PATH"] = os.pathsep.join(
        [path for path in library_dirs if Path(path).is_dir()] + ([env["LD_LIBRARY_PATH"]] if env.get("LD_LIBRARY_PATH") else [])
    )
    # GCC's link-time search is distinct from the loader's LD_LIBRARY_PATH.
    env["LIBRARY_PATH"] = os.pathsep.join(
        [path for path in library_dirs if Path(path).is_dir()] + ([env["LIBRARY_PATH"]] if env.get("LIBRARY_PATH") else [])
    )
    env.update(
        {
            "CUDA_VISIBLE_DEVICES": "0",
            "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
            "CUDA_HOME": str(cuda_home),
            "CUDACXX": str(cuda_home / "bin/nvcc"),
            "HF_HOME": str(cache_root / "huggingface"),
            "XDG_CACHE_HOME": str(cache_root),
            "TORCH_HOME": str(cache_root / "torch"),
            "TORCHINDUCTOR_CACHE_DIR": str(compile_root / "torchinductor"),
            "TRITON_CACHE_DIR": str(compile_root / "triton"),
            "CUDA_CACHE_PATH": str(compile_root / "cuda"),
            "TMPDIR": str(temp_root),
            "HF_HUB_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "VLLM_NO_USAGE_STATS": "1",
            "VLLM_ENABLE_CUDA_COMPATIBILITY": "0",
            "DO_NOT_TRACK": "1",
            "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
            "PYTHONDONTWRITEBYTECODE": "1",
            "TOKENIZERS_PARALLELISM": "false",
            "LOCAL_ANALYZER_BASE_URL": BASE_URL,
            "OPENAI_BASE_URL": BASE_URL,
            "BASE_URL": BASE_URL,
            "LOCAL_ANALYZER_PROVIDER": "vllm",
            "OPENAI_PROVIDER": "vllm",
            "LOCAL_ANALYZER_MODEL_ID": MODEL_NAME,
            "INFERENCE_ANALYZER_MODEL": MODEL_NAME,
            "MODEL_NAME": MODEL_NAME,
            "LOCAL_ANALYZER_API_KEY": "offline",
            "OPENAI_API_KEY": "offline",
            "LOCAL_ANALYZER_CONTEXT_WINDOW": str(MAX_MODEL_LEN),
            "LOCAL_ANALYZER_MAX_OUTPUT": "0",
            "LOCAL_ANALYZER_TOOL_STEPS": "0",
            "LOCAL_ANALYZER_TOOL_TIMEOUT": "30",
            "LOCAL_ANALYZER_TOOL_OUTPUT_TOKENS": "1024",
            "LOCAL_ANALYZER_YIELD_SECONDS": "60",
            "LOCAL_ANALYZER_TEMPERATURE": "0.6",
            "LOCAL_ANALYZER_TOP_P": "0.95",
            "LOCAL_ANALYZER_ENABLE_THINKING": "true",
            "MULTIMODAL_CONTEXT": "",
        }
    )
    return env, {
        "environment_strategy": "derived_from_verified_runtime_not_qwen_runtime_environment",
        "site_packages": str(site),
        "cuda_home": str(cuda_home),
        "cuda13_libcudart_link_directory": str(cuda_lib),
        "cuda13_libcudart": str(cuda_lib / "libcudart.so"),
    }


def _duck_environment(env: dict[str, str]) -> dict[str, str]:
    keys = (
        "LOCAL_ANALYZER_PROVIDER", "OPENAI_PROVIDER", "LOCAL_ANALYZER_BASE_URL",
        "OPENAI_BASE_URL", "BASE_URL", "LOCAL_ANALYZER_MODEL_ID",
        "INFERENCE_ANALYZER_MODEL", "MODEL_NAME", "LOCAL_ANALYZER_API_KEY",
        "OPENAI_API_KEY", "LOCAL_ANALYZER_CONTEXT_WINDOW", "LOCAL_ANALYZER_MAX_OUTPUT",
        "LOCAL_ANALYZER_TOOL_STEPS", "LOCAL_ANALYZER_TOOL_TIMEOUT",
        "LOCAL_ANALYZER_TOOL_OUTPUT_TOKENS", "LOCAL_ANALYZER_YIELD_SECONDS",
        "LOCAL_ANALYZER_TEMPERATURE", "LOCAL_ANALYZER_TOP_P",
        "LOCAL_ANALYZER_ENABLE_THINKING", "MULTIMODAL_CONTEXT",
    )
    return {key: env[key] for key in keys}


def _prepare_harmony_cache(working_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    """Verify the pinned offline vocabulary and expose only its cache directory."""
    cache_dir = working_dir / HARMONY_CACHE_DIRNAME
    vocabulary = cache_dir / HARMONY_TIKTOKEN_CACHE_KEY
    if not vocabulary.is_file() or vocabulary.is_symlink():
        raise FileNotFoundError(f"Pinned Harmony vocabulary is missing: {vocabulary}")
    actual_bytes = vocabulary.stat().st_size
    if actual_bytes != HARMONY_VOCAB_BYTES:
        raise RuntimeError(
            f"Pinned Harmony vocabulary has {actual_bytes} bytes; expected {HARMONY_VOCAB_BYTES}."
        )
    actual_sha256 = _sha256(vocabulary)
    if actual_sha256 != HARMONY_VOCAB_SHA256:
        raise RuntimeError("Pinned Harmony vocabulary SHA-256 did not match the approved offline asset.")
    # A stale override can change the upstream URL and therefore the cache key.
    # The pinned asset is for openai-harmony's unmodified official URL.
    env.pop("TIKTOKEN_ENCODINGS_BASE", None)
    env["TIKTOKEN_RS_CACHE_DIR"] = str(cache_dir)
    return {
        "cache_dir": str(cache_dir), "cache_key": HARMONY_TIKTOKEN_CACHE_KEY,
        "bytes": actual_bytes, "sha256": actual_sha256,
    }


_HARMONY_PREFLIGHT_SOURCE = """
import json
from importlib.metadata import version
from openai_harmony import Conversation, HarmonyEncodingName, Message, Role, SystemContent, load_harmony_encoding

encoding = load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)
conversation = Conversation.from_messages([
    Message.from_role_and_content(Role.SYSTEM, SystemContent.new()),
    Message.from_role_and_content(Role.USER, "Reply with only: ok."),
])
tokens = encoding.render_conversation_for_completion(conversation, Role.ASSISTANT)
print(json.dumps({"harmony_version": version("openai-harmony"), "token_count": len(tokens)}))
"""


def _run_harmony_preflight(env: dict[str, str], output_path: Path, deadline: float) -> dict[str, Any]:
    """Render a fixed conversation without CUDA or a vLLM server process."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("GPT-OSS startup budget expired before Harmony CPU preflight.")
    timeout = min(HARMONY_PREFLIGHT_MAX_SECONDS, remaining)
    result: dict[str, Any] = {"phase": "running", "timeout_seconds": timeout}
    _json_write(output_path, result)
    try:
        completed = subprocess.run(
            [sys.executable, "-c", _HARMONY_PREFLIGHT_SOURCE], env=env,
            capture_output=True, text=True, timeout=timeout, check=True,
        )
        value = json.loads(completed.stdout)
        if not isinstance(value, dict) or not isinstance(value.get("harmony_version"), str) or not isinstance(value.get("token_count"), int):
            raise RuntimeError("Harmony CPU preflight returned an invalid report.")
        result.update({"phase": "passed", **value})
        _json_write(output_path, result)
        return result
    except Exception as exc:
        result.update({"phase": "failed", "error_type": type(exc).__name__, "error": str(exc)})
        _json_write(output_path, result)
        raise


def server_command(model_dir: Path) -> list[str]:
    """The GPT-OSS command intentionally has no Qwen template/parser/MTP flags."""
    return [
        sys.executable, "-m", "vllm.entrypoints.cli.main", "serve", str(model_dir),
        "--served-model-name", MODEL_NAME, "--host", HOST, "--port", str(PORT),
        "--tensor-parallel-size", "1", "--gpu-memory-utilization", GPU_MEMORY_UTILIZATION,
        "--max-model-len", str(MAX_MODEL_LEN), "--max-num-seqs", str(MAX_NUM_SEQS),
        "--enforce-eager", "--enable-prefix-caching", "--enable-auto-tool-choice",
        "--tool-call-parser", "openai", "--no-enable-log-requests",
        "--disable-uvicorn-access-log",
    ]


def _http_bytes(url: str, timeout: float, payload: dict[str, Any] | None = None) -> bytes:
    try:
        request = urllib.request.Request(
            url,
            None if payload is None else json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        # Preserve just enough server evidence to diagnose a rejected request.
        # Do not retain response headers, which can carry infrastructure details.
        body = exc.read(4096).decode("utf-8", errors="replace").strip()
        detail = f": {body}" if body else ""
        raise RuntimeError(f"HTTP request failed for {url}: HTTP {exc.code}{detail}") from exc
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeError(f"HTTP request failed for {url}: {exc}") from exc


def _worker_identity(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in ("pid", "start_ticks", "pgid", "sid", "argv_sha256")}


def _snapshot_owned_workers(identity: dict[str, Any]) -> list[dict[str, Any]]:
    """Snapshot exact session members only while the root proves ownership."""
    matching, reason = _identity_matches(identity)
    if not matching:
        raise RuntimeError(f"Cannot update worker identity after root change: {reason}")
    workers = [_worker_identity(record) for record in _owned_live_records(identity)]
    root = [worker for worker in workers if worker["pid"] == identity["pid"]]
    if len(root) != 1 or root[0]["start_ticks"] != identity["start_ticks"]:
        raise RuntimeError("Owned worker snapshot lost the GPT-OSS root.")
    return sorted(workers, key=lambda worker: int(worker["pid"]))


def _wait_ready(identity: dict[str, Any], paths: dict[str, Path], deadline: float) -> float:
    while time.monotonic() < deadline:
        live = _proc_record(int(identity["pid"]))
        if live is None or live["state"] == "Z" or int(live["start_ticks"]) != int(identity["start_ticks"]):
            raise RuntimeError("GPT-OSS server exited before readiness.")
        # Persist only a root-verified snapshot; a vanished/reused root cannot
        # erase the last known-good child identities.
        identity["workers"] = _snapshot_owned_workers(identity)
        identity["worker_snapshot_epoch"] = time.time()
        _json_write(paths["identity"], identity)
        try:
            value = json.loads(_http_bytes(f"{BASE_URL}/models", min(5.0, max(0.1, deadline - time.monotonic()))))
        except RuntimeError:
            time.sleep(1.0)
            continue
        except json.JSONDecodeError as exc:
            raise RuntimeError("GPT-OSS /v1/models did not return JSON.") from exc
        if not isinstance(value, dict):
            raise RuntimeError("GPT-OSS /v1/models did not return an object.")
        ids = [row.get("id") for row in value.get("data", []) if isinstance(row, dict)]
        if ids == [MODEL_NAME]:
            return time.time()
        if ids:
            raise RuntimeError(f"GPT-OSS endpoint served the wrong model IDs: {ids}")
        time.sleep(1.0)
    raise TimeoutError("Timed out waiting for GPT-OSS /v1/models readiness.")


def _tool_smoke(deadline: float, output_path: Path) -> dict[str, Any]:
    """Exercise native tool parsing before the benchmark's first game compiles.

    This is fixed data only: it never authorizes model-produced code or tools.
    """
    first = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": "Call submit_number with value 4. Do not answer in prose."}],
        "tools": [{"type": "function", "function": {"name": "submit_number", "description": "Submit one integer.", "parameters": {"type": "object", "properties": {"value": {"type": "integer"}}, "required": ["value"]}}}],
        "tool_choice": "auto", "ignore_eos": False,
        "temperature": 0.0, "reasoning_effort": "low", "max_tokens": 512,
    }
    first_timeout = min(120.0, max(0.1, deadline - time.monotonic()))
    result: dict[str, Any] = {"first_request": first}
    _json_write(output_path, result)
    try:
        first_response = json.loads(_http_bytes(f"{BASE_URL}/chat/completions", first_timeout, first))
    except Exception as exc:
        result["first_error"] = {"type": type(exc).__name__, "message": str(exc)}
        _json_write(output_path, result)
        raise
    result["first_response"] = first_response
    _json_write(output_path, result)
    message = ((first_response.get("choices") or [{}])[0].get("message") or {})
    calls = message.get("tool_calls") or []
    if len(calls) != 1 or (calls[0].get("function") or {}).get("name") != "submit_number":
        raise RuntimeError(f"GPT-OSS native tool smoke returned no submit_number call: {first_response}")
    call_id = calls[0].get("id")
    if not isinstance(call_id, str) or not call_id.strip():
        raise RuntimeError(f"GPT-OSS native tool smoke returned an invalid call ID: {calls}")
    raw_arguments = (calls[0].get("function") or {}).get("arguments", "{}")
    arguments = raw_arguments if isinstance(raw_arguments, dict) else json.loads(raw_arguments)
    if arguments.get("value") != 4:
        raise RuntimeError(f"GPT-OSS native tool smoke returned wrong arguments: {calls}")
    assistant_message = {"role": "assistant", "content": message.get("content"), "tool_calls": calls}
    for field in ("reasoning", "reasoning_content"):
        if field in message:
            assistant_message[field] = message[field]
    second = {
        "model": MODEL_NAME,
        "messages": [*first["messages"], assistant_message, {"role": "tool", "tool_call_id": call_id, "content": "{\"accepted\":true}"}],
        "tools": first["tools"], "tool_choice": "auto", "ignore_eos": False,
        "temperature": 0.0, "reasoning_effort": "low", "max_tokens": 512,
    }
    second_timeout = min(120.0, max(0.1, deadline - time.monotonic()))
    result["second_request"] = second
    _json_write(output_path, result)
    try:
        second_response = json.loads(_http_bytes(f"{BASE_URL}/chat/completions", second_timeout, second))
    except Exception as exc:
        result["second_error"] = {"type": type(exc).__name__, "message": str(exc)}
        _json_write(output_path, result)
        raise
    result["second_response"] = second_response
    _json_write(output_path, result)
    final_message = ((second_response.get("choices") or [{}])[0].get("message") or {})
    if final_message.get("tool_calls"):
        raise RuntimeError(f"GPT-OSS tool-result smoke returned unexpected tool calls: {second_response}")
    if not isinstance(final_message.get("content"), str) or not final_message["content"].strip():
        raise RuntimeError(f"GPT-OSS tool-result smoke returned no final response: {second_response}")
    return result


def _register_atexit_guard(working_dir: Path) -> None:
    key = str(working_dir.resolve())
    if key in _ATEXIT_GUARDS:
        return
    _ATEXIT_GUARDS.add(key)
    import atexit

    def cleanup() -> None:
        try:
            stop_server(working_dir)
        except Exception:
            pass

    atexit.register(cleanup)


def arm_shutdown_watchdog(working_dir: Path, deadline_epoch: float) -> dict[str, Any]:
    """Arm one identity-bound, in-process deadline guard for a short smoke.

    The guard checks that the same PID/start-ticks identity still owns the
    working directory before it calls ``stop_server``.  It is deliberately
    bounded to twenty minutes and is cancelled implicitly by successful stop.
    """
    if not isinstance(deadline_epoch, (int, float)):
        raise TypeError("deadline_epoch must be an epoch timestamp.")
    paths = _server_paths(Path(working_dir))
    identity = _json_read(paths["identity"])
    delay = float(deadline_epoch) - time.time()
    if not 0 < delay <= MAX_WATCHDOG_SECONDS:
        raise ValueError(f"watchdog deadline must be within {MAX_WATCHDOG_SECONDS}s.")
    expected = (identity.get("pid"), identity.get("start_ticks"))

    def guard() -> None:
        time.sleep(delay)
        try:
            current = _json_read(paths["identity"])
            if (current.get("pid"), current.get("start_ticks")) == expected:
                stop_server(Path(working_dir))
        except Exception:
            pass

    thread = threading.Thread(target=guard, name="gptoss-shutdown-guard", daemon=True)
    thread.start()
    return {"armed": True, "deadline_epoch": float(deadline_epoch), "pid": expected[0], "start_ticks": expected[1]}


def _identity_matches(identity: dict[str, Any]) -> tuple[bool, str | None]:
    try:
        pid = int(identity["pid"])
        ticks = int(identity["start_ticks"])
        pgid = int(identity["pgid"])
        sid = int(identity["sid"])
    except (KeyError, TypeError, ValueError):
        return False, "invalid_identity_numbers"
    if identity.get("boot_id") != _boot_id():
        return False, "boot_id_changed"
    current = _proc_record(pid)
    if current is None or current["state"] == "Z":
        return False, "root_not_live"
    if ticks != current["start_ticks"]:
        return False, "pid_identity_changed"
    if pgid != pid or sid != pid or current["pgid"] != pgid or current["sid"] != sid:
        return False, "process_group_not_owned"
    if identity.get("argv_sha256") != current["argv_sha256"]:
        return False, "argv_identity_changed"
    return True, None


def _alive_identity(identity: dict[str, Any]) -> bool:
    current = _proc_record(int(identity["pid"]))
    return current is not None and current["state"] != "Z" and int(current["start_ticks"]) == int(identity["start_ticks"])


def _owned_live_records(identity: dict[str, Any]) -> list[dict[str, Any]]:
    """Enumerate the isolated session while it is still bound to our launch."""
    try:
        pgid, sid = int(identity["pgid"]), int(identity["sid"])
    except (KeyError, TypeError, ValueError):
        return []
    records: list[dict[str, Any]] = []
    try:
        proc_entries = list(Path("/proc").iterdir())
    except OSError:
        return []
    for entry in proc_entries:
        if not entry.name.isdigit():
            continue
        record = _proc_record(int(entry.name))
        if record is not None and record["state"] != "Z" and record["pgid"] == pgid and record["sid"] == sid:
            records.append(record)
    return records


def _same_live_record(expected: dict[str, Any]) -> dict[str, Any] | None:
    current = _proc_record(int(expected["pid"]))
    if current is None or current["state"] == "Z":
        return None
    for key in ("start_ticks", "pgid", "sid", "argv_sha256"):
        if current.get(key) != expected.get(key):
            return None
    return current


def _saved_child_workers(identity: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Validate persisted workers without inferring ownership from a name."""
    workers = identity.get("workers")
    required = {"pid", "start_ticks", "pgid", "sid", "argv_sha256"}
    errors: list[str] = []
    if not isinstance(workers, list):
        return [], ["saved_workers_missing"]
    valid: list[dict[str, Any]] = []
    for worker in workers:
        if not isinstance(worker, dict) or set(worker) != required:
            errors.append("saved_worker_schema_invalid")
            continue
        if not all(isinstance(worker[key], int) for key in ("pid", "start_ticks", "pgid", "sid")) or not isinstance(worker["argv_sha256"], str):
            errors.append("saved_worker_fields_invalid")
            continue
        valid.append(worker)
    roots = [worker for worker in valid if worker["pid"] == identity.get("pid")]
    if len(roots) != 1 or any(roots[0].get(key) != identity.get(key) for key in ("start_ticks", "pgid", "sid", "argv_sha256")):
        errors.append("saved_root_worker_mismatch")
    return [worker for worker in valid if worker["pid"] != identity.get("pid")], errors


def _terminate_saved_children(workers: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Bounded exact-PID teardown for a session whose root already exited."""
    errors: list[str] = []
    live: list[dict[str, Any]] = []
    for worker in workers:
        current = _same_live_record(worker)
        if current is not None:
            live.append(worker)
        elif _proc_record(int(worker["pid"])) is not None:
            errors.append(f"saved_child_identity_changed:{worker['pid']}")
    for worker in live:
        try:
            os.kill(int(worker["pid"]), signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + TERM_GRACE_SECONDS
    while any(_same_live_record(worker) is not None for worker in live) and time.monotonic() < deadline:
        time.sleep(0.2)
    survivors = [worker for worker in live if _same_live_record(worker) is not None]
    for worker in survivors:
        # Recheck immediately before every exact PID SIGKILL.
        if _same_live_record(worker) is None:
            continue
        try:
            os.kill(int(worker["pid"]), signal.SIGKILL)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + KILL_GRACE_SECONDS
    while any(_same_live_record(worker) is not None for worker in survivors) and time.monotonic() < deadline:
        time.sleep(0.2)
    return [worker for worker in survivors if _same_live_record(worker) is not None], errors


def _gpu_rows() -> tuple[list[dict[str, Any]], bool]:
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10.0, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [{"query_error": str(exc)}], False
    if completed.returncode != 0:
        return [{"query_error": completed.stderr.strip() or "nvidia-smi failed"}], False
    rows: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        record = _proc_record(pid)
        rows.append({"pid": pid, "process_name": parts[1], "used_memory_mib": parts[2], "start_ticks": None if record is None else record["start_ticks"]})
    return rows, True


def gpu_rows() -> list[dict[str, Any]]:
    """Return a fresh GPU process snapshot; query failures are explicit rows."""
    return _gpu_rows()[0]


def _capture_metrics(paths: dict[str, Path], errors: list[str]) -> bool:
    if paths["metrics"].is_file() and paths["metrics"].stat().st_size > 0:
        return True
    try:
        metrics = _http_bytes(f"http://{HOST}:{PORT}/metrics", METRICS_TIMEOUT_SECONDS)
        if not metrics:
            raise RuntimeError("metrics endpoint returned an empty response")
        paths["metrics"].write_bytes(metrics)
        return True
    except Exception as exc:  # stop must still terminate an owned server.
        errors.append(f"metrics_capture:{type(exc).__name__}:{exc}")
        return False


def start_server(bundle_dir: Path, working_dir: Path, timeout_seconds: int = 900) -> dict[str, Any]:
    """Extract, launch, and return only after the offline endpoint is ready."""
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 1800:
        raise ValueError("timeout_seconds must be an integer from 1 through 1800.")
    bundle_dir, working_dir = Path(bundle_dir), Path(working_dir)
    working_dir.mkdir(parents=True, exist_ok=True)
    paths = _server_paths(working_dir)
    prior = stop_server(working_dir)
    if paths["identity"].is_file() and not prior.get("shutdown_ok", False):
        raise RuntimeError(f"A prior owned GPT-OSS server did not shut down: {prior}")
    try:
        with socket.create_connection((HOST, PORT), timeout=0.25):
            raise RuntimeError(f"{HOST}:{PORT} is already occupied by an unowned process.")
    except OSError:
        pass

    deadline = time.monotonic() + timeout_seconds
    identity: dict[str, Any] | None = None
    process: subprocess.Popen[str] | None = None
    provenance: dict[str, Any] | None = None
    try:
        setup, source = _load_bootstrap(bundle_dir, working_dir)
        if getattr(setup, "VLLM_RUNTIME_MANIFEST_SHA256", None) != BOOTSTRAP_RUNTIME_MANIFEST_SHA256:
            raise RuntimeError("Pinned bootstrap has an unexpected runtime manifest pin.")
        if getattr(setup, "VLLM_VERSION", None) != BOOTSTRAP_VLLM_VERSION:
            raise RuntimeError("Pinned bootstrap has an unexpected vLLM version pin.")
        model_dir, model_provenance = resolve_model_dir()
        runtime_dir = setup.resolve_runtime_dir()
        verification = setup.verify_and_extract_runtime(runtime_dir, full_layer_hashes=True)
        if time.monotonic() >= deadline:
            raise TimeoutError("GPT-OSS startup budget expired during runtime extraction.")
        env, environment_provenance = _runtime_environment(Path(setup.RUNTIME_ROOT), working_dir)
        provenance = {
            "schema_version": 1, "phase": "preflight", "runtime_dataset": RUNTIME_DATASET,
            "bootstrap_path": str(source), "bootstrap_sha256": BOOTSTRAP_SHA256,
            "bootstrap_runtime_manifest_sha256": BOOTSTRAP_RUNTIME_MANIFEST_SHA256,
            "bootstrap_vllm_version": BOOTSTRAP_VLLM_VERSION, "runtime_verification": verification,
            "model": model_provenance, "environment": environment_provenance,
        }
        _json_write(paths["provenance"], provenance)
        provenance["harmony_cache"] = _prepare_harmony_cache(working_dir, env)
        _json_write(paths["provenance"], provenance)
        provenance["harmony_preflight"] = _run_harmony_preflight(env, paths["harmony_preflight"], deadline)
        provenance["phase"] = "preflight_complete"
        _json_write(paths["provenance"], provenance)
        command = server_command(model_dir)
        provenance.update({"phase": "launching", "actual_command": command})
        _json_write(paths["provenance"], provenance)
        paths["log"].unlink(missing_ok=True)
        with paths["log"].open("w", encoding="utf-8") as log_handle:
            process = subprocess.Popen(command, env=env, stdout=log_handle, stderr=subprocess.STDOUT, text=True, start_new_session=True)
        root = _proc_record(process.pid)
        if root is None or root["pgid"] != process.pid or root["sid"] != process.pid:
            raise RuntimeError(f"Launched GPT-OSS root lacks an isolated session: {root}")
        argv_sha256 = hashlib.sha256(json.dumps(command, separators=(",", ":")).encode("utf-8")).hexdigest()
        if root["argv_sha256"] != argv_sha256:
            raise RuntimeError("Launched GPT-OSS argv did not match the recorded command.")
        identity = {
            "schema_version": 1, "backend": "vllm", "model_name": MODEL_NAME,
            "boot_id": _boot_id(), "host": HOST, "port": PORT, "pid": process.pid,
            "start_ticks": root["start_ticks"], "pgid": root["pgid"], "sid": root["sid"],
            "argv": command, "argv_sha256": argv_sha256, "started_epoch": time.time(),
            "phase": "starting", "server_ready_epoch": None,
            "workers": [_worker_identity(root)], "worker_snapshot_epoch": time.time(),
        }
        _json_write(paths["identity"], identity)
        _wait_ready(identity, paths, deadline)
        if time.monotonic() >= deadline:
            raise TimeoutError("GPT-OSS startup budget expired before tool readiness smoke.")
        _tool_smoke(deadline, paths["tool_smoke"])
        if time.monotonic() >= deadline:
            raise TimeoutError("GPT-OSS startup budget expired during tool readiness smoke.")
        identity["workers"] = _snapshot_owned_workers(identity)
        identity["worker_snapshot_epoch"] = time.time()
        ready_epoch = time.time()
        identity["phase"] = "ready"
        identity["server_ready_epoch"] = ready_epoch
        _json_write(paths["identity"], identity)
        _register_atexit_guard(working_dir)
        provenance.update({
            "phase": "ready", "actual_command": command, "tool_smoke_path": str(paths["tool_smoke"]),
            "tool_smoke_sha256": _sha256(paths["tool_smoke"]), "server_ready_epoch": ready_epoch,
        })
        _json_write(paths["provenance"], provenance)
        return {"environment": _duck_environment(env), "server_ready_epoch": ready_epoch, "provenance": provenance}
    except Exception as exc:
        teardown: dict[str, Any]
        if identity is not None:
            try:
                teardown = stop_server(working_dir)
            except Exception as teardown_exc:
                teardown = {"attempted": True, "error_type": type(teardown_exc).__name__, "error": str(teardown_exc)}
        elif process is not None and process.poll() is None:
            # Popen is our exact child even if it failed before identity capture.
            try:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                teardown = {"attempted": True, "method": "direct_child", "returncode": process.returncode}
            except Exception as teardown_exc:
                teardown = {"attempted": True, "method": "direct_child", "error_type": type(teardown_exc).__name__, "error": str(teardown_exc)}
        else:
            teardown = {"attempted": False, "reason": "process_not_started"}
        if provenance is not None:
            provenance.update({"phase": "failed", "failure": {"type": type(exc).__name__, "message": str(exc)}})
            _json_write(paths["provenance"], provenance)
        _json_write(paths["startup_failure"], {
            "exception_type": type(exc).__name__, "exception_message": str(exc), "teardown": teardown,
        })
        raise


def stop_server(working_dir: Path) -> dict[str, Any]:
    """Capture metrics then terminate only the PID-reuse-checked owned session."""
    working_dir = Path(working_dir)
    paths = _server_paths(working_dir)
    previous = _json_read(paths["teardown"]) if paths["teardown"].is_file() else None
    repeated_success = previous is not None and previous.get("shutdown_ok") is True
    errors: list[str] = []
    if not paths["identity"].is_file():
        rows, query_ok = _gpu_rows()
        result = {"shutdown_ok": False, "metrics_preserved": paths["metrics"].is_file(), "errors": ["identity_missing"], "post_gpu_rows": rows, "gpu_query_ok": query_ok}
        if previous is None:
            _json_write(paths["teardown"], result)
        return result
    identity = _json_read(paths["identity"])
    matching, reason = _identity_matches(identity)
    root_dead = reason == "root_not_live"
    saved_children, saved_worker_errors = _saved_child_workers(identity)
    owned_at_start_of_stop = matching or (root_dead and not saved_worker_errors)
    metrics_preserved = _capture_metrics(paths, errors) if matching else paths["metrics"].is_file() and paths["metrics"].stat().st_size > 0
    saved_child_survivors: list[dict[str, Any]] = []
    if matching:
        owned_before = _owned_live_records(identity)
        try:
            os.killpg(int(identity["pgid"]), signal.SIGTERM)
        except ProcessLookupError:
            pass
        term_deadline = time.monotonic() + TERM_GRACE_SECONDS
        while any(_same_live_record(record) is not None for record in owned_before) and time.monotonic() < term_deadline:
            time.sleep(0.2)
        survivors = [record for record in owned_before if _same_live_record(record) is not None]
        if survivors:
            # Revalidate immediately before SIGKILL; never kill a reused PID/group.
            matching, reason = _identity_matches(identity)
            if matching:
                try:
                    os.killpg(int(identity["pgid"]), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                # The root can exit first.  Kill only the start-tick/argv matched
                # child PIDs captured while the owned session was live.
                for record in survivors:
                    if _same_live_record(record) is None:
                        continue
                    try:
                        os.kill(int(record["pid"]), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            kill_deadline = time.monotonic() + KILL_GRACE_SECONDS
            while any(_same_live_record(record) is not None for record in survivors) and time.monotonic() < kill_deadline:
                time.sleep(0.2)
    elif root_dead and not saved_worker_errors:
        saved_child_survivors, child_errors = _terminate_saved_children(saved_children)
        errors.extend(child_errors)
    else:
        if not repeated_success:
            errors.append(f"identity_rejected:{reason}")
        errors.extend(saved_worker_errors)
    rows, query_ok = _gpu_rows()
    owned_after = [row for row in rows if row.get("pid") == identity.get("pid") and row.get("start_ticks") == identity.get("start_ticks")]
    cpu_survivors = _owned_live_records(identity) if matching else saved_child_survivors
    shutdown_ok = (owned_at_start_of_stop or repeated_success) and not errors and not cpu_survivors and query_ok and not owned_after and metrics_preserved
    result = {"shutdown_ok": shutdown_ok, "metrics_preserved": metrics_preserved, "errors": errors, "post_gpu_rows": rows, "gpu_query_ok": query_ok, "owned_gpu_rows_after": owned_after, "cpu_survivors": [{"pid": row["pid"], "start_ticks": row["start_ticks"]} for row in cpu_survivors], "pid": identity.get("pid"), "start_ticks": identity.get("start_ticks")}
    if repeated_success:
        # Do not overwrite the first successful metrics/lifecycle evidence.
        result["first_success_preserved"] = True
        result["repeated"] = True
        return result
    _json_write(paths["teardown"], result)
    return result

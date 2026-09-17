#!/usr/bin/env python3
"""Build the crash-proof Gate 2 response-cap comparison notebook.

The current passing Version 11 notebook is the immutable lifecycle base.  This
builder replaces only the experiment orchestration and its terminal audit.  A
single boolean selects the minimum-scale two-arm smoke or the full paired
eight-game comparison; serving, persistence, and teardown code are identical.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "notebooks" / "arc3-gate2-cap1024-smoke.ipynb"
SOURCE_SHA256 = "f63a14c04631460efb6efc612135f2cfa38a0010e2728e334cedf90bf7e01714"
OUTPUT_SMOKE = ROOT / "notebooks" / "arc3-gate2-comparison-smoke.ipynb"
OUTPUT_FULL = ROOT / "notebooks" / "arc3-gate2-token-cap-comparison.ipynb"


def source_text(cell: dict) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else source


def set_source(cell: dict, source: str) -> None:
    cell["source"] = source.splitlines(keepends=True)


def cell_with_prefix(notebook: dict, prefix: str) -> dict:
    matches = [
        cell
        for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "code" and source_text(cell).startswith(prefix)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one cell beginning {prefix!r}, found {len(matches)}")
    return matches[0]


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return source.replace(old, new, 1)


def seed_for(replicate: int) -> int:
    payload = f"349893477:replicate:{replicate}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big") & 0x7FFFFFFF


def _gate2_terminal_gate_after_drain(
    evidence_result: dict,
    process_result: dict,
    post_gpu_rows: list[dict],
) -> tuple[bool, dict]:
    """Reconcile preserved teardown evidence with the current process table.

    The first teardown is the only attempt that can capture live vLLM metrics.
    A GPU process may still be visible briefly after that capture.  Once the
    exact owned process has drained, running teardown again cannot recapture the
    now-closed endpoint and therefore must not replace the first attempt's
    evidence.  This helper keeps the two facts separate.
    """

    owned_identity = {
        int(row["pid"]): row.get("start_ticks")
        for row in (evidence_result.get("vllm_gpu_rows_after") or [])
        if "pid" in row
    }

    def is_owned(row: dict) -> bool:
        pid = int(row.get("pid", -1))
        if pid not in owned_identity:
            return False
        expected_ticks = owned_identity[pid]
        actual_ticks = row.get("start_ticks")
        return expected_ticks is None or actual_ticks == expected_ticks

    post_owned = [row for row in post_gpu_rows if is_owned(row)]
    final_scan = process_result.get("process_scan_final_gate") or {}
    conflict = bool(final_scan.get("root_conflict") or final_scan.get("saved_conflicts"))
    cpu_survivors = bool(
        final_scan.get("authorized_records")
        or final_scan.get("suspect_records")
        or process_result.get("full_proc_marker_survivors")
        or process_result.get("cpu_only_vllm_ple_marker_survivors")
    )
    gpu_query_error = any("query_error" in row for row in post_gpu_rows)
    checks = {
        "identity_valid": bool(evidence_result.get("identity_valid")),
        "no_process_identity_conflict": not conflict,
        "port_closed": bool(process_result.get("port_closed")),
        "no_cpu_survivors": not cpu_survivors,
        "gpu_query_succeeded": not gpu_query_error,
        "no_owned_gpu_survivors": not post_owned,
        "final_metrics_preserved": bool(evidence_result.get("final_metrics_preserved")),
        "required_artifacts_preserved": bool(
            evidence_result.get("required_artifacts_preserved")
        ),
    }
    details = {
        "checks": checks,
        "owned_pids": sorted(owned_identity),
        "post_owned": post_owned,
        "post_gpu_rows": post_gpu_rows,
    }
    return all(checks.values()), details


def teardown_helpers(notebook: dict) -> str:
    source = source_text(
        cell_with_prefix(
            notebook,
            "# Build the live competition game list from the gateway's available environments.",
        )
    )
    start = source.index("def _gate1_proc_start_ticks")
    recovery_start = source.index("\n\ndef _gate1_teardown_with_recovery", start)
    helpers = source[start:recovery_start]
    translated = (
        helpers.replace("_gate1_", "_gate2_")
        .replace("_GATE1_", "_GATE2_")
        .replace("Gate 1", "Gate 2")
    )
    reconciliation = inspect.getsource(_gate2_terminal_gate_after_drain)
    recovery = r'''
def _gate2_teardown_with_recovery():
    first = _gate2_teardown_once("initial")
    first_result = first.get("result") or {}
    first_codes_ok = all(item.get("returncode") == 0 for item in first["commands"])
    if first_codes_ok and first_result.get("shutdown_ok") is True:
        return True, first_result, _gate2_gpu_rows()

    owned_rows = list(first_result.get("vllm_gpu_rows_after") or [])
    owned_identity = {
        int(row["pid"]): row.get("start_ticks")
        for row in owned_rows
        if "pid" in row
    }
    fallback_kills = _gate2_kill_exact(owned_rows)
    drain_started = time.monotonic()
    drain_deadline = drain_started + 45.0
    remaining = []
    while True:
        post_rows = _gate2_gpu_rows()
        remaining = [
            row
            for row in post_rows
            if row.get("pid") in owned_identity
            and (
                owned_identity[row["pid"]] is None
                or row.get("start_ticks") == owned_identity[row["pid"]]
            )
        ]
        if not remaining or time.monotonic() >= drain_deadline:
            break
        retry_rows = [
            {"pid": row["pid"], "start_ticks": owned_identity.get(row["pid"])}
            for row in remaining
        ]
        fallback_kills.extend(_gate2_kill_exact(retry_rows))
        time.sleep(0.5)
    print(
        "GATE2_GPU_DRAIN "
        + json.dumps(
            {
                "owned_pids": sorted(owned_identity),
                "fallback_kills": fallback_kills,
                "wait_seconds": time.monotonic() - drain_started,
                "remaining": remaining,
            },
            sort_keys=True,
        ),
        flush=True,
    )

    process_result = first_result
    recovered, recovery_details = _gate2_terminal_gate_after_drain(
        first_result, process_result, post_rows
    )
    if not recovered:
        # A real CPU-side survivor can require one more bounded cleanup pass.
        # Preserve the first attempt's metrics/artifact evidence and use the
        # retry only as a fresh process-state observation.
        second = _gate2_teardown_once("post_gpu_drain")
        process_result = second.get("result") or {}
        post_rows = _gate2_gpu_rows()
        recovered, recovery_details = _gate2_terminal_gate_after_drain(
            first_result, process_result, post_rows
        )

    if not recovered:
        print(
            "GATE2_TEARDOWN_RECOVERY_BLOCKED "
            + json.dumps(recovery_details, sort_keys=True),
            flush=True,
        )
        return False, process_result, post_rows

    recovered_result = dict(first_result)
    recovered_result["gpu_rows_after"] = post_rows
    recovered_result["gpu_query_error_after"] = any(
        "query_error" in row for row in post_rows
    )
    recovered_result["vllm_gpu_rows_after"] = recovery_details["post_owned"]
    recovered_result["shutdown_ok"] = True
    recovered_result["terminal_gate_recovered_after_gpu_drain"] = True
    recovered_result["terminal_gate_recovery"] = recovery_details
    _gate2_atomic_json(WORKING_DIR / "vllm-server-teardown.json", recovered_result)
    print(
        "GATE2_TEARDOWN_RECOVERED "
        + json.dumps(
            {
                "owned_pids": recovery_details["owned_pids"],
                "post_owned": recovery_details["post_owned"],
                "post_gpu_rows": post_rows,
                "shutdown_ok": True,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return True, recovered_result, post_rows
'''.strip()
    return translated + "\n\n" + reconciliation + "\n\n" + recovery


def instrumentation_cell(smoke: bool) -> str:
    return f'''# Gate 2 paired response-cap experiment. Serving is unchanged from passing Version 11.
GATE2_COMPARISON_SMOKE = {smoke!r}
GATE2_SMOKE_GAME_SECONDS = 60.0
GATE2_TRIAL_SECONDS = 6600.0
GATE2_SMOKE_STARTUP_LIMIT_SECONDS = 900.0
GATE2_SAFETY_MARGIN_SECONDS = 4860.0
GATE2_SOFT_STOP_GRACE_SECONDS = 120.0
GATE2_CONTROL_CAP = 0
GATE2_CANDIDATE_CAP = 1024
GATE2_CONCURRENCY = 1 if GATE2_COMPARISON_SMOKE else 8
GATE2_ACTION_CAP = 400
GATE2_SEEDS = ({seed_for(0)}, {seed_for(1)})

if TRUE_SUBMISSION:
    raise RuntimeError("Gate 2 comparison is local-only and must never be submitted.")
if float(getattr(target, "max_runtime_s", 0.0) or 0.0) != 32400.0:
    raise RuntimeError(
        f"Expected the 32400-second notebook budget, got {{target.max_runtime_s!r}}."
    )
if GATE2_SAFETY_MARGIN_SECONDS < 0.15 * float(target.max_runtime_s):
    raise RuntimeError("Gate 2 safety margin is below 15% of the notebook budget.")
if GATE1_SERVER_READY_EPOCH <= NOTEBOOK_START_EPOCH:
    raise RuntimeError("Server-ready timestamp must follow notebook start.")
if GATE1_SERVER_STARTUP_SECONDS > GATE2_SMOKE_STARTUP_LIMIT_SECONDS:
    raise TimeoutError(
        f"vLLM startup exceeded {{GATE2_SMOKE_STARTUP_LIMIT_SECONDS}}s: "
        f"{{GATE1_SERVER_STARTUP_SECONDS}}s."
    )

import threading as _gate2_threading
import inference.agent.tool_agent as _gate2_tool_agent_module
from inference.agent.tool_agent import ToolAgent as _Gate2ToolAgent
from inference.framework.solver import _HarnessGameSession as _Gate2Session

_GATE2_METRICS_LOCK = _gate2_threading.Lock()
_GATE2_METRICS = {{
    "instrumentation_epoch": time.time(),
    "first_request_started_epoch": None,
    "first_response_epoch": None,
    "llm_calls_total": 0,
    "finish_reason_length_total": 0,
}}
_GATE2_SESSION_METRICS = {{}}

if not getattr(_Gate2ToolAgent, "_gate2_call_counter_installed", False):
    _GATE2_ORIGINAL_CHAT_COMPLETION = _Gate2ToolAgent._chat_completion

    def _gate2_counted_chat_completion(self, *args, **kwargs):
        is_first = False
        started_epoch = time.time()
        with _GATE2_METRICS_LOCK:
            self._gate2_llm_calls = int(getattr(self, "_gate2_llm_calls", 0)) + 1
            _GATE2_METRICS["llm_calls_total"] += 1
            if _GATE2_METRICS["first_request_started_epoch"] is None:
                _GATE2_METRICS["first_request_started_epoch"] = started_epoch
                is_first = True
        try:
            result = _GATE2_ORIGINAL_CHAT_COMPLETION(self, *args, **kwargs)
            finish_reason = str(getattr(result, "finish_reason", "") or "").lower()
            if finish_reason == "length":
                with _GATE2_METRICS_LOCK:
                    self._gate2_finish_reason_length = int(
                        getattr(self, "_gate2_finish_reason_length", 0)
                    ) + 1
                    _GATE2_METRICS["finish_reason_length_total"] += 1
            return result
        finally:
            if is_first:
                with _GATE2_METRICS_LOCK:
                    _GATE2_METRICS["first_response_epoch"] = time.time()

    _Gate2ToolAgent._chat_completion = _gate2_counted_chat_completion
    _Gate2ToolAgent._gate2_call_counter_installed = True

if not getattr(_Gate2Session, "_gate2_action_counter_installed", False):
    _GATE2_ORIGINAL_EXECUTE_ACTION = _Gate2Session._execute_action

    def _gate2_counted_execute_action(self, *args, **kwargs):
        payload = _GATE2_ORIGINAL_EXECUTE_ACTION(self, *args, **kwargs)
        self._gate2_executed_actions = int(getattr(self, "_gate2_executed_actions", 0)) + 1
        if not bool(payload.get("board_changed")):
            self._gate2_noop_actions = int(getattr(self, "_gate2_noop_actions", 0)) + 1
        return payload

    _Gate2Session._execute_action = _gate2_counted_execute_action
    _Gate2Session._gate2_action_counter_installed = True

if not getattr(_Gate2Session, "_gate2_session_timer_installed", False):
    _GATE2_ORIGINAL_SESSION_PLAY = _Gate2Session.play

    def _gate2_traced_session_play(self):
        active_started = time.monotonic()
        try:
            return _GATE2_ORIGINAL_SESSION_PLAY(self)
        finally:
            run = getattr(self.game, "game_run", None)
            game_id = getattr(run, "game_id", str(self.game_index))
            trial_id = str(getattr(self.analyzer, "_gate2_trial_id", "unknown"))
            row = {{
                "session_started": True,
                "active_wall_seconds": time.monotonic() - active_started,
                "llm_calls": int(getattr(self.analyzer, "_gate2_llm_calls", 0)),
                "finish_reason_length": int(
                    getattr(self.analyzer, "_gate2_finish_reason_length", 0)
                ),
                "no_op_actions": int(getattr(self, "_gate2_noop_actions", 0)),
                "instrumented_actions": int(getattr(self, "_gate2_executed_actions", 0)),
            }}
            with _GATE2_METRICS_LOCK:
                _GATE2_SESSION_METRICS[(trial_id, game_id)] = row

    _Gate2Session.play = _gate2_traced_session_play
    _Gate2Session._gate2_session_timer_installed = True

print(
    "GATE2_SETTINGS "
    + json.dumps(
        {{
            "smoke": GATE2_COMPARISON_SMOKE,
            "trial_seconds": (
                GATE2_SMOKE_GAME_SECONDS if GATE2_COMPARISON_SMOKE else GATE2_TRIAL_SECONDS
            ),
            "concurrency": GATE2_CONCURRENCY,
            "action_cap": GATE2_ACTION_CAP,
            "control_cap": GATE2_CONTROL_CAP,
            "candidate_cap": GATE2_CANDIDATE_CAP,
            "seeds": list(GATE2_SEEDS),
            "safety_margin_seconds": GATE2_SAFETY_MARGIN_SECONDS,
        }},
        sort_keys=True,
    ),
    flush=True,
)
'''


def experiment_cell(notebook: dict) -> str:
    helpers = teardown_helpers(notebook)
    return f'''# Gate 2 crash-proof paired comparison. Every arm shares this one vLLM session.
import asyncio as _gate2_asyncio
import copy as _gate2_copy
import os as _gate2_os
import signal as _gate2_signal


def _offline_games(env_dir: str):
    import arc_agi
    import taaf.game_api

    spec = taaf.game_api.ArcadeSpec(
        operation_mode=arc_agi.OperationMode.OFFLINE,
        environments_dir=env_dir,
    )
    arcade = arc_agi.Arcade(
        operation_mode=arc_agi.OperationMode.OFFLINE,
        environments_dir=env_dir,
    )
    game_ids = [env_info.game_id for env_info in arcade.available_environments]
    if not game_ids:
        raise RuntimeError(f"No offline environments found under {{env_dir}}.")
    return [taaf.game_api.GameAPI(env_name=game_id, arcade_spec=spec) for game_id in game_ids]


PUBLIC_GAME_IDS = (
    "tn36-ef4dde99", "lf52-271a04aa", "cn04-2fe56bfb", "bp35-0a0ad940",
    "wa30-ee6fef47", "lp85-305b61c3", "r11l-495a7899", "tu93-0768757b",
    "sp80-589a99af", "m0r0-492f87ba", "vc33-5430563c", "ar25-0c556536",
    "ka59-38d34dbb", "sc25-635fd71a", "sk48-d8078629", "dc22-fdcac232",
    "cd82-fb555c5d", "ft09-0d8bbf25", "g50t-5849a774", "ls20-9607627b",
    "re86-8af5384d", "s5i5-18d95033", "sb26-7fbdac44", "su15-1944f8ab",
    "tr87-cd924810",
)
GATE2_GAME_IDS = (
    "cd82-fb555c5d",
    "lp85-305b61c3",
    "sp80-589a99af",
    "tn36-ef4dde99",
    "bp35-0a0ad940",
    "g50t-5849a774",
    "ka59-38d34dbb",
    "ls20-9607627b",
)

competition_env_files = str(
    Path("/kaggle/input/competitions/arc-prize-2026-arc-agi-3/arc_agi_3_wheels").parent
    / "environment_files"
)
offline_games = _offline_games(competition_env_files)
offline_by_id = {{game.env_name: game for game in offline_games}}
if len(offline_by_id) != len(offline_games):
    raise RuntimeError("The offline public game list contains duplicate IDs.")
missing_public = sorted(set(PUBLIC_GAME_IDS) - set(offline_by_id))
extra_public = sorted(set(offline_by_id) - set(PUBLIC_GAME_IDS))
if missing_public or extra_public:
    raise RuntimeError(
        f"Offline public game set changed; missing={{missing_public}}, extra={{extra_public}}."
    )

_gate2_expected_ids = list(GATE2_GAME_IDS[:1] if GATE2_COMPARISON_SMOKE else GATE2_GAME_IDS)
_gate2_trial_seconds = (
    GATE2_SMOKE_GAME_SECONDS if GATE2_COMPARISON_SMOKE else GATE2_TRIAL_SECONDS
)
_gate2_trial_specs = [
    {{"trial_id": "seed0-control", "replicate": 0, "arm": "control", "cap": 0, "seed": GATE2_SEEDS[0]}},
    {{"trial_id": "seed0-cap1024", "replicate": 0, "arm": "cap1024", "cap": 1024, "seed": GATE2_SEEDS[0]}},
]
if not GATE2_COMPARISON_SMOKE:
    # Counterbalance arm order in replicate 1 to avoid systematic server-age bias.
    _gate2_trial_specs.extend(
        [
            {{"trial_id": "seed1-cap1024", "replicate": 1, "arm": "cap1024", "cap": 1024, "seed": GATE2_SEEDS[1]}},
            {{"trial_id": "seed1-control", "replicate": 1, "arm": "control", "cap": 0, "seed": GATE2_SEEDS[1]}},
        ]
    )

print(
    "GATE2_PROTOCOL "
    + json.dumps(
        {{
            "games": _gate2_expected_ids,
            "trial_seconds": _gate2_trial_seconds,
            "concurrency": GATE2_CONCURRENCY,
            "trials": _gate2_trial_specs,
            "note": "Budgets are matched; realized token counts are measured, not forced equal.",
        }},
        sort_keys=True,
    ),
    flush=True,
)

_GATE2_ROOT = WORKING_DIR / "gate2-comparison"
_GATE2_ROOT.mkdir(parents=True, exist_ok=True)
_GATE2_PROGRESS_START = time.monotonic()
_gate2_hard_guard_triggered = False
_gate2_benchmark_error = None
_gate2_benchmark_ok = False
_gate2_teardown_error = None
_gate2_teardown_ok = False
_gate2_teardown_attempts = []
_gate2_teardown_result = {{}}
_gate2_post_gpu_rows = []
_gate2_completed_trials = []
_gate2_trial_benchmarks = {{}}


def _gate2_atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\\n")
    _gate2_os.replace(tmp, path)


def _gate2_ratio(numerator, denominator):
    return float(numerator) / float(denominator) if denominator else None


def _gate2_run_snapshot(trial_id, run, trial_started):
    session = _GATE2_SESSION_METRICS.get((trial_id, run.game_id)) or {{}}
    generated_tokens = sum(int(record.generated_tokens) for record in run.history)
    generated_tokens += int(getattr(run, "final_generated_tokens", 0) or 0)
    base_raw = run.base_actions_per_level
    return {{
        "trial_id": trial_id,
        "game_id": run.game_id,
        "state": str(run.state),
        "final_score": float(run.final_score) if run.final_score is not None else None,
        "actions_taken": len(run.history),
        "actions_per_level": [int(value) for value in run.actions_per_level],
        "base_actions_per_level": (
            None if base_raw is None else [int(value) for value in base_raw]
        ),
        "levels_completed": int(run.levels_completed),
        "number_of_levels": int(run.number_of_levels),
        "generated_tokens": generated_tokens,
        "llm_calls": int(session.get("llm_calls", 0)),
        "finish_reason_length": int(session.get("finish_reason_length", 0)),
        "no_op_actions": int(session.get("no_op_actions", 0)),
        "instrumented_actions": int(session.get("instrumented_actions", 0)),
        "active_wall_seconds": session.get("active_wall_seconds"),
        "trial_elapsed_seconds": time.monotonic() - trial_started,
        "notebook_elapsed_seconds": time.monotonic() - _GATE2_PROGRESS_START,
    }}


def _gate2_persist_run(trial_id, run, trial_started, terminal):
    row = _gate2_run_snapshot(trial_id, run, trial_started)
    row["terminal"] = bool(terminal)
    _gate2_atomic_json(_GATE2_ROOT / trial_id / "games" / f"{{run.game_id}}.json", row)
    return row


def _gate2_trial_rows(trial_id):
    rows = []
    for path in sorted((_GATE2_ROOT / trial_id / "games").glob("*.json")):
        try:
            rows.append(json.loads(path.read_text()))
        except Exception as exc:
            print(f"GATE2_PROGRESS_READ_ERROR path={{path}} error={{exc!r}}", flush=True)
    return rows


def _gate2_write_progress_index():
    rows = []
    for spec in _gate2_trial_specs:
        rows.extend(_gate2_trial_rows(spec["trial_id"]))
    _gate2_atomic_json(_GATE2_ROOT / "progress.json", rows)
    jsonl_tmp = _GATE2_ROOT / "progress.jsonl.tmp"
    jsonl_tmp.write_text("".join(json.dumps(row, sort_keys=True) + "\\n" for row in rows))
    _gate2_os.replace(jsonl_tmp, _GATE2_ROOT / "progress.jsonl")
    return rows


def _gate2_flush_trial(trial_id, trial_bm, trial_started):
    for run in list(trial_bm.game_runs):
        terminal = str(run.state) != "playing"
        _gate2_persist_run(trial_id, run, trial_started, terminal=terminal)
    rows = _gate2_write_progress_index()
    try:
        trial_bm._save_json()
    except Exception as exc:
        print(
            f"GATE2_BENCHMARK_SAVE_ERROR trial={{trial_id}} error={{exc!r}}",
            flush=True,
        )
    return rows


async def _gate2_progress_loop(trial_id, trial_bm, trial_started, stop_event):
    emitted = set()
    try:
        while not stop_event.is_set():
            for run in list(trial_bm.game_runs):
                if run.game_id in emitted or str(run.state) == "playing":
                    continue
                row = _gate2_persist_run(trial_id, run, trial_started, terminal=True)
                _gate2_write_progress_index()
                try:
                    trial_bm._save_json()
                except Exception as exc:
                    print(
                        f"GATE2_INCREMENTAL_SAVE_ERROR trial={{trial_id}} error={{exc!r}}",
                        flush=True,
                    )
                emitted.add(run.game_id)
                print(
                    "GATE2_GAME_COMPLETE "
                    + json.dumps(
                        {{
                            "trial_id": trial_id,
                            "game_id": row["game_id"],
                            "state": row["state"],
                            "levels_completed": row["levels_completed"],
                            "actions_taken": row["actions_taken"],
                            "generated_tokens": row["generated_tokens"],
                            "trial_elapsed_seconds": row["trial_elapsed_seconds"],
                        }},
                        sort_keys=True,
                    ),
                    flush=True,
                )
            await _gate2_asyncio.sleep(0.25)
    finally:
        for run in list(trial_bm.game_runs):
            if run.game_id not in emitted and str(run.state) != "playing":
                row = _gate2_persist_run(trial_id, run, trial_started, terminal=True)
                print(
                    "GATE2_GAME_COMPLETE "
                    + json.dumps(
                        {{
                            "trial_id": trial_id,
                            "game_id": row["game_id"],
                            "state": row["state"],
                            "levels_completed": row["levels_completed"],
                            "actions_taken": row["actions_taken"],
                            "generated_tokens": row["generated_tokens"],
                            "trial_elapsed_seconds": row["trial_elapsed_seconds"],
                        }},
                        sort_keys=True,
                    ),
                    flush=True,
                )
        _gate2_write_progress_index()


def _gate2_make_analyzer_factory(spec, solver):
    trial_id = spec["trial_id"]

    def factory(game, index):
        analyzer = _Gate2ToolAgent(
            model=solver.model,
            timeout=solver.analyzer_timeout,
            save_request_logs=solver.save_request_logs,
        )
        analyzer._gate2_trial_id = trial_id
        analyzer._gate2_game_id = getattr(game, "env_name", str(index))
        return analyzer

    return factory


def _gate2_summarize_trial(spec, rows, gpu_seconds):
    actions = sum(int(row["actions_taken"]) for row in rows)
    calls = sum(int(row["llm_calls"]) for row in rows)
    tokens = sum(int(row["generated_tokens"]) for row in rows)
    levels = sum(int(row["levels_completed"]) for row in rows)
    no_ops = sum(int(row["no_op_actions"]) for row in rows)
    length_count = sum(int(row["finish_reason_length"]) for row in rows)
    score = sum(float(row["final_score"] or 0.0) for row in rows) / len(_gate2_expected_ids)
    return {{
        **spec,
        "game_count": len(rows),
        "gpu_seconds": gpu_seconds,
        "weighted_rhae": score,
        "weighted_rhae_per_gpu_second": _gate2_ratio(score, gpu_seconds),
        "generated_tokens": tokens,
        "llm_calls": calls,
        "actions": actions,
        "completed_levels": levels,
        "games_with_progress": sum(int(row["levels_completed"] > 0) for row in rows),
        "games_won": sum(int(row["state"] == "won") for row in rows),
        "tokens_per_call": _gate2_ratio(tokens, calls),
        "actions_per_call": _gate2_ratio(actions, calls),
        "tokens_per_action": _gate2_ratio(tokens, actions),
        "tokens_per_completed_level": _gate2_ratio(tokens, levels),
        "no_op_actions": no_ops,
        "no_op_rate": _gate2_ratio(no_ops, actions),
        "finish_reason_length_count": length_count,
        "finish_reason_length_rate": _gate2_ratio(length_count, calls),
    }}


{helpers}


def _gate2_make_trial_benchmark(spec):
    trial_bm = _gate2_copy.deepcopy(bm)
    trial_bm.label = f"gate2-{{spec['trial_id']}}"
    trial_bm.job_dir = _GATE2_ROOT / spec["trial_id"]
    trial_bm.games = [offline_by_id[game_id] for game_id in _gate2_expected_ids]
    trial_bm.n_passes = 1
    trial_bm.game_weights = None
    trial_bm.solver.max_runtime_s_per_game = _gate2_trial_seconds
    trial_bm.solver.analyzer_timeout = 60.0 if GATE2_COMPARISON_SMOKE else 900.0
    trial_bm.solver.concurrency = GATE2_CONCURRENCY
    trial_bm.solver.max_actions_per_game = GATE2_ACTION_CAP
    trial_bm.solver.save_request_logs = False
    trial_bm.solver.analyzer_factory = _gate2_make_analyzer_factory(spec, trial_bm.solver)
    return trial_bm


async def _gate2_run_trial(spec, global_soft_epoch, global_hard_epoch):
    global _gate2_hard_guard_triggered
    trial_id = spec["trial_id"]
    _gate2_tool_agent_module._LOCAL_ANALYZER_MAX_OUTPUT = int(spec["cap"])
    _gate2_tool_agent_module._LOCAL_ANALYZER_SEED = int(spec["seed"])
    os.environ["LOCAL_ANALYZER_MAX_OUTPUT"] = str(spec["cap"])
    os.environ["LOCAL_ANALYZER_SEED"] = str(spec["seed"])
    trial_bm = _gate2_make_trial_benchmark(spec)
    _gate2_trial_benchmarks[trial_id] = trial_bm
    trial_started = time.monotonic()
    trial_started_epoch = time.time()
    trial_soft_epoch = min(trial_started_epoch + _gate2_trial_seconds, global_soft_epoch)
    trial_hard_epoch = min(trial_soft_epoch + 60.0, global_hard_epoch)
    if trial_soft_epoch <= trial_started_epoch:
        raise TimeoutError(f"No global runtime remains before trial {{trial_id}}.")
    print(
        "GATE2_TRIAL_START "
        + json.dumps(
            {{
                **spec,
                "games": _gate2_expected_ids,
                "soft_end_epoch": trial_soft_epoch,
                "hard_end_epoch": trial_hard_epoch,
            }},
            sort_keys=True,
        ),
        flush=True,
    )
    stop_event = _gate2_asyncio.Event()
    progress_task = _gate2_asyncio.create_task(
        _gate2_progress_loop(trial_id, trial_bm, trial_started, stop_event)
    )
    error = None
    try:
        await _gate2_asyncio.wait_for(
            trial_bm.run(
                soft_end_time=datetime.fromtimestamp(trial_soft_epoch),
                runtime_environment=target,
                minimal_diagnostics=True,
            ),
            timeout=max(1.0, trial_hard_epoch - time.time()),
        )
    except _gate2_asyncio.TimeoutError:
        _gate2_hard_guard_triggered = True
        error = f"Hard runtime guard triggered in {{trial_id}}."
    except Exception as exc:
        error = repr(exc)
    finally:
        stop_event.set()
        await _gate2_asyncio.gather(progress_task, return_exceptions=True)
        _gate2_flush_trial(trial_id, trial_bm, trial_started)

    rows = _gate2_trial_rows(trial_id)
    gpu_seconds = time.monotonic() - trial_started
    problems = []
    row_ids = [row["game_id"] for row in rows]
    if row_ids != sorted(_gate2_expected_ids):
        problems.append(f"coverage ids={{row_ids}}")
    if len(rows) != len(_gate2_expected_ids):
        problems.append(f"coverage count={{len(rows)}}")
    if not all(bool(row.get("terminal")) for row in rows):
        problems.append("non-terminal row")
    if any(row.get("final_score") is None for row in rows):
        problems.append("missing final score")
    if sum(int(row["actions_taken"]) for row in rows) <= 0:
        problems.append("zero actions")
    if error is not None:
        problems.append(error)
    summary = _gate2_summarize_trial(spec, rows, gpu_seconds)
    summary["validation_problems"] = problems
    _gate2_atomic_json(_GATE2_ROOT / trial_id / "summary.json", summary)
    print("GATE2_TRIAL_SUMMARY " + json.dumps(summary, sort_keys=True), flush=True)
    if problems:
        raise RuntimeError(f"Gate 2 trial {{trial_id}} failed validation: {{problems}}")
    _gate2_completed_trials.append(trial_id)
    return summary


if str(BUNDLE_DIR) not in sys.path:
    sys.path.insert(0, str(BUNDLE_DIR))
import vllm_server_watchdog as vllm_watchdog

vllm_watchdog_setup = vllm_watchdog.load_setup(BUNDLE_DIR / "serving_setup.py")
vllm_watchdog.start_background(
    vllm_watchdog_setup,
    vllm_watchdog.WatchdogConfig(
        interval_seconds=15.0,
        request_timeout_seconds=5,
        failure_threshold=4,
        max_restart_attempts=2,
    ),
)

if GATE2_COMPARISON_SMOKE:
    _gate2_global_soft_epoch = (
        GATE1_SERVER_READY_EPOCH + len(_gate2_trial_specs) * _gate2_trial_seconds + 120.0
    )
    _gate2_global_hard_epoch = _gate2_global_soft_epoch + 60.0
else:
    _gate2_budget = float(target.max_runtime_s)
    _gate2_global_hard_epoch = (
        NOTEBOOK_START_EPOCH + _gate2_budget - GATE2_SAFETY_MARGIN_SECONDS
    )
    _gate2_global_soft_epoch = _gate2_global_hard_epoch - GATE2_SOFT_STOP_GRACE_SECONDS

print(
    "GATE2_DEADLINES "
    + json.dumps(
        {{
            "smoke": GATE2_COMPARISON_SMOKE,
            "server_ready_epoch": GATE1_SERVER_READY_EPOCH,
            "startup_seconds": GATE1_SERVER_STARTUP_SECONDS,
            "global_soft_epoch": _gate2_global_soft_epoch,
            "global_hard_epoch": _gate2_global_hard_epoch,
        }},
        sort_keys=True,
    ),
    flush=True,
)

try:
    for _gate2_spec in _gate2_trial_specs:
        _gate2_summary = await _gate2_run_trial(
            _gate2_spec,
            _gate2_global_soft_epoch,
            _gate2_global_hard_epoch,
        )
except Exception as exc:
    _gate2_benchmark_error = repr(exc)
    print(f"GATE2_BENCHMARK_EXCEPTION {{_gate2_benchmark_error}}", flush=True)
finally:
    _gate2_write_progress_index()

try:
    if _gate2_benchmark_error is None:
        import pandas as pd

        pd.DataFrame(
            [["1_0", "1", True, 1]],
            columns=["row_id", "game_id", "end_of_game", "score"],
        ).to_parquet(WORKING_DIR / "submission.parquet", index=False)
        _gate2_benchmark_ok = True
except Exception as exc:
    _gate2_benchmark_error = repr(exc)
    _gate2_benchmark_ok = False
    print(f"GATE2_BENCHMARK_VALIDATION_EXCEPTION {{_gate2_benchmark_error}}", flush=True)
finally:
    _gate2_write_progress_index()

try:
    vllm_watchdog.stop_background(timeout_seconds=15.0)
except Exception as exc:
    print(f"GATE2_WATCHDOG_STOP_ERROR {{exc!r}}", flush=True)

try:
    _gate2_teardown_ok, _gate2_teardown_result, _gate2_post_gpu_rows = (
        _gate2_teardown_with_recovery()
    )
    if not _gate2_teardown_ok:
        _gate2_teardown_error = "bounded terminal gate did not pass after recovery"
except Exception as exc:
    _gate2_teardown_error = repr(exc)
    _gate2_teardown_ok = False
    _gate2_post_gpu_rows = _gate2_gpu_rows()

_gate2_lifecycle = {{
    "smoke_mode": GATE2_COMPARISON_SMOKE,
    "benchmark_ok": _gate2_benchmark_ok,
    "benchmark_error": _gate2_benchmark_error,
    "completed_trials": _gate2_completed_trials,
    "expected_trials": [spec["trial_id"] for spec in _gate2_trial_specs],
    "teardown_ok": _gate2_teardown_ok,
    "teardown_error": _gate2_teardown_error,
    "hard_guard_triggered": _gate2_hard_guard_triggered,
    "teardown_attempts": _gate2_teardown_attempts,
    "post_teardown_gpu_rows": _gate2_post_gpu_rows,
    "elapsed_seconds": time.monotonic() - _GATE2_PROGRESS_START,
}}
_gate2_atomic_json(_GATE2_ROOT / "lifecycle.json", _gate2_lifecycle)
print(
    "GATE2_LIFECYCLE "
    + json.dumps(
        {{
            "benchmark": "ok" if _gate2_benchmark_ok else "failed",
            "benchmark_error": _gate2_benchmark_error,
            "completed_trials": _gate2_completed_trials,
            "teardown": "ok" if _gate2_teardown_ok else "failed",
            "teardown_error": _gate2_teardown_error,
            "hard_guard_triggered": _gate2_hard_guard_triggered,
            "post_teardown_gpu_rows": _gate2_post_gpu_rows,
            "elapsed_seconds": _gate2_lifecycle["elapsed_seconds"],
        }},
        sort_keys=True,
    ),
    flush=True,
)
'''


def audit_cell() -> str:
    return '''# Gate 2 terminal audit. Never raise past persisted measurement data.
import json as _g2_json
import subprocess as _g2_subprocess

_g2_lifecycle_path = _GATE2_ROOT / "lifecycle.json"
_g2_lifecycle = (
    _g2_json.loads(_g2_lifecycle_path.read_text())
    if _g2_lifecycle_path.is_file()
    else {"benchmark_ok": False, "teardown_ok": False, "error": "lifecycle artifact missing"}
)
_g2_rows = _gate2_write_progress_index()
for _g2_row in _g2_rows:
    print("GATE2_GAME_TRACE " + _g2_json.dumps(_g2_row, sort_keys=True), flush=True)

_g2_trial_summaries = []
for _g2_spec in _gate2_trial_specs:
    _g2_path = _GATE2_ROOT / _g2_spec["trial_id"] / "summary.json"
    if _g2_path.is_file():
        _g2_trial_summaries.append(_g2_json.loads(_g2_path.read_text()))
for _g2_summary in _g2_trial_summaries:
    print("GATE2_TRIAL_RESULT " + _g2_json.dumps(_g2_summary, sort_keys=True), flush=True)

_g2_arm_summary = {}
for _g2_arm in ("control", "cap1024"):
    _g2_members = [row for row in _g2_trial_summaries if row["arm"] == _g2_arm]
    _g2_gpu = sum(float(row["gpu_seconds"]) for row in _g2_members)
    _g2_score_sum = sum(float(row["weighted_rhae"]) for row in _g2_members)
    _g2_arm_summary[_g2_arm] = {
        "replicates": len(_g2_members),
        "weighted_rhae_mean": _g2_score_sum / len(_g2_members) if _g2_members else None,
        "gpu_seconds_total": _g2_gpu,
        "weighted_rhae_sum_per_gpu_second": _g2_score_sum / _g2_gpu if _g2_gpu else None,
        "generated_tokens": sum(int(row["generated_tokens"]) for row in _g2_members),
        "llm_calls": sum(int(row["llm_calls"]) for row in _g2_members),
        "actions": sum(int(row["actions"]) for row in _g2_members),
        "completed_levels": sum(int(row["completed_levels"]) for row in _g2_members),
        "games_with_progress": sum(int(row["games_with_progress"]) for row in _g2_members),
        "finish_reason_length_count": sum(
            int(row["finish_reason_length_count"]) for row in _g2_members
        ),
        "no_op_actions": sum(int(row["no_op_actions"]) for row in _g2_members),
    }
    _g2_agg = _g2_arm_summary[_g2_arm]
    _g2_agg["tokens_per_call"] = _gate2_ratio(_g2_agg["generated_tokens"], _g2_agg["llm_calls"])
    _g2_agg["actions_per_call"] = _gate2_ratio(_g2_agg["actions"], _g2_agg["llm_calls"])
    _g2_agg["tokens_per_action"] = _gate2_ratio(_g2_agg["generated_tokens"], _g2_agg["actions"])
    _g2_agg["tokens_per_completed_level"] = _gate2_ratio(
        _g2_agg["generated_tokens"], _g2_agg["completed_levels"]
    )
    _g2_agg["finish_reason_length_rate"] = _gate2_ratio(
        _g2_agg["finish_reason_length_count"], _g2_agg["llm_calls"]
    )
    _g2_agg["no_op_rate"] = _gate2_ratio(_g2_agg["no_op_actions"], _g2_agg["actions"])

_g2_pairs = []
for _g2_replicate in sorted({int(spec["replicate"]) for spec in _gate2_trial_specs}):
    _g2_control = next(
        (row for row in _g2_trial_summaries if row["replicate"] == _g2_replicate and row["arm"] == "control"),
        None,
    )
    _g2_candidate = next(
        (row for row in _g2_trial_summaries if row["replicate"] == _g2_replicate and row["arm"] == "cap1024"),
        None,
    )
    if _g2_control and _g2_candidate:
        _g2_pairs.append(
            {
                "replicate": _g2_replicate,
                "seed": _g2_control["seed"],
                "control_weighted_rhae_per_gpu_second": _g2_control["weighted_rhae_per_gpu_second"],
                "candidate_weighted_rhae_per_gpu_second": _g2_candidate["weighted_rhae_per_gpu_second"],
                "ratio": _gate2_ratio(
                    _g2_candidate["weighted_rhae_per_gpu_second"],
                    _g2_control["weighted_rhae_per_gpu_second"],
                ),
                "control_games_with_progress": _g2_control["games_with_progress"],
                "candidate_games_with_progress": _g2_candidate["games_with_progress"],
            }
        )

_g2_comparison = {"arms": _g2_arm_summary, "paired": _g2_pairs}
_gate2_atomic_json(_GATE2_ROOT / "comparison.json", _g2_comparison)
print("GATE2_COMPARISON " + _g2_json.dumps(_g2_comparison, sort_keys=True), flush=True)

_g2_submission_path = WORKING_DIR / "submission.parquet"
_g2_schema_ok = False
_g2_schema = {"exists": _g2_submission_path.is_file()}
if _g2_submission_path.is_file():
    import pandas as _g2_pd

    _g2_submission = _g2_pd.read_parquet(_g2_submission_path)
    _g2_schema.update({
        "columns": list(_g2_submission.columns),
        "rows": len(_g2_submission),
        "dtypes": {column: str(dtype) for column, dtype in _g2_submission.dtypes.items()},
    })
    _g2_schema_ok = list(_g2_submission.columns) == [
        "row_id", "game_id", "end_of_game", "score"
    ]
print("GATE2_SUBMISSION_SCHEMA " + _g2_json.dumps(_g2_schema, sort_keys=True), flush=True)

_g2_nvidia = _g2_subprocess.run(
    ["nvidia-smi"], capture_output=True, text=True, check=False, timeout=10.0
)
print("GATE2_POST_NVIDIA_SMI_BEGIN", flush=True)
print(_g2_nvidia.stdout, flush=True)
print(_g2_nvidia.stderr, flush=True)
print("GATE2_POST_NVIDIA_SMI_END", flush=True)

_g2_expected_trial_ids = [spec["trial_id"] for spec in _gate2_trial_specs]
_g2_expected_row_count = len(_gate2_expected_ids) * len(_gate2_trial_specs)
_g2_clean = bool(
    _g2_lifecycle.get("benchmark_ok")
    and _g2_lifecycle.get("teardown_ok")
    and not _g2_lifecycle.get("hard_guard_triggered")
    and _g2_lifecycle.get("completed_trials") == _g2_expected_trial_ids
    and len(_g2_rows) == _g2_expected_row_count
    and all(bool(row.get("terminal")) for row in _g2_rows)
    and len(_g2_trial_summaries) == len(_gate2_trial_specs)
    and _g2_schema_ok
    and not _g2_lifecycle.get("post_teardown_gpu_rows")
)
print(
    "GATE2_FINAL_STATUS "
    + _g2_json.dumps(
        {
            "benchmark": "ok" if _g2_lifecycle.get("benchmark_ok") else "failed",
            "teardown": "ok" if _g2_lifecycle.get("teardown_ok") else "failed",
            "teardown_error": _g2_lifecycle.get("teardown_error"),
            "logical_exit_code": 0 if _g2_clean else 1,
            "post_teardown_gpu_rows": _g2_lifecycle.get("post_teardown_gpu_rows"),
            "smoke_mode": GATE2_COMPARISON_SMOKE,
        },
        sort_keys=True,
    ),
    flush=True,
)
if GATE2_COMPARISON_SMOKE:
    print("GATE2_COMPARISON_SMOKE_OK" if _g2_clean else "GATE2_COMPARISON_SMOKE_FAILED", flush=True)
else:
    print("GATE2_COMPARISON_OK" if _g2_clean else "GATE2_COMPARISON_FAILED", flush=True)
'''


def validate_python(notebook: dict) -> None:
    failures: list[str] = []
    count = 0
    for index, cell in enumerate(notebook.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        count += 1
        source = source_text(cell)
        cleaned = "\n".join(
            "" if line.lstrip().startswith(("!", "%", "?")) else line
            for line in source.splitlines()
        )
        try:
            ast.parse(cleaned)
        except SyntaxError as exc:
            failures.append(f"cell {index}, line {exc.lineno}: {exc.msg}")
    if failures:
        raise RuntimeError("generated notebook does not parse: " + "; ".join(failures))
    print(f"PARSE OK: {count} code cells")


def build(smoke: bool, output: Path) -> None:
    notebook = json.loads(SOURCE.read_text())
    first = cell_with_prefix(notebook, "import json")
    first_source = source_text(first)
    first_source = replace_once(
        first_source,
        "# Gate 2 response-cap ablation. This is the only policy change from immutable Version 7.\n"
        "GATE2_RESPONSE_TOKEN_CAP = 1024\n"
        'os.environ["LOCAL_ANALYZER_MAX_OUTPUT"] = str(GATE2_RESPONSE_TOKEN_CAP)\n'
        'print(f"GATE2_RESPONSE_TOKEN_CAP={GATE2_RESPONSE_TOKEN_CAP}", flush=True)\n',
        "# Gate 2 imports the analyzer at the control setting; each sequential trial then "
        "sets its own cap and paired seed before constructing agents.\n"
        'os.environ["LOCAL_ANALYZER_MAX_OUTPUT"] = "0"\n'
        'os.environ["LOCAL_ANALYZER_SEED"] = "-1"\n',
        "initial analyzer settings",
    )
    set_source(first, first_source)

    set_source(
        cell_with_prefix(notebook, "# Gate 1 production path with a minimum-scale lifecycle smoke switch."),
        instrumentation_cell(smoke),
    )
    set_source(
        cell_with_prefix(
            notebook,
            "# Build the live competition game list from the gateway's available environments.",
        ),
        experiment_cell(notebook),
    )
    set_source(
        cell_with_prefix(
            notebook,
            "# Gate 1 terminal audit. This cell reports independent benchmark and teardown facts.",
        ),
        audit_cell(),
    )

    notebook["cells"][0]["source"] = [
        "# ARC-AGI-3 Gate 2 response-cap comparison\n",
        "\n",
        (
            "Minimum-scale paired lifecycle smoke. "
            if smoke
            else "Full paired eight-game comparison. "
        ),
        "Control and 1024-token-cap arms share one production vLLM session. "
        "This notebook never submits to the competition.\n",
    ]
    validate_python(notebook)
    output.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n")
    print(f"WROTE {output}")


def main() -> None:
    actual_source_sha = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if actual_source_sha != SOURCE_SHA256:
        raise RuntimeError(
            f"passing Version 11 source changed: expected {SOURCE_SHA256}, "
            f"got {actual_source_sha}"
        )
    build(True, OUTPUT_SMOKE)
    build(False, OUTPUT_FULL)


if __name__ == "__main__":
    main()

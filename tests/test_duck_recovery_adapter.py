"""Host-boundary checks for the opt-in recovery treatment (no GPU)."""

from __future__ import annotations

import sys
from pathlib import Path
import json

import pytest


DUCK_SOURCE = Path(__file__).resolve().parents[2] / "duck-harness-source" / "ARC3-Inference"
if DUCK_SOURCE.is_dir():
    sys.path.insert(0, str(DUCK_SOURCE))
pytest.importorskip("inference.agent.tool_agent")

from arc3.duck_recovery_adapter import RecoveryToolAgent  # noqa: E402
from arc3.recovery import StallSignal  # noqa: E402
from inference.agent.runtime_state import Frame, HistoryEntry, write_runtime_state  # noqa: E402


def _frame(step: int, border: int, level: int = 1) -> Frame:
    grid = ((border, border, border), (border, 0, border),
            (border, border, border))
    return Frame(grid=grid, step=step, level=level)


def test_recovery_prompt_is_shown_once_after_border_only_repetitions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("LOCAL_ANALYZER_MODEL_ID", "test-model")
    monkeypatch.setenv("LOCAL_ANALYZER_BASE_URL", "http://127.0.0.1:8000/v1")
    monkeypatch.setenv("ARC3_RECOVERY_ACTION_LIMIT", "0")
    monkeypatch.setenv("ARC3_RECOVERY_WALL_SECONDS", "inf")
    history = [HistoryEntry(action="", frame=_frame(0, 0))]
    history.extend(HistoryEntry(action="RIGHT", frame=_frame(i, i))
                   for i in range(1, 5))
    path = tmp_path / "state.json"
    write_runtime_state(path, current_frame=history[-1].frame, history=history)
    agent = RecoveryToolAgent(model="qwen")
    agent._gate2_game_id = "test-game"
    agent._ensure_session(path)
    args = {
        "valid_actions": ["ACTION4"],
        "current_frame": history[-1].frame,
        "history_entries": history,
        "previous_step_summary": None,
    }
    first = agent._build_user_prompt(4, **args)
    second = agent._build_user_prompt(4, **args)
    assert "RECOVERY CHECKPOINT" in first
    assert "RECOVERY CHECKPOINT" not in second
    assert agent._recovery_prompt_count == 1
    assert agent._recovery_last_reason == "repeated_interior_noop"


def test_repeat_only_mode_never_falls_back_to_action_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("LOCAL_ANALYZER_MODEL_ID", "test-model")
    monkeypatch.setenv("LOCAL_ANALYZER_BASE_URL", "http://127.0.0.1:8000/v1")
    monkeypatch.setenv("ARC3_RECOVERY_ACTION_LIMIT", "0")
    monkeypatch.setenv("ARC3_RECOVERY_WALL_SECONDS", "inf")
    history = [HistoryEntry(action="", frame=_frame(0, 0))]
    history.extend(HistoryEntry(
        action="RIGHT",
        frame=Frame(grid=((0, 0, 0), (0, i % 16, 0), (0, 0, 0)),
                    step=i, level=1),
    ) for i in range(1, 82))
    path = tmp_path / "state.json"
    write_runtime_state(path, current_frame=history[-1].frame, history=history)
    agent = RecoveryToolAgent(model="qwen")
    agent._ensure_session(path)
    prompt = agent._build_user_prompt(
        81, valid_actions=["ACTION4"], current_frame=history[-1].frame,
        history_entries=history, previous_step_summary=None,
    )
    assert "RECOVERY CHECKPOINT" not in prompt


def test_normal_turn_does_not_change_the_prompt_or_require_a_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("LOCAL_ANALYZER_MODEL_ID", "test-model")
    monkeypatch.setenv("LOCAL_ANALYZER_BASE_URL", "http://127.0.0.1:8000/v1")
    history = [HistoryEntry(action="", frame=_frame(0, 0))]
    history.extend(HistoryEntry(
        action="RIGHT",
        frame=Frame(grid=((0, 0, 0), (0, i, 0), (0, 0, 0)), step=i, level=1),
    ) for i in range(1, 5))
    path = tmp_path / "state.json"
    write_runtime_state(path, current_frame=history[-1].frame, history=history)
    agent = RecoveryToolAgent(model="qwen")
    agent._gate2_game_id = "test-game"
    agent._ensure_session(path)
    prompt = agent._build_user_prompt(
        4, valid_actions=["ACTION4"], current_frame=history[-1].frame,
        history_entries=history, previous_step_summary=None,
    )
    assert "RECOVERY CHECKPOINT" not in prompt
    assert agent._recovery_prompt_count == 0


def test_recovery_executes_only_declared_probe_and_persists_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("LOCAL_ANALYZER_MODEL_ID", "test-model")
    monkeypatch.setenv("LOCAL_ANALYZER_BASE_URL", "http://127.0.0.1:8000/v1")
    first = HistoryEntry(action="", frame=_frame(0, 0))
    path = tmp_path / "state.json"
    write_runtime_state(path, current_frame=first.frame, history=[first])
    agent = RecoveryToolAgent(model="qwen")
    agent._ensure_session(path)
    agent._current_valid_actions = ["RIGHT"]
    agent._recovery_pending = True
    agent._recovery_signal = StallSignal(1, "time_without_completion", 0, 0, None, 0, 180)

    def step(payload):
        assert payload == {"actions": [{"action": "RIGHT"}]}
        second = HistoryEntry(action="RIGHT", frame=_frame(1, 1))
        write_runtime_state(path, current_frame=second.frame, history=[first, second])
        return {"executed": True, "action_display": "RIGHT", "board_changed": True}

    agent._step_env_callback = step
    probe = {
        "goal_predicate": "center tile changes",
        "hypotheses": [
            {"explanation": "RIGHT moves", "observed_evidence": "older move",
             "predicted_outcome": "moves"},
            {"explanation": "RIGHT waits", "observed_evidence": "older stall",
             "predicted_outcome": "stays"},
        ],
        "action": {"action": "RIGHT"},
        "next_if_first": "continue", "next_if_second": "change direction",
    }
    rejected = agent._run_python_tool(path, {"code": "action(['LEFT'])", "recovery_probe": probe})
    assert not rejected.step_executed
    assert agent._recovery_probe_count == 0
    accepted = agent._run_python_tool(path, {"code": "action(['RIGHT'])", "recovery_probe": probe})
    assert accepted.step_executed
    assert agent._recovery_probe_count == 1
    event = json.loads(agent._recovery_event_path.read_text().splitlines()[0])
    assert event["probe"]["action"] == {"action": "RIGHT"}
    assert event["actual_action"] == "RIGHT"
    assert event["before"]["step"] == 0
    assert event["after"]["step"] == 1

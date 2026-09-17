"""Tests at Duck's real host/sandbox boundary (no model or GPU required)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


DUCK_SOURCE = Path(__file__).resolve().parents[2] / "duck-harness-source" / "ARC3-Inference"
if DUCK_SOURCE.is_dir():
    sys.path.insert(0, str(DUCK_SOURCE))
pytest.importorskip("inference.agent.tool_agent")

from arc3.duck_memory_adapter import MemoryToolAgent, known_transition_ids, parse_memory_update
from arc3.memory import MemoryJournal, Status
from inference.agent.runtime_state import Frame, HistoryEntry, write_runtime_state


def _frame(step: int, level: int = 1) -> Frame:
    return Frame(grid=((0, 1), (2, 3)), step=step, level=level)


def _state(path: Path, level: int = 1, actions: int = 0) -> None:
    history = [HistoryEntry(action="", frame=_frame(0))]
    history.extend(HistoryEntry(action="ACTION1", frame=_frame(i, level))
                   for i in range(1, actions + 1))
    write_runtime_state(path, current_frame=_frame(actions, level), history=history)


def _agent(path: Path, monkeypatch: pytest.MonkeyPatch) -> MemoryToolAgent:
    monkeypatch.setenv("LOCAL_ANALYZER_MODEL_ID", "test-model")
    monkeypatch.setenv("LOCAL_ANALYZER_BASE_URL", "http://127.0.0.1:8000/v1")
    agent = MemoryToolAgent(model="qwen")
    agent._gate2_game_id = "test-game"
    agent._ensure_session(path)
    agent._current_valid_actions = ["ACTION1"]
    return agent


def test_parser_rejects_unexpected_shape_and_ungrounded_confirmation():
    with pytest.raises(ValueError, match="unknown memory_update"):
        parse_memory_update({"untrusted": 1})
    with pytest.raises(ValueError, match="without evidence"):
        parse_memory_update({"mechanics": [{"statement": "A moves", "status": "CONFIRMED"}]})
    with pytest.raises(ValueError, match="expected outcome"):
        parse_memory_update({"winning_paths": [{
            "level": 1, "start_signature": "hash", "actions": [[1, None, None]],
            "expected_outcomes": [], "evidence": [0],
        }]})


def test_history_indices_match_the_tool_visible_transitions(tmp_path: Path):
    path = tmp_path / "state.json"
    _state(path, actions=2)
    assert known_transition_ids(path) == {0, 1}


def test_update_is_fsynced_before_action_and_survives_level_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    path = tmp_path / "state.json"
    _state(path, actions=1)
    agent = _agent(path, monkeypatch)
    journal = path.with_suffix(".memory.jsonl")

    def action_callback(_payload):
        restored = MemoryJournal(journal).restore()
        assert restored is not None
        assert restored.mechanics[0].statement == "ACTION1 moves the blue piece"
        assert restored.current_plan == [(1, None, None)]
        write_runtime_state(
            path,
            current_frame=_frame(2, level=2),
            history=[
                HistoryEntry(action="", frame=_frame(0)),
                HistoryEntry(action="ACTION1", frame=_frame(1)),
                HistoryEntry(action="ACTION1", frame=_frame(2, level=2)),
            ],
        )
        return {
            "executed": True, "action_num": 2, "level": 2,
            "level_completed": True, "valid_actions": ["ACTION1"],
            "board_changed": True, "state": "NOT_FINISHED",
        }

    agent._step_env_callback = action_callback
    result = agent._run_python_tool(path, {
        "code": 'action("ACTION1")',
        "memory_update": {
            "mechanics": [{
                "statement": "ACTION1 moves the blue piece", "status": "CONFIRMED", "evidence": [0],
            }],
            "current_plan": [[1, None, None]],
        },
    })
    assert result.step_executed
    restored = MemoryJournal(journal).restore()
    assert restored is not None
    assert restored.level == 2
    assert restored.mechanics[0].status is Status.CONFIRMED
    assert restored.current_plan == []
    assert [row["event"] for row in MemoryJournal(journal).entries()] == [
        "update", "level_transition",
    ]


def test_bad_evidence_rejects_tool_before_any_environment_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    path = tmp_path / "state.json"
    _state(path, actions=1)
    agent = _agent(path, monkeypatch)
    called = []
    agent._step_env_callback = lambda payload: called.append(payload)
    result = agent._run_python_tool(path, {
        "code": 'action("ACTION1")',
        "memory_update": {
            "mechanics": [{
                "statement": "A moves", "status": "CONFIRMED", "evidence": [999],
            }],
        },
    })
    assert "do not exist" in json.loads(result.content)["error"]
    assert called == []
    assert not path.with_suffix(".memory.jsonl").exists()


def test_empty_update_does_not_create_a_false_memory_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    path = tmp_path / "state.json"
    _state(path)
    agent = _agent(path, monkeypatch)
    result = agent._run_python_tool(path, {"code": "result = 1", "memory_update": {}})
    assert json.loads(result.content)["returncode"] == 0
    assert agent._memory_commits == 0
    assert agent._memory_empty_updates == 1
    assert agent._memory_missing_updates == 0
    assert not path.with_suffix(".memory.jsonl").exists()


def test_missing_update_is_counted_without_blocking_an_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    path = tmp_path / "state.json"
    _state(path)
    agent = _agent(path, monkeypatch)
    result = agent._run_python_tool(path, {"code": "result = 1"})
    assert json.loads(result.content)["returncode"] == 0
    assert agent._memory_missing_updates == 1
    assert agent._memory_empty_updates == 0


def test_level_sync_recovers_action_completed_before_transition_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    path = tmp_path / "state.json"
    _state(path)
    agent = _agent(path, monkeypatch)
    agent._memory.mechanics.append(parse_memory_update({"mechanics": [
        {"statement": "ACTION1 moves the blue piece", "status": "ASSUMED"}
    ]}).mechanics[0])
    # Simulate a crash after the game state advanced but before our transition hook ran.
    _state(path, level=2, actions=1)
    agent._ensure_session(path)
    assert agent._memory.level == 2
    assert agent._memory.mechanics[0].statement == "ACTION1 moves the blue piece"
    assert [row["event"] for row in MemoryJournal(path.with_suffix(".memory.jsonl")).entries()] == [
        "level_transition"
    ]


def test_prompt_carries_memory_but_marks_only_real_transition_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    path = tmp_path / "state.json"
    _state(path, actions=1)
    agent = _agent(path, monkeypatch)
    agent._memory.mechanics.append(parse_memory_update({"mechanics": [
        {"statement": "ACTION1 moves the blue piece", "status": "ASSUMED"}
    ]}).mechanics[0])
    from inference.agent.runtime_state import load_runtime_state
    frame, history = load_runtime_state(path)
    prompt = agent._build_user_prompt(
        1, valid_actions=["ACTION1"], current_frame=frame,
        history_entries=history,
    )
    assert "ACTION1 moves the blue piece" in prompt
    assert "latest available transition index is 0" in prompt
    assert "memory_update" in prompt
    assert "Every python tool call must include memory_update" in prompt
    assert '"status":"ASSUMED"' in prompt
    schema = agent._tools(path)[0]["function"]["parameters"]
    assert schema["required"] == ["code", "memory_update"]

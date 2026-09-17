"""The replay must use action events and evaluate only at analysis boundaries."""

import json

from research.replay_recovery_triggers import first_action_trigger


def test_first_trigger_ignores_non_action_events(tmp_path):
    board = [[0] * 4 for _ in range(4)]
    events = [{"type": "initial", "board": board, "level": 1,
               "action_display": "RESET", "action_num": 0}]
    for action_num in range(1, 5):
        events.append({"type": "action", "board": board, "level": 1,
                       "action_display": "RIGHT", "action_num": action_num})
        events.append({"type": "analysis", "board": board, "level": 1,
                       "action_num": action_num})
    path = tmp_path / "game_events.jsonl"
    path.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
    result = first_action_trigger(path)
    assert result["analysis_action_num"] == 4
    assert result["signal"]["reason"] == "repeated_interior_noop"
    assert result["signal"]["actions_on_level"] == 4

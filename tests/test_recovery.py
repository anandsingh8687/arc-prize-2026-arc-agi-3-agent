"""The recovery trigger is advisory and scoped to the level being played."""

from types import SimpleNamespace

import pytest

from arc3.recovery import detect_stall, recovery_instruction, validate_recovery_probe


def entry(action: str, grid: tuple[tuple[int, ...], ...], level: int = 1):
    return SimpleNamespace(action=action, frame=SimpleNamespace(grid=grid, level=level))


def board(center: int = 0, border: int = 0):
    return ((border, border, border), (border, center, border),
            (border, border, border))


def test_repeated_apparent_noop_can_be_border_only_and_never_vetoes_action():
    history = [entry("", board())]
    history.extend(entry("RIGHT", board(border=i)) for i in range(1, 5))
    signal = detect_stall(history)
    assert signal is not None
    assert signal.reason == "repeated_interior_noop"
    assert signal.repeated_in_last_ten == 3
    assert signal.border_only_changes == 4
    instruction = recovery_instruction(signal)
    assert "border cells may encode a timer" in instruction
    assert "Do not blindly forbid" in instruction
    assert "DIFFERENT outcomes" in instruction


def test_no_progress_trigger_catches_games_without_noops():
    history = [entry("", board())]
    history.extend(entry("RIGHT", board(center=i + 1)) for i in range(80))
    signal = detect_stall(history)
    assert signal is not None
    assert signal.reason == "no_level_completion"
    assert signal.actions_on_level == 80
    assert signal.repeated_in_last_ten == 0


def test_level_transition_resets_budget_and_later_threshold_is_80():
    history = [entry("", board())]
    history.extend(entry("RIGHT", board(center=i + 1)) for i in range(50))
    history.append(entry("RIGHT", board(center=1), level=2))
    history.extend(entry("RIGHT", board(center=i + 2), level=2) for i in range(79))
    assert detect_stall(history) is None
    history.append(entry("RIGHT", board(center=81), level=2))
    signal = detect_stall(history)
    assert signal is not None
    assert signal.level == 2
    assert signal.actions_on_level == 80


def test_no_signal_on_short_productive_history():
    history = [entry("", board())]
    history.extend(entry("RIGHT", board(center=i + 1)) for i in range(20))
    assert detect_stall(history) is None


def probe():
    return {
        "goal_predicate": "The red tile changes when the player reaches it",
        "hypotheses": [
            {"explanation": "RIGHT moves", "observed_evidence": "step 2 moved red",
             "predicted_outcome": "red moves right"},
            {"explanation": "RIGHT waits", "observed_evidence": "step 3 did not move red",
             "predicted_outcome": "red stays"},
        ],
        "action": {"action": "RIGHT"},
        "next_if_first": "continue right once",
        "next_if_second": "try UP",
    }


def test_probe_requires_two_distinct_predictions_and_legal_one_action():
    valid = probe()
    assert validate_recovery_probe(valid, ["RIGHT"]) == valid
    valid["hypotheses"][1]["predicted_outcome"] = "red moves right"
    with pytest.raises(ValueError, match="different predicted outcomes"):
        validate_recovery_probe(valid, ["RIGHT"])
    valid = probe()
    with pytest.raises(ValueError, match="not currently legal"):
        validate_recovery_probe(valid, ["LEFT"])

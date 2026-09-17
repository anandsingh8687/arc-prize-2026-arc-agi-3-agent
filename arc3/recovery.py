"""Cheap, advisory stall detection for Duck's per-game history.

The interior-only comparison is deliberately not a state-equivalence claim:
border cells may be causal. A signal asks the actor to re-evaluate a hypothesis;
it must never veto an environment action or declare a game unsolvable.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
from typing import Any, Sequence


@dataclass(frozen=True)
class StallSignal:
    level: int
    reason: str
    actions_on_level: int
    repeated_in_last_ten: int
    repeated_action: str | None
    border_only_changes: int
    elapsed_seconds: float = 0.0


def validate_recovery_probe(raw: Any, valid_actions: Sequence[str]) -> dict[str, Any]:
    """Validate a proposed *single* discriminating action before it is charged.

    This checks structure and legality, not whether the hypotheses are true. The
    subsequent environment transition is recorded and must be inspected when
    deciding whether recovery actually helped.
    """
    if not isinstance(raw, dict) or set(raw) != {
        "goal_predicate", "hypotheses", "action", "next_if_first", "next_if_second"
    }:
        raise ValueError("recovery_probe needs goal_predicate, hypotheses, action and two next steps")
    goal = raw["goal_predicate"]
    hypotheses = raw["hypotheses"]
    action = raw["action"]
    if not isinstance(goal, str) or not goal.strip():
        raise ValueError("goal_predicate must be non-empty")
    if not isinstance(hypotheses, list) or len(hypotheses) != 2:
        raise ValueError("exactly two hypotheses are required")
    for hypothesis in hypotheses:
        if not isinstance(hypothesis, dict) or set(hypothesis) != {
            "explanation", "observed_evidence", "predicted_outcome"
        }:
            raise ValueError("each hypothesis needs explanation, observed_evidence, predicted_outcome")
        if any(not isinstance(value, str) or not value.strip() for value in hypothesis.values()):
            raise ValueError("hypothesis fields must be non-empty strings")
    if hypotheses[0]["predicted_outcome"].strip().casefold() == hypotheses[1]["predicted_outcome"].strip().casefold():
        raise ValueError("the probe must distinguish two different predicted outcomes")
    if not isinstance(action, dict) or not set(action) <= {"action", "row", "col"}:
        raise ValueError("action must be an action object")
    name = action.get("action")
    if not isinstance(name, str) or name not in valid_actions:
        raise ValueError(f"probe action {name!r} is not currently legal")
    if name == "MOUSE":
        if set(action) != {"action", "row", "col"}:
            raise ValueError("MOUSE probe needs row and col")
        if any(type(action[key]) is not int or not 0 <= action[key] <= 63 for key in ("row", "col")):
            raise ValueError("MOUSE coordinates must be integers in 0..63")
    elif set(action) != {"action"}:
        raise ValueError("non-MOUSE probe must not include coordinates")
    for key in ("next_if_first", "next_if_second"):
        if not isinstance(raw[key], str) or not raw[key].strip():
            raise ValueError(f"{key} must be a non-empty conditional plan")
    return raw


def _digest(grid: Sequence[Sequence[int]], *, interior: bool) -> bytes:
    rows = grid[1:-1] if interior and len(grid) > 2 else grid
    digest = hashlib.blake2b(digest_size=12)
    digest.update(len(rows).to_bytes(2, "little"))
    for row in rows:
        cells = row[1:-1] if interior and len(row) > 2 else row
        digest.update(len(cells).to_bytes(2, "little"))
        digest.update(bytes(cells))
    return digest.digest()


def detect_stall(
    history: Sequence[Any], *, first_level_limit: int = 80,
    later_level_limit: int = 80, repeat_threshold: int = 3,
) -> StallSignal | None:
    """Inspect history entries with ``action`` and ``frame.grid/level`` fields.

    Returns one current-level signal or ``None``. The caller decides whether
    it has already shown this signal and whether to spend an LLM call on it.
    """
    if len(history) < 2:
        return None
    level = int(history[-1].frame.level)
    start = len(history) - 1
    while start > 0 and int(history[start - 1].frame.level) == level:
        start -= 1
    # The first entry for a new level is the *result* of completing the prior
    # level; it is not an action charged to this level.
    actions_on_level = len(history) - start - 1
    seen_noops: set[tuple[bytes, str]] = set()
    recent: deque[int] = deque(maxlen=10)
    repeated_action = None
    border_only_changes = 0
    for index in range(start + 1, len(history)):
        before = history[index - 1].frame.grid
        after = history[index].frame.grid
        action = str(history[index].action)
        inner_before = _digest(before, interior=True)
        inner_after = _digest(after, interior=True)
        inner_unchanged = inner_before == inner_after
        if inner_unchanged and _digest(before, interior=False) != _digest(after, interior=False):
            border_only_changes += 1
        key = (inner_before, action)
        repeated = inner_unchanged and key in seen_noops
        if inner_unchanged:
            seen_noops.add(key)
        if repeated:
            repeated_action = action
        recent.append(int(repeated))
    repeats = sum(recent)
    if repeats >= repeat_threshold:
        reason = "repeated_interior_noop"
    elif actions_on_level >= (first_level_limit if level == 1 else later_level_limit):
        reason = "no_level_completion"
    else:
        return None
    return StallSignal(
        level=level,
        reason=reason,
        actions_on_level=actions_on_level,
        repeated_in_last_ten=repeats,
        repeated_action=repeated_action,
        border_only_changes=border_only_changes,
    )


def recovery_instruction(signal: StallSignal) -> str:
    """A decision-changing prompt, not an unbounded request to think harder."""
    if signal.reason == "time_without_completion":
        observation = (
            f"{signal.elapsed_seconds:.1f} seconds on level {signal.level} "
            f"without completing it"
        )
    elif signal.reason == "repeated_interior_noop":
        observation = (
            f"{signal.repeated_in_last_ten} repeated apparent no-effects "
            "in the last 10 actions"
        )
    else:
        observation = (
            f"{signal.actions_on_level} actions on level {signal.level} "
            "without completing it"
        )
    if signal.repeated_action:
        observation += f"; the last repeated action was {signal.repeated_action}"
    return (
        "\n\nRECOVERY CHECKPOINT — " + observation + ". "
        "This is an advisory signal: border cells may encode a timer or a rule, "
        "and an apparently ineffective action may work after hidden state changes. "
        "Do not blindly forbid it. Before spending another game action, use the "
        "Python tool and recorded transitions to state: (1) one concrete, "
        "observable goal/progress predicate; (2) two competing explanations "
        "for the last failure, each tied to a specific observation; and (3) one "
        "low-cost diagnostic action for which the explanations predict DIFFERENT "
        "outcomes. Check whether older transitions already resolve that test. "
        "Then execute only that diagnostic action, inspect its outcome, and "
        "revise the goal/mechanic model before committing to a longer plan. "
        "If no discriminating action exists, explicitly say UNKNOWN and switch "
        "to a different plausible goal rather than repeating an unchanged plan."
    )

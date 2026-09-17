"""Opt-in structured memory for Duck's Python-tool agent.

The memory update is a sibling of ``code`` in the existing Python tool call.
It is validated and fsynced by the host *before* the sandbox can execute an
environment action.  Nothing here changes Duck's policy when this subclass is
not selected.  Winning paths are stored but deliberately never auto-replayed
in the memory ablation; replay would be a second treatment.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arc3.memory import (
    Fact,
    GameMemory,
    MemoryJournal,
    MemoryUpdate,
    Status,
    WinningPath,
    commit,
    transition,
)
from inference.agent.runtime_state import load_runtime_state
from inference.agent.tool_agent import ToolAgent, _ToolDispatchResult


FACT_FIELDS = ("mechanics", "goal_evidence", "counterexamples", "goal_guesses")
UPDATE_FIELDS = set(FACT_FIELDS) | {
    "action_semantics", "winning_paths", "current_plan", "level_coordinates",
    "object_identities",
}


def _action_key(raw: Any) -> tuple[int, int | None, int | None]:
    if not isinstance(raw, list) or len(raw) != 3:
        raise ValueError("an action key must be [id, x, y]")
    key = tuple(raw)
    if not isinstance(key[0], int) or isinstance(key[0], bool):
        raise ValueError("action id must be an integer")
    if any(value is not None and (not isinstance(value, int) or isinstance(value, bool))
           for value in key[1:]):
        raise ValueError("action coordinates must be integers or null")
    return key


def _fact(raw: Any) -> Fact:
    if not isinstance(raw, dict) or set(raw) - {"statement", "status", "evidence"}:
        raise ValueError("a fact must contain only statement, status, and evidence")
    evidence = raw.get("evidence", [])
    if not isinstance(evidence, list):
        raise ValueError("fact evidence must be a list of transition indices")
    return Fact(
        statement=raw.get("statement"),
        status=Status(raw.get("status", "ASSUMED")),
        evidence=tuple(evidence),
    )


def parse_memory_update(raw: Any) -> MemoryUpdate:
    """Convert the JSON tool argument to the tested memory contract."""
    if not isinstance(raw, dict):
        raise ValueError("memory_update must be a JSON object")
    unknown = set(raw) - UPDATE_FIELDS
    if unknown:
        raise ValueError(f"unknown memory_update fields: {sorted(unknown)}")
    values: dict[str, Any] = {}
    for name in FACT_FIELDS:
        if name in raw:
            if not isinstance(raw[name], list):
                raise ValueError(f"{name} must be a list")
            values[name] = [_fact(item) for item in raw[name]]
    if "action_semantics" in raw:
        if not isinstance(raw["action_semantics"], list):
            raise ValueError("action_semantics must be a list")
        semantics: dict[tuple[int, int | None, int | None], list[Fact]] = {}
        for item in raw["action_semantics"]:
            if not isinstance(item, dict) or set(item) != {"action", "facts"}:
                raise ValueError("action_semantics entries need action and facts")
            key = _action_key(item["action"])
            if key in semantics or not isinstance(item["facts"], list):
                raise ValueError("duplicate action or non-list facts")
            semantics[key] = [_fact(fact) for fact in item["facts"]]
        values["action_semantics"] = semantics
    if "winning_paths" in raw:
        if not isinstance(raw["winning_paths"], list):
            raise ValueError("winning_paths must be a list")
        paths = []
        for item in raw["winning_paths"]:
            if not isinstance(item, dict) or set(item) != {
                "level", "start_signature", "actions", "expected_outcomes", "evidence"
            }:
                raise ValueError("winning path needs all five fields")
            if not isinstance(item["actions"], list) or not isinstance(item["expected_outcomes"], list):
                raise ValueError("winning path actions and outcomes must be lists")
            if len(item["actions"]) != len(item["expected_outcomes"]):
                raise ValueError("a winning path needs one expected outcome per action")
            if not isinstance(item["evidence"], list):
                raise ValueError("winning path evidence must be a list")
            paths.append(WinningPath(
                level=item["level"],
                start_signature=item["start_signature"],
                actions=tuple(_action_key(a) for a in item["actions"]),
                expected_outcomes=tuple(item["expected_outcomes"]),
                evidence=tuple(item["evidence"]),
            ))
        values["winning_paths"] = paths
    if "current_plan" in raw:
        if not isinstance(raw["current_plan"], list):
            raise ValueError("current_plan must be a list")
        values["current_plan"] = [_action_key(item) for item in raw["current_plan"]]
    for name in ("level_coordinates", "object_identities"):
        if name in raw:
            values[name] = raw[name]
    return MemoryUpdate(**values)


def known_transition_ids(state_path: Path) -> set[int]:
    """Match the zero-based ``transitions`` list visible in Duck's sandbox."""
    _, history = load_runtime_state(state_path)
    return set(range(sum(bool(entry.action.strip()) for entry in history)))


class MemoryToolAgent(ToolAgent):
    """Duck with explicit, per-game, crash-proof belief revision."""

    def _ensure_session(self, state_path: Path) -> None:
        super()._ensure_session(state_path)
        journal_path = state_path.with_suffix(".memory.jsonl")
        if getattr(self, "_memory_journal_path", None) == journal_path:
            self._sync_level(state_path)
            return
        self._memory_journal_path = journal_path
        self._memory_journal = MemoryJournal(journal_path)
        game_id = str(getattr(self, "_gate2_game_id", state_path.stem))
        restored = self._memory_journal.restore()
        if restored is not None and restored.game_id != game_id:
            raise RuntimeError("memory journal belongs to a different game")
        frame, _ = load_runtime_state(state_path)
        self._memory = restored or GameMemory(game_id=game_id, level=frame.level if frame else 1)
        self._memory_commits = 0
        self._memory_rejections = 0
        self._memory_transitions = 0
        self._memory_missing_updates = 0
        self._memory_empty_updates = 0
        self._sync_level(state_path)

    def _sync_level(self, state_path: Path) -> None:
        """Recover a transition even if a prior tool call died after the action."""
        frame, _ = load_runtime_state(state_path)
        if frame is not None and frame.level != self._memory.level:
            transition(self._memory, frame.level, self._memory_journal)
            self._memory_transitions += 1

    def _tools(self, state_path: Path) -> list[dict[str, Any]]:
        tools = super()._tools(state_path)
        tool = tools[0]["function"]
        tool["description"] += (
            " Required memory_update is validated and persisted before code runs. "
            "Use it for concise mechanics and goal evidence, not a turn journal."
        )
        tool["parameters"]["properties"]["memory_update"] = {
            "type": "object",
            "description": (
                "Required decision: use {} when nothing new was learned; otherwise "
                "record at most two concise causal rules or goal hypotheses. "
                "Fields mechanics, goal_evidence, "
                "counterexamples, goal_guesses are arrays of facts. A fact is "
                "{statement, status: ASSUMED|CONFIRMED|REFUTED, evidence: [transition indices]}. "
                "CONFIRMED and REFUTED require an existing evidence index."
            ),
        }
        tool["parameters"]["required"].append("memory_update")
        return tools

    def _build_user_prompt(self, action_num: int, **kwargs: Any) -> str:
        prompt = super()._build_user_prompt(action_num, **kwargs)
        memory = self._memory
        facts = []
        for name in ("mechanics", "goal_evidence", "counterexamples", "goal_guesses"):
            for fact in getattr(memory, name):
                facts.append(f"{name}: [{fact.status.value}] {fact.statement}")
        for action, claims in memory.action_semantics.items():
            for fact in claims:
                facts.append(f"action {action}: [{fact.status.value}] {fact.statement}")
        if memory.current_plan:
            facts.append(f"current_plan: {memory.current_plan!r}")
        shown = []
        shown_chars = 0
        for fact in facts:
            if shown_chars + len(fact) + 1 > 3500:
                break
            shown.append(fact)
            shown_chars += len(fact) + 1
        text = "\n".join(shown)
        if len(shown) < len(facts):
            text += f"\n[{len(facts) - len(shown)} additional beliefs remain in the per-game journal.]"
        history = kwargs.get("history_entries") or []
        latest_id = sum(bool(entry.action.strip()) for entry in history) - 1
        return prompt + "\n\nStructured per-game memory (not a journal of turns):\n" + (
            text or "[empty]"
        ) + (
            "\nEvery python tool call must include memory_update as a JSON sibling of code. "
            "Use {} only when you have learned no new causal rule or goal hypothesis. "
            "After an action changes the puzzle, consider whether it supports one concise "
            "mechanic or goal claim; record at most two new claims, not a turn journal. "
            "For an unverified hypothesis use ASSUMED without evidence, for example "
            '{"code":"action([\'RIGHT\'])",'
            '"memory_update":{"mechanics":[{"statement":"RIGHT moves the frame",'
            '"status":"ASSUMED"}]}}. '
            "Use CONFIRMED or REFUTED only with evidence from a transition that already "
            "exists. Evidence indices are zero-based positions in transitions. "
            f"The latest available transition index is {latest_id}; never cite a future index. "
            "To refute one, repeat its exact "
            "statement as REFUTED with the contradictory transition index. "
            "At a new level, keep mechanics and verified goal evidence; discard the old plan and coordinates."
        )

    def _run_python_tool(self, state_path: Path, arguments: dict[str, Any]) -> _ToolDispatchResult:
        self._ensure_session(state_path)
        code = str(arguments.get("code", "")).rstrip()
        if not code:
            return _ToolDispatchResult(json.dumps({"error": "python requires non-empty code"}))
        try:
            compile(code, "<python_tool>", "exec")
        except SyntaxError as exc:
            return _ToolDispatchResult(json.dumps({"error": f"Python syntax error: {exc}"}))
        if "memory_update" not in arguments:
            self._memory_missing_updates += 1
        else:
            try:
                update = parse_memory_update(arguments["memory_update"])
                if any(bool(value) for value in vars(update).values()):
                    commit(
                        self._memory, update, self._memory_journal,
                        known_transitions=known_transition_ids(state_path),
                    )
                    self._memory_commits += 1
                else:
                    self._memory_empty_updates += 1
            except (TypeError, ValueError) as exc:
                self._memory_rejections += 1
                return _ToolDispatchResult(json.dumps({"error": f"memory_update rejected: {exc}"}))
        result = super()._run_python_tool(state_path, arguments)
        frame, _ = load_runtime_state(state_path)
        if frame is not None and frame.level != self._memory.level:
            transition(self._memory, frame.level, self._memory_journal)
            self._memory_transitions += 1
        return result

"""Structured per-game memory the model commits explicitly.

Duck keeps 30 assistant turns and clears six summary fields at a level
transition. The defect is not the clearing: durable summaries update only from
assistant `content`, and the model reasons then emits a tool call, so the channel
Duck reads is frequently empty. Preserving those summaries preserves nothing.
**The model has to commit memory explicitly**, as a typed argument beside its
action.

Every rule below exists because it is a way to silently destroy knowledge.

**All-or-nothing.** The WHOLE update is validated -- every field, to its leaves --
before a single byte is written. A half-applied update leaves memory in a state
no one designed.

**Omission keeps, empty never clears.** A field not mentioned retains its value;
`[]` means "nothing to add", not "forget". A model truncated under length
pressure must not wipe the store.

**Conflict is recorded, not resolved.** Status is not a precedence ladder. A
REFUTED claim re-proposed as a guess is blocked; a CONFIRMED claim later refuted
becomes CONTESTED with both evidence sets intact. An earlier version let a guess
resurrect a disproven claim and made a wrong confirmation permanently
uncorrectable -- opposite errors from the same mistake of ordering statuses.

**Evidence must exist.** A fact citing transition 999999 of a 300-transition
ledger is an assertion wearing a citation. Pass `known_transitions` and it is
checked.

**A winning path is not a list of actions.** Replaying one into a level it was
not learned in, from a state it does not fit, is worse than not having it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from arc3.effects import ActionKey


class Status(str, Enum):
    CONFIRMED = "CONFIRMED"  # checked against recorded transitions
    ASSUMED = "ASSUMED"      # plausible, untested
    REFUTED = "REFUTED"      # contradicted; kept so it is not re-proposed
    CONTESTED = "CONTESTED"  # confirmed AND refuted; needs a discriminating probe


EVIDENCE_REQUIRED = (Status.CONFIRMED, Status.REFUTED, Status.CONTESTED)


@dataclass(frozen=True)
class Fact:
    statement: str
    status: Status = Status.ASSUMED
    evidence: tuple[int, ...] = ()  # transition indices in this game's ledger

    def __post_init__(self) -> None:
        if not isinstance(self.statement, str) or not self.statement.strip():
            raise ValueError("a fact with no statement carries no information")
        if not isinstance(self.status, Status):
            raise ValueError(f"status must be a Status, got {self.status!r}")
        if any(not isinstance(i, int) or isinstance(i, bool) for i in self.evidence):
            raise ValueError(f"evidence must be transition indices: {self.evidence!r}")
        if self.status in EVIDENCE_REQUIRED and not self.evidence:
            raise ValueError(
                f"{self.status.value} without evidence: {self.statement!r}. "
                "The store cannot tell knowledge from assertion otherwise"
            )


@dataclass(frozen=True)
class WinningPath:
    """A sequence that worked, with everything needed to know when it applies.

    Carrying bare actions across a level transition is how a 'memory' feature
    makes an agent worse: the board may have been resized, the objects renamed,
    the mechanic changed. A path is replayable only from a matching level and
    start signature, and only while each step's expectation holds.
    """

    level: int
    start_signature: str  # raw board hash the path was learned from
    actions: tuple[ActionKey, ...]
    expected_outcomes: tuple[str, ...] = ()  # after-hash expected at each step
    evidence: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.actions:
            raise ValueError("a winning path with no actions is not a path")
        for action in self.actions:
            _check_action(action)
        if not self.start_signature:
            raise ValueError("a path without a start signature cannot be matched")
        if self.expected_outcomes and len(self.expected_outcomes) != len(self.actions):
            raise ValueError("expected_outcomes must align 1:1 with actions")

    def usable_from(self, level: int, signature: str) -> bool:
        """Never replay unless the precondition matches exactly."""
        return level == self.level and signature == self.start_signature


DURABLE = ("action_semantics", "mechanics", "goal_evidence", "counterexamples",
           "winning_paths")
VOLATILE = ("current_plan", "level_coordinates", "goal_guesses", "object_identities")
FACT_LISTS = ("mechanics", "goal_evidence", "counterexamples", "goal_guesses")


@dataclass
class MemoryUpdate:
    """What the model commits alongside its action. ``None`` means "not touching"."""

    action_semantics: dict[ActionKey, list[Fact]] | None = None
    mechanics: list[Fact] | None = None
    goal_evidence: list[Fact] | None = None
    counterexamples: list[Fact] | None = None
    winning_paths: list[WinningPath] | None = None
    current_plan: list[ActionKey] | None = None
    level_coordinates: dict[str, Any] | None = None
    goal_guesses: list[Fact] | None = None
    object_identities: dict[str, Any] | None = None

    def touched(self) -> list[str]:
        return [n for n in DURABLE + VOLATILE if getattr(self, n) is not None]


def _check_action(action: Any) -> None:
    if (not isinstance(action, tuple) or len(action) != 3
            or not isinstance(action[0], int) or isinstance(action[0], bool)
            or any(not (v is None or (isinstance(v, int) and not isinstance(v, bool)))
                   for v in action[1:])):
        raise ValueError(f"not an action key (id, x, y): {action!r}")


def _check_jsonable(name: str, value: Any) -> None:
    try:
        json.dumps(value, default=_json_default)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be JSON-serialisable: {exc}") from exc


def _json_default(obj: Any) -> Any:
    if isinstance(obj, tuple):
        return list(obj)
    raise TypeError(f"{type(obj).__name__} is not serialisable")


def validate(update: MemoryUpdate, known_transitions: set[int] | None = None) -> None:
    """Validate EVERY field to its leaves. Raises before anything is written."""
    for name in FACT_LISTS:
        value = getattr(update, name)
        if value is None:
            continue
        if not isinstance(value, list) or any(not isinstance(f, Fact) for f in value):
            raise ValueError(f"{name} must be a list of Fact, got {value!r}")
        _check_evidence(name, value, known_transitions)

    if update.action_semantics is not None:
        if not isinstance(update.action_semantics, dict):
            raise ValueError("action_semantics must be a dict keyed by action")
        for key, facts in update.action_semantics.items():
            _check_action(key)
            if not isinstance(facts, list) or any(not isinstance(f, Fact) for f in facts):
                raise ValueError(f"action_semantics[{key}] must be a list of Fact")
            _check_evidence("action_semantics", facts, known_transitions)

    if update.winning_paths is not None:
        if not isinstance(update.winning_paths, list) or any(
                not isinstance(p, WinningPath) for p in update.winning_paths):
            raise ValueError("winning_paths must be a list of WinningPath")
        if known_transitions is not None:
            for path in update.winning_paths:
                _check_indices("winning_paths", path.evidence, known_transitions)

    if update.current_plan is not None:
        if not isinstance(update.current_plan, list):
            raise ValueError(f"current_plan must be a list, got {update.current_plan!r}")
        for action in update.current_plan:
            _check_action(action)

    for name in ("level_coordinates", "object_identities"):
        value = getattr(update, name)
        if value is None:
            continue
        if not isinstance(value, dict):
            raise ValueError(f"{name} must be a dict, got {value!r}")
        _check_jsonable(name, value)


def _check_evidence(name: str, facts: Iterable[Fact],
                    known: set[int] | None) -> None:
    if known is None:
        return
    for fact in facts:
        _check_indices(f"{name}: {fact.statement!r}", fact.evidence, known)


def _check_indices(label: str, indices: Iterable[int], known: set[int]) -> None:
    missing = [i for i in indices if i not in known]
    if missing:
        raise ValueError(
            f"{label} cites transitions that do not exist: {missing}. "
            "A citation to nothing is an assertion wearing a citation"
        )


def _revise(incoming: Fact, existing: Fact) -> Fact | None:
    """Belief revision for one statement. None means the incoming fact is blocked.

    Not a precedence ladder:

    ```
    existing    incoming     result
    ASSUMED     CONFIRMED    upgrade, merge evidence
    ASSUMED     REFUTED      refute, merge evidence
    CONFIRMED   ASSUMED      blocked -- a guess cannot unseat a verified claim
    CONFIRMED   REFUTED      CONTESTED, both evidence sets kept
    REFUTED     ASSUMED      blocked -- a disproven claim is not re-proposed
    REFUTED     CONFIRMED    CONTESTED, both evidence sets kept
    CONTESTED   anything     stays CONTESTED, evidence accumulates
    ```
    """
    merged = tuple(dict.fromkeys(existing.evidence + incoming.evidence))

    if existing.status is Status.CONTESTED:
        return replace(existing, evidence=merged)
    if incoming.status is Status.ASSUMED and existing.status is not Status.ASSUMED:
        return None
    if existing.status is Status.ASSUMED:
        return replace(incoming, evidence=merged)
    if existing.status == incoming.status:
        return replace(existing, evidence=merged)
    # CONFIRMED vs REFUTED, in either direction.
    return replace(existing, status=Status.CONTESTED, evidence=merged)


def _merge_facts(existing: list[Fact], incoming: Iterable[Fact]
                 ) -> tuple[list[Fact], list[str]]:
    """Returns (merged, blocked statements)."""
    out = list(existing)
    index = {f.statement: i for i, f in enumerate(out)}
    blocked: list[str] = []
    for fact in incoming:
        position = index.get(fact.statement)
        if position is None:
            index[fact.statement] = len(out)
            out.append(fact)
            continue
        revised = _revise(fact, out[position])
        if revised is None:
            blocked.append(fact.statement)
        else:
            out[position] = revised
    return out, blocked


@dataclass
class MemoryDelta:
    changed: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)  # re-proposed refuted claims
    contested: list[str] = field(default_factory=list)


@dataclass
class GameMemory:
    """Everything known about ONE game. Never shared across games."""

    game_id: str
    level: int = 1
    action_semantics: dict[ActionKey, list[Fact]] = field(default_factory=dict)
    mechanics: list[Fact] = field(default_factory=list)
    goal_evidence: list[Fact] = field(default_factory=list)
    counterexamples: list[Fact] = field(default_factory=list)
    winning_paths: list[WinningPath] = field(default_factory=list)
    current_plan: list[ActionKey] = field(default_factory=list)
    level_coordinates: dict[str, Any] = field(default_factory=dict)
    goal_guesses: list[Fact] = field(default_factory=list)
    object_identities: dict[str, Any] = field(default_factory=dict)
    unpersisted: bool = False

    def snapshot(self) -> dict[str, Any]:
        """JSON-safe and REVERSIBLE -- action keys stay lists, not strings."""
        return {
            "game_id": self.game_id,
            "level": self.level,
            "action_semantics": [[list(k), [_fact(f) for f in v]]
                                 for k, v in self.action_semantics.items()],
            "mechanics": [_fact(f) for f in self.mechanics],
            "goal_evidence": [_fact(f) for f in self.goal_evidence],
            "counterexamples": [_fact(f) for f in self.counterexamples],
            "winning_paths": [_path(p) for p in self.winning_paths],
            "current_plan": [list(a) for a in self.current_plan],
            "level_coordinates": json.loads(json.dumps(self.level_coordinates,
                                                       default=_json_default)),
            "goal_guesses": [_fact(f) for f in self.goal_guesses],
            "object_identities": json.loads(json.dumps(self.object_identities,
                                                       default=_json_default)),
        }

    @classmethod
    def restore(cls, snapshot: dict[str, Any]) -> "GameMemory":
        """Rebuild from a snapshot. Persistence that cannot be loaded is a log."""
        return cls(
            game_id=snapshot["game_id"],
            level=snapshot["level"],
            action_semantics={tuple(k): [_unfact(f) for f in v]
                              for k, v in snapshot["action_semantics"]},
            mechanics=[_unfact(f) for f in snapshot["mechanics"]],
            goal_evidence=[_unfact(f) for f in snapshot["goal_evidence"]],
            counterexamples=[_unfact(f) for f in snapshot["counterexamples"]],
            winning_paths=[_unpath(p) for p in snapshot["winning_paths"]],
            current_plan=[tuple(a) for a in snapshot["current_plan"]],
            level_coordinates=snapshot["level_coordinates"],
            goal_guesses=[_unfact(f) for f in snapshot["goal_guesses"]],
            object_identities=snapshot["object_identities"],
        )

    def apply(self, update: MemoryUpdate,
              known_transitions: set[int] | None = None) -> MemoryDelta:
        validate(update, known_transitions)
        delta = MemoryDelta()

        for name in FACT_LISTS:
            incoming = getattr(update, name)
            if not incoming:
                continue
            merged, blocked = _merge_facts(getattr(self, name), incoming)
            delta.blocked.extend(blocked)
            if merged != getattr(self, name):
                setattr(self, name, merged)
                delta.changed.append(name)

        if update.action_semantics:
            for key, facts in update.action_semantics.items():
                merged, blocked = _merge_facts(self.action_semantics.get(key, []), facts)
                delta.blocked.extend(blocked)
                if merged != self.action_semantics.get(key, []):
                    self.action_semantics[key] = merged
                    if "action_semantics" not in delta.changed:
                        delta.changed.append("action_semantics")

        if update.winning_paths:
            for path in update.winning_paths:
                if path not in self.winning_paths:
                    self.winning_paths.append(path)
                    if "winning_paths" not in delta.changed:
                        delta.changed.append("winning_paths")

        for name in ("current_plan", "level_coordinates", "object_identities"):
            incoming = getattr(update, name)
            if not incoming:
                continue
            setattr(self, name, incoming.copy())
            delta.changed.append(name)

        delta.contested = sorted(self.contested())
        if delta.changed:
            self.unpersisted = True
        return delta

    def contested(self) -> set[str]:
        """Statements needing a discriminating probe rather than more assertion."""
        out = {f.statement for name in FACT_LISTS for f in getattr(self, name)
               if f.status is Status.CONTESTED}
        out |= {f.statement for facts in self.action_semantics.values()
                for f in facts if f.status is Status.CONTESTED}
        # Two different CONFIRMED claims about one action is also a conflict.
        for facts in self.action_semantics.values():
            confirmed = [f.statement for f in facts if f.status is Status.CONFIRMED]
            if len(confirmed) > 1:
                out |= set(confirmed)
        return out

    def replayable(self, level: int, signature: str) -> list[WinningPath]:
        return [p for p in self.winning_paths if p.usable_from(level, signature)]

    def on_level_transition(self, new_level: int) -> None:
        """Keep what was learned about the game; drop what was true of the level."""
        self.level = new_level
        self.current_plan = []
        self.level_coordinates = {}
        self.goal_guesses = []
        self.object_identities = {}
        self.unpersisted = True


def _fact(f: Fact) -> dict[str, Any]:
    return {"statement": f.statement, "status": f.status.value,
            "evidence": list(f.evidence)}


def _unfact(d: dict[str, Any]) -> Fact:
    return Fact(d["statement"], Status(d["status"]), tuple(d["evidence"]))


def _path(p: WinningPath) -> dict[str, Any]:
    return {"level": p.level, "start_signature": p.start_signature,
            "actions": [list(a) for a in p.actions],
            "expected_outcomes": list(p.expected_outcomes),
            "evidence": list(p.evidence)}


def _unpath(d: dict[str, Any]) -> WinningPath:
    return WinningPath(level=d["level"], start_signature=d["start_signature"],
                       actions=tuple(tuple(a) for a in d["actions"]),
                       expected_outcomes=tuple(d["expected_outcomes"]),
                       evidence=tuple(d["evidence"]))


class MemoryJournal:
    """Append-only before/after record. Durable per entry, and RESTORABLE.

    An audit log that cannot be loaded is not persistence. `restore` rebuilds the
    store from the last complete entry, so a run killed mid-game resumes with
    what it had learned instead of starting over.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, memory: GameMemory, event: str, before: dict[str, Any],
               delta: MemoryDelta) -> None:
        entry = {"event": event, "game_id": memory.game_id, "level": memory.level,
                 "changed": delta.changed, "blocked": delta.blocked,
                 "contested": delta.contested, "before": before,
                 "after": memory.snapshot()}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        memory.unpersisted = False

    def entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # a torn tail costs one entry, not the store
        return out

    def restore(self) -> GameMemory | None:
        entries = self.entries()
        return GameMemory.restore(entries[-1]["after"]) if entries else None


def commit(memory: GameMemory, update: MemoryUpdate, journal: MemoryJournal,
           known_transitions: set[int] | None = None) -> MemoryDelta:
    """Apply and persist, in that order, BEFORE the action is taken.

    The action may complete the level, and the transition reset that follows
    would discard an update that had not yet reached the journal.
    """
    before = memory.snapshot()
    delta = memory.apply(update, known_transitions)
    journal.record(memory, "update", before, delta)
    return delta


def transition(memory: GameMemory, new_level: int, journal: MemoryJournal) -> None:
    """Journal the reset too -- it destroys four fields and must be reconstructible."""
    before = memory.snapshot()
    memory.on_level_transition(new_level)
    journal.record(memory, "level_transition", before,
                   MemoryDelta(changed=list(VOLATILE)))

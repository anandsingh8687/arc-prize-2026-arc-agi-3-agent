"""Expect-checked action queues.

A plan is a list of actions each optionally carrying a board expectation.
Execution stops at the first mismatch so a bad world model costs one action,
not the rest of the queue. Pure helpers — no LLM, no Duck imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Protocol, Sequence


Grid = Mapping[tuple[int, int], int] | None


@dataclass(frozen=True)
class QueuedAction:
    action_id: str
    data: dict | None = None
    expect: dict[tuple[int, int], int] = field(default_factory=dict)
    note: str = ""


@dataclass
class StepResult:
    action: QueuedAction
    ok: bool
    mismatch: dict[tuple[int, int], tuple[int | None, int]] = field(default_factory=dict)
    # mismatch maps cell -> (observed_or_None, expected)


class EnvLike(Protocol):
    def step(self, action_id: str, data: dict | None = None) -> "FrameLike":
        ...


class FrameLike(Protocol):
    def cell(self, row: int, col: int) -> int | None:
        ...


def check_expect(frame: FrameLike, expect: Mapping[tuple[int, int], int]) -> dict[tuple[int, int], tuple[int | None, int]]:
    bad: dict[tuple[int, int], tuple[int | None, int]] = {}
    for (r, c), expected in expect.items():
        observed = frame.cell(r, c)
        if observed != expected:
            bad[(r, c)] = (observed, expected)
    return bad


def run_queue(
    env: EnvLike,
    queue: Sequence[QueuedAction],
    *,
    on_mismatch: Callable[[StepResult], None] | None = None,
) -> list[StepResult]:
    """Execute until empty or first failed expectation."""
    results: list[StepResult] = []
    for item in queue:
        frame = env.step(item.action_id, item.data)
        mismatch = check_expect(frame, item.expect) if item.expect else {}
        step = StepResult(action=item, ok=not mismatch, mismatch=mismatch)
        results.append(step)
        if not step.ok:
            if on_mismatch is not None:
                on_mismatch(step)
            break
    return results


def halt_index(results: Sequence[StepResult]) -> int | None:
    for i, step in enumerate(results):
        if not step.ok:
            return i
    return None

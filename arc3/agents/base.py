"""Agent interface.

An agent returns a *plan* -- a short sequence of actions -- rather than one action
at a time. This is deliberate. The budget is roughly 0.577 actions/sec aggregate
across 110 games in 9 hours, and decode throughput is dominated by context length,
so a model consulted once per action cannot keep pace. Agents that genuinely want
to act one step at a time simply return a length-1 plan.

Each planned action may carry an expectation. The executor plays the plan out and
stops at the first action whose expectation is violated, handing control back with
the diff. A wrong world model then costs one action instead of a whole plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
from arcengine import FrameDataRaw, GameAction


@dataclass
class Observation:
    """What the agent sees after an action."""

    grid: np.ndarray  # (H, W) int array, values 0-15
    available_actions: list[GameAction]
    levels_completed: int
    state: str
    action_count: int  # cumulative, scoring-relevant

    @classmethod
    def from_frame(
        cls,
        frame: FrameDataRaw,
        action_count: int,
        fallback_grid: "np.ndarray | None" = None,
    ) -> "Observation":
        from .. import env as _env  # local import; avoids a cycle at module load

        return cls(
            grid=_env.grid_of(frame, fallback_grid),
            available_actions=[GameAction.from_id(a) for a in frame.available_actions],
            levels_completed=frame.levels_completed,
            state=str(frame.state),
            action_count=action_count,
        )


@dataclass
class PlannedAction:
    action: GameAction
    data: dict | None = None  # ACTION6 carries {"x": int, "y": int}
    # Cells the settled board must show afterwards: {(row, col): value}. Checked
    # against the real frame; a mismatch halts the rest of the plan.
    expect: dict[tuple[int, int], int] = field(default_factory=dict)
    note: str = ""


@dataclass
class Plan:
    actions: list[PlannedAction]
    # Level count the agent expects when the plan finishes, if it has a view.
    expect_levels_completed: int | None = None

    def __len__(self) -> int:
        return len(self.actions)


class Agent(Protocol):
    """Implemented by every strategy, LLM-backed or not."""

    name: str

    def reset(self, game_id: str) -> None:
        """Called once before a new game."""

    def plan(self, obs: Observation) -> Plan:
        """Return the next batch of actions to play."""

    def on_mismatch(self, obs: Observation, failed: PlannedAction) -> None:
        """Called when an expectation was violated, before the next plan()."""

    def is_done(self, obs: Observation) -> bool:
        """Return True to stop playing this game early."""

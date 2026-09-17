"""Effect ledger: what each action actually did, per state and overall.

Two jobs. Per state, it stops the agent re-probing an action that did nothing here
before -- under a squared metric a repeated no-op is pure loss. Globally, it learns
which actions matter in *this* game, so exploration starts with the ones that have
paid off rather than cycling the full action space.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

ActionKey = tuple[int, int | None, int | None]  # (action id, x, y) -- x/y for ACTION6


@dataclass
class ActionStats:
    attempts: int = 0
    changes: int = 0  # times the board actually moved
    level_advances: int = 0
    cells_changed: int = 0

    @property
    def change_rate(self) -> float:
        return self.changes / self.attempts if self.attempts else 0.0

    @property
    def mean_cells_changed(self) -> float:
        return self.cells_changed / self.changes if self.changes else 0.0


@dataclass
class EffectLedger:
    """Per-game record of action outcomes."""

    by_action: dict[ActionKey, ActionStats] = field(
        default_factory=lambda: defaultdict(ActionStats)
    )
    # (state hash, action) -> did anything change last time we tried it here
    by_state: dict[tuple[str, ActionKey], bool] = field(default_factory=dict)

    def record(
        self,
        state_hash: str,
        action: ActionKey,
        changed_cells: int,
        level_advanced: bool,
    ) -> None:
        stats = self.by_action[action]
        stats.attempts += 1
        if changed_cells > 0:
            stats.changes += 1
            stats.cells_changed += changed_cells
        if level_advanced:
            stats.level_advances += 1
        self.by_state[(state_hash, action)] = changed_cells > 0

    def is_known_noop(self, state_hash: str, action: ActionKey) -> bool:
        """True if this action did nothing the last time it was tried here."""
        return self.by_state.get((state_hash, action)) is False

    def tried_here(self, state_hash: str, action: ActionKey) -> bool:
        return (state_hash, action) in self.by_state

    def attempts(self, action: ActionKey) -> int:
        stats = self.by_action.get(action)
        return stats.attempts if stats else 0

    def exploration_rank(self, action: ActionKey) -> tuple[int, float]:
        """Sort key for choosing among actions untried in the current state.

        Breadth first, then what has worked. Ranking purely by past success
        collapses the agent onto whichever action moved the board most often,
        which it then repeats forever -- it stops covering the action space and
        the run stalls. Fewest global attempts wins, with effectiveness only
        breaking ties, so all actions keep getting exercised.

        Returned for use with ``min``; lower is better.
        """
        return (self.attempts(action), -self.value(action))

    def value(self, action: ActionKey) -> float:
        """How useful this action has proven, ignoring novelty."""
        stats = self.by_action.get(action)
        if stats is None or stats.attempts == 0:
            return 1.0  # unknown actions carry the most information
        if stats.level_advances:
            return 0.9
        return stats.change_rate * 0.8

    def useful_colours(self) -> set[int]:
        """Placeholder for colour bias; filled in by the agent that owns it."""
        return set()

    def reset_level(self) -> None:
        """Per-state facts do not survive a level; per-action tendencies do."""
        self.by_state.clear()

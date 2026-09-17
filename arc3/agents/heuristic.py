"""Deterministic explorer: no model, no GPU.

Its purpose is to be the floor and the control. Every LLM change gets measured
against this, so we know whether reasoning is paying for its throughput. It also
exercises the whole deterministic stack -- volatility masking, effect ledger,
win-path cache -- on real games, where bugs in that stack would otherwise hide
behind model noise.

Strategy, cheapest information first:

1. Replay a cached winning path if we have re-entered a level we already solved.
2. At the current state, try actions never tried here, ranked by what has worked
   elsewhere in this game.
3. Skip actions known to do nothing in this exact state.
4. For ACTION6, propose clicks at component centroids -- smaller components first,
   since a rare small object is more likely to be interactive than the background.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from arcengine import GameAction

from ..effects import ActionKey, EffectLedger
from ..state import StateTracker, components
from .base import Observation, Plan, PlannedAction

# Clicks proposed per state before falling back to a coarse grid sweep.
MAX_CLICK_CANDIDATES = 12
# Components bigger than this are probably background or walls, not targets.
MAX_INTERESTING_COMPONENT = 64


@dataclass
class WinPath:
    """Actions that cleared a level, keyed by the state they started from."""

    from_state: str
    actions: list[ActionKey]


@dataclass
class HeuristicAgent:
    name: str = "heuristic"

    tracker: StateTracker = field(default_factory=StateTracker)
    ledger: EffectLedger = field(default_factory=EffectLedger)
    win_paths: dict[int, WinPath] = field(default_factory=dict)  # level -> path

    _level: int = 0
    _state_hash: str = ""
    _since_level_start: list[ActionKey] = field(default_factory=list)
    _level_start_state: str = ""
    _replay: list[ActionKey] = field(default_factory=list)
    _last_action: ActionKey | None = None

    def reset(self, game_id: str) -> None:
        self.tracker = StateTracker()
        self.ledger = EffectLedger()
        self.win_paths = {}
        self._level = 0
        self._since_level_start = []
        self._level_start_state = ""
        self._replay = []
        self._last_action = None

    # -- bookkeeping ----------------------------------------------------------

    def _observe(self, obs: Observation) -> None:
        """Fold the new frame into the ledger and trackers."""
        changed = self.tracker.last_diff(obs.grid)
        advanced = obs.levels_completed > self._level

        if self._last_action is not None and self._state_hash:
            self.ledger.record(
                state_hash=self._state_hash,
                action=self._last_action,
                changed_cells=len(changed),
                level_advanced=advanced,
            )

        if advanced:
            # Remember how we got out of this level, then start fresh.
            self.win_paths[self._level] = WinPath(
                from_state=self._level_start_state,
                actions=list(self._since_level_start),
            )
            self._level = obs.levels_completed
            self.tracker.reset_level()
            self.ledger.reset_level()
            self._since_level_start = []
            self._level_start_state = ""

        self._state_hash = self.tracker.observe(obs.grid)
        if not self._level_start_state:
            self._level_start_state = self._state_hash

    # -- action proposal ------------------------------------------------------

    def _click_candidates(self, grid: np.ndarray) -> list[ActionKey]:
        """Centroids of small components first, then a coarse sweep."""
        small = [
            comp
            for comp in components(grid)
            if comp.size <= MAX_INTERESTING_COMPONENT
        ]
        small.sort(key=lambda c: c.size)  # rarest/smallest carry most information

        candidates: list[ActionKey] = []
        for comp in small[:MAX_CLICK_CANDIDATES]:
            row, col = comp.centroid
            candidates.append((GameAction.ACTION6.value, col, row))  # (x, y)

        if len(candidates) < MAX_CLICK_CANDIDATES:
            step = max(grid.shape[0] // 4, 1)
            for y in range(step // 2, grid.shape[0], step):
                for x in range(step // 2, grid.shape[1], step):
                    candidates.append((GameAction.ACTION6.value, x, y))
        return candidates

    def _candidates(self, obs: Observation) -> list[ActionKey]:
        available = {a.value for a in obs.available_actions}
        out: list[ActionKey] = [
            (a, None, None)
            for a in available
            if a not in (GameAction.RESET.value, GameAction.ACTION6.value, GameAction.ACTION7.value)
        ]
        if GameAction.ACTION6.value in available:
            out.extend(self._click_candidates(obs.grid))
        return out

    def plan(self, obs: Observation) -> Plan:
        self._observe(obs)

        # 1. Replay a known winning path if we are back at its starting state.
        cached = self.win_paths.get(self._level)
        if cached and cached.from_state == self._state_hash and not self._replay:
            self._replay = list(cached.actions)
        if self._replay:
            key = self._replay.pop(0)
            return Plan(actions=[self._to_planned(key)])

        candidates = self._candidates(obs)
        if not candidates:
            return Plan(actions=[])

        untried = [
            key
            for key in candidates
            if not self.ledger.tried_here(self._state_hash, key)
        ]
        pool = untried or [
            key
            for key in candidates
            if not self.ledger.is_known_noop(self._state_hash, key)
        ]
        if not pool:
            pool = candidates  # everything here is a dead end; take the best guess

        best = min(pool, key=self.ledger.exploration_rank)
        return Plan(actions=[self._to_planned(best)])

    def _to_planned(self, key: ActionKey) -> PlannedAction:
        action_id, x, y = key
        self._last_action = key
        self._since_level_start.append(key)
        action = GameAction.from_id(action_id)
        data = {"x": x, "y": y} if action == GameAction.ACTION6 else None
        return PlannedAction(action=action, data=data)

    def on_mismatch(self, obs: Observation, failed: PlannedAction) -> None:
        self._replay = []  # a cached path stopped working; stop trusting it

    def is_done(self, obs: Observation) -> bool:
        return False

"""Uniform-random baseline.

Its only job is to prove the harness end to end and to establish the floor. It
should score ~0: random play rarely completes a level, and the squared metric
punishes the actions it wastes trying.
"""

from __future__ import annotations

import random

from arcengine import GameAction

from .base import Observation, Plan, PlannedAction


class RandomAgent:
    name = "random"

    def __init__(self, seed: int = 0, plan_length: int = 1) -> None:
        self._rng = random.Random(seed)
        self._plan_length = plan_length

    def reset(self, game_id: str) -> None:
        pass

    def plan(self, obs: Observation) -> Plan:
        choices = [a for a in obs.available_actions if a != GameAction.RESET]
        if not choices:
            return Plan(actions=[])

        actions = []
        for _ in range(self._plan_length):
            action = self._rng.choice(choices)
            data = None
            if action == GameAction.ACTION6:
                data = {"x": self._rng.randrange(64), "y": self._rng.randrange(64)}
            actions.append(PlannedAction(action=action, data=data))
        return Plan(actions=actions)

    def on_mismatch(self, obs: Observation, failed: PlannedAction) -> None:
        pass

    def is_done(self, obs: Observation) -> bool:
        return False

"""RHAE scoring, mirroring arc_agi/scorecard.py.

Reimplemented rather than imported so a run can be scored from a recorded action
log without a live scorecard, and so the throughput terms live alongside the score.
Verified against the toolkit's own EnvironmentScoreCalculator in tests/test_scoring.py.

The rules that matter, from the engine source:

* A RESET is charged as an action (``inc_reset_count`` bumps both counters).
* The action counter is monotonic across a run. Per-level tallies are differences
  of the cumulative count at each level completion, so exploration, dead ends and
  resets are all charged to whichever level was in progress.
* A level scores ``(baseline/actions)**2 * 100``, capped at 115.
* A game scores the level-index-weighted mean, capped by the weight of the levels
  actually completed -- finishing 2 of 7 caps the game at (1+2)/28.
* The total is the mean over ALL environments; ones never played score 0 and
  still divide.
"""

from __future__ import annotations

from dataclasses import dataclass, field

LEVEL_SCORE_CAP = 115.0


@dataclass
class LevelResult:
    index: int  # 1-indexed; doubles as the aggregation weight
    baseline_actions: int
    actions_taken: int
    completed: bool

    @property
    def score(self) -> float:
        if not self.completed or self.actions_taken <= 0:
            return 0.0
        raw = (self.baseline_actions / self.actions_taken) ** 2 * 100
        return min(raw, LEVEL_SCORE_CAP)


@dataclass
class GameResult:
    game_id: str
    total_levels: int
    levels: list[LevelResult] = field(default_factory=list)
    wall_seconds: float = 0.0

    @property
    def actions(self) -> int:
        return sum(lv.actions_taken for lv in self.levels)

    @property
    def levels_completed(self) -> int:
        return sum(1 for lv in self.levels if lv.completed)

    @property
    def score(self) -> float:
        """Level-index-weighted mean, capped by completed depth."""
        if not self.levels:
            return 0.0
        total_weight = sum(range(1, self.total_levels + 1))
        if total_weight == 0:
            return 0.0
        earned = sum(lv.index * lv.score for lv in self.levels)
        completed_weight = sum(lv.index for lv in self.levels if lv.score > 0)
        return min(earned / total_weight, completed_weight / total_weight * 100)

    @property
    def ceiling(self) -> float:
        """Best score still reachable given the depth already completed.

        Reported alongside the score to show whether a game is efficiency-limited
        (score near ceiling) or depth-limited (score far below it).
        """
        total_weight = sum(range(1, self.total_levels + 1))
        depth = self.levels_completed
        return sum(range(1, depth + 1)) / total_weight * 100 if total_weight else 0.0


@dataclass
class RunResult:
    games: list[GameResult] = field(default_factory=list)
    scored_environments: int = 0  # unplayed environments score 0 and still divide

    @property
    def score(self) -> float:
        if not self.games:
            return 0.0
        divisor = max(self.scored_environments, len(self.games))
        return sum(g.score for g in self.games) / divisor

    @property
    def actions(self) -> int:
        return sum(g.actions for g in self.games)

    @property
    def wall_seconds(self) -> float:
        return sum(g.wall_seconds for g in self.games)

    @property
    def actions_per_second(self) -> float:
        return self.actions / self.wall_seconds if self.wall_seconds > 0 else 0.0


def levels_from_action_log(
    baselines: list[int],
    cumulative_at_completion: list[int],
    final_cumulative: int,
) -> list[LevelResult]:
    """Turn a monotonic action log into per-level results.

    ``cumulative_at_completion[i]`` is the total action count at the moment level
    i+1 was completed -- exactly what the scorecard records. A trailing partial
    level is included as incomplete so its wasted actions stay visible.
    """
    levels: list[LevelResult] = []
    previous = 0
    for i, cumulative in enumerate(cumulative_at_completion):
        if i >= len(baselines):
            break
        levels.append(
            LevelResult(
                index=i + 1,
                baseline_actions=baselines[i],
                actions_taken=cumulative - previous,
                completed=True,
            )
        )
        previous = cumulative

    partial = final_cumulative - previous
    if partial > 0 and len(levels) < len(baselines):
        levels.append(
            LevelResult(
                index=len(levels) + 1,
                baseline_actions=baselines[len(levels)],
                actions_taken=partial,
                completed=False,
            )
        )
    return levels

"""Open-loop portfolio scheduler for competition-mode runs.

Competition mode: one `make` per environment, no mid-run scorecard, untouched
games score 0 and still divide the mean. Time left on a stuck game is often
worth more as a first-level attempt elsewhere — or as a revisit on a progressing game.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Phase(str, Enum):
    EXPLORE = "explore"  # first touch: try to clear level 1
    EXPLOIT = "exploit"  # continue a game that already cleared >=1
    REVISIT = "revisit"


@dataclass
class GameBudget:
    game_id: str
    allocated_seconds: float
    phase: Phase = Phase.EXPLORE
    levels_completed: int = 0
    spent_seconds: float = 0.0
    abandon_reason: str = ""

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.allocated_seconds - self.spent_seconds)

    @property
    def exhausted(self) -> bool:
        return self.remaining_seconds <= 1e-9 or bool(self.abandon_reason)


@dataclass
class PortfolioPlan:
    total_seconds: float
    scored_environments: int
    games: list[GameBudget] = field(default_factory=list)
    reserve_seconds: float = 0.0

    def next_game(self) -> GameBudget | None:
        for game in self.games:
            if not game.exhausted:
                return game
        return None


def build_equal_explore_plan(
    game_ids: list[str],
    total_seconds: float,
    *,
    scored_environments: int | None = None,
    reserve_fraction: float = 0.08,
    min_seconds_per_game: float = 90.0,
) -> PortfolioPlan:
    """First pass: equal explore budget; hold a reserve for exploit revisits."""
    if total_seconds <= 0:
        raise ValueError("total_seconds must be positive")
    if not game_ids:
        raise ValueError("game_ids must be non-empty")
    scored = scored_environments if scored_environments is not None else len(game_ids)
    reserve = total_seconds * reserve_fraction
    pool = total_seconds - reserve
    per = pool / len(game_ids)
    if per < min_seconds_per_game:
        # Prefer covering fewer games with a usable slice over touching all with noise.
        max_games = max(1, int(pool // min_seconds_per_game))
        chosen = game_ids[:max_games]
        per = pool / len(chosen)
        game_ids = chosen
    games = [GameBudget(game_id=g, allocated_seconds=per, phase=Phase.EXPLORE) for g in game_ids]
    return PortfolioPlan(
        total_seconds=total_seconds,
        scored_environments=scored,
        games=games,
        reserve_seconds=reserve,
    )


def should_abandon(
    *,
    spent_seconds: float,
    allocated_seconds: float,
    levels_completed: int,
    actions: int,
    no_level_progress_seconds: float,
    min_actions_before_abandon: int = 15,
) -> str:
    """Return abandon reason or empty string to continue.

    Hard stop when the slice is gone. Soft abandon when we burned most of the
    slice with zero levels and enough actions to prove we are stuck.
    """
    if spent_seconds >= allocated_seconds:
        return "time_budget_exhausted"
    if (
        levels_completed == 0
        and actions >= min_actions_before_abandon
        and no_level_progress_seconds >= 0.7 * allocated_seconds
    ):
        return "no_level1_progress"
    return ""


def reallocate_on_level(
    plan: PortfolioPlan,
    game_id: str,
    *,
    bonus_seconds: float,
) -> None:
    """Move reserve time onto a game that just cleared a level."""
    target = next((g for g in plan.games if g.game_id == game_id), None)
    if target is None:
        return
    take = min(plan.reserve_seconds, max(0.0, bonus_seconds))
    plan.reserve_seconds -= take
    target.allocated_seconds += take
    target.phase = Phase.EXPLOIT
    target.levels_completed = max(target.levels_completed, 1)


def mark_spent(plan: PortfolioPlan, game_id: str, spent_seconds: float, levels_completed: int, abandon_reason: str = "") -> None:
    game = next((g for g in plan.games if g.game_id == game_id), None)
    if game is None:
        return
    game.spent_seconds += spent_seconds
    game.levels_completed = max(game.levels_completed, levels_completed)
    if abandon_reason:
        game.abandon_reason = abandon_reason
    if game.levels_completed > 0 and game.phase == Phase.EXPLORE:
        game.phase = Phase.EXPLOIT

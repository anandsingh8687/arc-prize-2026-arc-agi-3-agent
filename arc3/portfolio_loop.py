"""Drive a multi-game run from a PortfolioPlan.

Shared scheduler for ``arc3.evaluate`` and the Qwen/Duck budget bridge.
``play_fn`` is injected so unit tests stay free of Duck and the game engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .instrumentation import GameTrace, TraceRecorder
from .portfolio import (
    PortfolioPlan,
    build_equal_explore_plan,
    mark_spent,
    reallocate_on_level,
    should_abandon,
)


@dataclass
class PlayOutcome:
    """Minimal result a play callback must return for portfolio accounting."""

    game_id: str
    wall_seconds: float
    actions: int
    levels_completed: int
    level_indices_completed: list[int] = field(default_factory=list)
    abandon_reason: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    llm_calls: int = 0
    score: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)


PlayFn = Callable[[str, float], PlayOutcome]


@dataclass
class PortfolioRunResult:
    outcomes: list[PlayOutcome]
    plan: PortfolioPlan
    recorder: TraceRecorder | None = None


def run_portfolio(
    game_ids: list[str],
    play_fn: PlayFn,
    *,
    total_seconds: float,
    scored_environments: int | None = None,
    reserve_fraction: float = 0.08,
    min_seconds_per_game: float = 90.0,
    bonus_seconds_on_level: float = 120.0,
    min_actions_before_abandon: int = 15,
    trace_path: str | None = None,
    on_outcome: Callable[[PlayOutcome], None] | None = None,
) -> PortfolioRunResult:
    """Visit games under an equal-explore plan until budgets are exhausted."""
    plan = build_equal_explore_plan(
        list(game_ids),
        total_seconds,
        scored_environments=scored_environments,
        reserve_fraction=reserve_fraction,
        min_seconds_per_game=min_seconds_per_game,
    )
    recorder = TraceRecorder(trace_path) if trace_path else None
    outcomes: list[PlayOutcome] = []

    while True:
        budget = plan.next_game()
        if budget is None:
            break
        max_seconds = budget.remaining_seconds
        if max_seconds <= 1e-9:
            mark_spent(
                plan,
                budget.game_id,
                spent_seconds=0.0,
                levels_completed=budget.levels_completed,
                abandon_reason="time_budget_exhausted",
            )
            continue

        outcome = play_fn(budget.game_id, max_seconds)
        reason = outcome.abandon_reason or should_abandon(
            spent_seconds=outcome.wall_seconds,
            allocated_seconds=budget.allocated_seconds,
            levels_completed=outcome.levels_completed,
            actions=outcome.actions,
            no_level_progress_seconds=outcome.wall_seconds,
            min_actions_before_abandon=min_actions_before_abandon,
        )
        if reason and not outcome.abandon_reason:
            outcome.abandon_reason = reason

        if outcome.levels_completed > budget.levels_completed:
            reallocate_on_level(
                plan,
                budget.game_id,
                bonus_seconds=bonus_seconds_on_level
                * max(1, outcome.levels_completed - budget.levels_completed),
            )

        mark_spent(
            plan,
            budget.game_id,
            spent_seconds=outcome.wall_seconds,
            levels_completed=outcome.levels_completed,
            abandon_reason=outcome.abandon_reason,
        )
        outcomes.append(outcome)
        if on_outcome is not None:
            on_outcome(outcome)
        if recorder is not None:
            recorder.record(
                GameTrace(
                    game_id=outcome.game_id,
                    wall_seconds=outcome.wall_seconds,
                    actions=outcome.actions,
                    levels_completed=outcome.levels_completed,
                    level_indices_completed=list(outcome.level_indices_completed),
                    abandon_reason=outcome.abandon_reason,
                    tokens_in=outcome.tokens_in,
                    tokens_out=outcome.tokens_out,
                    llm_calls=outcome.llm_calls,
                    score=outcome.score,
                    meta=dict(outcome.meta),
                )
            )

    if recorder is not None:
        recorder.write_summary(plan.scored_environments)
    return PortfolioRunResult(outcomes=outcomes, plan=plan, recorder=recorder)

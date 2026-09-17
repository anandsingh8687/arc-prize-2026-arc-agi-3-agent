"""Bridge portfolio + JSONL tracing onto the Qwen/Duck solver surface.

Duck Gate-1 notebooks drive per-game wall via duck-typed solver attributes:

* ``solver.max_runtime_s_per_game`` — per-game wall budget
* ``solver.analyzer_timeout`` — single LLM call timeout (left alone here)

Session/progress rows typically carry ``game_id``, ``levels_completed``,
``actions_taken``, ``active_wall_seconds``, ``llm_calls``, ``generated_tokens``.

This module never imports Duck ``inference``, so local coverage gates stay
GPU-free. Notebooks add the repo root to ``sys.path`` and call the helpers below.

Expect-queue is intentionally *not* wired into the Qwen XML/tool loop — Duck
already executes tool plans; grafting Retrodict-style board expects onto model
tool XML would break the live path. Use ``arc3.expect_queue`` only for non-Duck
local agents that emit ``QueuedAction`` plans.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

from .instrumentation import GameTrace, TraceRecorder
from .portfolio import (
    GameBudget,
    PortfolioPlan,
    build_equal_explore_plan,
    mark_spent,
    reallocate_on_level,
    should_abandon,
)
from .portfolio_loop import PlayOutcome, run_portfolio

ENV_TRACE = "ARC3_TRACE"
ENV_PORTFOLIO_SECONDS = "ARC3_PORTFOLIO_SECONDS"
ENV_SCORED_ENVIRONMENTS = "ARC3_SCORED_ENVIRONMENTS"
ENV_MIN_SECONDS_PER_GAME = "ARC3_MIN_SECONDS_PER_GAME"
ENV_RESERVE_FRACTION = "ARC3_RESERVE_FRACTION"
ENV_BONUS_ON_LEVEL = "ARC3_BONUS_SECONDS_ON_LEVEL"


def resolve_trace_path(cli_value: str | None = None) -> str | None:
    """CLI ``--trace`` wins; else non-empty ``ARC3_TRACE``."""
    if cli_value:
        return cli_value
    env = os.environ.get(ENV_TRACE, "").strip()
    return env or None


def resolve_portfolio_seconds(cli_value: float | None = None) -> float | None:
    if cli_value is not None and cli_value > 0:
        return float(cli_value)
    raw = os.environ.get(ENV_PORTFOLIO_SECONDS, "").strip()
    if not raw:
        return None
    return float(raw)


def resolve_float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    return float(raw) if raw else default


def resolve_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


@dataclass
class DuckBudgetSlice:
    """One portfolio assignment expressed in Duck solver knobs."""

    game_id: str
    max_runtime_s_per_game: float
    phase: str
    allocated_seconds: float
    remaining_seconds: float


def plan_for_qwen(
    game_ids: list[str],
    total_seconds: float,
    *,
    scored_environments: int | None = None,
    reserve_fraction: float | None = None,
    min_seconds_per_game: float | None = None,
) -> PortfolioPlan:
    return build_equal_explore_plan(
        game_ids,
        total_seconds,
        scored_environments=scored_environments
        if scored_environments is not None
        else resolve_int_env(ENV_SCORED_ENVIRONMENTS, len(game_ids)),
        reserve_fraction=reserve_fraction
        if reserve_fraction is not None
        else resolve_float_env(ENV_RESERVE_FRACTION, 0.08),
        min_seconds_per_game=min_seconds_per_game
        if min_seconds_per_game is not None
        else resolve_float_env(ENV_MIN_SECONDS_PER_GAME, 90.0),
    )


def duck_slices(plan: PortfolioPlan) -> list[DuckBudgetSlice]:
    return [
        DuckBudgetSlice(
            game_id=g.game_id,
            max_runtime_s_per_game=g.remaining_seconds,
            phase=g.phase.value if hasattr(g.phase, "value") else str(g.phase),
            allocated_seconds=g.allocated_seconds,
            remaining_seconds=g.remaining_seconds,
        )
        for g in plan.games
        if not g.exhausted
    ]


def apply_budget_to_solver(solver: Any, slice_: DuckBudgetSlice | GameBudget) -> float:
    """Set Duck ``max_runtime_s_per_game`` from a portfolio slice. Returns seconds applied."""
    if isinstance(slice_, GameBudget):
        seconds = float(slice_.remaining_seconds)
    else:
        seconds = float(slice_.max_runtime_s_per_game)
    solver.max_runtime_s_per_game = seconds
    return seconds


def apply_plan_game_to_solver(solver: Any, plan: PortfolioPlan, game_id: str) -> float:
    game = next((g for g in plan.games if g.game_id == game_id), None)
    if game is None:
        raise KeyError(f"game_id {game_id!r} not in portfolio plan")
    return apply_budget_to_solver(solver, game)


def trace_from_duck_row(row: Mapping[str, Any], *, abandon_reason: str = "") -> GameTrace:
    """Convert a Gate-1 progress / session row into a coverage GameTrace."""
    levels = int(row.get("levels_completed") or 0)
    actions = int(row.get("actions_taken") or row.get("actions") or 0)
    wall = float(
        row.get("active_wall_seconds")
        or row.get("wall_seconds")
        or row.get("persisted_elapsed_seconds")
        or 0.0
    )
    indices = row.get("level_indices_completed")
    if indices is None and levels > 0:
        indices = list(range(1, levels + 1))
    reason = abandon_reason or str(row.get("abandon_reason") or "")
    if not reason and levels == 0 and actions > 0:
        state = str(row.get("state") or "")
        if state in {"gave_up", "cancelled"}:
            reason = f"duck_{state}"
    return GameTrace(
        game_id=str(row.get("game_id") or ""),
        wall_seconds=wall,
        actions=actions,
        levels_completed=levels,
        level_indices_completed=list(indices or []),
        abandon_reason=reason,
        tokens_in=int(row.get("tokens_in") or 0),
        tokens_out=int(row.get("generated_tokens") or row.get("tokens_out") or 0),
        llm_calls=int(row.get("llm_calls") or 0),
        score=float(row["final_score"]) if row.get("final_score") is not None else None,
        meta={
            k: row[k]
            for k in ("state", "number_of_levels", "actions_per_level")
            if k in row
        },
    )


def record_duck_rows(
    rows: list[Mapping[str, Any]],
    *,
    trace_path: str,
    scored_environments: int,
) -> dict[str, Any]:
    recorder = TraceRecorder(trace_path)
    for row in rows:
        recorder.record(trace_from_duck_row(row))
    return recorder.write_summary(scored_environments)


def notify_level_and_spend(
    plan: PortfolioPlan,
    *,
    game_id: str,
    wall_seconds: float,
    levels_completed: int,
    actions: int,
    bonus_seconds: float | None = None,
) -> str:
    """Update plan after one Duck game finishes; return abandon reason (may be empty)."""
    game = next((g for g in plan.games if g.game_id == game_id), None)
    prev_levels = game.levels_completed if game else 0
    if levels_completed > prev_levels:
        per = (
            bonus_seconds
            if bonus_seconds is not None
            else resolve_float_env(ENV_BONUS_ON_LEVEL, 120.0)
        )
        reallocate_on_level(
            plan,
            game_id,
            bonus_seconds=per * max(1, levels_completed - prev_levels),
        )
    allocated = game.allocated_seconds if game else wall_seconds
    reason = should_abandon(
        spent_seconds=wall_seconds,
        allocated_seconds=allocated,
        levels_completed=levels_completed,
        actions=actions,
        no_level_progress_seconds=wall_seconds,
    )
    mark_spent(
        plan,
        game_id,
        spent_seconds=wall_seconds,
        levels_completed=levels_completed,
        abandon_reason=reason,
    )
    return reason


def dry_run_budget_api(
    game_ids: list[str],
    total_seconds: float,
    *,
    play_seconds: float = 10.0,
    levels_by_game: Mapping[str, int] | None = None,
) -> tuple[PortfolioPlan, list[PlayOutcome]]:
    """GPU-free harness: fake plays that consume portfolio time via the budget API."""

    class _Solver:
        max_runtime_s_per_game = 0.0

    levels_by_game = dict(levels_by_game or {})

    def play_fn(game_id: str, max_seconds: float) -> PlayOutcome:
        solver = _Solver()
        applied = apply_budget_to_solver(
            solver,
            DuckBudgetSlice(
                game_id=game_id,
                max_runtime_s_per_game=max_seconds,
                phase="explore",
                allocated_seconds=max_seconds,
                remaining_seconds=max_seconds,
            ),
        )
        assert abs(applied - max_seconds) < 1e-9
        assert solver.max_runtime_s_per_game == max_seconds
        # Consume the full portfolio slice (Duck applies one session budget per visit).
        spent = max_seconds
        levels = int(levels_by_game.get(game_id, 0))
        actions = max(15, int(min(play_seconds, max_seconds)))
        return PlayOutcome(
            game_id=game_id,
            wall_seconds=spent,
            actions=actions,
            levels_completed=levels,
            level_indices_completed=list(range(1, levels + 1)),
            meta={"solver_budget": solver.max_runtime_s_per_game},
        )

    result = run_portfolio(
        game_ids,
        play_fn,
        total_seconds=total_seconds,
        min_seconds_per_game=min(90.0, total_seconds / max(1, len(game_ids))),
        bonus_seconds_on_level=30.0,
    )
    return result.plan, result.outcomes

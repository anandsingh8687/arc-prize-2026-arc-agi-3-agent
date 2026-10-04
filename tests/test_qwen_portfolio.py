"""Qwen/Duck budget API bridge — no Duck/GPU required."""

from __future__ import annotations

from pathlib import Path

from arc3.qwen_portfolio import (
    DuckBudgetSlice,
    apply_budget_to_solver,
    dry_run_budget_api,
    notify_level_and_spend,
    plan_for_qwen,
    record_duck_rows,
    resolve_portfolio_seconds,
    resolve_trace_path,
    trace_from_duck_row,
)


def test_resolve_env(monkeypatch) -> None:
    monkeypatch.delenv("ARC3_TRACE", raising=False)
    monkeypatch.delenv("ARC3_PORTFOLIO_SECONDS", raising=False)
    assert resolve_trace_path(None) is None
    assert resolve_trace_path("/tmp/a.jsonl") == "/tmp/a.jsonl"
    monkeypatch.setenv("ARC3_TRACE", "/tmp/env.jsonl")
    assert resolve_trace_path(None) == "/tmp/env.jsonl"
    assert resolve_trace_path("/tmp/cli.jsonl") == "/tmp/cli.jsonl"
    monkeypatch.setenv("ARC3_PORTFOLIO_SECONDS", "3600")
    assert resolve_portfolio_seconds(None) == 3600.0
    assert resolve_portfolio_seconds(120.0) == 120.0


def test_apply_budget_sets_duck_knob() -> None:
    class Solver:
        max_runtime_s_per_game = 0.0

    solver = Solver()
    applied = apply_budget_to_solver(
        solver,
        DuckBudgetSlice(
            game_id="ls20",
            max_runtime_s_per_game=180.0,
            phase="explore",
            allocated_seconds=180.0,
            remaining_seconds=180.0,
        ),
    )
    assert applied == 180.0
    assert solver.max_runtime_s_per_game == 180.0


def test_trace_from_duck_row_and_record(tmp_path: Path) -> None:
    row = {
        "game_id": "r11l-495a7899",
        "levels_completed": 2,
        "actions_taken": 40,
        "active_wall_seconds": 55.5,
        "llm_calls": 3,
        "generated_tokens": 900,
        "final_score": 1.25,
        "state": "gave_up",
    }
    trace = trace_from_duck_row(row)
    assert trace.game_id == "r11l-495a7899"
    assert trace.levels_completed == 2
    assert trace.level_indices_completed == [1, 2]
    assert trace.tokens_out == 900
    summary = record_duck_rows(
        [row, {**row, "game_id": "ft09", "levels_completed": 0, "actions_taken": 20}],
        trace_path=str(tmp_path / "duck.jsonl"),
        scored_environments=25,
    )
    assert summary["games_touched"] == 2
    assert summary["total_levels_completed"] == 2


def test_notify_level_moves_reserve() -> None:
    plan = plan_for_qwen(["a", "b"], total_seconds=1000, min_seconds_per_game=50)
    before = plan.reserve_seconds
    reason = notify_level_and_spend(
        plan,
        game_id="a",
        wall_seconds=30,
        levels_completed=1,
        actions=12,
        bonus_seconds=40,
    )
    assert plan.reserve_seconds == before - 40
    assert reason == ""
    game = next(g for g in plan.games if g.game_id == "a")
    assert game.phase.value == "exploit"


def test_dry_run_budget_api_drives_solver() -> None:
    plan, outcomes = dry_run_budget_api(
        ["g0", "g1", "g2"],
        total_seconds=400,
        play_seconds=50,
        levels_by_game={"g0": 1},
    )
    assert outcomes
    assert all(o.meta.get("solver_budget", 0) > 0 for o in outcomes)
    hot = next(g for g in plan.games if g.game_id == "g0")
    assert hot.levels_completed >= 1


def test_live_reallocate_bumps_solver_mid_session() -> None:
    class Solver:
        max_runtime_s_per_game = 0.0

    from arc3.qwen_portfolio import live_reallocate_if_level_up

    solver = Solver()
    plan = plan_for_qwen(
        ["hot", "cold"],
        total_seconds=1000,
        min_seconds_per_game=50,
        reserve_fraction=0.2,
    )
    # Initial explore apply.
    first = apply_budget_to_solver(
        solver,
        next(g for g in plan.games if g.game_id == "hot"),
    )
    assert first > 0
    reserve_before = plan.reserve_seconds
    bumped = live_reallocate_if_level_up(
        plan,
        solver,
        game_id="hot",
        levels_completed=1,
        bonus_seconds=50,
    )
    assert bumped > first
    assert solver.max_runtime_s_per_game == bumped
    assert plan.reserve_seconds == reserve_before - 50
    # Idempotent for same level count.
    assert (
        live_reallocate_if_level_up(
            plan, solver, game_id="hot", levels_completed=1, bonus_seconds=50
        )
        == 0.0
    )


def test_notify_before_next_apply_changes_subsequent_allocation() -> None:
    """Level complete + partial spend → next apply (revisit) sees exploit leftover."""
    from arc3.qwen_portfolio import drive_sequential_portfolio

    class Solver:
        max_runtime_s_per_game = 0.0

    solver = Solver()
    plan = plan_for_qwen(
        ["hot", "cold"],
        total_seconds=500,
        min_seconds_per_game=40,
        reserve_fraction=0.2,
    )
    # pool=400, per=200 explore each, reserve=100
    hot0 = next(g for g in plan.games if g.game_id == "hot")
    explore_slice = hot0.allocated_seconds
    assert explore_slice == 200.0

    visits: list[tuple[str, float]] = []

    def play_session(game_id: str, applied: float):
        visits.append((game_id, applied))
        if game_id == "hot" and sum(1 for g, _ in visits if g == "hot") == 1:
            # Clear a level after burning only part of the slice; bonus extends revisit.
            return {
                "levels_completed": 1,
                "actions_taken": 20,
                "active_wall_seconds": 60.0,
            }
        # Exhaust whatever remains on later visits / cold.
        return {
            "levels_completed": 1 if game_id == "hot" else 0,
            "actions_taken": 25,
            "active_wall_seconds": applied,
        }

    records = drive_sequential_portfolio(
        solver,
        plan,
        play_session,
        bonus_seconds=80.0,
        max_visits=4,
    )
    assert visits[0] == ("hot", explore_slice)
    # After notify: allocated=200+80=280, spent=60 → remaining=220 for revisit.
    assert len(visits) >= 2
    assert visits[1][0] == "hot"
    assert abs(visits[1][1] - 220.0) < 1e-6
    assert records[0].allocated_after == 280.0
    assert records[0].remaining_after == 220.0
    # Contrast: without session-end notify before next apply, revisit would still
    # see the pre-bonus remaining (200-60=140). Prove the delta.
    assert visits[1][1] > (explore_slice - 60.0) + 1e-6


def test_notify_session_end_skips_double_bonus_after_live() -> None:
    from arc3.qwen_portfolio import live_reallocate_if_level_up, notify_session_end

    class Solver:
        max_runtime_s_per_game = 0.0

    solver = Solver()
    plan = plan_for_qwen(["a", "b"], total_seconds=1000, min_seconds_per_game=50)
    live_reallocate_if_level_up(
        plan, solver, game_id="a", levels_completed=1, bonus_seconds=40
    )
    reserve_after_live = plan.reserve_seconds
    reason = notify_session_end(
        plan,
        game_id="a",
        wall_seconds=30,
        levels_completed=1,
        actions=12,
        already_live_reallocated=True,
    )
    assert plan.reserve_seconds == reserve_after_live
    assert reason == ""

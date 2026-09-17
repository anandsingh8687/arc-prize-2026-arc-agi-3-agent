from arc3.portfolio import (
    build_equal_explore_plan,
    mark_spent,
    reallocate_on_level,
    should_abandon,
)


def test_equal_explore_respects_min_slice() -> None:
    plan = build_equal_explore_plan(
        [f"g{i}" for i in range(50)],
        total_seconds=900,
        min_seconds_per_game=90.0,
        reserve_fraction=0.1,
    )
    assert len(plan.games) <= 9
    assert all(g.allocated_seconds >= 90.0 - 1e-6 for g in plan.games)


def test_abandon_no_progress() -> None:
    reason = should_abandon(
        spent_seconds=80,
        allocated_seconds=100,
        levels_completed=0,
        actions=20,
        no_level_progress_seconds=80,
    )
    assert reason == "no_level1_progress"


def test_reallocate_moves_reserve() -> None:
    plan = build_equal_explore_plan(["a", "b"], total_seconds=1000, min_seconds_per_game=10)
    before = plan.reserve_seconds
    reallocate_on_level(plan, "a", bonus_seconds=50)
    assert plan.reserve_seconds == before - 50
    target = next(g for g in plan.games if g.game_id == "a")
    assert target.phase.value == "exploit"
    mark_spent(plan, "a", spent_seconds=10, levels_completed=1)
    assert target.levels_completed == 1

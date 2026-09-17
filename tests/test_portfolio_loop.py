"""Integration: portfolio scheduler drives play_fn budgets and tracing."""

from __future__ import annotations

from pathlib import Path

from arc3.instrumentation import load_jsonl
from arc3.portfolio_loop import PlayOutcome, run_portfolio


def test_portfolio_loop_abandons_and_traces(tmp_path: Path) -> None:
    calls: list[tuple[str, float]] = []

    def play_fn(game_id: str, max_seconds: float) -> PlayOutcome:
        calls.append((game_id, max_seconds))
        return PlayOutcome(
            game_id=game_id,
            wall_seconds=min(max_seconds, max_seconds * 0.75),
            actions=20,
            levels_completed=0,
        )

    trace = tmp_path / "cov.jsonl"
    result = run_portfolio(
        ["a", "b", "c"],
        play_fn,
        total_seconds=300,
        min_seconds_per_game=50.0,
        reserve_fraction=0.1,
        trace_path=str(trace),
    )
    assert len(calls) >= 1
    assert all(sec > 0 for _, sec in calls)
    assert result.recorder is not None
    rows = load_jsonl(trace)
    assert len(rows) == len(result.outcomes)
    assert any(r.get("abandon_reason") == "no_level1_progress" for r in rows)
    summary = result.recorder.coverage_summary(scored_environments=110)
    assert summary["games_touched"] == len({r["game_id"] for r in rows})
    assert summary["games_untouched"] == 110 - summary["games_touched"]


def test_portfolio_loop_reallocates_on_level(tmp_path: Path) -> None:
    def play_fn(game_id: str, max_seconds: float) -> PlayOutcome:
        levels = 1 if game_id == "hot" else 0
        return PlayOutcome(
            game_id=game_id,
            wall_seconds=max_seconds,  # exhaust slice
            actions=25 if levels == 0 else 10,
            levels_completed=levels,
            level_indices_completed=list(range(1, levels + 1)),
        )

    result = run_portfolio(
        ["hot", "cold"],
        play_fn,
        total_seconds=200,
        min_seconds_per_game=40.0,
        reserve_fraction=0.2,
        bonus_seconds_on_level=20.0,
        trace_path=str(tmp_path / "t.jsonl"),
    )
    hot = next(g for g in result.plan.games if g.game_id == "hot")
    assert hot.phase.value == "exploit"
    assert hot.levels_completed >= 1

from pathlib import Path

from arc3.instrumentation import GameTrace, TraceRecorder, load_jsonl


def test_trace_recorder_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "games.jsonl"
    recorder = TraceRecorder(path)
    recorder.record(
        GameTrace(
            game_id="ls20",
            wall_seconds=12.5,
            actions=40,
            levels_completed=2,
            level_indices_completed=[1, 2],
            score=3.1,
        )
    )
    recorder.record(
        GameTrace(
            game_id="ft09",
            wall_seconds=30.0,
            actions=80,
            levels_completed=0,
            abandon_reason="no_level1_progress",
        )
    )
    rows = load_jsonl(path)
    assert len(rows) == 2
    assert rows[0]["game_id"] == "ls20"
    summary = recorder.write_summary(scored_environments=110)
    assert summary["games_touched"] == 2
    assert summary["games_untouched"] == 108
    assert summary["total_levels_completed"] == 2
    assert summary["games_with_zero_levels"] == 1
    assert (tmp_path / "games.summary.json").exists()

"""Check our RHAE against the toolkit's own EnvironmentScoreCalculator.

Everything downstream is measured with this scorer, so it has to agree with the
implementation that actually decides the leaderboard.
"""

from __future__ import annotations

import pytest
from arc_agi import EnvironmentScoreCalculator

from arc3.scoring import GameResult, LevelResult, RunResult, levels_from_action_log


def reference_score(
    baselines: list[int], actions: list[int], completed: list[bool]
) -> float:
    """The toolkit's own calculation, for comparison."""
    calc = EnvironmentScoreCalculator(id="test")
    for i, (baseline, taken, done) in enumerate(zip(baselines, actions, completed)):
        calc.add_level(
            level_index=i + 1,
            completed=done,
            actions_taken=taken,
            baseline_actions=baseline,
        )
    return calc.to_score().score


def ours(
    baselines: list[int], actions: list[int], completed: list[bool], total_levels: int
) -> float:
    levels = [
        LevelResult(index=i + 1, baseline_actions=b, actions_taken=a, completed=c)
        for i, (b, a, c) in enumerate(zip(baselines, actions, completed))
    ]
    return GameResult(game_id="test", total_levels=total_levels, levels=levels).score


@pytest.mark.parametrize(
    "baselines,actions,completed",
    [
        ([10, 20, 30], [10, 20, 30], [True, True, True]),      # exactly human
        ([10, 20, 30], [20, 40, 60], [True, True, True]),      # 2x human -> 25%
        ([10, 20, 30], [5, 20, 30], [True, True, True]),       # beats human, capped
        ([10, 20, 30], [10, 20, 0], [True, True, False]),      # partial depth
        ([22, 123, 73, 84, 96, 192, 186], [22, 150, 0, 0, 0, 0, 0], [True, True, False, False, False, False, False]),
    ],
)
def test_matches_toolkit(baselines, actions, completed):
    assert ours(baselines, actions, completed, len(baselines)) == pytest.approx(
        reference_score(baselines, actions, completed)
    )


def test_level_cap_is_115():
    """Beating the human baseline outright is capped, not rewarded without limit."""
    assert LevelResult(1, baseline_actions=100, actions_taken=1, completed=True).score == 115.0


def test_incomplete_level_scores_zero_but_still_costs():
    level = LevelResult(1, baseline_actions=10, actions_taken=500, completed=False)
    assert level.score == 0.0
    game = GameResult("g", total_levels=5, levels=[level])
    assert game.actions == 500  # wasted actions stay visible


def test_depth_caps_the_game_score():
    """Two of seven levels caps the game at (1+2)/28, however well they were played."""
    levels = [
        LevelResult(1, baseline_actions=10, actions_taken=1, completed=True),
        LevelResult(2, baseline_actions=10, actions_taken=1, completed=True),
    ]
    game = GameResult("g", total_levels=7, levels=levels)
    assert game.score == pytest.approx(3 / 28 * 100)
    assert game.ceiling == pytest.approx(3 / 28 * 100)


def test_unplayed_environments_divide_the_total():
    """A perfect game among 110 environments is worth its share, not the whole score."""
    perfect = GameResult(
        "g",
        total_levels=1,
        levels=[LevelResult(1, baseline_actions=10, actions_taken=10, completed=True)],
    )
    run = RunResult(games=[perfect], scored_environments=110)
    assert run.score == pytest.approx(100 / 110)


def test_action_log_charges_resets_and_dead_ends_to_the_level_in_progress():
    """Level 2's tally is the difference of cumulative counts, not its own actions."""
    levels = levels_from_action_log(
        baselines=[10, 20, 30],
        cumulative_at_completion=[12, 80],  # level 2 took 68, including waste
        final_cumulative=95,
    )
    assert [lv.actions_taken for lv in levels] == [12, 68, 15]
    assert [lv.completed for lv in levels] == [True, True, False]


# -- research/per_level_efficiency.py ------------------------------------------
# Imported here rather than in its own module so the analysis tooling is covered
# by the same suite as the scorer it depends on.

import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent / "research"))
from per_level_efficiency import build, capped  # noqa: E402


def test_full_length_duck_arrays_are_sliced_at_levels_completed():
    """Duck sends every level, not just completed ones.

    Reading the arrays whole scores uncompleted levels as cleared and inflates
    the result.
    """
    games = [
        {
            "game_id": "g",
            "actions_per_level": [10, 20, 0, 0],
            "base_actions_per_level": [10, 20, 30, 40],
            "levels_completed": 2,
            "number_of_levels": 4,
        }
    ]
    run = build(games)
    assert [lv.index for lv in run.games[0].levels] == [1, 2]
    assert run.games[0].total_levels == 4
    # Two of four levels at exactly human pace: (1+2)/(1+2+3+4) * 100.
    assert run.score == pytest.approx(3 / 10 * 100)


def test_counterfactual_cap_is_never_exceeded():
    """Rounding could land above the target; baseline 5 at 1.5x rounds to 8."""
    assert capped(actual=100, baseline=5, efficiency=1.5) == 7  # floor(7.5), not 8
    assert 7 / 5 <= 1.5

    for baseline in range(1, 200):
        for target in (1.0, 1.2, 1.5, 2.0):
            actions = capped(actual=10**6, baseline=baseline, efficiency=target)
            assert actions / baseline <= target or actions == 1


def test_counterfactual_leaves_levels_already_better_alone():
    assert capped(actual=5, baseline=100, efficiency=1.5) == 5

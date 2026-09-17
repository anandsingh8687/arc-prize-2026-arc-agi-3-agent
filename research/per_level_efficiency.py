#!/usr/bin/env python3
"""Correct per-level RHAE efficiency analysis, and the counterfactual.

Replaces the invalid aggregate estimate in v1 of gate1-analysis.md, which divided
total actions (including actions spent on levels never completed) by the count of
completed levels, and compared the result to a mean level-1 baseline rather than
to each level's own baseline.

RHAE compares actions to baseline per level, so the analysis must too.

Input: the raw Duck per-game artifact, one object per game:

    [
      {"game_id": "lp85",
       "actions_per_level":      [41, 55, 30, 22, 18, 60, 0, 0],
       "base_actions_per_level": [17, 38, 31, 16, 41, 60, 26, 159],
       "levels_completed": 6,
       "number_of_levels": 8},
      ...
    ]

Duck serialises FULL-LENGTH arrays covering every level, not just completed ones,
so `levels_completed` is what says where the completed prefix ends. Reading the
arrays without it scores uncompleted levels as though they had been cleared and
inflates the result.

    python research/per_level_efficiency.py run1_levels.json
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arc3.scoring import GameResult, LevelResult, RunResult  # noqa: E402


def capped(actual: int, baseline: int, efficiency: float | None) -> int:
    """Actions after capping at ``efficiency`` times this level's own baseline.

    Floors rather than rounds: rounding can land above the cap (baseline 5 at
    1.5x rounds to 8, a ratio of 1.6), which would break the guarantee that no
    level ends up worse than the target. Never returns 0, which would be an
    undefined ratio.
    """
    if efficiency is None:
        return actual
    return min(actual, max(1, math.floor(baseline * efficiency)))


def build(games: list[dict], efficiency: float | None = None) -> RunResult:
    """Score the games as recorded, or counterfactually at a fixed ratio.

    ``efficiency`` caps each level at that multiple of its own baseline, holding
    depth fixed -- it answers "what would this run have scored if no level had been
    played worse than 1.5x human?" Levels already better than the target are left
    untouched: forcing them down to the target would penalise the agent for the
    levels it plays well and understate the gain.
    """
    run = RunResult(scored_environments=len(games))
    for game in games:
        taken = game["actions_per_level"]
        bases = game["base_actions_per_level"]

        # Duck sends full-length arrays; levels_completed marks the completed
        # prefix. Fall back to the array length only for already-truncated input.
        completed = game.get("levels_completed", len(taken))
        total = game.get("number_of_levels", game.get("total_levels", len(bases)))

        levels = [
            LevelResult(
                index=i + 1,
                baseline_actions=base,
                actions_taken=capped(actual, base, efficiency),
                completed=True,
            )
            for i, (actual, base) in enumerate(
                zip(taken[:completed], bases[:completed])
            )
        ]
        run.games.append(
            GameResult(
                game_id=game["game_id"],
                total_levels=total,
                levels=levels,
            )
        )
    return run


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    games = json.loads(Path(sys.argv[1]).read_text())

    actual = build(games)
    ratios = [
        lv.actions_taken / lv.baseline_actions
        for g in actual.games
        for lv in g.levels
        if lv.baseline_actions
    ]

    print(f"{len(actual.games)} games, {len(ratios)} completed levels")
    print(f"score {actual.score:.3f}\n")

    print("ACTIONS RELATIVE TO EACH LEVEL'S OWN BASELINE")
    print(f"  median {statistics.median(ratios):.2f}x   mean {statistics.fmean(ratios):.2f}x")
    print(f"  best   {min(ratios):.2f}x   worst {max(ratios):.2f}x")
    beat = sum(1 for r in ratios if r <= 1.0)
    print(f"  at or better than human: {beat}/{len(ratios)}")

    print("\nWORST 10 LEVELS BY RATIO (where the squared penalty bites hardest)")
    rows = sorted(
        (
            (lv.actions_taken / lv.baseline_actions, g.game_id, lv.index,
             lv.actions_taken, lv.baseline_actions, lv.score)
            for g in actual.games
            for lv in g.levels
            if lv.baseline_actions
        ),
        reverse=True,
    )[:10]
    for ratio, game, idx, taken, base, score in rows:
        print(f"  {game:<6} L{idx}  {taken:>4} vs {base:>4} = {ratio:>5.2f}x -> {score:>5.1f}%")

    print("\nCOUNTERFACTUAL — same depth, no level worse than the target")
    print(f"  {'as played':<14} {actual.score:>7.3f}")
    for target in (2.0, 1.5, 1.2, 1.0):
        hypo = build(games, efficiency=target)
        print(f"  {f'at {target:.1f}x human':<14} {hypo.score:>7.3f}"
              f"   ({hypo.score / actual.score:.2f}x)" if actual.score else "")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Marginal score from one more level, per game.

RHAE weights level i by i, so the value of a level rises with how deep the game
already is. This ranks the 25 public games by what their NEXT level is worth,
which is the objective function an adaptive scheduler should maximise.

    python research/marginal_value.py research/gate1-run1-levels.json
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path


def marginal_gain(depth: int, total_levels: int, games_scored: int) -> float:
    """Points added to the run total by clearing one more level at human pace.

    The new level carries weight depth+1 out of the game's total weight, and the
    run total is the mean across every scored environment.
    """
    return (depth + 1) * 100 / sum(range(1, total_levels + 1)) / games_scored


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "research/gate1-run1-levels.json")
    games = json.loads(path.read_text())

    rows = []
    for game in games:
        total = game.get("number_of_levels", len(game["base_actions_per_level"]))
        depth = game["levels_completed"]
        if depth >= total:
            continue  # nothing left to win
        bases = game["base_actions_per_level"]
        rows.append((
            marginal_gain(depth, total, len(games)),
            game["game_id"][:4],
            depth,
            total,
            bases[depth] if depth < len(bases) else None,
        ))
    rows.sort(reverse=True)

    print(f"{'game':<6}{'depth':>7}{'next':>6}{'baseline':>10}{'+total':>9}")
    for gain, gid, depth, total, base in rows:
        print(f"{gid:<6}{depth:>3}/{total:<3}{depth+1:>6}{str(base):>10}{gain:>9.3f}")

    zeros = [r for r in rows if r[2] == 0]
    ones = [r for r in rows if r[2] == 1]
    print(f"\n  five zero-completion games -> depth 1 : +{sum(r[0] for r in zeros):.2f}")
    print(f"  ten one-level games        -> depth 2 : +{sum(r[0] for r in ones):.2f}")
    print(f"  five deepest games        +one level : +{sum(r[0] for r in rows[:5]):.2f}")
    print(f"  best single level ({rows[0][1]} L{rows[0][2]+1})          : +{rows[0][0]:.2f}")

    def median_base(subset):
        vals = [r[4] for r in subset if r[4]]
        return statistics.median(vals) if vals else float("nan")

    print("\nhuman baseline for that next level (cost does not offset the gain):")
    print(f"  zero-completion games: {median_base(zeros):.0f} actions")
    print(f"  five deepest games   : {median_base(rows[:5]):.0f} actions")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Can a 3-4 game development gate detect a 2x improvement?

The proposed gate is "2x weighted RHAE per GPU-second on 3-4 games". This
bootstraps the false-positive rate of that gate directly from run 1's own
per-game score distribution, under a true null: two arms, zero real effect.

    python research/gate_power.py
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arc3.scoring import GameResult, LevelResult  # noqa: E402

TRIALS = 200_000


def game_score(g) -> float:
    """RHAE for one game, via the scorer verified against the toolkit.

    An inline reimplementation here scored lp85 at 65.4 against its true 58.33:
    it dropped the completed-depth cap, which binds whenever a level hits the
    115 per-level cap. Use arc3.scoring, which tests/test_scoring.py checks
    against EnvironmentScoreCalculator.
    """
    return GameResult(
        game_id=g["game_id"],
        total_levels=g["number_of_levels"],
        levels=[
            LevelResult(index=i + 1,
                        baseline_actions=g["base_actions_per_level"][i],
                        actions_taken=g["actions_per_level"][i],
                        completed=True)
            for i in range(g["levels_completed"])
        ],
    ).score


def main() -> None:
    scores = [game_score(g) for g in json.load(open("research/gate1-run1-levels.json"))]
    mean = sum(scores) / len(scores)
    sd = (sum((s - mean) ** 2 for s in scores) / (len(scores) - 1)) ** 0.5
    print(f"25 public games: mean {mean:.2f}, sd {sd:.2f}, CV {sd / mean:.0%}")
    print(f"  per-game scores {sorted(round(s, 1) for s in scores)}\n")

    rng = random.Random(0)
    print("TRUE NULL -- two identical arms, no real effect.")
    print("How often does arm B look >= 2x arm A by chance alone?\n")
    print(f"  {'games/arm':>10}  {'P(false 2x)':>12}  {'P(false 1.5x)':>14}")
    for k in (3, 4, 8, 25):
        f2 = f15 = 0
        for _ in range(TRIALS):
            a = sum(rng.choice(scores) for _ in range(k)) / k
            b = sum(rng.choice(scores) for _ in range(k)) / k
            if a <= 0:
                continue
            if b >= 2 * a:
                f2 += 1
            if b >= 1.5 * a:
                f15 += 1
        print(f"  {k:>10}  {f2 / TRIALS:>11.1%}  {f15 / TRIALS:>13.1%}")

    print("\nA gate that fires on a third of null experiments is not a gate.")
    print("The distribution is the reason: one game (lp85) carries 58 of the")
    print("total. Whether it lands in an arm dominates whatever the arm changed.\n")

    # The count of cleared levels is far better behaved than RHAE: it is bounded,
    # roughly symmetric, and no single game dominates it.
    games = json.load(open("research/gate1-run1-levels.json"))
    levels = [g["levels_completed"] for g in games]
    print(f"cleared levels per game: {sorted(levels)}")
    print("LEVELS CLEARED is the better small-set outcome -- bounded, no outlier.\n")
    print(f"  {'games/arm':>10}  {'5% threshold':>14}   meaning")
    for k in (3, 4, 8):
        diffs = sorted(
            sum(rng.choice(levels) for _ in range(k))
            - sum(rng.choice(levels) for _ in range(k))
            for _ in range(TRIALS)
        )
        thresh = diffs[int(TRIALS * 0.95)]
        print(f"  {k:>10}  {'+' + str(thresh + 1):>14}   arm B must clear {thresh + 1}+ more "
              f"levels than arm A\n{'':>28}   across {k} games ({sum(levels) / len(levels) * k:.1f} expected)")

    print("\nBOTH TABLES ASSUME UNPAIRED ARMS -- each arm drawing its own games.")
    print("Playing both arms on the SAME games with matched seeds removes the")
    print("game-selection term, which is the dominant one. What remains is")
    print("run-to-run stochastic variance, measured at 24% CV across three")
    print("25-game runs (8.596 / 7.686 / 5.265) but never decomposed per game,")
    print("because only run 1's per-level arrays were extracted into this repo.")
    print("Run 3's arrays exist in its saved Kaggle output. Extracting them costs")
    print("no GPU and would set the paired threshold by measurement, not theory.")


if __name__ == "__main__":
    main()

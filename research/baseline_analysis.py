#!/usr/bin/env python3
"""Derive the depth/efficiency/throughput requirements for a target RHAE score.

Uses the human baselines the ARC-AGI toolkit exposes per environment. An anonymous
API key is issued automatically, so this needs no credentials.

    uv venv --python 3.12 .venv
    uv pip install --python .venv/bin/python arc-agi
    .venv/bin/python research/baseline_analysis.py

Scoring (arc_agi/scorecard.py):
    level_score = min((baseline/actions)**2 * 100, 115)
    game_score  = sum(level_index * level_score) / sum(all level_indices)
                  capped at max_weights/total_weights*100, i.e. by completed depth
    total       = mean(game_score) over ALL environments
"""

import statistics

from arc_agi import Arcade

# Kaggle evaluation constants, verified against the live competition pages 2026-09-14.
RUNTIME_SECONDS = 9 * 3600
HIDDEN_GAMES = 110


def max_score_at_depth(baselines: list[list[int]], k: int) -> float:
    """Mean ceiling across games when the first k levels of each are completed.

    Completing k of n levels caps a game at sum(1..k)/sum(1..n), however
    efficiently those k were played.
    """
    total = 0.0
    for b in baselines:
        n = len(b)
        kk = min(k, n)
        total += sum(range(1, kk + 1)) / sum(range(1, n + 1)) * 100
    return total / len(baselines)


def main() -> None:
    envs = Arcade().get_environments()
    baselines = [e.baseline_actions or [] for e in envs]
    per_game = RUNTIME_SECONDS / HIDDEN_GAMES

    print(f"{len(envs)} public games, {sum(len(b) for b in baselines)} levels, "
          f"{sum(sum(b) for b in baselines)} total baseline actions")
    print(f"Budget: {RUNTIME_SECONDS}s / {HIDDEN_GAMES} games = {per_game:.1f}s per game\n")

    print("Ceiling by depth (perfect human-equal efficiency):")
    for k in range(1, 11):
        done = sum(1 for b in baselines if len(b) <= k)
        print(f"  depth {k:>2}: {max_score_at_depth(baselines, k):>6.2f}   "
              f"({done} games fully completed)")

    print("\nWhat a target score demands:")
    for target in (8.40, 11.04, 15.0, 25.0):
        for k in range(1, 11):
            ceiling = max_score_at_depth(baselines, k)
            if ceiling >= target:
                # score scales with efficiency^2 against the ceiling
                ratio = (target / ceiling) ** 0.5
                actions = statistics.mean(sum(b[:k]) for b in baselines)
                print(f"  {target:>6}: depth {k} (ceiling {ceiling:.2f}), "
                      f"max {1/ratio:.2f}x human actions, "
                      f"{actions/per_game:.2f} actions/sec sustained")
                break

    whole = statistics.mean(sum(b) for b in baselines)
    print(f"\n  Finishing every level at 1.0x human would need "
          f"{whole/per_game:.2f} actions/sec.")


if __name__ == "__main__":
    main()

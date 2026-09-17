#!/usr/bin/env python3
"""Version 7's eight games: the right baseline, and the regime it is running in.

Two things the live Version 7 numbers cannot be read without.

1. The control arm's comparison baseline is run 1 restricted to THESE EIGHT
   games, not run 1's 25-game 8.596. The subset is not a sample of the same
   population -- it contains lp85, which alone scored 58.33.

2. Eight games share the GPU that twenty-five shared, so each game's token
   share is several times production's. Games in this run stop at the 400-ACTION
   cap rather than at the token budget, which is the opposite of the regime the
   110-game competition run is in.

    python research/v7_subset.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arc3.scoring import GameResult, LevelResult  # noqa: E402

SUBSET = ["bp35", "cd82", "g50t", "ka59", "lp85", "ls20", "sp80", "tn36"]

# Version 7, seed0-control arm, read live at ~1h25m. STILL RUNNING.
V7_CONTROL = {  # game: (levels_completed, total_levels, actions)
    "bp35": (1, 9, 67), "cd82": (2, 6, 218), "g50t": (0, 7, 115), "ka59": (2, 7, 400),
    "lp85": (3, 8, 61), "ls20": (1, 7, 318), "sp80": (1, 6, 400), "tn36": (0, 7, 400),
}
V7_TOKENS, V7_ACTIONS, ACTION_CAP = 943_007, 1_967, 400

# The nine-hour budget, from research/token-budget.md.
RUN_TOKEN_BUDGET, HIDDEN_GAMES = 6_860_000, 110


def score(g: dict) -> float:
    return GameResult(
        game_id=g["game_id"], total_levels=g["number_of_levels"],
        levels=[LevelResult(index=i + 1, baseline_actions=g["base_actions_per_level"][i],
                            actions_taken=g["actions_per_level"][i], completed=True)
                for i in range(g["levels_completed"])],
    ).score


def main() -> None:
    runs = {g["game_id"][:4]: g for g in json.load(open("research/gate1-run1-levels.json"))}

    print("BASELINE -- run 1 restricted to Version 7's eight games")
    total = 0.0
    for s in SUBSET:
        g = runs[s]
        sc = score(g)
        total += sc
        print(f"  {s:<6}{g['levels_completed']}/{g['number_of_levels']:<4}"
              f"{sum(g['actions_per_level']):>5} actions{sc:>8.2f}")
    print(f"  {'mean':<6}{'':>9}{'':>13}{total / len(SUBSET):>8.2f}   <- compare Version 7 to THIS")
    print(f"  not to run 1's 25-game 8.596: lp85 alone carries {score(runs['lp85']):.2f}\n")

    r1_cap = sum(1 for s in SUBSET if sum(runs[s]["actions_per_level"]) >= ACTION_CAP)
    v7_cap = sum(1 for v in V7_CONTROL.values() if v[2] >= ACTION_CAP)
    print(f"REGIME -- games stopped by the {ACTION_CAP}-action cap")
    print(f"  run 1 (25 games sharing the GPU)   {r1_cap} of 8")
    print(f"  Version 7 (8 games sharing it)     {v7_cap} of 8   <- and still running\n")

    r1_tokens_per_game = 3563 * 549.5 / 25
    v7_tokens_per_game = V7_TOKENS / len(SUBSET)
    production = RUN_TOKEN_BUDGET / HIDDEN_GAMES
    print("PER-GAME TOKEN SHARE")
    print(f"  competition, 110 games   {production:>9,.0f}  <- the regime that matters")
    print(f"  run 1, 25 games          {r1_tokens_per_game:>9,.0f}  ({r1_tokens_per_game / production:.1f}x)")
    print(f"  Version 7, 8 games       {v7_tokens_per_game:>9,.0f}  ({v7_tokens_per_game / production:.1f}x, still rising)\n")

    print("CONSEQUENCE. In production the token budget binds and games never reach")
    print(f"{ACTION_CAP} actions. In Version 7 the action cap binds first, so a response cap")
    print("that makes each action cheaper has nowhere to spend the actions it frees.")
    print("Its score benefit is therefore UNDERSTATED here. Read tokens per completed")
    print("level, which is regime-independent -- not the score, which is not.")
    print()
    print(f"To reproduce production's regime in a screen, cap each game at ~{production:,.0f}")
    print("generated tokens rather than letting it run to the action cap.")


if __name__ == "__main__":
    main()

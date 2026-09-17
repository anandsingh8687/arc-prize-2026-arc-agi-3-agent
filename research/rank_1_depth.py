#!/usr/bin/env python3
"""What depth does each score target require?

Efficiency and depth are not comparable levers, and the score alone hides that.
This prints both ceilings from the real level counts so they can be read side by
side: perfect efficiency at today's depth, against simply going deeper.

    python research/rank_1_depth.py
"""
import json

RANK_1_HIDDEN = 18.81
# Local/hidden ratios from every paired observation available; see
# research/transfer.py. Our own 2.2216 is the BEST of the five, so using it
# alone -- as earlier versions of this file did -- states the easiest case.
# CORRECTED: aggregated per CONFIGURATION (n=3), not per hidden draw (n=5).
# A stress range for planning, not a target band -- three points cannot test
# whether the local/hidden relationship is multiplicative at all.
RATIOS = {"best observed": 2.2216,
          "mean of three configs": 2.7674,
          "worst observed": 3.4061}


def game_score(cleared: int, n: int, level_score: float = 100.0) -> float:
    """RHAE for a game clearing `cleared` levels, each scoring `level_score`."""
    return sum(i * level_score for i in range(1, cleared + 1)) / sum(range(1, n + 1))


def main() -> None:
    games = json.load(open("research/gate1-run1-levels.json"))

    def total(depth_of) -> float:
        return sum(
            game_score(min(depth_of(g), g["number_of_levels"]), g["number_of_levels"])
            for g in games
        ) / len(games)

    depths = [g["levels_completed"] for g in games]
    print(f"{len(games)} games, {sum(depths)} levels cleared, mean depth "
          f"{sum(depths) / len(depths):.2f} of {sum(g['number_of_levels'] for g in games) / len(games):.2f} available")
    print(f"rank 1's hidden {RANK_1_HIDDEN} maps to a STRESS RANGE, not a target:")
    for name, r in RATIOS.items():
        print(f"  ratio {r:.4f}  ({name:<24}) -> local {RANK_1_HIDDEN * r:>6.1f}")
    print()

    print("UNIFORM DEPTH, every level at human efficiency")
    for d in range(1, 7):
        print(f"  depth {d} in all {len(games)}   local {total(lambda g, d=d: d):6.2f}")

    print("\nTODAY'S DEPTH PLUS k, every level at human efficiency")
    for k in range(0, 5):
        t = total(lambda g, k=k: g["levels_completed"] + k)
        note = "  <- all efficiency work, perfectly executed" if k == 0 else ""
        print(f"  +{k} levels everywhere   local {t:6.2f}{note}")

    print("\nWHAT RANK 1 MIGHT REQUIRE, ACROSS THE TRANSFER STRESS RANGE")
    for name, r in RATIOS.items():
        target = RANK_1_HIDDEN * r
        need = next((k for k in range(0, 12)
                     if total(lambda g, k=k: g["levels_completed"] + k) >= target), None)
        print(f"  local {target:>5.1f} ({name:<24}) -> +{need - 1} to +{need} levels in EVERY game")
    print("\nNo efficiency lever produces that. Only solving levels we cannot solve")
    print("today. And the range's own width is the argument against tuning on local:")
    print("across three configurations the same local score maps to hidden scores")
    print("1.5x apart, and the relationship may not be multiplicative at all.")


if __name__ == "__main__":
    main()

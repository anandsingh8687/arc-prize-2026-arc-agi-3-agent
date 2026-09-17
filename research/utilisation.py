#!/usr/bin/env python3
"""Was run 1 throughput-bound? Yes. It was at 97.7% of measured saturation.

RETRACTION. An earlier version of this script reported 24.4% utilisation and
3.76x headroom. It divided run 1's generated tokens by FOUR waves of 7,920 s.
The 25 public games ran in ONE wave at game concurrency 28; four waves is the
projection for the 110 hidden games (ceil(110/28) = 4). The denominator was 4x
too large and the entire headroom figure was that error.

research/gate1_math.py:10 states the wave structure in a comment on the constant
itself, and research/token-budget.md:97 already concluded that aggregate
throughput is saturated. Both were in this repository before the claim was made.

    python research/utilisation.py
"""
import json

# Measured in Gate 1 run 1 (research/gate1-analysis.md).
TOKENS_PER_ACTION = 549.5
ACTIONS_PER_CALL = 2.62
WAVE_S = 7920.127764303001  # ONE wave; 25 games at concurrency 28

# Measured on the exact Gate 1 checkpoint at a real 8,194-token shared-prefix
# prompt (research/exact-qwen38-flash-next-probe-2026-09-14.md).
SATURATED_TOK_S = 252.96473239736997

ACTION_CAP = 400


def main() -> None:
    games = json.load(open("research/gate1-run1-levels.json"))
    actions = sorted(sum(g["actions_per_level"]) for g in games)
    total_actions = sum(actions)
    generated = total_actions * TOKENS_PER_ACTION
    achieved = generated / WAVE_S

    print(f"actions            {total_actions} over {len(games)} games in ONE wave")
    print(f"  median per game  {actions[len(actions) // 2]}")
    print(f"  at the {ACTION_CAP} cap    {sum(1 for a in actions if a >= ACTION_CAP)} of {len(games)}")
    print()
    print(f"generated tokens   {generated:,.0f} in {WAVE_S:,.2f} s")
    print(f"  achieved rate    {achieved:.5f} tok/s")
    print(f"  saturated rate   {SATURATED_TOK_S:.5f} tok/s")
    print(f"  utilisation      {achieved / SATURATED_TOK_S:.4%}")
    print(f"  headroom         {SATURATED_TOK_S / achieved:.4f}x")
    print()

    afforded = WAVE_S * SATURATED_TOK_S
    print("what full saturation would have afforded, at run 1's cost per action:")
    print(f"  {afforded:,.0f} tokens = {afforded / TOKENS_PER_ACTION:,.0f} actions"
          f" = {afforded / TOKENS_PER_ACTION / len(games):.0f} per game")
    print(f"  run 1 produced {total_actions:,} = {total_actions / len(games):.0f} per game")
    print()
    print("CONSEQUENCE. There is no idle time to recover. The only way to buy more")
    print("actions is to make each action cost fewer generated tokens, which makes")
    print("the token levers the main lever rather than a secondary one.")
    print()
    print("The 400-action cap still binds on only 1 of 25 games and the median game")
    print("took 113 actions -- but that is the token budget expressing itself, not")
    print("idleness. 'One action per 70 s per game' is 25 games sharing one GPU.")
    print()

    # Run 3 is an independent check on the retraction, from a different
    # configuration. research/gate1-run3-recovery.md: 1h59m15s, 2,551 actions,
    # 1,489,200 generated tokens, C16.
    r3_play = (1 * 3600 + 59 * 60 + 15) - 591.0260334014893
    r3_gen, r3_actions = 1_489_200, 2551
    print("INDEPENDENT CHECK -- run 3 (C16, ~6,600 s cap), same arithmetic:")
    print(f"  play time        {r3_play:,.0f} s  (consistent with a 6,600 s cap)")
    print(f"  achieved         {r3_gen / r3_play:.2f} tok/s")
    print(f"  utilisation      {r3_gen / r3_play / SATURATED_TOK_S:.2%}")
    print(f"  tokens/action    {r3_gen / r3_actions:.1f}  (run 1: {TOKENS_PER_ACTION})")
    print("  Two runs, two configurations, both near saturation. Neither is")
    print("  anywhere near the retracted 24%.")
    print()
    print("RUN 3 CANNOT CALIBRATE THE NOISE FLOOR. It differs from run 1 in TWO")
    print("configuration dimensions -- per-game cap (6,600 vs 7,920 s) and game")
    print("concurrency (16 vs 28) -- so the 8.596 -> 7.686 gap mixes configuration")
    print("effect with randomness and isolates neither. A noise floor needs two")
    print("arms that differ in nothing but the sampling seed.")


if __name__ == "__main__":
    main()

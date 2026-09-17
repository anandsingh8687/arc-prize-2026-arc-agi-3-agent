#!/usr/bin/env python3
"""Three pieces of arithmetic that bear on the strategy, run independently.

    python research/independent_assessment.py
"""
import json, statistics

GAMES = json.load(open("research/gate1-run1-levels.json"))
SUBSET = ["bp35", "cd82", "g50t", "ka59", "lp85", "ls20", "sp80", "tn36"]
RUN1 = {g["game_id"][:4]: g for g in GAMES}

def uniform_depth_score(d):
    """Local score if every one of the 25 games cleared exactly d levels at human pace."""
    return sum(sum(i * 100.0 for i in range(1, min(d, g["number_of_levels"]) + 1))
               / sum(range(1, g["number_of_levels"] + 1)) for g in GAMES) / len(GAMES)


print("=" * 72)
print("1. THE CAP MAKES DEPTH CONVEX -- so is CONCENTRATION optimal?")
print("=" * 72)
print("docs.arcprize.org/methodology: 'To unlock a maximum game score of 100%,")
print("the AI must complete all levels, including the final one.'\\n")
print("depth -> local score, all 25 games, human efficiency:")
prev = 0.0
for d in range(1, 9):
    s = uniform_depth_score(d)
    print(f"  depth {d}   {s:6.2f}   marginal +{s - prev:5.2f}")
    prev = s
print("\n  Marginal value RISES with depth to depth 6. Payoff is convex in depth.")
print("  Convex payoff + roughly linear cost per level => CONCENTRATE, do not spread.\\n")

HIDDEN = 110
print("  If depth were LINEAR in per-game budget, playing only m of 110 games:")
print(f"  {'games played':>13}{'budget x':>10}{'depth':>7}{'played score':>14}{'MEAN over 110':>15}")
for m, depth in ((110, 1), (55, 2), (37, 3), (27, 4), (22, 5), (18, 6)):
    played = uniform_depth_score(depth)
    print(f"  {m:>13}{110/m:>9.1f}x{depth:>7}{played:>14.2f}{m/HIDDEN*played:>15.2f}")
print("\n  Under that assumption abandoning 84% of games would TRIPLE the score.")
print("  The assumption is the whole question, and our own data tests it.\\n")

print("=" * 72)
print("2. OUR DATA SAYS DEPTH IS **NOT** LINEAR IN BUDGET -- the thesis fails")
print("=" * 72)
r1 = sum(RUN1[g]["levels_completed"] for g in SUBSET)
print(f"  Same 8 games, run 1 (25 games sharing the GPU):      {r1} levels")
print("  Gate 2 control arms (8 games sharing the same GPU):  15 and 10 levels")
print(f"  -> roughly 3x the per-game budget, {r1} -> 12.5 mean levels. No reliable gain.\\n")
print("  lp85 alone: 6/8 at 1/25 of the GPU; 8/8 and 1/8 at 1/8 of it.")
print("  Enormous variance, no dependable budget->depth conversion.\\n")
print("  CONCLUSION: on these games the agent is ABILITY-limited, not")
print("  budget-limited. Concentration is theoretically attractive and")
print("  empirically unsupported. It is a cheap test, not a plan.\\n")

print("=" * 72)
print("3. GPT-OSS AT reasoning_effort=high DOES NOT FIT THE ACTION BUDGET")
print("=" * 72)
V3_TOKENS, V3_SECONDS = 4025, 59.799306
RUNTIME, STARTUP, HIDDEN_GAMES = 9 * 3600, 306.5444188117981, 110
oss_rate, qwen_rate = 466.0, 252.96
play = RUNTIME - STARTUP
print(f"  V3: {V3_TOKENS} tokens in {V3_SECONDS:.1f}s at concurrency 1 = "
      f"{V3_TOKENS/V3_SECONDS:.1f} tok/s, request never returned")
print(f"  So ONE high-effort decision exceeds {V3_TOKENS} tokens and >60 s at C1.")
print(f"  The 60 s smoke window could not have contained a single decision.\\n")
for name, rate, per_call in (("GPT-OSS high effort", oss_rate, 4025),
                             ("GPT-OSS at Qwen's call size", oss_rate, 1442),
                             ("Qwen3.8 Flash-Next", qwen_rate, 1442)):
    budget = rate * play
    calls = budget / per_call
    print(f"  {name:<28} {budget/1e6:>5.2f}M tokens  {calls/HIDDEN_GAMES:>5.1f} calls/game"
          f"  {calls/HIDDEN_GAMES*2.62:>6.0f} actions/game")
print("\n  1.85x the throughput buys nothing if each decision costs 2.8x more.")
print("  GPT-OSS is only viable with reasoning effort and/or max_tokens capped")
print(f"  near {oss_rate*play/(4757):.0f} tokens per call -- and that cap is the very")
print("  intervention Gate 2 rejected for Qwen. Untested for GPT-OSS.")

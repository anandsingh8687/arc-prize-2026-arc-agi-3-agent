# Cutting the per-game cap improved the metric we are optimising

Run 3 (the recovered validation, 6,600 s per-game cap) against run 1 (7,920 s),
same 25 public games, same agent, same model.

| | run 1 | run 3 | change |
|---|---:|---:|---:|
| per-game cap | 7,920 s | 6,600 s | **-16.7%** |
| actions | 3,563 | 2,551 | -28.4% |
| generated tokens | 1,958,045 | 1,489,200 | -23.9% |
| levels completed | 40 | 35 | -12.5% |
| local score | 8.596 | 7.686 | -10.6% |
| **tokens per completed level** | **48,951** | **42,549** | **-13.1%** |

## What it means

Cutting 16.7% of wall time cost only 10.6% of score and **improved tokens per
completed level by 13.1%**. The last stretch of each game's allowance is low-yield:
the agent keeps spending tokens without converting them into levels.

**What this does and does not show.** It shows the final 1,320 s per game were
low-yield. It does *not* show that a scheduler can identify the right games to
starve *in advance*. Those are different claims: the first is about waste existing,
the second about predicting where it is. A uniform cap cut needs no prediction at
all -- it starves every game equally, including the ones that would have converted.

Score retention was 7.686 / 8.596 = **89.41%** for a 16.67% cap reduction.

Projected onto the hidden set, at run 3's efficiency the 6.86M token budget buys
**161 levels over 110 games = 1.47 per game**, against 140 = 1.27 at run 1's rate.

Progress toward the targets in `CODEX_NEXT.md`:

```
run 1                48,951
run 3                42,549   <- here
first milestone      39,000
competitive target   31,188
```

## Caveat

**This is not a controlled ablation.** Two separate runs of a stochastic agent,
one cap change, no repetition. The leaderboard has already shown byte-identical
code scoring 1.70 and 1.32, so a single-run 10% difference is within the range
noise could produce.

What makes it worth recording is that the *direction* matches the scheduler
prediction and the magnitude is consistent with run 1's own diagnostic — median
per-game consumption of 7,920.13 s against a 7,920 s allowance, meaning nearly
every game ran to its limit rather than finishing. If time were being converted
into levels at a constant rate, a 16.7% cut would have cost 16.7% of levels. It
cost 12.5%.

Treat it as a hypothesis with supporting evidence, not a result.

## Consequence for the scheduler ablation

**The control must be the shorter uniform cap, not run 1's long cap.**

A uniform cap reduction is already a scheduler with zero predictive content, and it
captured a 13.1% improvement for free. Measuring a marginal-value scheduler against
run 1 would credit it with that same gain and make prediction look valuable when
it contributed nothing.

The question the ablation has to answer is narrower: **what does prediction add
over cutting everything equally?**

```
arm A   uniform 6,600 s cap            the control -- already measured
arm B   uniform cap swept lower        does more blunt cutting keep paying?
arm C   marginal-value scheduler       does targeting beat the BEST blunt cut?
```

**Conditions binding on B and C:**

1. **Identical total GPU-time and token budget.** Otherwise C can win by spending
   more rather than by allocating better, and the comparison measures nothing.
2. **Identical seeds and game order.** The agent is stochastic and the leaderboard
   has shown byte-identical code varying by 10%+; unmatched seeds would swamp the
   effect being measured.
3. **C must beat the best cap found in B**, not the 6,600 s starting point.
   Comparing against a deliberately weak control would let C claim a gain that a
   single tuned constant already delivers.
4. Decided on **weighted RHAE per GPU-second**, not tokens per level or raw score.

If C does not clear that bar, the scheduler is an expensive way to buy what a
smaller number achieves. Arm B is nearly free -- one config value -- and must not
be skipped on the assumption that sophistication wins.

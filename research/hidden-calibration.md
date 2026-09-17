# Our own local-to-Kaggle-public ratio

First competition-scored submission, 2026-09-15. Version 7, **Kaggle Public
Score 2.37**. This is an unseen test subset, but it is not the final private score.

## The correct pairing

```
GATE1_SCORE    {"score": 5.265162984780623}
GATE1_COVERAGE {"games_expected": 25, "games_persisted": 25, "games_terminal": 25,
                "games_with_level": 19, "levels_completed": 31,
                "total_actions": 2723, "total_generated_tokens": 1566282,
                "total_llm_calls": 1137}
```

**Version 7 local 5.2652 -> public leaderboard 2.37 = ratio 2.2216.**

An earlier version of this document paired **run 3's** local 7.686 with Version 7's
public score 2.37 and derived 3.24x. That was wrong: run 3 was a different run and its
score does not belong to this submission. The mistake is the same kind as pairing
the 27B checkpoint's KV measurement with the NVFP4 checkpoint — **a number carried
from one run onto another.**

## What it means -- and does not mean

The ratio is numerically about 7% lower than the reference notebook's 2.40. One
stochastic run on a different game set does **not** establish better transfer.
It is only a provisional planning conversion.

| Public leaderboard target | Local equivalent at the v7 ratio | vs v7 |
|---:|---:|---:|
| 2.37 (us now) | 5.27 | 1.0x |
| 8.44 (2026-09-15 rank-3 cut) | **18.75** | 3.6x |
| 18.81 (2026-09-15 rank 1) | **41.79** | 7.9x |

These equivalents are not predictions. They move with the leaderboard and could
move materially after another byte-identical run because both the local score and
the public-leaderboard score are high variance.

## Coverage remains unmeasured

Kaggle does not expose the scored rerun's runtime or coverage. The ratio cannot
recover either value: a single point cannot separate "hidden games are harder"
from "we reached fewer of them," and the mean score of the reached games is also
unknown. The wave arithmetic
(`625 + 4 x 6,600 = 27,025 s`, inside nine hours) says four waves had *room* to
run, not that they did.

Treat coverage as **unmeasured**. The scheduler stays gated for a better reason
than this: direct competitor evidence that local scheduling gains fail to transfer
(see below).

## Direct evidence against local scheduling gains

A competitor reports that prioritising games which reached level 2 lifted their
local score from roughly **7.6 to 13** -- a 71% improvement -- and *slightly
worsened* their hidden result.
[Discussion 740812](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/discussion/740812)

This is stronger than any inference in this document, and it cuts two ways:

1. **The predictive scheduler stays gated.** Someone has already run roughly the
   experiment we planned and it did not transfer.
2. **Local improvement is not self-evidently progress.** A 71% local gain went the
   wrong way on hidden. Our whole measurement approach reads local numbers as a
   proxy; this is a case where the proxy actively misled.

The second point should temper every local result we adopt, batching included.

## Variance warning

Local score per completed level, across three runs of nearly the same agent:

```
run 1   8.596 / 40 levels = 0.215
run 3   7.686 / 35 levels = 0.220
v7      5.265 / 31 levels = 0.170
```

Version 7 scored 23% less per level than the other two. Which games and which level
indices get cleared matters more than how many — consistent with the level-index
weighting. It also means **a single run's local score is a noisy instrument**, and
the 2.2216 ratio rests on exactly one paired observation.

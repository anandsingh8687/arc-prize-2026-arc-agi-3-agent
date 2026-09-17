# The token budget is the whole problem

Derived from the exact-checkpoint probe (`Qwen3.8-Flash-Next-NVFP4`) and Gate 1 run 1.
Reproduce with `research/token_budget.py`.

## The ceiling

Aggregate decode saturates at **~255 tok/s** and stays there from C8 to C32.
Concurrency changes who waits, not how much work gets done. So the GPU produces a
fixed quantity of tokens in nine hours, and that quantity is the budget:

```
9h minus cold start (625 s)          31,775 s  ->  8.10M tokens
minus the 15% safety margin          26,915 s  ->  6.86M tokens
```

**6.86M generated tokens. That is the entire resource.** Every design decision is
a claim about how to spend them.

## What run 1 spent

| | |
|---|---:|
| tokens | 1,958,045 |
| games | 25 |
| **tokens per game** | **78.3k** |
| tokens per action | 550 |
| actions per LLM call | 2.62 |
| tokens per LLM call | 1,442 |
| levels completed | 40 |
| **tokens per completed level** | **48,951** |

Spread across 110 games, the budget allows **62.4k tokens per game** — so the same
work must be done with **20% fewer tokens per game than run 1 used**.

## The consequence nobody has stated yet

At run 1's token efficiency, the full budget buys:

```
6.86M / 48,951 tokens per level  =  140 completed levels across 110 games
                                 =  1.27 levels per game
```

Run 1 managed 1.60 levels per game on 25 games. **Scaling to 110 games at
unchanged efficiency makes the agent shallower, not deeper** — the per-game token
allowance falls by 20% and depth falls with it.

That is why coverage and depth are not separate problems here. They compete for
one pool of tokens.

## The single number to optimise

**Tokens per completed level.** Everything else is instrumental.

```
run 1                                    48,951
needed for 2 levels/game on 110 games    31,200   (a 36% reduction)
needed for 3 levels/game                 20,800   (a 58% reduction)
```

## Why plan batching is the lever

Run 1 emits 2.62 actions per LLM call at 1,442 tokens per call. Holding tokens per
call fixed and raising actions per call:

| actions/call | tokens/action | actions/game affordable | vs run 1 |
|---:|---:|---:|---:|
| 2.62 (now) | 550 | 113 | 0.80x |
| 4 | 360 | 173 | 1.21x |
| 6 | 240 | 260 | 1.82x |
| 8 | 180 | 346 | 2.43x |

Run 1 averaged 143 actions per game. At the current ratio, scaling to 110 games
*reduces* that to 113. At 6 actions per call it becomes 260.

This is not a throughput optimisation. It is the only identified way to convert a
fixed token supply into more actions, and therefore into more depth. It is what
Gate 4.1 exists to do, and the `Agent` interface in `arc3/agents/base.py` already
returns plans rather than single actions.

**Caveat:** this assumes tokens per call stays flat as plans lengthen. It may not
— a model asked for eight actions may reason longer than one asked for three. The
ablation must measure tokens per call, not assume it.

## The KV ceiling explains the queueing

```
KV cache: 42,910 tokens
  at  4,096-token context -> 10.5 concurrent sequences
  at  8,192-token context ->  5.2 concurrent sequences
  at 16,384-token context ->  2.6 concurrent sequences
```

Run 1 ran game concurrency 28 against roughly five slots. The rest queued. That
matches the observed saturation at C8-C16, and it means **shorter contexts buy
concurrency directly** — though since aggregate throughput is already saturated,
more concurrency mainly improves fairness and latency, not total work.

## What this says about the gates

- **Gate 3 scheduling** matters for *distribution* — which games get the tokens —
  not for producing more of them. Its value is avoiding waste on hopeless games,
  which run 1 demonstrably did not do: median per-game consumption was 7,920.13 s
  against a 7,920 s allowance, so nothing was abandoned early.
- **Gate 4 plan batching** is the only lever that raises total actions.
- **Efficiency work is nearly exhausted**: 23 of 40 completed levels already match
  or beat human action counts, and perfect efficiency at unchanged depth reaches
  only 10.34 locally.

The engineering question Gate 1 leaves is therefore precise: **can plan batching
raise actions per call without proportionally raising tokens per call?** If yes,
depth follows. If no, 6.86M tokens caps what this architecture can reach and the
model or the harness has to change.

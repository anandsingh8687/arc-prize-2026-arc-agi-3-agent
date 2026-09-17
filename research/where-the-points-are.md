# Where the points are

Computed from `research/gate1-run1-levels.json` (Gate 1 run 1, 25 games, 40 levels).
Reproduce with `research/marginal_value.py`.

## The claim this revises

The Gate 1 report concluded: *"The largest opportunity is advancing the five
zero-level games and ten one-level games."*

The level-index weighting says otherwise. RHAE weights level `i` by `i`, so the
value of one more level scales with **how deep the game already is**.

## Marginal value of one more level, at human-equal efficiency

Points added to the 25-game total:

| Target | Gain |
|---|---:|
| All five zero-completion games reach depth 1 | **+0.62** |
| All ten one-level games reach depth 2 | +2.77 |
| The five *highest-marginal-weight* games each gain one level | **+3.25** |
| The five *deepest* games each gain one level | +3.11 |
| `lp85` alone, level 6 -> 7 | +0.78 |

**Correction:** an earlier version of this table labelled the +3.25 row "the five
deepest games". It is not. Ranking by marginal gain gives
`lp85 6/8, ft09 3/6, vc33 3/7, tr87 2/6, sc25 2/6`; the five literally deepest are
`lp85 6/8, tu93 4/9, re86 4/8, vc33 3/7, ft09 3/6`, worth **+3.11**. Marginal
weight depends on `(k+1)/sum(1..n)`, so a shallow game with few total levels can
outrank a deeper game with many. The conclusion survives, the label was wrong.

**One more level in `lp85` is worth more than fixing all five zero games combined.**

Top and bottom of the table:

```
game    depth  next lvl  baseline   +total
lp85    6/8           7        26    0.778
ft09    3/6           4        28    0.762
vc33    3/7           4        61    0.571
tr87    2/6           3        40    0.571
...
sk48    0/8           1        61    0.111
wa30    0/9           1        71    0.089
bp35    0/9           1        21    0.089
```

A first level in `bp35` is worth **0.089**. A seventh level in `lp85` is worth
**0.778** — nearly nine times as much.

## Cost does not offset it

The obvious objection is that deeper levels are harder, so the gain is bought at a
higher price. The human baselines say otherwise: the median baseline for the next
level is **32 actions for the zero games and 32 for the five deepest**. In human
terms the next level costs about the same either way.

## Probability is more complicated than the first version claimed

An earlier version asserted that marginal weight and probability of success both
rise with depth — "an unusual alignment". **That is not supported.** Weight rises;
the probability of clearing the *next* level plausibly falls, because later levels
are harder. The human baselines show difficulty climbing with index:

```
L1 median 29    L4 median 42
L2 median 26    L5 median 41
L3 median 34    L6 median 60
```

What survives is weaker but still useful: a game at depth 6 demonstrates the agent
has *some* working model of it, while a game at zero after 7,920 seconds has
demonstrated the opposite. That is evidence about the agent's grip on the game, not
a guarantee the next level is easy.

So the scheduler cannot rank on weight alone. The priority is closer to:

```
P(clear next level within budget)
  x expected level RHAE
  x next-level weight
  / expected tokens required
```

with `P` estimated from observable signals — recent progress, no-op rate, repeated
states, actions since the last completion, remaining depth.

## Consequence for the Gate 3 scheduler

The objective is not "reach every game equally", and it is not weight alone. Using
the fuller form above, the policy is roughly: **fair trial for every game, then
spend where expected RHAE per token is highest, which in practice means the games
showing progress rather than the ones stuck at zero.**

Run 1 did the opposite — median per-game consumption was 7,920.13 s against a
7,920 s allowance, so the five hopeless games each consumed a full share of the
budget and returned nothing. On a 110-game run that is the single largest
identified waste, and unlike plan batching it needs no model change.

## Two caveats

1. **Coverage has a floor on *attempts*, not on outcomes.** A game never touched
   scores 0 and still divides the total, so every game needs a fair-trial
   allocation. But an earlier version made "games reaching depth 1 must not fall"
   a hard constraint, which is wrong twice over: clearing level 1 is not something
   the scheduler controls, and enforcing it could block a strictly higher-RHAE
   allocation. The floor is that every game is *attempted*; whether it clears
   anything is an outcome, not a budget rule.
2. **This is 25 public games.** The hidden 110 may have a different depth
   distribution, and the weighting argument is only as good as the assumption that
   some games go deep. If the hidden set is uniformly shallow, the marginal
   advantage shrinks.

## What it does not change

Efficiency remains close to exhausted: 23 of 40 completed levels already match or
beat human action counts, and perfect efficiency at fixed depth reaches only
10.336 locally. The two conclusions are consistent — depth is the constraint, and
this document says *which* depth is worth buying.

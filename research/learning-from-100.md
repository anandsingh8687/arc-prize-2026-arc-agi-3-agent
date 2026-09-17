# Learning from the 100-point systems

Answering directly: *there are open-source systems scoring ~100, can we copy them
into first place?* The pattern, yes. The implementations, no — and the reason is
arithmetic, not pessimism. Reproduce with `research/what_100_costs.py`.

## 1. There is no open-source *model* scoring 100

Every system at 95-100 is an open-source **harness** driving a **closed, online
frontier model** — GPT-5.6 Sol, Opus 5, Fable 5. Kaggle gives us one GPU, nine
hours and no internet. The harness is available; the thing doing the work is not.

## 2. CORRECTED — the generated-token gap is 4x to 14x, not 400x to 2,500x

An earlier version of this section divided the public systems' **total** token
counts by our **generated**-token budget. That is apples to oranges: Retrodict's
660M is overwhelmingly cached input — 629M of it — and cached input cannot be
charged against an output budget. Corrected against published output-token
breakdowns:

```
our per-game budget         62,364 generated tokens

system                score   output/game   vs ours
Retrodict             99.86       296,000       4.7x
baseline1 textual     95.97       256,000       4.1x
baseline1 exec        98.77       860,000      13.8x
```

**This is a lower bound on the real gap**, not proof the approach fits: their
contexts are far larger, and processing input still costs GPU time even when
cached. Still, **4-14x on generated tokens is a gap selective modelling can
plausibly attack; 400x would not have been.** The retraction makes the bet more
credible without making it safe.

baseline1's own ablation still prices the expensive half: **+2.80 points for 3.3x
the generated tokens** to go from a textual model to a comprehensive executable
one. Comprehensive modelling is the part we cannot afford, which is exactly why
the bet in `rank-1-plan.md` §8 is *selective*.

## 3. CORRECTED — neither transfer form is supported

Tycho's ablation is the only architecture measurement holding the model fixed:

```
no world model                79.07
single actor-written model    85.36
actor-controlled builder      88.49
auto-triggered builder        83.07
```

An earlier version of this section rejected *adding* +9.42 points to our 5.2652,
then *multiplied* by 1.119x and called 5.89 a prediction. **That is the same
error in a different form.** One run per policy, one model, one inference budget,
from a base of 79.07. Nothing there establishes an additive or a multiplicative
transfer function to Qwen at 5.

The only supported statement:

> Actor-controlled modelling had a positive effect at frontier capability. The
> effect size at Qwen capability is unknown and must be measured.

That is precisely what E0 exists to measure, and it is why E0 comes before the
build rather than after it.

**Correction to the survey:** the auto-triggered builder did not score worse than
no builder. 83.07 beats 79.07. It lost 5.42 to letting the actor choose. The
conclusion — actor-controlled, not always-on — survives; the justification was
overstated.

## 4. CORRECTED — Polyphony's 19.80 is not a one-GPU result

An earlier version called 19.80 "demonstrated at open weights on one GPU" and
treated it as a reachable target. **The one-GPU part was asserted without reading
the repository and is false.** Its published reproduction command:

```
--tensor-parallel-size 8      --max-model-len 262144
--per-game-deadline-s 14400   24-hour window      5 concurrent games
```

```
                  GPU-seconds/game   total GPU-hours
Polyphony             <=     23,040        <=     192
us                           294.5                  9
                        up to 78x           up to 21.3x
```

**These are configured ceilings, not measured consumption.** 192 is simply
8 GPUs x the 24-hour window; 25 games in five four-hour waves is 160 GPU-hours
at full cap before overhead. Actual use is unpublished and lower.

So 19.80 is a valuable **open-weight architectural reference** and nothing more.
Converting it through our transfer ratios is speculative twice over — an
unverified score obtained under 78x our per-game compute, pushed through a ratio
estimated from three configurations:

```
ratio 2.222 (best)            hidden 8.91   above the rank-3 cut
ratio 2.767 (mean of three)   hidden 7.15   BELOW the cut
ratio 3.406 (worst)           hidden 5.81   BELOW the cut
```

Rank 3 is 8.44. **Only the most favourable ratio clears it.** Treat 19.80 as an
aspirational development target, not evidence the prize cut is within reach.

## 5. E0 — the right experiment, on a contract that now supports it

Everything above turns on one unmeasured question: **can Qwen3.8 write a `step()`
that passes verification at all?** If it cannot, the architecture is unavailable
at this model and the decision becomes a model change rather than an architecture
change.

The first version of `arc3/ledger.py` could not run that experiment honestly.
Its contract was `step(state_hash, action)` — **nothing can induce a mechanic
from a digest**; a candidate could only recognise hashes, which is memorisation
by construction. Its synthetic tests validated the arithmetic, not learnability.
Rewritten:

```python
step(state: SimulatorState, action) -> Prediction | UNKNOWN
```

`SimulatorState` carries the board, level, attempt, available actions and
proposed latents. `Prediction` carries changed cells, level transition, status,
available actions, next latents and optionally the next grid — and a prediction
is exact only if **all** of them match, because getting the cells right and the
level wrong would plan straight into a finished level.

Other defects fixed, each pinned by a test:

```
three-way chronological split   60 induce / 20 repair / 20 locked holdout
novel-pair scoring              a table replaying repeated pairs cannot pass
level in the transition key     masked hashes can collide across levels
MIN_CLAIMS and a novel run      one correct claim is not a model
progress requirement            a perfect no-op detector buys no levels
```

### Pass condition

```
soundness 1.0 wherever the candidate claims
whole outcome correct -- cells, level transition, status, available actions
at least 3 consecutive NOVEL held-out transitions
at least one correct prediction that changed something
no reliance on repeated state-action pairs
```

### On failure

A one-game success proves the capability exists. A one-game failure does **not**
prove Qwen cannot do it — it could be a poor representation or an unusually
opaque mechanic. Classify the cause, then try one structurally different game
before screening gpt-oss.

### Order

```
1  fix the ledger contract, integrate real transition recording   <- done / next
2  run corrected E0 on Qwen3.8
3  if E0 passes, build the sparse controller
4  run W / W-repeat / C
5  promote only on additional levels, never token savings
```

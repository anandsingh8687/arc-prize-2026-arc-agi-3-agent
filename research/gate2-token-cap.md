# Gate 2 — the 1024-token response cap. Rejected. (2026-09-16)

Kaggle script version `350147858`, four trials, two seeds x {control, cap1024},
one server session. Benchmark `ok`, HTML export successful, final `nvidia-smi`
clean, no competition submission. Reproduce the arithmetic with
`research/gate2_result.py`.

**Verdict: do not promote, do not submit.** The reasoning below deliberately
rests on the metrics with thousands of samples, not on the score.

## What the run resolves

```
                       control     cap1024      change   samples
length-limit rate       0.0023      0.2975     +12,842% 2175/3499
tokens per call      1288.3246    708.8845        -45.0% 2175/3499
actions per call        2.8543      1.7102        -40.1% 2175/3499
tokens per action     451.3702    414.5032         -8.2% 6208/5984
```

The mechanism closes exactly:

```
tokens/call -45.0%  x  calls +60.9%  =  total tokens -11.5%
```

**The cap did not make decisions cheaper. It truncated them mid-plan.** Nearly
thirty percent of capped calls hit the length limit, against 0.23% for control,
so the model could not finish a plan; actions per call fell almost as far as
tokens per call did, the agent needed 61% more calls, and only 8.2% was
recovered on tokens per action.

That is the finding, and it has thousands of samples behind it.

## The actual verdict metric

```
tokens per completed level   control  112,084
                             cap1024  118,114   +5.4%  WORSE
```

The cap was proposed to buy more decisions from a fixed 6.86M-token budget. It
bought fewer completed levels per token. Gate 2's first milestone was to bring
48,951 below ~39,000; this went the wrong way. **That is why it is rejected** --
not the score.

## What the run does NOT resolve

The reject is right; the -65% headline is not a measurement.

```
control RHAE by seed   13.568 and 3.464    spread 3.92x
cap     RHAE by seed    3.372 and 2.547    spread 1.32x
```

**The control arm's own seed-to-seed spread is larger than the control-versus-cap
difference.** And it has one cause: `seed0-control` won `lp85` 8/8, worth 87.83
as a game score, which is **10.979 of that arm's 13.568 -- 81% of it.** The other
seven games total 2.588. `lp85` was won in one of four trials. A single coin flip
drives the headline.

Paired by seed, which is the comparison actually available:

```
       RHAE control  RHAE cap  ratio   levels c  levels k  delta
seed0        13.568     3.372  0.249         15        11     -4
seed1         3.464     2.547  0.735         10        10      0
```

Both ratios below 1, so the direction is consistent -- but they differ threefold.
**-65.4% is a real observed point estimate for this experiment; it is not a
precise estimate of the general effect**, and quoting it to sixteen significant
figures states a precision the design cannot support.

## The most useful thing this run produced

Not the cap verdict. **The first direct measurement of seed sensitivity on this
subset**, from two identical configurations:

```
RHAE varied            3.92x
cleared levels varied  1.50x     -- 2.6x more stable
```

`rank-1-plan.md` §5 gates E2 on additional cleared levels rather than score. That
was an argument; it is now a measurement. It also sharpens why E2 still needs its
same-seed `W-repeat` arm: this number is **seed** sensitivity, and the null for a
seed-paired comparison is execution nondeterminism, which remains unmeasured.

Consistency check: control mean 8.516 against run 1 restricted to these same
eight games, 9.45 (-9.9%, `research/v7_subset.py`). The subset baseline holds and
the agent has not regressed.

## CORRECTED — what this does and does not eliminate

An earlier version of this section concluded "the token levers cannot be the
strategy". **Too broad, and retracted.** This run rejects exactly one lever:
blunt truncation. Plan batching, deterministic execution between decision points
and verified world models all work the *other* way round -- they aim to raise the
number of correct actions per completed reasoning call. The cap lowered it, by
40.1%. Opposite mechanism, and `actions per call` is precisely the variable that
separates them.

Nor does this run price batching, and it is worth showing why, because the
arithmetic looks inviting. Fitting `tokens/call = F + M x actions/call` across the
two arms gives a marginal cost of **506.5 tokens per planned action** and an
implied fixed overhead of **-157.2 tokens per call**. A negative fixed cost is
nonsense, so the linear model does not fit these two points -- and it should not,
because **truncating a response is not the same intervention as asking for a
different plan length.** The cap clipped the output distribution; batching changes
what is requested. Any headroom projected from this run would be the same error
this section just corrected.

What *does* survive, from a different route entirely: `research/rank_1_depth.py`
shows every efficiency lever executed perfectly is worth local 10.34, against
needing two to five more cleared levels in every game. That argument stands on the
depth arithmetic, not on this experiment.

## If a cap is ever revisited

Do not sweep blind. The missing measurement is the **control arm's response-length
distribution**: we have its mean, 1288 tokens per call, and not its percentiles. A
cap is only harmless above roughly the 95th percentile of that distribution, and
1024 sits below the mean. Extract the distribution from the saved per-call data
first, then either place a cap above it or conclude that no useful cap exists.

## Lifecycle defect, again

```
GATE2_FINAL_STATUS  logical_exit_code 1, post_teardown_gpu_rows [pid 238, "[No data]"]
GATE2_GPU_DRAIN     fallback_kills [pid 238], remaining []
GATE2_TEARDOWN_RECOVERED  post_owned [], shutdown_ok true
final nvidia-smi    0MiB / 97887MiB, no running processes
```

A bookkeeping false negative: the terminal gate read a **stale** snapshot
containing PID 238 after the recovery had already killed it and a fresh query had
confirmed an empty table. Measurements are unaffected.

This is the third teardown false negative (v5, v10, now this). `run-discipline.md`
rule 3b item 2 already requires re-polling `nvidia-smi` after the bounded exact-PID
drain and reconciling against the fresh table; the final status is evidently still
reading the pre-drain snapshot. The rule is right and the implementation does not
follow it yet.

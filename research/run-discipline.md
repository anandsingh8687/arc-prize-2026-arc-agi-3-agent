# Run discipline

Standing rules for anything that costs more than ten minutes of GPU. Effective
2026-09-15.

Written after a Gate 1 validation burned **1h 59m** and died in teardown — a
defect already identified in run 1 and carried forward as a checklist item
rather than fixed. The benchmark's saved artifacts were later recovered, but
the failure still delayed the gate and made the measurement appear lost.

## 1. Never let a long run's result depend on an untested short operation

The teardown that killed the run takes seconds. It gated two hours of work.

**Smoke-test the whole lifecycle first, at minimum scale:**

```text
start vLLM -> play ONE game for 60 seconds -> write results -> tear down -> exit 0
```

**Budget the smoke from server-ready, not from notebook start.** Version 8 failed
this way: a 600 s whole-notebook guard was consumed by 480 s of model startup plus
setup, leaving the game 3.85 s and zero actions. The smoke reported
`Public runs produced no actions.` -- a true statement about a test that never got
to run.

Startup is not a constant. It measured 625 s in the Version 7 profile and 480 s in
Version 8, so any fixed whole-notebook guard is fragile. The correct shape:

```
startup        generously bounded, ~900 s, and NOT counted against the game
server ready   <- start the clock here
game window    60 s, measured from server-ready
teardown       bounded
```

Assert the server-ready timestamp explicitly and derive the game deadline from it.
A smoke that ends with zero actions is a failed *test*, not a failed agent, and
must be reported as such.

No Kaggle run longer than ten minutes may start until the exact notebook code
and serving configuration intended for that run has passed this end-to-end
smoke test. The smoke must:

1. start the production vLLM server;
2. play one game for 60 seconds;
3. persist the game result and submission artifacts;
4. run the production teardown path;
5. exit with code 0; and
6. show, using `nvidia-smi`, that no owned vLLM worker remains.

Changing lifecycle, serving, persistence, shutdown, model, or process-management
code invalidates the previous smoke result. A new smoke test is required before
another run longer than ten minutes.

## 1b. Amortise startup across experiment arms

Model startup costs 480-625 s and buys nothing. An ablation that runs each arm in
its own notebook session pays it every time: three plan lengths run separately is
~24 minutes of pure startup, against ~8 minutes if one session serves all three
arms in sequence.

Run every arm of a sweep inside a single session wherever the arms differ only in
agent configuration. It also removes startup variance as a confound between arms,
which matters because the arms are being compared on GPU-seconds.

## 2. Results must survive a crash anywhere after the benchmark

Write per-game results to disk **atomically as each game finishes**, not in one
block at the end. Emit one progress line per completed game with elapsed time.
A run that completes the work and dies in cleanup must still yield its data.

Structure the notebook so benchmark and shutdown are independent:

```python
try:
    results = run_benchmark()
finally:
    persist(results)        # always, even on exception
try:
    teardown()
except Exception as exc:
    log(f"teardown failed: {exc}")   # never re-raise past persisted results
```

## 3. Separate "the work succeeded" from "the process exited cleanly"

These are different facts and must be reported separately. A teardown failure
is an infrastructure defect to fix; it is not evidence the benchmark was
invalid. Raising it as a cell error conflates the two and throws away the result.

Teardown may still **block a competition submission** — a surviving GPU worker
on a nine-hour run is a real risk. It must not block *measurement*.

Never submit a version unless teardown passes its terminal gate, the hard
runtime guard remains unused, the submission schema is valid, and the required
runtime margin is preserved.

## 3b. Hardware is teardown authority; preserved evidence is measurement authority

Teardown has now blocked three runs (v7, v10, and the Gate 2 comparison smoke),
each time in a different way. The latest is the clearest: the benchmark completed
both arms, Kaggle marked the run successful, and the final `nvidia-smi` audit
showed **0 MiB and no running processes** -- while the gate reported "bounded
terminal gate did not pass after recovery" and set `logical_exit_code 1`.

For process cleanup, the live process state is authoritative. An earlier GPU
snapshot cannot override a later successful query showing that the exact owned
PID/start-time identity has gone. The cleanup condition is:

```
port closed + no owned CPU/GPU process + no identity conflict  ->  cleanup PASS
```

The measurement has a separate condition: required artifacts and final metrics
must have been preserved while the endpoint was still live. Those checks still
fail closed. A recovery flag or a teardown command's non-zero return code is
diagnostic; it cannot override the conjunction of preserved first-attempt
evidence and a clean current process table.

### Confirmed cause: a second teardown destroyed the evidence chain

The multi-arm ownership theory was wrong: both arms shared one vLLM server and
teardown ran only after both trials. The initial teardown preserved metrics and
artifacts, closed the port, reported zero CPU survivors, and identified the real
worker PID 238 as the one remaining GPU row. That row disappeared
`0.013733579000017926` seconds later.

The wrapper then invoked teardown again. The endpoint was already closed, so the
second attempt necessarily reported `metrics_preserved=false` and overwrote the
valid first result. The wrapper treated that expected second-attempt limitation
as a failed terminal gate.

### What to check

1. Preserve the first live attempt's identity, metrics, artifact and port evidence.
2. Re-poll `nvidia-smi` after bounded exact-PID drain and reject query errors.
3. Reconcile those two evidence sources. Invoke teardown again only when a real
   CPU/process-state survivor needs another cleanup attempt; never replace the
   first attempt's metrics evidence with the closed-endpoint retry.

## 4. Fix defects before they are rediscovered

A defect seen once is a defect that will happen again. "Fix before submitting"
in a checklist is not a fix. Either it is repaired before the next long run, or
the run is structured so it cannot destroy the output.

## 5. Checkpoint and record evidence

For anything over an hour, emit a progress line per completed game with elapsed
time. A stalled run should be identifiable in minutes, not at the end.

Before promotion, record the notebook version, exact serving profile, exit code,
benchmark status, teardown status, post-teardown `nvidia-smi` process table,
artifact list, and runtime.

## Current passing reference: Version 11 (2026-09-15)

The full production path, including the HTML-export fix, passed end to end:

```
Kaggle              "661.0 second run - successful"
GATE1_SERVER_READY  epoch=1789485168.348303  startup_seconds=586.6337132453918
game                10 actions, 9 LLM calls, 7,309 generated tokens
teardown            one draining worker -> GATE1_TEARDOWN_RECOVERED shutdown_ok=true
GATE1_FINAL_STATUS  benchmark=ok, teardown=ok, logical_exit_code=0,
                    post_teardown_gpu_rows=[], smoke_mode=true
GATE1_SMOKE_OK
final nvidia-smi    0 MiB used, no running processes
```

Startup of 586.6 s sits inside the observed 480-625 s band, and the game took its
full window from server-ready -- the Version 8 fix behaving as intended.

**This clears the eight-game comparison to proceed.**

Do not read the smoke's 812 tokens per call as a baseline. Nine calls in a
sixty-second window on one game is not a measurement; the ablation establishes the
real number.

Four consecutive failures preceded it, none in the agent: teardown (2h), smoke
budget (10m), syntax (10.8s), missing attachment (10m). The last two now fail
locally in milliseconds via `research/validate_notebook.py`.

### Earlier reference

Kaggle notebook version `349890386` (`Gate 1 lifecycle smoke v2`) was the first
passing reference for this rule. It used serving profile
`kv5-bf16-mtp3-c16-cg32` and finished successfully in `585.4` seconds.

```text
GATE1_GAME_COMPLETE {"actions_taken": 1, "elapsed_seconds": 20.337635156000033, "game_id": "tn36-ef4dde99", "levels_completed": 0, "state": "cancelled"}
GATE1_GPU_DRAIN {"fallback_kills": [{"pid": 238, "start_ticks": 764474}, {"pid": 238, "start_ticks": 764474}], "owned_pids": [238], "remaining": [], "wait_seconds": 0.5278688879998299}
GATE1_TEARDOWN_RECOVERED {"owned_pids": [238], "post_gpu_rows": [], "post_owned": [], "shutdown_ok": true}
GATE1_FINAL_STATUS {"benchmark": "ok", "logical_exit_code": 0, "post_teardown_gpu_rows": [], "smoke_mode": true, "teardown": "ok", "teardown_error": null}
GATE1_SMOKE_OK
```

The final `nvidia-smi` report showed `0MiB / 97887MiB` and `No running
processes found`. The smoke persisted one terminal game, `score.json`,
`benchmark.json`, and a `submission.parquet` with the expected columns:
`row_id`, `game_id`, `end_of_game`, and `score`.

## Gate 2 Version 5 teardown false negative (2026-09-15)

The paired response-cap smoke completed both arms and Kaggle marked the run
successful, but its logical lifecycle gate failed. The first teardown had
already preserved final metrics and required artifacts, closed the serving
port, and reported zero CPU survivors. One owned GPU row was still draining.
It disappeared `0.013733579000017926` seconds later.

The wrapper then ran the teardown script a second time. Because the endpoint
was already closed, that second attempt could not capture live metrics and
overwrote the valid first result with `metrics_preserved=false`. Treating the
second attempt as the final truth produced `logical_exit_code=1` even though the
final `nvidia-smi` showed `0 MiB` and no processes.

The repaired Gate 2 path keeps the first attempt as the evidence source and
reconciles it against a fresh post-drain process table. It still fails closed
for missing first-attempt metrics or artifacts, invalid process identity,
identity conflicts, CPU survivors, GPU-query errors, and exact owned GPU
survivors. A second teardown is now only a process-cleanup fallback and can no
longer replace the first attempt's metrics evidence. This lifecycle change
invalidates Version 11 for Gate 2 and requires a new short smoke before the
eight-game comparison.

### Passing repair: Version 6

Kaggle script version `350146037` ran the regenerated smoke notebook with SHA-256
`6e44078559da75ef2c7ae114b980fc96fe10ef9278c65c0ee50447076e6bf68c`.
It passed the entire paired lifecycle:

```text
Kaggle               12 minute run - successful
GATE1_SERVER_READY   epoch=1789501180.299865
                     startup_seconds=547.4657666683197
control              7 actions, 11 calls, 5786 generated tokens, 60.17842851200021 s
cap1024              9 actions, 13 calls, 4483 generated tokens, 63.92703201899985 s
teardown             shutdown_ok=true, metrics_preserved=true,
                     required_artifacts_preserved=true, cpu_survivors=0,
                     vllm_gpu_survivors=0
GATE2_LIFECYCLE      benchmark=ok, teardown=ok, hard_guard_triggered=false,
                     post_teardown_gpu_rows=[]
GATE2_FINAL_STATUS   logical_exit_code=0
GATE2_COMPARISON_SMOKE_OK
final nvidia-smi     0 MiB used, no running processes
```

This is the current passing lifecycle reference for the full Gate 2 comparison.

## 6. Pre-register the noise floor before reading a comparison

Decide what size of difference you will believe **before** seeing the numbers.

Three runs of a near-identical agent on the 25 public games scored 8.596, 7.686
and 5.265 -- a 24% coefficient of variation. Sampling 8 games instead of 25 scales
the standard error by `sqrt(25/8) = 1.77`, so an 8-game single run carries a CV
near **42%**, about 3 points on a 5-8 point score.

```
a single-run 8-game arm has a standard error of roughly 3 points
differences below about 4-5 points are not distinguishable from noise
```

This matters for the control-versus-token-cap comparison now running. **Do not
adopt or reject the cap on the headline score alone.** Read instead the quantities
that are per-call or per-action rather than per-run, because they average over
hundreds of samples instead of eight:

```
tokens per LLM call        hundreds of samples, tight
actions per LLM call       hundreds of samples, tight
tokens per action          derived from both, tight
tokens per completed level fewer samples, noisier
local score                eight samples, very noisy
```

If the cap halves tokens per call while actions per call holds, that is a real
finding even if the score moves the wrong way, because the score arm is too noisy
to contradict it. The reverse is also true: a score improvement with unchanged
tokens per call is probably noise.

## 7. Choose a metric with enough samples, then choose a run length

Rule 6 says an 8-game score cannot resolve a 3-point difference. The mistake that
rule half-diagnoses is not the set size — it is reaching for `score` at all.

Per run, the available metrics differ in how much they observe:

```
tokens per LLM call                   ~1,400 observations
actions per LLM call                  ~1,400
no-op and repeated-state rate         ~3,500
parse-failure rate                    ~1,400
tokens per completed level                40
local score                              8-25   <- resolves almost nothing
```

**Observations are not independent samples.** Calls within a game share its state
trajectory, prompt prefix and difficulty, so effective N sits between the game
count and the call count -- closer to the game count for anything outcome-shaped.
An earlier version of this rule read the left column as a sample count and used it
to claim a per-call metric resolves a difference `sqrt(1400/25)` times smaller.
It does not. Per-call metrics are still materially better than score; the design
fix that actually buys resolution is **pairing** -- both arms on the same games
with matched seeds -- not counting calls. See `research/gate_power.py`.

**No run longer than fifteen minutes may be scheduled to decide a question that a
per-call metric could decide.** Before booking GPU time, name the metric, its
sample count, and the pass mark, in that order. If the metric is `score`, the
experiment is probably the wrong shape.

The corollary is the useful one: a question asked in per-call terms usually needs
three paired games and an hour, not eight games and eight hours. See
`research/rank-1-plan.md` §5.

One caution, learned by breaking it. This rule makes cheap arithmetic attractive,
and cheap arithmetic is exactly where a wrong constant does the most damage: a
utilisation claim of 3.76x headroom was published from this repository's own data
by dividing one wave's tokens by four waves' seconds. **Before computing a ratio
from stored constants, read the comment on each constant.** Both the wave
structure (`research/gate1_math.py:10`) and the conclusion it implied
(`research/token-budget.md:97`) were already written down.

## 8. A subset changes the regime, not just the sample size

Run 1 put 25 games on the GPU; Version 7 puts 8. Same hardware, same nine-hour
shape, but each game's token share rises with the reciprocal of the game count:

```
per-game generated-token share
  competition, 110 games      62,364
  run 1, 25 games             78,315   (1.3x)
  Version 7, 8 games         117,876   (1.9x, and rising)
```

The binding constraint moves with it. Run 1 stopped at the token budget and one
game of eight reached the 400-action cap; Version 7 has three of eight at the cap
with the arm unfinished. A token-efficiency change measured where actions bind
cannot be promoted into production where tokens bind.

**Pin the per-game token budget to production's, in every screen.** ~62,400
generated tokens per game is the 110-game figure. A subset chosen for speed
otherwise silently becomes a subset chosen for a different experiment.

Corollary: a subset's baseline is that subset's own score, never the full set's.
Run 1 scores 8.596 over 25 games and 9.45 over Version 7's eight
(`research/v7_subset.py`). Comparing an 8-game arm against 8.596 is a category
error, and `lp85` at 58.33 is most of the difference.

## 9. Gate 2 confirmed rule 6, and priced the thing rule 6 could not

The response-cap comparison (2026-09-16, `research/gate2-token-cap.md`) is the
first run read strictly under rules 6 and 7, and it worked exactly as intended:

```
resolved     length-limit rate 0.23% -> 29.75%, actions/call -40.1%
             thousands of calls; the mechanism closes to the decimal
NOT resolved weighted RHAE -65.4%
             control's own seed-to-seed spread is 3.92x, LARGER than the effect
```

`seed0-control` scored 13.568 because it won `lp85` once, worth **81% of that
arm's total**. One game in one of four trials drove the headline.

The rule that follows: **quote a score difference only after quoting the same
configuration's own spread.** Sixteen significant figures on a quantity whose
replicate varies fourfold is a precision the design cannot support, and it
invites a decision the data does not license -- here, harmlessly, because the
capacity metric agreed. Next time it may not.

### Seed sensitivity, measured

```
identical configuration, two seeds:   RHAE 3.92x    cleared levels 1.50x
```

Cleared levels are **2.6x more stable than score**. Every promotion gate should
use them. This is seed sensitivity, not execution nondeterminism, so it does not
replace the same-seed repeat arm -- it raises how badly that arm is needed.

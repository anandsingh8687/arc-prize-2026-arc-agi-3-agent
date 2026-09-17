# Gate 1 run 1 — analysis (v2, corrected)

Source: Kaggle notebook "ARC-AGI-3 Gate 1 Duck Qwen3.8 Coverage Baseline", run 1.
Local mean RHAE **8.5959343492651522**, 25/25 games reached, 40 levels, 3,563 actions.

**v1 of this document was substantially wrong. See §0 before reading further.**

---

## 0. Retractions from v1

An independent review refuted most of v1. Retracted claims, so they do not get
re-cited:

| v1 claim | Status | Why |
|---|---|---|
| "KV cache allocated at a ninth of what is available (55.23 GiB)" | **RETRACTED** | The 55.23 GiB figure came from probing `qwen3-8-27b-fp8-repacked`, which loads at 28.51 GiB. Gate 1 runs `RadixArk/Qwen3.8-Flash-Next-NVFP4`, which loads at **81.8 GiB**. On a ~94.97 GiB GPU that leaves at most ~13.17 GiB for KV, activations, CUDA graphs and workspace. 5 GiB may be conservative; it is not 11x low. |
| "5 GiB holds 2.4 sequences; the engine was oversubscribed before any game connected" | **RETRACTED** | vLLM pages KV. `max_model_len` is a ceiling, not a per-sequence reservation. `max_num_seqs=8` bounds *concurrently scheduled* sequences; the other 20 clients queue. Queueing adds latency; it is not oversubscription. |
| "KV starvation caused the 23 timeouts" | **RETRACTED** | Duck clamps each request timeout to the remaining per-game and global budget (`solver.py:227`). Requests still pending as the 7,920 s deadline arrives become read timeouts *by construction*. That explains all 23 without invoking KV pressure. Low KV and `max_num_seqs=8` may have added queueing, but this run does not isolate it. |
| "Raise concurrency to 37 or 55" | **UNPROVEN** | The framework does run concurrency-limited waves (`solver.py:896`), so the wave arithmetic holds. But aggregate GPU throughput is already saturated: raising client concurrency divides the same tokens across more games, buying coverage at the cost of depth per game. It needs a score-per-GPU-second ablation, not an assumption. |
| "2.55x human, ~15% per level, 2.9x available at 1.5x" | **RETRACTED** | Invalid arithmetic. The 3,563 actions include actions spent on levels never completed, while 40 counts only completed levels; and 34.9 is the mean *level-1* baseline, not the matching baseline for each completed level. RHAE compares actions to baseline **per level**. See §3 for the correct method. |
| "`tn36` is a loop the agent cannot detect" | **UNPROVEN** | 10.5 actions per LLM call against a 2.6 average is anomalous and worth a trace. It does not show the actions revisited identical states. |

Root cause of the error: a measurement taken from one checkpoint was applied to a
different one, when the 81.8 GiB load figure was present in the same report.
**Memory figures are per-checkpoint and do not transfer.**

---

## 1. What survives — the configuration does not fit in 9 hours

Confirmed independently, using the observed median per-game consumption:

```
591.0260334014893 + 4 x 7920.127764303001  =  32,271.537090613493 s
32,400 - 32,271.537090613493               =       128.462909386507 s
```

**128 seconds of margin on a nine-hour run**, with a known teardown defect that
leaves a vLLM worker alive. An overrun loses the scorecard. This configuration
must not be submitted.

Games were time-limited, not completion-limited: median per-game consumption was
7,920.13 s against a 7,920 s allowance, so nearly every game burned its whole
allocation and none was abandoned early. That is evidence for the Gate 3 adaptive
scheduler, independent of any concurrency change.

The fit can be recovered by reducing per-game allowance, raising concurrency, or
speeding up the model. **Which of those is correct is not yet determined** — the
first two trade depth against coverage and need measuring.

---

## 2. The checkpoint memory question (new, unresolved)

Two checkpoints with very different memory profiles are in play:

| Checkpoint | Weights | Leaves for KV etc. |
|---|---:|---:|
| `qwen3-8-27b-fp8-repacked` (probe) | 28.51 GiB | ~55 GiB measured |
| `RadixArk/Qwen3.8-Flash-Next-NVFP4` (Gate 1) | **81.8 GiB** | ~13 GiB at most |

This is a genuine trade-off rather than a mistake in the Gate 1 setup: the
NVFP4 Flash-Next checkpoint spends most of the GPU on weights, which caps
concurrency no matter how the server is tuned. If the FP8 repacked variant scores
comparably per game, it would admit far more KV and far more concurrent games.

Stated as a question for Gate 2, not a recommendation: **is Flash-Next's quality
worth ~53 GiB of KV capacity?** Nothing measured so far answers that.

---

## 3. Efficiency — the correct method

v1's estimate was invalid. The right computation uses Duck's recorded
`actions_per_level` and `base_actions_per_level`, comparing each completed level
against *its own* baseline:

```
level_score = min((baseline_i / actions_i)^2 * 100, 115)
game_score  = sum(i * level_score_i) / sum(1..n)   capped by completed depth
```

`arc3/scoring.py` in this repository already implements exactly this and is
verified against the toolkit's own `EnvironmentScoreCalculator` (5 tests).
`research/per_level_efficiency.py` consumes the per-level arrays and reports the
true ratio distribution plus a counterfactual: what the score becomes if every
completed level were played at 1.5x or 1.2x its own baseline.

The raw per-level arrays were subsequently extracted from the saved Kaggle run
and recorded in `research/gate1-run1-levels.json`. Running the corrected tool on
all 25 games prints:

```
25 games, 40 completed levels
score 8.596

ACTIONS RELATIVE TO EACH LEVEL'S OWN BASELINE
  median 0.87x   mean 1.29x
  best   0.09x   worst 9.83x
  at or better than human: 23/40

COUNTERFACTUAL — same depth, no level worse than the target
  as played        8.596
  at 2.0x human    8.788   (1.02x)
  at 1.5x human    9.024   (1.05x)
  at 1.2x human    9.609   (1.12x)
  at 1.0x human   10.336   (1.20x)
```

Unrounded values:

| Counterfactual | Score | Factor |
|---|---:|---:|
| As played | 8.595934349265152 | 1.0 |
| No completed level worse than 2.0x human | 8.788326805156839 | 1.0223817967977076 |
| No completed level worse than 1.5x human | 9.02436058538404 | 1.0498405663318628 |
| No completed level worse than 1.2x human | 9.609482917959483 | 1.1179102268016945 |
| Every completed level at human efficiency or better | 10.336219336219335 | 1.2024544297622464 |

The completed-level action-ratio median is `0.8726795803066989`, mean
`1.2915575923147886`, best `0.09302325581395349`, and worst
`9.833333333333334`. Completion depth is distributed as follows:
`{0: 5, 1: 10, 2: 5, 3: 2, 4: 2, 6: 1}`.

**Finding:** broad efficiency is not the main score limiter in this run. Twenty-three
of 40 completed levels are already at or better than human efficiency, and perfect
human efficiency at fixed depth adds only 20.24544297622464%. It still does not
reach the current 11.04 leader score even on the public set. The primary target is
therefore more completed levels, especially in the five zero-completion games and
the ten one-level games. Targeted recovery for the long-tail inefficient levels may
help, but an efficiency-only program cannot close the gap.

Other measured facts:

- 40 levels completed across 25 games — 1.60 per game.
- Distribution is heavily skewed: median game score 3.13, mean 8.60, five games
  at zero, `lp85` alone at 58.33.
- 549.5 generated tokens per action, 2.62 actions per LLM call.
- Cold start 591 s, 1.8% of budget — not worth optimising in isolation.

---

## 4. Exact-checkpoint probe result

The exact Gate 1 checkpoint was subsequently profiled. Full raw measurements and
the saved private Kaggle notebook version are recorded in
`research/exact-qwen38-flash-next-probe-2026-09-14.md`.

Key decision results:

- The checkpoint loads at **81.8 GiB** and vLLM exposes **42,910 KV tokens** with
  the tested configuration.
- At a real 8,194-token shared-prefix prompt, aggregate decode throughput is
  `170.9665160629042` tok/s at C1, `252.96473239736997` at C8,
  `254.92803868668747` at C16, and `251.9829309596138` at C32.
- Aggregate throughput is saturated by C8. C24-C32 mostly divide the same
  throughput among more games; they do not create more model work per second.
- The practical operating range remains **8-16 active sequences**, subject to a
  paired score-per-GPU-second ablation. Coverage above that should come from a
  scheduler, not blind concurrency.

## 5. Remaining Gate 1 experiment

A short probe before any further full run:

1. Extract the **maximum real input-context length** observed in run 1 before
   choosing any lower `max_model_len`.
2. Run a true exact-checkpoint prefix-caching on/off comparison. The cache-on
   metrics are captured, but the exact checkpoint has not yet been relaunched
   with caching disabled.
3. Sweep the real agent at 8 / 16 active sequences with fixed seeds. Synthetic
   throughput is settled; score per GPU-second is not.
4. Gate promotion on: zero analyzer timeouts, clean teardown, and **>= 15%
   projected nine-hour margin**.
5. Only then run replicated validations and produce `submission.parquet`.
6. Submit only after those criteria pass; then measure 110-game coverage and the
   hidden score.

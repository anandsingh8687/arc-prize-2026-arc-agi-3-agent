# Complete-scene screen — neither treatment advances

Source: [private Kaggle notebook Version 1](https://www.kaggle.com/code/anandsingh8687/arc3-scene-screen-20260917), prepared at `eedc1e4`. Public development games only; this was not a competition submission. Frozen protocol: `scene-capability-screen-2026-09-17.md`.

## Decision

**Reject C (image + complete scene) for promotion.** C cleared 3 levels, W 3, W-repeat 4. It did not even exceed the better control, before considering the required margin beyond the one-level repeat difference. Its efficiency score beats the weaker control but not the repeat. Geometry supplied automatically is not a demonstrated depth improvement here.

**T (complete scene, no image) fails the text-viability gate.** T cleared 2 levels against the weaker whole-arm image control W's 3. It lost no more than one level on an individual game, but failed the total-level criterion. This is not proof that all text representations or a different text model must fail; it means this observation contract has not passed the agreed viability test.

No locked transfer, full-25 benchmark, nine-hour run or submission follows automatically. Verified competition score remains **2.37**. These subset RHAE numbers are not scores on the full public set or hidden set.

## Raw arm totals

| Arm | Levels | Weighted RHAE | Actions | Calls | Generated tokens | Allocated-GPU wall seconds |
|---|---:|---:|---:|---:|---:|---:|
| W, image | 3 | 3.0102488766999667 | 228 | 99 | 126459 | 603.135573545 |
| C, image + scene | 3 | 3.4595406217027835 | 201 | 86 | 123498 | 600.144972411 |
| T, scene only | 2 | 1.6460905349794241 | 301 | 109 | 125010 | 619.5771380010001 |
| W-repeat, image | 4 | 3.638741916519694 | 239 | 104 | 131748 | 607.5386617230001 |

Same checkpoint, sampling seed, action limit and nominal 600-second window; three games concurrent per arm on one server. Wall seconds are elapsed arm times on one allocated GPU, not sums across the three game streams. These small, fixed-order arms do not establish a population effect size.

## Raw per-game measurements

Time is the artifact's `trial_elapsed_seconds` at per-game persistence. Exact action/level arrays, active wall times and all delivery counters are retained in `scene-screen-result-data-2026-09-17.json`.

| Arm | Game | Levels | RHAE | Actions | Calls | Generated tokens | Trial elapsed seconds |
|---|---|---:|---:|---:|---:|---:|---:|
| W | cd82 | 0 | 0.0 | 65 | 28 | 39727 | 603.1334679959999 |
| W | ka59 | 1 | 0.9967960128159488 | 70 | 32 | 44954 | 603.1335718859999 |
| W | re86 | 2 | 8.033950617283951 | 93 | 39 | 41778 | 603.1336480159999 |
| C | cd82 | 0 | 0.0 | 89 | 28 | 46232 | 600.142798221 |
| C | ka59 | 1 | 2.0452885317750185 | 48 | 22 | 40296 | 600.142916091 |
| C | re86 | 2 | 8.333333333333332 | 64 | 36 | 36970 | 600.1430000109999 |
| T | cd82 | 0 | 0.0 | 50 | 26 | 41791 | 619.5743710709999 |
| T | ka59 | 1 | 2.160493827160494 | 80 | 41 | 43328 | 619.5744647309998 |
| T | re86 | 1 | 2.7777777777777777 | 171 | 42 | 39891 | 619.574547441 |
| W-repeat | cd82 | 1 | 4.761904761904762 | 63 | 38 | 46892 | 607.5360660629999 |
| W-repeat | ka59 | 1 | 1.7499999999999998 | 65 | 30 | 40310 | 607.5361670729999 |
| W-repeat | re86 | 2 | 4.40432098765432 | 111 | 36 | 44546 | 607.5362473529999 |

## Validity and bounded trace audit

Kaggle status COMPLETE. Saved log prints `SCENE_DELIVERY_ERRORS []`, `SCENE_SCREEN_FINAL clean=true` and `SCENE_SCREEN_OK`. Lifecycle: benchmark_ok=true, teardown_ok=true, no errors, no hard guard, post_teardown_gpu_rows=[], all four trials complete. Startup: 599.595944404602 seconds. Benchmark plus teardown: 2434.614958486 seconds. Every required C/T outer-turn scene was delivered in the declared modality.

Independent verification recomputed every game score from its own completed-level arrays and baseline actions using `arc3.scoring`, reconciled every aggregate against per-game rows, checked matching game sets and scene delivery, then applied the frozen gates. Reproduce with:

```sh
python3 research/scene_screen_result.py research/scene-screen-result-data-2026-09-17.json
```

A read-only follow-up inspected two C transcripts. In cd82, the model still alternated between timer/panel/fill/stamp goal hypotheses near transcript lines 6730–6768, and subsequent DOWN probes had no completion; it cleared no level in 89 actions. In re86 it cleared levels at actions 23 and 60 and inferred a consume-targets rule from recorded changes, but stopped at two completed levels. These are observations of unresolved and partially resolved mechanics, not causal evidence that the renderer helped or harmed.

Artifacts: `/tmp/arc3-scene-screen.wKE6sDdC`. Small exact result data is committed; large traces remain in that directory and the Kaggle output. Fresh GPU quota after completion: 1.92 hours, refresh 2026-09-19 00:00 UTC.

## Bounded next frontier

Retain the existing image baseline. Stop this candidate as preregistered; do not tune it repeatedly on these three games or claim a breakthrough from token savings. The renderer is a verified data-format component, not a promoted agent. A different model or goal/mechanics-learning design remains an untested hypothesis and requires a separately specified, quota-bounded test. This run provides no justified prediction of leaderboard score above 10.

# Structured-memory two-game screen — 2026-09-16

Private Kaggle notebook: https://www.kaggle.com/code/anandsingh8687/arc3-memory-depth-screen-20260916 (version 1)
Source revision: `d1b0b63`. This was a local benchmark, **not** a competition
submission. The verified hidden score remains 2.37.

All three arms completed on one vLLM server with the same sampling seed,
two games per arm, nominal 900-second trial windows. Kaggle status was
`COMPLETE`; the notebook printed `MEMORY_SCREEN_OK`. The initial serving
teardown raised `RuntimeError: vLLM teardown did not reach the bounded terminal
gate`, but bounded recovery passed: `benchmark_ok=true`, `teardown_ok=true`,
`post_teardown_gpu_rows=[]`, `hard_guard_triggered=false`. No trial reported a
validation problem.

| Arm | cd82 levels / score | ka59 levels / score | Total levels | Mean RHAE | Actions | Calls | Generated tokens | GPU seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| W | 0 / 0.0 | 2 / 10.714285714285714 | 2 | 5.357142857142857 | 300 | 125 | 175938 | 900.603963525 |
| M | 2 / 14.285714285714285 | 2 / 10.714285714285714 | 4 | 12.5 | 175 | 101 | 177753 | 932.9076242409999 |
| W-repeat | 2 / 3.7586492768232143 | 1 / 3.571428571428571 | 3 | 3.6650389241258927 | 422 | 132 | 163841 | 916.6909074499999 |

M logged 62 valid memory commits, 32 empty updates, 0 missing updates,
6 rejected updates, and 4 level transitions. It also had 5 no-op actions
of 175 (2.857%) versus 42/300 (14.0%) for W and 60/422 (14.2%) for W-repeat.
These are descriptive, not causal estimates: the controls themselves differ
substantially on the same two games and seed.

## Pre-registered decision

M **fails** the depth promotion gate. It needs at least one additional cleared
level in **both** games relative to **both** controls. On cd82 it ties W-repeat
at 2 levels; on ka59 it ties W at 2 levels. The aggregate 4-versus-2/3 level
comparison and higher mean RHAE are encouraging, but do not satisfy the
pre-registered per-game criterion. Do not spend an eight-game or scored run on
this memory version. Stop this line and pivot to goal discovery / selective
mechanic induction using a new, bounded gate.

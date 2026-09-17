# State-dependent affordance screen — result, 2026-09-17

Private Kaggle notebook: https://www.kaggle.com/code/anandsingh8687/arc3-affordance-screen-20260917
Source revision: `c5fd000` (subsequent `e5f2876` changed documentation only).
Saved raw artifacts: `../run-artifacts/affordance-screen-v1/`. This was a
development benchmark, **not** a competition submission. Verified hidden score
remains **2.37**.

Kaggle status `COMPLETE`; log marker `AFFORDANCE_SCREEN_OK`. The lifecycle
record says `benchmark_ok=true`, `teardown_ok=true`, no hard guard and no
post-teardown GPU rows. Initial graceful teardown returned 1, but bounded
recovery drained the owned worker, so the benchmark artifacts are usable. All
three arms completed, with no validation problems. The addendum appears in all
three A transcripts and in none of the W or W-repeat transcripts. Server-ready
startup was 572.8121380805969 seconds; each arm had a nominal 900-second
window on the same vLLM server.

| Arm | cd82 levels / RHAE | ka59 levels / RHAE | tn36 levels / RHAE | Total levels | Mean RHAE | Actions | Calls | Generated tokens | GPU seconds | Tokens/level |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| W | 3 / 14.818357413273585 | 1 / 2.422145328719723 | 1 / 3.571428571428571 | 5 | 6.937310437807294 | 457 | 159 | 206856 | 916.8794745370001 | 41371.2 |
| A | 2 / 5.692945330316269 | 1 / 3.571428571428571 | 2 / 6.2802391635989165 | 5 | 5.181537688447919 | 287 | 142 | 218036 | 900.2975164200002 | 43607.2 |
| W-repeat | 1 / 0.8523527754296985 | 2 / 10.714285714285714 | 2 / 10.714285714285714 | 5 | 7.426974734667041 | 640 | 185 | 178230 | 902.7039421729996 | 35646.0 |

## Decision: reject this prompt treatment

The pre-registered promotion gate required A to clear at least one extra level
versus **both** controls in at least two games, with no regression versus the
weaker control and no more than 15% extra generated tokens per completed level.
A gained **zero** levels over the stronger control on every game; total levels
were identical across all arms. Its 43,607.2 tokens/level exceed W-repeat's
35,646.0 by about 22.3%, also failing the resource condition. Do **not**
promote to the eight-game transfer screen, full-25 run, or scored submission.
This does not establish that the idea is harmful; three-game runs are noisy.
It establishes that this exact cheap prompt did not clear its decision gate.

## Mechanism check

On `tn36`, A clicked a blue control at action 4 with no level transition, then
clicked the same location at action 34 and advanced. So the state-dependent
retest behavior was present. But W also advanced by revisiting a blue control
at action 31, and W-repeat advanced at action 33. The treatment did not make
the model reliably faster at this selected mechanism, and on the other two
games it did not add depth. In A, level 2 took until action 143 to clear;
W-repeat cleared it at action 60. The level count, not an isolated correct
click, controls the decision.

## Next bounded direction

Do not tune this prompt on these three games: that would optimize against the
same selected evidence. The next hypothesis should target *goal evidence* rather
than another generic reminder. A CPU-only trace audit can compare successful
and stalled turns for the earliest falsifiable goal/progress hypothesis and the
time/actions until it is tested. Only after that audit names a measurable
failure should a different short treatment be built and smoked. No new GPU run
is justified by this result alone.

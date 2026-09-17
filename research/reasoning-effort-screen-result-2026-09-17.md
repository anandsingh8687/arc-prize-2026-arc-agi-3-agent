# Native reasoning-effort screen — result, 2026-09-17

Source: [private Kaggle notebook, Version 1](https://www.kaggle.com/code/anandsingh8687/arc3-reasoning-effort-screen-20260917).
This was a local public-game benchmark, **not** a competition submission.
Protocol and promotion rule were fixed in
[`reasoning-effort-screen-2026-09-17.md`](reasoning-effort-screen-2026-09-17.md)
before launch. W used the checkpoint's default reasoning effort, E used native
`medium` with thinking still enabled and no output cap, and W-repeat used the
same default as W. All arms used one vLLM session, seed 1214842320, the same
three games, concurrency 3, and a 600-second game allowance.

## Verdict: reject E

E cleared **6 levels**, W cleared **6**, and W-repeat cleared **5**. The
preregistered primary rule required E to beat *both* controls in total cleared
levels. It did not. E is not promoted; no eight-game transfer, full-25 run,
scored submission or nine-hour run follows from this result. The verified
hidden score remains **2.37**.

| Game | W levels | E levels | W-repeat levels | W / E / W-repeat actions |
|---|---:|---:|---:|---:|
| `ar25` | 2 | 3 | 2 | 91 / 125 / 105 |
| `lf52` | 1 | 1 | 1 | 24 / 48 / 55 |
| `re86` | 3 | 2 | 2 | 158 / 96 / 97 |

| Arm | Weighted local RHAE | Generated tokens | Actions | LLM calls | GPU seconds | Tokens/action | Tokens/completed level |
|---|---:|---:|---:|---:|---:|---:|---:|
| W | 8.939393939393938 | 132950 | 273 | 118 | 614.9422536879999 | 486.996336996337 | 22158.333333333332 |
| E | 8.939393939393938 | 133973 | 269 | 131 | 603.299642425 | 498.04089219330854 | 22328.833333333332 |
| W-repeat | 5.927452051829597 | 129089 | 257 | 120 | 618.055432608 | 502.2918287937743 | 25817.8 |

The treatment did not even reduce generated tokens across the arms. It moved
one game (`ar25`) forward and another (`re86`) backward relative to W;
W-repeat also failed to reach W's third `re86` level. These three observations
cannot attribute either game-level difference to the reasoning setting.

The saved lifecycle reports `benchmark_ok=true`, `teardown_ok=true`, all three
trials complete, `post_teardown_gpu_rows=[]`, and no hard guard. The teardown
script initially raised, as in the smoke, but bounded recovery left no owned
GPU process and the notebook emitted `REASONING_SCREEN_OK`. There was no
export-layer failure.

## Bounded failure read and next falsification

In E's `re86` transcript, after reaching level 3, the model asserted that
eight apparent dots could not all be covered because it counted a maximum of
seven, then spent later calls reconstructing level 2's winning state from
history (transcript around lines 4313–4365). W reached level 4 at action 107;
E and W-repeat ended at level 3. This is **one observed goal/perception stall**,
not proof that medium reasoning caused it. On `ar25`, E instead reached one
level deeper. A global reasoning-effort knob is not a reliable fix for
game-specific goal and mechanics uncertainty.

The next high-value candidate is a **model-capability comparison**, not another
small prompt/timeout knob. Prepare the already-planned fair text-perception
representation from saved *observations* (never game source code), then test
Qwen3.8 versus gpt-oss-120b on the same short games, seeds and wall/GPU budget.
The text-only model must not be dropped into Duck's image-dependent prompt.
Pre-screen the renderer and action parser on saved traces without GPU; launch a
short smoke only after the full lifecycle is locally valid. Promotion still
requires more completed levels than a same-model repeat, then a locked transfer
set. A faster token rate or plausible text answer alone does not promote it.

This is a candidate experiment, not a prediction of a score above 10 or rank 1.

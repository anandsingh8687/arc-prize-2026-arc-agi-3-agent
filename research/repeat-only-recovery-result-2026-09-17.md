# Repeat-only recovery screen: REJECTED

Date: 2026-09-17 IST. Private Kaggle notebook:
`anandsingh8687/arc3-recovery-repeat-screen-20260917`, Version 1. This was
**not** a scored competition submission. Official hidden score remains **2.37**.

The treatment was preregistered in
`research/repeat-only-recovery-gate-2026-09-17.md`: a structured diagnostic
probe only after repeated apparent interior no-ops, with the 180-second wall
trigger and action-count trigger disabled. Same model/checkpoint, game set,
seed, arm window, and server as the two Duck controls. The exact-code smoke
passed before this screen.

## Result

All three 900-second arm windows completed. `lifecycle.json` says
`benchmark_ok=true`, `teardown_ok=true`, no hard guard and no surviving owned
GPU rows. Initial teardown needed the bounded exact-PID recovery; final
artifacts and metrics were preserved. Source artifacts:
`../run-artifacts/recovery-repeat-screen-v1/gate2-comparison/`.

| Arm | cd82 levels | ka59 levels | tn36 levels | Total levels | Weighted RHAE on these 3 games | GPU seconds | Generated tokens | Probe count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| W | 2 | 1 | 2 | 5 | 5.470662530783876 | 900.241913071 | 214203 | 0 |
| S-repeat | 1 | 2 | 0 | 3 | 3.975568568195451 | 902.2339100020001 | 201572 | 2 |
| W-repeat | 2 | 1 | 2 | 5 | 7.060944542426024 | 905.3101720249997 | 182033 | 0 |

The two S probes were genuine `repeated_interior_noop` triggers: cd82 at
level 1/action 22 (RIGHT probe), ka59 at level 2/action 28 (LEFT probe). Both
changed the board and stayed within their level. `recovery_rejections=2` means
two invalid structured probe attempts were rejected before valid diagnostic
actions executed. S never triggered on tn36.

## Frozen gate and interpretation

The preregistered promotion required S to beat **both** W and W-repeat on at
least two games, regress on none, and stay within 15% extra GPU time. It only
beat them on ka59, regressed on cd82 and tn36, and used roughly the same GPU
time. **Reject; do not run the locked eight-game transfer test or submit.**

The individual difference on tn36 is not attributable to the intervention:
there was no S probe there. W and W-repeat also have materially different
weighted RHAE despite identical settings and seed. These three games cannot
estimate a stable effect size. They can, however, falsify this candidate
against its own promotion rule. The ka59 gain is a useful trace to study, not
evidence to promote the branch or tune its threshold post hoc on these games.

Next work should change hypothesis, not keep searching recovery thresholds
on cd82/ka59/tn36. Keep the crash-proof event instrumentation and the saved
traces; stop spending GPU on this repeat-only treatment. Full public-25 score
above 10 remains the gate before any scored long run.

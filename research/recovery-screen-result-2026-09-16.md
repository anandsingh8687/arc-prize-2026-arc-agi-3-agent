# Recovery screen — 2026-09-16

This was a private Kaggle notebook, **not** a competition submission. The
verified hidden score remains **2.37**. Notebook:
`anandsingh8687/arc3-recovery-depth-screen-20260916`. Raw downloaded output:
`../run-artifacts/recovery-screen-v1/gate2-comparison/` (local, not committed).

## Validity

`lifecycle.json` reports `benchmark_ok=true`, `benchmark_error=null`, all
expected trials `W`, `S`, and `W-repeat` completed, `teardown_ok=true`,
`hard_guard_triggered=false`, and an empty post-teardown GPU process table.
The three arms shared one vLLM server, the same sampling seed and the same
three games. Each arm received approximately 900 seconds of play.

| Arm | cd82 levels / score | ka59 levels / score | tn36 levels / score | Total levels | Three-game weighted RHAE | Generated tokens | GPU seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| W | 0 / 0 | 1 / 0.7524858908895459 | 0 / 0 | 1 | 0.2508286302965153 | 193522 | 908.797949206 |
| S, recovery | 2 / 8.049719985975972 | 2 / 10.714285714285714 | 0 / 0 | 4 | 6.254668566753895 | 204732 | 905.9392694570001 |
| W-repeat | 1 / 4.761904761904762 | 1 / 1.939058171745152 | 1 / 0.11040764572946679 | 3 | 2.270456859793127 | 211645 | 900.3325164509997 |

Source: downloaded `summary.json` for each arm and `progress.json`. These are
**three-game development scores**, not the 25-game public score or hidden
leaderboard score. W and W-repeat differ despite identical configuration and
seed, so causation cannot be assigned from this single screen.

S exceeded both controls by one or more levels on `cd82` and `ka59`, with no
GPU-time penalty versus W. But it reached **zero** levels on `tn36`, while
W-repeat reached one. Therefore it **fails the frozen promotion gate**: no
regression on the third game was required. Do not promote S to a 25-game run
or submit it on this evidence. The positive result on two games remains a
lead worth studying, not a validated multi-game gain.

## Mechanism observed

S logged one recovery probe per game. `cd82` proposed DOWN to distinguish a
vertically movable piece from a spent stamp; the actual action changed 201
grid cells without immediately completing the level. S subsequently cleared
two levels. On `ka59`, it clicked a different square to test whether control
could be transferred; six cells changed, and S later cleared level two.
On `tn36`, it clicked a mark to test whether the mark toggles; four cells
changed, but S did not clear level one. All three recovery prompts were
triggered by 180 seconds without completion, not by the repeated-no-op or
80-action trigger. `cd82` needed one schema rejection/retry before a valid
probe; the other two had none.

One instrumentation defect is visible: the wall-clock fallback populates
`StallSignal.actions_on_level=0` even when the trace has actions (e.g. the
`cd82` probe was action 15). That number must not be used to argue a game had
zero actions. It does not invalidate the recorded action/outcome or the
completed-level comparison, but should be fixed before this signal is reused.

## Decision

Reject the current unconditional 180-second recovery checkpoint as a promoted
agent change. Preserve the probe traces for offline study. Do not reinterpret
the three-game RHAE as evidence of a public score above 10; run an independent
matched screen only after a *specific* trigger improvement is defined and
tested locally. No scored submission was made.

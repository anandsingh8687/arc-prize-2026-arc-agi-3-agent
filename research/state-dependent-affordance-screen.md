# State-dependent affordance screen — 2026-09-17

Current gate: private, short public-game development screen. No competition
submission and no nine-hour run. The verified hidden score remains 2.37.

## Evidence and hypothesis

In the saved `tn36` W transcript, clicking the blue circular control on the
initial board appeared to do nothing. After configuring the T-shaped switches,
clicking it cleared level 1 at action 23. In the S transcript the first inert
click was interpreted as evidence that the circle was decorative. The S run
cleared no level in its 900-second window. This is a *state-dependent action*
failure, not evidence that a longer action plan or a lower response cap helps.

A CPU-side trace audit on the two prior W controls gives stronger, exact
retrospective evidence for this mechanism. For the level-1 completion at action
23 in W, the same click at action 2 changed **zero non-timer cells**. On level 2,
the completion click at action 70 had been tried at actions 24, 34, 50 and 55;
each previous click changed zero non-timer cells. W-repeat likewise cleared
level 2 at action 64 with a click previously tried at actions 31 and 42, both
zero non-timer-cell outcomes. This uses row 1 as the known `tn36` timer band for
retrospective interpretation; it is not a game-general agent heuristic or a
causal treatment result. The treatment still has to win the live comparison.

Hypothesis: making Duck explicitly preserve plausible submit/confirm controls
after a state-specific no-op, and retest them only after a meaningful board
configuration change, increases completed levels at the same time and action
limits. The treatment is a short system-prompt addendum only. It does not add
tools, actions, model calls, or hidden game-specific coordinates.

## Pre-registered screen

Arms: W (plain Duck), A (W plus addendum), W-repeat (plain Duck), same model,
seed, and 900-second arm windows, three games (`tn36`, `cd82`, `ka59`). One vLLM
session; smoke first on the exact built notebook code. Keep individual per-game
traces, calls, actions, generated tokens and time. W-repeat measures execution
variation; it is not a new algorithm.

Mechanism check on `tn36`: determine whether A retries a previously inert,
salient control after modifying the board, and whether a level transition
follows. A success on this selected game alone is **not** transfer evidence.

Promotion to a locked eight-game transfer screen requires A to clear at least
one more level than **both** controls on at least two of the three games, no
regression relative to the weaker control on any game, and no more than 15%
extra generated tokens per cleared level. If only the selected `tn36` game
improves, run at most one different-seed `tn36` confirmation; do not promote.
If the mechanism fails to appear, or completed levels do not improve, stop this
prompt bet. Even a passing short screen does not authorize a scored submission:
the user's full-public-25 local score gate (>10) still applies.

Do not read implementation files under `environment_files/`; only play games
through the documented API and inspect saved action traces.

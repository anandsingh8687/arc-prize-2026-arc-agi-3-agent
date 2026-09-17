# Goal versus dynamics audit — 2026-09-17

CPU-only review of saved Duck transcripts and action events. No GPU run, game
implementation, hidden result, or leaderboard submission was used. Verified
hidden score remains 2.37. The paired W and W-repeat arms below used the same
game list, seed, model, prompt and 900-second nominal game windows; vLLM
execution is still stochastic at a fixed seed. This is a failure classification,
**not** a causal effect estimate.

## cd82: a stated goal did not prevent a dynamics failure

| Same-game control | First level completed | Levels by window end |
|---|---:|---:|
| W | action 46 | 3 |
| W-repeat | action 130 | 1 |

W-repeat had a concrete target hypothesis by analysis step 6 (a purple/white
paint pattern). It did not lack a goal. At step 12 it asserted that the painting
stamp had **exactly three** swing positions. Later it discovered additional
positions; by step 21/action 81 it said its movement mapping was inconsistent
and needed a transition table. The attempt reached game-over around action 102.
It finally cleared level 1 after restarting, at action 130. See saved
`../run-artifacts/affordance-screen-v1/gate2-comparison/W-repeat/transcripts/cd82-fb555c5d_p0.txt`,
especially lines 2899, 5217, 5632 and the action event at 130.

W, by contrast, wrote an observed pose/action chain by analysis step 16/action
30, extended it to a reachable below-canvas pose at step 17/action 34, and
cleared level 1 at action 46. See the corresponding W transcript lines 3808,
4016 and 4625. W's goal statement was not uniquely superior; its *control
model* became executable sooner. The 84-action difference is descriptive and
could include other run-to-run effects, but the false pose count, later
contradiction and reset are directly visible.

## ka59: a discriminating mechanics probe preceded a solve

In W, placing one block in a ring at action 14 did not complete the level, so
the model revised the goal to filling both rings. It then tested whether control
follows the white center: toggle the center, press DOWN, observe which block
moves. It explicitly marked that rule confirmed at step 12/action 21 and
cleared level 1 at action 34. The transcript records the hypothesis and test
at lines 1917 and 2952, and completion at 3951. W-repeat cleared its first
level at action 30 and its second at action 116. This example shows the desired
behavior—an uncertain rule tested with one discriminating action—rather than a
universal prompt failure.

## tn36: conditional completion action, but the cheap fix failed

Prior W traces show a submit-like click that changed zero non-timer cells until
the board was configured, then cleared a level. That justified the
state-dependent-affordance prompt screen. In that screen A did make the
conditional re-test, but all three arms cleared five total levels and A failed
the pre-registered depth and token gates. See
`research/affordance-screen-result-2026-09-17.md`. Correcting one recognizable
reasoning mistake in one game was not enough to raise score across the screen.

## Decision and next falsification

The saved runs exhibit at least two separable bottlenecks: an uncertain
goal/conditional completion action (`tn36`) and an overconfident, incorrect
action-transition map (`cd82`). A generic reminder to “think about the goal”
is not supported as the next multifold lever. The higher-value bounded bet is
**evidence-gated dynamics**: before a long plan, distinguish observed
`(state, action) → outcome` transitions from inferred ones, mark untested edges
UNKNOWN, and halt/re-plan when a predicted edge contradicts the next frame.

Next, without GPU, test whether existing saved `cd82` transitions can be
compressed into a game-agnostic object/pose representation that reconstructs
the observed action edges without claiming unobserved ones. This is a
feasibility test, not a hard-coded `cd82` solver. If it requires game-specific
coordinates or cannot distinguish aliased states, stop that representation
before integrating it into Duck. If it succeeds, pre-register a new short
same-seed W/W-repeat/treatment screen on different games; no full-25 or scored
run until the user's public-score gate is met.

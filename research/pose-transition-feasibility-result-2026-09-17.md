# Observed object-pose transition map — CPU feasibility result

Date: 2026-09-17. No GPU or game-implementation files used. Input was saved
action/frame JSONL from the private affordance screen. Script:
`research/pose_transition_feasibility.py`; tests:
`tests/test_pose_transition_feasibility.py`. This is a *pose/navigation* map,
not a complete game-state simulator and not a goal model. The verified hidden
score remains 2.37.

## Contract tested

From each board, select a single moderately sized, non-border connected
component of each color. Over the first observed actions, pick the unique
component color that moves most often. Identify a pose by its observed shape
and position, then record only actual `(pose, action) → next pose` edges.
Unobserved edges and conflicting outcomes return UNKNOWN. Selection uses only
the early prefix; nothing is hard-coded to `cd82` coordinates or color 2.

## Measured

| Saved trace | Early selector | Prefix map | Later pose-edge claims | Exact | Wrong | Unknown |
|---|---|---|---:|---:|---:|---:|
| cd82 W | color 2 after 20 actions | 9 edges / 4 poses at action 20 | 4 | 4 | 0 | 13 |
| cd82 W | same | 15 edges / 6 poses at action 40 | 3 | 3 | 0 | 1 |
| cd82 W-repeat | abstains at action 20 (only 2 movements); color 2 after action 30 | 14 edges / 5 poses at action 60 | 35 | 35 | 0 | 22 |
| ka59 W and W-repeat | abstains: two relevant blocks share a color | — | — | — | — | — |
| tn36 W and W-repeat | selects color 3 | 12 edges / 13 poses at action 20 | 0 | 0 | 0 | 1–4 |

The map makes no wrong *pose* claim on these holdouts, but it predicts only
already observed pose/action pairs. It does not score novel mechanics or full
frame outcomes. `tn36` color 3 is an unhelpful selection; its zero coverage is
not evidence of a sound useful model. `ka59` demonstrates that the uniqueness
assumption excludes multi-object games before modelling even starts.

The decisive `cd82` check: the below-canvas pose used by W at action 33 to
enable its fast level-1 solve was **absent** from W-repeat's first 60 actions.
W-repeat first reached that same observed pose at action **93**, shortly before
its action-102 game-over/reset. A sound lookup table built by action 60 cannot
plan a path through an unobserved pose. It might stop an unjustified claim,
but cannot discover the missing route without active model-guided probing.

## Decision

Do **not** integrate this single-component pose lookup into Duck or book a GPU
screen. It passes a narrow correctness check on one selected game but fails the
general-utility check: useful selection/holdout coverage occurs in only one of
the three game types available, and the needed successful pose was unknown at
the moment the slow run was stuck. Calling this a simulator would repeat the
earlier teacher-forcing/lookup-table mistake. This is a cheap negative result,
not a score improvement.

The remaining capability bet requires **active, verified exploration of
UNKNOWN edges** plus a multi-object representation and a separate goal test.
That is materially more than a small harness tweak. Before another GPU run,
the next bounded CPU question is whether a generic *effect-of-action* summary
can identify which unknown probe would distinguish two mechanics hypotheses,
without game-specific rules. If not, stop this line rather than iterate on
`cd82` until it looks solved.

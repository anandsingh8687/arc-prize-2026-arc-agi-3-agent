# ARC-AGI-3: the next capability bet, not another efficiency tweak

Date: 2026-09-16. Verified hidden score remains 2.37. No competition submission
or new GPU run was made for this analysis.

## What the saved traces say

`research/stall_trace_audit.py` audited 500 public Duck example-run traces (20
attempts on each of 25 games; these are historical Qwen3.6 traces, not our
current Qwen3.8 baseline). On the complete board, including the HUD:

| Quantity | Observation |
|---|---:|
| Actions | 68,682 |
| Completed levels | 309 |
| Traces clearing no level | 248 / 500 |
| Exact board/state no-op actions | 7,790 |
| Repeated already-observed no-op on same board/action | 2,251 (3.28% of actions) |
| Traces with ≥3 such repeats in a rolling 10 actions | 61 / 500 |
| Those traces later clearing a level | 9 / 61 |
| Zero-level traces with **no** exact no-op | 67 / 248 |
| Same observed board/action previously no-op, later changed | 2,344 events |

Board/state here does not include every possible hidden game variable. The last
row was also excluded in a sensitivity analysis: warnings rose to 226/500, but
53 of those traces later cleared a level. That is **not** evidence for blindly
masking the last row; it demonstrates how an aggressive mask changes the alarm.

Of 252 traces that eventually cleared a first level, 164 did so by action 40,
217 by action 80, and 35 after action 80. An 80-action no-completion trigger is
therefore plausible as a request for diagnosis, but unsafe as a termination.

Our current two-game screen gives a related, not causal, observation: W on cd82
had 114 last-row-masked no-ops and cleared 0 levels; M had 10 and cleared 2.
However W-repeat also cleared 2, so this cannot be credited to memory. A stall
warning would have fired on W and W-repeat but not M. The screen does **not**
promote M under the preregistered gate.

## Conclusion from the negative evidence

Removing every repeated no-op would recover only 3.28% of historical actions,
far short of the several-fold score gain needed. It misses 67 zero-level runs
that never no-op. A hard blocker is unsound because the same observed action
sometimes changes outcome later. The useful role for this detector is to call a
**supervisor**, not to substitute for the agent or veto its action.

## Capability hypothesis: conditional scientific recovery

Normal play stays with the current fast Duck actor (no memory-arm changes).
When either (a) three repeated **interior-board** apparent no-ops occur in ten
actions, (b) 80 actions elapse on any level without completing it, or (c) 180
seconds elapse on a level without completion, pause
once per level for a *bounded* supervisory call. Give
it the last transitions and the current state, then require four outputs:

1. A concrete proposed goal/progress predicate, explicitly labelled uncertain.
2. Two competing mechanical explanations tied to observed transitions.
3. One low-cost action whose predicted outcomes distinguish the explanations.
4. A short conditional plan: expected observable change after each action, stop
   on mismatch, update the goal/mechanic belief after the probe.

The supervisor may say `UNKNOWN`; that is preferable to a false simulator. It
can ask for executable mechanic induction **only when** enough transitions
exist and a specific uncertain step blocks a plan. Program synthesis is not a
prerequisite for this experiment. Preserve verified findings, not unbounded raw
reasoning, between levels.

This is a proposed mechanism, not a measured gain. Its distinction from the
previous memory-only arm is that it forces a *decision-changing experiment and
goal check* at a demonstrated stall, rather than merely retaining text.
The inner-board signal is explicitly advisory: border cells can encode causal
timers or controls. The complete-board historical detector fired on none of
our six current W/W-repeat/M game traces, whereas the last-row-masked variant
fired on W cd82 at action 17 and W-repeat cd82 at action 14. Thus a raw-board
trigger would fail the proposed smoke despite being correct on the older logs.
The live treatment now uses an inner-board warning and never blocks actions.

The external evidence is directional, not a score prediction. NVIDIA's AVO
reports a supervisor that intervenes on stagnation, persistent memory, and
100/100 on the public set with Claude Opus 5; it explicitly did **not** center
its ARC agent on a programmatic world model and did **not** evaluate the hidden
Kaggle set:
https://developer.nvidia.com/blog/nvidia-avo-reaches-100-on-arc-agi-3-demonstrating-a-frontier-level-general-purpose-architecture-for-long-horizon-autonomous-agents/
OpenAI reports 13.3→38.3 public RHAE with retained reasoning and compaction on
GPT-5.6 Sol, which does not establish the effect on Qwen:
https://openai.com/index/how-two-settings-tripled-our-arc-agi-3-scores/
Retrodict's expected-outcome plan queues and hypothesis checks are useful
mechanisms, but its frontier API runtime is not Kaggle-eligible:
https://github.com/ryanbbrown/Retrodict

## Bounded gate

1. CPU replay: the triggers and evidence packet must reconstruct exactly from
   saved traces. Structural validation requires a legal single action, two
   evidence-linked explanations with different predicted outcomes, and a
   proposed progress predicate. It cannot certify that the claims are true.
2. One-game lifecycle smoke on cd82. For smoke only, set the wall threshold to
   zero after server-ready to force the rare branch; this tests code and
   persistence, **not** the 180-second trigger policy or score. Pass only if
   the model provides a structurally valid probe, the runner executes exactly
   that action, and the before/action/after evidence is saved. Inspect the
   event manually before interpreting it as a useful experiment.
3. Paired 3-game screen with the real 180-second threshold on cd82
   (repetition), tn36 (no-op-free cold start), and
   ka59 (partial-progress regression guard): W, same-seed W-repeat, and supervisor arm. Promote
   only for additional cleared levels over **both** controls on at least two
   games, no regression on the third, within 15% GPU-time overhead. Measure
   per-game RHAE, tokens, actions, and trigger-to-next-level outcomes too.
4. If that passes, locked 8-game transfer, then a 25-game public run. A scored
   submission remains blocked until that full public run demonstrates score >10,
   per the operator's stated gate. One allowed prompt revision
   after a failed smoke/screen; then stop this bet and diagnose, no open-ended
   prompt tweaking.

The 500 example traces are all unsuccessful at winning a *whole* game. They
cannot establish that this mechanism will improve score on a winning run or on
hidden environments. They are enough to reject no-op blocking as a claimed
breakthrough and to choose a falsifiable, low-cost recovery experiment.

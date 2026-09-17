# Repeat-only recovery: pre-registered short screen

Date: 2026-09-17. The official hidden score remains 2.37. The earlier
180-second recovery arm was **not** promoted: it regressed on `tn36` against
the identical-repeat control. This is a new trigger hypothesis, not a
retroactive pass for that arm.

## CPU evidence before changing code

`python3 -m research.replay_recovery_triggers
../run-artifacts/recovery-screen-v1/gate2-comparison` replays the exact
`detect_stall()` implementation at each saved analysis boundary. It reads
recorded frames and actions only, never game implementation files. First
action-based warnings from the previous notebook:

| Arm | cd82 | ka59 | tn36 |
|---|---|---|---|
| W | repeated apparent no-op at action 22 | repeated apparent no-op at action 15 | action-count limit at 96 |
| S | none | action-count limit at 99 (level 2) | action-count limit at 86 |
| W-repeat | none | none | action-count limit at 106 |

All three *actual* S interventions came instead from the fixed 180-second
wall trigger. On `tn36` it fired at action 21, even though neither control
had a repeated-no-op signal. The action-only replay therefore supports a
specific testable change: reserve the structured hypothesis probe for
repeated observable failures, not simply elapsed time or a fixed number of
actions. It does **not** prove that the timer caused the regression; the
same-seed controls are visibly stochastic.

## Treatment and controls

- W: plain Duck, same model and sampling as the previous screen.
- W-repeat: identical Duck and seed, to expose execution variation.
- S-repeat: the same recovery probe code as the previous S arm, but only after three repeated
  interior-board apparent no-ops in the most recent ten actions. The
  wall-time and action-count fallbacks are disabled; no hard action veto.

Run on `cd82`, `ka59`, and `tn36`, with the previous 900-second-per-arm
game windows and one shared vLLM server. The notebook labels this arm `S`;
the only intended treatment delta versus the previous S is the trigger
policy. No scored competition submission.

## Gates

1. CPU tests and notebook parser pass. The September 16 notebook remains
   byte-for-byte untouched; the new notebook embeds the current adapter.
2. Private one-game exact-code smoke: W and S act, S executes one forced
   diagnostic probe, artifacts persist, clean shutdown, exit zero. Smoke's
   forced trigger tests the branch and says nothing about the real policy.
3. Only after smoke, paired three-game screen. Promote S only if it clears
   more levels than *both* W and W-repeat on at least two games, does not
   regress on the third, and uses no more than 15% additional GPU seconds.
   Record trigger count and reason, per-game completed levels, RHAE, actions,
   calls, generated tokens and wall/GPU time. A zero-trigger S arm cannot
   support the mechanism even if stochastic score improves.
4. Passing this screen permits a locked eight-game transfer test, not a
   scored submission. A full 25-game public score above 10 remains the
   operator's gate before any scored long run.

If the screen fails, reject this trigger variant rather than searching for
post-hoc thresholds on these same three games. Review at most one clear
implementation defect with a bounded repair; otherwise change hypothesis.

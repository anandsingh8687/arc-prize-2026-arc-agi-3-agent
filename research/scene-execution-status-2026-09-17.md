# Complete-scene execution frontier

Last verified: 2026-09-17 15:19 UTC.

- Source: `eedc1e4`, branch `codex/arc3-memory-screen`.
- Smoke: `anandsingh8687/arc3-scene-smoke-20260917`, Version 1, COMPLETE and independently verified PASS. This is a private benchmark, not a competition submission. See `scene-smoke-result-2026-09-17.md`.
- Screen: `anandsingh8687/arc3-scene-screen-20260917`, Version 1, COMPLETE with `SCENE_SCREEN_OK`, clean lifecycle and exact scene delivery. W/C/T/W-repeat completed 3/3/2/4 levels. C fails promotion; T fails viability. See `scene-capability-screen-result-2026-09-17.md`. Do not relaunch it.
- Local verification: 150 tests passed excluding unchanged `tests/test_scoring.py` because `arc_agi` is absent in the local interpreter. Both generated notebooks passed syntax/attachment validation. Actual upstream Duck user-message construction checked for all four arms. All 565 saved observation frames were independently reconstructed exactly from rendered text.
- Review finding ARC3-SCENE-INT-001: delivery gate strengthened to require per-turn equality of generated scene observations, actual delivered scene messages and expected modality messages, not mere presence. Negative tests reject missing and partially delivered scenes and incorrect modality. No further broad review loop.
- GPU allowance after screen: 1.92 hours. Refresh 2026-09-19 00:00 UTC. This tranche is complete; no further automatic GPU experiment.
- Existing heartbeat `arc-agi-3-recovery-screen-follow-up` is to be PAUSED after recording this terminal result. No continuing polls or relaunches.

## Next action

Current experiment gate completed with rejection. Retain the image baseline and preserve the exact results. A new model/goal-learning test requires a separate bounded protocol and quota reassessment; this result does not authorize a long run or submission. Do not treat three-game scores as a full-public or hidden result.

Competition score remains **2.37**. No candidate has yet demonstrated full-public-25 score above 10. No new long run or scored submission is authorized by this checkpoint.

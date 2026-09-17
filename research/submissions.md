# Submission log

One submission per UTC day. Never spend one on a change that has not passed a
replicated local gate. A public-leaderboard delta under ~0.4 ranks nothing.

| # | Date (UTC) | Commit / run | Change | Local | Public LB | Games reached | Notes |
|--:|---|---|---|--:|--:|--:|---|
| — | 2026-09-14 | not captured | Gate 1 public baseline completed | 8.595934349265152 | — | 25/25 public | 40/183 levels completed; 3,563 actions. Not submitted: projected full-run margin is only 128.462909386507 s. |
| 1 | 2026-09-14 | Kaggle v7 / `349893477` | Gate 1 safe baseline: Qwen3.8 Flash Next NVFP4, C16 serving, 6,600 s wave cap, crash-proof persistence and bounded teardown | **5.265162984780623** | **2.37 public LB** | 25/25 local; scored-run coverage unmeasured | The previous row incorrectly carried run 3's `7.6855` local score onto Version 7. Version 7 completed 31 local levels and finished with benchmark ok, teardown ok, logical exit 0, and no surviving GPU process. Source frozen in `notebooks/arc3-gate1-v7-source.ipynb`; the Kaggle script version, not a Git SHA, is the authoritative run identity. |

## Anchors

| Reference | Score | Source |
|---|--:|---|
| Published Duck/Qwen3.8 notebook (our Gate 1 base) | **3.22** | Kaggle public notebook |
| Qwen3.8 Flash Next NVFP4 (best associated) | 4.33 | Kaggle Models tab |
| gpt-oss-120b (best associated) | 0.24 | Kaggle Models tab — likely modality mismatch |
| Our model-free floor | 0.086 local | `arc3.evaluate --agent heuristic` |
| Leader (2026-09-15) | 18.81 | Tufa Labs |

Local scores and Kaggle's public-leaderboard score are measured on different game
sets and stochastic executions. The v7 ratio below is a single noisy planning
observation, not a stable conversion factor.

## Leaderboard watch

| Date | Rank 1 | Rank 3 (prize cut) | Notes |
|---|--:|--:|---|
| 2026-09-13 | 11.04 Tufa Labs | 8.40 NVARC3 | from screenshot |
| 2026-09-14 | 11.04 Tufa Labs | 8.40 NVARC3 | unchanged |
| 2026-09-15 | **18.81** Tufa Labs | **8.44** Lord Han Solo | rank 1 +70% in two days; us 2.37 at rank 602 |
| 2026-09-16 20:09 UTC | **18.81** Tufa Labs | **8.68** Ebi | Authenticated Kaggle CLI top-10 lookup; no new submission from us. |
| 2026-09-17 08:45 UTC | **18.81** Tufa Labs | **11.04** NVARC3 | Authenticated Kaggle CLI top-10 lookup; no new submission from us. |

## Local vs public-leaderboard calibration

Build our own ratio here. The only published figure is 2.4-2.9x, from three
correlated points by a single team on a different architecture.

| Run | Local (25 games) | Public LB | Ratio |
|---|--:|--:|--:|
| model-free floor | 0.086 | not submitted | — |
| run 1 (7,920s cap, 40 levels) | 8.5959 | not submitted | — |
| run 3 (6,600s cap, 35 levels) | 7.6855 | not submitted | — |
| **Kaggle v7 (31 levels)** | **5.2652** | **2.37** | **2.2216** |

Only the v7 row is a valid pairing. Run 1 and run 3 were never submitted, and
pairing either local score with v7's hidden result gives a wrong ratio -- an error
this document made once already.

Local score per completed level varies sharply between runs of nearly the same
agent: 0.215 (run 1), 0.220 (run 3), 0.170 (v7). Which levels get cleared matters
more than how many, so a single local score is a noisy instrument.

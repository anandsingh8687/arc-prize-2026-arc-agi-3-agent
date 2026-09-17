# Competitor survey — what is actually established (2026-09-15)

Compiled by Codex from public harness code and Kaggle discussion. **The numbers
below are third-party and unverified here.** No competitor's bundled public game
source files were read, only harness code — the same rule this repository applies
to `environment_files/`.

Sources: [Sahasawatt serving analysis](https://github.com/Sahasawatt/arc-agi-3-agent/blob/master/notes/B69-flash-next-serving-design.md),
[run ledger](https://github.com/Sahasawatt/arc-agi-3-agent/blob/master/notes/LEDGER-all-runs.md),
[animation discussion](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/discussion/734369),
[STaR discussion](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/discussion/739047),
[Retrodict](https://github.com/ryanbbrown/Retrodict) and its
[experiments](https://github.com/ryanbbrown/Retrodict/blob/main/experiments.md),
[Polyphony](https://github.com/Mininglamp-AI/polyphony-arc-3),
[JEPA approach](https://github.com/CalamityChasm/ARC-AGI-3-JEPAstyle_approach),
[OpenAI report](https://openai.com/index/how-two-settings-tripled-our-arc-agi-3-scores/).

## Newly checked Duck fork: stop HUD-only action batches (2026-09-16)

[Son Pham's public Duck lab](https://github.com/sonpham-org/arc-3) reports a
two-pass, same-stack comparison excluding the unusually volatile `ft09` game:
without a no-impact guard, mean 1.046 and 15 levels/pass; with a learned
HUD-band no-impact guard, mean 1.624 and 21 levels/pass. Each arm ran into the
same ~132-minute cap. These are **their** local runs, not a result on our Qwen
checkpoint or on Kaggle hidden data. Two passes are too few to claim a stable
55% effect. The precise evidence and implementation are in their
[variant manifest](https://github.com/sonpham-org/arc-3/blob/main/harnesses/ffa7g/MANIFEST.md)
and [patch](https://github.com/sonpham-org/arc-3/blob/main/harnesses/ffa7g/patch/ffa7g-full-stack.patch).

Their negative ablations matter as much: a state graph regressed repeatedly;
a required ledger and other agent changes cost ~2.2x tempo; 35B-A3B, GLM-4.6V,
and Gemma-4-31B swaps all lost in this harness. The tested guard learns rows or
columns that change on nearly every action, then stops the **rest of an
exploratory batch** at its first action with no gameplay change. It does not
claim a level win from classifying a HUD pixel. This is a better-evidenced
fallback than a new world-model tool if our short recovery screen fails.

On our saved two-game traces, a simple exact-board replay found 16 W batches
on `cd82` and 11 W-repeat batches on `ka59` with actions *after* the first
no-op. No later action in those batches completed a level. This is a narrow
candidate signal, not a counterfactual score: changed boards can still be
productive, and the historical replay has no access to the alternate trajectory
after an early stop. The next experiment would need its own exact-code smoke
and same-seed control, not reuse a recovery-screen result.

The CPU-only fallback in `arc3/no_impact.py` adds one safety qualification to
the published row/column band: a full-width ticking row also makes **every
column** appear volatile. Unioning both masks then hides a real object change
elsewhere on the board. A synthetic test reproduced this false positive before
repair. The fallback selects only the smaller-area orientation, rejects an
ambiguous tie or a mask covering at least half the board, and still requires a
live ablation before any claim of score benefit. On the six saved cd82/ka59
traces, this safer band adds only one HUD-only classification beyond exact
no-ops; these games are not evidence for a large HUD-band effect.

## Techniques

| Technique | Evidence | Decision |
|---|---|---|
| Flash-Next NVFP4 serving | 4.39 -> 8.69 local, 24.25 -> 38.5 levels. The only statistically convincing large gain. | **Already adopted.** |
| Animation-aware solver | 9.5584 local; hidden 3.74 and 3.41. Fewer wasted actions, no measurable score win over Flash serving. | Adopt as cheap automatic evidence, not an on-demand tool call. |
| Generic prompt changes | ACT-NOW versions 5.51 and 2.47; dead-turn rate unchanged. | **Reject.** |
| Generic memory / compaction | Duck compaction neutral; Polyphony found per-turn history rewriting destroyed prefix caching. | Compact only near the context limit; keep verified facts in files. |
| STaR / LoRA fine-tuning | Hidden 1.25 -> 1.94. Curation mattered more than data volume. | Too small and too risky before the deadline. |
| Learned JEPA world-model rollouts | Prediction error exceeds the identity baseline by rollout depth 2, then compounds. | **Reject** learned multi-step rollouts. |
| Executable simulator + search | Retrodict: stuck-level escalation converted previously blocked levels once the model wrote and verified a simulator. Polyphony independently implements state/engine/planner/verifier with per-frame checking. | **Strongest capability direction.** |

## The transfer finding — the most important thing here

**Three configurations and five hidden draws** -- not five observations. An
earlier version of this section averaged the five ratios, which double-weights
the two configurations that submitted twice. Draws are averaged within a
configuration first. `research/transfer.py`:

```
configuration           local           draws   mean   ratio
us, Version 7          5.2652            2.37  2.370   2.222
animation solver       9.5584       3.74/3.41  3.575   2.674
competitor            10.9337       3.60/2.82  3.210   3.406

n = 3 configurations. ratio min 2.222  mean 2.767  max 3.406
```

The ratio framing assumes the relationship is multiplicative, which three points
cannot test. If it is additive or saturating, these conversions are wrong in a
way averaging does not fix. What follows is a **stress range for planning, never
a target band**.

**Our 2.2216 is the best of the five**, and every "local equivalent" in this
repository was computed from it — so every target stated so far is the easiest
case. Rank 1's 18.81 becomes a band:

```
ratio 2.222 (best observed)    local 41.8   -> +2 to +3 levels in every game
ratio 2.767 (mean of three)    local 52.1   -> +3 to +4 levels in every game
ratio 3.406 (worst observed)   local 64.1   -> +3 to +4 levels in every game
```

Two further readings, both weakly supported and both worth acting on:

**Transfer appears to degrade as local rises.** Local 5.27 transfers at 2.222;
9.56 at 2.679; 10.93 at 3.457. That is the shape overfitting to 25 public games
would produce. Three distinct local values cannot establish a trend — this is a
caution, not a finding — but it is the direction that would hurt us, and it argues
against tuning anything on local score.

**The hidden side has its own variability.** The same configuration drew
3.74/3.41 and 3.60/2.82: roughly +/-5% and +/-12%. Two pairs cannot establish a
noise floor, so the earlier claim that 2.37 -> 2.7 "would not be distinguishable
from noise" was too strong. The usable version: such a move **could** be noise,
so a daily submission should not be spent on a small predicted gain.

## Corrections and additions (2026-09-16)

| Claim | Status |
|---|---|
| AERA scored 21.16 with a 0.5B model | **FALSE.** The paper reports 0.2116 public, 0.30 private. A comparison table scaled it by 100. |
| Polyphony 19.80 is a one-GPU result | **FALSE**, verified against the repo: `--tensor-parallel-size 8`, 24 h window, 4 h/game. |
| Agno's warm/seeded scores transfer | **No.** They reuse manuals from previous attempts on the same public games; Kaggle allows one unseen play. |

Additions:

- **NVIDIA AVO**, 100 with Opus 5: exact text grids, persistent memory,
  supervision, stagnation recovery. Vision is not required; durable state is.
- **OpenAI harness study**: GPT-5.6 Sol **13.3 -> 38.3 with 6x fewer output
  tokens**, by retaining reasoning and replacing rolling deletion with
  compaction. The largest directly-measured harness delta in public work, and the
  opposite direction from a response cap.
- **NOOA**: **+8.5 RHAE** from its world-model skill, **+11.8** from its memory
  system (GPT-5.5). The one place the two levers were separated, memory was
  larger.
- **Tycho** also warns that transition accuracy alone does not identify the goal
  or guarantee better actions -- directly relevant to the E0 pass condition,
  which tests prediction and not goal discovery.

## What this changes

Nothing in the direction of the work, and one thing in how it is judged:
**a local improvement is not evidence of a hidden improvement**, and the gap
between them widens exactly where we are trying to go. The promotion rule in
`rank-1-plan.md` §5 already requires additional *cleared levels* rather than
score; that requirement is now load-bearing rather than fastidious.

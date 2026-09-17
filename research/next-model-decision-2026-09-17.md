# Decision after the complete-scene screen

Evidence baseline: `0a9dde8`. Competition score still **2.37**; no new submission.

## What changed our decision

The latest valid scene screen completed 3 / 3 / 2 / 4 levels for image control,
image+scene, scene-only, and image-control repeat. It did not establish a better
Qwen agent. Memory's earlier 4 vs 2/3 levels remains an encouraging fragment,
not a replicated win. Neither result supports stacking interventions and calling
their gains additive. Old preregistered verdicts remain unchanged.

The read-only experiment audit identified three limitations for future gates:

- EXP-GATE-001: fixed arm order is not counterbalancing. Control-repeat differences
  show uncertainty; they do not identify its source or constitute a calibrated
  significance test.
- EXP-GATE-002: budget matters. The scene screen used about 41–44k generated tokens
  per game, below the older production planning allowance. A failed short gate is
  not proof of failure at every budget. Across different models, match GPU time,
  action limits and observations; tokenizer-dependent token counts are diagnostic,
  not an interchangeable resource unit.
- EXP-GATE-003: selecting the few positive games from earlier failed screens would
  compound selection bias. New capability tests must not tune to those fragments.

## Public code checked again

- [Sahasawatt's run ledger](https://github.com/Sahasawatt/arc-agi-3-agent/blob/master/notes/LEDGER-all-runs.md):
  B81 increased actions 2,008 to 2,965 and levels 39 to 41 while local score fell
  9.56 to 8.72. Its submitted result was still listed as pending when checked.
  The same ledger reports negative frame-change-veto results and no attributable
  hidden gain for the no-impact wrapper. Throughput alone is not solved depth.
- [Son Pham's Duck lab](https://github.com/sonpham-org/arc-3): combined no-impact
  tooling has a positive local observation, but there is no comparable hidden-
  validated breakthrough; state-graph and several model swaps were negative.
- The search did not find a newly published, eligible one-GPU recipe that we can
  truthfully present as a reliable score above 10. This is a search result, not
  a claim that no undisclosed technique exists.
- A [GPT-OSS notebook titled 40–50](https://www.kaggle.com/code/ahoirg/40-50-gpt-oss-120b-cwmv-low-min-p-temp-swep)
  linked from a competition discussion was checked by downloading its source,
  without running it. It uses AIMO-3 mathematics, an H100 and an integer-answer
  inference server, not ARC-AGI-3. Its title is not evidence of an ARC score.

## New bounded question

Can **gpt-oss-120b + the complete scene + native tools** make useful decisions in
the existing agent loop? Unlike more Qwen prompt changes, this changes the model
capability. Qwen's scene-only failure does not answer that different question.
This is not a retroactive promotion of the rejected text arm.

The [model documentation](https://developers.openai.com/api/docs/models/gpt-oss-120b)
specifies text-only input and configurable reasoning; the
[vLLM recipe](https://github.com/vllm-project/recipes/blob/main/OpenAI/GPT-OSS.md)
requires its native `openai` function parser. Qwen XML instructions, chat template,
MTP and quantization overrides must not carry over.

Current gate is only **BUILD + lifecycle feasibility**:

1. CPU-test model payload, seed, tool-result history, exact scene and no images.
2. One private 60-second smoke on `r11l`, timed after server/model readiness.
3. Persist results independently of shutdown; require a clean fresh process table.
4. At most one bounded repair. No capability claim from this smoke.

The later model-selection screen must be separately frozen before launch. A large
completed-level gain, followed by transfer replication, would justify spending
scarce quota on a full public benchmark. A full-public score above 10 is still the
user's prerequisite for another long scored submission—not a predicted outcome.

Quota observed before implementation: **1.92 GPU hours remaining**, refresh
2026-09-19 00:00 UTC. No paid compute purchase or new submission is authorized here.

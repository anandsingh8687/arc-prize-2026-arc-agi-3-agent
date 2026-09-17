# Text-only modality screen — preregistered 2026-09-17

## Why this is different from another tuning knob

The unresolved high-leverage question is whether a stronger offline text-only
model can out-reason Qwen on novel games. The old plan assumed a separate text
perception layer had to be built before that could even be tested. Duck already
exposes `current_frame.ascii` and `current_frame.segmentation` through its Python
tool. Its image attachment and multimodal system-prompt addendum are both
conditional on `MULTIMODAL_CONTEXT=current_grid` in
`../duck-harness-source/ARC3-Inference/inference/agent/vision_context.py` and
`tool_agent.py`. A local import check confirmed that clearing the flag removes
the image from the user message and the multimodal addendum from the system
message, without removing the Python board views. This is a shortcut to a fair
first model comparison, **not** proof that the text view is sufficient.

## Locked short protocol

- Smoke first: one game, W/image then T/text-only, 60 seconds per arm from
  server-ready; require actions, saved results, and clean final process table.
- Screen only if the smoke passes: one Qwen3.8 Flash-Next NVFP4 server; three
  arms W/image, T/text-only, W-repeat/image, same seed 1214842320, no output
  cap, 400-action cap, 600 seconds/arm, concurrency 3.
- Games: `cd82`, `ka59`, `g50t`, chosen before the run from different prior
  depths. These are public observations, not game implementation files.
- The sole treatment is `MULTIMODAL_CONTEXT=""` in T. W and W-repeat explicitly
  set `current_grid`. Agent class, tool, checkpoint, prompts apart from the
  conditional image addendum, serving configuration, and scheduler are fixed.
- Primary *viability* gate for a future gpt-oss test: T clears at least as many
  total levels as the weaker image control, and loses no more than one level on
  any game against that control. This does **not** promote T as a scoring
  improvement. Scoring promotion is stricter: T must beat **both** image arms in
  total cleared levels, with no game losing more than one level against the
  better image arm; then a locked eight-game transfer set is required.
- Secondary readouts: per-game clears, actions, generated tokens, calls,
  weighted RHAE/GPU-second, token/action and model error rate. Faster or cheaper
  alone does not promote.
- If T fails viability, do not load gpt-oss into the same inadequate text view.
  Diagnose one concrete perception loss from transcripts first. If T is viable,
  the next short gate compares both models with the *same text-only* view and
  their correct tool/reasoning parsers.
- No competition submission or nine-hour run. A full 25-game local score must
  exceed 10 before either is considered, per the user's instruction.

Builder: `research/build_text_only_screen_notebook.py`. Generated notebooks
are private and use the same pinned Qwen checkpoint as the prior screens.

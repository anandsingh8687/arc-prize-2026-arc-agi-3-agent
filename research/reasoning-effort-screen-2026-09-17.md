# Native reasoning-effort screen — preregistered 2026-09-17

## Why this experiment

The 1,024-token response cap failed: it cut off plans mid-response. Qwen3.8
Flash-Next's [chat template](https://huggingface.co/RadixArk/Qwen3.8-Flash-Next-NVFP4/blob/main/chat_template.jinja)
has a separate `reasoning_effort` control. Its default `xhigh` adds an explicit
instruction to think carefully; `medium` removes that instruction while keeping
thinking enabled and **not** truncating the response. The checkpoint maker
[notes](https://huggingface.co/RadixArk/Qwen3.8-Flash-Next-NVFP4) that long
agentic generations tend to run longer than BF16. This is a plausible way to
spend fewer tokens per decision without the cap's truncation failure, not an
established score improvement.

An entrant's [competition forum report](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/discussion/739938)
said broader thinking-cap and on/off changes did not move results much; this
lowers the prior probability. The precise native `medium` setting with the same
checkpoint and harness has not been measured by us. We run one screen, then
stop if it fails.

The latest public Flash-Next Kaggle notebooks inspected on September 17 use
essentially our existing Duck source bundle and serving configuration; a
notebook copy is not a new capability lever. The live scoreboard is 18.81 at
rank 1 and 11.04 at rank 3; our verified hidden score remains 2.37.

## Locked protocol

- Exact current Qwen3.8 Flash-Next NVFP4 checkpoint and one vLLM session.
- Three arms in order: W/default, E/`reasoning_effort=medium`, W-repeat/default.
- Same seed (1214842320), game order, 400-action cap, unbounded response length,
  concurrency 3, 600 seconds per arm.
- This is a development screen near the full-run per-game token budget, not a
  full-run reproduction: actual generated tokens/game and GPU seconds will be
  reported before interpretation.
- Games: `lf52`, `ar25`, `re86` — selected before the run from distinct prior
  depths (1, 2, 4), not from the candidate's result. No public game sources read.
- Smoke first: one game, 60 seconds per arm from server-ready, valid results,
  clean teardown, no surviving GPU worker. No >10-minute test before it passes.
- Candidate payload is modified only in arm E. All three arms use the base Duck
  agent; no memory, recovery, affordance, or other policy change.
- No competition submission. No full-25 or nine-hour run from this screen alone.

## Decision rule

Primary: E must clear more total levels than **both** W and W-repeat, with no
game losing more than one level against the better matched control. If not,
reject this setting. Secondary diagnostics: generated tokens/call, actions/call,
tokens/action, tokens/completed level, weighted RHAE/GPU-second, and finish-reason
`length` rate. A token reduction without extra cleared levels is **not** a
promotion. If it passes, repeat on a locked eight-game set with two seeds before
any full-25 evaluation. A full-25 local score must exceed 10 before any long
competition run or scored submission, per user instruction.

The generic two-hour heartbeat was replaced with a run-specific 30-minute
check. It must pause when this screen reaches a terminal result; no blind
recurring research loop.

## Execution checkpoint — 2026-09-17

The [smoke notebook](https://www.kaggle.com/code/anandsingh8687/arc3-reasoning-effort-smoke-20260917)
completed. Saved output reports `GATE1_SERVER_READY` at `520.0645833015442`
startup seconds, `REASONING_EFFORT_ACTIVE` for W/default and E/medium,
`medium_payloads_total=11` in E, and `REASONING_SMOKE_OK`. The two 60-second
arms made 9 and 11 LLM calls, respectively; neither cleared a level. Those
tiny arms test the lifecycle and payload, not score. The initial teardown
script raised, but bounded recovery left `post_teardown_gpu_rows=[]`, saved
metrics, and reported `benchmark_ok=true`, `teardown_ok=true`.

The [matched screen notebook](https://www.kaggle.com/code/anandsingh8687/arc3-reasoning-effort-screen-20260917)
was pushed as Version 1 after the smoke passed and completed. It is not a
competition submission. E failed the preregistered depth gate: W/E/W-repeat
cleared 6/6/5 levels. Full results and the bounded follow-on decision are in
[`reasoning-effort-screen-result-2026-09-17.md`](reasoning-effort-screen-result-2026-09-17.md).

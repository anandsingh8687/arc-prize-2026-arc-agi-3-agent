# Structured-memory screen: bounded score gate

Source revision: `15e05f7`. This branch adds an opt-in Duck memory adapter;
the control agent, Qwen3.8 Flash-Next model, sampling seed, action cap, serving,
and teardown remain unchanged. This is **BUILD + local EVALUATE**, not a scored
submission. The verified hidden score remains 2.37 until a new submission.

## Current gate

The 2026-09-16 Kaggle smoke completed W and M and recovered a clean final
teardown, but M made zero memory commits. Its 60-second arms cleared no levels,
so it tested lifecycle only. Transcript inspection found a plausible causal
inference that was never sent via `memory_update`, and the prompt's example
cited transition 0 even before any transition existed. The one permitted
prompt/schema repair now requires an explicit `memory_update` decision on each
tool call (`{}` when nothing new is learned) and counts missing/empty updates.
That repair invalidates the old smoke; rerun the smoke before the two-game screen.

1. Parse and attachment validation of the exact generated smoke notebook.
2. Kaggle lifecycle smoke: W and M each play one game for 60 seconds from
   server-ready; action count > 0; results persist; teardown exits cleanly.
3. Only after that, one matched-seed screen: W, M, W-repeat, each on `cd82` and
   `ka59` for at most 900 seconds per game; all trials share one vLLM server.
4. Read per-game cleared levels, actions, generated tokens, calls, and M's
   memory commit/rejection counts. Do not treat fewer tokens alone as success.

## Promotion and stopping

M must make at least one valid commit and clear an additional level in **both**
games relative to W and W-repeat, with no regression in either. If M never
commits, allow **one** bounded prompt/schema repair followed by the same short
screen. If it commits but fails the depth gate, stop the memory line and switch
to goal discovery / selective mechanic induction. Do not lengthen the budget to
turn a failed screen into a pass.

A passing two-game screen earns an eight-game, two-seed transfer check. Only a
transfer winner earns a 25-public-game local run. **Local 25-game RHAE > 10**
is the gate for a nine-hour scored submission. This is a local benchmark gate,
not a claim that Kaggle's public leaderboard score will exceed 10.

No Kaggle submission, full-length run, model swap, scheduler, response cap, or
automatic win-path replay is part of this gate. A winning path stored in memory
is never executed by the adapter. If replay is added later, require one
expected outcome per action and check it after each real action.

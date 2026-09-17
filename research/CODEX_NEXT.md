# Codex work order — Gate 1 exit and the two levers

Paste this whole file into Codex. Repository:
`git clone -b claude/arc-prize-2026-9e0g6n https://github.com/anandsingh8687/swift-loan-tracker`

Milestone 2 closes **2026-09-30 23:59 UTC**. One submission per UTC day.

---

## 0. Where we stand (updated 2026-09-15, after the first hidden score)

```
2026-09-13   rank 1  11.04    rank 3  8.40
2026-09-15   rank 1  18.81    rank 3  8.44    us 2.37, rank 602
```

**Rank 1 rose 70% in two days.** Our own calibration is Version 7's local 5.2652
against hidden 2.37, a ratio of **2.2216** -- one paired observation, noisy.

| Goal | Hidden | vs us | Local equivalent | Depth/game | Levels of 183 |
|---|---:|---:|---:|---:|---:|
| where we are | 2.37 | 1.0x | 5.27 | 1.2 | 31 |
| rank-3 prize cut | 8.44 | **3.6x** | 18.8 | 2.8 | 69 |
| rank 1 | 18.81 | **7.9x** | 41.8 | 4.4 | 109 |

These local equivalents are planning estimates from a single stochastic ratio, not
predictions. **Milestone 2 first place is not a realistic target**: it needs a 7.9x
improvement in fifteen days against a leader still accelerating. The rank-3 cut at
3.6x is a stretch. The work below is worth doing regardless, because it is the same
work the 2026-11-02 final needs.

Prior versions of this document targeted local 27 for first place, then 32-36. Both
are superseded: the arithmetic was right, the leaderboard moved.

---

## 1. What is already established — do not re-derive

- Aggregate decode saturates at **~255 tok/s** from C8 to C32. Concurrency changes
  who waits, not total work.
- The run therefore has a fixed budget: **6.86M generated tokens** after cold start
  and a 15% safety margin.
- Run 1 spent **48,951 tokens per completed level**. At that rate the budget buys
  **1.27 levels/game across 110 games** — *less* than the 1.60 it managed on 25.
- Efficiency is nearly exhausted: **23 of 40** completed levels already match or
  beat human action counts; perfect efficiency at fixed depth reaches only **10.34**.
- Level weighting puts the points in **high-marginal-weight games, not zero games**:
  all five zero-completion games reaching depth 1 adds **+0.62**; the five
  highest-marginal-weight games each gaining one level adds **+3.25**, the five
  literally deepest **+3.11**. Weight is `(k+1)/sum(1..n)`, so a shallow game with
  few total levels can outrank a deeper game with many.
- `MAX_ACTIONS` 400 is sanctioned — the official `reasoning_agent.py` uses it.
- The current configuration has **128 seconds** of nine-hour margin. Do not submit it.

Full detail: `research/token-budget.md`, `research/where-the-points-are.md`,
`research/gate1-analysis.md`.

---

## 2. The primary metric

**`weighted RHAE gained / GPU-second`.** Tokens per completed level is a capacity
metric, not the objective: it treats every level as equal and RHAE does not. The
same 87 completed public levels can score anywhere from ~25.06 to ~54.14 depending
which games and which indices they land on.

Supporting metrics, reported alongside every experiment:

```
generated tokens per weighted RHAE point
tokens per completed level
completed levels
games attempted / games reaching level 1
action efficiency vs each level's own baseline
```

## 3. The token levers — batching is one of several

A fixed 6.86M tokens buys more useful decisions if each decision costs less. Ranked
by expected value per unit of effort:

| Lever | Why | Cost |
|---|---|---|
| **Cap routine response length** | 1,442 tokens per call is enormous for what is usually one move choice | cheapest |
| **Reason fully only at decision points** | level start, novel transition, expectation failure, stuck state | cheap |
| **Plan batching** | divides a fixed per-call cost across more actions | medium |
| **Deterministic movement macros** | no model call at all for understood motion | medium |
| **Replay known winning paths** | re-entering a solved level should cost nothing | medium |
| **Compact old observations and tool output** | shorter context is also faster to decode | cheap |
| **gpt-oss screen** | ~1.85x the exact-checkpoint throughput; ARC ability unknown | Gate 2 |

An earlier version of this document claimed plan batching was the only lever that
moves the number. That was too narrow — **response-length capping is plausibly
cheaper and larger**, and should be tested alongside it.

---

## 4. TASK A — Plan batching and response-length capping

Run 1 emits **2.62 actions per LLM call** at **1,442 tokens per call**. If actions
per call rises while tokens per call stays flat, the same budget buys more actions:

| actions/call | tokens/action | actions/game affordable | vs run 1 |
|---:|---:|---:|---:|
| 2.62 (now) | 550 | 114 | 0.80x |
| 4 | 360 | 173 | 1.21x |
| 6 | 240 | 260 | 1.82x |
| 8 | 180 | 346 | 2.43x |

**The assumption this rests on is that tokens per call stays flat as plans lengthen.
It may not — a model asked for eight actions may reason proportionally longer, and
then the whole gain evaporates. Measuring that is the point of the experiment, not
a detail of it.**

### What to build

Change the prompt contract so the model emits a **queue of actions** rather than
one, each optionally carrying the cells it expects the board to show afterwards.
The runner plays the queue out one action per step, verifies expectations, and
re-invokes the model only when the plan runs out, an expectation is violated, the
level changes, or the game ends.

`arc3/agents/base.py` on the branch already defines this interface (`Plan`,
`PlannedAction.expect`) — reuse the shape rather than inventing another.

### Measurement protocol

Sweep target plan length **1, 3, 6** on the same 8-game subset, fixed seeds,
identical everything else. Add **10** only if 6-action plans stay reliable -- a plan
must halt on any unexpected transition, and long plans that keep halting waste the
actions they already spent. Cross the sweep with a routine-response token cap.
For each cell, report:

```
actions per LLM call          (did batching actually happen?)
tokens per LLM call           (THE number -- did it stay flat?)
tokens per action             (the derived quantity that matters)
levels completed
tokens per completed level
weighted RHAE per GPU-second  (THE decision metric)
weighted RHAE per million generated tokens
no-op rate
expectation-violation rate
mean plan length actually executed before a halt
completed levels, GPU seconds
```

### Decision rule

```
Adopt the configuration that maximises weighted RHAE per GPU-second.
If tokens per call scales linearly with plan length, batching does not work --
say so plainly and stop. Never adopt on actions-per-call alone: more actions of
worse quality is a loss, and tokens-per-level alone would accept it.
```

First milestone: tokens per completed level from **48,951** below **~39,000**.
Competitive target for two levels per hidden game: **31,188**.

---

## 5. TASK B — Marginal-value scheduler

Run 1's median per-game consumption was **7,920.13 s** against a 7,920 s allowance.
Nothing was abandoned. Five games returned zero after a full share each.

### The objective function

```
priority =  P(clear next level within budget)
              x expected level RHAE
              x next-level weight
              / expected tokens required
```

Marginal level weight for a game at depth `k` of `n` levels is `(k+1)/sum(1..n)`.
Weight rises with depth; **P(clear) plausibly falls**, since later levels are
harder -- human baselines climb from a median of 29 actions at level 1 to 60 at
level 6. An earlier version claimed both terms rise together; they do not.
Estimate `P` from recent progress, no-op rate, repeated states, actions since the
last completion, and remaining depth. In practice:

- **Fair trial first.** Every game gets a minimum allocation — enough to establish
  whether it is going anywhere. An untouched game scores 0 and still divides.
- **Then cut losses.** A game that has not cleared level 1 after its fair trial
  gets no more tokens until every progressing game is served.
- **Then feed the leaders.** Remaining tokens go to games by marginal weight.

### What to measure

Ablate against run 1's equal time-slicing on the same 25 games:

```
levels completed (total, and per game)
tokens per completed level
games reaching depth >= 1  (coverage floor must not regress)
score
```

### Decision rule

```
Adopt if weighted RHAE per GPU-second improves AND every game still receives a
fair-trial allocation.
```

The floor is on **attempts**, not outcomes. An earlier version made "games reaching
depth 1 must not fall" a hard constraint; that is wrong twice over -- clearing
level 1 is not something the scheduler controls, and enforcing it could block a
strictly higher-RHAE allocation. Every game must be *attempted*; what it clears is
an outcome.

---

## 6. STEP 1 — the safe baseline (do this first)

**This supersedes the earlier Gate 1 exit list, which required the scheduler and
two replicated validations before any submission.** That list and §7 contradicted
each other. The resolution: the scheduler and replication requirements belong to
promoting a *tuned* configuration, not to the first submission, whose entire
purpose is to obtain the hidden score and coverage number as early as possible.

Ship the current baseline with safety changes only — no scheduler, no batching,
no model change:

1. Per-wave cap **~6,600 s** instead of 7,920.
   `625 + 4 x 6,600 = 27,025 s` leaves **5,375 s** margin, above the 4,860 required.
2. Hard global shutdown guard, so the run cannot overrun and lose its scorecard.
3. C8 vs C16 active-sequence validation.
4. Clean vLLM teardown — the surviving worker must be fixed.
5. Valid `submission.parquet`.
6. Per-game instrumentation preserved.
7. **One validation run, then submit.** Not two: the second replication is for
   believing an ablation delta, and there is no delta here — this is known-good
   code with safety limits. Spending 2h12m of GPU quota to re-confirm it delays
   the measurement that matters.

Also report per game: `actions_per_level`, `base_actions_per_level`,
`levels_completed`, `number_of_levels`, so `research/per_level_efficiency.py` and
`research/marginal_value.py` run directly on the output.

**Expected outcome:** a hidden score near 3.6 and a coverage number for the 110
games. Both are inputs, not achievements. The coverage number in particular decides
how much the scheduler is worth.

---

## 7. Order of work

**Revised again (2026-09-15).** `research/rank-1-plan.md` establishes that every
efficiency lever we own, perfectly executed, is worth local 10.34, while rank 1
needs two to three more cleared levels in *every* game. Depth, not efficiency.

A companion claim in the same document -- that run 1 ran at 24.4% utilisation with
3.76x of idle headroom -- was **wrong and is retracted**. One wave's tokens were
divided by four waves' seconds. Corrected: **97.72% utilisation, 1.023x headroom**
(`research/utilisation.py`). The GPU was saturated, so there is no idle time to
recover and no configuration change available. That makes the token levers in §3
the main lever rather than a supporting one, and it makes the 6.86M-token ceiling
binding.

Build the sparse reasoning controller -- 3-6 checked actions per call,
deterministic execution between decision points, compact board diffs, winning-path
replay, persistent discovered-rule memory, immediate replan on unexpected
transitions -- then gate it on three paired development games before any long run.
Gate design in `research/gate_power.py`: arms must be **paired on the same games
with matched seeds**, because an unpaired 4-game 2x gate fires on 28% of null
experiments. Include a **duplicate control arm at the SAME seeds** -- since candidate and
control are compared at identical seeds, the seed term cancels in the pairing and
the null is execution nondeterminism, not seed sensitivity. Neither run 1 vs run 3
(which differ in cap *and* concurrency) nor Version 7 (whose arms differ by the
cap) measures it, so without that arm every promotion threshold is chosen by
argument rather than measured. Seed sensitivity is a separate question and belongs
to the locked eight-game transfer gate, which carries two seeds. Screen design in
`research/rank-1-plan.md` §5 E2.

**THE MEMORY DEFECT IS THE NEXT TARGET, AND IT IS NOT "STOP DELETING".**

Duck does not erase everything at a level transition -- it clears six summary
fields (`tool_agent.py:1113`) and keeps 30 assistant turns (`:151`). The defect is
that durable summaries update only from assistant `content`, while the model
reasons and emits a tool call. Hypotheses live in reasoning; reasoning reaches
durable memory never.

**How often that bites is UNMEASURED.** An earlier version of this file claimed
"123 calls per level, four evictions per level". That is retracted: it pooled
control with the rejected cap arm, divided calls spent on unfinished and
zero-completion games by completed levels only, and treated an HTTP request as a
retained assistant turn. The one clean case (`lp85` won 8/8, 196 calls, 24.5 per
level) is an average of requests, not retained turns per level, and supports
nothing either way. Re-extract `content_chars` from Gate 2's own Flash-Next
transcripts, **per arm, not pooled**, before building on this.

Fix: a typed `memory_update` the model writes alongside its action.
`arc3/memory.py` implements the contract (29 tests). PRESERVE action semantics,
mechanics, goal evidence, counterexamples, winning paths; RESET current plan,
level coordinates, goal guesses, object identities. Conflicts are recorded as
CONTESTED rather than resolved by precedence; evidence is checked against the
ledger; a winning path carries its level, start signature and expected outcomes
and is never replayed unless the precondition matches.

Two analyses of mine were wrong and are retracted in
`research/honest-assessment.md`: "level 1 is the worst level" (paired within-game,
level 2 costs **1.58x** level 1 relative to its own baseline, worse in 6 of 10 --
the opposite, and it strengthens the memory case) and "the stalled 60% are worth
+0.62" (all fifteen stalled games gaining one level is **+3.39**, more than the
post-hoc best-five +3.25).

Screen games, derived from run 1 plus both Gate 2 control arms: **`cd82` and
`ka59`** -- past level 1 in every observation, never finishing. `lp85` is excluded
despite being our best game: it won outright in one arm, so a ceiling caps any
improvement. Run **`W` / `W-repeat` / `M`**, never `W` / `M` alone.

E0 now needs TWO verified components: a transition predictor and a goal/progress
model. Tycho warns they come apart, and a perfect `step()` that cannot recognise a
win is useless.

**Gate 2 closed 2026-09-16: the 1024-token cap is REJECTED.** It truncated 29.75%
of responses against control's 0.23%, so actions per call fell 40.1% while tokens
per call fell 45.0%, calls rose 60.9%, and tokens per completed level went from
112,084 to 118,114 -- 5.4% the wrong way. Full reading in
`research/gate2-token-cap.md`; arithmetic in `research/gate2_result.py`.

This rejects ONE lever, not the class. Batching, deterministic execution and
verified models raise correct actions per call; the cap lowered it. This run also
cannot price batching: fitting a fixed-plus-marginal model to its two arms implies
a NEGATIVE per-call overhead, because truncating a response is not the same
intervention as asking for a different plan length.

Do not start another cap sweep. Extracting control's response-length percentiles
is worth doing at zero GPU cost; a cap is only harmless above roughly the 95th,
and 1024 sits below the 1288 mean.

Also from this run: identical configurations at different seeds varied **3.92x on
RHAE and 1.50x on cleared levels**. Levels are 2.6x more stable. Gate on levels.

Blocking before any further long run: the terminal gate still reads a stale
pre-drain `nvidia-smi` snapshot (third false negative -- v5, v10, v7). Rule 3b
item 2 already specifies the fix.

**The capability bet.** `research/competitor-survey.md`: no public rank-1 patch
exists, the one convincing public gain (Flash-Next serving) is already ours, and
the strongest untested direction is a stuck-triggered, verified micro-simulator
with animation frames as automatic constraints. Full shape and build order in
`research/rank-1-plan.md` §8. Its induction and verification steps run **offline on
CPU against recorded transitions** and need no GPU booking at all.

**Transfer.** `research/transfer.py`: our 2.2216 local/hidden ratio is the BEST of
five paired observations (mean 2.899, worst 3.877), and transfer appears to degrade
as local rises. Rank 1's 18.81 is a band -- local 41.8 to 72.9, +2 to +5 levels in
every game. A single hidden draw carries +/-5-12%, so 2.37 -> 2.7 would be noise.
Every "local equivalent" in this file was computed from the best-case ratio.

**Then: Gate 1 exit.** An earlier version put the batching
experiment ahead of the first submission. That was wrong — it risks days of tuning
against a local-to-hidden conversion that may not apply to us, when the hidden
score and the 110-game coverage number are the highest-information measurements
available and cost only a day of GPU.

1. **Step 1 — safe baseline, submitted.** Per-wave cap ~6,600 s instead of 7,920,
   hard global shutdown guard, C8 vs C16 validation, clean teardown, valid
   `submission.parquet`, per-game instrumentation preserved.
   `625 + 4 x 6,600 = 27,025 s`, leaving **5,375 s** margin against the required
   4,860. Submit once; obtain hidden score and 110-game coverage.
2. **Step 2 — token levers.** Response-length capping and plan batching (§4).
   First target: tokens per completed level from 48,951 below ~39,000. Competitive
   target for two levels per hidden game: 31,188.
3. **Step 3 — scheduler** (§5), on whatever Step 2 established.
4. **Step 4 — model screen.** Qwen vs gpt-oss on a stratified subset spanning
   zero-, shallow- and deep-performing games. Promote on weighted RHAE/GPU-second,
   never on raw throughput or raw local score.

Step 1 runs on GPU while Step 2 is built, so they overlap rather than queue.

---

## 8. Standing rules

- One submission per UTC day. Never spend one on a change that has not passed a
  replicated local gate.
- Two runs before believing any delta. Byte-identical code has scored 1.70 and 1.32.
- Never read from `environment_files/` — it is the source of the public games.
- Hold out by environment, never by frame.
- Record every run in `research/submissions.md`: commit SHA, local, hidden, coverage.
- Open-source the notebook before the deadline or the milestone does not pay.

---

## 9. What would change the plan

- **Tokens per call scales with plan length** -> batching is dead, the 6.86M token
  ceiling binds, and the model or harness has to change instead.
- **Coverage on 110 games comes back near 110** -> the scheduler's value is only in
  redistribution, not in recovering waste.
- **Hidden score diverges sharply from local/2.4** -> the 25 public games stop being
  a usable proxy and every local measurement loses its meaning.
- **Someone discloses the technique behind the jump to 11** -> adopt it; the rules
  permit building on open-sourced work.

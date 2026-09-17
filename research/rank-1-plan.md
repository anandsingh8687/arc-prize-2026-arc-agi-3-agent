# What seven hours bought, and the plan for rank 1

Written 2026-09-15, in answer to a fair challenge: *we have run experiments for
seven hours, what have we learned that improves the score multifold, and why are
we proving things with eight-hour runs instead of small sets that must
over-achieve first?*

Both halves of that challenge are correct. This document answers them with
numbers rather than agreement.

---

## 1. The honest ledger of the seven hours

Almost none of it was spent measuring the agent. Reconstructed from
`research/run-discipline.md`:

| Run | Outcome | Cause |
|---|---|---|
| Gate 1 v7 | 2h lost | teardown left a vLLM worker |
| v8 | 10m lost | 600 s guard consumed by 480 s of startup; the game got 3.85 s |
| v9 | 10.8 s | IndentationError reached Kaggle |
| v10 | 10m lost | agent succeeded; nbconvert failed on a missing image attachment |
| v11 | passed | first clean full lifecycle |
| Gate 2 smoke v5 | failed gate | a second teardown overwrote the valid first result |
| Gate 2 smoke v6 | passed | current lifecycle reference |

Four of those are harness defects and one is a presentation-layer defect. The
agent was never the thing under test. That is the plain reason no multifold
improvement came out of the elapsed time: **the elapsed time bought reliability,
not capability.** The syntax and attachment classes now fail locally in
milliseconds (`research/validate_notebook.py`); the teardown class has a root
cause and a repair.

What the *earlier* runs did establish, which is real:

- a fixed budget of **6.86M generated tokens** in nine hours;
- **48,951 generated tokens per completed level**;
- **23 of 40** completed levels already at or better than human action counts;
- our one paired local/hidden observation, **5.2652 -> 2.37**, a ratio of 2.2216.

---

## 2. The reframe: efficiency is over, depth is everything

Two numbers from `research/gate1-run1-levels.json`, computed by
`research/rank_1_depth.py` on the real level counts:

```
every completed level replayed at perfect human efficiency,
  at the depth we already reach                      local 10.34
two more levels in every one of the 25 games         local 32.10
three more levels in every one of the 25 games       local 47.27
```

Rank 1's 18.81 hidden converts to roughly **41.8 local** at our measured ratio.

So: *every efficiency lever we own, executed perfectly, is worth 10.34.* Rank 1
needs somewhere between two and three more cleared levels in **every game**.

This is why the score has not moved multifold, and it is not a tuning problem.
Response-length capping, plan batching and the marginal-value scheduler are all
worth doing, and none of them can produce this on their own, because none of them
makes the agent able to solve a level it currently cannot solve.

Uniform-depth reference, for calibration:

```
depth 1 in all 25 ->  3.52      depth 4 -> 35.24
depth 2          -> 10.57      depth 5 -> 52.85
depth 3          -> 21.14
```

We are at mean depth **1.60**.

---

## 3. RETRACTED — the GPU was not idle, it was saturated

An earlier version of this section claimed run 1 achieved 61.8 tok/s against a
saturated 253.0, for **24.4% utilisation and 3.76x headroom**, and called it "the
multifold improvement". **It was an arithmetic error and the claim is withdrawn.**

The error: generated tokens were divided by four waves of 7,920 s. The 25 public
games ran in **one** wave at game concurrency 28. Four waves is the projection for
the 110 *hidden* games, `ceil(110/28) = 4`. The denominator was 4x too large, and
the headroom was entirely that factor.

`research/utilisation.py` now computes it correctly:

```
generated tokens   1,957,868 in 7,920.13 s   (ONE wave, 25 games at C28)
  achieved rate    247.20163 tok/s
  saturated rate   252.96473 tok/s
  utilisation      97.7218%
  headroom         1.0233x

full saturation would have afforded 3,646 actions (146/game)
run 1 produced                      3,563 actions (143/game)
```

Run 1 came within 2.3% of the measured ceiling. **There is no idle time to
recover.**

The supporting observations do not survive either. "One action every seventy
seconds per game" is not idleness — it is 25 games sharing one GPU. That only one
game of 25 reached the 400-action cap is the *token* budget expressing itself, not
an unused action allowance.

Two documents already in this repository said so before the claim was made:
`research/gate1_math.py:10` states the wave structure in a comment on the constant
itself, and `research/token-budget.md:97` concludes that aggregate throughput is
already saturated so more concurrency "mainly improves fairness and latency, not
total work". Neither was read.

**The consequence runs the opposite way from the retracted claim.** At 97.7%
utilisation the only way to buy more actions is to make each action cost fewer
generated tokens. That makes the token levers — response-length capping, plan
batching, deterministic execution between decision points — the *main* lever
rather than a secondary one, and it makes §2's depth requirement harder, not
easier: the 6.86M-token ceiling is real and binding.

## 4. The methodology change

The challenge was: *make something that over-achieves on a small set first, then
we would know with confidence it will improve.* That is right, and it is in
tension with `run-discipline.md` rule 6, which shows an 8-game single run carries
a ~42% coefficient of variation. A small set does not, by itself, give
confidence.

The resolution is that the problem was never the set size. **It is that we kept
choosing `score` as the metric.** Score has eight to twenty-five samples per run
and a 24% CV; it cannot resolve anything smaller than a 4-5 point difference. The
fix is to choose metrics with hundreds or thousands of samples per run:

```
metric                         observations   effective N
tokens per LLM call                  ~1,400   between games and calls
actions per LLM call                 ~1,400   between games and calls
no-op / repeated-state rate          ~3,500   between games and calls
parse-failure rate                   ~1,400   closest to calls -- weakly game-dependent
levels completed                         40   games
local score                            8-25   games, and dominated by one of them
```

**Corrected:** an earlier version of this table read the left column as the
sample count. It is not. Calls within a game share its state trajectory, its
prompt prefix and its difficulty, so they are strongly correlated and 1,400 calls
are nowhere near 1,400 independent samples. The effective N sits between the game
count and the call count, closer to the game count for anything outcome-shaped.
Per-call metrics are still materially better than score, but the factor is not
`sqrt(1400/25)`, and the design fix is **pairing** (§7.1), not sample counting.

Standing rule, added to `run-discipline.md`: **no run longer than fifteen minutes
may be scheduled to decide a question that a per-call metric could decide.**

---

## 5. The small-set experiments, in order

Each is cheap and each has a pre-registered pass mark. None is a nine-hour run.
E1 is withdrawn and E2 is revised; see §3 and §7.3 for why.

### E1 — WITHDRAWN

E1 proposed measuring a GPU busy-fraction to confirm §3's idle time. §3 is
retracted, so the question it asked is answered: utilisation is 97.7%. The design
was also unsound independently — summing wall-clock across concurrent requests
double-counts overlap and can exceed elapsed time.

### E2 — The controller screen (~60-80 min GPU, one server session)

Superseded three times; this is the frozen form. The original gave `lp85` the
whole GPU alone. The second used three games with matched seeds. The third added a
duplicate control arm at a **different** seed as the null — which was the right
instinct applied to the wrong quantity.

Three noise sources, and only one of them is the null for this comparison:

```
same config, different seed    seed sensitivity
same config, same seed         execution nondeterminism   <- THE NULL
candidate vs control, same seed  treatment effect
```

Because `C` and `W` are compared at identical seeds, the seed term cancels in the
pairing and never enters the difference. What remains under the null is execution
nondeterminism: vLLM's continuous batching makes numerics depend on batch
composition, which depends on timing, and Duck's per-request timeout clamps
against a wall clock. Both are live at a fixed seed. Comparing the treatment
effect against seed-to-seed variance instead would set the bar above the right
one and reject real improvements.

**Sequence.** Version 7 settles the response cap first, on paired games and seeds.
Its winner becomes the baseline `W`. Then one server session, three arms:

```
W          Version 7's winning baseline,      seeds 0/1/2
W-repeat   identical configuration,           seeds 0/1/2
C          W + the sparse controller,         seeds 0/1/2
```

Three development games at different depths — `lp85` (6/8), `tu93` (4/9),
`re86` (4/8) — nine streams run concurrently, so serving sits in the saturated
regime production actually runs in rather than an artificially uncontended one.

Per (game, seed) pair:

```
treatment effect  =  C  - W
execution noise   =  W-repeat - W
```

```
PROMOTE C only if, against W and by more than the observed W-repeat noise:
  tokens per useful action fall >= 40%
  completed depth does not regress
  >= 2 of 3 games improve across matched seeds
  paired weighted RHAE per GPU-second improves
```

`W-repeat` has a second use: if it comes back large, that is itself a finding — it
would mean runs are barely reproducible at a fixed seed and every past paired
comparison, Version 7 included, needs rereading.

**Seed sensitivity is not dropped, it is deferred.** Repeat noise answers "does the
treatment do anything at these seeds"; it cannot answer "does it generalise beyond
them". Three seeds on three development games is a small enough surface to overfit.
That question belongs to the locked eight-game transfer test, which already
carries two seeds — and it is the reason that gate must not be skipped for a
candidate that clears E2 convincingly.

### E3 — Version 7, read in the right regime (running)

Two constraints on reading it, from `research/v7_subset.py`.

**The baseline is 9.45, not 8.596.** Run 1 restricted to Version 7's own eight
games scores 9.45. The subset is not a sample of the same population — it contains
`lp85`, which alone scored 58.33. Any statement of the form "Version 7 control is
at 4.67 against run 1's 8.596" compares two different game sets.

The arm is also mid-flight: `lp85` stands at 3/8 in 61 actions, against 6/8 in 141
actions in run 1, and run 1's first three levels cost 53 actions. It is plausibly
on level 4 rather than finished, and a game carrying that much weight is exactly
the one whose partial state makes a running total unreadable.

**The run is in the wrong regime, and this is the part that governs the
conclusion.** Eight games share the GPU that twenty-five shared:

```
per-game generated-token share
  competition, 110 games      62,364   <- the regime that matters
  run 1, 25 games             78,315   (1.3x)
  Version 7, 8 games         117,876   (1.9x, still rising)

games stopped by the 400-action cap
  run 1      1 of 8
  Version 7  3 of 8, with the arm unfinished
```

In production the token budget binds and games never approach 400 actions. In
Version 7 the **action cap binds first**, so a response cap that makes each action
cheaper has nowhere to spend the actions it frees. Its score benefit is therefore
*understated* here, and a null result on score would not be evidence against it.

```
READ     tokens per completed level, tokens per call, actions per call
         -- regime-independent
DO NOT   promote or reject the cap on the paired score difference
```

**This applies with more force to E2.** Three games at three seeds is nine streams,
which saturates *serving* but leaves each game instance roughly a third of
production's contention — further into the wrong regime than Version 7. The fix is
to make the screen's per-game budget match production directly: **cap each game at
~62,400 generated tokens** rather than at 400 actions or a wall clock. That is one
constant, it costs nothing, and without it the screen measures the controller in a
token-rich regime and promotes it into a token-poor one.

## 6. What this means for Milestone 2

Unchanged from `CODEX_NEXT.md` §0, and it should not be softened: rank 1 is
18.81 and rose 70% in two days; we are at 2.37, rank 602. That is 7.9x in fifteen
days with one submission per day. **Milestone 2 first place is not achievable.**

E2 is worth running anyway, because it is exactly what the 2026-11-02 final needs
and because it costs an hour and addresses the question that governs everything
else: *is our depth limited by budget or by capability?*

We have never answered that question. Seven hours of runs did not answer it
because none of them was designed to. That is the real lesson, and it survives
the retraction in §3 — which is itself an instance of the same failure, a claim
made without the measurement that would have tested it, when two files in this
repository already contained the answer.

---

## 7. Reconciliation with the parallel Codex analysis (2026-09-15)

Codex reached the same top-level conclusion independently — depth not efficiency,
gate before spending, Version 7 as the last long micro-ablation — and proposed a
two-gate process plus a **sparse reasoning controller** as the architecture. Three
corrections and one concession.

### 7.1 The proposed development gate cannot fire honestly

The proposal is *"3-4 games, require 2x weighted RHAE per GPU-second."*
`research/gate_power.py` bootstraps that gate against run 1's own per-game score
distribution, under a true null of two identical arms:

```
25 public games: mean 8.60, sd 13.30, CV 155%
scores [0, 0, 0, 0, 0, 0.3, 1.5, 1.8, 1.9, 2.8, ... 27.8, 28.6, 58.3]

games/arm   P(false 2x)   P(false 1.5x)
        3        30.5%         37.9%
        4        28.2%         36.7%
        8        20.0%         31.0%
       25         6.0%         17.9%
```

**A 2x gate on four games fires on 28% of experiments that changed nothing.** The
per-game distribution has a CV of 155% and one game, `lp85`, carries 58.3 of the
total; which arm it lands in dominates whatever the arm actually did.

Cleared levels is a far better small-set outcome — bounded, no outlier — but
unpaired it is no better as a gate:

```
games/arm   threshold for 5% false positive
        3   arm B must clear +7 more levels   (4.8 expected in total)
        4   arm B must clear +8 more levels   (6.4 expected)
        8   arm B must clear +10 more levels  (12.8 expected)
```

Requiring an arm to more than double the total level count is not a gate either.

**The fix is pairing, and it is mandatory, not a refinement.** Both arms must play
the *same* games with matched seeds, so game selection cancels and only run-to-run
stochastic variance remains. Codex specifies matched seeds for the transfer gate
but not the development gate; it belongs in both.

### 7.2 CORRECTED — run 3 cannot calibrate the noise floor

This subsection previously proposed extracting run 3's per-level arrays to obtain
a paired two-run sample on the same 25 games, and setting the development-gate
threshold from it. **That is wrong.** Run 3 differs from run 1 in two configuration
dimensions at once:

```
          per-game cap    game concurrency   score
run 1          7,920 s                  28   8.596
run 3        ~6,600 s                   16   7.686
```

The 0.91-point gap therefore mixes cap effect, concurrency effect and randomness,
and isolates none of them. Extracting the arrays is still worth doing — it is free
and gives per-game detail for two configurations — but it **cannot** produce a
noise threshold.

Nor can Version 7, despite being properly paired by game and seed: its two arms
differ by the response cap, so it measures that cap's effect, not the null.

**A noise floor requires two arms differing in nothing but the sampling seed.**
The cheapest way to get one is to include a **duplicate control arm** in the same
multi-arm session — same configuration, different sampling seed. It costs one arm
slot and it is the only measurement that calibrates every promotion threshold in
the plan. Without it, "2 of 3 games improve" and "40% fewer tokens per useful
action" are thresholds chosen by argument rather than by measurement, which is the
failure `research/gate_power.py` was written to prevent.

While computing this, run 3 also served as an independent check on §3's
retraction: 226.87 tok/s against the same 252.96 saturation, **89.7% utilisation**
at C16. Two runs, two configurations, both near saturation, neither anywhere near
the retracted 24%.

### 7.3 CONCEDED — the controller is the main lever

This subsection previously argued that the sparse reasoning controller was a bet
on depth being budget-bound, and that a concurrency or pipelining change might be
a cheaper multifold lever, on the strength of the 24.4% utilisation figure.

That figure was wrong (§3). At 97.7% utilisation there is no configuration change
available: concurrency cannot create throughput that is already saturated. The
controller — fewer, cheaper, checked calls with deterministic execution between
decision points — is the main lever, not a secondary one. Conceded in full.

### 7.4 The concession

The controller is **robust to both regimes**, which is a real argument for building
it regardless of E1's outcome. If we are throughput-bound it cuts tokens per
action; if we are latency-bound, its deterministic executor produces actions with
no model call at all, which is exactly what a latency-bound regime needs. Two of
its elements are also new here and worth adopting outright: replaying known
winning paths after death without re-reasoning, and a persistent playbook of
discovered mechanics that survives context resets.

So: build it. But run E1 and E2 first, because together they cost ninety minutes
and they determine whether the controller is the main lever or a secondary one.

### 7.5 Agreed without qualification

- Version 7 is the last long isolated micro-ablation.
- No daily submission is spent on a token-cap adjustment worth 10-20%.
- Both gates must pass before any 25-game run.
- Qwen and gpt-oss are compared only after both have the same text-perception layer.
- The hidden equivalents in either plan are planning estimates from one noisy
  conversion, not forecasts.

---

## 8. The capability bet — verified micro-simulator (2026-09-15)

`research/competitor-survey.md` establishes that no public "rank-1 patch" exists,
that the one large convincing gain in public work (Flash-Next serving) is already
ours, and that the strongest untested direction is an executable, verified model of
the game rather than better prompting. Adopted as proposed, with the escalation
**conditional** — Retrodict's always-on "investigate everything" nearly doubled
actions on easy levels, while runner-triggered escalation cracked hard ones.

Shape: Duck explores; every action is recorded as a compact transition (settled
frame before, action, frame after, intermediate animation evidence, changed
components, level/state change); the controller emits 3-6 action plans carrying
expected-cell or expected-object invariants and runs them without another model
call until an expectation fails; on a *stuck* signal — repeated states, two
voluntary resets, repeated no-ops, sustained calls without progress — the model
writes a small `step(state, action)` and `goal(state)`; the program is rejected
unless it reproduces every recorded transition relevant to the mechanic it claims;
search runs against the verified program; the plan executes live and halts on the
first mismatch; only verified rules and explicit counterexamples persist.

The original combination is using **intermediate animation frames as automatic
constraints on the simulator** rather than as a tool the model may or may not
remember to call (priced and triggered in §9 below) — more causal evidence per charged action, without growing the
prompt. Not claimed as unique; claimed as the strongest untested opening visible
in public work.

### CORRECTED — verification is CPU-only; induction is not

An earlier version of this section claimed "program induction and verification are
a pure function of recorded data" and put both offline. **Only verification is.**
Producing a candidate `step` requires a model — Qwen on Kaggle at competition time,
or an API model during development, which does not transfer because the
competition run has no internet. Search over an already-verified program is also
free. Induction is not.

```
verify_candidate(step_fn) over recorded transitions   CPU only, free, seconds
search against a verified program                     CPU only, free
inducing the candidate                                needs a model -- GPU
prompt/contract quality for induction                 needs Qwen -- GPU
```

That is still worth a great deal: the verifier and the search can be built and
tested to completion before any GPU is booked, so when GPU time is spent it is
spent **only** on induction quality, with everything downstream of it already
known-good. It is a smaller claim than the one it replaces, and it survives.

### Four design constraints the first version got wrong

**Transitions do not pool across games.** The 3,563 recorded transitions belong to
25 different games with different mechanics. Each game gets its own model. The
ledger is therefore per-game, and so is every verification.

**Evidence is thinnest exactly where it is needed — but a count does not measure
that.** An earlier version of this section said the bet fails if distinct
`(state, action) -> outcome` triples come back small. **Too strong.** A handful of
transitions can pin down a simple mechanic; thousands can stay redundant or
ambiguous. Count is not learnability.

The ledger reports what actually decides it — implemented in `arc3/ledger.py`,
pinned by `tests/test_ledger.py`:

```
unique normalised state-action pairs
repetition rate
ALIASING          identical visible state + action, different outcome
coverage by legal action, and by interaction/object type
changed vs no-op outcomes
chronological train/holdout split
```

Aliasing is the one that blocks the whole contract: if the visible state does not
determine the outcome, no `step(state, action)` can be exact until latent
variables are proposed, and it is measurable from recorded data with no model in
the loop at all.

**`step(frame, action)` is the wrong signature.** Visible frames can alias hidden
state — two identical boards can behave differently. The simulator needs
history-derived latent variables, so the contract is closer to
`step(state, action)` where `state` carries inferred latents, with the induction
allowed to propose them.

**Animation frames constrain event interpretation, not state prediction.** The
simulator predicts *settled* frames. Requiring it to reproduce every intermediate
frame would fit presentation timing rather than mechanics. Animation is evidence
about what happened between settled states, not a prediction target.

### The contract is a partial model

```python
step(state, action) -> NextState | UNKNOWN
```

It does not need to understand the game. It must be **exact on the domain it
claims** and explicitly `UNKNOWN` everywhere else, tested on chronologically held
out transitions, used for search only while the plan stays inside its verified
domain, and followed by a discriminating live probe when search reaches `UNKNOWN`.

This is what makes the Milestone 2 slice small: the target is a verified local
mechanic, not a game engine.

Scoring keeps two numbers apart rather than collapsing them into an accuracy:

```
soundness = exact / claimed     must be 1.0
coverage  = claimed / total     how much of the game the model actually buys
```

A 90%-accurate model is *worse* than one covering 20% exactly, because search
plans straight through the wrong 10% into a state that does not exist and every
action after that is charged for nothing.

The two amendments compose without a special case. **A memorised lookup table
returns `UNKNOWN` for everything it has not seen, so it scores perfect soundness
and near-zero coverage on the holdout** — which reads correctly as useless.
Without the chronological split it would score 100% and mean nothing;
`tests/test_ledger.py` pins exactly that case.

### E0 — can Qwen3.8 write a verified `step()` at all? (~20 min, one game)

**This gates the build. It runs after the ledger contract is fixed, and before
the three-game screen.**

Tycho's ablation (`research/what_100_costs.py`) shows actor-controlled modelling
helped a frontier model: 79.07 -> 88.49. It establishes **neither** an additive
nor a multiplicative transfer to Qwen at 5.27 -- one run per policy, one model,
one budget, from a base of 79. The only supported statement is that the effect
was positive at frontier capability and its size at our capability is unknown.
E0 measures it.

```
one game we already reach depth 3+ on (lp85 6/8, re86 4/8)
record transitions for one level      (rides any run, free)
ask Qwen3.8 for a step() for that mechanic, at most 3 attempts
verify offline with arc3.ledger       (CPU, free)

PASS  ZERO confident errors anywhere in the holdout AND no rollout failure
      from any start position -- a partial model returns UNKNOWN, it does not
      guess -- AND >= 3 consecutive NOVEL steps advanced
      on the candidate's OWN predicted states (verify_rollout, not
      teacher-forced), each exact in grid, level, attempt, status and
      available actions, with >= 1 step inside that chain that changed
      something
FAIL  classify the cause, try ONE structurally different game, then screen
      gpt-oss-120b -- a single failure is a bad representation as easily as
      a model limit
```

The screen tests whether the controller helps. E0 tests whether it can exist.

**The ledger took two rewrites to become able to run this honestly.**

The first contract was `step(state_hash, action)`, and nothing can induce a
mechanic from a digest -- a candidate could only recognise hashes.

The second passed a board but scored **teacher-forced one-step predictions**:
every call received the recorded ground-truth state, so "three consecutive
correct predictions" meant three independent guesses, not three steps of
simulation. **Search chains predictions, so the verifier has to chain them too.**
A candidate whose latent evolution is completely broken scored 100% soundness
and 100% coverage under that gate;
`test_teacher_forcing_passes_a_model_that_cannot_simulate` is exactly that
candidate, and it now fails at `longest == 1`.

`arc3/ledger.py` now has two verifiers with different jobs:

```
verify()           teacher-forced, one step   DIAGNOSTIC ONLY -- locates a defect
verify_rollout()   feeds each PREDICTED successor into the next call   THE GATE
```

A fourth pass closed a false positive created by the third's own fix:

```
init_latent let a candidate DODGE the sweep. Silent while its latent was empty,
  it registered zero confident errors, then guessed wrong once a rollout
  initialised it. Two repairs, both needed: the sweep now runs WITH init_latent,
  and `usable` honours `first_failure`, which is where a chained failure shows
  up when the sweep is clean.
evidence volume was counted on RAW keys, so a ticking HUD turned six revisits
  of one state into six "unique situations" at 0% repetition. unique_keys and
  repetition_rate now use the masked key; the raw count is reported alongside.
the three hashes are now REQUIRED -- a recorder omitting `before_raw_hash`
  would have silently collapsed every alias key and disabled alias detection
  while reporting nothing wrong.
```

A third pass closed two more false positives, both reproduced before repair:

```
a clean chain excused confident errors elsewhere -- a candidate wrong 5 of 8
  passed on the strength of the 3 it happened to get right. The gate now
  requires ZERO confident errors across the holdout; search reaches those
  states too.
a ticking HUD read as aliasing -- novelty used the masked before-hash while
  the outcome used the raw after-hash. Novelty now uses the masked key,
  ALIASING uses the raw key (same COMPLETE observable state), and divergence
  visible only under the mask is reported separately as `masked_alias_keys`,
  which means the mask discarded information needed to reproduce the raw
  frame -- not necessarily causal game state, since a decorative HUD carried
  forward triggers it too. What it rules out is hidden state; raw aliasing is
  the signal for that.
continuity is checked before chaining: if a recorded `after` is not the next
  `before`, a reset or dropped frame sits between them and crediting the
  candidate for that jump would credit the environment.
latents can be initialised from preceding history, so a mechanic depending on
  anything not visible in the current frame is representable at all. Every
  chain previously started from {}.
attempt joins the outcome signature.
```

Also fixed in the second rewrite, each pinned by a test:

```
Prediction carries a COMPLETE successor ObservedState -- grid, level, attempt,
  available actions, status -- and all of it is compared. Optional fields let a
  candidate omit the available actions and still score exact.
aliasing compares AFTER signatures, not the before-state's raw hash; a ticking
  HUD previously registered as two different outcomes for one action.
progress must occur INSIDE the novel chain, so a memorised progress step cannot
  be borrowed to rescue three novel no-ops.
latents are never compared to ground truth -- there is none -- but are carried
  forward, which is what surfaces a wrong latent update two steps later.
```

Test grids are now genuinely different boards with hashes computed from them,
rather than identical grids carrying hand-assigned hash strings.

### What now stands between here and E0

```
DONE   ledger contract, four passes, 40 tests
DONE   crash-proof persistence + trace round-trip test   arc3/trace.py, 9 tests
TODO   the Duck-side adapter: FrameDataRaw -> Transition
TODO   the induction prompt, with the 20% holdout genuinely locked
TODO   E0 end to end, locally
THEN   ~20 min of Kaggle GPU, and not before
```

`arc3/trace.py` is append-only JSONL, one self-contained record per transition,
flushed and fsynced before `write` returns. `research/run-discipline.md` rule 2
exists because a run completed its work and died in teardown; a ledger held in
memory for nine hours is that failure waiting to happen. A killed process now
keeps every transition it finished recording, and `read_trace` tolerates the
torn final line an interrupted write leaves behind -- one lost transition, not a
lost run.

The Duck-side adapter is genuinely not done. Duck's source is not in this
repository (it lives in the notebook), so what exists here is the schema, the
persistence and the round-trip proof that a restored ledger reports and verifies
identically to the original. Turning a `FrameDataRaw` pair into a `Transition` --
including `animation_frames` from the intermediate frame list, and the masked
hash from the live `VolatilityTracker` -- is the next piece of code to write.

### The four falsifications, ordered by what they cost

Three of the four are offline. Only the last needs the full live loop.

```
F1  visible-state aliasing survives proposed latents   ledger only -- NO MODEL, free
F2  candidates fit train, fail chronological holdout   verifier -- CPU, needs induction
F3  verified domain too narrow to plan inside          verifier -- CPU, needs induction
F4  a verified plan still clears no extra level live   full loop -- GPU
```

**F1 needs no model at all** and is the cheapest kill available: it runs the
instant a ledger exists. Recording transitions is nearly free to bolt onto a run
already being made, so the ledger should ride the next GPU run rather than
justify one.

A note on reading F2. Within a game, transitions are not interchangeable — later
ones come from deeper levels with different mechanics. So a chronological holdout
tests generalisation *across levels*, which is what we need, but a model exact on
level-1 mechanics will legitimately fail a level-4 holdout. Under the partial
contract that resolves itself: it should score soundness 1.0 with coverage falling
to zero on the later material, which is a model whose domain ended, not a model
that is wrong.

**Budget the probe.** Resolving an `UNKNOWN` at the search boundary is a
deliberate experiment, not exploration, and it costs charged actions. Probe only
when the unknown blocks a plan that would clear a level, and when the probe's cost
is small against that level's remaining budget.

### Risk, and the Milestone 2 disagreement

The full architecture will not be built, gated and validated before Milestone 2
closes on 2026-09-30. A **tightly scoped slice** might: per-game transition ledger,
`verify_candidate(step_fn)` over recorded settled transitions, short plans carrying
invariants, a stuck trigger on repeated states / no-ops / resets / calls without
progress, Qwen writing a mechanic-specific transition function on trigger, search
only after the verifier passes, and halt on first mismatch. That reuses Duck's
existing Python REPL and is days of work, not weeks.

Where the disagreement actually sits is not the build but the **gate cascade after
it**: three-game screen, locked eight-game transfer, 25-game run, then a scored
nine-hour submission at one per day. That is several days of GPU cycles assuming
each passes first time, and in this project four of the last six Kaggle runs failed
on harness defects rather than on the agent.

So: pursue the slice, and if it clears the gates before 2026-09-30, submit it. The
disagreement does not change what to do next, because the slice is the November
work either way — which is the only reason it is worth starting under a deadline it
probably misses.


---

## 9. Animation evidence — recorded in full, surfaced almost never

### RETRACTED — the "15x tokens per insight" figure

An earlier version of this section took the disclosed **+17% tokens per action**
and multiplied it by a proposed surfacing rate to price selective surfacing. That
is invalid: the +17% covered the whole animation arm — metadata, prompts and tool
usage — not a per-surfacing cost, and multiplying it by a rate assumes a linearity
nobody measured. The derived table (0.17% overhead at 1% surfacing, and so on) is
withdrawn.

What stands without arithmetic: **recording is free** — the frames already arrive
in the engine's response — and **surfacing is what costs**. The disclosed arm
found **2 of 181 tool calls genuinely useful**, so a design that records always
and surfaces rarely is attacking the right term. How much it saves is unmeasured.

### The trigger is ranked, not a single condition

An earlier version made genuine aliasing the *only* trigger. Too narrow: a
deterministic animation can reveal the route a change took even when the settled
outcome never varies — liquid flowing along a path, say — and requiring divergence
would discard exactly that. `GameLedger.animation_candidates()` now returns
`(priority, transition)`:

```
1  genuine aliasing plus informative animation     the board cannot explain it
2  settled no-op with transient motion             the board says nothing happened
3  level/status change the settled diff does NOT explain -- transient cells
   present, or the board resized mid-animation
4  >= LARGE_TRANSIENT_CELLS touched where the mechanic model returned UNKNOWN
```

Priorities 3 and 4 previously said "unexplained" and "large" while the code
accepted any animated level change and any informative animation. Both
qualifications are now implemented rather than described. `LARGE_TRANSIENT_CELLS`
is a chosen default, not a measured threshold, and is named so it can be revised
when something measures it.

Priority 4 needs `unknown_keys` from a candidate simulator: no amount of recorded
data says where a model fell silent.

### A resize is a snapshot, not a skipped frame

v3's builder dropped any frame whose shape differed from its predecessor, so the
first frame after a board resize was discarded — and since a **level transition
is exactly what resizes the board**, the animations priority 3 exists to surface
were the ones that could not be reconstructed. A `FrameStep` now carries either
incremental `changes` or a full `snapshot`, and `AnimationEvidence.frames(before)`
rebuilds every recorded frame.

### Order is preserved, because losing it is permanent

The v2 schema stored `transient_cells[(r, c)] = unique_values`, which **cannot
tell `A -> B -> C` from `C -> B -> A`.** Once the raw frames are discarded that
loss cannot be undone, and the selective surfacing this whole section exists to
support would have had nothing faithful to surface.

v3 stores an ordered, consecutively-deduplicated timeline — each entry is one
frame's changes against the previous — and derives transient cells from it.
`test_the_timeline_preserves_order` pins the two directions apart.

The model sees only compact metadata by default:

```
frame_count   distinct_frame_count   touched_cell_count   bounding_box   settled_noop
```

`touched_cell_count` is deliberately not called transient: it counts every cell
the animation wrote, including ones whose final value is plainly visible in the
settled diff. A true transient count needs the before and after boards, so it
lives on `Transition.animation_summary()` instead. The full timeline is surfaced
only for transitions the triggers select.

### Reading an older record is refused, not tolerated

`decode` rejects any `v` it does not support. Silently reading a v3 record would
hand back an empty animation timeline, which reads as "this transition had no
animation" — evidence loss disguised as evidence, and the one failure mode the
ledger is least able to detect afterwards.

### Both keys now mean the complete observable state

It was `(level, before_raw_hash, action)`, omitting `attempt`, `status` and
`available_actions` — so identical boards on different attempts registered as
hidden-state aliasing when the difference was plainly visible. Now:

```python
(level, attempt, status, available_actions, before_raw_hash, action)
```

`novelty_key` had the same omission, which understated novelty in the holdout,
weakened lookup-table rejection and mismatched priority-4 UNKNOWN lookups. It now
carries the same fields with the **masked** grid hash, so a ticking HUD still does
not make every state look new.

Same defect class as the ticking-HUD bug, three times over: a key claiming to be
complete that was not.

### Scope, stated plainly

**13 of the 25 public games produce multi-frame responses — 52%.** For the other
twelve this lever is exactly zero, and nothing is known about the proportion among
the hidden 110.

The trace format is **v4, frozen**. Nothing has been recorded, so there is no
migration — but this is the last moment that is true, and the Duck adapter must be
written against v4.

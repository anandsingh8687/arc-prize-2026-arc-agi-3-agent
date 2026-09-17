# ARC-AGI-3 — Gate plan and standing work queue

Working document. Milestone 2 closes **2026-09-30 23:59 UTC**.
Branch: `claude/arc-prize-2026-9e0g6n`. No PR open yet.

Two operators:
- **Claude** — repository, agent code, local evaluation. No GPU, no Kaggle account.
- **Codex** — Kaggle account, browser, GPU notebooks, submissions.

Read [PLAN.md](PLAN.md) for the architecture and [probe-2026-09-14.md](probe-2026-09-14.md)
for measured hardware limits. This file is the task queue.

---

## 0. Where we actually are

| Thing | Status | Value |
|---|---|---|
| Scoring harness | done, 18 tests pass | RHAE verified against the toolkit's own calculator |
| Deterministic layer | done | volatility masking, effect ledger, components, win-path cache |
| Model-free floor | **measured: 0.086** | 2 of 183 levels, 25 games, 400 actions each |
| Hardware | measured | 1x RTX PRO 6000 Blackwell 96GB, 9h, 1 submission/UTC day |
| Model throughput | measured | gpt-oss-120b 2.4x faster than Qwen3.8 at matched 8k context |
| Kaggle submissions made | **0** | Gate 1 not started |
| Leaderboard rank 1 | 11.04 (Tufa Labs) | rank 3 cut line 8.40 |

---

## 1. The score model — where points actually come from

Total score decomposes multiplicatively:

```
total  ≈  (games_reached / 110)  ×  mean_score_on_reached_games
```

Both factors are winnable, and **they are not equally hard**. Depth is bounded by
model capability. Coverage is bounded by engineering. From our own computation of
the 183 public levels:

| Depth reached per game | Ceiling at perfect efficiency |
|---:|---:|
| 1 level | 3.52 |
| 2 levels | 10.57 |
| 3 levels | 21.14 |
| 4 levels | 35.24 |

Tufa's 11.04 sits just above the depth-2 ceiling, so they are finishing 2 levels
almost everywhere and reaching 3 occasionally — *if* their coverage is complete.
If their coverage is only 70%, their per-game mean is nearer 15.8 and they are
deeper than they look.

### The single most valuable unknown

**How many of the 110 games does a real 9-hour run actually reach?**

Nobody has published this. Unreached games score 0 *and still divide the total*
(verified in `arc_agi/scorecard.py`). If an unmodified Duck run reaches only 40 of
110, then coverage work alone is a **2.75x multiplier** — the cheapest route from
4 to 11 that exists, and pure scheduling, no reasoning improvement required.

If coverage is already near 110, that multiplier is gone and everything must come
from depth, which is far harder. **This one measurement reorders the whole plan.**
It is Gate 1's real deliverable — the submission is secondary.

### Estimated contributions

Budget targets to test against, not predictions. Confidence is our own.

| Lever | Est. contribution | Confidence | Owner |
|---|---|---|---|
| Working Duck-class baseline | 1.5 – 4.0 | high (forks land here) | Codex |
| Full 110-game coverage via scheduling | **×1.5 – ×2.75** | medium, depends on the unknown above | both |
| Model upgrade (Qwen3.8 or gpt-oss-120b) | ×1.5 – ×3 | medium (the field jumped when Qwen3.8 landed) | Codex |
| Plan batching (multi-action per call) | ×1.2 – ×2 | medium — converts token budget into depth | Claude |
| Win-path caching + no-op avoidance | +10 – 30% | high — squared metric, cheap to implement | Claude |
| Retrodiction | +5 – 20% | low — unproven at 27B/120B scale | Claude |
| Behavioral cloning | −0 – +10% | **very low** — a competitor reports it failing | last |

Multiply the plausible middles and 11 is reachable. Multiply the pessimistic ends
and we land near 4. Both outcomes are consistent with what we currently know,
which is why the measurements below matter more than the theorising.

---

## 2. Standing rules

1. **One submission per UTC day.** Never spend one on a change that has not passed
   a replicated local gate. Record every submission in `research/submissions.md`
   with commit SHA, local score, hidden score.
2. **Two runs minimum before believing a delta.** Byte-identical code has scored
   1.70 and 1.32 on this leaderboard. A hidden delta under ~0.4 ranks nothing.
3. **Never read anything from `environment_files/`.** It is the source of the 25
   public games. Nothing derived from it generalises to the 110 hidden ones. It is
   not a competition rule; it is about not poisoning our own measurements.
4. **Every component ships with an ablation.** Score *and* actions/sec, both.
5. **Hold out by environment, never by frame.** Frame-level splits leak game
   identity and will make everything look like it works.
6. **Open-source the notebook before the deadline** or the milestone does not pay.

---

## 3. GATE 1 — Baseline and the coverage measurement

**Exit criteria:** a valid 9-hour Kaggle run, submitted, with a known hidden score,
and a per-game trace showing how many of the 110 games were reached.

### Codex tasks

- **1.1** Package the Duck harness (https://github.com/Tufalabs/duck-harness) with
  Qwen3.8 27B FP8 using the runtime bootstrap already captured. Get it running end
  to end in a Kaggle notebook.
- **1.2** Confirm `submission.parquet` is produced in the expected schema. Check
  the competition's sample submission for the exact columns.
- **1.3** Raise `MAX_ACTIONS` from 80 to 400 (the official `reasoning_agent.py`
  template already uses 400, so this is sanctioned).
- **1.4** **Instrument the run before submitting.** Log per game: wall seconds,
  actions taken, levels completed, LLM calls, generated tokens, and whether the
  game was reached at all. Write it to the notebook output. This trace is the
  actual deliverable.
- **1.5** Submit. Record the hidden score.
- **1.6** **Report the coverage number**: how many of 110 games were reached, and
  the distribution of wall-time per game. Everything after this reprioritises on
  that answer.
- **1.7** Report cold-start cost: engine load + first generation, as a fraction of
  the 9 hours. Measured at ~190s for Qwen; confirm in a full run.

### Claude tasks

- **1.8** vLLM backend behind the existing `Agent` interface, written against the
  captured launch config, with a local stub so it is testable without a GPU.
- **1.9** Port the deterministic layer into the submission path so Gate 3 work
  does not require re-packaging.

---

## 4. GATE 2 — Model selection

**Exit criteria:** one model chosen on paired game score, the other stops
consuming engineering time.

Throughput is already settled — gpt-oss-120b is ~2.4x faster at matched 8k context
(466 vs 197 tok/s at C32). That establishes affordability, **not** ARC ability.

Two facts that cut against gpt-oss and must be resolved:
- Its associated best public score on the Models tab is **0.24** (Qwen3.8 Flash
  Next: 4.33). Probably a modality mismatch rather than capability, but unproven.
- **It is text-only.** Duck feeds both image and text grid representations.
  Dropping it in unchanged deletes half the perception, which would produce
  exactly that 0.24.

Counter-evidence on capability: Retrodict, the highest-scoring harness anywhere at
99.86%, is deliberately text-only — parsed boards, diffs and components through a
log, never images. Text perception is not a ceiling; it is what the best design chose.

### Codex tasks

- **2.1** Paired evaluation on the 25 public games: identical prompts, action
  limits, seeds, time budgets. Both models. Report per game: RHAE, levels
  completed, actions, LLM calls, generated tokens, wall seconds.
- **2.2** Run gpt-oss **with the text perception layer** (task 2.5), not raw Duck.
  Benchmarking it inside an image-dependent harness measures the mismatch, not
  the model.
- **2.3** Report tokens-per-action and actions-per-level per model. The decision
  metric is **expected weighted RHAE per GPU-second**, not tokens/sec.
- **2.4** Confirm gpt-oss KV capacity under the real agent load. It holds 251k
  tokens against Qwen's 670k, capping it near 28 concurrent streams.

### Claude tasks

- **2.5** Text perception layer: parsed board, per-step diff, connected components,
  object centroids, as compact text. This is the prerequisite for 2.2 and is
  useful to both models.

### Promotion rule (agreed)

```
Use gpt-oss-120b only if:
    paired local RHAE improvement >= 20%
AND completed-environment count does not decrease
AND projected full-run time fits with >= 15% margin
Otherwise stay with Qwen3.8.
```

---

## 5. GATE 3 — Systems

**Exit criteria:** every component ablated, full coverage of 110 games achieved,
throughput sustained.

Prefix caching is already proven mandatory: wall 16.26s → 1.69s, mean TTFT
10.52s → 1.63s. That win has to survive into the agent loop, not just the probe.

### Codex tasks

- **3.1** Prefix caching in the real agent: shared system prompt as an exact
  common prefix across all game streams. Verify cache hit rate at runtime.
- **3.2** Concurrency tuning. Aggregate saturates ~C32; per-stream degrades much
  earlier (Qwen: 29.3 → 6.2 tok/s from C1 to C32). Find the operating point that
  maximises weighted score per GPU-second, expected in the **8–16 active** range.
- **3.3** Adaptive scheduler across 110 games: broad first pass so every game is
  reached, then reallocate toward games making progress. Ablate against equal
  time-slicing. A competitor reports ~13.6% counterfactual action savings from a
  shadow scheduler — unvalidated on RHAE, treat as a hypothesis.
- **3.4** Deterministic serving: fixed seeds, pinned sampling params, reproducible
  across runs. Without this no ablation means anything.
- **3.5** Wall-clock guard: hard stop with margin so a run never dies mid-game and
  loses its scorecard.

### Claude tasks

- **3.6** Legal-action guard — never spend an action the frame says is unavailable.
- **3.7** Win-path cache keyed on state preconditions, invalidated on mismatch.
  Already drafted in `agents/heuristic.py`; needs porting to the LLM agent.
- **3.8** Volatile-cell masking in the LLM path — **hashing only**. Timers and life
  counters stay visible to the model; they are often causal.

---

## 6. GATE 4 — Reasoning

**Exit criteria:** plan batching and retrodiction each ablated; BC attempted only
if the earlier gates have landed.

### Claude tasks

- **4.1** Plan queues: one model call emits several actions, each carrying the
  cells it expects afterwards. Interface already built (`agents/base.py`); needs
  the prompt contract and parser. **This is the component that converts the token
  budget into depth** — at 0.577 actions/sec a model consulted per action cannot
  keep pace.
- **4.2** Expected-frame checking on stable invariants, not pixel-perfect equality
  — animated games will false-positive otherwise.
- **4.3** Retrodiction: replay a hypothesis over recorded history in Python before
  spending a real action. Wrong guesses cost nothing.
- **4.4** Playbook memory surviving context resets — a curated working model, not
  a journal.
- **4.5** Escalation on stuck levels: after N actions, build an executable
  `step(state, action)` simulator, verify it retrodicts every recorded frame, then
  search it.

### Codex tasks

- **4.6** Ablate 4.1–4.5 individually on the 25 public games, two runs each.
- **4.7** BC / affordance prior **only if the gates above reach ~7**. Held out by
  environment. Kill it unless it beats simple geometry and effect heuristics.
  A competitor reports hand-built imitation data underperforming Qwen3.8 and
  overfitting individual games. 342 replays, 145 successful solves, all from the
  public games whose mechanics the hidden set deliberately changes.

---

## 7. Continuous background tasks for Codex

Run these throughout, not once:

- **7.1** Check the leaderboard daily. Record rank 1 and rank 3 in
  `research/submissions.md`. The rank-3 cut line is the milestone-prize threshold.
- **7.2** Watch the competition discussion forum for technique disclosures. The
  jump from ~1.7 in late August to ~11 in mid September is still unexplained. If
  anyone discloses what caused it, that outranks everything else in this document.
- **7.3** Watch for the 5n action cap. Not present in the Kaggle harness, stated in
  the ARC Prize technical report. If a run shows levels terminating at exactly 5x
  the human median, it is enforced server-side and efficiency work immediately
  becomes depth work.
- **7.4** Track GPU quota burn. A 9-hour run is expensive; know the weekly budget.
- **7.5** After each submission, diff hidden against local score. Build our own
  local→hidden calibration. The only published ratio is 2.4–2.9x from three
  correlated points by one team — we should have our own.

---

## 8. What would most change our mind

Listed so we notice if it happens:

- Coverage turns out to already be near 110 → the scheduler multiplier vanishes
  and everything depends on depth.
- gpt-oss with text perception still scores badly → the 0.24 was capability, not
  modality, and Qwen is the answer.
- The 5n cap is real on Kaggle → efficiency and depth merge into one problem.
- Someone discloses the technique behind the jump to 11 → adopt it immediately;
  the rules explicitly permit building on open-sourced work.
- Local runs stop predicting hidden runs → the 25 public games are no longer a
  usable proxy and we are flying blind on 55 submissions' worth of signal.

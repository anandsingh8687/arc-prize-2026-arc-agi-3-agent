# ARC Prize 2026 (ARC-AGI-3) — Research Findings & Plan (v2)

**Status:** v2, revised 2026-09-14 after an independent audit (Codex, with a signed-in
Kaggle session) refuted several v1 claims. Corrections are logged in §0.

Facts are labelled by evidence strength:
- **[SRC]** verified by reading the installed engine source (`arc-agi` 0.9.9 / `arcengine` 0.9.3)
- **[LIVE]** verified against signed-in Kaggle pages on 2026-09-14
- **[3P]** self-reported by a third-party competitor repo — may be stale or self-serving
- **[OPEN]** unresolved

---

## 0. CORRECTIONS LOG (v1 → v2)

Every item here is a v1 error. Listed so they are not silently reintroduced.

| v1 claim | Correct value | Source |
|---|---|---|
| 12-hour runtime | **9 hours** per notebook execution, CPU and GPU alike | [LIVE] |
| ~6.5 min/game | **540 / 110 = 4.91 min/game** aggregate (not a serial timeout — calls can overlap) | arithmetic |
| 5 submissions/day | **1 per UTC day per team** — Rules text, not just UI | [LIVE] |
| Milestone 2 prizes $25K/$10K/$2.5K | **$25,000 / $7,500 / $5,000** | [LIVE] |
| 110 games, split unknown | **110 hidden games: 55 public LB / 55 private LB** | [LIVE] |
| RTX 6000 Ada, 48GB | **RTX PRO 6000 Blackwell, 96GB**, one GPU on `g4-standard-48` | [LIVE] + Google G4 docs |
| "Search is structurally incapable" | Overstated. Two teams' results show *their* search agents lost to *their* LLM agents. Does not generalise to all search. | audit |
| Local→LB shrink of 2.4–2.9x usable for target setting | **Not usable.** Three correlated points, one team, changing systems, near-zero scores. | audit |
| BC on human replays = the differentiated bet | Demote to a gated ablation. Only 342 replays / **145 successful solves**, all from the 25 *public* games whose mechanics the hidden games deliberately change. A competitor already reports hand-built imitation data failing and overfitting. | audit |
| Submit on Days 15–16 | **Submit a valid baseline on Day 1.** At 1/day, packaging failure is the likeliest way to lose the window. | audit |
| "Every leaderboard score uses 27–31B models" | **Unsupported.** Kaggle does not reveal models behind private notebooks. | audit |
| "120B MoE with 5.1B active may outrun dense 27B" | Not implied. Routed-expert memory traffic, MXFP4 kernel quality, reasoning-token length and batching decide throughput. | audit |
| "~35GB left for KV cache" | Upper bound, not usable capacity. CUDA graphs, activations, vLLM workspace and fragmentation consume part of it. | audit |

---

## 1. PROBLEM STATEMENT

An agent is dropped into a turn-based grid video game it has never seen, with no
instructions, no stated rules and no stated goal. It must infer the mechanics, work out
what winning means, and complete levels — in roughly as few actions as a human needed.

- **Observation:** 2D grid, max 64x64, cell values 0-15, plus state metadata.
- **Actions:** `RESET`, `ACTION1`-`ACTION5` (simple), `ACTION6` (click at x,y, 0-63),
  `ACTION7` (undo). Each game exposes a subset via `available_actions`.
- **States:** `NOT_PLAYED`, `NOT_FINISHED`, `WIN`, `GAME_OVER`.

**Scoring — RHAE** [SRC]:

```
level_score = min( (human_baseline_actions / agent_actions)^2 * 100 , 115 )
game_score  = Σ(level_index × level_score) / Σ(level_index over ALL levels)
total       = mean(game_score) over ALL environments; unplayed ones score 0 and still divide
```

Baseline = upper-median first-time human player, per level.

**Constraints** [LIVE]: no internet during evaluation (offline open-weights only);
one GPU (`g4-standard-48` = 1× RTX PRO 6000 Blackwell, 96GB); **9-hour** runtime;
**1 submission per UTC day**; forced competition mode.

**Competition mode** [SRC + docs]: one scorecard, one `make` per environment, level-resets
only, no in-flight scorecard reads, all environments scored whether touched or not.
Note `EnvironmentScoreList.score` returns `max(run.score for run in runs)` — best-run-wins —
which is presumably *why* competition mode caps you at one run.

**Target:** 1st place in Milestone 2 (deadline **2026-09-30 23:59 UTC**). Requires beating
**11.04**. Operator's stated target: **15**.

**Realism:** beating the leader by ~36% from a zero baseline in 16 days, against teams with
months of accumulated experiments and likely private fine-tuning. Both the author and the
independent audit rate this a very-low-probability stretch outcome. The operator has been
told this twice and has chosen to proceed. What follows is the best available attempt, not
a forecast.

---

## 2. STANDINGS [LIVE, unchanged 2026-09-13 → 09-14]

```
1  Tufa Labs           11.04
2  Ebi                  8.68
3  NVARC3               8.40
4  Third Intelligence   8.21
5  Daniel Franzen       7.63
6  mostik.ai            7.51
7  Mark Slavin          7.29
```

Public LB = 55 games; final standings use the other 55.

---

## 3. KEY MECHANICS [SRC]

**RESET costs an action, and the scoring counter never decreases.** `arc_agi/scorecard.py`:

```python
def inc_reset_count(self, guid):
    self.resets[idx] += 1
    self.actions[idx] += 1     # a RESET is charged as an action
```

Per-level tallies are differences of a monotonic cumulative counter (`set_levels_completed`
appends `(levels_completed, actions[index])`). **You cannot explore wastefully, reset, and
speedrun for a clean score.** Exploration cost is permanent.

*Trap:* `arcengine/base_game.py` does reset an internal `_action_count` to 0 on level reset.
That counter does not score you.

**Completion cap.** `max_score = max_weights / total_weights * 100`. Finishing 2 of 7 levels
caps that game at (1+2)/28 = 10.7%, however perfectly those two were played.

**5n action budget** [OPEN]. The ARC-AGI-3 technical report states agents are terminated
after 5× the human median action count per level. It is **not** enforced in the installed
package, and no Kaggle staff statement confirms it applies to hidden evaluation. A related
host clarification does confirm that no-op actions count and that offline competition mode
matches the scored server. **Plan as though actions are scarce regardless** — the squared
metric already makes waste expensive, and a hidden cap only sharpens that.

---

## 4. ARCHITECTURE

**Shape: sparse LLM controller + deterministic executor.** Not an LLM invoked per action,
not unguided search.

The LLM's irreplaceable contribution is *goal identification* — recognising what winning
looks like in a game nobody described. Search cannot do that. But once mechanics are
understood, deterministic code should own state differencing, object tracking, shortest
paths, safe replay, hypothesis ledgers, invariant-checked action queues, and scheduling.

Base: fork the Tufa Labs Duck harness — the open-sourced Milestone-1 winner — as a starting
point, not as the final architectural commitment.

### Components, in build order

| # | Component | Evidence | Risk |
|---|---|---|---|
| 1 | Exact tracing + local RHAE scoring + throughput profile | none needed — instrumentation | Low |
| 2 | Deterministic serving, legal-action guard, effect ledger, safe cache | [3P] "reproducible serving" cited by a competitor as what worked | Low |
| 3 | Adaptive scheduler over 110 games | [3P] shadow-mode estimate of **13.6% counterfactual action savings** — the only quantified harness result found, but unvalidated on RHAE or hidden score | Low |
| 4 | Win-path caching, keyed on state preconditions, invalidated on mismatch | [3P] a competitor found `solved_path` declared but never read/written | Low |
| 5 | Volatile-cell masking — **hashing only** | [3P] | Low |
| 6 | Sparse controller + short invariant-checked action queues | [3P] from Retrodict (online) | Medium |
| 7 | Retrodiction — falsify hypotheses against recorded history before spending actions | [3P] | Medium |
| 8 | BC / affordance prior, held out by *environment* | negative prior evidence | High — gated |

Caveats carried from the audit:
- Win-path caching prevents *re*-discovery; it cannot refund already-charged exploration.
- Volatile masking must affect the state hash only. **Do not hide timers, lives or counters
  from the model** — they may be causal.
- Retrodiction can falsify a hypothesis against history but cannot establish behaviour in
  unvisited states.
- Expected-frame queues should predict stable invariants or relevant cells, not demand
  pixel-perfect equality in animated games.
- Scheduling should maximise expected weighted score per remaining GPU-second, with a broad
  initial pass — not equal time per game.

---

## 5. THE MODEL QUESTION (open, highest-value early experiment)

96GB of VRAM expands the design space well beyond the 27–31B models in common use.

**For gpt-oss-120b:** 117B total / 5.1B active, ~60–61GB at MXFP4, fits one 96GB GPU with
room for KV cache. It is on Kaggle's attached model list.

**Against, and these are serious:**
1. The Models tab already associates gpt-oss-120b with a best public score of **0.24**,
   versus 4.33 for Qwen3.8 Flash Next NVFP4. Not a controlled comparison, but not nothing.
2. **gpt-oss-120b is text-only — image input unsupported.** Duck exposes both visual and
   textual grid representations.
3. Active-parameter count does not predict throughput.
4. Remaining VRAM after weights is not all usable for KV cache.

**Working hypothesis:** (1) and (2) are likely the same fact. Dropping a text-only model
into an image-dependent harness silently removes half its perception, and 0.24 is what that
would look like.

**Counter-evidence on capability:** Retrodict — the highest-scoring harness anywhere at
99.86% — is deliberately text-only. Its agent is never shown images after a single priming
call; everything arrives through `log.txt` plus a helper library giving parsed boards,
per-step diffs and connected components. Text perception is not a ceiling; it is what the
best-performing design chose.

**Consequence for the experiment:** benchmarking gpt-oss-120b inside *unmodified* Duck
would mostly re-measure the incompatibility. A fair read requires a text perception layer
first (component-parsed boards, diffs, centroids) — about a day of work. So the model
decision lands ~Day 3, and it is a gated fork, not a quick A/B.

**Gate:** if the text perception layer is not working by end of Day 2, the 120B experiment
does not run and we commit to Qwen 3.8.

### Day-1/3 A/B measurement spec

Measure both models under the *same* harness:

- cold-start and model-load time
- peak VRAM before and during generation
- prefill and decode throughput, separately
- latency and aggregate throughput at concurrency 1 / 4 / 8 / 16
- max stable context and concurrency before OOM
- generated reasoning tokens per action
- tool-call / Harmony parsing success rate
- valid-action and no-op frequency
- **level progress and RHAE per GPU-minute on a fixed game subset**

Decision metric: **expected weighted RHAE gained per GPU-second.** Raw tokens/sec is
insufficient — a larger model needing half as many calls can win despite lower throughput,
and a fast model that reasons verbosely or mishandles the Python protocol can lose badly.

---

## 6. SCHEDULE (16 days to 2026-09-30)

1. **Day 1** — Hardware verification notebook: `nvidia-smi`, GPU count, real VRAM, driver,
   vLLM version, token-generation timing. Running a notebook does **not** spend a submission.
   In parallel: unmodified Duck baseline end-to-end, **submitted the same day**.
2. **Days 2–3** — Text perception layer. Then the model A/B per §5. Commit to a model.
3. **Days 4–6** — Serving hardening, scheduler (component 3), win-path caching, volatile
   masking. Cheap, individually measurable.
4. **Days 7–10** — Sparse controller + invariant-checked queues on the winning serving stack.
5. **Days 11–12** — Retrodiction and conditional recovery, as measured ablations.
6. **Days 13–14** — BC / affordance-prior experiment, held out by environment. Kill fast if
   neutral against simple geometry/effect heuristics.
7. **Days 15–16** — Replicated multi-seed runs, packaging hardening, open-source the notebook
   under an OSI licence (**required by the deadline to qualify**), one considered submission
   per UTC day.

**Submission discipline:** 1/day. Spend one only on a change that has passed a replicated
local gate without a throughput regression.

**Interim targets, in order:** (a) valid 9-hour Kaggle run; (b) reproduce Duck unchanged;
(c) replicated local improvement with no throughput regression; (d) beat the 4.33 associated
with Flash Next; (e) only then chase 11–15.

---

## 7. WHAT IS STILL UNKNOWN

1. Whether Kaggle enforces the 5n per-level termination. Unresolved after a signed-in
   forum search. Plan as if actions are scarce either way.
2. What produced the jump from ~1.7 (late Aug) to ~11 (mid Sep). No public technique
   explains it. Best available inference: a mix of the Qwen 3.8 family, private
   fine-tuning, stronger teams and harness work — not one reusable public breakthrough.
3. Whether a text-only 120B, given proper text perception, is actually better at ARC-AGI-3
   than a 27B with images. This is the central open bet.

Reported by a participant as **not** working: manually created imitation data (underperformed
Qwen3.8, overfit individual games); five-role LLM systems (ran out of time).
Reported as working: reproducible serving, verified transition memory, single-step recovery,
conditional verifier roles, adaptive allocation.

---

## 8. SOURCES

### Official
- Competition: https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3
- Leaderboard / Rules / Models / Data / Discussion: append
  `/leaderboard`, `/rules`, `/models`, `/data`, `/discussion`
- Runtime clarification (6h → 9h): https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/discussion/697944
- Milestone deadline clarification: https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/discussion/713634
- No-op / action-counter clarification: https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/discussion/718638
- Score-jump discussion: https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/discussion/737617
- Technique / failure report: https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/discussion/739938
- Top-three discussion: https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/discussion/740812
- Duck harness thread: https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/discussion/717133
- Milestone 1 announcement: https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/discussion/725002
- ARC Prize 2026: https://arcprize.org/competitions/2026 · track: `/arc-agi-3`
- Milestone 1 results: https://arcprize.org/blog/arc-prize-2026-milestone-1
- Human performance dataset: https://arcprize.org/blog/arc-agi-3-human-dataset
- Technical report: https://arcprize.org/media/ARC_AGI_3_Technical_Report.pdf
- Google G4 spec: https://docs.cloud.google.com/compute/docs/accelerator-optimized-machines

### Docs (append `.md` for plain markdown)
- Index: https://docs.arcprize.org/llms.txt
- Methodology / actions / game-schema / competition mode / starter kit:
  https://docs.arcprize.org/methodology · `/actions` · `/game-schema` ·
  `/toolkit/competition_mode` · `/arc-prize-2026`

### Official code
- Starter kit: https://github.com/arcprize/ARC-AGI-3-Kaggle-Starter
- Agents framework: https://github.com/arcprize/ARC-AGI-3-Agents
- Engine: `pip install arc-agi` (0.9.9) → also installs `arcengine` (0.9.3)

### Kaggle-eligible competitor code
- Tufa Labs Duck: https://github.com/Tufalabs/duck-harness · https://tufalabs.ai/research/duck-harness/
- Duck notebook: https://www.kaggle.com/code/jeroencottaar/tufa-labs-duck-harness-june-30-milestone-winner
- Sahasawatt / Thuitanium (two lines + score ledger): https://github.com/Sahasawatt/arc-agi-3-agent
- samrishtt (Go-Explore, Forge v20): https://github.com/samrishtt/arc-agi-3-kaggle-competition
- AR6420 (behavioral cloning): https://github.com/AR6420/arc-agi-3-agent
- ssppsy: https://github.com/ssppsy/arc-agi-3
- CalamityChasm (JEPA): https://github.com/CalamityChasm/ARC-AGI-3-JEPAstyle_approach

### Online-model harnesses — NOT submittable; techniques only
| Harness | RHAE | Cost | Link |
|---|---:|---:|---|
| Tycho | 100.00% | $2,986 | https://github.com/NIMI-research/Tycho |
| Retrodict | 99.86% | $654 | https://github.com/ryanbbrown/Retrodict |
| Schema | 98.98% | $6,447+ | https://schema-harness.github.io/ |
| baseline1 | 98.97% | $2,722 | https://github.com/astroseger/arc-3-agents-baseline1 |
| PRO-LONG | 97.4% | $1,750 | https://github.com/alexisfox7/PRO-LONG |
| Prime Agent | 95.5% | ~$944 | https://github.com/PrimeIntellect-ai/prime-agent |
| NOOA (NVIDIA) | 85.13% | $332 | https://github.com/NVIDIA-NeMo/labs-OO-Agents |
| OPINE-World | 78.37% | $1,040 | https://github.com/david-courtis/opine-world |

Also: RGB-Agent https://github.com/alexisfox7/RGB-Agent ·
ThinHarness https://github.com/ryanbbrown/thinharness

### Papers
- ARC-AGI-3 technical report: https://arxiv.org/abs/2603.24621
- "Explore Before You Solve: The Speed-Depth Trade-off in Epistemic Agents for ARC-AGI-3":
  https://arxiv.org/pdf/2605.25931
- ARC Prize 2025 technical report: https://arxiv.org/abs/2601.10904
- gpt-oss-120b: https://developers.openai.com/api/docs/models/gpt-oss-120b

---

## 9. REPRODUCING THE SOURCE CHECKS

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python arc-agi
SP=.venv/lib/python3.12/site-packages

sed -n '160,210p' $SP/arc_agi/scorecard.py     # RHAE formula + completion cap
sed -n '693,726p' $SP/arc_agi/scorecard.py     # RESET charges an action; monotonic counter
grep -n "_action_count" $SP/arcengine/base_game.py            # the trap
grep -rnE "action_budget|max_actions|action_limit" $SP/arc_agi/ $SP/arcengine/   # no 5n client-side
```

Line numbers are for `arc-agi` 0.9.9; they differ in the GitHub `main` branch.

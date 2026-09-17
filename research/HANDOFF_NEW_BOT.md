# Handoff — ARC Prize 2026 / new Grok Bot

**Owner:** Anand Singh (`anandsingh8687` on GitHub & Kaggle)  
**Timezone:** Asia/Kolkata (IST)  
**Written:** 2026-09-18 ~04:45 IST  
**Purpose:** Start a **new** Grok Bot on **this same computer** and continue without re-collecting credentials.

---

## 0) First actions for the new bot (do in order)

1. Read this file fully, then `research/ACTIVE_GATES.md` and `research/GPU_HYGIENE.md` in the repo.
2. Confirm access (no user prompts if OK):
   - `/workspace/arc3/bin/with-kaggle.sh kaggle competitions list --page-size 1`
   - `/workspace/arc3/bin/with-github.sh gh auth status`
3. `cd /workspace/arc3/arc-prize-2026-arc-agi-3-agent && git fetch && git checkout psd/t0-portfolio-expect && git pull`
4. Resume the **next unfinished gate** in §5 (do **not** scored-submit without same-day human OK).

---

## 1) Access already on this computer (do NOT ask user to paste tokens)

Secrets live in `/home/box/agent-data/box-secrets.json` under `card.*` (never print values):

| Key | Use |
|---|---|
| `card.KAGGLE_API_TOKEN` | Kaggle CLI / kernels |
| `card.GITHUB_PERSONAL_ACCESS_TOKEN` | `gh` push/PR (classic, `repo` scope; short-lived — rotate if expired) |

Wrappers (prefer these):

```bash
/workspace/arc3/bin/with-kaggle.sh <cmd>
/workspace/arc3/bin/with-github.sh <cmd>
```

Kaggle venv: `/workspace/venv-kaggle` (on `PATH` via with-kaggle).

**If a brand-new bot runs on a different machine**, secrets will NOT follow — user must re-add via secure card. On **this** shared box, they should already work.

**Colab Pro ↔ Kaggle:** attempted; **not confirmed linked** as of handoff. Settings still showed `29:15 / 30 hrs` GPU. Linking needs user Google consent in browser (`File → Link to Colab`). Do not invent a second Kaggle account for quota.

---

## 2) Hard user rules (non-negotiable)

- **No scored Kaggle submission** without **explicit same-day** human approval.
- Drive **all intermediate** work autonomously; only ping when a **full / scored** run is ready.
- Prefer **API / CLI** over Chrome clicking.
- Anti-overfit: **do not** read public game implementations under `environment_files/`.
- Do **not** multi-account for GPU quota. Real teammate may run kernels on **their** account and share outputs (no shared logins).
- Competition stack is **CUDA/GPU** (Duck/Qwen/vLLM). **TPU is not a substitute.**

---

## 3) Goal & strategy snapshot

- Competition: **ARC Prize 2026 — ARC-AGI-3** (`arc-prize-2026-arc-agi-3`)
- Aim: rank improvement toward top; Milestone 2 ~**2026-09-30**, final ~**2026-11-02**
- Public LB when last checked: score **~2.37**, rank ~**650+**; leader ~**18–19**
- Bottleneck: **more late-weighted levels completed**, not tok/s micro-tweaks
- Architecture bet: **Portfolio Scientist Duck (PSD)** — keep Duck REPL; portfolio time allocation + JSONL traces; **default Qwen**; **GPT-OSS shelved** after T1 FAIL

---

## 4) Repo / PR / code

| Item | Value |
|---|---|
| Repo | https://github.com/anandsingh8687/arc-prize-2026-arc-agi-3-agent |
| Clone | `/workspace/arc3/arc-prize-2026-arc-agi-3-agent` |
| Branch | `psd/t0-portfolio-expect` (tracking origin) |
| PR | https://github.com/anandsingh8687/arc-prize-2026-arc-agi-3-agent/pull/1 — open |
| `main` | `e1f4563` (published ARC-only history) |

Key modules: `arc3/instrumentation.py`, `portfolio.py`, `portfolio_loop.py`, `qwen_portfolio.py`, `expect_queue.py`, `gptoss_guards.py`, `evaluate.py`  
Docs: `research/ACTIVE_GATES.md`, `research/GPU_HYGIENE.md`  
Notebooks: `notebooks/qwen-portfolio-smoke/`, `notebooks/qwen-portfolio-miniwave/` (+ `QUOTA_HOLD.md`)  
Local gate: `python scripts/qwen_portfolio_coverage_gate.py`  
Tests: `pytest tests/test_portfolio_loop.py tests/test_qwen_portfolio.py …` (helpers green)

Enable portfolio+trace:

```bash
python -m arc3.evaluate --agent random --games … \
  --portfolio-seconds 600 --trace /tmp/cov.jsonl
# or ARC3_TRACE=… ARC3_PORTFOLIO_SECONDS=…
```

Duck notebooks: `plan_for_qwen` → `apply_plan_game_to_solver`; after game `notify_session_end` / level notify **before** next apply. Expect-queue **not** on Qwen XML tool path.

---

## 5) Status & next work (priority order)

### Done
- T0 instrumentation, T3 portfolio, T4 expect helpers
- GPT-OSS T1 **FAIL** (v6): 0 gameplay actions; Harmony parser 500 — **OSS shelved**
- Qwen portfolio smoke v1 **PASS** (non-scored): kernel `anandsingh8687/arc3-qwen-portfolio-smoke-20260918`  
  - 354 actions, 1 level; abandon + reallocate evidence  
  - Outputs: `/workspace/arc3/kaggle-outputs/qwen-portfolio-smoke-v1/` (+ `GATE_VERDICT.md`)
- Live session-end notify + next-game apply fix pushed
- GPU hygiene docs pushed

### Blocked / pending
1. **GPU quota:** ~**0.75h** left of 30h; refresh **2026-09-19T00:00:00Z** = **05:30 IST**  
   Routine was set to queue mini-wave ~05:45 IST (folder `queue-qwen-mini-wave-after-gpu-quota`) — recreate on new bot if missing.
2. **Mini-wave** (6 games, `ARC3_PORTFOLIO_SECONDS≈5400`, `TRUE_SUBMISSION=False`) — prepared under `notebooks/qwen-portfolio-miniwave/`; **do not queue** until ≥~2–3h free.
3. After mini-wave PASS → full **25-game non-scored** dress rehearsal → only then ask human for scored submit.
4. Optional: finish **Colab Pro/Pro+ link** (user Google consent) for +15/+30h on same account.

### Side note (user asked)
Low-GPU cash comps near deadline: **Kaggriculture** (30 Sep, $50k, agent/CPU) or **ARC Paper Track** (9 Nov). Do not abandon ARC AGI-3 GPU path without explicit user redirect.

---

## 6) Kaggle kernels (user `anandsingh8687`)

| Kernel | Role |
|---|---|
| `arc3-qwen-portfolio-smoke-20260918` | PASS portfolio smoke |
| `arc3-gptoss-smoke-20260917` | ERROR / T1 fail trail |
| Many `*-smoke` / `*-screen` Sep 16–17 | Ablation farm (burned most of weekly GPU) |

Always: private/non-competition for experiments; `TRUE_SUBMISSION=False`.

---

## 7) Communication style

- Warm, concise; lead with result.
- No permission-asks for reversible intermediates.
- Never claim top-3 certainty; score = levels under 9h/1×GPU rules.

---

## 8) What the human does once

Create a new Grok Bot on **this** computer, send:

> Read `/workspace/arc3/HANDOFF_NEW_BOT.md` and the ARC repo `research/ACTIVE_GATES.md`. Continue from §5. Do not ask me to re-paste Kaggle/GitHub tokens unless the wrappers fail. No scored submit without my same-day OK.

Then archive or pause this chat if desired.

# Active promotion gates (PSD)

Working rules while chasing Milestone 2 / final. Scored Kaggle submits need **explicit human OK that UTC day**.

## North star

Increase **levels completed** (especially late-weighted) under 1×GPU / 9h / latency.
Efficiency-only gains that do not add levels are insufficient for a jump past ~18 public.

## Always-on instrumentation (T0)

Every run — local or Kaggle — must emit per-game JSONL with at least:
`game_id`, `wall_seconds`, `actions`, `levels_completed`, `level_indices_completed`,
`abandon_reason`, `tokens_in`, `tokens_out`, `llm_calls`.

Enable on the Qwen path:

* CLI: `python -m arc3.evaluate ... --trace /path/cov.jsonl --portfolio-seconds 7200`
* Env: `ARC3_TRACE=/path/cov.jsonl` and `ARC3_PORTFOLIO_SECONDS=7200`
* Duck notebooks: `arc3.qwen_portfolio.apply_plan_game_to_solver` + `record_duck_rows`

A run without coverage accounting cannot be used to argue for a scored submit.

## Gate ladder

| Gate | Question | Pass | Fail → |
|---|---|---|---|
| T0 | Do we know coverage & depth? | Trace summary present; untouched count known | Add recorder; no submit |
| T1 | Can GPT-OSS emit ≥1 real game action? | ≥1 valid tool/action in-game under ≥300s timeout | **FAIL v6 — OSS shelved; stay on Qwen** |
| T2 | OSS vs Qwen levels @ matched wall | OSS levels ≥ Qwen+2 on fixed 3-game set, no ≥1 level regress | Keep Qwen default (N/A while OSS shelved) |
| T3 | Portfolio beat sticky equal-time? | More total levels or more games off zero on 8-game / 120min | Revisit allocator |
| T4 | Expect-queue + log-check help? | +≥2 levels on 3–5 game panel | Drop aesthetic Retrodict copy |
| Promote | Full-25 local | Levels ≫ prior best (31/183 on scored twin) **and** T0 live | Keep iterating |
| Scored | Public LB | Human OK that day; 1/day budget | — |

## Current status (2026-09-18 IST)

* **T1 GPT-OSS: FAIL v6** — Harmony/tool-call path still produced 0 gameplay actions
  after ≥300s analyzer timeout. OSS path shelved.
* **Qwen portfolio smoke v1: PASS** — 354 actions, 1 level, abandon+reallocate recorded
  (`kaggle-outputs/qwen-portfolio-smoke-v1/`). Post-hoc notify caveat fixed in code:
  session-end notify + mid-session level-up bump before next apply.
* **Next gate: Qwen mini-wave** (non-scored, 5–8 games, `ARC3_PORTFOLIO_SECONDS≈3600–7200`).
  - Local (no GPU): `python scripts/qwen_portfolio_coverage_gate.py`
  - Downloaded artifact assert:
    `python scripts/qwen_portfolio_coverage_gate.py --artifacts /path/to/kaggle-outputs/...`
  - Tests: `pytest tests/test_portfolio_loop.py tests/test_qwen_portfolio.py -q`
  - Keep `TRUE_SUBMISSION=False`; never scored submit without human OK.

## Concurrency policy (portfolio)

* **`concurrency=1` is required for true portfolio sequential runs.**
  With `concurrency>1`, multiple games receive `PORTFOLIO_APPLY` before any
  session-end `notify`, so exploit/abandon reallocations cannot change the next
  game's live `max_runtime_s_per_game`.
* Small parallel waves (throughput screens) may use higher concurrency, but must
  **not** be treated as evidence for T3 portfolio allocator quality.
* Duck session hook contract: **apply → play → session-end notify → next apply**;
  mid-session `live_reallocate_if_level_up` may bump the *current* game's wall when
  a level clears before session end.

Expect-queue helpers remain available for non-Duck local agents; they are **not**
wired into the Qwen XML/tool loop (would break Duck tool plans).

## Non-goals this week

- Prompt micro-ablations without a level gate
- World-model ledger E2E before T3/T4
- Treating Retrodict 99 / Polyphony 19.8 as Kaggle targets
- Reading `environment_files/` implementations
- Retrying OSS until Harmony gameplay tool-calls are fixed offline

## Owner loop

Bot: implement + unit test + non-scored kernel when needed.
Human: approve scored submit; publish OSS notebook by Milestone 2 if prize-eligible.

## GPU quota note (2026-09-18 ~02:47 IST)

* Kaggle GPU: **0.74h remaining** / 30.00h (refreshAt **2026-09-19T00:00:00Z** = 05:30 IST).
* Mini-wave notebook prepared at `notebooks/qwen-portfolio-miniwave/` but **not queued**
  (needs ≥~2–3h). See `notebooks/qwen-portfolio-miniwave/QUOTA_HOLD.md`.

## GPU hygiene (always-on — save weekly hours)

Kaggle charges **wall-clock while the session has GPU enabled**, including boot, installs, and idle. Our Sep 16–18 burn was mostly repeated smoke+screen pairs + OSS retries + Qwen smoke — not a leak.

### Before every GPU kernel
1. Confirm remaining hours (Kaggle → Settings → Accelerators / quota). Need ≥ planned wall + 20% margin.
2. `TRUE_SUBMISSION=False` unless human OK that UTC day.
3. `concurrency=1` for portfolio allocator evidence.
4. Prefer **one** purposeful run over smoke+screen duplicates the same day.

### Session rules
- Do **not** leave interactive GPU notebooks idle; Save Version / Shut down when done.
- Keep installs short; prefer cached datasets/models already on the kernel.
- Cap smoke walls tightly (`ARC3_PORTFOLIO_SECONDS` matches intent: smoke ≤1200, mini-wave 3600–7200, full dress ≤ competition budget).
- Abort/requeue rather than babysit a hung GPU session overnight.

### Quota boost (legit, same account)
- Link **Google Colab Pro** (+~15h/week) or **Pro+** (+~30h/week) via Kaggle notebook **File → Link to Colab** (does not spend Colab compute units). Verify extra hours appear under Settings before relying on them.
- Teammate runs on **their** account + shared artifacts are fine; do not share logins.
- **TPU is not a substitute** for Duck/Qwen/vLLM CUDA gameplay.

### After each run
- Download outputs immediately; shut down GPU session.
- Log approx hours used in the gate verdict so the next run can budget.


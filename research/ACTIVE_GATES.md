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

## Current status (2026-10-05 ~00:55 IST)

* **T1 GPT-OSS: FAIL v6** — Harmony/tool-call path still produced 0 gameplay actions
  after ≥300s analyzer timeout. OSS path shelved.
* **Qwen portfolio smoke v1: PASS** — 354 actions, 1 level, abandon+reallocate recorded
  (`kaggle-outputs/qwen-portfolio-smoke-v1/`).
* **Qwen mini-wave 20260918: FAIL / CANCEL_ACKNOWLEDGED** — `CellTimeoutError` at
  1200s during cold vLLM load; no gameplay. Fixed by `-t 10800` + slug
  `...-20261004`.
* **Qwen mini-wave 20261004: PASS** — kernel
  `anandsingh8687/arc3-qwen-portfolio-miniwave-20261004` `COMPLETE`.
  Artifacts: `kaggle-outputs/arc3-qwen-portfolio-miniwave-20261004/` (+ `GATE_VERDICT.md`).
  - Framework score **3.84** (6 games) vs smoke **0.91** (2 games) / prior public ~**2.37**
  - **8** levels, **1227** actions, 6 touched, 1 zero-level (tn36 stuck L0)
  - Live reallocate on level-up (lf52/cn04/bp35→948s, wa30→900s); lp85 cleared **4**
    levels; abandon `time_budget_exhausted` on tn36/wa30/lp85
  - Log: `PORTFOLIO_MINIWAVE_OK` / `GATE1_SMOKE_OK`; non-scored only
* **Full 25-game non-scored dress rehearsal: FAIL / CANCEL_ACKNOWLEDGED (2026-10-05 ~00:55 IST)**
  - Kernel `anandsingh8687/arc3-qwen-portfolio-dress-20261004`
    (https://www.kaggle.com/code/anandsingh8687/arc3-qwen-portfolio-dress-20261004)
    pushed with `-t 30000 --accelerator NvidiaRtxPro6000`; notebook
    `notebooks/qwen-portfolio-dress-rehearsal/`.
  - **External cancel** mid-game 12 (`ar25`) after ~3.2h GPU / ~11425s notebook wall.
    Log has **no** `CellTimeoutError` (unlike mini-wave 20260918). Soft/hard deadlines
    were still ~4.4h away. No `PORTFOLIO_DRESS_OK`; coverage artifacts not flushed.
  - Partial (not a pass): **11** finished games, **20** levels, last framework mean
    print **3.86** / 25 slots; ~2330 actions. First-6 vs mini-wave: tn36 0→1, lp85 4→5
    (score 13.83→28.68); cn04 score regress. Artifacts + `GATE_VERDICT.md` in
    `kaggle-outputs/arc3-qwen-portfolio-dress-20261004/`.
  - Config reminder: 25 games, `concurrency=1`, `TRUE_SUBMISSION=False`,
    `ARC3_PORTFOLIO_SECONDS=22500` (~828s/game), hard guard 28800s.
  - **No auto GPU requeue** — standing order 2026-10-04 forbids Kaggle GPU until Anand
    explicitly allows. Cheap requeue (same `-t 30000`) only after that OK. Scored submit
    still needs **same-day Anand approval** after a real `PORTFOLIO_DRESS_OK`.

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

## GPU quota note (2026-10-05 ~00:55 IST)

* Kaggle GPU (CLI `kaggle quota`): **15.37h remaining** / 30.00h
  (refreshAt **2026-10-10T00:00:00Z** = 05:30 IST). Dress cancel burned ~3.19h on top of
  mini-wave (~1.9h).
* Dress 20261004 **FAIL / CANCEL_ACKNOWLEDGED** (incomplete). Standing GPU hold remains
  until Anand lifts it; do not requeue.
* See `research/QUOTA_HOLD.md`, dress `GATE_VERDICT.md`, and
  `notebooks/qwen-portfolio-miniwave/QUOTA_HOLD.md`.

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


## Dress rehearsal quota note (2026-10-04 ~18:00 IST)

* Before push: 18.56h GPU remaining. Dress kernel expected ~6.7h (max ~8.3h). Download outputs and log actual hours in a GATE_VERDICT.md after completion.

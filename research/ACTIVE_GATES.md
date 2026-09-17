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
* **Next gate: Qwen local portfolio coverage** (non-scored).
  - Local (no GPU): `python scripts/qwen_portfolio_coverage_gate.py`
  - Tests: `pytest tests/test_portfolio_loop.py tests/test_qwen_portfolio.py -q`
  - Next GPU: non-scored Qwen Gate-1/smoke with `ARC3_TRACE` + `ARC3_PORTFOLIO_SECONDS`;
    do **not** create a scored Kaggle submission.

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

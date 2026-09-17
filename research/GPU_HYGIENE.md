# Kaggle GPU hygiene (ARC-AGI-3)

## Why hours disappear
Accelerator quota is **per Kaggle account**, billed for **session wall time with GPU on** (boot + pip + idle + play). Team membership does **not** pool GPU.

## Colab Pro link (extra hours on THIS account)
1. Open any Kaggle notebook editor while logged in as the competition account.
2. **File → Link to Colab** (wording may vary slightly).
3. Complete Google consent for an active **Colab Pro** (+~15h/wk) or **Pro+** (+~30h/wk) subscription.
4. Confirm under **Account settings → Accelerators** that weekly GPU allowance increased.
5. Extra Kaggle hours do **not** consume Colab compute units (per Kaggle’s announcement).

If OAuth is required, a human must complete Google login — bots cannot finish that step alone.

## Run sizing cheat-sheet
| Intent | Portfolio seconds | Expect wall | Min free quota |
|---|---|---|---|
| Tiny debug | ≤300 | ~10–20 min | ≥0.5h |
| Smoke (2 games) | ~1200 | ~25–45 min | ≥1h |
| Mini-wave (5–8 games) | 3600–7200 | ~2–3h | ≥3h |
| Full-25 dress | up to ~9h race | ~6–9h | ≥10h |

## Do / don’t
- DO: concurrency=1 for portfolio; download then power off.
- DO: one experiment thesis per GPU session.
- DON’T: start mini-wave on &lt;2h remaining.
- DON’T: use TPU for this CUDA agent stack.
- DON’T: share Kaggle passwords across people — teammate runs their own kernel instead.

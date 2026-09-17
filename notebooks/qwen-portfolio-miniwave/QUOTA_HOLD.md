# Mini-wave hold — GPU quota

Prepared from `qwen-portfolio-smoke` with:
- `GATE1_SMOKE_GAME_COUNT=6`
- `ARC3_PORTFOLIO_SECONDS=5400`
- `GATE1_SMOKE_GAME_SECONDS=900`
- `concurrency=1`
- `TRUE_SUBMISSION=False`

## Status
**Not queued** while free GPU &lt; ~2–3h.

Last check: **~0.74h** remaining; weekly refresh **2026-09-19T00:00:00Z** (05:30 IST).

## Unblock options (same account)
1. **Link Colab Pro/Pro+** in a Kaggle notebook: File → Link to Colab → confirm Settings shows +15h/+30h.
2. Wait for weekly refresh, then push (below).
3. Teammate runs this folder on **their** account and shares `/kaggle/working` outputs.

See `research/GPU_HYGIENE.md`.

## Push when quota allows (≥~3h free)
```bash
/workspace/arc3/bin/with-kaggle.sh kaggle kernels push -p notebooks/qwen-portfolio-miniwave -t 1200 --accelerator NvidiaRtxPro6000
```

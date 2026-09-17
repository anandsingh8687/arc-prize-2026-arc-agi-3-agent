# Mini-wave hold — GPU quota

Prepared from `qwen-portfolio-smoke` with:
- `GATE1_SMOKE_GAME_COUNT=6`
- `ARC3_PORTFOLIO_SECONDS=5400`
- `GATE1_SMOKE_GAME_SECONDS=900`
- `concurrency=1`
- `TRUE_SUBMISSION=False`

**Not queued** at prepare time: Kaggle GPU remaining was **0.74h**
(refreshAt 2026-09-19T00:00:00Z / 2026-09-19 05:30 IST). Need ≥~2–3h free.

Push when quota allows:
```bash
/workspace/arc3/bin/with-kaggle.sh kaggle kernels push -p notebooks/qwen-portfolio-miniwave -t 1200 --accelerator NvidiaRtxPro6000
```

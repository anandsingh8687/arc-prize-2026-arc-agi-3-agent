# Mini-wave hold — GPU quota / timeout

Prepared from `qwen-portfolio-smoke` with:
- `GATE1_SMOKE_GAME_COUNT=6`
- `ARC3_PORTFOLIO_SECONDS=5400`
- `GATE1_SMOKE_GAME_SECONDS=900`
- `concurrency=1`
- `TRUE_SUBMISSION=False`

## Status (2026-10-04 IST)

**Kernel `anandsingh8687/arc3-qwen-portfolio-miniwave-20260918` → `CANCEL_ACKNOWLEDGED`.**

- Logs under `/workspace/arc3/kaggle-outputs/miniwave-20260918/` (vLLM timestamps `10-04` ~03:56–04:13Z ≈ 09:26–09:43 IST).
- Root cause: papermill/nbclient `CellTimeoutError` after **1200s** on the vLLM setup cell (cell that runs `setup_commands.json`). Cold Qwen3.8-Flash-Next load was still in progress: model shards done, **PLE-offload ~205/206 (~100%)** when the cell was killed. `VLLM_WAIT` reached `elapsed_s=1020`. No gameplay; no levels/coverage; **not comparable to 2.37 smoke baseline**.
- Cause of 1200s: prior push used `kaggle kernels push ... -t 1200` (smoke-sized per-cell timeout). Smoke vLLM ready in ~465s wait; this cold load needed ~15–20+ min.

## Fix

Use a **per-cell** timeout large enough for cold vLLM load **and** the long portfolio cell (`ARC3_PORTFOLIO_SECONDS=5400`, notebook limit 7200):

```bash
# From repo root, non-scored only:
/workspace/arc3/bin/with-kaggle.sh kaggle kernels push \
  -p notebooks/qwen-portfolio-miniwave \
  -t 10800 \
  --accelerator NvidiaRtxPro6000
```

Do **not** use `-t 1200` for mini-wave (that value is smoke-only).

Prefer new dated slug when re-pushing after cancel (see `kernel-metadata.json`).

## Quota

Check before push:

```bash
/workspace/arc3/bin/with-kaggle.sh kaggle quota
```

Need ≥~3h free (load + 5400s portfolio + margin). Weekly refresh shown in `kaggle quota` `refreshAt`.

Unblock if low: Colab Pro/Pro+ link, wait for refresh, or teammate non-scored run + shared outputs. See `research/GPU_HYGIENE.md` and `research/QUOTA_HOLD.md`.

## After a good mini-wave

Full 25-game **non-scored** dress rehearsal next. Scored submit still needs **same-day Anand approval**.

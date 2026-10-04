# Quota / mini-wave hold (ARC Qwen portfolio)

Canonical mini-wave push notes also live in
`notebooks/qwen-portfolio-miniwave/QUOTA_HOLD.md`.

## 2026-10-04 — mini-wave CANCEL_ACKNOWLEDGED

| Field | Value |
|---|---|
| Kernel | `anandsingh8687/arc3-qwen-portfolio-miniwave-20260918` |
| Status | `KernelWorkerStatus.CANCEL_ACKNOWLEDGED` |
| Logs | `/workspace/arc3/kaggle-outputs/miniwave-20260918/` |
| Wall clock (vLLM log) | `10-04` ~03:56–04:13Z (≈09:26–09:43 IST) |
| Gameplay / levels / coverage | **None** (died in setup) |
| vs 2.37 smoke baseline | **N/A** (no comparable metrics) |

### Root cause

`nbclient.exceptions.CellTimeoutError` after **1200 seconds** while the setup cell was still loading Qwen3.8-Flash-Next via vLLM (model load ~755s+; PLE-offload shards ~100% / 205 of 206 when timeout fired). `VLLM_WAIT elapsed_s` reached **1020**. Stack: papermill → nbclient `_async_handle_timeout`.

The push used **`-t 1200`**, which Kaggle applies as the papermill **per-cell** execution timeout. That matches smoke (vLLM ready in ~465s wait) but is too tight for a cold mini-wave load, and would also be too tight for the ~5400s portfolio cell.

### Fix applied

- Documented + corrected push timeout to **`-t 10800`** (3h per-cell) in
  `notebooks/qwen-portfolio-miniwave/QUOTA_HOLD.md`.
- Retarget kernel slug to `arc3-qwen-portfolio-miniwave-20261004` for a clean non-scored requeue after cancel.
- No gameplay logic changes.

### Requeue / quota

At fix time, `kaggle quota` showed GPU **20.43h remaining** / 30.00h (`refreshAt 2026-10-10T00:00:00Z`).

**Requeued (non-scored):** `anandsingh8687/arc3-qwen-portfolio-miniwave-20261004` via
`kaggle kernels push -p notebooks/qwen-portfolio-miniwave -t 10800 --accelerator NvidiaRtxPro6000`.
Initial status: `KernelWorkerStatus.QUEUED` (version 1). **No scored submit.**

### Next step after a successful mini-wave

1. Full **25-game non-scored** dress rehearsal.
2. Scored public submit only with **same-day Anand approval**.

## 2026-10-04 — mini-wave 20261004 COMPLETE / PASS

| Field | Value |
|---|---|
| Kernel | `anandsingh8687/arc3-qwen-portfolio-miniwave-20261004` |
| Status | `KernelWorkerStatus.COMPLETE` |
| Logs / artifacts | `/workspace/arc3/kaggle-outputs/arc3-qwen-portfolio-miniwave-20261004/` |
| Verdict | **PASS** — see `GATE_VERDICT.md` in that folder |
| Framework score | **3.84** (6 games) vs smoke 0.91 (2 games) / prior public ~**2.37** |
| Levels / actions | **8** levels, **1227** actions; 6 touched, 1 zero-level (tn36) |
| Portfolio | live reallocate on level-up; abandon on time_budget for tn36/wa30/lp85 |
| GPU after | **18.56h** remaining / 30h (`refreshAt` 2026-10-10T00:00:00Z) |

### Next step

1. Full **25-game non-scored** dress rehearsal.
2. Scored public submit only with **same-day Anand approval**.


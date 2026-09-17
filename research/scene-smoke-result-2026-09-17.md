# Complete-scene smoke — PASS

Private Kaggle notebook: https://www.kaggle.com/code/anandsingh8687/arc3-scene-smoke-20260917, Version 1. Source `eedc1e4`. Kaggle CLI status COMPLETE, checked 2026-09-17 14:18 UTC; terminal artifacts downloaded to `/tmp/arc3-scene-smoke.Fe0dVPX7`.

`SCENE_SMOKE_OK`, `SCENE_DELIVERY_ERRORS []`, `SCENE_SCREEN_FINAL clean=true`. Lifecycle: benchmark_ok=true, teardown_ok=true, hard_guard_triggered=false, post_teardown_gpu_rows=[], completed_trials=[W,C,T]. The first teardown command returned 0; no recovery exception this run. Startup seconds: 574.4088954925537. Benchmark plus teardown seconds: 183.55407764699976.

| Arm | Actions | Calls | Generated tokens | Trial wall seconds | Scene observations / delivered | Image / text-only messages |
|---|---:|---:|---:|---:|---:|---:|
| W | 10 | 8 | 5417 | 60.25431923899987 | 0 / 0 | 5 / 0 |
| C | 15 | 7 | 7141 | 60.26274397099996 | 6 / 6 | 6 / 0 |
| T | 15 | 7 | 6528 | 60.248519665 | 5 / 5 | 0 / 5 |

All arms ran cd82 for a 60-second game window and completed zero levels. This validates integration only; the action and token differences do not establish a capability gain. Provider calls can outnumber outer-turn observations because the tool agent makes multiple requests within a turn.

An independent local check reloaded every game row, asserted positive actions and terminal rows, checked every per-turn delivery equality, verified lifecycle and the success marker, and confirmed that the downloaded `scene.py` and `duck_scene_adapter.py` match local source byte-for-byte. Lifecycle SHA256: `20e953798f3c44c9edf5a46d185ae3e23c534f937e5dc549dc170a546e499de8`.

Fresh GPU allowance 2.76h, sufficient for the frozen approximately 50-minute W/C/T/W-repeat screen. Recent prior screens are COMPLETE. The prepared screen was dispatched once; no competition submission. Verified competition score remains 2.37.

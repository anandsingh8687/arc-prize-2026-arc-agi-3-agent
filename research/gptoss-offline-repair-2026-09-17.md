# One bounded repair after GPT-OSS smoke Version 1

Current gate: repair the observed offline vocabulary failure, then permit at most the one remaining private lifecycle retry. This is not score optimization or permission for a capability benchmark/submission.

## Reproduction and CPU evidence

With `openai-harmony==0.0.8`, an empty `TIKTOKEN_RS_CACHE_DIR`, and macOS `sandbox-exec -p '(version 1)(allow default)(deny network*)'`, loading `HARMONY_GPT_OSS` exits 1 with the same HarmonyError as Kaggle Version 1. Supplying the exact official `o200k_base.tiktoken` asset makes the same library load and render with OS networking still denied.

The final local test used the notebook builder's actual embedded asset and the integrated runtime's `_prepare_harmony_cache` and `_run_harmony_preflight`, not a mock or separately written loader:

```json
{"os_network_denied":true,"runtime_preflight":{"phase":"passed","timeout_seconds":19.999998957995558,"harmony_version":"0.0.8","token_count":62}}
```

Official source contract: https://github.com/openai/harmony/blob/main/src/tiktoken_ext/public_encodings.rs . Both O200kBase and O200kHarmony use `o200k_base.tiktoken`; no separate Harmony vocabulary is needed. Official API-format verification guidance: https://developers.openai.com/cookbook/articles/gpt-oss/verifying-implementations . These sources establish packaging/format requirements, not ARC ability.

## Scope

- Notebook reads the private offline input asset; validates 3,613,922 raw bytes and SHA256 `446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d`. See the delivery correction below; embedding was rejected before execution.
- Runtime independently validates it and sets Rust's tokenizer cache, removing an inherited lookup override.
- CPU preflight runs in the actual extracted runtime environment, before launching vLLM, for at most 20 seconds or the remaining startup budget. It records the remote installed Harmony version rather than assuming it equals the local version.
- Startup provenance is written before model process launch. Warmup requests are written before HTTP; errors and shutdown evidence survive failed startup.
- No changes to model, prompt, sampling, game, action cap, 60-second game window, shutdown policy or 1,200-second external run bound.

Integrated validation: **179 tests passed**, excluding only unchanged `tests/test_scoring.py` because local `arc_agi` is unavailable; all 9 notebook code cells parse, 1 markdown cell resolves, diff check passes. Transport is unchanged.

Routing: current selected lead handles integration/packaging; Luna read-only dependency trace; Terra-medium runtime implementation in the existing clean isolated worktree; Terra-high finding-delta review. No Sol escalation or paid compute. Runtime implementation `dabc846` integrated as `d8c4e80`; vocabulary packaging `5706c09`.

Fresh Kaggle UI allowance at approximately 17:45 UTC: **Quota: 28:10 / 30 hrs**, with draft session **off**. That display implies 1 hour 50 minutes remaining at its minute resolution. No Colab Pro connection, purchase, new permissions or draft session start was performed.

## Decision after the retry

If lifecycle fails again, stop this GPU route and preserve the evidence; no third blind retry. If it passes, first freeze a short controlled model-capability protocol under the remaining quota. Advance only on a substantial, replicated completed-level improvement, then test transfer before any full benchmark. The user's full-public-score-above-10 condition remains required before a scored long run, but a local score is not a guarantee of the Kaggle score.

The current 2.37 competition result has not changed. We do not yet have evidence for 10+, top three, or an additive combination of previous Qwen treatments.

## Delivery correction before the remaining GPU retry

Kaggle rejected the embedded-source upload with HTTP 400:

```json
{"error":{"code":400,"message":"The kernel source must be less than 1 megabytes in size.","status":"INVALID_ARGUMENT"}}
```

The UI still showed only failed Version 1; these rejected uploads did not launch a GPU run. The official vocabulary was moved to a new **private** input, `anandsingh8687/arc3-harmony-vocab-20260917`, version 1. `kaggle datasets status` reports ready. The server expands gzip on upload: its file list contains raw `o200k_base.tiktoken` (3,613,922 bytes), not `.gz`. The loader accepts the raw mount or compressed form, verifying the same raw size and SHA256 in both cases. A missing/wrong asset fails before vLLM startup. Notebook generation now also rejects source >=1,000,000 bytes.

The actual dataset was downloaded again and passed the actual generated bootstrap plus runtime CPU preflight under OS-level network denial:

```json
{"source":"downloaded private Kaggle dataset v1","os_network_denied":true,"bytes":3613922,"sha256":"446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d","preflight":{"phase":"passed","harmony_version":"0.0.8","token_count":62}}
```

Six delivery tests cover raw and gzip roundtrips, missing/corrupt input, size limit, and exact smoke wiring. This delivery correction does not reset the GPU retry budget: only the same one remaining private 1,200-second smoke is allowed. No model, prompt, sampling, game, runtime flags, or teardown code changed.

## Launch checkpoint

At approximately 17:53 UTC, Kaggle SaveKernel accepted **Version 2**, kernel ID `134757429`, source commit `0be4b3a`, with no invalid dataset/model/competition inputs. Fresh `kernels status` returned `KernelWorkerStatus.RUNNING`. Private notebook: https://www.kaggle.com/code/anandsingh8687/arc3-gptoss-smoke-20260917 . External timeout: 1,200 seconds; GPU: `NvidiaRtxPro6000`; internet disabled. Final integrated CPU suite: **182 passed**, same unchanged scorer exclusion as above. Delta review resolved raw-mount finding `GPTOSS-BUILD-004`; no current-gate findings remained.

The existing heartbeat `arc-agi-3-recovery-screen-follow-up` was reactivated at five-minute intervals for **Version 2 only**. It must download and report terminal evidence, then pause; it cannot launch a third retry or a capability run. This is execution underway, not a lifecycle pass or a score result. Next gate, conditional on a pass: freeze an equal-budget, same-games/seeds model-capability comparison and evaluate additional completed levels. No additive score forecast from rejected Qwen interventions.

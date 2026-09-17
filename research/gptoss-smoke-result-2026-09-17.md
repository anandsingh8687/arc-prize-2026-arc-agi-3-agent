# GPT-OSS smoke Version 1 — failed before gameplay

**Lifecycle FAIL; capability NOT TESTED; teardown PASS.** The competition score remains **2.37**. No competition submission or additional GPU run was launched by this monitor.

Kaggle notebook: https://www.kaggle.com/code/anandsingh8687/arc3-gptoss-smoke-20260917 (Version 1).
Uploaded source: `e454e36`. Terminal CLI status observed 2026-09-17 after the 17:12 UTC heartbeat: `KernelWorkerStatus.ERROR`.

## Exact observations

| Measurement | Saved output |
|---|---|
| vLLM | `0.1.dev20073+g8e685d198` |
| Actual model | `/kaggle/input/models/danielhanchen/gpt-oss-120b/transformers/default/1` |
| Architecture / quantization | `GptOssForCausalLM` / `gpt_oss_mxfp4` |
| MoE backend | `MARLIN`, `MarlinExperts` |
| Context / sequences / utilization | `32768` / `16` / `0.9` |
| Prefix caching / eager / tool parser | `True` / `True` / `openai` |
| Weight load | `87.11 seconds` |
| Model loading, including post-load processing | `66.14 GiB memory and 89.401882 seconds` |
| Available KV cache memory | `18.22 GiB` |
| GPU KV cache | `352,715 tokens` |
| Reported maximum concurrency at 32,768 tokens/request | `10.76x` |
| Unrounded concurrency in metrics / GPU blocks | `10.7640376501136` / `33164` |
| Engine initialization | `22.72 s` |
| HTTP server starting | `17:10:55` UTC; subsequently `Application startup complete.` |
| Notebook exception log timestamp | `339.787839478` seconds, first PapermillExecutionError line |
| Last notebook/export log timestamp | `343.166805307` seconds |
| Game trial / actions / levels | Not started / not measured / not measured |
| Server prompt tokens / generation tokens | `0.0` / `0.0` |

Printed memory and timing values above retain the precision of the source. Model-loading memory is **not** a separate `torch.cuda.max_memory_allocated()` measurement. Notebook log timestamps are not a separately exposed Kaggle billed runtime. No explicit process exit number was provided; the authoritative terminal status is ERROR.

## Blocking error

The HTTP server reached model readiness, then the first fixed native-function warmup request failed before token generation. The stack reaches `openai_harmony.load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)` while rendering the request:

```text
openai_harmony.HarmonyError: error downloading or loading vocab file: failed to download or load vocab file
RuntimeError: HTTP request failed for http://127.0.0.1:1234/v1/chat/completions: HTTP Error 500: Internal Server Error
```

This is an offline Harmony vocabulary loading failure. It does not show an inability to reason, use tools after a valid request, solve `r11l`, or improve ARC score. The native request never reached successful generation.

There are also **1,843** allocator OOM warnings during model-load processing. Exact repeated message:

```text
memory allocation failed with OOM on device 0 while trying to allocate 20971520 bytes (free: 18612224, total: 101973950464).
```

They did not terminate initialization: the subsequent log records model load, KV allocation, engine initialization and HTTP startup. They remain a memory-risk observation; do not erase them or label the eventual failure an OOM. The actual terminal exception is Harmony vocabulary loading.

## Shutdown and missing artifacts

Saved `gptoss-server-teardown.json`:

```json
{
  "cpu_survivors": [],
  "errors": [],
  "gpu_query_ok": true,
  "metrics_preserved": true,
  "owned_gpu_rows_after": [],
  "pid": 146,
  "post_gpu_rows": [],
  "shutdown_ok": true,
  "start_ticks": 104193
}
```

Identity file remained `phase: starting`, `server_ready_epoch: null`, correctly withholding game readiness until native tools worked. Because failure occurred before the first warmup response, `gptoss-tool-smoke.json`, `gptoss-runtime-provenance.json`, `gptoss-smoke-final.json` and per-game request/result files were **not produced**. Therefore no full post-readiness provenance or game-level request evidence exists. The model/runtime identity is supported by the launch identity and server log, not by a missing final manifest.

The underlying server force-killed the remaining EngineCore during shutdown and emitted a leaked-semaphore warning. The saved fresh process checks still report no surviving owned CPU/GPU processes. Read-only Luna evidence review independently confirmed the model, memory, KV, OOM-warning count, pre-game error and clean process tables. Endpoint readiness is not the same as this harness's stronger native-tool readiness gate.

## Evidence and continuation

All downloaded outputs: `/tmp/arc3-gptoss-smoke-v1.tmsgjbjk`. The five relevant raw files are archived in `research/artifacts/gptoss-smoke-v1/runtime-evidence.tar.gz`. Raw SHA256 values:

```text
823a6942d463d4dd0ebe090459e53b7f6e620c16e958ba41b6a2c248ab1eb736  arc3-gptoss-smoke-20260917.log
0b93e00f440190b20fccddcc93b503ffe4db27d7e0c28c09b16b41fd77b117ac  gptoss-vllm.log
6d85831d3fe38d24faf6546af43a2565a9d20d91ec200f6ca1ed036a82b98a88  gptoss-server-identity.json
e6e54617e58d0602caebe5130f6915e2528b5da732dfa7200067363232012b0c  gptoss-server-teardown.json
e267f856602bef659388ecba11b3ce8d46cc8331662f8c9ff183bfbbc0a54862  gptoss-vllm-metrics-final.prom
```

The existing heartbeat was **PAUSED** on terminal outcome. No replacement schedule was created. Post-run GPU quota was not remeasured; do not subtract notebook log seconds from the previously observed balance as though that were an authoritative quota reading.

The one permitted bounded repair should package the vocabulary required by this exact Harmony version and prove CPU-only, network-disabled request rendering before another GPU launch. Also persist startup provenance and the warmup request/error before sending it, so a startup failure has a final failure artifact. No model/prompt/hyperparameter sweep is indicated by this error. A retry needs separate exact-code validation/review and a launch decision; this monitor does not authorize or start it.

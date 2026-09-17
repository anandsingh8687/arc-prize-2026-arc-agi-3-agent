# GPT-OSS smoke Version 2 — terminal failure; GPU route stopped

## Identity and verdict

- Notebook: https://www.kaggle.com/code/anandsingh8687/arc3-gptoss-smoke-20260917
- Latest authenticated SDK metadata explicitly returned `currentVersionNumber: 2`, kernel ID `134757429`, private true, internet false, GPU `NvidiaRtxPro6000`, the expected GPT-OSS model and new vocabulary input.
- Source commit: `0be4b3a`; private vocabulary dataset version 1. Launch accepted at approximately 17:53 UTC; terminal check 17:59 UTC on 2026-09-17.
- Fresh status: `KernelWorkerStatus.ERROR`. Exact numeric notebook process exit code is not exposed in the downloaded artifacts; do not invent one.
- **Lifecycle failed before gameplay. Capability unmeasured. Competition score remains 2.37.**
- This consumes the one failed smoke plus one repair/retry allowance. No third GPU retry, capability benchmark, long run or submission was started. The existing five-minute heartbeat is now **PAUSED**.

## Exact measurements

| Measurement | Saved value |
|---|---:|
| Runtime extraction seconds | 120.27881146600004 |
| Harmony CPU preflight | passed |
| Remote Harmony version | 0.0.8 |
| Preflight rendered tokens | 62 |
| Weights loading seconds (server log precision) | 66.27 |
| Model loading seconds | 68.484402 |
| Model memory GiB (server log precision) | 66.14 |
| Available KV GiB (server log precision) | 18.22 |
| KV cache tokens | 352715 |
| Engine initialization seconds (server log precision) | 22.75 |
| Engine warmup request prompt tokens | 131.0 |
| Engine warmup generated tokens | 35.0 |
| Engine warmup TTFT seconds | 0.5202581882476807 |
| Engine warmup request latency seconds | 1.0227577686309814 |
| Engine warmup decode seconds | 0.5027339199999687 |
| Notebook exception elapsed seconds | 280.95007599 |
| Last notebook-log elapsed seconds, including export | 284.098609427 |
| Game trials started | 0 |
| Game actions / completed levels | 0 / 0 — no trial ran |

Full startup-to-game-ready time is **unavailable**, not 68.484402 seconds: the readiness contract never passed. Server identity retained `phase: starting`, `server_ready_epoch: null`. HTTP application startup completed, but the required native tool call did not. The engine's `request_success_total{finished_reason="stop"}=1.0` refers to token generation, not successful HTTP/tool parsing.

## Failure

The first synthetic readiness request asked `submit_number(value=4)`, with `tool_choice="required"`, temperature 0.0, low reasoning, max_tokens 512. It generated tokens but failed while parsing the response:

```text
.../vllm/entrypoints/openai/chat_completion/serving.py:946
    reasoning, content, tool_calls = parser.parse(...)
.../vllm/parser/harmony.py:191
    result = self.process_chunk(model_output_token_ids)
.../vllm/parser/harmony.py:338
    self._harmony_parser.process(token_id)
openai_harmony.HarmonyError: Unexpected token 200002 while expecting start token 200006
```

The client received:

```text
RuntimeError: HTTP request failed for http://127.0.0.1:1234/v1/chat/completions: HTTP Error 500: Internal Server Error
```

One native tool HTTP request failed; no second request, valid tool response, or ARC action occurred. The exact generated token sequence was not preserved, so the artifact does not establish whether the underlying cause is model output, tokenizer/template alignment, parser behavior, or their interaction. Do not label this a model-capability failure.

The previous missing-vocabulary defect **was fixed on Kaggle**, not merely locally: the runtime validated 3,613,922 bytes and SHA256 `446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d`, and Harmony preflight passed. Allocator warnings during loading were nonterminal: model initialization and generation subsequently completed.

## Persistence and teardown

Saved files include `gptoss-harmony-preflight.json`, `gptoss-runtime-provenance.json`, `gptoss-server-identity.json`, `gptoss-tool-smoke.json` (request plus failure), `gptoss-startup-failure.json`, `gptoss-server-teardown.json`, `gptoss-vllm-metrics-final.prom`, `gptoss-vllm.log`, and the notebook log. There is no `gptoss-smoke-final.json`, gameplay request/response audit, or per-game result: failure occurred in startup before the game cell.

Final teardown evidence:

```json
{"shutdown_ok":true,"metrics_preserved":true,"gpu_query_ok":true,"post_gpu_rows":[],"owned_gpu_rows_after":[],"cpu_survivors":[],"errors":[]}
```

Root PID 147 and EngineCore PID 661 were terminated; saved fresh post-drain tables were empty. This is evidence from run shutdown, not a claim of an additional live GPU inspection after the session ended.

Raw download: `/tmp/arc3-gptoss-smoke-v2.DjbNBYEV`. Durable archive: `research/artifacts/gptoss-smoke-v2/runtime-evidence.tar.gz`, SHA256 `e9ddd809830f8c1a14af6ef06851de67ea36ac3b54ef9228ac5631787b8343d7`.

## Decision and continuation boundary

**STOPPED**, not promoted. This smoke supplies no evidence of deeper ARC solving, score >10, or rank improvement. Any renewed attempt needs a separately frozen CPU reproduction of the exact serving/parser failure, an explicit launch decision and a new bounded budget. Changing flags and launching again is not authorized by this monitor. No scorer or agent implementation was changed during inspection.

Execution: current selected lead inspected terminal artifacts and archived evidence; one Luna explorer independently checked the failure/readiness distinction and teardown. No implementation worker, escalation, new worktree, or GPU run in this monitoring turn.

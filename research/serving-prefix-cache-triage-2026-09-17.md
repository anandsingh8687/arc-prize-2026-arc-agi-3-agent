# Prefix-cache triage (2026-09-17)

This is a **candidate**, not a score improvement. The scored leaderboard result
remains 2.37. Do not change the running repeat-only recovery screen or infer a
promotion from these aggregate server counters.

## Exact observed counters

Source: saved `../run-artifacts/recovery-screen-v1/vllm-metrics-final.prom`,
the September 16 three-arm screen using the exact Qwen3.8-Flash-Next-NVFP4
checkpoint. Its notebook sets `TAAF_VLLM_ENABLE_PREFIX_CACHING=0`.

| Counter | Value |
|---|---:|
| `vllm:prefix_cache_queries_total` | 0 |
| `vllm:prefix_cache_hits_total` | 0 |
| `vllm:prompt_tokens_total` | 10120814 |
| `vllm:generation_tokens_total` | 621994 |
| `vllm:request_prefill_time_seconds_count` | 505 |
| `vllm:request_prefill_time_seconds_sum` | 812.6770469390044 |
| `vllm:request_decode_time_seconds_count` | 505 |
| `vllm:request_decode_time_seconds_sum` | 6777.191056843993 |
| `vllm:time_to_first_token_seconds_count` | 510 |
| `vllm:time_to_first_token_seconds_sum` | 864.4649810791016 |

Prompt tokens are 16.271562105100692 times generated tokens, so there is substantial
prefill traffic. Yet the sum of per-request prefill phase time is 10.70739353868276%
of the sum of prefill-plus-decode phase times. **These are per-request phase
times under concurrency, not disjoint GPU wall seconds.** They do not tell us
that caching saves 10.70739353868276% of the run, nor that it is worthless. We need an
on/off measurement on the exact checkpoint and real agent prompts. The older
synthetic shared-prefix probe is not transferable as an effect-size estimate.

## Next experiment if the recovery screen does not promote

One shared server cannot switch prefix caching dynamically, so this has a
startup cost for each arm. Before booking GPU, extract the exact common prefix
length from **real request messages**, without reading game implementation
files. Then run a matched short test with cache on/off, same checkpoint,
concurrency, seeds, game order, and request transcript. Record cache hit rate,
prefill GPU time, TTFT, generated tokens/sec, actions/sec, and completed levels.
Only a material improvement in levels or weighted RHAE per GPU second should
promote it. A high cache-hit rate by itself is not a score result.

This is a secondary systems lever. The primary deficiency is still cleared
level depth; no serving counter currently establishes a path from 2.37 to 10+.

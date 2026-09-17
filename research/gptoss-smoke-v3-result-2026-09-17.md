# GPT-OSS V3: tool protocol passes; first game decision times out

## Identity and verdict

- [Private notebook](https://www.kaggle.com/code/anandsingh8687/arc3-gptoss-smoke-20260917),
  version **3**, source `9f60ae802bc0438d74843e27d2b96d20c9a6a603`.
- Authenticated metadata returned currentVersionNumber 3 and the expected model,
  runtime inputs, private status, internet disabled and NvidiaRtxPro6000 machine.
- Fresh terminal status at 2026-09-17 18:27 UTC: `KernelWorkerStatus.ERROR`.
- **Native tool roundtrip passed. Gameplay smoke failed. Teardown passed.**
- No competition submission; verified competition score remains **2.37**.
- No numeric notebook process exit code is exposed; do not substitute the local
  log-stream client's exit code or invent one.

## Exact saved measurements

| Measurement | Value |
|---|---:|
| Runtime extraction seconds | 128.577301214 |
| Startup to complete readiness seconds | 306.5444188117981 |
| First readiness completion tokens | 41 |
| Second readiness completion tokens | 5 |
| All engine generated tokens | 4071 |
| Inferred game-request generated tokens | 4025 |
| Game HTTP requests / returned responses | 1 / 0 |
| Client-counted game generated tokens | 0 |
| Game actions / completed levels | 0 / 0 |
| Client request read-timeout seconds | 59.799306 |
| Active game wall seconds | 59.874599182 |
| Persisted per-game trial elapsed seconds | 60.267418314 |
| Trial summary GPU wall seconds | 60.26783096299994 |
| Benchmark plus teardown elapsed seconds | 60.905308882999975 |

The synthetic native call returned `submit_number({"value":4})` with a valid
call ID, finish_reason `tool_calls`, and preserved reasoning. The subsequent
tool-result turn returned final content and finish_reason `stop`. The prior
Harmony exception did not recur in these completed requests. This demonstrates
the repaired path works for readiness, not universal parser reliability.

The only gameplay request used complete SCENE_V1 text, `reasoning_effort=high`,
`tool_choice=auto`, `ignore_eos=false`, `stream=false`, temperature 0.6,
top_p 0.95 and seed 1214842320. `max_tokens` was **omitted**, not explicitly zero
or null. The python tool had no strict flag. System/user content lengths were
13341/7166 characters. Nothing received a complete gameplay response before:

```text
analyzer request failed at action 1: HTTPConnectionPool(host='127.0.0.1', port=1234): Read timed out. (read timeout=59.799306)
RuntimeError("Gate 2 trial G failed validation: ['zero actions']")
```

## What this resolves and what it does not

The engine generated `4071 - (41 + 5) = 4025` tokens during the sole game request.
That subtraction reconciles engine work with zero client-accounted response
tokens; zero in the game row does **not** mean the GPU did no work. Server logs
show one active request, no queued requests, generation throughput 67.1–67.9
tokens/s in successive reporting intervals, and increasing KV use during the
game window. This supports active decoding, not idle GPU or a decode-time OOM.

We did not stream or retain the partial model output. Therefore the 4025 tokens
cannot all be labeled reasoning, nor can we determine whether generation was
useful deliberation, a long tool program, repetition or malformed output before
completion. Completed-request latency histograms cover the two readiness calls;
they must not be used as gameplay latency measurements.

This is a first-decision latency failure against the 60-second game window,
not evidence about cleared-level capability. Increasing the window might permit
a decision, but no such result has been measured. Blindly lowering response
limits would also repeat the rejected token-cap experiment without knowing the
output's contents.

## Persistence and shutdown

`benchmark_ok=false`, `clean=false`, `completed_trials=[]`, `teardown_ok=true`.
Fresh shutdown evidence: `shutdown_ok=true`, `metrics_preserved=true`,
`gpu_query_ok=true`, `post_gpu_rows=[]`, `owned_gpu_rows_after=[]`,
`cpu_survivors=[]`, `errors=[]`. No hard guard fired. Native warmup evidence,
game request, per-game zero-action row, metrics, server log and notebook log all
survived the failed final assertion and HTML export.

Raw output: `/tmp/arc3-gptoss-smoke-v3.3cqIF6vr`.
Durable archive: `research/artifacts/gptoss-smoke-v3/runtime-evidence.tar.gz`.
SHA256: `56d941ba63bb3eab394d312c2e8bcfea6bdd322e9405711fff6931c4bbcc2700`.

## Stop and continuation

The sole GPU validation in the renewed parser-repair objective is consumed.
Monitor paused after terminal recovery; **no V4, capability benchmark, long run
or scored submission launched**. This route is checkpointed/stopped, not promoted.

Before another GPU decision, the next diagnostic must preserve streaming partial
output and measure time to a complete, validated first tool call on the actual
game prompt. Tool-call fragments must never be executed. Any changed reasoning
policy or longer first-decision allowance needs its own declared short budget;
it cannot be disguised as rerunning this passed synthetic readiness test.

Execution: current selected lead; Terra-medium scoped implementation in one
reused isolated worktree; Terra-high source trace/delta review; Luna read-only
terminal verification. No Sol escalation. 188 local tests and notebook checks
passed before launch. Terminal artifact verification made no source changes.
The current gate has established request compatibility but not deeper solving,
score above 10, or a rank prediction.

# Gate 1 C16 validation — recovered measurement

Source: Kaggle notebook version `349837918`, named
`Gate 1 C16 safety validation`, run on 2026-09-14.

## Benchmark outcome

The 25-game benchmark completed before the notebook failed during external vLLM
teardown. The saved `score.json` contains 25 games and reports the exact local
score:

```text
7.685530742451533
```

Recovered aggregate results:

| Metric | Value |
|---|---:|
| Games present | 25 |
| Games completing at least one level | 20 |
| Levels completed | 35 |
| Actions | 2,551 |
| Generated tokens | 1,489,200 |
| Notebook runtime | 1h 59m 15s |

The output directory contains `benchmark.json`, `score.json`,
`submission.parquet`, prompts, transcripts, solver analysis, final vLLM metrics,
the model endpoint capture, the server log, server identity, preflight and setup
provenance, watchdog data, and `vllm-server-teardown.json`.

## Teardown failure

Cell `In [7]` failed because the bundled teardown command returned exit status 1:

```text
RuntimeError: vLLM teardown did not reach the bounded terminal gate
```

The teardown report preserved both required artifacts and showed the API port
closed, no final CPU marker survivors, and no final owned process-scan matches.
Its remaining terminal-gate violation was one GPU process:

```text
pid: 238
comm: VLLM::Worker
start_ticks: 29860
used_memory_mib: 96342
```

The server log shows that SIGTERM began the orderly engine shutdown, after which
vLLM force-killed its remaining EngineCore. The teardown script allowed three
seconds for SIGTERM and two seconds for SIGKILL, but performed no bounded wait
for the NVIDIA process table to drain after the process left the ordinary process
scan.

Kaggle notebook version `349890386` (`Gate 1 lifecycle smoke v2`) verified the
fix. The same owned `VLLM::Worker` identity (PID `238`, with the smoke run's
`start_ticks=764474`) remained briefly after the bundled teardown. An exact
PID/start-time `SIGKILL` plus bounded NVIDIA-table polling cleared it in
`0.5278688879998299` seconds. The final process table was empty, the notebook
reported independent benchmark and teardown success, and the logical exit code
was zero.

The smoke also exposed a reporting bug: rerunning the entire bundled teardown
after the port had closed could no longer capture the metrics endpoint and
therefore falsely failed `final_metrics_preserved`. The terminal audit now keeps
the first teardown's successfully captured metrics and re-evaluates only the
post-drain GPU-process predicate. Its final markers were
`GATE1_TEARDOWN_RECOVERED`, `GATE1_FINAL_STATUS` with `logical_exit_code: 0`,
and `GATE1_SMOKE_OK`.

No competition submission was made from this version.

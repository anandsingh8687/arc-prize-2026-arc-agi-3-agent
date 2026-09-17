# Exact Qwen3.8 Flash-Next checkpoint probe — 2026-09-14

Source: private Kaggle notebook, saved Version 4 (not submitted):
https://www.kaggle.com/code/anandsingh8687/arc-agi-3-hardware-throughput-probe?scriptVersionId=349806717

Checkpoint identity:

```
MODEL_HF_REPO RadixArk/Qwen3.8-Flash-Next-NVFP4
MODEL_HF_REVISION 7b719225242aacd3dbd3f9407468c2ee9a9d2594
MODEL_KAGGLE_PATH /kaggle/input/models/keithtyser/qwen3-8-flash-next-nvfp4/pytorch/radixark-modelopt-fp4/1
MODEL_TOTAL_BYTES 135253622894
MODEL_CONFIG_SHA256 e765305daba0951974308f4d32c075b52a6a45974730d273f2216718a994d624
```

No competition submission was made. The GPU draft session was stopped after the
notebook version was saved.

## Hardware and serving stack

```
NVIDIA-SMI 580.159.04
Driver Version: 580.159.04
CUDA Version: 13.0
GPU NVIDIA RTX PRO 6000 Blackwell Server Edition
97887 MiB
torch 2.10.0+cu128
torch.cuda.device_count() 1
torch total_memory/1e9 101.973950464
RAM total 176 GiB
nproc 46
/kaggle/working 20G
transformers 5.0.0
triton 3.6.0
vLLM preinstalled: False
PackageNotFoundError('vllm')
```

The attached competition runtime supplies vLLM
`0.1.dev20073+g8e685d198`.

## Server configuration

```
python3 -m vllm.entrypoints.cli.main serve MODEL_PATH
--served-model-name Qwen/Qwen3.8-Flash-Next-NVFP4
--host 127.0.0.1 --port 1234
--load-format safetensors --dtype bfloat16 --quantization modelopt_fp4
--tensor-parallel-size 1 --distributed-executor-backend mp
--gpu-memory-utilization 0.92 --max-model-len 32768
--max-num-seqs 32 --max-num-batched-tokens 8192 --async-scheduling
--enable-chunked-prefill --enable-prefix-caching --enable-auto-tool-choice
--tool-call-parser qwen3_coder --reasoning-parser qwen3
--chat-template MODEL_PATH/chat_template.jinja
--speculative-config {"method":"mtp","num_speculative_tokens":3}
--no-enable-log-requests --disable-uvicorn-access-log --uvicorn-log-level info
```

This used `max_num_seqs=32` for the probe. The frozen Duck configuration used 28.

## Load and memory

```
ready_seconds 625.072029711
load_and_ready_seconds 625.0732558699999
model loading 398.802295 seconds
Model loading took 81.8 GiB memory
Available KV cache memory: 2.26 GiB
GPU KV cache size: 42,910 tokens
Maximum concurrency for 32,768 tokens per request: 1.31x
NVIDIA after load: used 90844 MiB, free 6407 MiB, total 97887 MiB
```

vLLM recommendations printed during profiling:

```
--kv-cache-memory=1036644987
--kv-cache-memory=8609259008
```

The first is approximately 0.97 GiB to fit the 0.92 utilization target; the
second is approximately 8.02 GiB to fully utilize the GPU. The tested server
reported 2.26 GiB of available KV cache.

## Duck prompt size

```
system prompt chars 12358
no tools prompt tokens 2851
no tools elapsed 0.9732843410001806
with Python tool prompt tokens 3322
with Python tool elapsed 1.0210168139999496
_LOCAL_ANALYZER_CONTEXT_WINDOW=32768
_LOCAL_ANALYZER_MAX_OUTPUT=0
tool steps 12
tool output tokens 1024
thinking true
request safety margin 512
```

## Realistic 4,403-token prompt sweep

All requests generated 128 tokens and completed with zero errors.

| Concurrency | Aggregate decode tok/s | Per-stream tok/s | Wall seconds | Mean TTFT seconds | Median TTFT seconds | Max TTFT seconds | Cache hits | Cache queries |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 159.84466315618454 | 159.84466315618454 | 1.0485957750001944 | 0.2475570270003118 | 0.2475570270003118 | 0.2475570270003118 | 1600 | 4403 |
| 8 | 199.09527901026905 | 24.88690987628363 | 5.397493828000279 | 2.43879887737495 | 2.5258499535000283 | 4.474474929999815 | 12800 | 35224 |
| 16 | 196.20977889264256 | 12.26311118079016 | 10.701479898999878 | 5.054721616250106 | 5.084717848000082 | 9.872146027000326 | 25600 | 70454 |
| 24 | 191.84742439086696 | 7.99364268295279 | 16.281606361000286 | 7.765520716000007 | 7.734865634000016 | 15.528421335000075 | 38400 | 105686 |
| 32 | 187.8472272557216 | 5.8702258517413 | 22.08091997700012 | 10.684368141093728 | 10.564195672499864 | 21.19070408000016 | 51200 | 140918 |

## Matched 8K sweep

The shared prefix was warmed. Prompts contained 8,194-8,195 tokens. Every request
generated 256 tokens and completed with zero errors.

Warm request:

```
prompt tokens 8194
TTFT 0.5183059110004251
wall 0.5187022709997109
cache hits delta 1600
```

| Concurrency | Aggregate decode tok/s | Per-stream tok/s | Wall seconds | Mean TTFT seconds | Median TTFT seconds | Max TTFT seconds | Effective requested prefill tok/s | Cache hits | Cache queries |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 170.9665160629042 | 170.9665160629042 | 2.0300150200000644 | 0.5323612229999526 | 0.5323612229999526 | 0.5323612229999526 | 15391.804748334816 | 1600 | 8194 |
| 8 | 252.96473239736997 | 31.620591549671246 | 8.280821554999875 | 3.335108619374978 | 3.2902837229999022 | 6.5191033510000125 | 10055.370573308139 | 51200 | 65552 |
| 16 | 254.92803868668747 | 15.933002417917967 | 16.25901984400025 | 7.317531218999989 | 7.306374601500011 | 14.51561719900019 | 9032.34069916301 | 102400 | 131110 |
| 32 | 251.9829309596138 | 7.874466592487932 | 32.71171493199972 | 15.6998489442188 | 15.895222562000072 | 31.060820805000276 | 8442.4684603887 | 204800 | 262230 |

## Findings and limitations

- Aggregate decode throughput is effectively saturated by C8-C16. C32 preserves
  aggregate throughput but reduces per-stream throughput and raises tail latency.
- The exact Flash-Next checkpoint reaches `251.9829309596138` aggregate decode
  tok/s at C32 with an 8K prompt. The older `197` figure came from a different
  repacked checkpoint and must not be transferred to this checkpoint.
- The prior matched gpt-oss result of approximately 466 tok/s is therefore about
  1.85x this exact checkpoint, not 2.4x. This establishes an affordability
  difference only; ARC score capability is still unmeasured.
- Prefix caching was enabled. Metrics do not show the entire prompt as a cache
  hit: the C1 requests reported only 1,600 hit tokens. The exact checkpoint still
  needs a true server-on versus server-off comparison before attributing the full
  wall-time difference to prefix caching.
- Synthetic throughput does not choose the agent operating point. The next gate
  is paired RHAE per GPU-second at 8 and 16 active sequences.

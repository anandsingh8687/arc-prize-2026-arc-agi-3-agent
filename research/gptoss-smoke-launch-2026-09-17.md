# GPT-OSS private lifecycle smoke — launch record

Status at 2026-09-17 17:06 UTC: **RUNNING**, not passed.

- Notebook: https://www.kaggle.com/code/anandsingh8687/arc3-gptoss-smoke-20260917
- Kaggle version: **1**.
- Source revision: **e454e36**.
- Launched around 2026-09-17 17:06 UTC with `kaggle kernels push -p notebooks/gptoss-smoke -t 1200 --accelerator NvidiaRtxPro6000`.
- Private notebook, internet disabled, no competition submission.
- One `r11l-495a7899` game, seed 1214842320, 60-second game window measured from ready after native-tool warmup. The external Kaggle limit is 1,200 seconds, including startup and shutdown.
- Model: `danielhanchen/gpt-oss-120b/Transformers/default/1`; served name `gpt-oss-120b`, high reasoning, native function tools, complete scene text, no images.
- Complete scene is delivered with every outer game-observation message. This does not claim a newly rendered scene is inserted into every inner tool-call response.
- Quota observed before launch: 1.92 GPU hours until 2026-09-19 00:00 UTC. This is not a post-run balance.

## Validation and review

172 tests passed using `PYTHONPATH=../duck-harness-source/ARC3-Inference:. python3 -m pytest -q --ignore=tests/test_scoring.py`. The unchanged scorer tests require `arc_agi`, unavailable in this local interpreter; no score calculation was modified. The notebook validator passed all 9 code cells and its one markdown cell. `git diff --check` passed.

Read-only Terra-high review found two current-gate P1 defects. One bounded repair and finding-ID delta verification resolved both:

- **GPTOSS-BUILD-001**, introduced in `c3f6361`, resolved in `82ef1b5`: root-dead worker cleanup now uses saved, root-verified exact process identities and fails closed on identity conflicts.
- **GPTOSS-BUILD-002**, reviewed in the integration at `c3f6361`, resolved in `7317ee3`: normalized requests are fsynced before POST; actual response JSON is persisted, excluding authorization headers. Final audit checks model, seed, reasoning effort, tools, text modality, scene delivery, request counts and absence of Qwen-specific parameters.

Delta reviewer `/root/gptoss_integration_review` verified both fixes and 22 targeted tests. Requested/observed worker route was Terra-high; no Sol escalation. The in-process watchdog is not an independent process-survival guarantee; the external Kaggle limit supplies the hard bound.

## Completion and stop rules

The existing thread heartbeat `arc-agi-3-recovery-screen-follow-up` was updated, not duplicated, to inspect this exact notebook every five minutes. On terminal outcome it must download artifacts, report model/runtime/request evidence, actions/levels and clean shutdown separately, write a result, and pause. It cannot launch another GPU run or a submission.

Acceptance requires real game actions, durable request/result evidence, valid text/native-tool delivery and clean fresh process state. A failed game-solving attempt is not the same as a failed lifecycle. A lifecycle pass establishes no score improvement. At most one bounded runtime repair/retry is allowed by this gate; no open-ended repair loop.

The next model-capability protocol is **not launched**. It must be frozen separately with matched GPU-time budgets, controls/repeats, held-out environments, and an aggregate completed-level decision plus a catastrophic-regression bound. Token rates are diagnostic, not the promotion target. Different model tokenizers prevent treating equal token counts as equal resource use.

Verified competition score remains **2.37**. No evidence yet supports a score above 10, a rank guarantee, or an additive combination of the rejected Qwen interventions.

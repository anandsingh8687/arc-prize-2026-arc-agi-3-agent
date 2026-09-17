# GPT-OSS parser repair: evidence and bounded launch decision

Objective: `20260917-gptoss-parser-repair`, BUILD. This is a renewed, bounded
investigation after V2 stopped the earlier objective; not an uncounted retry.

## Evidence

V2 failed before any game action with `Unexpected token 200002 while expecting
start token 200006`. `research/reproduce_harmony_parser.py`, using installed
`openai-harmony==0.0.8` and the verified offline vocabulary with network denied,
reproduces that exact error on a **synthetic** double-ending stream. Valid final
and native-tool streams each parse one message. V2's actual generated token
IDs were not saved, so this is not a causal replay.

The exact packaged vLLM `0.1.dev20073+g8e685d198` source was read from the runtime
dataset, not inferred solely from upstream HEAD. Layer 24 SHA256:
`10dce885652a53a2e644a75d256b90830663330988b8599c3c0e56cd6c8a4675`.

`research/check_packaged_harmony_dispatch.py` runs the exact registry's two
dispatch functions using stub schema/grammar builders, CPU only:

| Request | Dispatch |
|---|---|
| required, non-strict tools | structural grammar selected |
| auto, non-strict tools | no structural grammar |
| auto, strict tools | structural grammar selected |

Registry SHA256 `015b989c567c6794e6dbbba72af88694470421adab13775c95b50efe9eedd2b7`.
Harmony parser SHA256 `9dbaf2b2797e36864780267660c63a479a1d9953f58e24d7d66c9d3f47f39685`.
The packaged Harmony grammar has `_END_TAG = ["<|end|>", ""]`, and token
processing passes IDs directly to Harmony's streaming parser. This supports a
distinct constrained-path failure hypothesis; it does not prove V2's exact
generation or show that auto cannot fail.

## Repair and validation

- Readiness and actual agent requests explicitly use `tool_choice="auto"`.
- Tools remain non-strict. Adding `strict:true` would invalidate the dispatch
  evidence for bypassing structural grammar.
- Readiness turn two preserves reasoning/reasoning_content and tool definitions.
- `ignore_eos=False` is explicit; it was already the default, not a demonstrated
  cause or a claimed causal fix.
- Native call name, value, ID and final response remain checked. No parser
  relaxation, token stripping, serving flags, weights or teardown changes.
- HTTP error bodies are bounded to 4096 characters; headers are not logged.
- 188 tests pass with Duck on PYTHONPATH; unchanged scorer tests excluded because
  `arc_agi` is unavailable locally. Notebook: 9 code cells parse, 1 markdown cell
  resolves. Exact dispatch CPU probe passes. `git diff --check` passes.
- Terra-high delta review: no P1, 38 scoped tests passed; one bounded hypothesis
  test justified, no capability/long-run/submission approval. No Sol escalation.

## Launch decision

Authorize **one** new private lifecycle validation of this repaired notebook:
`anandsingh8687/arc3-gptoss-smoke-20260917`, next version after terminal V2.
Maximum 1200 seconds including startup/shutdown, internet disabled, existing free
quota only, RTX PRO 6000, one game for 60 seconds after readiness. No competition
submission. Before launch status was ERROR, no job active; quota telemetry showed
reserved time zero and pay-to-scale disabled. The API's malformed used-time
string is not treated as an exact balance.

Success requires verified native tool roundtrip, actual game actions, durable
request/result artifacts, and a clean fresh process table. Failure is preserved
and ends this validation budget; no automated retry. Any pass is transport and
lifecycle evidence only. The verified competition score remains 2.37.

Source commit, Kaggle version and terminal result will be recorded separately
after upload so the source does not contain a circular self-revision.

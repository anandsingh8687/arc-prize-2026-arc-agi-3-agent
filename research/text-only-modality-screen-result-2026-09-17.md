# Qwen image-vs-text screen — result, 2026-09-17

Source: [Kaggle notebook Version 1](https://www.kaggle.com/code/anandsingh8687/arc3-text-only-screen-20260917), built from `611d9612b990668bc420083c564767410787ae13`. This was a public-game development run, not a competition submission. The preceding 60-second W/T smoke passed with 7 actions in each arm and `TEXT_SMOKE_OK`.

The full run completed all three preregistered arms. `lifecycle.json` reports `benchmark_ok=true`, `teardown_ok=true`, no benchmark or teardown error, no hard guard, and an empty post-teardown GPU process table. No arm has validation problems or length-limit finishes.

| Arm | Image | Cleared levels | Weighted RHAE | Actions | Calls | Generated tokens | GPU seconds |
|---|---|---:|---:|---:|---:|---:|---:|
| W | yes | 1 | 1.1904761904761905 | 174 | 103 | 125551 | 600.0900143520001 |
| T | no | 0 | 0.0 | 218 | 139 | 121524 | 608.3451654559999 |
| W-repeat | yes | 2 | 1.9738077846185955 | 154 | 101 | 131146 | 612.2268811790002 |

Cleared levels by game:

| Game | W | T | W-repeat |
|---|---:|---:|---:|
| `cd82` | 0 | 0 | 2 |
| `ka59` | 1 | 0 | 0 |
| `g50t` | 0 | 0 | 0 |

**Preregistered verdict: T fails viability and scoring promotion.** It clears fewer levels than even the weaker image control (0 vs 1). No gpt-oss-120b run should reuse this text view unchanged, and no long run or scored submission follows this result. The verified hidden score remains 2.37.

## Concrete information-channel loss

The T transcript's first user message contains no board or scene description; it gives only `step 1`, `level 1`, valid actions and instructions to inspect `current_frame` via Python. The system prompt explicitly says to use segmentation as the primary view and to use ASCII only for a small region, “never” to scan or summarize the whole board. Its first tool call therefore prints 14 segmented components, color, size and a first boundary point, but not the whole spatial layout. In W the multimodal addendum says the user turn includes an attached image, and later W reasoning explicitly refers to what “the image shows.” The text arm retained access to `.ascii` and `.segmentation`, but it did **not** receive an equivalent full-scene representation in the prompt. This is a concrete perception mismatch, not proof that text-only reasoning is intrinsically weaker. The two image controls also differ from each other (1 vs 2 clears), so this small screen does not establish a stable modality effect size.

Before a fair gpt-oss screen, provide a compact but complete text scene representation at each turn (or at least the initial turn and scene changes), then test Qwen with that representation against image Qwen on a short paired gate. Do not infer model superiority from token/action: T used fewer tokens per action while clearing no levels.

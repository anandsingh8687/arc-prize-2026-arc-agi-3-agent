# Complete-scene capability screen — frozen before GPU

Objective: obtain evidence for a candidate that clears more levels and can advance toward a full-public-25 score above 10. No short-subset score is a claim about Kaggle leaderboard score. Verified hidden score remains 2.37.

## Evidence selection

Completed short screens have not justified promotion: memory 4 levels vs controls 2/3 but no robust per-game advantage; recovery 4 vs 1/3 with a regression on tn36; repeat recovery 3 vs 5/5; affordance 5 vs 5/5; medium reasoning 6 vs 6/5; image removal 0 vs 1/2. These totals come from different subsets and budgets and must not be compared across experiments as agent scores. The eight-game output-cap experiment also failed and is not combined with this treatment.

The code/transcript audit identifies a concrete missing input: default Duck does not directly supply complete text observations. The failed T treatment removed the image while retaining instructions that discouraged full-grid inspection. A stronger text model remains untested. The proposed scene view is useful to image Qwen too: explicit component bounds and exact cell changes can replace repeated model-written inspection code. Whether this improves reasoning is unknown.

## Treatment

Host-generated SCENE_V1 is appended to every outer agent turn. It includes every visible cell through lossless collapse of consecutive identical rows/columns, inclusive original coordinate ranges, neutral 4-connected component areas/bounding boxes (maximum 64, with truncation disclosed), and changes since the prior outer-turn observation. Large change lists are summarized, but the full current grid is always present. It never labels a component as a goal, avatar, wall or HUD. No game identities or source mechanics enter the renderer.

The text was independently decoded back to all 565 recorded frames in the affordance control traces (cd82, ka59, tn36), with exact equality. Scene size ranged from 1264 to 6615 characters, median 2668. CPU processing of all 565 took 5.436708790999546 seconds locally. This proves data preservation only. It does not establish LLM readability or score.

## Protocol

- Same Qwen3.8 Flash-Next NVFP4 checkpoint, serving setup, uncapped responses, action cap 400, seed 1214842320.
- One server. W=image baseline; C=image+SCENE_V1; T=SCENE_V1 without image; W-repeat=image baseline.
- Exact-code smoke: W/C/T each 60 seconds on cd82 after server-ready, then bounded teardown. Require real actions in every arm, scene telemetry in C/T, correct image gates, saved artifacts and clean final process table/export.
- Screen after smoke: cd82, ka59, re86; 600 seconds per arm, three concurrent games; W/C/T/W-repeat in one server session. These are development games, not held-out transfer evidence. Budget approximately 50 minutes including startup.
- Advance C to a locked transfer test only if its total levels beat the better control by more than the absolute W/W-repeat total difference, no game is below the weaker per-game control, and its RHAE/GPU-second exceeds the weaker control. This is a conservative screening heuristic, not a statistical confidence interval.
- T viability for model comparison: total clears at least the weaker whole-arm image control and no game loses more than one level against that same control. This only supports a model experiment; it does not promote T.
- If both fail, stop this candidate after recording failure modes. No broad repair sweep.
- With 2.98 GPU hours remaining at selection, run at most this smoke plus one screen before reassessing quota. No paid purchase, scored submission or nine-hour run.

Source of serving/function-calling requirements for later gpt-oss packaging: OpenAI gpt-oss-120b model documentation and vLLM's official GPT-OSS recipe. The parser is model-specific (`openai` function-call parser); Qwen parser/template settings must not be carried across checkpoints. Later model testing is a separate gate.

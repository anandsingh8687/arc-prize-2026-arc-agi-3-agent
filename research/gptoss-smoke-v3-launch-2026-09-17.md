# GPT-OSS V3 bounded lifecycle validation

Accepted by Kaggle on 2026-09-17 around 18:20 UTC; status RUNNING at 18:20:51 UTC.
This is not a result or a capability claim.

- Notebook: https://www.kaggle.com/code/anandsingh8687/arc3-gptoss-smoke-20260917
- Version: **3**, kernel ID `134757429`.
- Exact source: `9f60ae802bc0438d74843e27d2b96d20c9a6a603`.
- Decision/evidence: [parser repair](gptoss-parser-repair-2026-09-17.md).
- Objective: `20260917-gptoss-parser-repair`.
- Private, internet off, existing free GPU quota, RTX PRO 6000, 1200-second total
  timeout. Kaggle accepted all dataset/model/competition inputs without errors.
- One `r11l-495a7899` game, 60 seconds after native-tool readiness. No submission.
- Existing five-minute heartbeat updated for this exact version; it must recover
  results on terminal status, pause, and never relaunch.
- No additional GPU retry in this objective. Long tests and score claims remain
  outside this gate. Last verified competition score: **2.37**.

The pre-launch API reported zero reserved time and pay-to-scale disabled. Its
used-time string `15326.106.0s` is malformed, so it is retained as raw telemetry,
not converted into an asserted exact remaining balance.

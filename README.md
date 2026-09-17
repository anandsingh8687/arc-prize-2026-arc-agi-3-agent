# ARC Prize 2026 — ARC-AGI-3

An agent for the [ARC-AGI-3 Kaggle competition](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3).

This repository is a snapshot of our ARC-AGI-3 agent, evaluation code, Kaggle
notebooks, tests, and experiment reports through 2026-09-18. It contains no
competition model weights or Kaggle credentials. The notebooks build on the
[Tufa Labs Duck harness](https://github.com/Tufalabs/duck-harness); that upstream
project is not vendored here.

## Measured status

Our one scored Kaggle submission achieved **2.37 on the public leaderboard**.
Its matched 25-game local run scored **5.265162984780623** and cleared **31 of
183 levels**. Later experiments in `research/` are local development screens,
not additional leaderboard submissions; none has established a score above 10.
See [the submission log](research/submissions.md) for run identities and caveats.

See [research/PLAN.md](research/PLAN.md) for the architecture and the evidence behind it,
and [research/probe-2026-09-14.md](research/probe-2026-09-14.md) for measured hardware limits.

## Setup

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python arc-agi pytest
```

The toolkit issues an anonymous API key on first use and caches game sources under
`environment_files/`, so no credentials are needed for local development.

## Evaluate

```bash
.venv/bin/python -m arc3.evaluate --agent random --games ls20,ft09 --max-actions 150
.venv/bin/python -m pytest tests/ -q --ignore=tests/test_duck_gptoss_adapter.py
```

`test_duck_gptoss_adapter.py` also requires Duck's `inference` package, which
is supplied separately by the upstream harness. The remaining suite includes
the scoring tests when `arc-agi` is installed.

`--scored-environments 110` divides by the hidden-set size instead of the games played,
projecting what a partial local run would be worth on the leaderboard.

## The budget

110 hidden games, 9 hours, one 96GB Blackwell GPU, no internet, 1 submission per UTC day.

Reaching level 3 of every game needs **0.577 actions/sec sustained**. The game engine
runs at ~800 actions/sec on CPU, so essentially the entire budget is model time.
Every change is measured on score *and* throughput; a change that improves reasoning
but drops below the action rate is not an improvement.

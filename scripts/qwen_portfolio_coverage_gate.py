#!/usr/bin/env python3
"""Local non-scored coverage gate for Qwen portfolio wiring (no GPU / no Kaggle).

Pass criteria (this box):
  1. Portfolio plan builds for a 25-id list under a 2h wall.
  2. Dry harness proves solver.max_runtime_s_per_game is driven by the plan.
  3. JSONL + summary artifacts are written.

Does NOT launch Duck/vLLM and does NOT create a scored submission.

Next non-scored Qwen kernel / local GPU run:
  export ARC3_TRACE=/kaggle/working/coverage.jsonl
  export ARC3_PORTFOLIO_SECONDS=7200
  # In Gate-1 / smoke notebook settings, before bm.run(...):
  #   from arc3.qwen_portfolio import (
  #       plan_for_qwen, apply_plan_game_to_solver,
  #       notify_level_and_spend, trace_from_duck_row, record_duck_rows,
  #   )
  #   plan = plan_for_qwen(game_ids, float(os.environ["ARC3_PORTFOLIO_SECONDS"]))
  #   apply_plan_game_to_solver(bm.solver, plan, game_id)  # per session start
  #   # after each game: notify_level_and_spend(...); collect rows then record_duck_rows
  # Keep TRUE_SUBMISSION / competition submit False.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from arc3.qwen_portfolio import dry_run_budget_api, plan_for_qwen, record_duck_rows

PUBLIC_SHORT_IDS = [
    "tn36", "lf52", "cn04", "bp35", "wa30", "lp85", "r11l", "tu93",
    "sp80", "m0r0", "vc33", "ar25", "ka59", "sc25", "sk48", "dc22",
    "cd82", "ft09", "g50t", "ls20", "re86", "s5i5", "sb26", "su15", "tr87",
]


def main() -> int:
    out_dir = Path(tempfile.mkdtemp(prefix="qwen_portfolio_gate_"))
    plan = plan_for_qwen(
        PUBLIC_SHORT_IDS,
        total_seconds=7200,
        scored_environments=25,
        min_seconds_per_game=90.0,
    )
    plan_path = out_dir / "portfolio_plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "total_seconds": plan.total_seconds,
                "scored_environments": plan.scored_environments,
                "reserve_seconds": plan.reserve_seconds,
                "games": [
                    {
                        "game_id": g.game_id,
                        "allocated_seconds": g.allocated_seconds,
                        "phase": g.phase.value,
                    }
                    for g in plan.games
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    live_plan, outcomes = dry_run_budget_api(
        [g.game_id for g in plan.games[:5]],
        total_seconds=600,
        play_seconds=40,
        levels_by_game={plan.games[0].game_id: 1} if plan.games else {},
    )
    rows = [
        {
            "game_id": o.game_id,
            "levels_completed": o.levels_completed,
            "actions_taken": o.actions,
            "active_wall_seconds": o.wall_seconds,
            "llm_calls": 0,
            "generated_tokens": 0,
            "abandon_reason": o.abandon_reason,
            "state": "gave_up",
        }
        for o in outcomes
    ]
    summary = record_duck_rows(
        rows,
        trace_path=str(out_dir / "coverage.jsonl"),
        scored_environments=25,
    )

    ok = (
        len(plan.games) >= 1
        and all(g.allocated_seconds >= 90.0 - 1e-6 for g in plan.games)
        and len(outcomes) >= 1
        and all(o.meta.get("solver_budget", 0) > 0 for o in outcomes)
        and summary["games_touched"] >= 1
    )
    report = {
        "gate": "qwen_local_portfolio_coverage",
        "pass": ok,
        "games_in_plan": len(plan.games),
        "dry_outcomes": len(outcomes),
        "trace_summary": summary,
        "artifacts": str(out_dir),
        "oss_status": "shelved_after_T1_FAIL_v6",
        "next_gpu_hint": (
            "Non-scored Qwen Gate-1/smoke with ARC3_TRACE + ARC3_PORTFOLIO_SECONDS; "
            "TRUE_SUBMISSION=False; do not push scored submit."
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"PORTFOLIO_GATE_{'OK' if ok else 'FAIL'}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

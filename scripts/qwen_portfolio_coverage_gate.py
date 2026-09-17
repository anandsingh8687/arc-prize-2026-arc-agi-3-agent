#!/usr/bin/env python3
"""Local non-scored coverage gate for Qwen portfolio wiring (no GPU / no Kaggle).

Pass criteria (this box):
  1. Portfolio plan builds for a 25-id list under a 2h wall.
  2. Dry harness proves solver.max_runtime_s_per_game is driven by the plan.
  3. JSONL + summary artifacts are written.
  4. Sequential notify-before-next-apply changes revisit allocation after a level.
  5. Optional: downloaded Kaggle artifact dir asserts abandon/reallocate fields
     (pass --artifacts DIR pointing at coverage.jsonl / portfolio_plan_final.json).

Does NOT launch Duck/vLLM and does NOT create a scored submission.

Next non-scored Qwen kernel / local GPU run:
  export ARC3_TRACE=/kaggle/working/coverage.jsonl
  export ARC3_PORTFOLIO_SECONDS=7200
  # concurrency=1 required for true sequential portfolio (see research/ACTIVE_GATES.md)
  # Session play: apply → play → session-end notify → next apply
  # Keep TRUE_SUBMISSION / competition submit False.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from arc3.qwen_portfolio import (
    apply_budget_to_solver,
    drive_sequential_portfolio,
    dry_run_budget_api,
    plan_for_qwen,
    record_duck_rows,
)

PUBLIC_SHORT_IDS = [
    "tn36", "lf52", "cn04", "bp35", "wa30", "lp85", "r11l", "tu93",
    "sp80", "m0r0", "vc33", "ar25", "ka59", "sc25", "sk48", "dc22",
    "cd82", "ft09", "g50t", "ls20", "re86", "s5i5", "sb26", "su15", "tr87",
]


def assert_downloaded_artifacts(artifacts_dir: Path) -> dict:
    """Require abandon_reason / reallocate evidence from a Kaggle output dir."""
    cov = artifacts_dir / "coverage.jsonl"
    plan_final = artifacts_dir / "portfolio_plan_final.json"
    if not cov.is_file():
        raise FileNotFoundError(f"missing {cov}")
    rows = []
    for line in cov.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    if not rows:
        raise AssertionError("coverage.jsonl is empty")
    if not any("abandon_reason" in r for r in rows):
        raise AssertionError("coverage.jsonl rows missing abandon_reason field")
    abandon_nonzero = [
        (r.get("game_id"), r.get("abandon_reason"))
        for r in rows
        if str(r.get("abandon_reason") or "").strip()
    ]
    reallocate = None
    if plan_final.is_file():
        doc = json.loads(plan_final.read_text(encoding="utf-8"))
        games = doc.get("games") or []
        exploit = [g for g in games if str(g.get("phase")) == "exploit"]
        # Reallocate evidence: exploit phase and/or allocated growth vs equal explore.
        reallocate = {
            "exploit_games": [g.get("game_id") for g in exploit],
            "reserve_seconds": doc.get("reserve_seconds"),
            "levels": [
                (g.get("game_id"), g.get("levels_completed"), g.get("allocated_seconds"))
                for g in games
                if int(g.get("levels_completed") or 0) > 0
            ],
        }
        if not exploit and not reallocate["levels"]:
            raise AssertionError(
                "portfolio_plan_final.json has no exploit phase or leveled games"
            )
    elif not abandon_nonzero and not any(
        int(r.get("levels_completed") or 0) > 0 for r in rows
    ):
        raise AssertionError(
            "no abandon_reason values and no levels_completed>0 in coverage.jsonl; "
            "missing portfolio_plan_final.json for reallocate cross-check"
        )
    return {
        "coverage_rows": len(rows),
        "abandon_nonzero": abandon_nonzero,
        "reallocate": reallocate,
        "has_plan_final": plan_final.is_file(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifacts",
        default="",
        help="optional downloaded Kaggle output dir to assert abandon/reallocate fields",
    )
    args = parser.parse_args()

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

    class _Solver:
        max_runtime_s_per_game = 0.0

    seq_plan = plan_for_qwen(
        ["hot", "cold"],
        total_seconds=500,
        min_seconds_per_game=40,
        reserve_fraction=0.2,
    )
    explore = next(g for g in seq_plan.games if g.game_id == "hot").allocated_seconds
    applies: list[float] = []

    def play_session(game_id: str, applied: float):
        applies.append(applied)
        if game_id == "hot" and len(applies) == 1:
            return {
                "levels_completed": 1,
                "actions_taken": 20,
                "active_wall_seconds": 60.0,
            }
        return {
            "levels_completed": 1 if game_id == "hot" else 0,
            "actions_taken": 25,
            "active_wall_seconds": applied,
        }

    drive_sequential_portfolio(
        _Solver(),
        seq_plan,
        play_session,
        bonus_seconds=80.0,
        max_visits=3,
    )
    sequential_ok = len(applies) >= 2 and applies[1] > (explore - 60.0) + 1e-6

    artifact_report = None
    if args.artifacts:
        artifact_report = assert_downloaded_artifacts(Path(args.artifacts))

    ok = (
        len(plan.games) >= 1
        and all(g.allocated_seconds >= 90.0 - 1e-6 for g in plan.games)
        and len(outcomes) >= 1
        and all(o.meta.get("solver_budget", 0) > 0 for o in outcomes)
        and summary["games_touched"] >= 1
        and sequential_ok
        and (artifact_report is not None if args.artifacts else True)
    )
    report = {
        "gate": "qwen_local_portfolio_coverage",
        "pass": ok,
        "games_in_plan": len(plan.games),
        "dry_outcomes": len(outcomes),
        "trace_summary": summary,
        "sequential_notify_before_apply": {
            "ok": sequential_ok,
            "applies": applies[:4],
            "explore_slice": explore,
        },
        "downloaded_artifacts": artifact_report,
        "artifacts": str(out_dir),
        "concurrency_policy": "concurrency=1 required for true portfolio sequential runs",
        "oss_status": "shelved_after_T1_FAIL_v6",
        "next_gpu_hint": (
            "Non-scored Qwen mini-wave with ARC3_TRACE + ARC3_PORTFOLIO_SECONDS; "
            "TRUE_SUBMISSION=False; concurrency=1; do not push scored submit."
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"PORTFOLIO_GATE_{'OK' if ok else 'FAIL'}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

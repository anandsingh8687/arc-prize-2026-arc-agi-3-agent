"""Retrospective stall-signal audit over Duck *_events.jsonl traces.

This is a diagnostic, not a proposed action blocker. An apparently unchanged
board may conceal time or other latent state, and the row-63 variant is only a
sensitivity check, not a universal volatility mask.
"""

from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
from statistics import mean


def board_digest(board: list[list[int]], ignore_last_row: bool) -> bytes:
    rows = board[:-1] if ignore_last_row else board
    digest = hashlib.blake2b(digest_size=12)
    digest.update(len(rows).to_bytes(2, "little"))
    for row in rows:
        digest.update(len(row).to_bytes(2, "little"))
        digest.update(bytes(row))
    return digest.digest()


def audit(path: Path, ignore_last_row: bool = False) -> dict:
    previous = None
    prior_noops: set[tuple] = set()
    recent_repeats: deque[int] = deque(maxlen=10)
    repeats = noops = alias_exceptions = actions = level_completions = 0
    trigger_at = None
    first_completion_at = None
    levels_after_trigger = 0
    final_state = None
    with path.open(encoding="utf-8") as source:
        for line in source:
            event = json.loads(line)
            if event.get("type") not in {"initial", "action"}:
                continue
            if event["type"] == "initial":
                previous = event
                continue
            if previous is None:
                raise ValueError(f"{path}: action before initial frame")
            actions += 1
            final_state = event.get("state")
            before = (previous.get("level"), previous.get("state"),
                      board_digest(previous["board"], ignore_last_row))
            after = (event.get("level"), event.get("state"),
                     board_digest(event["board"], ignore_last_row))
            action = (event.get("action_name"), event.get("action_display"))
            key = (*before, action)
            unchanged = before == after
            repeated = unchanged and key in prior_noops
            if unchanged:
                noops += 1
                prior_noops.add(key)
            elif key in prior_noops:
                alias_exceptions += 1
            if repeated:
                repeats += 1
            recent_repeats.append(int(repeated))
            if trigger_at is None and sum(recent_repeats) >= 3:
                trigger_at = actions
            if event.get("level_completed"):
                level_completions += 1
                if first_completion_at is None:
                    first_completion_at = actions
                if trigger_at is not None:
                    levels_after_trigger += 1
                recent_repeats.clear()
            previous = event
    return {
        "game": path.name.split("-")[0],
        "actions": actions,
        "levels": level_completions,
        "noops": noops,
        "repeats": repeats,
        "trigger_at": trigger_at,
        "first_completion_at": first_completion_at,
        "levels_after_trigger": levels_after_trigger,
        "alias_exceptions": alias_exceptions,
        "won": final_state == "WIN",
    }


def summarize(rows: list[dict]) -> dict:
    triggered = [row for row in rows if row["trigger_at"] is not None]
    return {
        "traces": len(rows),
        "games": len({row["game"] for row in rows}),
        "actions": sum(row["actions"] for row in rows),
        "total_wins": sum(row["won"] for row in rows),
        "total_cleared_levels": sum(row["levels"] for row in rows),
        "zero_level_traces": sum(row["levels"] == 0 for row in rows),
        "zero_level_no_noops": sum(row["levels"] == 0 and row["noops"] == 0 for row in rows),
        "first_level_by_40_actions": sum(row["first_completion_at"] is not None
                                         and row["first_completion_at"] <= 40 for row in rows),
        "first_level_by_80_actions": sum(row["first_completion_at"] is not None
                                         and row["first_completion_at"] <= 80 for row in rows),
        "first_level_after_80_actions": sum(row["first_completion_at"] is not None
                                            and row["first_completion_at"] > 80 for row in rows),
        "noops": sum(row["noops"] for row in rows),
        "repeated_noops": sum(row["repeats"] for row in rows),
        "triggered_traces": len(triggered),
        "triggered_then_cleared_level": sum(row["levels_after_trigger"] > 0 for row in triggered),
        "triggered_then_won": sum(row["won"] for row in triggered),
        "alias_exceptions": sum(row["alias_exceptions"] for row in rows),
        "mean_levels_triggered": mean(row["levels"] for row in triggered) if triggered else None,
        "mean_levels_untriggered": mean(row["levels"] for row in rows if row["trigger_at"] is None)
        if len(triggered) < len(rows) else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--ignore-last-row", action="store_true")
    parser.add_argument("--per-game", action="store_true")
    args = parser.parse_args()
    paths = sorted(args.directory.glob("*_events.jsonl"))
    rows = [audit(path, args.ignore_last_row) for path in paths]
    print(json.dumps(summarize(rows), sort_keys=True))
    if args.per_game:
        groups: dict[str, list[dict]] = {}
        for row in rows:
            groups.setdefault(row["game"], []).append(row)
        for game, game_rows in sorted(groups.items()):
            print(game, json.dumps(summarize(game_rows), sort_keys=True))


if __name__ == "__main__":
    main()

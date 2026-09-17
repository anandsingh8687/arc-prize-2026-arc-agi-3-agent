"""Replay the live recovery detector at recorded Duck analysis boundaries.

Only notebook event logs are read; game implementation files are never used.
The replay excludes the wall-clock fallback because event logs do not carry
per-level wall time. It answers whether the repeated-no-op or action-count
signals would have fired *without* the 180-second timer.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from types import SimpleNamespace

from arc3.recovery import detect_stall


def first_action_trigger(path: Path) -> dict | None:
    history = []
    for line in path.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        kind = event.get("type")
        if kind in ("initial", "action"):
            history.append(SimpleNamespace(
                action=str(event.get("action_display") or ""),
                frame=SimpleNamespace(
                    grid=event["board"], level=int(event["level"]),
                ),
            ))
        elif kind == "analysis":
            signal = detect_stall(history)
            if signal is not None:
                return {
                    "analysis_action_num": int(event["action_num"]),
                    "signal": asdict(signal),
                }
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comparison_dir", type=Path)
    args = parser.parse_args()
    for arm in ("W", "S", "W-repeat"):
        for path in sorted((args.comparison_dir / arm / "artifacts").glob("*_events.jsonl")):
            game = path.name.split("_")[0]
            print(json.dumps({
                "arm": arm,
                "game": game,
                "first_action_trigger": first_action_trigger(path),
            }, sort_keys=True))


if __name__ == "__main__":
    main()

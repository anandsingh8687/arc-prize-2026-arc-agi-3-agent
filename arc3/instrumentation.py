"""Per-game run instrumentation for coverage and depth decisions.

Every competed environment should emit one record so we can answer:
how many games were touched, how deep, why abandoned, and where wall time went.
Untouched scored environments still contribute 0 to the mean — coverage gaps
are first-class signal, not an afterthought.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1


@dataclass
class GameTrace:
    game_id: str
    wall_seconds: float = 0.0
    actions: int = 0
    levels_completed: int = 0
    level_indices_completed: list[int] = field(default_factory=list)
    abandon_reason: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    llm_calls: int = 0
    score: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = SCHEMA_VERSION
        return payload


class TraceRecorder:
    """Append-only JSONL + optional final JSON summary."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.path.unlink()
        self._rows: list[dict[str, Any]] = []

    def record(self, trace: GameTrace) -> None:
        row = trace.to_dict()
        self._rows.append(row)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    def coverage_summary(self, scored_environments: int) -> dict[str, Any]:
        touched = {r["game_id"] for r in self._rows}
        return {
            "schema_version": SCHEMA_VERSION,
            "scored_environments": scored_environments,
            "games_touched": len(touched),
            "games_untouched": max(0, scored_environments - len(touched)),
            "games_with_zero_levels": sum(
                1 for r in self._rows if int(r.get("levels_completed") or 0) == 0
            ),
            "total_levels_completed": sum(
                int(r.get("levels_completed") or 0) for r in self._rows
            ),
            "total_wall_seconds": sum(
                float(r.get("wall_seconds") or 0) for r in self._rows
            ),
            "total_actions": sum(int(r.get("actions") or 0) for r in self._rows),
        }

    def write_summary(
        self, scored_environments: int, summary_path: str | Path | None = None
    ) -> dict[str, Any]:
        summary = self.coverage_summary(scored_environments)
        out = Path(summary_path) if summary_path else self.path.with_suffix(".summary.json")
        out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return summary


class GameTimer:
    def __init__(self) -> None:
        self._t0 = time.monotonic()

    def elapsed(self) -> float:
        return time.monotonic() - self._t0


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows

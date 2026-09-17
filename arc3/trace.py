"""Crash-proof persistence for the transition ledger.

`research/run-discipline.md` rule 2 was written after a run completed its work
and died in teardown: results must survive a crash anywhere after the benchmark.
A ledger accumulated in memory and written at the end of a nine-hour run is
exactly the shape that rule forbids.

So the trace is **append-only JSONL, one self-contained record per transition,
flushed and fsynced as it is written**. A run killed at any instant keeps every
transition it had finished recording, and the reader tolerates the half-written
final line that an interrupted write leaves behind.

    writer = TraceWriter(path, game_id="lp85-305b61c3")
    writer.write(transition)          # durable before it returns
    ledger = read_trace(path)         # skips a torn tail, counts what it skipped

Size. Each record stores the BEFORE grid verbatim and the AFTER grid as a cell
diff, since an action usually changes a handful of cells. At 64x64 int8 that is
roughly 5.5 KB per transition, so a 400-action game costs about 2.2 MB. That is
fine for E0, which records one game. Recording all 110 in a competition run
would need a compaction pass -- consecutive records duplicate a board that the
previous record already implies -- and that is deliberately not done here,
because breaking record independence is what makes a torn file unreadable.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from arc3.ledger import AnimationEvidence, FrameStep, GameLedger, ObservedState, Transition

FORMAT_VERSION = 4  # v4 records resize frames as snapshots; v3 dropped them
SUPPORTED_VERSIONS = frozenset({FORMAT_VERSION})


def _encode_grid(grid: np.ndarray) -> dict[str, Any]:
    contiguous = np.ascontiguousarray(grid)
    return {
        "shape": list(contiguous.shape),
        "dtype": contiguous.dtype.name,
        "b64": base64.b64encode(contiguous.tobytes()).decode("ascii"),
    }


def _decode_grid(payload: dict[str, Any]) -> np.ndarray:
    raw = base64.b64decode(payload["b64"])
    return np.frombuffer(raw, dtype=np.dtype(payload["dtype"])).reshape(payload["shape"])


def _encode_observed(state: ObservedState, *, grid: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {
        "level": state.level,
        "attempt": state.attempt,
        "available_actions": list(state.available_actions),
        "status": state.status,
    }
    if grid:
        out["grid"] = _encode_grid(state.grid)
    return out


def encode(t: Transition) -> dict[str, Any]:
    """One self-contained JSON record.

    The after-grid is stored as a diff when it has the same shape as the before
    grid, and verbatim when it does not -- a level change can resize the board,
    and a diff across differing shapes would be meaningless.
    """
    same_shape = t.before.grid.shape == t.after.grid.shape
    after = _encode_observed(t.after, grid=not same_shape)
    if same_shape:
        after["diff"] = [[r, c, int(v)] for (r, c), v in sorted(t.diff.items())]

    return {
        "v": FORMAT_VERSION,
        "index": t.index,
        "action": list(t.action),
        "before": _encode_observed(t.before),
        "after": after,
        "before_norm_hash": t.before_norm_hash,
        "before_raw_hash": t.before_raw_hash,
        "after_raw_hash": t.after_raw_hash,
        "animation": {
            "frame_count": t.animation.frame_count,
            "settled_noop": t.animation.settled_noop,
            # Ordered: each entry is one frame's changes against the previous.
            # A set of values per cell cannot tell A->B->C from C->B->A, and
            # once the raw frames are gone that loss is permanent.
            "timeline": [
                {"snapshot": _encode_grid(step.snapshot)} if step.resizes
                else {"changes": [[r, c, v] for (r, c), v in sorted(step.changes.items())]}
                for step in t.animation.timeline
            ],
        },
    }


def decode(record: dict[str, Any]) -> Transition:
    version = record.get("v")
    if version not in SUPPORTED_VERSIONS:
        # Silently decoding an older record would hand back an empty animation
        # timeline that reads as "this transition had no animation" -- evidence
        # loss disguised as evidence.
        raise ValueError(
            f"trace record version {version!r} is not supported "
            f"(this build reads {sorted(SUPPORTED_VERSIONS)}); re-record rather "
            "than decoding it as empty"
        )
    before_grid = _decode_grid(record["before"]["grid"])
    before = ObservedState(
        grid=before_grid,
        level=record["before"]["level"],
        attempt=record["before"]["attempt"],
        available_actions=tuple(record["before"]["available_actions"]),
        status=record["before"]["status"],
    )

    after_payload = record["after"]
    if "grid" in after_payload:
        after_grid = _decode_grid(after_payload["grid"])
    else:
        after_grid = before_grid.copy()
        for r, c, v in after_payload["diff"]:
            after_grid[r, c] = v

    after = ObservedState(
        grid=after_grid,
        level=after_payload["level"],
        attempt=after_payload["attempt"],
        available_actions=tuple(after_payload["available_actions"]),
        status=after_payload["status"],
    )

    action = record["action"]
    return Transition(
        index=record["index"],
        before=before,
        action=(action[0], action[1], action[2]),
        after=after,
        before_norm_hash=record["before_norm_hash"],
        before_raw_hash=record["before_raw_hash"],
        after_raw_hash=record["after_raw_hash"],
        animation=AnimationEvidence(
            frame_count=record.get("animation", {}).get("frame_count", 1),
            settled_noop=record.get("animation", {}).get("settled_noop", False),
            timeline=tuple(
                FrameStep(snapshot=_decode_grid(step["snapshot"])) if "snapshot" in step
                else FrameStep(changes={(r, c): v for r, c, v in step["changes"]})
                for step in record.get("animation", {}).get("timeline", [])
            ),
        ),
    )


class TraceWriter:
    """Append-only writer. Every record is durable before `write` returns.

    Opened in append mode on purpose: a resumed run adds to the trace it already
    has rather than truncating it. That also means a caller must not reuse a path
    across two different games -- `read_trace` would merge them into one ledger,
    and transitions never pool across games.
    """

    def __init__(self, path: str | Path, game_id: str) -> None:
        self.path = Path(path)
        self.game_id = game_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a", encoding="utf-8")

    def write(self, transition: Transition) -> None:
        self._handle.write(json.dumps(encode(transition), separators=(",", ":")) + "\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.close()

    def __enter__(self) -> "TraceWriter":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


@dataclass
class TraceRead:
    """What came back, and what did not."""

    ledger: GameLedger
    skipped: int = 0  # lines that would not parse -- normally the torn tail
    tail_truncated: bool = False


def iter_trace(path: str | Path) -> Iterator[tuple[int, dict[str, Any] | None]]:
    """Yield (line number, record or None) so callers can see what failed."""
    with Path(path).open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield number, json.loads(line)
            except json.JSONDecodeError:
                yield number, None


def read_trace(path: str | Path, game_id: str = "") -> TraceRead:
    """Rebuild the ledger, tolerating a torn final line.

    A killed process leaves a partial line at the end. That is one lost
    transition, not a lost run, and it must not raise -- rule 3 separates "the
    work succeeded" from "the process exited cleanly", and an unreadable trace
    would collapse the two again.
    """
    result = TraceRead(ledger=GameLedger(game_id or Path(path).stem))
    records = list(iter_trace(path))
    for position, (number, record) in enumerate(records):
        if record is None:
            result.skipped += 1
            if position == len(records) - 1:
                result.tail_truncated = True
            continue
        result.ledger.record(decode(record))
    return result

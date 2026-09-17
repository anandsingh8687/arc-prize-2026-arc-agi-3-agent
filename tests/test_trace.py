"""A trace must survive the crash that rule 2 was written about."""

from __future__ import annotations

import json

import numpy as np
import pytest

from arc3.ledger import AnimationEvidence, FrameStep, GameLedger, ObservedState, Transition
from arc3.trace import TraceWriter, encode, decode, read_trace
from arc3.state import hash_grid

MOVE = (1, None, None)
CLICK = (6, 12, 30)


def state(fill: int = 0, *, shape=(8, 8), level=1, attempt=0,
          actions=(1, 2, 6), status="NOT_FINISHED") -> ObservedState:
    grid = np.full(shape, fill, dtype=np.int8)
    return ObservedState(grid=grid, level=level, attempt=attempt,
                         available_actions=actions, status=status)


def transition(index: int, *, before=None, after=None, action=MOVE, animation=None) -> Transition:
    b = before if before is not None else state(0)
    a = after if after is not None else state(0)
    if after is None:
        a.grid[index % a.grid.shape[0], 1] = 7  # something actually changed
    return Transition(index=index, before=b, action=action, after=a,
                      before_norm_hash=hash_grid(b.grid),
                      before_raw_hash=hash_grid(b.grid),
                      after_raw_hash=hash_grid(a.grid),
                      animation=animation or AnimationEvidence())


def assert_same(a: Transition, b: Transition) -> None:
    assert a.index == b.index
    assert a.action == b.action
    assert a.before.equals(b.before)
    assert a.after.equals(b.after)
    assert (a.before_norm_hash, a.before_raw_hash, a.after_raw_hash) == (
        b.before_norm_hash, b.before_raw_hash, b.after_raw_hash)
    assert a.animation.frame_count == b.animation.frame_count
    assert a.animation.timeline == b.animation.timeline
    assert a.animation.settled_noop == b.animation.settled_noop


def test_round_trip_preserves_every_field(tmp_path):
    rows = [transition(0),
            transition(1, action=CLICK,
                       animation=AnimationEvidence(
                           frame_count=4, settled_noop=True,
                           timeline=(FrameStep(changes={(2, 3): 9, (5, 1): 7}),
                                     FrameStep(changes={(2, 3): 4}),
                                     FrameStep(changes={(2, 3): 0, (5, 1): 0})))),
            transition(2)]
    path = tmp_path / "lp85.jsonl"
    with TraceWriter(path, "lp85") as writer:
        for row in rows:
            writer.write(row)

    out = read_trace(path, "lp85")
    assert out.skipped == 0 and not out.tail_truncated
    assert len(out.ledger.transitions) == 3
    for original, restored in zip(rows, out.ledger.ordered()):
        assert_same(original, restored)


def test_a_torn_final_line_costs_one_transition_not_the_run():
    """The crash rule 2 exists for: killed mid-write, keep everything before."""
    rows = [transition(i) for i in range(5)]
    lines = [json.dumps(encode(r), separators=(",", ":")) for r in rows]
    blob = "\n".join(lines)
    torn = blob[: len(blob) - 20]  # process died part-way through the last record

    import tempfile, pathlib
    path = pathlib.Path(tempfile.mkdtemp()) / "torn.jsonl"
    path.write_text(torn + "\n")

    out = read_trace(path, "g")
    assert out.tail_truncated
    assert out.skipped == 1
    assert len(out.ledger.transitions) == 4
    assert [t.index for t in out.ledger.ordered()] == [0, 1, 2, 3]


def test_a_corrupt_line_in_the_middle_is_counted_not_fatal(tmp_path):
    path = tmp_path / "g.jsonl"
    rows = [transition(i) for i in range(3)]
    body = [json.dumps(encode(rows[0]), separators=(",", ":")),
            "{not json at all",
            json.dumps(encode(rows[2]), separators=(",", ":"))]
    path.write_text("\n".join(body) + "\n")

    out = read_trace(path, "g")
    assert out.skipped == 1
    assert not out.tail_truncated  # the damage is not at the tail
    assert [t.index for t in out.ledger.ordered()] == [0, 2]


def test_the_after_grid_is_reconstructed_exactly_from_the_diff(tmp_path):
    before = state(0)
    after = state(0)
    after.grid[3, 4] = 9
    after.grid[0, 0] = 15
    row = transition(0, before=before, after=after)

    restored = decode(encode(row))
    assert np.array_equal(restored.after.grid, after.grid)
    assert restored.diff == row.diff


def test_a_level_change_that_resizes_the_board_survives(tmp_path):
    """A diff across differing shapes is meaningless, so the grid is stored whole."""
    before = state(0, shape=(8, 8), level=1)
    after = state(3, shape=(16, 16), level=2, actions=(1, 2, 3, 6))
    row = transition(0, before=before, after=after)

    restored = decode(encode(row))
    assert restored.after.grid.shape == (16, 16)
    assert restored.after.equals(after)
    assert restored.level_changed


def test_terminal_metadata_survives_the_round_trip(tmp_path):
    after = state(0, level=2, attempt=3, actions=(), status="GAME_OVER")
    row = transition(0, after=after)
    restored = decode(encode(row))
    assert restored.after.status == "GAME_OVER"
    assert restored.after.attempt == 3
    assert restored.after.available_actions == ()
    assert restored.after.level == 2


def test_writing_is_append_only_across_reopens(tmp_path):
    """A resumed run must add to its trace, never truncate it."""
    path = tmp_path / "g.jsonl"
    TraceWriter(path, "g").write(transition(0))
    writer = TraceWriter(path, "g")
    writer.write(transition(1))
    writer.close()
    assert [t.index for t in read_trace(path, "g").ledger.ordered()] == [0, 1]


def test_a_restored_ledger_reports_and_verifies_like_the_original(tmp_path):
    """The point of persistence: the analysis is identical after a round trip."""
    rows = [transition(i) for i in range(10)]
    path = tmp_path / "g.jsonl"
    with TraceWriter(path, "g") as writer:
        for row in rows:
            writer.write(row)

    original = GameLedger("g", rows).report()
    restored = read_trace(path, "g").ledger.report()
    assert (restored.transitions, restored.unique_keys, restored.unique_raw_keys) == (
        original.transitions, original.unique_keys, original.unique_raw_keys)
    assert restored.aliased_keys == original.aliased_keys
    assert restored.noop_rate == pytest.approx(original.noop_rate)
    assert (restored.induction, restored.repair, restored.holdout) == (
        original.induction, original.repair, original.holdout)


def test_a_record_missing_a_hash_is_rejected_on_read(tmp_path):
    """The __post_init__ guard must not be bypassable through the file format."""
    payload = encode(transition(0))
    payload["before_raw_hash"] = ""
    with pytest.raises(ValueError, match="before_raw_hash"):
        decode(payload)


def test_the_animation_timeline_survives_the_round_trip_in_order(tmp_path):
    """v2 stored a set of values per cell and lost the order permanently."""
    forward = AnimationEvidence(
        frame_count=4,
        timeline=tuple(FrameStep(changes={(1, 1): v}) for v in (3, 6, 9)))
    restored = decode(encode(transition(0, animation=forward)))
    assert [step.changes[(1, 1)] for step in restored.animation.timeline] == [3, 6, 9]
    assert restored.animation.distinct_frame_count == 3


def test_an_older_record_is_rejected_rather_than_decoded_as_empty(tmp_path):
    """Silently reading a v3 record would hand back an empty animation timeline,
    which reads as 'this transition had no animation' -- evidence loss disguised
    as evidence."""
    payload = encode(transition(0))
    payload["v"] = 3
    with pytest.raises(ValueError, match="version 3"):
        decode(payload)

    payload.pop("v")
    with pytest.raises(ValueError, match="version None"):
        decode(payload)


def test_a_resize_animation_round_trips(tmp_path):
    from arc3.ledger import animation_evidence

    before = np.zeros((2, 4), dtype=np.int8)
    big = np.ones((4, 8), dtype=np.int8)
    ev = animation_evidence(before, [big, big.copy()])

    row = Transition(index=0,
                     before=ObservedState(grid=before, level=1, available_actions=(1,)),
                     action=MOVE,
                     after=ObservedState(grid=big, level=2, available_actions=(1,)),
                     before_norm_hash="n", before_raw_hash="r", after_raw_hash="a",
                     animation=ev)

    restored = decode(encode(row))
    assert [s.resizes for s in restored.animation.timeline] == \
           [s.resizes for s in ev.timeline]
    assert np.array_equal(restored.animation.frames(before)[0], big)

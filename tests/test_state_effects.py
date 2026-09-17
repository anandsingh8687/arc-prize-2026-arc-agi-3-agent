"""Tests for the deterministic layer: masking, hashing, components, ledger."""

from __future__ import annotations

import numpy as np

from arc3.effects import EffectLedger
from arc3.state import (
    MIN_SAMPLES_FOR_MASK,
    StateTracker,
    VolatilityTracker,
    components,
    diff_cells,
    hash_grid,
)


def test_volatile_cells_are_excluded_from_the_hash():
    """A ticking counter must not make every board look new."""
    board = np.zeros((8, 8), dtype=np.int16)
    board[2:5, 2:5] = 3

    tracker = VolatilityTracker()
    for step in range(MIN_SAMPLES_FOR_MASK + 2):
        frame = board.copy()
        frame[0, 0] = step % 10  # a timer in the corner
        tracker.observe(frame)

    mask = tracker.mask
    assert mask is not None
    assert not mask[0, 0]  # the timer is volatile
    assert mask[3, 3]  # the board is not

    a, b = board.copy(), board.copy()
    a[0, 0], b[0, 0] = 1, 9
    assert hash_grid(a, mask) == hash_grid(b, mask)
    assert hash_grid(a) != hash_grid(b)  # unmasked, they look different


def test_resizing_board_restarts_volatility_statistics():
    tracker = VolatilityTracker()
    for _ in range(MIN_SAMPLES_FOR_MASK + 2):
        tracker.observe(np.zeros((8, 8), dtype=np.int16))
    assert tracker.mask is not None

    tracker.observe(np.zeros((16, 16), dtype=np.int16))  # level change
    assert tracker.samples == 0
    assert tracker.mask is None


def test_components_finds_regions_largest_first():
    grid = np.zeros((6, 6), dtype=np.int16)
    grid[0:3, 0:3] = 4  # 9 cells
    grid[5, 5] = 7  # 1 cell

    found = components(grid)
    assert [c.size for c in found] == [9, 1]
    assert found[0].colour == 4
    assert found[1].centroid == (5, 5)


def test_components_handles_a_long_snaking_region():
    """Flood fill must not rely on recursion; a 64x64 snake would overflow it."""
    grid = np.zeros((64, 64), dtype=np.int16)
    grid[0, :] = 5
    for row in range(1, 64):
        grid[row, 63 if row % 2 else 0] = 5
        if row % 2 == 0:
            grid[row, :] = 5
    assert components(grid)[0].size > 1000


def test_diff_reports_changed_cells_only():
    before = np.zeros((4, 4), dtype=np.int16)
    after = before.copy()
    after[1, 2] = 7
    assert diff_cells(before, after) == {(1, 2): 7}


def test_ledger_remembers_per_state_noops():
    ledger = EffectLedger()
    ledger.record("state-a", (1, None, None), changed_cells=0, level_advanced=False)
    assert ledger.is_known_noop("state-a", (1, None, None))
    assert not ledger.is_known_noop("state-b", (1, None, None))  # different state


def test_exploration_prefers_breadth_over_past_success():
    """Regression: ranking by success alone collapsed the agent onto one action.

    A blind explorer that always picks whichever action moved the board most
    often stops covering the action space and stalls. Fewest attempts must win,
    with effectiveness only breaking ties.
    """
    ledger = EffectLedger()
    winner = (2, None, None)
    other = (1, None, None)

    # `winner` has a perfect record; `other` has been tried once, fruitlessly.
    for _ in range(50):
        ledger.record("s", winner, changed_cells=9, level_advanced=False)
    ledger.record("s", other, changed_cells=0, level_advanced=False)

    assert ledger.value(winner) > ledger.value(other)  # exploitation favours winner
    assert min([winner, other], key=ledger.exploration_rank) == other  # breadth wins


def test_state_tracker_forgets_everything_on_a_level_change():
    tracker = StateTracker()
    tracker.observe(np.zeros((8, 8), dtype=np.int16))
    assert tracker.visited

    tracker.reset_level()
    assert not tracker.visited
    assert tracker.previous_grid is None

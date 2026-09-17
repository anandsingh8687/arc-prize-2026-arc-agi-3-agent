"""Grid state: volatile-cell masking, hashing, and object extraction.

The state hash decides whether the agent thinks it has been somewhere before, so a
ticking clock or animated HUD must not make every frame look novel. We learn which
cells change constantly and exclude them *from the hash only* -- they stay visible
to the agent, because a timer or life counter is often causal.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np

# A cell changing in more than this fraction of observed steps is treated as
# decorative for hashing purposes.
VOLATILITY_THRESHOLD = 0.5
# Volatility needs a few frames before it means anything.
MIN_SAMPLES_FOR_MASK = 4


@dataclass
class VolatilityTracker:
    """Counts how often each cell changes, to find HUD and timer regions."""

    shape: tuple[int, int] | None = None
    changes: np.ndarray | None = None
    samples: int = 0
    _previous: np.ndarray | None = None

    def observe(self, grid: np.ndarray) -> None:
        if self.shape != grid.shape:
            # A level change can resize the board; start the statistics over.
            self.shape = grid.shape
            self.changes = np.zeros(grid.shape, dtype=np.int32)
            self.samples = 0
            self._previous = grid.copy()
            return

        if self._previous is not None:
            self.changes += (grid != self._previous).astype(np.int32)
            self.samples += 1
        self._previous = grid.copy()

    @property
    def mask(self) -> np.ndarray | None:
        """True where a cell is stable enough to hash. None until we have samples."""
        if self.changes is None or self.samples < MIN_SAMPLES_FOR_MASK:
            return None
        return (self.changes / self.samples) <= VOLATILITY_THRESHOLD

    def volatile_cells(self) -> int:
        mask = self.mask
        return 0 if mask is None else int((~mask).sum())


def hash_grid(grid: np.ndarray, mask: np.ndarray | None = None) -> str:
    """Stable 20-hex-char digest of the board, ignoring masked cells."""
    if mask is not None and mask.shape == grid.shape:
        grid = np.where(mask, grid, -1)
    return hashlib.md5(grid.tobytes()).hexdigest()[:20]


def diff_cells(before: np.ndarray, after: np.ndarray) -> dict[tuple[int, int], int]:
    """Cells that changed, as {(row, col): new_value}."""
    if before.shape != after.shape:
        return {(r, c): int(after[r, c]) for r, c in np.ndindex(after.shape)}
    rows, cols = np.nonzero(before != after)
    return {(int(r), int(c)): int(after[r, c]) for r, c in zip(rows, cols)}


@dataclass
class Component:
    """A 4-connected region of one colour."""

    colour: int
    cells: list[tuple[int, int]]

    @property
    def size(self) -> int:
        return len(self.cells)

    @property
    def centroid(self) -> tuple[int, int]:
        rows = [r for r, _ in self.cells]
        cols = [c for _, c in self.cells]
        return round(sum(rows) / len(rows)), round(sum(cols) / len(cols))


def components(grid: np.ndarray, ignore: set[int] | None = None) -> list[Component]:
    """4-connected same-colour regions, largest first.

    Flood fill over an explicit stack: a 64x64 board can produce a region long
    enough to blow the recursion limit.
    """
    ignore = ignore if ignore is not None else {0}
    seen = np.zeros(grid.shape, dtype=bool)
    found: list[Component] = []

    for start_r, start_c in np.ndindex(grid.shape):
        if seen[start_r, start_c]:
            continue
        colour = int(grid[start_r, start_c])
        if colour in ignore:
            seen[start_r, start_c] = True
            continue

        cells: list[tuple[int, int]] = []
        stack = [(start_r, start_c)]
        seen[start_r, start_c] = True
        while stack:
            r, c = stack.pop()
            cells.append((r, c))
            for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if (
                    0 <= nr < grid.shape[0]
                    and 0 <= nc < grid.shape[1]
                    and not seen[nr, nc]
                    and grid[nr, nc] == colour
                ):
                    seen[nr, nc] = True
                    stack.append((nr, nc))
        found.append(Component(colour=colour, cells=cells))

    found.sort(key=lambda comp: comp.size, reverse=True)
    return found


@dataclass
class StateTracker:
    """Per-level view of the board: volatility, hashes, and visited states."""

    volatility: VolatilityTracker = field(default_factory=VolatilityTracker)
    visited: set[str] = field(default_factory=set)
    previous_grid: np.ndarray | None = None

    def observe(self, grid: np.ndarray) -> str:
        self.volatility.observe(grid)
        digest = hash_grid(grid, self.volatility.mask)
        self.visited.add(digest)
        self.previous_grid = grid.copy()
        return digest

    def last_diff(self, grid: np.ndarray) -> dict[tuple[int, int], int]:
        if self.previous_grid is None:
            return {}
        return diff_cells(self.previous_grid, grid)

    def reset_level(self) -> None:
        """Board geometry and dynamics change between levels; keep nothing."""
        self.volatility = VolatilityTracker()
        self.visited = set()
        self.previous_grid = None

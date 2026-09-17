"""Per-level, online HUD-band evidence for a future batch-stop ablation.

This is a classifier, not a veto. The caller may stop the remainder of an
*exploratory* batch after an observed no-impact action; an individual action is
never blocked. The band is learned only from prior actions, so classification
does not peek at a transition before choosing its mask.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Sequence


Grid = Sequence[Sequence[int]]


@dataclass(frozen=True)
class Impact:
    board_changed: bool
    gameplay_changed: bool
    no_impact: bool
    masked_rows: frozenset[int]
    masked_cols: frozenset[int]
    changed_cells: int
    reason: str


class HousekeepingBand:
    """Infer rows/columns that change on nearly every recent game action."""

    def __init__(self, *, window: int = 20, threshold: float = 0.9, warmup: int = 8):
        if window < 1 or not 0 < threshold <= 1 or not 1 <= warmup <= window:
            raise ValueError("invalid HUD-band window, threshold or warmup")
        self.window = window
        self.threshold = threshold
        self.warmup = warmup
        self._history: deque[tuple[frozenset[int], frozenset[int]]] = deque(maxlen=window)
        self._level: int | None = None

    def reset(self, level: int | None = None) -> None:
        self._history.clear()
        self._level = level

    def band(self) -> tuple[frozenset[int], frozenset[int]]:
        count = len(self._history)
        if count < self.warmup:
            return frozenset(), frozenset()
        rows: dict[int, int] = {}
        cols: dict[int, int] = {}
        for seen_rows, seen_cols in self._history:
            for row in seen_rows:
                rows[row] = rows.get(row, 0) + 1
            for col in seen_cols:
                cols[col] = cols.get(col, 0) + 1
        cutoff = self.threshold * count
        return (
            frozenset(row for row, hits in rows.items() if hits >= cutoff),
            frozenset(col for col, hits in cols.items() if hits >= cutoff),
        )

    def observe(self, before: Grid, after: Grid, *, before_level: int, after_level: int) -> Impact:
        """Classify this action using *prior* evidence, then learn its changes."""
        if before_level != after_level:
            self.reset(after_level)
            return Impact(True, True, False, frozenset(), frozenset(), 0, "level_transition")
        if self._level != after_level:
            self.reset(after_level)
        if len(before) != len(after) or any(len(a) != len(b) for a, b in zip(before, after)):
            self.reset(after_level)
            return Impact(True, True, False, frozenset(), frozenset(), 0, "shape_change")
        band_rows, band_cols = self.band()
        # A horizontal timer changing the entire top row also makes *every*
        # column look volatile. Unioning row and column masks would erase the
        # entire board and misclassify a real object change as HUD-only. Use
        # the narrower orientation; ties are ambiguous and are not masked.
        height = len(before)
        width = max((len(row) for row in before), default=0)
        row_area = len(band_rows) * width
        col_area = len(band_cols) * height
        if band_rows and band_cols:
            if row_area < col_area:
                band_cols = frozenset()
            elif col_area < row_area:
                band_rows = frozenset()
            else:
                band_rows = band_cols = frozenset()
        if row_area >= 0.5 * height * width and band_rows:
            band_rows = frozenset()
        if col_area >= 0.5 * height * width and band_cols:
            band_cols = frozenset()
        changed = [(r, c) for r, (old, new) in enumerate(zip(before, after))
                   for c, (a, b) in enumerate(zip(old, new)) if a != b]
        board_changed = bool(changed)
        gameplay_changed = any(r not in band_rows and c not in band_cols for r, c in changed)
        if not (band_rows or band_cols):
            gameplay_changed = board_changed
        self._history.append((frozenset(r for r, _ in changed),
                              frozenset(c for _, c in changed)))
        return Impact(
            board_changed=board_changed,
            gameplay_changed=gameplay_changed,
            no_impact=not gameplay_changed,
            masked_rows=band_rows,
            masked_cols=band_cols,
            changed_cells=len(changed),
            reason="hud_band" if board_changed and not gameplay_changed else
                   "exact_noop" if not board_changed else "gameplay_change",
        )

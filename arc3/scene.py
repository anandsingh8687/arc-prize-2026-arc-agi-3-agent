"""Lossless, game-agnostic descriptions of ARC colour grids.

``encode_grid`` is intended for storage or programmatic consumption; its small
run-length representation remains entirely JSON serializable.  ``render_scene``
is a compact, human- and LLM-readable view of the same complete board.  Neither
function assigns a meaning to colours or components.
"""

from __future__ import annotations

from collections import deque
from numbers import Integral
from typing import Any, Sequence


COLOUR_SYMBOLS = "WwgGcBMP RbSYOrNp".replace(" ", "")
"""Standard ARC colour symbols, indexed by colour number (0 through 15)."""


def _normalise_grid(grid: Any) -> list[list[int]]:
    """Validate *grid* and return an independent, plain-Python copy."""
    if isinstance(grid, (str, bytes)):
        raise ValueError("grid must be a rectangular sequence of rows")
    try:
        rows = list(grid)
    except TypeError as exc:
        raise ValueError("grid must be a rectangular sequence of rows") from exc
    if not 1 <= len(rows) <= 64:
        raise ValueError("grid height must be between 1 and 64")

    copied: list[list[int]] = []
    width: int | None = None
    for row in rows:
        if isinstance(row, (str, bytes)):
            raise ValueError("each grid row must be a sequence of colour integers")
        try:
            values = list(row)
        except TypeError as exc:
            raise ValueError("each grid row must be a sequence of colour integers") from exc
        if width is None:
            width = len(values)
            if not 1 <= width <= 64:
                raise ValueError("grid width must be between 1 and 64")
        elif len(values) != width:
            raise ValueError("grid must be rectangular")
        clean_row: list[int] = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value, Integral):
                raise ValueError("grid colours must be non-boolean integers from 0 to 15")
            value = int(value)
            if not 0 <= value <= 15:
                raise ValueError("grid colours must be from 0 to 15")
            clean_row.append(value)
        copied.append(clean_row)
    return copied


def _equal_ranges(items: Sequence[Any]) -> list[list[int]]:
    """Inclusive consecutive ranges of identical items; never merge non-neighbours."""
    ranges: list[list[int]] = []
    start = 0
    for index in range(1, len(items) + 1):
        if index == len(items) or items[index] != items[start]:
            ranges.append([start, index - 1])
            start = index
    return ranges


def _rle_row(row: Sequence[int]) -> list[list[int]]:
    runs: list[list[int]] = []
    start = 0
    for index in range(1, len(row) + 1):
        if index == len(row) or row[index] != row[start]:
            runs.append([row[start], index - start])
            start = index
    return runs


def encode_grid(grid: Any) -> dict[str, Any]:
    """Encode a 1--64 square/rectangular colour grid without losing any cell.

    The payload contains row and column equivalence *runs* for compact rendering,
    plus RLE for every original row so decoding is independent of those summaries.
    """
    cells = _normalise_grid(grid)
    height, width = len(cells), len(cells[0])
    columns = [tuple(cells[row][col] for row in range(height)) for col in range(width)]
    return {
        "shape": [height, width],
        "row_ranges": _equal_ranges(cells),
        "column_ranges": _equal_ranges(columns),
        "color_grid": [_rle_row(row) for row in cells],
    }


def decode_grid(payload: Any) -> list[list[int]]:
    """Decode and validate an ``encode_grid`` payload into a plain nested list."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a mapping")
    shape = payload.get("shape")
    encoded_rows = payload.get("color_grid")
    if (
        not isinstance(shape, list)
        or len(shape) != 2
        or any(isinstance(value, bool) or not isinstance(value, Integral) for value in shape)
    ):
        raise ValueError("payload shape must be two integer dimensions")
    height, width = (int(shape[0]), int(shape[1]))
    if not 1 <= height <= 64 or not 1 <= width <= 64:
        raise ValueError("payload shape dimensions must be between 1 and 64")
    if not isinstance(encoded_rows, list) or len(encoded_rows) != height:
        raise ValueError("payload color_grid must contain one row per shape row")

    rows: list[list[int]] = []
    for encoded_row in encoded_rows:
        if not isinstance(encoded_row, list):
            raise ValueError("payload row runs must be lists")
        row: list[int] = []
        for run in encoded_row:
            if (
                not isinstance(run, list)
                or len(run) != 2
                or isinstance(run[0], bool)
                or isinstance(run[1], bool)
                or not isinstance(run[0], Integral)
                or not isinstance(run[1], Integral)
            ):
                raise ValueError("payload runs must be [colour, positive_count]")
            colour, count = int(run[0]), int(run[1])
            if not 0 <= colour <= 15 or count < 1:
                raise ValueError("payload runs contain an invalid colour or count")
            row.extend([colour] * count)
        if len(row) != width:
            raise ValueError("payload row runs do not match shape width")
        rows.append(row)
    return rows


def _components(cells: list[list[int]]) -> list[tuple[int, int, tuple[int, int, int, int]]]:
    """Return every same-colour 4-connected component as neutral facts."""
    height, width = len(cells), len(cells[0])
    seen = [[False] * width for _ in range(height)]
    found: list[tuple[int, int, tuple[int, int, int, int], int, int]] = []
    for row in range(height):
        for col in range(width):
            if seen[row][col]:
                continue
            colour = cells[row][col]
            seen[row][col] = True
            queue = deque([(row, col)])
            area = 0
            min_row = max_row = row
            min_col = max_col = col
            while queue:
                current_row, current_col = queue.popleft()
                area += 1
                min_row, max_row = min(min_row, current_row), max(max_row, current_row)
                min_col, max_col = min(min_col, current_col), max(max_col, current_col)
                for next_row, next_col in (
                    (current_row - 1, current_col), (current_row + 1, current_col),
                    (current_row, current_col - 1), (current_row, current_col + 1),
                ):
                    if (
                        0 <= next_row < height and 0 <= next_col < width
                        and not seen[next_row][next_col]
                        and cells[next_row][next_col] == colour
                    ):
                        seen[next_row][next_col] = True
                        queue.append((next_row, next_col))
            found.append((colour, area, (min_row, min_col, max_row, max_col), row, col))
    found.sort(key=lambda item: (-item[1], item[3], item[4], item[0]))
    return [(colour, area, bbox) for colour, area, bbox, _, _ in found]


def _range_text(ranges: Sequence[Sequence[int]]) -> str:
    return ", ".join(str(start) if start == end else f"{start}-{end}" for start, end in ranges)


def render_scene(grid: Any, previous: Any | None = None) -> str:
    """Render a complete, compact SCENE_V1 snapshot and neutral change facts."""
    cells = _normalise_grid(grid)
    height, width = len(cells), len(cells[0])
    encoded = encode_grid(cells)
    row_ranges = encoded["row_ranges"]
    column_ranges = encoded["column_ranges"]
    reduced_rows = [
        "".join(COLOUR_SYMBOLS[cells[row_range[0]][column_range[0]]] for column_range in column_ranges)
        for row_range in row_ranges
    ]

    lines = [
        "SCENE_V1",
        f"shape: {height}x{width}",
        "legend: 0=W 1=w 2=g 3=G 4=c 5=B 6=M 7=P 8=R 9=b 10=S 11=Y 12=O 13=r 14=N 15=p",
        f"rows (inclusive original ranges): {_range_text(row_ranges)}",
        f"columns (inclusive original ranges): {_range_text(column_ranges)}",
        "reduced letter grid (row-ranges x column-ranges):",
        *reduced_rows,
    ]

    if previous is None:
        lines.append("changes: full snapshot (no previous grid)")
    else:
        before = _normalise_grid(previous)
        if (len(before), len(before[0])) != (height, width):
            lines.append(
                f"changes: shape-change {len(before)}x{len(before[0])} -> {height}x{width}; full current snapshot above"
            )
        else:
            changed = [
                (row, col, cells[row][col])
                for row in range(height)
                for col in range(width)
                if before[row][col] != cells[row][col]
            ]
            if len(changed) <= 128:
                facts = ", ".join(f"({row},{col})={COLOUR_SYMBOLS[colour]}" for row, col, colour in changed)
                lines.append(f"changes: {len(changed)} exact cells" + (f": {facts}" if facts else ""))
            else:
                min_row = min(row for row, _, _ in changed)
                max_row = max(row for row, _, _ in changed)
                min_col = min(col for _, col, _ in changed)
                max_col = max(col for _, col, _ in changed)
                lines.append(
                    f"changes: {len(changed)} cells; bbox inclusive ({min_row},{min_col})-({max_row},{max_col}); "
                    "exact change list omitted; full current snapshot above"
                )

    components = _components(cells)
    lines.append(f"components (4-connected, all colours): {len(components)} total")
    for colour, area, (min_row, min_col, max_row, max_col) in components[:64]:
        lines.append(
            f"- color {colour}={COLOUR_SYMBOLS[colour]} area={area} bbox=({min_row},{min_col})-({max_row},{max_col})"
        )
    if len(components) > 64:
        lines.append("component summary truncated after 64; lossless grid remains complete above")
    return "\n".join(lines)

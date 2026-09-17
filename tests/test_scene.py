"""Adversarial preservation tests for the game-agnostic scene encoder."""

from __future__ import annotations

import json
import random

import pytest

from arc3.scene import COLOUR_SYMBOLS, decode_grid, encode_grid, render_scene


def test_randomised_roundtrip_is_exact_and_json_serializable():
    rng = random.Random(20260917)
    for _ in range(80):
        height, width = rng.randint(1, 64), rng.randint(1, 64)
        grid = [[rng.randrange(16) for _ in range(width)] for _ in range(height)]
        payload = encode_grid(grid)
        json.dumps(payload)
        assert payload["shape"] == [height, width]
        assert decode_grid(payload) == grid


def test_only_consecutive_identical_rows_and_columns_are_collapsed():
    grid = [[1, 1, 2], [3, 3, 4], [1, 1, 2], [1, 1, 2]]
    payload = encode_grid(grid)
    assert payload["row_ranges"] == [[0, 0], [1, 1], [2, 3]]
    assert payload["column_ranges"] == [[0, 1], [2, 2]]
    assert decode_grid(payload) == grid


@pytest.mark.parametrize(
    "grid",
    [[], [[]], [[0], []], [[16]], [[-1]], [[True]], [[1.0]], "012"],
)
def test_invalid_grids_are_rejected(grid):
    with pytest.raises(ValueError):
        encode_grid(grid)


def test_same_size_changes_list_exact_original_coordinates_and_neutral_components():
    previous = [[0, 0, 0], [0, 0, 0]]
    current = [[0, 3, 0], [4, 0, 5]]
    scene = render_scene(current, previous)
    assert "shape: 2x3" in scene
    assert "rows (inclusive original ranges): 0, 1" in scene
    assert "columns (inclusive original ranges): 0, 1, 2" in scene
    assert "changes: 3 exact cells: (0,1)=G, (1,0)=c, (1,2)=B" in scene
    assert "components (4-connected, all colours):" in scene
    assert "area=" in scene and "bbox=(" in scene


def test_resize_is_explicit_full_snapshot_and_reduced_grid_preserves_coordinates():
    scene = render_scene([[1, 1], [1, 1], [2, 2]], previous=[[1]])
    assert "shape-change 1x1 -> 3x2; full current snapshot above" in scene
    assert "rows (inclusive original ranges): 0-1, 2" in scene
    assert "columns (inclusive original ranges): 0-1" in scene
    assert "reduced letter grid (row-ranges x column-ranges):\nw\ng" in scene


def test_large_change_diff_is_bounded_but_current_snapshot_is_complete():
    previous = [[0] * 64 for _ in range(64)]
    current = [[1] * 64 for _ in range(64)]
    scene = render_scene(current, previous)
    assert "changes: 4096 cells; bbox inclusive (0,0)-(63,63); exact change list omitted" in scene
    assert "shape: 64x64" in scene
    assert "reduced letter grid" in scene


def test_component_summary_has_a_hard_bound_and_discloses_truncation():
    grid = [[(row + col) % 2 for col in range(16)] for row in range(16)]
    scene = render_scene(grid)
    assert "components (4-connected, all colours): 256 total" in scene
    assert scene.count("\n- color ") == 64
    assert "component summary truncated after 64; lossless grid remains complete above" in scene


def test_character_legend_is_exact_standard_arc_mapping():
    assert COLOUR_SYMBOLS == "WwgGcBMPRbSYOrNp"
    scene = render_scene([list(range(16))])
    assert "legend: 0=W 1=w 2=g 3=G 4=c 5=B 6=M 7=P 8=R 9=b 10=S 11=Y 12=O 13=r 14=N 15=p" in scene
    assert "WwgGcBMPRbSYOrNp" in scene


def test_decode_rejects_malformed_payload_instead_of_guessing():
    with pytest.raises(ValueError):
        decode_grid({"shape": [1, 2], "color_grid": [[[1, 1]] ]})

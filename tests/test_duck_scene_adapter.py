"""Verify what is actually delivered to the model, independent of JSON codec."""

import random
from types import SimpleNamespace

import pytest

from arc3.duck_scene_adapter import SceneObservationMixin, scene_delivery_problems
from arc3.scene import COLOUR_SYMBOLS, render_scene


def restore_rendered(scene):
    lines = scene.splitlines()
    height, width = map(int, lines[1].split(": ")[1].split("x"))
    def expand(text):
        spans = []
        for item in text.split(": ", 1)[1].split(", "):
            ends = list(map(int, item.split("-")))
            spans.append(range(ends[0], ends[-1] + 1))
        return spans
    row_spans, col_spans = expand(lines[3]), expand(lines[4])
    cells = [[None] * width for _ in range(height)]
    for row_span, encoded_row in zip(row_spans, lines[6:6+len(row_spans)], strict=True):
        assert len(encoded_row) == len(col_spans)
        for col_span, letter in zip(col_spans, encoded_row, strict=True):
            for r in row_span:
                for c in col_span:
                    assert cells[r][c] is None
                    cells[r][c] = COLOUR_SYMBOLS.index(letter)
    assert all(cell is not None for row in cells for cell in row)
    return cells


def test_actual_model_text_is_lossless_including_unequal_stripes():
    rng = random.Random(417)
    for _ in range(35):
        base = [[rng.randrange(16) for _ in range(6)] for _ in range(5)]
        row_sizes = [rng.randrange(1, 7) for _ in range(5)]
        col_sizes = [rng.randrange(1, 7) for _ in range(6)]
        grid = []
        for row, repeats in zip(base, row_sizes):
            expanded = [cell for cell, count in zip(row, col_sizes) for _ in range(count)]
            grid.extend([expanded[:]] * repeats)
        assert restore_rendered(render_scene(grid)) == grid


class Base:
    def __init__(self):
        self._system_prompt = "base"
    def _build_user_prompt(self, action_num, *, current_frame=None, **kwargs):
        return "base user"


class SceneAgent(SceneObservationMixin, Base):
    pass


def test_complete_snapshot_delivered_every_turn_and_no_stale_cross_level_delta():
    agent = SceneAgent()
    frames = [SimpleNamespace(grid=[[1, 1]], level=1),
              SimpleNamespace(grid=[[1, 2]], level=1),
              SimpleNamespace(grid=[[3, 3]], level=2)]
    outputs = [agent._build_user_prompt(i, current_frame=frame) for i, frame in enumerate(frames)]
    for text, frame in zip(outputs, frames):
        assert restore_rendered("SCENE_V1" + text.split("SCENE_V1", 1)[1]) == frame.grid
    assert "changes: 1 exact cells: (0,1)=g" in outputs[1]
    assert "no previous grid" in outputs[2]
    assert agent._scene_observations == 3
    assert agent._scene_chars > 0
    assert Base()._system_prompt == "base"


def test_scene_instances_do_not_share_previous_state_and_missing_frame_fails():
    first, second = SceneAgent(), SceneAgent()
    first._build_user_prompt(0, current_frame=SimpleNamespace(grid=[[1]], level=1))
    out = second._build_user_prompt(0, current_frame=SimpleNamespace(grid=[[2]], level=1))
    assert "no previous grid" in out
    with pytest.raises(ValueError):
        second._build_user_prompt(1)


def test_smoke_cannot_pass_plain_agent_mispackaged_as_treatment_or_wrong_modality():
    rows = []
    for arm in ("W", "C", "T", "W-repeat"):
        scene = arm in ("C", "T")
        rows.append(dict(trial_id=arm, game_id="synthetic", scene_observations=int(scene),
                         scene_chars=500*scene, scene_delivered_messages=int(scene),
                         scene_image_messages=int(arm != "T"), scene_text_only_messages=int(arm == "T")))
    assert scene_delivery_problems(rows) == []
    rows[1]["scene_observations"] = 2
    assert scene_delivery_problems(rows)
    rows[1]["scene_observations"] = 1
    rows[1]["scene_delivered_messages"] = 0
    assert scene_delivery_problems(rows)
    rows[1]["scene_delivered_messages"] = 1
    rows[2]["scene_image_messages"] = 1
    assert scene_delivery_problems(rows)

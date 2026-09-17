from __future__ import annotations

import numpy as np

from research.pose_transition_feasibility import (
    Edge, Pose, evaluate_observed_map, interior_unique_components, select_mover,
)


def board(row: int, col: int) -> np.ndarray:
    grid = np.zeros((12, 12), dtype=np.uint8)
    grid[row:row + 2, col:col + 4] = 7
    grid[11, :] = 3  # volatile border is never a candidate
    return grid


def test_unique_moving_interior_component_is_selected_without_coordinates():
    frames = [interior_unique_components(board(2, c)) for c in range(2, 7)]
    edges = [Edge(i + 1, 1, "RIGHT", frames[i], frames[i + 1]) for i in range(4)]
    choice = select_mover(edges, observation_limit=4)
    assert choice["color"] == 7
    assert choice["candidates"]["7"]["moved"] == 4


def test_unobserved_edge_is_unknown_and_conflict_retires_a_claim():
    p0 = Pose(7, 2, 2, 2, 4, "shape")
    p1 = Pose(7, 2, 3, 2, 4, "shape")
    p2 = Pose(7, 2, 4, 2, 4, "shape")
    edges = [
        Edge(1, 1, "RIGHT", {7: p0}, {7: p1}),
        Edge(2, 1, "RIGHT", {7: p0}, {7: p1}),
        Edge(3, 1, "RIGHT", {7: p0}, {7: p2}),
        Edge(4, 1, "RIGHT", {7: p1}, {7: p2}),
    ]
    result = evaluate_observed_map(edges, 7, train_count=3)
    assert result["aliased_pose_action_keys"] == 1
    assert result["holdout_claimed"] == 0
    assert result["holdout_unknown"] == 1


def test_known_edge_mismatch_is_counted_as_confident_error():
    p0 = Pose(7, 2, 2, 2, 4, "shape")
    p1 = Pose(7, 2, 3, 2, 4, "shape")
    p2 = Pose(7, 2, 4, 2, 4, "shape")
    edges = [Edge(1, 1, "RIGHT", {7: p0}, {7: p1}),
             Edge(2, 1, "RIGHT", {7: p0}, {7: p2})]
    result = evaluate_observed_map(edges, 7, train_count=1)
    assert result["holdout_claimed"] == 1
    assert result["holdout_confident_errors"] == 1

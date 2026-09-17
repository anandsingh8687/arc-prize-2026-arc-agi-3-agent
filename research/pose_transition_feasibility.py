"""CPU-only feasibility check for an observed, partial object-pose action map.

This does not predict a whole frame or infer a goal. It tests whether a generic
connected-component tracker can identify one moving object and give the actor
sound *observed* navigation edges. Unknown edges remain unknown.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import blake2b
import json
from pathlib import Path

import numpy as np

from arc3.state import components


@dataclass(frozen=True)
class Pose:
    color: int
    top: int
    left: int
    height: int
    width: int
    shape: str


@dataclass(frozen=True)
class Edge:
    action_num: int
    level: int
    action: str
    before: dict[int, Pose]
    after: dict[int, Pose]


def interior_unique_components(board: np.ndarray) -> dict[int, Pose]:
    """Return one non-border, moderately sized component per color, if unique."""
    height, width = board.shape
    candidates: dict[int, list[Pose]] = defaultdict(list)
    for comp in components(board, ignore=set()):
        if comp.size < 8 or comp.size >= height * width // 5:
            continue
        rows = [r for r, _ in comp.cells]
        cols = [c for _, c in comp.cells]
        top, bottom = min(rows), max(rows)
        left, right = min(cols), max(cols)
        if top == 0 or left == 0 or bottom == height - 1 or right == width - 1:
            continue
        bitmap = np.zeros((bottom - top + 1, right - left + 1), dtype=np.uint8)
        for row, col in comp.cells:
            bitmap[row - top, col - left] = 1
        signature = blake2b(bitmap.tobytes(), digest_size=8).hexdigest()
        candidates[comp.colour].append(Pose(
            color=comp.colour, top=top, left=left,
            height=bitmap.shape[0], width=bitmap.shape[1], shape=signature,
        ))
    return {color: poses[0] for color, poses in candidates.items()
            if len(poses) == 1}


def read_edges(path: Path, *, level: int = 1) -> list[Edge]:
    frames = []
    with path.open(encoding="utf-8") as source:
        for line in source:
            event = json.loads(line)
            if event.get("type") in {"initial", "action"}:
                frames.append(event)
    edges = []
    cached: dict[int, dict[int, Pose]] = {}

    def objects(index: int) -> dict[int, Pose]:
        if index not in cached:
            cached[index] = interior_unique_components(np.asarray(frames[index]["board"], dtype=np.uint8))
        return cached[index]

    for index in range(1, len(frames)):
        before, after = frames[index - 1], frames[index]
        if before.get("level") != level or after.get("level") != level:
            continue
        edges.append(Edge(
            action_num=int(after["action_num"]), level=level,
            action=str(after.get("action_display") or after.get("action_name")),
            before=objects(index - 1), after=objects(index),
        ))
    return edges


def select_mover(edges: list[Edge], *, observation_limit: int = 20) -> dict:
    """Pick the most frequently moving unique interior color using only early data."""
    observed = edges[:observation_limit]
    counts: dict[int, Counter] = defaultdict(Counter)
    for edge in observed:
        for color in edge.before.keys() & edge.after.keys():
            counts[color]["paired"] += 1
            if edge.before[color] != edge.after[color]:
                counts[color]["moved"] += 1
    ranked = sorted(counts, key=lambda color: (-counts[color]["moved"],
                                               -counts[color]["paired"], color))
    if not ranked or counts[ranked[0]]["moved"] < 3:
        return {"color": None, "candidates": {str(k): dict(v) for k, v in counts.items()}}
    selected = ranked[0]
    return {"color": selected, "candidates": {str(k): dict(v) for k, v in counts.items()}}


def evaluate_observed_map(edges: list[Edge], color: int, *, train_count: int) -> dict:
    """Score only pose/navigation claims; never claim a complete game transition."""
    if not 0 < train_count <= len(edges):
        raise ValueError("train_count must fall within the observed edges")
    training = edges[:train_count]
    movement_actions = {edge.action for edge in training
                        if color in edge.before and color in edge.after
                        and edge.before[color] != edge.after[color]}
    outcomes: dict[tuple[Pose, str], set[Pose]] = defaultdict(set)
    seen_poses: set[Pose] = set()
    for edge in training:
        if color in edge.before:
            seen_poses.add(edge.before[color])
        if color in edge.after:
            seen_poses.add(edge.after[color])
        if edge.action in movement_actions and color in edge.before and color in edge.after:
            outcomes[(edge.before[color], edge.action)].add(edge.after[color])
    alias_keys = sum(len(result) > 1 for result in outcomes.values())
    claimed = exact = confident_errors = unknown = 0
    novel_pairs = 0
    for edge in edges[train_count:]:
        if edge.action not in movement_actions or color not in edge.before or color not in edge.after:
            continue
        pair = edge.before[color], edge.action
        answers = outcomes.get(pair, set())
        if len(answers) == 1:
            claimed += 1
            if edge.after[color] in answers:
                exact += 1
            else:
                confident_errors += 1
        else:
            unknown += 1
            if not answers:
                novel_pairs += 1
    return {
        "train_edges": train_count,
        "holdout_edges": len(edges) - train_count,
        "movement_actions": sorted(movement_actions),
        "observed_poses": len(seen_poses),
        "observed_action_edges": len(outcomes),
        "aliased_pose_action_keys": alias_keys,
        "holdout_claimed": claimed,
        "holdout_exact": exact,
        "holdout_confident_errors": confident_errors,
        "holdout_unknown": unknown,
        "holdout_novel_pairs": novel_pairs,
    }


def report(path: Path, *, observation_limit: int = 20) -> dict:
    edges = read_edges(path)
    choice = select_mover(edges, observation_limit=observation_limit)
    result = {"file": path.name, "first_level_edges": len(edges), "selection": choice}
    if choice["color"] is not None:
        color = choice["color"]
        result["prefixes"] = [evaluate_observed_map(edges, color, train_count=n)
                              for n in (20, 40, 60)
                              if n < len(edges)]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.paths:
        print(json.dumps(report(path), sort_keys=True))


if __name__ == "__main__":
    main()

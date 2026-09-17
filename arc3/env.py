"""Thin helpers over the ARC-AGI toolkit's local environment wrapper.

The toolkit issues an anonymous API key on first use and caches game sources under
``environment_files/``, so local development needs no credentials and, after the
first run, no network.
"""

from __future__ import annotations

import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import FrameDataRaw

# Kaggle evaluation constants, verified against the live competition pages 2026-09-14.
RUNTIME_SECONDS = 9 * 3600
HIDDEN_GAMES = 110


def grid_of(frame: FrameDataRaw, fallback: np.ndarray | None = None) -> np.ndarray:
    """The settled board as an (H, W) int array.

    ``frame.frame`` is a list of grids; a multi-frame response is an animation and
    the last entry is the settled state. The engine also returns frames with an
    empty grid list (``frame.is_empty``) -- typically on a rejected or no-op
    action -- in which case the board has not changed and we carry the previous
    one forward rather than inventing an empty board.
    """
    if not frame.frame:
        if fallback is not None:
            return fallback
        return np.zeros((64, 64), dtype=np.int16)
    return np.asarray(frame.frame[-1], dtype=np.int16)


def make_arcade(competition_mode: bool = False) -> Arcade:
    """Competition mode forbids game resets and allows one play per environment.

    Leave it off for local development, where replaying a game is the whole point.
    """
    mode = OperationMode.COMPETITION if competition_mode else None
    return Arcade(operation_mode=mode) if mode else Arcade()


def baselines_by_game(arcade: Arcade) -> dict[str, list[int]]:
    """Per-level human baseline action counts, keyed by the short game id."""
    return {
        env.game_id.split("-")[0]: (env.baseline_actions or [])
        for env in arcade.get_environments()
    }

"""Guards for GPT-OSS gameplay requests (no Duck import).

V3 smoke showed readiness tools work while a ~60s non-streaming game call can
burn ~4k tokens and return zero actions. These helpers encode the promotion
rules for the next smoke: longer timeout, max_tokens ceiling, and zero-action fail.
"""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_GAMEPLAY_TIMEOUT_S = 300.0
DEFAULT_MAX_OUTPUT_TOKENS = 1024
ZERO_ACTION_TOKEN_LIMIT = 2048


@dataclass
class GameplayRequestPolicy:
    timeout_seconds: float = DEFAULT_GAMEPLAY_TIMEOUT_S
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    stream: bool = True
    tool_choice: str = "auto"


def validate_gameplay_outcome(
    *,
    actions_emitted: int,
    completion_tokens: int,
    timed_out: bool,
) -> list[str]:
    """Return problem strings; empty means the attempt is usable evidence."""
    problems: list[str] = []
    if timed_out and actions_emitted == 0:
        problems.append("gameplay_timeout_with_zero_actions")
    if actions_emitted == 0 and completion_tokens >= ZERO_ACTION_TOKEN_LIMIT:
        problems.append(
            f"zero_actions_after_{completion_tokens}_completion_tokens"
        )
    if actions_emitted == 0:
        problems.append("zero_game_actions")
    return problems


def recommend_timeout(previous_timeout: float, timed_out: bool) -> float:
    if not timed_out:
        return previous_timeout
    return min(600.0, max(DEFAULT_GAMEPLAY_TIMEOUT_S, previous_timeout * 2))

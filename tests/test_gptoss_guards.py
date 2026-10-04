from arc3.gptoss_guards import (
    DEFAULT_GAMEPLAY_TIMEOUT_S,
    recommend_timeout,
    validate_gameplay_outcome,
)


def test_zero_action_timeout_is_problem() -> None:
    problems = validate_gameplay_outcome(
        actions_emitted=0, completion_tokens=4025, timed_out=True
    )
    assert "gameplay_timeout_with_zero_actions" in problems
    assert "zero_game_actions" in problems


def test_success_has_no_problems() -> None:
    assert (
        validate_gameplay_outcome(
            actions_emitted=2, completion_tokens=100, timed_out=False
        )
        == []
    )


def test_recommend_timeout_doubles_on_timeout() -> None:
    assert recommend_timeout(60.0, timed_out=True) >= DEFAULT_GAMEPLAY_TIMEOUT_S

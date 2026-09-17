"""Run an agent across the public games and report RHAE plus throughput.

Throughput is reported next to the score because a change that improves reasoning
but cannot sustain the action rate is not an improvement. The budget is
0.577 actions/sec aggregate -- 110 games, 9 hours, depth 3.

    python -m arc3.evaluate --agent random --games ls20,ft09 --max-actions 200
"""

from __future__ import annotations

import argparse
import time

from arcengine import GameAction, GameState

from .agents.base import Agent, Observation
from .env import HIDDEN_GAMES, RUNTIME_SECONDS, baselines_by_game, grid_of, make_arcade
from .instrumentation import GameTrace, TraceRecorder
from .scoring import GameResult, RunResult, levels_from_action_log

# Aggregate action rate needed for depth 3 across the hidden set.
TARGET_ACTIONS_PER_SECOND = 0.577


def play_game(
    arcade,
    game_id: str,
    agent: Agent,
    baselines: list[int],
    max_actions: int = 400,
) -> GameResult:
    """Play one game, charging actions exactly as the scorecard does."""
    env = arcade.make(game_id)
    agent.reset(game_id)

    started = time.monotonic()
    actions = 0  # monotonic, mirrors scorecard.actions
    completions: list[int] = []  # cumulative action count at each level completion

    frame = env.reset()
    actions += 1  # a RESET is charged
    levels_seen = frame.levels_completed
    last_grid = grid_of(frame)

    while actions < max_actions:
        obs = Observation.from_frame(frame, actions, last_grid)
        last_grid = obs.grid
        if agent.is_done(obs) or frame.state == GameState.WIN:
            break

        if frame.state == GameState.GAME_OVER:
            frame = env.reset()
            actions += 1
            continue

        plan = agent.plan(obs)
        if not plan.actions:
            break

        for planned in plan.actions:
            if actions >= max_actions:
                break
            if planned.action not in [
                GameAction.from_id(a) for a in frame.available_actions
            ]:
                # Illegal actions still cost, so refuse to spend one.
                agent.on_mismatch(
                    Observation.from_frame(frame, actions, last_grid), planned
                )
                break

            frame = env.step(planned.action, planned.data)
            actions += 1

            if frame.levels_completed > levels_seen:
                for _ in range(frame.levels_completed - levels_seen):
                    completions.append(actions)
                levels_seen = frame.levels_completed

            if frame.state in (GameState.WIN, GameState.GAME_OVER):
                break

            if planned.expect:
                grid = grid_of(frame, last_grid)
                mismatch = any(
                    grid[r, c] != v for (r, c), v in planned.expect.items()
                )
                if mismatch:
                    agent.on_mismatch(
                        Observation.from_frame(frame, actions, last_grid), planned
                    )
                    break

        if frame.state == GameState.WIN:
            break

    return GameResult(
        game_id=game_id,
        total_levels=len(baselines),
        levels=levels_from_action_log(baselines, completions, actions),
        wall_seconds=time.monotonic() - started,
    )


def _record_game_trace(
    recorder: TraceRecorder | None, result: GameResult, abandon_reason: str = ""
) -> None:
    if recorder is None:
        return
    completed = [lv.index for lv in result.levels if lv.completed]
    recorder.record(
        GameTrace(
            game_id=result.game_id,
            wall_seconds=result.wall_seconds,
            actions=result.actions,
            levels_completed=result.levels_completed,
            level_indices_completed=completed,
            abandon_reason=abandon_reason,
            score=result.score,
        )
    )


def evaluate(
    agent: Agent,
    games: list[str] | None = None,
    max_actions: int = 400,
    scored_environments: int | None = None,
    trace_path: str | None = None,
) -> RunResult:
    arcade = make_arcade()
    baselines = baselines_by_game(arcade)
    targets = games or sorted(baselines)

    run = RunResult(scored_environments=scored_environments or len(targets))
    recorder = TraceRecorder(trace_path) if trace_path else None
    for game_id in targets:
        if game_id not in baselines:
            print(f"  skip {game_id}: no baseline data")
            continue
        result = play_game(arcade, game_id, agent, baselines[game_id], max_actions)
        _record_game_trace(recorder, result)
        run.games.append(result)
        rate = result.actions / result.wall_seconds if result.wall_seconds else 0.0
        print(
            f"  {game_id:<6} score {result.score:>6.2f} / ceiling {result.ceiling:>6.2f}"
            f"  depth {result.levels_completed}/{result.total_levels}"
            f"  actions {result.actions:>4}  {rate:>7.1f} act/s"
        )
    if recorder is not None:
        summary = recorder.write_summary(run.scored_environments)
        print(
            f"  trace coverage: touched {summary['games_touched']}"
            f" / scored {summary['scored_environments']}"
            f"  levels {summary['total_levels_completed']}"
        )
    return run


def report(run: RunResult) -> None:
    print(f"\n{'=' * 62}")
    print(f"  score            {run.score:.3f}   over {run.scored_environments} environments")
    print(f"  levels completed {sum(g.levels_completed for g in run.games)}")
    print(f"  actions          {run.actions}")
    print(f"  wall             {run.wall_seconds:.1f}s")
    print(f"  throughput       {run.actions_per_second:.2f} actions/sec", end="")
    if run.actions_per_second >= TARGET_ACTIONS_PER_SECOND:
        print(f"  (>= {TARGET_ACTIONS_PER_SECOND} target)")
    else:
        print(f"  (BELOW {TARGET_ACTIONS_PER_SECOND} target)")

    # What this pace implies for a real 9-hour run over the hidden set.
    if run.actions_per_second > 0:
        budget = RUNTIME_SECONDS * run.actions_per_second / HIDDEN_GAMES
        print(f"  projected         {budget:.0f} actions/game in a 9h run over {HIDDEN_GAMES} games")


def build_agent(name: str) -> Agent:
    if name == "random":
        from .agents.random_agent import RandomAgent

        return RandomAgent()
    if name == "heuristic":
        from .agents.heuristic import HeuristicAgent

        return HeuristicAgent()
    raise SystemExit(f"unknown agent: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default="random")
    parser.add_argument("--games", default="", help="comma-separated ids; default all")
    parser.add_argument("--max-actions", type=int, default=400)
    parser.add_argument(
        "--scored-environments",
        type=int,
        default=None,
        help=f"divisor for the total; use {HIDDEN_GAMES} to project the hidden set",
    )
    parser.add_argument(
        "--trace",
        default="",
        help="write per-game coverage JSONL to this path",
    )
    args = parser.parse_args()

    games = [g.strip() for g in args.games.split(",") if g.strip()] or None
    agent = build_agent(args.agent)
    print(f"agent: {agent.name}")
    run = evaluate(
        agent,
        games,
        args.max_actions,
        args.scored_environments,
        trace_path=args.trace or None,
    )
    report(run)


if __name__ == "__main__":
    main()

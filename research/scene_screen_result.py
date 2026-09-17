"""Verify saved scene-screen artifacts and reproduce the frozen gate decision."""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from arc3.duck_scene_adapter import scene_delivery_problems
from arc3.scoring import GameResult, LevelResult


def evaluate(data):
    arms = data["arms"]
    assert set(arms) == {"W", "C", "T", "W-repeat"}
    all_rows = []
    for name, arm in arms.items():
        rows, s = arm["games"], arm["summary"]
        assert len(rows) == 3 and all(r["terminal"] for r in rows)
        assert all(r["trial_id"] == name for r in rows)
        assert not s["validation_problems"]
        for row in rows:
            n = row["levels_completed"]
            game = GameResult(row["game_id"], row["number_of_levels"], [
                LevelResult(i+1, row["base_actions_per_level"][i],
                            row["actions_per_level"][i], True)
                for i in range(n)
            ])
            assert math.isclose(game.score, row["final_score"], abs_tol=1e-12)
        for summary_key, row_key in (("completed_levels", "levels_completed"),
                                     ("actions", "actions_taken"),
                                     ("llm_calls", "llm_calls"),
                                     ("generated_tokens", "generated_tokens")):
            assert s[summary_key] == sum(r[row_key] for r in rows)
        assert math.isclose(s["weighted_rhae"], sum(r["final_score"] for r in rows)/3,
                            abs_tol=1e-12)
        all_rows.extend(rows)
    assert not scene_delivery_problems(all_rows)
    game_ids = {r["game_id"] for r in arms["W"]["games"]}
    assert all({r["game_id"] for r in a["games"]} == game_ids for a in arms.values())
    levels = {a: arms[a]["summary"]["completed_levels"] for a in arms}
    by_game = {a: {r["game_id"]: r["levels_completed"] for r in arms[a]["games"]}
               for a in arms}
    repeat_difference = abs(levels["W"] - levels["W-repeat"])
    c_checks = {
        "beats_better_control_beyond_repeat_difference":
            levels["C"] - max(levels["W"], levels["W-repeat"]) > repeat_difference,
        "no_game_below_weaker_per_game_control": all(
            by_game["C"][g] >= min(by_game["W"][g], by_game["W-repeat"][g])
            for g in game_ids),
        "rhae_per_second_beats_weaker_control":
            arms["C"]["summary"]["weighted_rhae_per_gpu_second"] > min(
                arms[a]["summary"]["weighted_rhae_per_gpu_second"]
                for a in ("W", "W-repeat")),
    }
    weaker = min(("W", "W-repeat"), key=lambda a: levels[a])
    # An exact control-total tie is ambiguous for the per-game comparator;
    # expose both checks rather than choose the favorable control afterwards.
    weaker_controls = [a for a in ("W", "W-repeat") if levels[a] == levels[weaker]]
    t_checks = {
        "at_least_weaker_control_total": levels["T"] >= levels[weaker],
        "no_game_loses_more_than_one": all(
            by_game["T"][g] >= by_game[a][g] - 1
            for a in weaker_controls for g in game_ids),
    }
    return {"levels": levels, "repeat_difference": repeat_difference,
            "C_checks": c_checks, "C_promote": all(c_checks.values()),
            "T_weaker_controls": weaker_controls, "T_checks": t_checks,
            "T_viable": all(t_checks.values())}


if __name__ == "__main__":
    data = json.loads(Path(sys.argv[1]).read_text())
    print(json.dumps(evaluate(data), indent=2, sort_keys=True))

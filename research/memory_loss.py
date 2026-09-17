#!/usr/bin/env python3
"""Does wiping state at level transitions show up in our own action counts?

Duck clears its world model, goal model, action model, findings, questions and
plan at every level transition; only free-form cross-level notes survive
(tool_agent.py:1113, located by Codex). NOOA measured its memory system at
+11.8 RHAE against +8.5 for its world-model skill -- memory the larger lever,
in the one place the two were separated.

If that defect costs us, it should be visible WITHOUT a new run. Each level has a
human baseline, so `actions_taken / baseline` normalises away difficulty. An agent
that restarts goal discovery at every transition should get relatively WORSE as
level index rises.

    python research/memory_loss.py
"""
import json
import statistics
from collections import defaultdict

# Gate 2 per-game arrays, four arms (actions_per_level / base_actions_per_level).
GATE2 = {
    "seed0-control": {
        "bp35": ([39, 361], [21, 48], 1), "cd82": ([42, 52, 306], [55, 8, 41], 2),
        "ka59": ([27, 58, 315], [28, 109, 51], 2),
        "lp85": ([6, 22, 19, 28, 14, 23, 55, 57], [17, 38, 31, 16, 41, 60, 26, 159], 8),
        "ls20": ([16, 384], [22, 123], 1), "sp80": ([308, 92], [39, 58], 1),
    },
    "seed1-control": {
        "bp35": ([68, 316], [21, 48], 1), "cd82": ([81, 319], [55, 8], 1),
        "g50t": ([151, 249], [78, 175], 1), "ka59": ([26, 98, 276], [28, 109, 51], 2),
        "lp85": ([6, 394], [17, 38], 1), "ls20": ([19, 381], [22, 123], 1),
        "sp80": ([385, 15], [39, 58], 1), "tn36": ([30, 108, 262], [32, 72, 26], 2),
    },
}


def ratios_by_index(taken, base, completed):
    """(level index, actions/baseline) for COMPLETED levels only."""
    out = []
    for i in range(completed):
        if i < len(base) and base[i] > 0 and taken[i] > 0:
            out.append((i + 1, taken[i] / base[i]))
    return out


def main() -> None:
    by_index: dict[int, list[float]] = defaultdict(list)

    for game in json.load(open("research/gate1-run1-levels.json")):
        for index, ratio in ratios_by_index(game["actions_per_level"],
                                            game["base_actions_per_level"],
                                            game["levels_completed"]):
            by_index[index].append(ratio)
    run1_only = {k: list(v) for k, v in by_index.items()}

    for arm in GATE2.values():
        for taken, base, completed in arm.values():
            for index, ratio in ratios_by_index(taken, base, completed):
                by_index[index].append(ratio)

    print("ACTIONS RELATIVE TO EACH LEVEL'S OWN HUMAN BASELINE, BY LEVEL INDEX")
    print("(baselines already encode difficulty, so this is difficulty-adjusted)\n")
    print(f"{'level':>6}{'n':>5}{'median':>9}{'mean':>8}{'worse than human':>19}")
    for index in sorted(by_index):
        vals = by_index[index]
        worse = sum(1 for v in vals if v > 1.0) / len(vals)
        print(f"{index:>6}{len(vals):>5}{statistics.median(vals):>9.2f}"
              f"{statistics.mean(vals):>8.2f}{worse:>18.0%}")

    early = [v for i, vals in by_index.items() if i == 1 for v in vals]
    later = [v for i, vals in by_index.items() if i >= 2 for v in vals]
    print(f"\n  level 1        n={len(early):>3}  median {statistics.median(early):.2f}")
    print(f"  levels 2+      n={len(later):>3}  median {statistics.median(later):.2f}")

    print("\nTHE SELECTION EFFECT RUNS AGAINST THE HYPOTHESIS.")
    print("  A game only reaches level 5 if the agent understands it, so deep")
    print("  levels are sampled from games we are GOOD at. That biases the deep")
    print("  rows to look better. Degradation surviving that bias would be strong;")
    print("  flat or improving numbers are therefore weak evidence either way.\n")

    print("VERDICT")
    if statistics.median(later) > statistics.median(early) * 1.25:
        print("  Later levels cost relatively MORE. Consistent with state being")
        print("  wiped at transitions, and it survives a bias pointing the other way.")
    elif statistics.median(later) < statistics.median(early) * 0.8:
        print("  Later levels cost relatively LESS -- but that is what the selection")
        print("  effect alone predicts, so it does not clear the memory hypothesis.")
    else:
        print("  Flat. These aggregates do NOT detect the memory defect, and the")
        print("  selection effect means they could not have detected a modest one.")
    print("\n  Either way this is the wrong instrument: level-total action counts")
    print("  cannot see WITHIN a level, and a wipe costs most in the actions just")
    print("  AFTER a transition. The right measurement is actions-to-first-progress")
    print("  after each level change, which needs the transition ledger -- one more")
    print("  reason the ledger is on the critical path rather than beside it.")


if __name__ == "__main__":
    main()

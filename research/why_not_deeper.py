#!/usr/bin/env python3
"""Why do levels not get cleared? Asked of data already on disk, no GPU.

Gate 2 produced 32 game-runs: 8 games x 4 arms, with per-game levels, actions,
calls, tokens and no-ops. The cap verdict used the aggregates. Nobody looked at
the per-game rows, and they answer a question the aggregates cannot: when the
agent fails, HOW does it fail?

    python research/why_not_deeper.py
"""

# game: (levels, total, actions, score, tokens, calls, no_ops)
ARMS = {
    "seed0-control": {
        "bp35": (1, 9, 400, 0.6443129520052597, 216754, 215, 0),
        "cd82": (2, 6, 400, 5.701606086221471, 177203, 146, 64),
        "g50t": (0, 7, 400, 0.0, 280174, 160, 104),
        "ka59": (2, 7, 400, 10.714285714285714, 110990, 100, 26),
        "lp85": (8, 8, 224, 87.83449991566874, 316063, 196, 25),
        "ls20": (1, 7, 400, 3.571428571428571, 190679, 130, 45),
        "sp80": (1, 6, 400, 0.07634990241669276, 116354, 72, 0),
        "tn36": (0, 7, 400, 0.0, 83574, 56, 0),
    },
    "seed1-control": {
        "bp35": (1, 9, 384, 0.2119377162629758, 361756, 301, 0),
        "cd82": (1, 6, 400, 2.195513169450069, 112859, 123, 43),
        "g50t": (1, 7, 400, 0.952965722054797, 199153, 162, 72),
        "ka59": (2, 7, 400, 10.714285714285714, 104519, 92, 27),
        "lp85": (1, 8, 400, 2.7777777777777777, 38538, 46, 63),
        "ls20": (1, 7, 400, 3.571428571428571, 96701, 93, 8),
        "sp80": (1, 6, 400, 0.048863937546683375, 148452, 86, 0),
        "tn36": (2, 7, 400, 7.238095238095238, 248337, 197, 0),
    },
    "seed0-cap1024": {
        "bp35": (1, 9, 400, 0.008629115339573298, 169809, 253, 0),
        "cd82": (2, 6, 400, 2.431112217899775, 158179, 217, 65),
        "g50t": (1, 7, 332, 3.571428571428571, 187865, 288, 61),
        "ka59": (1, 7, 400, 2.160493827160494, 165573, 255, 52),
        "lp85": (4, 8, 165, 15.716365069961613, 217784, 293, 17),
        "ls20": (1, 7, 400, 3.0009920634920633, 179237, 244, 11),
        "sp80": (1, 6, 400, 0.08854781582054308, 88732, 136, 0),
        "tn36": (0, 7, 400, 0.0, 62562, 93, 0),
    },
    "seed1-cap1024": {
        "bp35": (1, 9, 308, 0.39199999999999996, 218313, 350, 0),
        "cd82": (2, 6, 400, 0.848890415465634, 119026, 167, 65),
        "g50t": (1, 7, 400, 1.970845481049563, 156415, 210, 101),
        "ka59": (1, 7, 400, 2.285714285714286, 136098, 198, 89),
        "lp85": (3, 8, 379, 13.059172453703704, 229832, 310, 10),
        "ls20": (1, 7, 400, 0.20873945520727313, 88289, 122, 7),
        "sp80": (1, 6, 400, 1.6134678420265414, 82341, 116, 0),
        "tn36": (0, 7, 400, 0.0, 220332, 247, 0),
    },
}
GAMES = sorted(ARMS["seed0-control"])
CONTROL = ["seed0-control", "seed1-control"]


def rows(arms):
    for arm in arms:
        for game, (lv, tot, act, sc, tok, calls, noop) in ARMS[arm].items():
            yield arm, game, lv, tot, act, sc, tok, calls, noop


def main() -> None:
    print("FAILURE MODE: the agent is not flailing.\n")
    stuck = [(a, g, act, noop, calls) for a, g, lv, _, act, _, _, calls, noop
             in rows(ARMS) if lv == 0]
    print(f"{'arm':<15}{'game':<7}{'actions':>8}{'no-ops':>8}{'no-op rate':>11}{'calls':>7}")
    for arm, game, act, noop, calls in stuck:
        print(f"{arm:<15}{game:<7}{act:>8}{noop:>8}{noop / act:>10.1%}{calls:>7}")
    print("\n  These games took hundreds of VALID actions that changed the board and")
    print("  still cleared nothing. tn36 twice: 400 actions, ZERO no-ops, no level.")
    print("  The agent is not failing to operate the game. It does not know what")
    print("  the game wants. That is goal discovery, not action semantics.\n")

    print("THE THING NOBODY LOOKED AT: reasoning density per game.\n")
    print("Same game, same configuration, different seed:\n")
    print(f"{'game':<7}{'seed0 lv':>9}{'a/call':>8}{'   |':>4}{'seed1 lv':>9}{'a/call':>8}")
    denser_wins = ties = denser_loses = 0
    for game in GAMES:
        l0, _, a0, _, _, c0, _ = ARMS["seed0-control"][game]
        l1, _, a1, _, _, c1, _ = ARMS["seed1-control"][game]
        d0, d1 = a0 / c0, a1 / c1
        print(f"{game:<7}{l0:>9}{d0:>8.2f}{'   |':>4}{l1:>9}{d1:>8.2f}")
        if l0 == l1:
            ties += 1
        elif (l0 > l1) == (d0 < d1):
            denser_wins += 1
        else:
            denser_loses += 1
    print(f"\n  Of {len(GAMES)} games, {ties} tied. Of the {denser_wins + denser_loses} that differed,")
    print(f"  the arm taking FEWER actions per call cleared more in {denser_wins}.")

    print("\n  tn36 is the cleanest case:")
    print("    seed0-control  400 actions,  56 calls = 7.14 a/call -> 0 levels")
    print("    seed1-control  400 actions, 197 calls = 2.03 a/call -> 2 levels")
    print("  Same game, same config. The run that reasoned 3.5x more often solved")
    print("  two levels; the run that batched 7 actions per call solved none.\n")

    print("ACROSS ALL 32 GAME-RUNS\n")
    cleared = [(a / c, lv) for _, _, lv, _, a, _, _, c, _ in rows(ARMS)]
    for lo, hi, label in ((0, 1.5, "< 1.5"), (1.5, 2.5, "1.5-2.5"),
                          (2.5, 4.0, "2.5-4.0"), (4.0, 99, ">= 4.0")):
        band = [lv for d, lv in cleared if lo <= d < hi]
        if band:
            print(f"  actions/call {label:<8} n={len(band):>2}   mean levels "
                  f"{sum(band) / len(band):>4.2f}")
    print("\n  The obvious confound runs the WRONG way. An agent executing a known")
    print("  plan should take MORE actions per call, so a solver ought to look")
    print("  batchier. We observe the opposite, which strengthens rather than")
    print("  explains the pattern.\n")

    print("IS DENSITY A CAUSE OR A SYMPTOM? GATE 2 ALREADY RAN THAT EXPERIMENT.\n")
    cap = [ARMS[a] for a in ("seed0-cap1024", "seed1-cap1024")]
    ctl = [ARMS[a] for a in CONTROL]
    cap_ac = sum(g[2] for arm in cap for g in arm.values()) / sum(
        g[5] for arm in cap for g in arm.values())
    ctl_ac = sum(g[2] for arm in ctl for g in arm.values()) / sum(
        g[5] for arm in ctl for g in arm.values())
    cap_lv = sum(g[0] for arm in cap for g in arm.values())
    ctl_lv = sum(g[0] for arm in ctl for g in arm.values())
    print(f"  control  actions/call {ctl_ac:.2f}   levels {ctl_lv}")
    print(f"  cap1024  actions/call {cap_ac:.2f}   levels {cap_lv}")
    print(f"  The cap FORCED density up ({ctl_ac:.2f} -> {cap_ac:.2f} actions per call)")
    print(f"  and levels went DOWN, {ctl_lv} -> {cap_lv}.\n")
    print("  So low actions-per-call does not CAUSE solving. It is a SYMPTOM of")
    print("  the model having a specific hypothesis to test one step at a time;")
    print("  a confused model emits a long speculative batch instead. Forcing the")
    print("  ratio -- in either direction -- moves the symptom and not the cause.")
    print("  That kills 'make reasoning denser' before it costs anything, and it")
    print("  is the second lever Gate 2 has eliminated from data already on disk.\n")

    print("WHAT HAS NEVER BEEN DONE\n")
    ctl_calls = sum(g[5] for arm in ctl for g in arm.values())
    print(f"  {ctl_calls} control LLM calls were saved with their transcripts.")
    print("  Nobody has read one. Four versions of a verifier have been built for")
    print("  a model whose output has never been examined.\n")
    print("  Twenty transcripts from tn36 -- 400 valid actions, zero no-ops, zero")
    print("  levels -- would separate three failure modes with different fixes:")
    print("    A  no hypothesis at all           -> the prompt never asks for one")
    print("    B  a hypothesis, never tested     -> needs prediction + checking")
    print("    C  a correct hypothesis it cannot execute -> needs planning/search")
    print("  Only C is what the verified-simulator bet is designed to fix.")


if __name__ == "__main__":
    main()

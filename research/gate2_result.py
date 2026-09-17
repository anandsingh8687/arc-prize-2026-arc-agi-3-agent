#!/usr/bin/env python3
"""Gate 2: the 1024-token cap, read per run-discipline rules 6 and 7.

Kaggle script version 350147858, four trials, 2026-09-16. The cap is rejected.
This script separates the part of that verdict the data RESOLVES from the part
it does not, because they point at different next steps.

    python research/gate2_result.py
"""

TRIALS = {  # arm -> (rhae, levels, actions, calls, tokens, gpu_s, length_rate)
    "seed0-control": (13.567810392753307, 15, 3024, 1075, 1491791, 6535.040727365, 0.0037209302325581397),
    "seed0-cap1024": (3.372196085137829, 11, 2897, 1779, 1229741, 6602.896265138, 0.26812816188870153),
    "seed1-control": (3.4638584808627284, 10, 3184, 1100, 1310315, 6602.985741615001, 0.0009090909090909091),
    "seed1-cap1024": (2.547353741645875, 10, 3087, 1720, 1250646, 6601.780296954001, 0.32790697674418606),
}

# seed0-control's lp85 alone: won 8/8, game score 87.83449991566874 over 8 games.
LP85_SEED0_CONTROL = 87.83449991566874
GAMES = 8

# Run 1 restricted to these same eight games (research/v7_subset.py).
RUN1_SUBSET = 9.45


def pct(new: float, old: float) -> str:
    return f"{(new / old - 1) * 100:+.1f}%"


def main() -> None:
    c0, k0 = TRIALS["seed0-control"], TRIALS["seed0-cap1024"]
    c1, k1 = TRIALS["seed1-control"], TRIALS["seed1-cap1024"]

    print("WHAT THE DATA RESOLVES -- thousands of calls per arm\n")
    ctrl_calls, cap_calls = c0[3] + c1[3], k0[3] + k1[3]
    ctrl_tok, cap_tok = c0[4] + c1[4], k0[4] + k1[4]
    ctrl_act, cap_act = c0[2] + c1[2], k0[2] + k1[2]
    ctrl_len = (c0[6] * c0[3] + c1[6] * c1[3]) / ctrl_calls
    cap_len = (k0[6] * k0[3] + k1[6] * k1[3]) / cap_calls

    print(f"{'':<18}{'control':>12}{'cap1024':>12}{'change':>12}{'samples':>10}")
    for label, a, b, n in (
        ("length-limit rate", ctrl_len, cap_len, f"{ctrl_calls}/{cap_calls}"),
        ("tokens per call", ctrl_tok / ctrl_calls, cap_tok / cap_calls, f"{ctrl_calls}/{cap_calls}"),
        ("actions per call", ctrl_act / ctrl_calls, cap_act / cap_calls, f"{ctrl_calls}/{cap_calls}"),
        ("tokens per action", ctrl_tok / ctrl_act, cap_tok / cap_act, f"{ctrl_act}/{cap_act}"),
    ):
        print(f"{label:<18}{a:>12.4f}{b:>12.4f}{pct(b, a):>12}{n:>10}")

    print(f"\nThe mechanism, and it closes exactly:")
    print(f"  tokens/call {pct(cap_tok / cap_calls, ctrl_tok / ctrl_calls)}"
          f"  x  calls {pct(cap_calls, ctrl_calls)}"
          f"  =  total tokens {pct(cap_tok, ctrl_tok)}")
    print("  The cap did not make decisions cheaper. It TRUNCATED them mid-plan,")
    print(f"  on {cap_len:.1%} of calls against {ctrl_len:.2%}, so the agent needed"
          f" {pct(cap_calls, ctrl_calls)} more of them")
    print(f"  and recovered only {pct(cap_tok / cap_act, ctrl_tok / ctrl_act)} on tokens per action.\n")

    print("WHAT THE DATA DOES NOT RESOLVE -- eight games, two seeds\n")
    print(f"  control RHAE by seed   {c0[0]:.3f} and {c1[0]:.3f}"
          f"   spread {c0[0] / c1[0]:.2f}x")
    print(f"  cap     RHAE by seed   {k0[0]:.3f} and {k1[0]:.3f}"
          f"   spread {k0[0] / k1[0]:.2f}x")
    print(f"  control levels by seed {c0[1]} and {c1[1]}"
          f"        spread {c0[1] / c1[1]:.2f}x")
    print(f"  cap     levels by seed {k0[1]} and {k1[1]}"
          f"        spread {k0[1] / k1[1]:.2f}x")
    print("\n  The control arm's own seed-to-seed spread on RHAE is LARGER than the")
    print("  control-versus-cap difference. The -65% headline is not a measurement.\n")

    others = (c0[0] * GAMES - LP85_SEED0_CONTROL) / GAMES
    print(f"  seed0-control scored {c0[0]:.3f}. lp85 alone (won 8/8) contributes"
          f" {LP85_SEED0_CONTROL / GAMES:.3f}")
    print(f"  of that -- {LP85_SEED0_CONTROL / GAMES / c0[0]:.0%}. The other seven games total {others:.3f}.")
    print("  One game winning in one of four trials drives the headline.\n")

    print("PAIRED BY SEED -- the comparison that is actually paired\n")
    print(f"{'':<10}{'RHAE control':>14}{'RHAE cap':>10}{'ratio':>8}"
          f"{'levels c':>10}{'levels k':>10}{'delta':>7}")
    for name, c, k in (("seed0", c0, k0), ("seed1", c1, k1)):
        print(f"{name:<10}{c[0]:>14.3f}{k[0]:>10.3f}{k[0] / c[0]:>8.3f}"
              f"{c[1]:>10}{k[1]:>10}{k[1] - c[1]:>+7}")
    print("\n  Both RHAE ratios are below 1, so the DIRECTION is consistent, but they")
    print("  differ 3x from each other. Levels move -4 and 0: same direction,")
    print("  far better behaved.\n")

    rh_spread = max(c0[0] / c1[0], c1[0] / c0[0])
    lv_spread = max(c0[1] / c1[1], c1[1] / c0[1])
    print(f"CONSEQUENCE FOR E2. On identical configurations at different seeds,")
    print(f"  RHAE varied {rh_spread:.2f}x and cleared levels varied {lv_spread:.2f}x --")
    print(f"  levels are {rh_spread / lv_spread:.1f}x more stable. Gating on cleared levels")
    print("  rather than score was the right call and is now measured, not argued.")
    print("  It is also the first direct read of SEED sensitivity, which is why E2")
    print("  still needs its same-seed W-repeat arm: this is not that number.\n")

    ctrl_mean = (c0[0] + c1[0]) / 2
    print(f"CONSISTENCY CHECK. Control mean {ctrl_mean:.3f} against run 1 restricted to")
    print(f"  these same eight games, {RUN1_SUBSET:.2f} ({pct(ctrl_mean, RUN1_SUBSET)}). The subset")
    print("  baseline holds; the agent has not regressed.\n")

    print("DOES THIS RUN PRICE PLAN BATCHING? NO -- and here is the check.\n")
    # Tempting: fit tokens/call = F + M x (actions/call) across the two arms and
    # read F as the fixed per-call overhead batching would amortise.
    tpc_c, apc_c = ctrl_tok / ctrl_calls, ctrl_act / ctrl_calls
    tpc_k, apc_k = cap_tok / cap_calls, cap_act / cap_calls
    marginal = (tpc_c - tpc_k) / (apc_c - apc_k)
    fixed = tpc_c - marginal * apc_c
    print(f"  marginal tokens per action in plan   {marginal:>9.1f}")
    print(f"  implied fixed cost per call          {fixed:>9.1f}   <- NEGATIVE")
    print("  A negative fixed overhead is nonsense, so the linear model does not")
    print("  fit these two points. It should not: truncating a response is not the")
    print("  same intervention as ASKING for a different plan length. The cap")
    print("  clipped the output distribution; batching changes what is requested.")
    print("  This run therefore says nothing about batching in either direction,")
    print("  and projecting headroom from it would repeat the error it just")
    print("  corrected -- rejecting one token lever is not rejecting the class.\n")

    print("TOKENS PER COMPLETED LEVEL -- the capacity metric, and the actual verdict")
    print(f"  control {ctrl_tok / (c0[1] + c1[1]):>10,.0f}")
    print(f"  cap1024 {cap_tok / (k0[1] + k1[1]):>10,.0f}"
          f"   {pct(cap_tok / (k0[1] + k1[1]), ctrl_tok / (c0[1] + c1[1]))} -- WORSE")
    print("  This is why the cap is rejected. Not the score.")


if __name__ == "__main__":
    main()

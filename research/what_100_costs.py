#!/usr/bin/env python3
"""What the 100-point public systems actually cost, in our budget's units.

RETRACTED AND CORRECTED. An earlier version of this script divided the public
systems' TOTAL token counts by our GENERATED-token budget and reported gaps of
423x to 2,546x. That is apples to oranges: Retrodict's 660M is overwhelmingly
CACHED INPUT -- 629M of it -- and cached input cannot be charged against an
output budget. On generated tokens the gap is 4x to 14x, which is a different
conclusion and a much more hopeful one.

What survives: every system at 95-100 is an open-source HARNESS driving a
closed, online frontier model, and Kaggle gives us one GPU, nine hours and no
internet.

Third-party numbers, unverified here. Sources in research/competitor-survey.md.

    python research/what_100_costs.py
"""

PUBLIC_GAMES = 25
OUR_TOKENS_PER_GAME = 6_860_000 / 110  # 9h budget / hidden games

# (label, public score, GENERATED/output tokens over the 25 public games, class).
# Output only -- the published breakdowns separate cached input, which is what
# the retracted version wrongly folded in.
SYSTEMS = [
    ("Tycho",             100.00, None,        "closed frontier, online"),
    ("Retrodict",          99.86, 7_400_000,   "closed frontier, online"),
    ("baseline1 textual",  95.97, 6_400_000,   "closed frontier, online"),
    ("baseline1 exec",     98.77, 21_500_000,  "closed frontier, online"),
    ("PRO-LONG",           97.40, None,        "closed frontier, online"),
    ("OPINE-World",        78.40, None,        "closed frontier, online"),
    ("Polyphony",          19.80, None,        "open weights, but 8 GPUs / 24 h"),
]

# Tycho's same-model ablation -- the only architecture measurement that holds
# the model fixed.
TYCHO = [
    ("no world model",            79.07),
    ("single actor-written model", 85.36),
    ("actor-controlled builder",   88.49),
    ("auto-triggered builder",     83.07),
]

OUR_LOCAL = 5.2652
# Polyphony's published reproduction command, read 2026-09-15.
POLY_GPUS, POLY_CONCURRENT, POLY_SECONDS_PER_GAME = 8, 5, 14_400
RATIOS = {"best": 2.2216, "mean of three": 2.7674, "worst": 3.4061}
RANK_3_HIDDEN, RANK_1_HIDDEN = 8.44, 18.81


def main() -> None:
    print(f"our per-game budget: {OUR_TOKENS_PER_GAME:,.0f} generated tokens\n")
    print(f"{'system':<20}{'score':>7}{'tokens/game':>14}{'vs ours':>10}  model")
    for label, score, tokens, cls in SYSTEMS:
        if tokens is None:
            print(f"{label:<20}{score:>7.2f}{'not published':>14}{'':>10}  {cls}")
            continue
        per_game = tokens / PUBLIC_GAMES
        print(f"{label:<20}{score:>7.2f}{per_game:>14,.0f}"
              f"{per_game / OUR_TOKENS_PER_GAME:>9,.0f}x  {cls}")

    print("\nOn GENERATED tokens the gap is 4x to 14x, not the 400-2,500x an")
    print("earlier version of this script reported by folding in cached input.")
    print("Their contexts are far larger too, which prefill and prefix caching")
    print("make cheap but not free. 4-14x is a gap selective modelling can")
    print("plausibly attack; 400x would not have been.\n")

    print("BASELINE1's OWN ABLATION -- what full executable modelling buys")
    t_score, t_tok = SYSTEMS[2][1], SYSTEMS[2][2]
    e_score, e_tok = SYSTEMS[3][1], SYSTEMS[3][2]
    print(f"  textual    {t_score} at {t_tok / 1e9:.2f}B tokens")
    print(f"  executable {e_score} at {e_tok / 1e9:.2f}B tokens")
    print(f"  +{e_score - t_score:.2f} points for {e_tok / t_tok:.1f}x the generated tokens.")
    print("  Comprehensive modelling is the part we cannot afford; SELECTIVE")
    print("  modelling is the whole bet.\n")

    print("TYCHO'S SAME-MODEL ABLATION -- architecture, model held fixed")
    base = TYCHO[0][1]
    for label, score in TYCHO:
        print(f"  {label:<28}{score:>7.2f}   {score / base:.3f}x")
    best = max(s for _, s in TYCHO)
    print(f"\n  NEITHER transfer form is supported. Adding {best - base:+.2f} points to our"
          f" {OUR_LOCAL}")
    print(f"  is wrong, and so is multiplying by {best / base:.3f}x -- an earlier version of")
    print("  this script did the second and called it a prediction. One run per")
    print("  policy, one model, one budget, from a base of 79.07.")
    print("  The only supported statement: actor-controlled modelling had a POSITIVE")
    print("  effect at frontier capability. The effect size at Qwen capability is")
    print("  UNKNOWN and has to be measured -- which is what E0 is for.")
    print(f"  Also: the auto-triggered builder did NOT lose to no builder"
          f" ({TYCHO[3][1]} beats {base});")
    print(f"  it lost {TYCHO[2][1] - TYCHO[3][1]:.2f} to letting the actor choose.\n")

    print("POLYPHONY IS OPEN-WEIGHT BUT NOT UNDER OUR CONSTRAINTS")
    poly = SYSTEMS[-1][1]
    # Verified from the repository's own reproduction command, 2026-09-15.
    poly_gpu_s = POLY_GPUS / POLY_CONCURRENT * POLY_SECONDS_PER_GAME
    ours_gpu_s = 9 * 3600 / 110
    print(f"  repo command: --tensor-parallel-size {POLY_GPUS}, --max-model-len 262144,")
    print(f"                --per-game-deadline-s {POLY_SECONDS_PER_GAME},"
          f" 24 h window, {POLY_CONCURRENT} concurrent")
    print(f"  that is <= {poly_gpu_s:,.0f} GPU-seconds per game against our {ours_gpu_s:,.1f}"
          f"  -> up to {poly_gpu_s / ours_gpu_s:.0f}x")
    print(f"  and <= {POLY_GPUS * 24:.0f} GPU-hours against our 9  -> up to {POLY_GPUS * 24 / 9:.1f}x")
    print("  THESE ARE CONFIGURED CEILINGS, NOT MEASURED CONSUMPTION. 192 is simply")
    print("  8 GPUs x the 24 h window; 25 games in 5 waves of 4 h is 160 GPU-hours")
    print("  at full cap, before overhead. Actual use is unpublished and lower.\n")
    print(f"  An earlier version of this script called {poly} \"demonstrated at open")
    print("  weights on one GPU\". That was asserted without reading the repository")
    print("  and is false. Converting it through our transfer ratios is therefore")
    print("  speculative twice over -- an unverified score under 78x our per-game")
    print("  compute, pushed through a ratio estimated from three configurations:")
    for name, r in RATIOS.items():
        hidden = poly / r
        rank = ("above the rank-3 cut" if hidden >= RANK_3_HIDDEN
                else "BELOW the rank-3 cut")
        print(f"    ratio {r:.3f} ({name:<13}) -> hidden {hidden:>5.2f}   {rank}")
    print(f"\n  Rank 3 is {RANK_3_HIDDEN}. Only the BEST ratio clears it. Treat {poly} as an")
    print("  aspirational architecture reference, not a calibrated forecast and not")
    print("  evidence that the prize cut is already within reach.")


if __name__ == "__main__":
    main()

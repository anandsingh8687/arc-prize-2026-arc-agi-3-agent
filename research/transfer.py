#!/usr/bin/env python3
"""Local-to-hidden transfer: THREE configurations, five hidden draws.

Until 2026-09-15 the plan rested on one pairing -- our Version 7's local 5.2652
against hidden 2.37 -- and every "local equivalent" in this repository came from
it. The competitor survey adds two more configurations.

CORRECTED. An earlier version of this script treated the five hidden draws as
five observations and averaged their ratios, which double-weights the two
configurations that submitted twice. Draws are averaged within a configuration
first; the ratio is then per configuration, n=3.

The numbers are third-party and unverified here. Sources in
research/competitor-survey.md.

    python research/transfer.py
"""

RANK_1_HIDDEN = 18.81
OUR_HIDDEN = 2.37

# label -> (local, [hidden draws])
CONFIGS = {
    "us, Version 7":    (5.2652, [2.37]),
    "animation solver": (9.5584, [3.74, 3.41]),
    "competitor":      (10.9337, [3.60, 2.82]),
}


def main() -> None:
    print(f"{'configuration':<20}{'local':>9}{'draws':>16}{'mean':>7}{'ratio':>8}")
    rows = []
    for label, (local, draws) in CONFIGS.items():
        hidden = sum(draws) / len(draws)
        ratio = local / hidden
        rows.append((local, ratio))
        shown = "/".join(f"{d:.2f}" for d in draws)
        print(f"{label:<20}{local:>9.4f}{shown:>16}{hidden:>7.3f}{ratio:>8.3f}")

    ratios = [r for _, r in rows]
    mean = sum(ratios) / len(ratios)
    print(f"\nn = {len(rows)} configurations (not 5). ratio min {min(ratios):.3f}"
          f"  mean {mean:.3f}  max {max(ratios):.3f}")
    print(f"our {rows[0][1]:.4f} is the BEST of the three; every target stated from")
    print("it alone is the easiest case.\n")

    print("THE RATIO FRAMING ASSUMES PROPORTIONALITY, WHICH THREE POINTS CANNOT TEST.")
    print("If the relationship is additive or saturating rather than multiplicative,")
    print("these conversions are wrong in a way no amount of averaging fixes. Treat")
    print("what follows as a STRESS RANGE for planning, never as a target band.\n")

    print("ordered by local score:")
    for local, ratio in sorted(rows):
        print(f"  local {local:>8.4f}   ratio {ratio:.3f}")
    print("  Direction: the highest local score transfers worst -- the shape that")
    print("  overfitting to 25 public games would produce. THREE points. A caution,")
    print("  not a finding, recorded because it is the direction that would hurt.\n")

    print("HIDDEN-SIDE VARIABILITY -- two configurations, two draws each")
    for label, (_, draws) in CONFIGS.items():
        if len(draws) < 2:
            continue
        m = sum(draws) / len(draws)
        print(f"  {label:<18}{draws[0]} and {draws[1]}   +/-{abs(draws[0] - draws[1]) / 2 / m:.1%}")
    print("  Two pairs cannot establish a noise floor. The usable conclusion is")
    print(f"  weaker than previously stated: a move from {OUR_HIDDEN} to about 2.7 COULD")
    print("  be noise, so do not spend a daily submission on a small predicted gain.\n")

    print(f"STRESS RANGE -- what local score might rank 1's {RANK_1_HIDDEN} correspond to?")
    for name, r in (("best observed", min(ratios)), ("mean of three", mean),
                    ("worst observed", max(ratios))):
        print(f"  ratio {r:.3f}  ({name:<14})  local {RANK_1_HIDDEN * r:>6.1f}")


if __name__ == "__main__":
    main()

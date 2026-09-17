#!/usr/bin/env python3
"""Arithmetic behind research/gate1-analysis.md. No dependencies, no network."""

import math

# Measured in Gate 1 run 1.
# Exact values as reported, so this reproduces the figures quoted in
# gate1-analysis.md rather than a rounded approximation of them.
COLD_START_S = 591.0260334014893
WAVE_SECONDS = 7920.127764303001  # median per-game consumption, 25 games at 28
GAME_CONCURRENCY = 28
# Competition constants.
HIDDEN_GAMES, RUNTIME_S = 110, 9 * 3600

# The KV-cache and efficiency sections of this script were REMOVED in v2: both
# rested on figures that do not apply. The 55.23 GiB KV measurement came from the
# fp8-repacked checkpoint (28.51 GiB of weights), while Gate 1 runs
# Qwen3.8-Flash-Next-NVFP4 (81.8 GiB of weights) -- memory figures are
# per-checkpoint and do not transfer. The efficiency estimate divided total
# actions by completed levels and compared against a mean level-1 baseline, which
# is not how RHAE works. Use research/per_level_efficiency.py instead.


def fit(concurrency: int, wave_s: float = WAVE_SECONDS) -> tuple[int, float]:
    """Waves needed for the hidden set, and the margin left in the 9 hours."""
    waves = math.ceil(HIDDEN_GAMES / concurrency)
    return waves, RUNTIME_S - (COLD_START_S + waves * wave_s)


def main() -> None:
    print("9-HOUR FIT")
    for c in (GAME_CONCURRENCY, 37, 55):
        waves, margin = fit(c)
        print(f"  concurrency {c:>3}: {waves} waves, margin {margin:>12.6f} s"
              f"  = {margin/60:>7.2f} min  ({margin/RUNTIME_S*100:+.1f}%)")

    print("\n  Concurrency changes trade depth per game against coverage and are")
    print("  NOT established as improvements -- they need a score-per-GPU-second")
    print("  ablation. The only supported conclusion is that the current")
    print("  configuration does not fit with a safe margin.")


if __name__ == "__main__":
    main()

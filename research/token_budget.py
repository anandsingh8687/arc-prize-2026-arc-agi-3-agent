#!/usr/bin/env python3
"""Token-budget arithmetic behind research/token-budget.md. No dependencies."""

# Exact-checkpoint probe, Qwen3.8-Flash-Next-NVFP4, 8k prompts.
AGGREGATE_TOK_S = 254.92803868668747  # C16; flat from C8 to C32
COLD_START_S = 625.0732558699999
KV_TOKENS = 42_910

# Gate 1 run 1.
RUN1 = dict(tokens=1_958_045, games=25, actions=3563, calls=1358, levels=40)

RUNTIME_S, HIDDEN_GAMES, SAFETY = 9 * 3600, 110, 0.15


def budget(with_margin: bool = True) -> float:
    """Generated tokens available in one competition run."""
    seconds = RUNTIME_S - COLD_START_S - (SAFETY * RUNTIME_S if with_margin else 0)
    return seconds * AGGREGATE_TOK_S


def main() -> None:
    safe = budget()
    print(f"budget: {budget(False)/1e6:.2f}M tokens, {safe/1e6:.2f}M within the 15% margin\n")

    per_game = RUN1["tokens"] / RUN1["games"]
    allowed = safe / HIDDEN_GAMES
    print(f"run 1 spent {per_game/1000:.1f}k tokens/game; "
          f"110 games allows {allowed/1000:.1f}k "
          f"({(1-allowed/per_game)*100:.0f}% less)")

    per_level = RUN1["tokens"] / RUN1["levels"]
    print(f"\ntokens per completed level: {per_level:,.0f}")
    print(f"  the budget buys {safe/per_level:.0f} levels = "
          f"{safe/per_level/HIDDEN_GAMES:.2f} per game "
          f"(run 1 managed {RUN1['levels']/RUN1['games']:.2f} on 25 games)")
    for depth in (2, 3):
        need = safe / (depth * HIDDEN_GAMES)
        print(f"  {depth} levels/game needs {need:,.0f} tokens/level "
              f"({(1-need/per_level)*100:.0f}% reduction)")

    print("\nPLAN BATCHING (tokens per call held flat -- must be verified, not assumed)")
    tok_per_call = RUN1["tokens"] / RUN1["calls"]
    now = RUN1["actions"] / RUN1["games"]
    for a in (RUN1["actions"] / RUN1["calls"], 4, 6, 8):
        acts = safe / (tok_per_call / a) / HIDDEN_GAMES
        print(f"  {a:>4.2f} actions/call -> {tok_per_call/a:>5.0f} tok/action"
              f" -> {acts:>5.0f} actions/game ({acts/now:.2f}x run 1)")

    print(f"\nKV cache {KV_TOKENS:,} tokens:")
    for ctx in (4096, 8192, 16384):
        print(f"  {ctx:>5}-token context -> {KV_TOKENS/ctx:>5.1f} concurrent sequences")


if __name__ == "__main__":
    main()

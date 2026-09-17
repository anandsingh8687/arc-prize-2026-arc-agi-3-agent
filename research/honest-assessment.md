# Is this strategy going to get us past 20? An honest answer.

2026-09-16. Written in response to a fair challenge: two days of work, the score
has not moved, and the last several exchanges were spent revising a data schema.

## 1. The criticism is correct

Hidden score **2.37**, rank 616, unchanged since 2026-09-15. In that time we have:

- rejected one idea (the 1024-token cap) with good evidence;
- built a measurement harness, a ledger contract and a crash-proof recorder;
- found and fixed nine defects in that contract, several of which would have
  produced permanently unusable data.

That is real work and none of it is score. Five revisions of a transition schema
for a recorder that has never recorded a transition is not progress toward first
place, whatever the individual bugs were worth.

## 2. Why we cannot clear more levels — from the data, not from theory

`research/why_not_deeper.py` reads the 32 per-game rows Gate 2 produced. The
aggregates were used for the cap verdict; nobody had looked at the rows.

**The agent is not failing to operate the game.**

```
arm            game   actions  no-ops  no-op rate  calls
seed0-control  tn36       400       0        0.0%     56
seed0-cap1024  tn36       400       0        0.0%     93
seed1-cap1024  tn36       400       0        0.0%    247
seed0-control  g50t       400     104       26.0%    160
```

`tn36` three times: four hundred actions that all changed the board, not one
wasted move, and not one level cleared. It knows what the buttons do. **It does
not know what the game wants.** That is goal discovery, and no token budget,
scheduler or response cap touches it.

## 3. A pattern, and the experiment that kills it

Same game, same configuration, different seed:

```
tn36   seed0-control  400 actions,  56 calls = 7.14 per call  ->  0 levels
       seed1-control  400 actions, 197 calls = 2.03 per call  ->  2 levels
```

Of the four games whose control arms differed, **all four** went to the arm that
reasoned more often per action. Across all 32 game-runs:

```
actions/call  < 1.5    n=6    mean levels 3.00
              1.5-2.5  n=11   mean levels 1.18
              2.5-4.0  n=7    mean levels 1.00
              >= 4.0   n=8    mean levels 1.00
```

The obvious confound runs the wrong way — an agent executing a known plan should
look *batchier*, not less — so the pattern survives it.

**And then Gate 2 accidentally tested it.** The cap forced actions per call from
2.85 down to 1.71, and cleared levels fell from 25 to 21. Forcing the ratio down
did not help.

So reasoning density is a **symptom, not a cause**: a model with a specific
hypothesis tests it one step at a time; a confused model emits a long speculative
batch. Moving the ratio moves the symptom. That eliminates "make reasoning
denser" before it costs anything — the second lever Gate 2 has killed from data
already on disk.

## 4. What we have never done, and should do first

**2,175 control LLM calls were saved with their transcripts. Nobody has read
one.** We have built four versions of a verifier for a model whose output we have
never examined.

Twenty transcripts from `tn36` separate three failure modes with entirely
different fixes:

```
A  no hypothesis at all                    the prompt never asks for one
B  a hypothesis, never tested              needs prediction + checking
C  a correct hypothesis it cannot execute  needs planning and search
```

**Only C is what the verified-simulator bet is designed to fix.** If the answer is
A, the fix is a prompt change measurable in an afternoon. We are about to spend
days building for C without having checked which one it is.

This costs no GPU and no long run. It should happen before the Duck adapter.

## 5. Can we reach 20?

Plainly, and without hedging:

- **20 hidden is above the current rank 1 (18.81).** Nobody at our constraints has
  publicly shown anything near it.
- The rank-3 cut is **8.44**, which is 3.56x our 2.37.
- The only open-weight architecture reference, Polyphony at 19.80 **local**, used
  8 GPUs and 24 hours — **78x our per-game compute** (`research/what_100_costs.py`).
  It is not a demonstration that 19.80 is reachable on one GPU in nine hours.
- The 95-100 systems are open-source harnesses driving closed frontier models we
  cannot run offline.

So: **I do not think 20 is reachable by 2026-09-30, and I will not claim
otherwise.** The rank-3 cut is a stretch that depends on a capability improvement
we have not yet demonstrated exists.

What I will say is that the direction is aimed at the right thing — the failure is
goal discovery, and mechanic induction is the only lever anyone has shown moves
goal discovery — and that §4 is a cheaper, faster test of that direction than
anything currently queued.

## 6. What changes as a result

1. **Read the transcripts first.** Twenty calls from a zero-level game, classify
   A/B/C, before any more building.
2. Keep the ledger frozen at v4. It is finished; stop revising it.
3. The Duck adapter and induction prompt stay next, but their priority depends on
   what §4 finds — if the answer is A, they are not the first fix.
4. No GPU until something in that chain is answered.

---

## 7. Reconciling the two findings — and a priority change (2026-09-16)

Codex located the single most actionable thing in this whole investigation:
**Duck clears its world model, goal model, action model, findings, questions and
plan at every level transition**; only free-form cross-level notes survive
(`tool_agent.py:1113`). That is a defect in code we actually run, at one location,
and it matches NOOA's separately-measured finding that **memory was worth +11.8
RHAE against +8.5 for its world-model skill** — memory the larger lever, in the
one place the two were isolated. (GPT-5.5; I am using the ordering, not the
magnitudes, and even the ordering is one measurement on one system.)

### I tested it against our own data. The test came back inconclusive.

`research/memory_loss.py`. Each level has a human baseline, so
`actions / baseline` normalises away difficulty. If state were being destroyed at
transitions, later levels should cost relatively more.

```
level    n   median   worse than human
    1   34     1.00                50%
    2   15     0.90                47%
    3    6     0.61                17%
    4    4     0.89                25%
   5-8   6     0.38-2.12            —

level 1     median 1.00
levels 2+   median 0.83
```

Flat to slightly better. **This does not confirm the memory defect costs us**, and
the instrument could not have detected a modest one: a wipe costs most in the
actions immediately *after* a transition, and level-total counts cannot see inside
a level. The right measurement is actions-to-first-progress after each level
change, which needs the transition ledger.

### RETRACTED — "level 1 is the worst level"

I claimed level 1 was the agent's worst and that "once it has a foothold, it is
better than human". **Both are wrong, and the analysis had three defects:** it
pooled the same games across run 1 and four Gate 2 arms, it was unpaired, and it
silently excluded the five games that never cleared level 1 at all.

Paired properly — run 1 only, the same game's first two completed levels, each
normalised by its own human baseline:

```
comparable games                              10
raw    L2/L1 actions        median 1.5602     L2 worse in 7/10
NORMALISED by own baseline  median 1.5764     L2 relatively worse in 6/10
```

**Level 2 costs about 1.58x what level 1 costs, relative to human, in the same
game.** That is the opposite of what I reported.

It does not prove memory loss — later levels may simply be harder in ways the
action baseline does not capture — but it removes my counter-evidence, and it is
the shape state destruction at a transition would produce. **Correcting my error
strengthened the memory hypothesis rather than weakening it.**

### RETRACTED — "the stalled 60% are worth only +0.62"

Also wrong, and from a table in this repository:

```
five zero-level games  -> depth 1     +0.62
ten one-level games    -> depth 2     +2.77
ALL FIFTEEN stalled    -> +1 level    +3.39
post-hoc best five                    +3.25
```

I compared +0.62 against +3.25 and concluded the stalled games were worth 5.2x
less. The stalled games are worth **+3.39 — more than the best-five figure**, and
+3.25 is a post-hoc upper bound on a hand-picked set, not an expectation. The
priority argument I built on that comparison does not stand.

The reordering survives, but **for the opposite reason to the one I gave**: not
because memory targets higher-weight games, but because the paired level analysis
above is consistent with state loss, and because the fix is cheap.

### RETRACTED — "reasoning is evicted four times per level"

Four defects, all fatal to the ratio: it pooled control with the rejected cap arm
(60.9% more calls); the numerator counted calls spent on unfinished levels and
zero-completion games while the denominator counted only completed levels; an LLM
request is not one retained assistant turn (retries may not persist, trimming can
happen before 30); and the 83.7163% empty-content figure came from Qwen3.6 example
logs, not from Gate 2's Flash-Next transcripts.

**The one clean measurement available points the other way.** A game that *won*
has no calls spent on an unfinished level, so every call is attributable to a
completed one — and there is exactly one such game across the four arms:

```
seed0-control lp85   won 8/8, 196 calls  ->  24.5 calls per level
```

24.5 is below 30 — but this does not point the other way either, and saying so
was a second overreach. It averages **HTTP requests across a whole game**, not
retained assistant turns within any one level. It supports nothing; it simply
removes the support I claimed.

What survives is the source-level fact, not a frequency: **reasoning is bounded
(30 turns, `tool_agent.py:151`) while durable summaries ignore reasoning entirely
and update only from `content` (cleared separately at `tool_agent.py:1113`).** How
often that bites is unmeasured, and the measurement needs the ledger — which is
why ledger recording lands *with* the memory change rather than after it.

Before implementing, the `content_chars` statistic must be re-extracted from Gate
2's own Flash-Next transcripts, **reported per arm and not pooled**.

### Game selection for the paired screen, from the data

Wanted: reaches beyond level 1, does not routinely finish, reproducible across
runs. Levels completed in run 1 and both Gate 2 control arms:

```
game   run1  s0  s1   of   verdict
cd82      2   2   1    6   PICK -- deep, stable, never finishes
ka59      1   2   2    7   PICK -- deep, stable, never finishes
lp85      6   8   1    8   sometimes finishes -- ceiling effect
bp35/g50t/ls20/sp80/tn36   never reliably past level 1
```

`lp85` must be excluded despite being our best game: it won outright in one arm,
so a ceiling caps any improvement the screen could show.

### Revised order

```
1  READ THE TRANSCRIPTS     20 from tn36 AND several multi-level successes;
                            classify missing / untested hypothesis, execution
                            failure, memory loss                         free
2  STRUCTURED memory_update a tool argument Qwen writes alongside its action,
                            not prose scraped from content that is empty 84%
                            of the time
                            PRESERVE  action semantics, verified mechanics,
                                      goal evidence, counterexamples, paths
                            RESET     current plan, level-specific coordinates,
                                      unverified goal guesses, object identities
3  ledger recording         landed WITH step 2, so the measurement is defined
4  paired 2-game test       Duck vs structured memory, same seeds, one session;
                            promotion on additional completed levels only
5  E0, two components       transition predictor AND goal/progress model
6  W / W-repeat / C         cleared levels as the gate
```

"Stop deleting state" was too blunt and is replaced. Carrying a stale
`current_plan` into a changed level could make things worse, and preserving
summaries that were never populated preserves nothing.

### One correction to the survey

**AERA did not score 21.16 with a 0.5B model.** Its paper reports **0.2116 public
and 0.30 private**; a comparison table scaled it by 100. A half-billion-parameter
model at 21 would have been the most important result in the field, and it is not
real. Recorded because it nearly entered our planning as evidence that small
models can do this.

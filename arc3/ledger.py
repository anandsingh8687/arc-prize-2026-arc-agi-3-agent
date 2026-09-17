"""Per-game transition ledger, and the verifier for a partial simulator.

The capability bet in research/rank-1-plan.md turns on a model writing a small
`step(state, action)` for one mechanic and SEARCH running against it. Search
chains predictions, so the verifier has to chain them too.

Each choice here answers a specific way the naive version certifies something
unusable.

**Teacher forcing is not simulation.** The previous version handed every call the
recorded ground-truth state, so "three consecutive correct predictions" meant
three independent one-step guesses. A candidate whose latent evolution is
completely broken passed. `verify_rollout` feeds each PREDICTED successor into
the next call, which is what a planner does.

**A hash is not evidence.** Before that, `step` received a digest. Nothing can
INDUCE a mechanic from a hash -- a candidate could only recognise hashes.
`step` receives the board, level, attempt, available actions and its own latents.

**A partial outcome is not an outcome.** Optional fields let a candidate omit the
available actions or the successor grid and still be scored exact. A `Prediction`
now carries a complete successor `ObservedState`, and all of it is compared.

**The lookup table.** Transitions split CHRONOLOGICALLY into induction / repair /
locked holdout, and the gate is scored on NOVEL state-action pairs, so replaying
repeated pairs cannot pass.

**The confident wrong answer.** A simulator 90% right is worse than one covering
20% exactly: search plans through the wrong 10% into a state that does not exist.
`step` is PARTIAL, returning ``UNKNOWN`` outside the domain it claims, and
soundness and coverage are kept apart rather than averaged into an accuracy.
The gate requires ZERO confident errors anywhere in the holdout, not merely one
clean chain: a candidate wrong five times out of eight could otherwise pass on
the strength of the three it happened to get right.

**Volatility is not aliasing.** Novelty and evidence volume use the
volatility-masked before-hash, because a ticking HUD should not make every state
look new or turn 400 revisits into 400 "unique" situations. Aliasing uses the RAW
before-hash, because it asks whether the same COMPLETE observable state and
action produced different outcomes. Mixing the two reports a ticking clock as
hidden state.

Transitions never pool across games, and the key carries the level, because a
volatility-masked hash can collide across levels with different dynamics.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Final

import numpy as np

from arc3.effects import ActionKey
from arc3.state import diff_cells


class _Unknown:
    """Sentinel for 'this model does not claim to predict here'."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "UNKNOWN"

    def __bool__(self) -> bool:
        return False


UNKNOWN: Final = _Unknown()

Diff = dict[tuple[int, int], int]

# Chronological thirds: induce on the first, repair against the second, never
# show the third until the candidate is final. Without the repair segment a
# third "attempt" absorbs the test set one counterexample at a time.
INDUCTION_FRACTION = 0.6
REPAIR_FRACTION = 0.2

MIN_CLAIMS = 3
MIN_ROLLOUT = 3  # consecutive novel steps the simulator must advance unaided


@dataclass(frozen=True)
class ObservedState:
    """What the environment shows. Every field is ground truth and is compared."""

    grid: np.ndarray
    level: int
    attempt: int = 0
    available_actions: tuple[int, ...] = ()
    status: str = "NOT_FINISHED"

    def equals(self, other: "ObservedState") -> bool:
        return (
            self.level == other.level
            and self.attempt == other.attempt
            and self.status == other.status
            and tuple(self.available_actions) == tuple(other.available_actions)
            and self.grid.shape == other.grid.shape
            and np.array_equal(self.grid, other.grid)
        )


@dataclass(frozen=True)
class SimulatorState:
    """What a candidate `step` sees: the board plus whatever latents it proposed.

    Latents have no ground truth, so they are never compared against the record.
    They are carried forward through a rollout instead, which is what exposes a
    broken latent update: the grid it produces two steps later stops matching.
    """

    observed: ObservedState
    latent: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Prediction:
    """A complete claimed successor. No optional fields -- partial is not exact."""

    observed: ObservedState
    latent: dict[str, Any] = field(default_factory=dict)


StepFn = Callable[[SimulatorState, ActionKey], "Prediction | _Unknown"]


# Priority 4 fires on "large" transient activity. This threshold is a chosen
# default, not a measured one; nothing yet says where the useful cut sits.
LARGE_TRANSIENT_CELLS = 4


@dataclass(frozen=True)
class FrameStep:
    """One frame of an animation, as a change against the previous frame.

    A level transition can RESIZE the board, and a diff across differing shapes
    is meaningless -- so a step that changes shape carries the whole frame
    instead. An earlier version simply skipped such frames, which silently
    discarded the first frame of exactly the animations priority 3 exists to
    surface.
    """

    changes: dict[tuple[int, int], int] = field(default_factory=dict)
    snapshot: np.ndarray | None = None

    @property
    def resizes(self) -> bool:
        return self.snapshot is not None

    def apply(self, previous: np.ndarray) -> np.ndarray:
        if self.snapshot is not None:
            return self.snapshot.copy()
        out = previous.copy()
        for (r, c), value in self.changes.items():
            out[r, c] = value
        return out

    @property
    def touched(self) -> set[tuple[int, int]]:
        if self.snapshot is not None:
            return {(int(r), int(c)) for r, c in np.ndindex(self.snapshot.shape)}
        return set(self.changes)


@dataclass(frozen=True)
class AnimationEvidence:
    """What the intermediate frames showed that the settled diff destroys.

    The engine returns a list of grids; the last is settled and the rest are the
    board resolving. A cell that moves and returns is invisible in
    before -> after, and is often the only trace of what actually happened.

    **Order is preserved.** An earlier version stored only the set of values each
    cell took, which cannot tell `A -> B -> C` from `C -> B -> A`. Once the raw
    frames are gone that loss is permanent.

    This is EVIDENCE, never a prediction target. It does not enter the outcome
    signature or the alias key: a simulator required to reproduce intermediate
    frames would fit presentation timing rather than mechanics.
    """

    frame_count: int = 1
    timeline: tuple[FrameStep, ...] = ()
    settled_noop: bool = False

    @property
    def distinct_frame_count(self) -> int:
        return len(self.timeline)

    @property
    def animated(self) -> bool:
        return self.frame_count > 1

    def frames(self, before: np.ndarray) -> list[np.ndarray]:
        """Reconstruct every recorded frame, resizes included."""
        out: list[np.ndarray] = []
        current = before
        for step in self.timeline:
            current = step.apply(current)
            out.append(current)
        return out

    @property
    def touched_cells(self) -> set[tuple[int, int]]:
        return {cell for step in self.timeline for cell in step.touched}

    @property
    def bounding_box(self) -> tuple[int, int, int, int] | None:
        """(min_row, min_col, max_row, max_col) over everything the animation touched."""
        cells = self.touched_cells
        if not cells:
            return None
        rows = [r for r, _ in cells]
        cols = [c for _, c in cells]
        return (min(rows), min(cols), max(rows), max(cols))

    def transient_cells(self, before: np.ndarray, after: np.ndarray
                        ) -> dict[tuple[int, int], tuple[int, ...]]:
        """Values a cell held that match NEITHER the before nor the after board.

        Derived from the reconstructed frames, so the ordered record stays the
        single source of truth. A cell that simply ends up changed is already in
        the settled diff and is not transient.
        """
        out: dict[tuple[int, int], list[int]] = {}
        for frame in self.frames(before):
            if frame.shape != before.shape or frame.shape != after.shape:
                continue
            rows, cols = np.nonzero((frame != before) & (frame != after))
            for r, c in zip(rows, cols):
                out.setdefault((int(r), int(c)), []).append(int(frame[r, c]))
        return {k: tuple(v) for k, v in out.items()}

    @property
    def informative(self) -> bool:
        """Carries motion the single settled frame could not have shown."""
        return self.distinct_frame_count > 1 or (self.settled_noop and bool(self.timeline))

    def summary(self) -> dict[str, Any]:
        """The compact metadata the model sees by DEFAULT.

        ``touched_cell_count`` is deliberately not called transient: it counts
        every cell the animation wrote, including ones whose final value is
        plainly visible in the settled diff. A true transient count needs the
        before and after boards -- see `Transition.animation_summary`.
        """
        return {
            "frame_count": self.frame_count,
            "distinct_frame_count": self.distinct_frame_count,
            "touched_cell_count": len(self.touched_cells),
            "bounding_box": self.bounding_box,
            "settled_noop": self.settled_noop,
        }


def animation_evidence(before: np.ndarray, frames: list[np.ndarray]) -> AnimationEvidence:
    """Build an ordered timeline from the engine's frame list.

    Recording this is free -- the frames already arrive in the response. A
    competitor's naive approach instead exposed animations to the model as a tool
    and found 2 of 181 calls genuinely useful. Recording always and surfacing
    selectively separates the two costs, which is the point.
    """
    if not frames:
        return AnimationEvidence()

    after = frames[-1]
    timeline: list[FrameStep] = []
    previous = before
    for frame in frames:
        if frame.shape != previous.shape:
            timeline.append(FrameStep(snapshot=frame.copy()))
        else:
            changes = diff_cells(previous, frame)
            if not changes:
                previous = frame
                continue  # consecutive identical frames add nothing
            timeline.append(FrameStep(changes=changes))
        previous = frame

    settled_noop = (before.shape == after.shape and np.array_equal(before, after))
    return AnimationEvidence(frame_count=len(frames), timeline=tuple(timeline),
                             settled_noop=settled_noop)


@dataclass(frozen=True)
class Transition:
    """One charged action, recorded between SETTLED states.

    ``animation`` carries what the intermediate frames showed. It is evidence
    about what happened, deliberately NOT a prediction target, and it is
    deliberately absent from both `outcome` and `alias_key`.
    """

    index: int  # chronological position within the game
    before: ObservedState
    action: ActionKey
    after: ObservedState
    before_norm_hash: str = ""  # volatility-masked; novelty only
    before_raw_hash: str = ""
    after_raw_hash: str = ""
    animation: AnimationEvidence = field(default_factory=AnimationEvidence)

    def __post_init__(self) -> None:
        """All three hashes are required.

        They default to empty only so the field order stays readable. A recorder
        that omits `before_raw_hash` would silently collapse every alias key and
        disable alias detection entirely -- the check reports nothing wrong, which
        is the worst failure mode this module has.
        """
        missing = [name for name in
                   ("before_norm_hash", "before_raw_hash", "after_raw_hash")
                   if not getattr(self, name)]
        if missing:
            raise ValueError(
                f"transition {self.index} is missing {', '.join(missing)}; "
                "an omitted hash silently disables alias or novelty detection"
            )

    @property
    def level(self) -> int:
        return self.before.level

    @property
    def diff(self) -> Diff:
        return diff_cells(self.before.grid, self.after.grid)

    @property
    def level_changed(self) -> bool:
        return self.after.level != self.before.level

    @property
    def is_noop(self) -> bool:
        """Nothing observable changed, so this action bought nothing."""
        return self.before.equals(self.after)

    @property
    def novelty_key(self) -> tuple[int, int, str, tuple[int, ...], str, ActionKey]:
        """Has the candidate effectively seen this situation before?

        The GRID hash is masked, so a ticking HUD does not make every state look
        new -- but the other observable fields are carried in full. An earlier
        version dropped `attempt`, `status` and `available_actions`, which
        understated novelty in the holdout, weakened lookup-table rejection, and
        mismatched priority-4 UNKNOWN lookups.
        """
        return (self.before.level, self.before.attempt, self.before.status,
                tuple(self.before.available_actions), self.before_norm_hash,
                self.action)

    @property
    def alias_key(self) -> tuple[int, int, str, tuple[int, ...], str, ActionKey]:
        """Did the same COMPLETE observable state and action diverge?

        Raw, not masked. Using the masked hash here reports a ticking HUD as
        hidden state, because the after-hashes then differ for a mechanic that
        is in fact deterministic.

        "Complete" means complete. An earlier version used only
        `(level, before_raw_hash, action)`, so identical boards on different
        attempts -- or with a different status or action set -- registered as
        hidden-state aliasing when the difference was plainly observable.
        """
        return (self.before.level, self.before.attempt, self.before.status,
                tuple(self.before.available_actions), self.before_raw_hash,
                self.action)

    def animation_summary(self) -> dict[str, Any]:
        """The default surface, plus the transient count only this pair can give."""
        out = self.animation.summary()
        out["transient_cell_count"] = len(
            self.animation.transient_cells(self.before.grid, self.after.grid))
        return out

    @property
    def outcome(self) -> tuple[str, int, int, str, tuple[int, ...]]:
        """The complete AFTER signature. Aliasing compares outcomes."""
        return (self.after_raw_hash, self.after.level, self.after.attempt,
                self.after.status, tuple(self.after.available_actions))


@dataclass
class LedgerReport:
    """Whether this game's recorded history could support a simulator at all."""

    transitions: int
    unique_keys: int  # distinct MASKED situations -- how much evidence there is
    unique_raw_keys: int  # distinct complete observations, HUD and all
    repetition_rate: float
    aliased_keys: int  # same RAW before-state and action, different outcome
    aliased_transitions: int
    masked_alias_keys: int  # same MASKED state diverges though raw does not
    actions_seen: int
    per_action: dict[ActionKey, int]
    noop_rate: float
    levels: int
    animated: int  # transitions whose response had more than one frame
    animation_resolvable_aliases: int  # aliased keys where animation could decide
    induction: int
    repair: int
    holdout: int
    novel_in_holdout: int

    def summary(self) -> str:
        return (
            f"{self.transitions} transitions, {self.unique_keys} unique "
            f"({self.unique_raw_keys} raw), "
            f"(repetition {self.repetition_rate:.0%}), aliasing {self.aliased_keys} keys"
            f"/{self.aliased_transitions} rows (masked-only {self.masked_alias_keys}), "
            f"{self.actions_seen} actions, "
            f"no-op {self.noop_rate:.0%}, {self.levels} levels, "
            f"{self.animated} animated ({self.animation_resolvable_aliases} "
            f"resolvable aliases), split "
            f"{self.induction}/{self.repair}/{self.holdout} "
            f"({self.novel_in_holdout} novel)"
        )


@dataclass
class GameLedger:
    """Every recorded transition for ONE game, in chronological order."""

    game_id: str
    transitions: list[Transition] = field(default_factory=list)

    def record(self, transition: Transition) -> None:
        self.transitions.append(transition)

    def ordered(self) -> list[Transition]:
        return sorted(self.transitions, key=lambda t: t.index)

    def split(self) -> tuple[list[Transition], list[Transition], list[Transition]]:
        """Chronological thirds. Never random -- a random split leaks the future."""
        rows = self.ordered()
        n = len(rows)
        a = int(n * INDUCTION_FRACTION)
        b = a + int(n * REPAIR_FRACTION)
        return rows[:a], rows[a:b], rows[b:]

    def seen_keys(self) -> set[tuple[int, str, ActionKey]]:
        """Novelty keys the candidate was allowed to see: induction plus repair."""
        induction, repair, _ = self.split()
        return {t.novelty_key for t in induction + repair}

    def animation_candidates(
        self, unknown_keys: set | None = None
    ) -> list[tuple[int, Transition]]:
        """Transitions worth surfacing the full timeline for, ranked by priority.

        An earlier version returned aliasing only. That was too narrow: a
        deterministic animation can reveal the route a change took even when the
        settled outcome never varies, and requiring divergence would discard
        exactly that. Aliasing stays the strongest signal, not the only one.

        ```
        1  genuine aliasing plus informative animation
        2  settled no-op with transient motion -- the board says nothing happened
        3  animation across an otherwise unexplained level or status transition
        4  large transient activity where the mechanic model returned UNKNOWN
        ```

        ``unknown_keys`` are novelty keys the current candidate simulator could
        not predict; priority 4 is unavailable without them, since no amount of
        recorded data says where a model fell silent.
        """
        rows = self.ordered()
        outcomes: dict = {}
        for t in rows:
            outcomes.setdefault(t.alias_key, set()).add(t.outcome)
        ambiguous = {k for k, seen in outcomes.items() if len(seen) > 1}
        unknown = unknown_keys or set()

        ranked: list[tuple[int, Transition]] = []
        for t in rows:
            if not t.animation.animated:
                continue
            transient = t.animation.transient_cells(t.before.grid, t.after.grid)
            if t.alias_key in ambiguous and t.animation.informative:
                ranked.append((1, t))
            elif t.animation.settled_noop and t.animation.timeline:
                ranked.append((2, t))
            elif (t.level_changed or t.after.status != t.before.status) and (
                    transient or any(step.resizes for step in t.animation.timeline)):
                # "Unexplained" means the settled diff does not account for the
                # motion: either cells held values matching neither board, or the
                # board was resized mid-animation.
                ranked.append((3, t))
            elif (t.novelty_key in unknown
                  and len(t.animation.touched_cells) >= LARGE_TRANSIENT_CELLS):
                ranked.append((4, t))
        ranked.sort(key=lambda pair: (pair[0], pair[1].index))
        return ranked

    def report(self) -> LedgerReport:
        """The ledger's first duty: say whether the evidence is usable.

        Counting transitions is not enough. A handful can pin down a simple
        mechanic while thousands stay redundant or ambiguous. Repetition and
        ALIASING decide learnability: aliasing means the visible state does not
        determine the outcome, so no `step(state, action)` can be exact until
        latent variables are proposed -- measurable with no model in the loop.
        """
        rows = self.ordered()
        outcomes: dict[tuple[int, str, ActionKey], set] = {}
        masked_outcomes: dict[tuple[int, str, ActionKey], set] = {}
        counts: Counter = Counter()
        per_action: Counter = Counter()
        for t in rows:
            outcomes.setdefault(t.alias_key, set()).add(t.outcome)
            masked_outcomes.setdefault(t.novelty_key, set()).add(t.outcome)
            counts[t.alias_key] += 1
            per_action[t.action] += 1

        aliased = {k for k, seen in outcomes.items() if len(seen) > 1}
        # Divergence visible only under the mask means the mask discarded
        # information needed to REPRODUCE THE RAW FRAME -- not necessarily
        # causal game state. A purely decorative HUD carried into the next
        # frame triggers it, so "widen the mask" is one possible response and
        # "ignore that region in the outcome too" is another. What it rules out
        # is hidden state: raw aliasing is the signal for that.
        masked_only = sum(1 for k, seen in masked_outcomes.items() if len(seen) > 1) - len(aliased)
        induction, repair, holdout = self.split()
        seen = self.seen_keys()
        total = len(rows)
        return LedgerReport(
            transitions=total,
            # Evidence volume is counted on MASKED keys. Counting raw keys makes
            # a ticking HUD turn 400 revisits of one state into 400 "unique"
            # situations, which is the opposite of what this number is for.
            unique_keys=len(masked_outcomes),
            unique_raw_keys=len(outcomes),
            repetition_rate=0.0 if not total else 1 - len(masked_outcomes) / total,
            aliased_keys=len(aliased),
            aliased_transitions=sum(counts[k] for k in aliased),
            masked_alias_keys=max(0, masked_only),
            actions_seen=len(per_action),
            per_action=dict(per_action),
            noop_rate=0.0 if not total else sum(t.is_noop for t in rows) / total,
            levels=len({t.level for t in rows}),
            animated=sum(1 for t in rows if t.animation.animated),
            # Priority-1 candidates: the visible board does not determine the
            # outcome AND the frames carry motion it could not have shown. The
            # strongest trigger, not the only one -- see animation_candidates.
            animation_resolvable_aliases=sum(
                1 for t in rows
                if t.alias_key in aliased and t.animation.informative
            ),
            induction=len(induction),
            repair=len(repair),
            holdout=len(holdout),
            novel_in_holdout=sum(1 for t in holdout if t.novelty_key not in seen),
        )


# --------------------------------------------------------------------------
# One-step verification: a diagnostic, NOT the gate.
# --------------------------------------------------------------------------


@dataclass
class VerifyResult:
    """Teacher-forced one-step scoring. Useful for locating a defect.

    It cannot be the promotion gate: every call receives the recorded state, so
    a candidate with broken latent evolution scores perfectly here and cannot
    simulate two steps. Use `verify_rollout` to decide anything.
    """

    total: int
    claimed: int = 0
    exact: int = 0
    novel_total: int = 0
    novel_claimed: int = 0
    novel_exact: int = 0
    wrong: list[Transition] = field(default_factory=list)

    @property
    def soundness(self) -> float:
        return 1.0 if self.claimed == 0 else self.exact / self.claimed

    @property
    def coverage(self) -> float:
        return 0.0 if self.total == 0 else self.claimed / self.total

    @property
    def novel_coverage(self) -> float:
        """The number a lookup table cannot fake."""
        return 0.0 if self.novel_total == 0 else self.novel_claimed / self.novel_total

    def summary(self) -> str:
        return (
            f"one-step: soundness {self.soundness:.1%} ({self.exact}/{self.claimed}), "
            f"coverage {self.coverage:.1%}, novel {self.novel_exact}/{self.novel_total}"
        )


def verify(step: StepFn, transitions: list[Transition],
           seen_keys: set | None = None,
           init_latent: "InitLatentFn | None" = None) -> VerifyResult:
    """Score one-step predictions against recorded transitions. Diagnostic only.

    ``init_latent`` matters even here: a candidate that returns UNKNOWN whenever
    its latent is empty would otherwise be silent through the whole sweep and
    register zero confident errors, while guessing wrong the moment a rollout
    initialises it.
    """
    seen = seen_keys or set()
    rows = sorted(transitions, key=lambda t: t.index)
    result = VerifyResult(total=len(rows))
    result.novel_total = sum(1 for t in rows if t.novelty_key not in seen)
    for i, t in enumerate(rows):
        novel = t.novelty_key not in seen
        latent = init_latent(rows[:i], t.before) if init_latent else {}
        predicted = step(SimulatorState(observed=t.before, latent=latent), t.action)
        if isinstance(predicted, _Unknown):
            continue
        result.claimed += 1
        if novel:
            result.novel_claimed += 1
        if predicted.observed.equals(t.after):
            result.exact += 1
            if novel:
                result.novel_exact += 1
        else:
            result.wrong.append(t)
    return result


# --------------------------------------------------------------------------
# Rollout verification: the gate.
# --------------------------------------------------------------------------


@dataclass
class RolloutResult:
    """The longest chain the candidate advanced on its OWN predicted states."""

    longest: int = 0
    progress_in_longest: int = 0
    start_index: int | None = None
    confident_errors: int = 0  # wrong predictions ANYWHERE it claimed
    first_failure: Transition | None = None
    broken_continuity: int = 0  # recorded gaps that cannot be chained across

    @property
    def usable(self) -> bool:
        """E0's pass condition.

        Three requirements, and the first is the one an earlier version omitted:

        1. ZERO confident errors anywhere in the holdout. A candidate wrong five
           times out of eight previously passed on the strength of one clean
           chain, which contradicts "sound wherever it claims". A partial model
           returns UNKNOWN; it does not guess.
        2. NO rollout failure from any start position. The sweep in (1) alone is
           not enough: a candidate that stays silent while its latent is empty
           registers no sweep errors and then guesses wrong once a rollout
           initialises it. `first_failure` is where that shows up.
        3. A chain of at least MIN_ROLLOUT consecutive NOVEL steps advanced on
           its own predicted states, not teacher-forced.
        4. At least one step inside that chain that changed something -- a
           perfect no-op predictor chains forever and buys no levels.
        """
        return (
            self.confident_errors == 0
            and self.first_failure is None
            and self.longest >= MIN_ROLLOUT
            and self.progress_in_longest >= 1
        )

    def summary(self) -> str:
        return (
            f"rollout: {self.longest} consecutive novel steps from index "
            f"{self.start_index}, {self.progress_in_longest} progress, "
            f"{self.confident_errors} confident errors, "
            f"{'USABLE' if self.usable else 'REJECTED'}"
        )


# A latent initialiser reconstructs history-derived hidden state at the point a
# rollout starts. Without one every chain begins from {}, so a mechanic that
# depends on anything not visible in the current frame cannot be represented.
InitLatentFn = Callable[[list[Transition], ObservedState], dict[str, Any]]


def _chain_from(step: StepFn, rows: list[Transition], start: int, seen: set,
                init_latent: InitLatentFn | None) -> tuple[int, int, Transition | None, int]:
    """Roll forward from `start`, feeding predictions into the next call."""
    history = rows[:start]
    latent = init_latent(history, rows[start].before) if init_latent else {}
    state = SimulatorState(observed=rows[start].before, latent=latent)
    length = progress = breaks = 0
    previous: Transition | None = None

    for t in rows[start:]:
        if t.novelty_key in seen:
            break  # a repeated pair tests nothing; the novel chain ends here
        if previous is not None and not previous.after.equals(t.before):
            # The recording is not contiguous here -- a reset, a dropped frame,
            # or a non-adjacent holdout slice. Chaining across it would credit
            # the candidate for a jump the environment made, not the model.
            breaks += 1
            break
        predicted = step(state, t.action)
        if isinstance(predicted, _Unknown):
            break
        if not predicted.observed.equals(t.after):
            return length, progress, t, breaks
        length += 1
        if not t.is_noop:
            progress += 1
        # The predicted successor, never the recorded one. This is the whole
        # point: an incorrect latent update surfaces as a wrong grid later.
        state = replace(state, observed=predicted.observed, latent=predicted.latent)
        previous = t
    return length, progress, None, breaks


def verify_rollout(step: StepFn, transitions: list[Transition],
                   seen_keys: set | None = None,
                   init_latent: InitLatentFn | None = None) -> RolloutResult:
    """Chain the candidate's own predictions and find its longest novel run.

    Search plans several actions ahead from a single model call, so a simulator
    is only worth planning against if it stays exact while consuming its own
    output. Every start position is tried, because the usable domain may begin
    part-way through the holdout.

    A separate teacher-forced sweep counts confident errors across ALL recorded
    transitions, because a good chain somewhere does not excuse a wrong
    prediction elsewhere -- search will reach that state too.
    """
    seen = seen_keys or set()
    rows = sorted(transitions, key=lambda t: t.index)
    best = RolloutResult()

    sweep = verify(step, rows, seen, init_latent)
    best.confident_errors = len(sweep.wrong)

    for start in range(len(rows)):
        if rows[start].novelty_key in seen:
            continue
        length, progress, failure, breaks = _chain_from(step, rows, start, seen, init_latent)
        best.broken_continuity = max(best.broken_continuity, breaks)
        if best.first_failure is None and failure is not None:
            best.first_failure = failure  # the counterexample to hand back
        if (length, progress) > (best.longest, best.progress_in_longest):
            best.longest, best.progress_in_longest, best.start_index = length, progress, start
    return best

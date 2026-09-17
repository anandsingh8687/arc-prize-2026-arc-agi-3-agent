"""The ledger must reject any model that search could not actually plan against."""

from __future__ import annotations

import numpy as np
import pytest

from arc3.ledger import (
    UNKNOWN,
    FrameStep,
    GameLedger,
    ObservedState,
    Prediction,
    SimulatorState,
    Transition,
    verify,
    verify_rollout,
)
from arc3.state import hash_grid

MOVE = (1, None, None)
ACTIONS = (1, 2)
WIDTH = 16


def board(pos: int, *, noise: int = 0) -> np.ndarray:
    """A marker at `pos`; `noise` writes a volatile HUD cell that hashing masks."""
    g = np.zeros((2, WIDTH), dtype=np.int8)
    g[0, pos] = 5
    g[1, 0] = noise
    return g


def seen_at(pos: int, **kw) -> ObservedState:
    return ObservedState(grid=board(pos, noise=kw.pop("noise", 0)),
                         level=kw.pop("level", 1), attempt=kw.pop("attempt", 0),
                         available_actions=kw.pop("available_actions", ACTIONS),
                         status=kw.pop("status", "NOT_FINISHED"))


def marker(grid: np.ndarray) -> int:
    return int(np.argmax(grid[0]))


def shift(index: int, pos: int, **kw) -> Transition:
    """The true mechanic: the marker advances one cell per action."""
    before = seen_at(pos, noise=kw.pop("before_noise", 0))
    after = kw.pop("after", None) or seen_at(pos + 1, **kw)
    # The masked hash ignores the volatile row, so it is computed on row 0 only.
    mask = np.array([[True] * WIDTH, [False] * WIDTH])
    return Transition(index=index, before=before, action=kw.pop("action", MOVE),
                      after=after,
                      before_norm_hash=hash_grid(before.grid, mask),
                      before_raw_hash=hash_grid(before.grid),
                      after_raw_hash=hash_grid(after.grid))


def frozen(index: int, pos: int) -> Transition:
    """An action that changed nothing."""
    here = seen_at(pos)
    return Transition(index=index, before=here, action=MOVE, after=seen_at(pos),
                      before_norm_hash=f"still{pos}", before_raw_hash=f"raw{pos}",
                      after_raw_hash=f"raw{pos}")


def advance(st: SimulatorState, action) -> Prediction:
    """A correct simulator: reads the board, moves the marker."""
    return Prediction(observed=seen_at(marker(st.observed.grid) + 1))


# --- the ledger reports learnability, not volume ---------------------------

def test_aliasing_compares_outcomes_not_before_states():
    """Volatile pixels differing in two BEFORE states is not aliasing.

    The earlier version keyed the outcome set on the before-state's raw hash, so
    a ticking HUD registered as two different outcomes for the same action.
    """
    rows = [shift(0, 2, before_noise=0), shift(1, 2, before_noise=7)]
    assert GameLedger("g", rows).report().aliased_keys == 0


def test_aliasing_is_detected_when_the_same_state_and_action_diverge():
    rows = [shift(0, 2), shift(1, 2, after=seen_at(6))]
    report = GameLedger("g", rows).report()
    assert report.aliased_keys == 1
    assert report.aliased_transitions == 2


def test_the_key_carries_the_level_so_masked_hashes_do_not_collide():
    rows = [shift(0, 2), shift(1, 2, level=2, after=seen_at(6, level=2))]
    rows[1] = Transition(index=1, before=seen_at(2, level=2), action=MOVE,
                         after=seen_at(6, level=2),
                         before_norm_hash=rows[0].before_norm_hash,
                         before_raw_hash="r", after_raw_hash="a")
    assert GameLedger("g", rows).report().aliased_keys == 0


def test_split_is_chronological_thirds_never_random():
    ledger = GameLedger("g", [shift(i, i) for i in range(10)])
    induction, repair, holdout = ledger.split()
    assert [x.index for x in induction] == list(range(6))
    assert [x.index for x in repair] == [6, 7]
    assert [x.index for x in holdout] == [8, 9]


def test_noop_rate_counts_actions_that_changed_nothing():
    still = frozen(0, 1)
    assert GameLedger("g", [still, shift(1, 3)]).report().noop_rate == pytest.approx(0.5)


def test_evidence_volume_is_counted_on_masked_keys():
    """Six revisits of one state with a ticking HUD are not six situations.

    Counting raw keys made repetition_rate read 0% for a game that had learned
    nothing new in six actions -- the opposite of what the number is for.
    """
    rows = [shift(i, 3, before_noise=i, noise=i) for i in range(6)]
    report = GameLedger("g", rows).report()
    assert report.unique_keys == 1
    assert report.unique_raw_keys == 6
    assert report.repetition_rate == pytest.approx(5 / 6)


def test_a_missing_hash_is_rejected_rather_than_silently_disabling_detection():
    for omit in ("before_norm_hash", "before_raw_hash", "after_raw_hash"):
        fields = {"before_norm_hash": "n", "before_raw_hash": "r", "after_raw_hash": "a"}
        fields[omit] = ""
        with pytest.raises(ValueError, match=omit):
            Transition(index=0, before=seen_at(1), action=MOVE, after=seen_at(2), **fields)


# --- the rollout gate -------------------------------------------------------

def test_teacher_forcing_passes_a_model_that_cannot_simulate():
    """The defect that made the previous gate meaningless.

    This candidate reads the board when handed one and is exact every time under
    one-step scoring. Rolled forward on its own output it corrupts its latent and
    diverges immediately. Only the rollout catches it.
    """
    rows = [shift(i, i) for i in range(6)]

    def broken_latent(st, action):
        pos = st.latent["pos"] if "pos" in st.latent else marker(st.observed.grid)
        nxt = pos + 1
        return Prediction(observed=seen_at(nxt), latent={"pos": nxt + 1})  # off by one

    one_step = verify(broken_latent, rows)
    assert one_step.soundness == 1.0 and one_step.coverage == 1.0

    rolled = verify_rollout(broken_latent, rows)
    assert rolled.longest == 1
    assert not rolled.usable


def test_a_correct_simulator_chains_and_is_usable():
    rows = [shift(i, i) for i in range(6)]
    rolled = verify_rollout(advance, rows)
    assert rolled.longest == 6
    assert rolled.progress_in_longest >= 1
    assert rolled.usable


def test_a_perfect_noop_predictor_chains_forever_and_is_rejected():
    """Predicting 'nothing happens' is exact, chains indefinitely, buys no levels."""
    rows = [frozen(i, 3) for i in range(6)]
    rolled = verify_rollout(lambda st, a: Prediction(observed=seen_at(3)), rows)
    assert rolled.longest == 6
    assert rolled.progress_in_longest == 0
    assert not rolled.usable


def test_progress_must_occur_inside_the_novel_chain():
    """Three novel no-ops plus a memorised progress step must not pass.

    The repeated pair ends the novel chain, so its progress cannot be borrowed.
    """
    rows = [frozen(i, 3) for i in range(3)]
    rows.append(shift(3, 5))
    seen = {rows[3].novelty_key}

    def noop_then_move(st, action):
        pos = marker(st.observed.grid)
        return Prediction(observed=seen_at(pos + 1 if pos == 5 else pos))

    rolled = verify_rollout(noop_then_move, rows, seen)
    assert rolled.progress_in_longest == 0
    assert not rolled.usable


def test_a_short_chain_is_rejected_even_when_exact():
    rows = [shift(i, i) for i in range(6)]

    def two_steps_only(st, action):
        return advance(st, action) if marker(st.observed.grid) < 2 else UNKNOWN

    rolled = verify_rollout(two_steps_only, rows)
    assert rolled.longest == 2
    assert not rolled.usable


def test_the_first_failure_is_returned_as_a_counterexample():
    rows = [shift(i, i) for i in range(6)]

    def wrong_at_three(st, action):
        pos = marker(st.observed.grid)
        return Prediction(observed=seen_at(pos + 2 if pos == 3 else pos + 1))

    assert verify_rollout(wrong_at_three, rows).first_failure is not None


# --- a partial outcome is not an outcome ------------------------------------

def test_omitting_available_actions_is_rejected():
    rows = [shift(0, 2)]

    def forgets_actions(st, action):
        return Prediction(observed=ObservedState(grid=board(3), level=1))

    assert verify(forgets_actions, rows).exact == 0


def test_getting_the_grid_right_but_the_level_wrong_is_rejected():
    """This would plan straight into a level that is already finished."""
    rows = [shift(0, 2, after=seen_at(3, level=2))]
    assert verify(lambda st, a: Prediction(observed=seen_at(3)), rows).exact == 0


def test_getting_the_status_wrong_is_rejected():
    rows = [shift(0, 2, after=seen_at(3, status="GAME_OVER"))]
    assert verify(lambda st, a: Prediction(observed=seen_at(3)), rows).exact == 0


def test_getting_the_attempt_wrong_is_rejected():
    rows = [shift(0, 2, after=seen_at(3, attempt=1))]
    assert verify(lambda st, a: Prediction(observed=seen_at(3)), rows).exact == 0


# --- the lookup table -------------------------------------------------------

def test_a_table_replaying_repeated_pairs_cannot_start_a_novel_chain():
    rows = [shift(i, 2, after=seen_at(3)) for i in range(6)]
    seen = {rows[0].novelty_key}  # every row shares the key
    table = {r.novelty_key: r.after for r in rows}
    key = rows[0].novelty_key
    rolled = verify_rollout(lambda st, a: Prediction(observed=table[key]), rows, seen)
    assert rolled.longest == 0
    assert not rolled.usable


def test_novel_coverage_exposes_a_memoriser_under_one_step_scoring():
    ledger = GameLedger("g", [shift(i, i) for i in range(10)])
    holdout = ledger.split()[2]
    result = verify(lambda st, a: UNKNOWN, holdout, ledger.seen_keys())
    assert result.soundness == 1.0
    assert result.novel_coverage == 0.0


# --- the two false positives found in 65e72c2 -------------------------------

def test_a_clean_chain_does_not_excuse_confident_errors_elsewhere():
    """Wrong five times out of eight, with one good three-step chain.

    The previous gate passed this. Search reaches the states it gets wrong too,
    so a partial model must return UNKNOWN there rather than guess.
    """
    rows = [shift(i, i) for i in range(8)]

    def mostly_wrong(st, action):
        pos = marker(st.observed.grid)
        return Prediction(observed=seen_at(pos + 1 if pos < 3 else 0))

    rolled = verify_rollout(mostly_wrong, rows)
    assert rolled.longest >= 3            # it does find a clean chain
    assert rolled.confident_errors == 5   # and it is wrong elsewhere
    assert not rolled.usable


def test_the_same_candidate_passes_once_it_says_unknown_instead_of_guessing():
    rows = [shift(i, i) for i in range(8)]

    def honest(st, action):
        pos = marker(st.observed.grid)
        return Prediction(observed=seen_at(pos + 1)) if pos < 3 else UNKNOWN

    rolled = verify_rollout(honest, rows)
    assert rolled.confident_errors == 0
    assert rolled.usable


def test_a_ticking_hud_is_not_aliasing():
    """Same masked before-state and action; the HUD ticks in before AND after.

    Keying aliasing on the masked hash while signing outcomes with the raw hash
    reported this deterministic mechanic as hidden state.
    """
    rows = [shift(0, 2, before_noise=1, noise=1), shift(1, 2, before_noise=2, noise=2)]
    report = GameLedger("g", rows).report()
    assert report.aliased_keys == 0
    assert report.masked_alias_keys >= 1  # but the mask IS discarding causal cells


def test_attempt_is_part_of_the_outcome_signature():
    rows = [shift(0, 2), shift(1, 2, after=seen_at(3, attempt=1))]
    assert GameLedger("g", rows).report().aliased_keys == 1


# --- continuity and latent initialisation -----------------------------------

def test_a_gap_between_recorded_transitions_cannot_be_chained_across():
    """A reset or dropped frame means the next `before` is not this `after`."""
    rows = [shift(0, 0), shift(1, 1), shift(2, 9), shift(3, 10)]  # jump at index 2
    rolled = verify_rollout(advance, rows)
    assert rolled.broken_continuity >= 1
    assert rolled.longest < len(rows)


def test_a_history_initialised_latent_survives_the_holdout_chain():
    """A mechanic depending on history is representable only if latents start right.

    Here the true successor depends on how many actions have already been taken,
    which is not visible in the frame. With the initialiser the chain holds; with
    the default empty latent it cannot even begin.
    """
    def parity_after(i: int, pos: int) -> ObservedState:
        s = seen_at(pos + 1)
        s.grid[1, 1] = i % 2  # a cell driven by history, not by the board
        return s

    rows = []
    for i in range(6):
        before = seen_at(i)
        before.grid[1, 1] = (i - 1) % 2 if i else 0
        rows.append(Transition(index=i, before=before, action=MOVE,
                               after=parity_after(i, i),
                               before_norm_hash=f"n{i}", before_raw_hash=f"r{i}",
                               after_raw_hash=f"a{i}"))

    def needs_history(st, action):
        if "count" not in st.latent:
            return UNKNOWN
        n = st.latent["count"]
        nxt = seen_at(marker(st.observed.grid) + 1)
        nxt.grid[1, 1] = n % 2
        return Prediction(observed=nxt, latent={"count": n + 1})

    assert verify_rollout(needs_history, rows).longest == 0

    rolled = verify_rollout(needs_history, rows,
                            init_latent=lambda history, start: {"count": len(history)})
    assert rolled.longest >= 3
    assert rolled.usable


def test_a_latent_dependent_candidate_cannot_dodge_the_sweep():
    """Silent while its latent is empty, wrong once a rollout initialises it.

    The teacher-forced sweep alone does not catch this: with a constant
    initialiser every sweep call looks correct, and only chaining reveals that
    the candidate guesses once its own counter advances. `first_failure` is the
    signal, and `usable` previously ignored it.
    """
    rows = [shift(i, i) for i in range(8)]

    def dodges(st, action):
        if "count" not in st.latent:
            return UNKNOWN
        n = st.latent["count"]
        pos = marker(st.observed.grid)
        return Prediction(observed=seen_at(pos + 1 if n < 3 else 0),
                          latent={"count": n + 1})

    rolled = verify_rollout(dodges, rows, init_latent=lambda history, start: {"count": 0})
    assert rolled.longest == 3            # it does find a clean chain
    assert rolled.confident_errors == 0   # and the sweep sees nothing wrong
    assert rolled.first_failure is not None
    assert not rolled.usable


def test_the_sweep_itself_sees_the_latents_the_rollout_will_have():
    """A candidate silent without a latent must still be swept with one."""
    rows = [shift(i, i) for i in range(6)]

    def wrong_once_initialised(st, action):
        if "count" not in st.latent:
            return UNKNOWN
        return Prediction(observed=seen_at(0), latent=st.latent)

    blind = verify(wrong_once_initialised, rows)
    assert blind.claimed == 0  # without the initialiser it looks clean

    seeing = verify(wrong_once_initialised, rows,
                    init_latent=lambda history, start: {"count": len(history)})
    assert len(seeing.wrong) == len(rows)


# --- animation evidence -----------------------------------------------------

def test_a_cell_that_moves_and_returns_is_invisible_in_the_settled_diff():
    """The whole reason to record intermediate frames."""
    from arc3.ledger import animation_evidence

    before = board(2)
    mid = board(2)
    mid[0, 4] = 5
    after = board(2)

    ev = animation_evidence(before, [mid, after])
    assert ev.animated and ev.informative
    assert ev.settled_noop                      # the settled diff is empty
    assert ev.transient_cells(before, after) == {(0, 4): (5,)}


def test_the_timeline_preserves_order():
    """A set of values cannot tell A -> B -> C from C -> B -> A.

    Once the raw frames are discarded that loss is permanent, and selective
    surfacing would have nothing to surface.
    """
    from arc3.ledger import animation_evidence

    before = board(0)
    forward, backward = [], []
    for value in (3, 6, 9):
        g = board(0)
        g[1, 5] = value
        forward.append(g)
    for value in (9, 6, 3):
        g = board(0)
        g[1, 5] = value
        backward.append(g)
    settled = board(0)

    a = animation_evidence(before, forward + [settled])
    b = animation_evidence(before, backward + [settled])

    assert [step.changes[(1, 5)] for step in a.timeline[:3]] == [3, 6, 9]
    assert [step.changes[(1, 5)] for step in b.timeline[:3]] == [9, 6, 3]
    assert a.timeline != b.timeline
    assert a.transient_cells(before, settled) != b.transient_cells(before, settled)


def test_consecutive_identical_frames_are_dropped_from_the_timeline():
    from arc3.ledger import animation_evidence

    before = board(2)
    held = board(2)
    held[0, 6] = 4
    ev = animation_evidence(before, [held, held, held, board(2)])
    assert ev.frame_count == 4
    assert ev.distinct_frame_count == 2  # the change, then the revert


def test_a_single_frame_response_carries_no_animation_evidence():
    from arc3.ledger import animation_evidence

    ev = animation_evidence(board(2), [board(3)])
    assert not ev.animated


def test_the_default_summary_is_compact_metadata_not_the_timeline():
    """Surfacing costs tokens; recording does not. The model sees this by default."""
    from arc3.ledger import animation_evidence

    before = board(2)
    mid = board(2)
    mid[0, 4] = 5
    mid[1, 7] = 6
    ev = animation_evidence(before, [mid, board(2)])

    summary = ev.summary()
    assert set(summary) == {"frame_count", "distinct_frame_count",
                            "touched_cell_count", "bounding_box", "settled_noop"}
    assert summary["bounding_box"] == (0, 4, 1, 7)
    assert "timeline" not in summary


def test_animation_is_not_part_of_the_outcome_or_the_alias_key():
    """A simulator must predict settled frames, not presentation timing."""
    from arc3.ledger import AnimationEvidence

    plain = shift(0, 2)
    animated = Transition(
        index=1, before=plain.before, action=MOVE, after=plain.after,
        before_norm_hash=plain.before_norm_hash,
        before_raw_hash=plain.before_raw_hash,
        after_raw_hash=plain.after_raw_hash,
        animation=AnimationEvidence(frame_count=6, timeline=(FrameStep(changes={(1, 1): 3}),)))
    assert plain.outcome == animated.outcome
    assert plain.alias_key == animated.alias_key
    assert GameLedger("g", [plain, animated]).report().aliased_keys == 0


def test_alias_key_uses_the_complete_observable_state():
    """Identical boards on different attempts are not hidden state.

    The earlier key was (level, before_raw_hash, action), so an observable
    difference in attempt, status or the action set read as aliasing.
    """
    def same_board(index, *, attempt=0, status="NOT_FINISHED", actions=ACTIONS, after_pos=3):
        before = ObservedState(grid=board(2), level=1, attempt=attempt,
                               available_actions=actions, status=status)
        return Transition(index=index, before=before, action=MOVE,
                          after=seen_at(after_pos), before_norm_hash="n",
                          before_raw_hash="r", after_raw_hash=f"a{index}")

    for differing in ({"attempt": 1}, {"status": "GAME_OVER"}, {"actions": (1,)}):
        rows = [same_board(0), same_board(1, after_pos=9, **differing)]
        assert GameLedger("g", rows).report().aliased_keys == 0, differing

    # Truly identical observable state, two outcomes -> genuine aliasing.
    rows = [same_board(0), same_board(1, after_pos=9)]
    assert GameLedger("g", rows).report().aliased_keys == 1


def test_animation_triggers_are_ranked_not_limited_to_aliasing():
    """A deterministic animation can reveal a route even when nothing diverges."""
    from arc3.ledger import AnimationEvidence

    def anim(index, after, *, timeline, noop=False, before=None, raw="r"):
        b = before or seen_at(2)
        return Transition(index=index, before=b, action=MOVE, after=after,
                          before_norm_hash=f"n{index}", before_raw_hash=raw,
                          after_raw_hash=f"a{index}",
                          animation=AnimationEvidence(frame_count=3, timeline=timeline,
                                                      settled_noop=noop))

    aliased_a = anim(0, seen_at(3), timeline=(FrameStep(changes={(1, 1): 8}), FrameStep(changes={(1, 1): 0})), raw="same")
    aliased_b = anim(1, seen_at(9), timeline=(FrameStep(changes={(1, 2): 8}), FrameStep(changes={(1, 2): 0})), raw="same")
    # Distinct raw hashes: these two must NOT share an alias key with the pair.
    settled_noop = anim(2, seen_at(2), timeline=(FrameStep(changes={(1, 4): 7}), FrameStep(changes={(1, 4): 0})),
                        noop=True, raw="quiet")
    level_change = anim(3, seen_at(5, level=2), timeline=(FrameStep(changes={(1, 2): 3}), FrameStep(changes={(1, 2): 9})),
                        raw="moving")

    ledger = GameLedger("g", [aliased_a, aliased_b, settled_noop, level_change])
    ranked = ledger.animation_candidates()
    assert [p for p, _ in ranked] == [1, 1, 2, 3]

    # Priority 4 needs the model: no recorded data says where it fell silent.
    # Priority 4 requires LARGE transient activity, so this touches four cells.
    plain = anim(4, seen_at(6), raw="lonely",
                 timeline=(FrameStep(changes={(0, 1): 2, (0, 2): 2, (1, 3): 2, (1, 4): 2}),
                           FrameStep(changes={(0, 1): 0, (0, 2): 0, (1, 3): 0, (1, 4): 0})))
    with_unknown = GameLedger("g", [plain])
    assert with_unknown.animation_candidates() == []
    assert [p for p, _ in with_unknown.animation_candidates({plain.novelty_key})] == [4]


# --- v4: the four gaps found in 6721bc5 -------------------------------------

def test_a_resize_mid_animation_reconstructs_every_frame():
    """v3 skipped the first frame of a new shape, so priority-3 animations --
    the level transitions it exists to surface -- could not be reconstructed."""
    from arc3.ledger import animation_evidence

    before = np.zeros((2, 4), dtype=np.int8)
    before[0, 1] = 3
    small = before.copy()
    small[0, 2] = 5                      # one incremental step
    big = np.zeros((4, 8), dtype=np.int8)  # the level resizes the board
    big[3, 7] = 9
    settled = big.copy()
    settled[0, 0] = 2

    ev = animation_evidence(before, [small, big, settled])
    assert ev.distinct_frame_count == 3
    assert [step.resizes for step in ev.timeline] == [False, True, False]

    rebuilt = ev.frames(before)
    assert np.array_equal(rebuilt[0], small)
    assert np.array_equal(rebuilt[1], big)
    assert np.array_equal(rebuilt[2], settled)


def test_novelty_key_carries_the_observable_fields_too():
    """It was (level, masked_hash, action), which understated novelty."""
    def row(index, *, attempt=0, status="NOT_FINISHED", actions=ACTIONS):
        before = ObservedState(grid=board(2), level=1, attempt=attempt,
                               available_actions=actions, status=status)
        return Transition(index=index, before=before, action=MOVE, after=seen_at(3),
                          before_norm_hash="n", before_raw_hash="r",
                          after_raw_hash="a")

    base = row(0)
    for differing in ({"attempt": 1}, {"status": "GAME_OVER"}, {"actions": (1,)}):
        assert row(1, **differing).novelty_key != base.novelty_key, differing
    assert row(1).novelty_key == base.novelty_key


def test_settled_changes_are_not_counted_as_transient():
    """A marker that moves and stays is already in the settled diff."""
    from arc3.ledger import animation_evidence

    before, after = board(2), board(5)
    ev = animation_evidence(before, [board(5), after])
    assert ev.transient_cells(before, after) == {}
    assert len(ev.touched_cells) > 0          # cells WERE written
    assert ev.summary()["touched_cell_count"] > 0
    assert "transient_cell_count" not in ev.summary()

    t = Transition(index=0, before=seen_at(2), action=MOVE, after=seen_at(5),
                   before_norm_hash="n", before_raw_hash="r", after_raw_hash="a",
                   animation=ev)
    assert t.animation_summary()["transient_cell_count"] == 0

"""Every test here is a way verified knowledge could be silently destroyed."""

from __future__ import annotations

import json

import pytest

from arc3.memory import (
    DURABLE,
    VOLATILE,
    Fact,
    GameMemory,
    MemoryJournal,
    MemoryUpdate,
    Status,
    WinningPath,
    commit,
    transition,
)

MOVE = (1, None, None)
CLICK = (6, 3, 4)
KNOWN = set(range(100))


def conf(statement: str, *evidence: int) -> Fact:
    return Fact(statement, Status.CONFIRMED, evidence or (1,))


def ref(statement: str, *evidence: int) -> Fact:
    return Fact(statement, Status.REFUTED, evidence or (2,))


def guess(statement: str) -> Fact:
    return Fact(statement, Status.ASSUMED)


def path(**kw) -> WinningPath:
    return WinningPath(level=kw.pop("level", 1), start_signature=kw.pop("sig", "abc"),
                       actions=kw.pop("actions", (MOVE, CLICK)),
                       expected_outcomes=kw.pop("outcomes", ()),
                       evidence=kw.pop("evidence", (3,)))


def populated() -> GameMemory:
    m = GameMemory("lp85")
    m.apply(MemoryUpdate(
        mechanics=[conf("blocks fall", 3)],
        goal_evidence=[conf("the exit glows", 8)],
        counterexamples=[ref("ACTION5 teleports", 6)],
        action_semantics={MOVE: [conf("ACTION1 moves left", 7)]},
        winning_paths=[path()],
        current_plan=[MOVE, MOVE],
        level_coordinates={"exit": [4, 9]},
        object_identities={"player": [0, 0]},
        goal_guesses=[guess("reach the corner")],
    ))
    return m


# --- all-or-nothing ---------------------------------------------------------

def test_a_valid_field_is_not_applied_when_a_later_field_is_invalid():
    """The defect that made 'all-or-nothing' a promise rather than a property:
    mechanics was written, then winning_paths raised."""
    m = populated()
    before = m.snapshot()
    with pytest.raises(ValueError, match="winning_paths"):
        m.apply(MemoryUpdate(mechanics=[conf("new and valid", 4)], winning_paths=[1]))
    assert m.snapshot() == before


@pytest.mark.parametrize("bad", [
    MemoryUpdate(current_plan=42),
    MemoryUpdate(current_plan=[(1, 2)]),
    MemoryUpdate(action_semantics={"ACTION1": [Fact("x")]}),
    MemoryUpdate(level_coordinates=["not", "a", "dict"]),
    MemoryUpdate(object_identities={"o": object()}),
    MemoryUpdate(mechanics=["a string, not a Fact"]),
    MemoryUpdate(winning_paths=[path(), "not a path"]),
])
def test_malformed_updates_raise_and_change_nothing(bad):
    m = populated()
    before = m.snapshot()
    with pytest.raises(ValueError):
        m.apply(bad)
    assert m.snapshot() == before


def test_an_omitted_field_keeps_its_prior_value():
    m = populated()
    m.apply(MemoryUpdate(goal_evidence=[conf("green ends the level", 9)]))
    assert [f.statement for f in m.mechanics] == ["blocks fall"]


def test_an_empty_collection_does_not_clear():
    m = populated()
    m.apply(MemoryUpdate(mechanics=[], action_semantics={}, winning_paths=[],
                         current_plan=[], level_coordinates={}, object_identities={}))
    assert m.mechanics and m.action_semantics and m.winning_paths
    assert m.current_plan == [MOVE, MOVE]
    assert m.level_coordinates == {"exit": [4, 9]}


# --- belief revision, not precedence ---------------------------------------

def test_a_refuted_claim_cannot_be_reintroduced_as_a_guess():
    """The old rule let ASSUMED overwrite REFUTED, resurrecting a dead claim."""
    m = GameMemory("g")
    m.apply(MemoryUpdate(mechanics=[ref("ACTION3 opens the door", 11)]))
    delta = m.apply(MemoryUpdate(mechanics=[guess("ACTION3 opens the door")]))
    assert m.mechanics[0].status is Status.REFUTED
    assert delta.blocked == ["ACTION3 opens the door"]


def test_a_confirmed_claim_cannot_be_unseated_by_a_guess():
    m = GameMemory("g")
    m.apply(MemoryUpdate(mechanics=[conf("water flows down", 4)]))
    delta = m.apply(MemoryUpdate(mechanics=[guess("water flows down")]))
    assert m.mechanics[0].status is Status.CONFIRMED
    assert delta.blocked == ["water flows down"]


def test_a_wrong_confirmation_can_be_corrected_and_becomes_contested():
    """The old rule made CONFIRMED permanent, so a mistaken belief was forever."""
    m = GameMemory("g")
    m.apply(MemoryUpdate(mechanics=[conf("the door needs a key", 4)]))
    delta = m.apply(MemoryUpdate(mechanics=[ref("the door needs a key", 19)]))
    assert m.mechanics[0].status is Status.CONTESTED
    assert set(m.mechanics[0].evidence) == {4, 19}
    assert delta.contested == ["the door needs a key"]


def test_contested_stays_contested_and_accumulates_evidence():
    m = GameMemory("g")
    m.apply(MemoryUpdate(mechanics=[conf("x", 1)]))
    m.apply(MemoryUpdate(mechanics=[ref("x", 2)]))
    m.apply(MemoryUpdate(mechanics=[conf("x", 3)]))
    assert m.mechanics[0].status is Status.CONTESTED
    assert set(m.mechanics[0].evidence) == {1, 2, 3}


def test_an_assumption_is_upgraded_by_confirmation_and_keeps_both_citations():
    m = GameMemory("g")
    m.apply(MemoryUpdate(mechanics=[Fact("ice is slippery", Status.ASSUMED, (2,))]))
    m.apply(MemoryUpdate(mechanics=[conf("ice is slippery", 5)]))
    assert m.mechanics[0].status is Status.CONFIRMED
    assert set(m.mechanics[0].evidence) == {2, 5}


def test_two_conflicting_confirmed_semantics_are_surfaced_not_overwritten():
    """The old dict kept one Fact per action, so the second silently won."""
    m = GameMemory("g")
    m.apply(MemoryUpdate(action_semantics={MOVE: [conf("moves left", 4)]}))
    m.apply(MemoryUpdate(action_semantics={MOVE: [conf("rotates the block", 9)]}))
    assert len(m.action_semantics[MOVE]) == 2
    assert m.contested() == {"moves left", "rotates the block"}


def test_confirmed_and_refuted_both_require_evidence():
    for status in (Status.CONFIRMED, Status.REFUTED, Status.CONTESTED):
        with pytest.raises(ValueError, match="without evidence"):
            Fact("the goal is the red square", status)


# --- evidence must exist ----------------------------------------------------

def test_evidence_is_checked_against_the_ledger_when_it_is_available():
    m = GameMemory("g")
    with pytest.raises(ValueError, match="do not exist"):
        m.apply(MemoryUpdate(mechanics=[conf("invented", 999999)]), known_transitions=KNOWN)
    assert m.mechanics == []
    m.apply(MemoryUpdate(mechanics=[conf("real", 12)]), known_transitions=KNOWN)
    assert m.mechanics[0].statement == "real"


def test_a_winning_paths_evidence_is_checked_too():
    m = GameMemory("g")
    with pytest.raises(ValueError, match="do not exist"):
        m.apply(MemoryUpdate(winning_paths=[path(evidence=(500000,))]),
                known_transitions=KNOWN)


# --- winning paths ----------------------------------------------------------

def test_a_path_is_not_replayable_from_a_different_level_or_state():
    m = populated()
    assert m.replayable(1, "abc")
    assert m.replayable(2, "abc") == []
    assert m.replayable(1, "different-board") == []


def test_a_path_without_a_signature_or_actions_is_rejected():
    with pytest.raises(ValueError, match="no actions"):
        WinningPath(level=1, start_signature="a", actions=())
    with pytest.raises(ValueError, match="signature"):
        WinningPath(level=1, start_signature="", actions=(MOVE,))


def test_expected_outcomes_must_align_with_actions():
    with pytest.raises(ValueError, match="1:1"):
        WinningPath(level=1, start_signature="a", actions=(MOVE, CLICK),
                    expected_outcomes=("only-one",))


# --- the level transition ---------------------------------------------------

def test_a_transition_keeps_the_game_and_drops_the_level():
    m = populated()
    m.on_level_transition(2)
    for name in DURABLE:
        assert getattr(m, name), f"{name} should survive a transition"
    for name in VOLATILE:
        assert not getattr(m, name), f"{name} should be dropped at a transition"


# --- persistence that can actually be loaded --------------------------------

def test_the_store_round_trips_through_its_snapshot():
    m = populated()
    restored = GameMemory.restore(m.snapshot())
    assert restored.snapshot() == m.snapshot()
    assert restored.action_semantics[MOVE][0].statement == "ACTION1 moves left"
    assert restored.winning_paths[0].actions == (MOVE, CLICK)


def test_a_killed_run_resumes_from_the_journal(tmp_path):
    """An audit log that cannot be loaded is not persistence."""
    journal = MemoryJournal(tmp_path / "m.jsonl")
    m = populated()
    commit(m, MemoryUpdate(mechanics=[conf("lava kills", 30)]), journal)

    resumed = MemoryJournal(tmp_path / "m.jsonl").restore()
    assert [f.statement for f in resumed.mechanics] == ["blocks fall", "lava kills"]
    assert resumed.action_semantics[MOVE][0].status is Status.CONFIRMED


def test_the_level_transition_is_journalled(tmp_path):
    path_ = tmp_path / "m.jsonl"
    journal = MemoryJournal(path_)
    m = populated()
    transition(m, 2, journal)
    entries = journal.entries()
    assert entries[-1]["event"] == "level_transition"
    assert entries[-1]["before"]["current_plan"] == [list(MOVE), list(MOVE)]
    assert entries[-1]["after"]["current_plan"] == []
    assert MemoryJournal(path_).restore().level == 2


def test_commit_persists_before_the_action_that_could_end_the_level(tmp_path):
    journal = MemoryJournal(tmp_path / "m.jsonl")
    m = GameMemory("g")
    commit(m, MemoryUpdate(goal_evidence=[conf("green ends the level", 12)]), journal)
    assert m.unpersisted is False
    m.on_level_transition(2)
    assert m.goal_evidence


def test_a_torn_journal_tail_costs_one_entry_not_the_store(tmp_path):
    path_ = tmp_path / "m.jsonl"
    journal = MemoryJournal(path_)
    m = populated()
    commit(m, MemoryUpdate(mechanics=[conf("a", 5)]), journal)
    commit(m, MemoryUpdate(mechanics=[conf("b", 6)]), journal)
    text = path_.read_text()
    path_.write_text(text[: len(text) - 30])
    assert len(journal.entries()) == 1
    assert journal.restore() is not None


def test_memory_is_per_game_and_never_merged():
    a, b = GameMemory("lp85"), GameMemory("ka59")
    a.apply(MemoryUpdate(mechanics=[conf("blocks fall", 1)]))
    assert b.mechanics == []

"""The future batch guard must never use the current action to learn its mask."""

from arc3.no_impact import HousekeepingBand


def board(tick: int, center: int = 0):
    return ((tick, tick, tick, tick), (0, center, 0, 0), (0, 0, 0, 0))


def test_hud_only_actions_become_classifiable_after_warmup():
    band = HousekeepingBand(window=20, threshold=0.9, warmup=8)
    for tick in range(1, 9):
        result = band.observe(board(tick - 1), board(tick), before_level=1, after_level=1)
        assert result.gameplay_changed  # no evidence existed when the action was classified
    result = band.observe(board(8), board(9), before_level=1, after_level=1)
    assert result.no_impact
    assert result.reason == "hud_band"
    assert result.masked_rows == frozenset({0})


def test_a_real_object_change_is_not_hidden_by_the_hud_band():
    band = HousekeepingBand(warmup=8)
    for tick in range(1, 9):
        band.observe(board(tick - 1), board(tick), before_level=1, after_level=1)
    result = band.observe(board(8), board(9, center=3), before_level=1, after_level=1)
    assert result.gameplay_changed
    assert not result.no_impact


def test_level_transition_cannot_be_called_no_impact_and_resets_band():
    band = HousekeepingBand(warmup=8)
    for tick in range(1, 9):
        band.observe(board(tick - 1), board(tick), before_level=1, after_level=1)
    transition = band.observe(board(8), board(9), before_level=1, after_level=2)
    assert transition.gameplay_changed
    assert transition.reason == "level_transition"
    assert band.band() == (frozenset(), frozenset())


def test_exact_noop_is_visible_without_a_learned_band():
    result = HousekeepingBand().observe(board(0), board(0), before_level=1, after_level=1)
    assert result.no_impact
    assert result.reason == "exact_noop"


def test_resize_is_progress_not_a_hud_only_change():
    result = HousekeepingBand().observe(board(0), ((0,),), before_level=1, after_level=1)
    assert result.gameplay_changed
    assert result.reason == "shape_change"

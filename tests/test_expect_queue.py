from arc3.expect_queue import QueuedAction, check_expect, halt_index, run_queue


class _Frame:
    def __init__(self, cells):
        self._cells = cells

    def cell(self, row: int, col: int):
        return self._cells.get((row, col))


class _Env:
    def __init__(self, frames):
        self._frames = list(frames)

    def step(self, action_id: str, data=None):
        return self._frames.pop(0)


def test_queue_halts_on_mismatch() -> None:
    env = _Env([
        _Frame({(0, 0): 1}),
        _Frame({(0, 0): 9}),
        _Frame({(0, 0): 2}),
    ])
    queue = [
        QueuedAction("ACTION1", expect={(0, 0): 1}),
        QueuedAction("ACTION2", expect={(0, 0): 2}),
        QueuedAction("ACTION3", expect={(0, 0): 2}),
    ]
    results = run_queue(env, queue)
    assert [r.ok for r in results] == [True, False]
    assert halt_index(results) == 1
    assert len(results) == 2


def test_check_expect_reports_cells() -> None:
    bad = check_expect(_Frame({(1, 1): 3}), {(1, 1): 4, (2, 2): 0})
    assert bad[(1, 1)] == (3, 4)
    assert bad[(2, 2)] == (None, 0)

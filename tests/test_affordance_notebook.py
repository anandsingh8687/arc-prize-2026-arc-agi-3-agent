"""The control must stay unchanged and the treatment must be exactly scoped."""

from __future__ import annotations

import json

from research.build_affordance_screen_notebook import build, source


def test_affordance_builds_parseable_private_smoke_and_screen():
    for smoke in (True, False):
        path = build(smoke)
        notebook = json.loads(path.read_text())
        package = source(notebook["cells"][6])
        experiment = source(notebook["cells"][8])
        assert "AFFORDANCE_ADAPTER_IMPORTED" in package
        assert "add_affordance_instruction(self)" in experiment
        assert "_AffordanceToolAgent if spec['arm'] == 'A' else _Gate2ToolAgent" in experiment
        assert "('W', 'W-repeat', 'A')" not in experiment  # no trial-order accident
        assert '"trial_id": "W-repeat"' in experiment
        assert '"trial_id": "A"' in experiment
        assert "kaggle competitions submit" not in experiment.lower()
        assert "tn36-ef4dde99" in experiment
        assert "AFFORDANCE_SCREEN_FINAL" in source(notebook["cells"][9])


def test_affordance_prompt_distinguishes_state_specific_noop_from_global_noop():
    from arc3.duck_affordance_adapter import AFFORDANCE_ADDENDUM

    assert "current board configuration" in AFFORDANCE_ADDENDUM
    assert "only after relevant state changes" in AFFORDANCE_ADDENDUM
    assert "never repeatedly" in AFFORDANCE_ADDENDUM
    assert "level transition" in AFFORDANCE_ADDENDUM

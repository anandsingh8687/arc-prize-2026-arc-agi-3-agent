"""Catch stale embedded agent files before any Kaggle GPU upload."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("variant,mode,wall_seconds", [
    ("timer", "smoke", "0"), ("timer", "screen", "180"),
    ("repeat", "smoke", "0"), ("repeat", "screen", "inf"),
])
def test_generated_notebook_embeds_exact_reviewed_source(
    variant: str, mode: str, wall_seconds: str,
):
    suffix = "" if variant == "timer" else "-repeat"
    path = ROOT / "notebooks" / f"recovery{suffix}-{mode}" / f"arc3-recovery{suffix}-{mode}.ipynb"
    notebook = json.loads(path.read_text())
    package = ast.parse("".join(notebook["cells"][6]["source"]))
    embedded = {}
    for node in ast.walk(package):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "write_text" or not node.args:
            continue
        target = node.func.value
        if not isinstance(target, ast.BinOp) or not isinstance(target.right, ast.Constant):
            continue
        embedded[target.right.value] = ast.literal_eval(node.args[0])
    for name in ("recovery.py", "duck_recovery_adapter.py"):
        if variant == "timer" and name == "duck_recovery_adapter.py":
            # The executed September 16 notebook is an immutable historical
            # artifact. Its embedded source must not silently become today's
            # repeat-only adapter.
            assert hashlib.sha256(embedded[name].encode()).hexdigest() == (
                "029ec1e89af9182e81c7e91b396abe2f59665ac9a34c466c60a6b480dc06c2d7"
            )
        else:
            assert embedded[name] == (ROOT / "arc3" / name).read_text()
    settings = "".join(notebook["cells"][7]["source"])
    assert f"os.environ['ARC3_RECOVERY_WALL_SECONDS'] = '{wall_seconds}'" in settings
    if variant == "repeat":
        assert "os.environ['ARC3_RECOVERY_ACTION_LIMIT'] = '0'" in settings
    experiment = "".join(notebook["cells"][8]["source"])
    assert "_RecoveryToolAgent if spec['arm'] == 'S' else _Gate2ToolAgent" in experiment
    assert '"recovery_probe_count"' in settings
    assert '"recovery_probe_count"' in experiment

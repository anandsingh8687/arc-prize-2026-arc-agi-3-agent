#!/usr/bin/env python3
"""Probe exact packaged vLLM dispatch on CPU, not engine/model generation.

Only the registry's two dispatch functions are executed; schema/grammar builders
are stubs. The source layer is pinned by SHA256 before reading any member.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

LAYER_SHA256 = "10dce885652a53a2e644a75d256b90830663330988b8599c3c0e56cd6c8a4675"
PREFIX = "usr/local/lib/python3.12/dist-packages/vllm/"


def probe(layer: Path) -> dict:
    with layer.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != LAYER_SHA256:
        raise ValueError("Unexpected runtime layer SHA256")
    with tarfile.open(layer) as archive:
        registry = archive.extractfile(PREFIX + "tool_parsers/structural_tag_registry.py").read()
        harmony = archive.extractfile(PREFIX + "parser/harmony.py").read()
    tree = ast.parse(registry)
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in {"_any_tool_strict", "get_model_structural_tag"}]
    assert len(functions) == 2
    unit = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *functions], type_ignores=[])
    ast.fix_missing_locations(unit)

    class FunctionTool:
        pass

    class ChatCompletionToolsParam:
        def __init__(self, strict):
            self.function = SimpleNamespace(strict=strict)

    namespace = {
        "FunctionTool": FunctionTool,
        "ChatCompletionToolsParam": ChatCompletionToolsParam,
        "_dump_tool_for_xgrammar": lambda tool: tool,
        "_dump_tool_choice_for_xgrammar": lambda choice: choice,
        "normalize_tool_choice": lambda tools, choice: (tools, [], choice),
        "_VLLM_STRUCTURAL_TAG_REGISTRY": {
            "harmony": lambda tools, builtin, choice, reasoning: "structural_grammar_selected"
        },
    }
    exec(compile(unit, "pinned-vllm-structural-tag-registry", "exec"), namespace)
    dispatch = namespace["get_model_structural_tag"]
    observed = {
        "required_non_strict": dispatch("harmony", [ChatCompletionToolsParam(None)], "required", True),
        "auto_non_strict": dispatch("harmony", [ChatCompletionToolsParam(None)], "auto", True),
        "auto_strict": dispatch("harmony", [ChatCompletionToolsParam(True)], "auto", True),
    }
    assert observed == {
        "required_non_strict": "structural_grammar_selected",
        "auto_non_strict": None,
        "auto_strict": "structural_grammar_selected",
    }
    assert b'_END_TAG = ["<|end|>", ""]' in harmony
    return {
        "layer_sha256": digest,
        "registry_sha256": hashlib.sha256(registry).hexdigest(),
        "harmony_sha256": hashlib.sha256(harmony).hexdigest(),
        "dispatch": observed,
        "engine_and_model_not_executed": True,
        "actual_v2_generated_tokens_unavailable": True,
        "passed": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("layer", type=Path)
    print(json.dumps(probe(parser.parse_args().layer), sort_keys=True))

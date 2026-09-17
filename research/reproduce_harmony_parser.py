#!/usr/bin/env python3
"""CPU-only Harmony protocol fixtures, not a replay of missing V2 output.

Run with openai-harmony==0.0.8 and the verified offline tokenizer cache.
No model, API, game source, generated code execution, or GPU is used.
The synthetic invalid stream reproduces the exact error class/message; it
does NOT establish that V2 emitted this particular token sequence.
"""
from __future__ import annotations

import json
from importlib.metadata import version

from openai_harmony import HarmonyEncodingName, Role, StreamableParser, load_harmony_encoding


EXPECTED_ERROR = "Unexpected token 200002 while expecting start token 200006"
FIXTURES = {
    "valid_final": "<|channel|>final<|message|>4<|return|>",
    "valid_tool": ' to=functions.submit_number<|channel|>commentary<|message|>{"value":4}<|call|>',
    "invalid_double_ending": "<|channel|>final<|message|>4<|end|><|return|>",
}


def run() -> dict:
    encoding = load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)
    results = {}
    for name, text in FIXTURES.items():
        parser = StreamableParser(encoding, role=Role.ASSISTANT)
        error = None
        ids = encoding.encode(text, allowed_special="all")
        try:
            for token_id in ids:
                parser.process(token_id)
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
        results[name] = {"tokens": ids, "messages": len(parser.messages), "error": error}
    assert results["valid_final"]["error"] is None
    assert results["valid_final"]["messages"] == 1
    assert results["valid_tool"]["error"] is None
    assert results["valid_tool"]["messages"] == 1
    assert results["invalid_double_ending"]["error"] == {
        "type": "HarmonyError", "message": EXPECTED_ERROR}
    return {
        "harmony_version": version("openai-harmony"),
        "synthetic_fixture_not_actual_v2_output": True,
        "fixtures": results,
        "passed": True,
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))

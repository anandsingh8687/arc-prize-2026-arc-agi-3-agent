"""Adversarial checks for the retrospective stall diagnostic."""

import json
from pathlib import Path
import tempfile
import unittest

from research.stall_trace_audit import audit


class StallTraceAuditTests(unittest.TestCase):
    def test_warning_does_not_imply_no_future_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example_events.jsonl"
            events = [{"type": "initial", "board": [[0]], "level": 1,
                       "state": "NOT_FINISHED"}]
            for number in range(1, 5):
                events.append({"type": "action", "action_num": number,
                               "action_name": "ACTION1", "action_display": "UP",
                               "board": [[0]], "level": 1, "state": "NOT_FINISHED",
                               "level_completed": False})
            events.append({"type": "action", "action_num": 5,
                           "action_name": "ACTION2", "action_display": "DOWN",
                           "board": [[1]], "level": 2, "state": "NOT_FINISHED",
                           "level_completed": True})
            path.write_text("".join(json.dumps(event) + "\n" for event in events))
            result = audit(path)
            self.assertEqual(result["trigger_at"], 4)
            self.assertEqual(result["levels_after_trigger"], 1)
            self.assertEqual(result["first_completion_at"], 5)

    def test_prior_noop_does_not_prove_an_action_can_never_work(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example_events.jsonl"
            events = [
                {"type": "initial", "board": [[0]], "level": 1,
                 "state": "NOT_FINISHED"},
                {"type": "action", "action_name": "ACTION1", "action_display": "UP",
                 "board": [[0]], "level": 1, "state": "NOT_FINISHED"},
                {"type": "action", "action_name": "ACTION1", "action_display": "UP",
                 "board": [[1]], "level": 1, "state": "NOT_FINISHED"},
            ]
            path.write_text("".join(json.dumps(event) + "\n" for event in events))
            result = audit(path)
            self.assertEqual(result["alias_exceptions"], 1)

    def test_stall_window_resets_on_level_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example_events.jsonl"
            events = [{"type": "initial", "board": [[0]], "level": 1,
                       "state": "NOT_FINISHED"}]
            for _ in range(3):
                events.append({"type": "action", "action_name": "ACTION1",
                               "action_display": "UP", "board": [[0]],
                               "level": 1, "state": "NOT_FINISHED"})
            events.append({"type": "action", "action_name": "ACTION2",
                           "action_display": "DOWN", "board": [[1]],
                           "level": 2, "state": "NOT_FINISHED",
                           "level_completed": True})
            for _ in range(3):
                events.append({"type": "action", "action_name": "ACTION1",
                               "action_display": "UP", "board": [[1]],
                               "level": 2, "state": "NOT_FINISHED"})
            path.write_text("".join(json.dumps(event) + "\n" for event in events))
            self.assertIsNone(audit(path)["trigger_at"])


if __name__ == "__main__":
    unittest.main()

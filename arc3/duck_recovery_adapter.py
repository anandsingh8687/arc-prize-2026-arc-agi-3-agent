"""Opt-in stall-triggered recovery on the same Duck actor as the control arm.

The intervention requires one structured, legal diagnostic action, records the
actual transition, and otherwise leaves Duck unchanged. It is not a second
memory treatment and it never silently vetoes ordinary actions.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any

from inference.agent.runtime_state import frame_to_payload, load_runtime_state
from inference.agent.tool_agent import ToolAgent, _ToolDispatchResult

from arc3.recovery import StallSignal, detect_stall, recovery_instruction, validate_recovery_probe


class RecoveryToolAgent(ToolAgent):
    def _ensure_session(self, state_path: Path) -> None:
        previous_runtime_dir = getattr(self, "_session_runtime_dir", None)
        super()._ensure_session(state_path)
        if previous_runtime_dir != self._session_runtime_dir:
            self._recovery_shown_levels: set[int] = set()
            self._recovery_prompt_count = 0
            self._recovery_probe_count = 0
            self._recovery_rejections = 0
            self._recovery_last_reason: str | None = None
            self._recovery_pending = False
            self._recovery_signal: StallSignal | None = None
            self._recovery_active_level: int | None = None
            self._recovery_level_started = time.monotonic()
            self._recovery_event_path = state_path.with_suffix(".recovery.jsonl")

    def _build_user_prompt(self, action_num: int, **kwargs: Any) -> str:
        prompt = super()._build_user_prompt(action_num, **kwargs)
        frame = kwargs.get("current_frame")
        level = int(frame.level) if frame is not None else 1
        if level != self._recovery_active_level:
            self._recovery_active_level = level
            self._recovery_level_started = time.monotonic()
            self._recovery_pending = False
        history = kwargs.get("history_entries") or []
        action_limit = int(os.environ.get("ARC3_RECOVERY_ACTION_LIMIT", "80"))
        if action_limit < 0:
            raise ValueError("ARC3_RECOVERY_ACTION_LIMIT must be non-negative")
        # Zero disables the blunt action-count trigger, without disabling the
        # evidence-based repeated-no-op trigger in detect_stall.
        effective_limit = action_limit or len(history) + 1
        signal = detect_stall(
            history,
            first_level_limit=effective_limit,
            later_level_limit=effective_limit,
        )
        elapsed = time.monotonic() - self._recovery_level_started
        wall_limit = float(os.environ.get("ARC3_RECOVERY_WALL_SECONDS", "180"))
        if signal is None and elapsed >= wall_limit:
            signal = StallSignal(
                level=level, reason="time_without_completion",
                actions_on_level=0, repeated_in_last_ten=0,
                repeated_action=None, border_only_changes=0,
                elapsed_seconds=elapsed,
            )
        if signal is None or signal.level in self._recovery_shown_levels:
            return prompt
        self._recovery_shown_levels.add(signal.level)
        self._recovery_prompt_count += 1
        self._recovery_last_reason = signal.reason
        self._recovery_signal = signal
        self._recovery_pending = True
        return prompt + recovery_instruction(signal) + (
            " For the diagnostic action, provide a recovery_probe JSON sibling of code "
            "with goal_predicate, hypotheses (exactly two objects each containing "
            "explanation, observed_evidence, predicted_outcome), action (one legal "
            "action object such as {\"action\":\"RIGHT\"}), next_if_first and "
            "next_if_second. Predictions must differ. Your Python code must execute "
            "exactly that one action; no batch. The host records its actual outcome."
        )

    def _tools(self, state_path: Path) -> list[dict[str, Any]]:
        tools = super()._tools(state_path)
        if self._recovery_pending:
            function = tools[0]["function"]
            function["parameters"]["properties"]["recovery_probe"] = {
                "type": "object",
                "description": "Two evidenced hypotheses, one discriminating legal action and conditional next steps.",
            }
            function["parameters"]["required"].append("recovery_probe")
        return tools

    def _append_event(self, event: dict[str, Any]) -> None:
        self._recovery_event_path.parent.mkdir(parents=True, exist_ok=True)
        with self._recovery_event_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, sort_keys=True, default=str) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _run_python_tool(self, state_path: Path, arguments: dict[str, Any]) -> _ToolDispatchResult:
        self._ensure_session(state_path)
        if not self._recovery_pending:
            return super()._run_python_tool(state_path, arguments)
        try:
            probe = validate_recovery_probe(arguments.get("recovery_probe"), self._current_valid_actions)
        except ValueError as exc:
            self._recovery_rejections += 1
            return _ToolDispatchResult(json.dumps({"error": f"recovery_probe rejected: {exc}"}))
        original_callback = self._step_env_callback
        if original_callback is None:
            return _ToolDispatchResult(json.dumps({"error": "diagnostic action unavailable"}))
        executed = False

        def one_probe(payload: dict[str, Any]) -> dict[str, Any]:
            nonlocal executed
            actions = payload.get("actions")
            if executed or actions != [probe["action"]]:
                raise ValueError("recovery requires exactly the declared single diagnostic action")
            before, history_before = load_runtime_state(state_path)
            result = original_callback(payload)
            after, history_after = load_runtime_state(state_path)
            executed = True
            self._recovery_pending = False
            self._append_event({
                "signal": vars(self._recovery_signal) if self._recovery_signal else None,
                "probe": probe,
                "before": frame_to_payload(before),
                "after": frame_to_payload(after),
                "history_count_before": len(history_before),
                "history_count_after": len(history_after),
                "actual_action": history_after[-1].action if len(history_after) > len(history_before) else None,
                "environment_result": result,
            })
            self._recovery_probe_count += 1
            return result

        self._step_env_callback = one_probe
        try:
            return super()._run_python_tool(state_path, arguments)
        finally:
            self._step_env_callback = original_callback

"""Text-only, native-function transport for a Duck scene agent using GPT-OSS.

This mixin is deliberately opt-in.  Put it before ``SceneObservationMixin``
and Duck's ``ToolAgent`` in the MRO.  It does not alter the action loop,
tool limits, or the scene renderer; it only adapts the messages and request
payload crossing the model boundary.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests

from inference.agent import tool_agent as _duck_tool_agent
from inference.agent.prompts import MULTIMODAL_CONTEXT_ADDENDUM, TOOL_CALL_FORMAT_GUIDANCE


NATIVE_FUNCTION_CALL_GUIDANCE = (
    "Call `python` through the native function-calling interface when you need "
    "to use it. Do not write XML, tags, or a textual tool-call wrapper in "
    "assistant content or reasoning."
)

_HTTP_ERROR_BODY_LIMIT = 4096


def _native_prompt(prompt: str) -> str:
    """Remove Duck's model-specific call-format wording without touching gameplay rules."""
    return (
        prompt.replace(MULTIMODAL_CONTEXT_ADDENDUM, "")
        .replace(TOOL_CALL_FORMAT_GUIDANCE, NATIVE_FUNCTION_CALL_GUIDANCE)
    )


def _require_text_only_messages(messages: list[dict[str, Any]]) -> None:
    """Fail closed if a caller would send a vision/content-part payload to GPT-OSS."""
    for index, message in enumerate(messages):
        content = message.get("content")
        if content is None or isinstance(content, str):
            continue
        raise ValueError(
            "GPT-OSS native transport requires text-only messages; "
            f"message {index} has non-text content."
        )


def _native_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copy message envelopes while replacing only inherited format guidance."""
    normalized: list[dict[str, Any]] = []
    for message in messages:
        copied = dict(message)
        if isinstance(copied.get("content"), str):
            copied["content"] = _native_prompt(copied["content"])
        normalized.append(copied)
    return normalized


def _contains_xml_tool_markup(message: dict[str, Any]) -> bool:
    for field in ("content", "reasoning", "reasoning_content"):
        value = message.get(field)
        if isinstance(value, str) and ("<tool_call" in value.lower() or "<function=" in value.lower()):
            return True
    return False


class GPTOSSNativeFunctionMixin:
    """Adapt an existing Duck + scene agent to GPT-OSS function transport.

    Assumes Duck's current ``ToolAgent.analyze`` continues to execute native
    ``tool_calls`` and append OpenAI ``role='tool'`` result messages with the
    corresponding ``tool_call_id``.  The mixin intentionally leaves that
    action/time-limit logic untouched.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._system_prompt = _native_prompt(self._system_prompt)

    def _build_user_prompt(self, action_num: int, **kwargs: Any) -> str:
        return _native_prompt(super()._build_user_prompt(action_num, **kwargs))

    def _build_user_message(self, user_prompt: str, current_frame: Any) -> dict[str, Any]:
        """Send the complete SceneObservationMixin prompt as text, never process an image.

        The concrete GPT-OSS class must instrument this method directly: the
        base implementation may construct an image attachment before returning,
        which would make a base-only modality counter describe the wrong
        payload boundary.
        """
        del current_frame
        return {"role": "user", "content": _native_prompt(user_prompt)}

    def _chat_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None,
        request_timeout_seconds: float | None = None,
    ) -> Any:
        """Use standard OpenAI tools/tool_calls without Qwen vLLM template options."""
        messages = _native_messages(messages)
        _require_text_only_messages(messages)
        payload: dict[str, Any] = {
            "model": self._model.model_id,
            "messages": messages,
            "stream": False,
            "temperature": _duck_tool_agent._LOCAL_ANALYZER_TEMPERATURE,
            "top_p": _duck_tool_agent._LOCAL_ANALYZER_TOP_P,
            "reasoning_effort": "high",
            "ignore_eos": False,
        }
        if self._max_output_tokens is not None:
            payload["max_tokens"] = self._max_output_tokens
        if _duck_tool_agent._LOCAL_ANALYZER_SEED >= 0:
            payload["seed"] = _duck_tool_agent._LOCAL_ANALYZER_SEED
        if tools:
            payload["tools"] = tools
            # GPT-OSS's supported native function mode is auto.  Do not inherit
            # Duck's model-specific required/named-tool selection here.
            payload["tool_choice"] = "auto"

        sequence = int(getattr(self, "_gptoss_http_sequence", 0)) + 1
        self._gptoss_http_sequence = sequence
        self._gptoss_audit("request", sequence, payload)

        response = requests.post(
            f"{self._model.base_url.rstrip('/')}/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=(
                request_timeout_seconds
                if request_timeout_seconds is not None
                else self._timeout
            ),
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = str(response.text or "")[:_HTTP_ERROR_BODY_LIMIT].strip()
            message = f"{exc}"
            if detail:
                message += f" | response: {detail}"
            raise requests.RequestException(message) from exc
        if getattr(response, "status_code", 200) >= 400:
            detail = str(response.text or "")[:_HTTP_ERROR_BODY_LIMIT].strip()
            message = f"{response.status_code} Error"
            if detail:
                message += f" | response: {detail}"
            raise requests.RequestException(message)
        response_payload = response.json()
        self._gptoss_audit("response", sequence, response_payload)
        choices = response_payload.get("choices", [])
        if not choices:
            raise requests.RequestException("server returned no choices")
        choice = choices[0]
        message = choice.get("message", {})
        if not message.get("tool_calls") and _contains_xml_tool_markup(message):
            # Duck's base agent has a legacy XML recovery fallback.  Refuse XML
            # here so GPT-OSS cannot enter that parser path; native tool_calls
            # are the only accepted transport for this adapter.
            raise requests.RequestException(
                "GPT-OSS response used unsupported XML tool markup; expected native tool_calls."
            )
        return _duck_tool_agent._ChatCompletionResult(
            message=message,
            finish_reason=str(choice.get("finish_reason", "") or ""),
            usage=response_payload.get("usage"),
        )

    def _gptoss_audit(self, event: str, sequence: int, payload: dict[str, Any]) -> None:
        """Persist the actual normalized HTTP body, never authorization headers.

        Opt-in for bounded development runs; the factory supplies a per-game
        path. Write failure stops the request rather than claiming evidence
        that was never preserved.
        """
        audit_path = getattr(self, "_gptoss_audit_path", None)
        if audit_path is None:
            return
        path = Path(audit_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"event": event, "sequence": sequence, "epoch": time.time(), "payload": payload}
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

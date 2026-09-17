"""CPU-only contract tests for the opt-in GPT-OSS transport mixin."""

from __future__ import annotations

from types import SimpleNamespace
import json

import pytest

import arc3.duck_gptoss_adapter as transport
from arc3.duck_gptoss_adapter import (
    GPTOSSNativeFunctionMixin,
    NATIVE_FUNCTION_CALL_GUIDANCE,
)
from arc3.duck_scene_adapter import SceneObservationMixin
from inference.agent.prompts import MULTIMODAL_CONTEXT_ADDENDUM, TOOL_CALL_FORMAT_GUIDANCE


class _Response:
    status_code = 200
    text = ""

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _DuckBase:
    def __init__(self):
        self.base_user_message_calls = 0
        self._system_prompt = (
            "gameplay safety stays intact\n"
            + MULTIMODAL_CONTEXT_ADDENDUM
            + "\n"
            + TOOL_CALL_FORMAT_GUIDANCE
        )
        self._model = SimpleNamespace(model_id="openai/gpt-oss-20b", base_url="http://test/v1")
        self._max_output_tokens = 777
        self._timeout = 31

    def _headers(self):
        return {"Authorization": "Bearer test"}

    def _build_user_prompt(self, action_num, *, current_frame=None, **kwargs):
        del action_num, current_frame, kwargs
        return "gameplay action limits stay intact\n" + TOOL_CALL_FORMAT_GUIDANCE

    def _build_user_message(self, user_prompt, current_frame):
        self.base_user_message_calls += 1
        del user_prompt, current_frame
        return {"role": "user", "content": [{"type": "text", "text": "base"}, {"type": "image_url"}]}


class _SceneGPTOSSAgent(GPTOSSNativeFunctionMixin, SceneObservationMixin, _DuckBase):
    pass


def _tool_messages(code="print('ok')"):
    return [
        {"role": "system", "content": "scene and gameplay guidance"},
        {"role": "user", "content": "SCENE_V1\ncomplete board"},
        {
            "role": "assistant",
            "content": "I will inspect it.",
            "reasoning": "Need a compact check.",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "python", "arguments": '{"code": "' + code + '"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "content": '{"stdout": "ok"}'},
    ]


def test_scene_is_complete_text_and_qwen_guidance_is_removed():
    agent = _SceneGPTOSSAgent()
    frame = SimpleNamespace(grid=[[1, 2], [3, 4]], level=1)
    prompt = agent._build_user_prompt(0, current_frame=frame)
    message = agent._build_user_message(prompt, frame)

    assert "SCENE_V1" in message["content"]
    assert isinstance(message["content"], str)
    assert agent.base_user_message_calls == 0
    assert "image" not in agent._system_prompt.lower()
    assert TOOL_CALL_FORMAT_GUIDANCE not in agent._system_prompt
    assert TOOL_CALL_FORMAT_GUIDANCE not in message["content"]
    assert NATIVE_FUNCTION_CALL_GUIDANCE in agent._system_prompt
    assert NATIVE_FUNCTION_CALL_GUIDANCE in message["content"]
    assert "gameplay safety stays intact" in agent._system_prompt
    assert "gameplay action limits stay intact" in message["content"]


def test_native_tool_call_roundtrip_preserves_history_reasoning_and_tools(monkeypatch):
    agent = _SceneGPTOSSAgent()
    monkeypatch.setattr(transport._duck_tool_agent, "_LOCAL_ANALYZER_SEED", 314159)
    monkeypatch.setattr(transport._duck_tool_agent, "_request_tool_choice", lambda tools: "required")
    sent = []
    replies = [
        {"choices": [{"message": {"role": "assistant", "reasoning": "inspect", "tool_calls": _tool_messages()[2]["tool_calls"]}, "finish_reason": "tool_calls"}]},
        {"choices": [{"message": {"role": "assistant", "content": "done", "reasoning": "verified"}, "finish_reason": "stop"}]},
    ]

    def post(url, *, headers, json, timeout):
        sent.append((url, headers, json, timeout))
        return _Response(replies.pop(0))

    monkeypatch.setattr("arc3.duck_gptoss_adapter.requests.post", post)
    tools = [{"type": "function", "function": {"name": "python", "parameters": {"type": "object"}}}]
    first = agent._chat_completion(_tool_messages()[:2], tools=tools)
    history = _tool_messages()
    history[2]["reasoning_content"] = "tool rationale"
    history[0]["content"] += "\n" + TOOL_CALL_FORMAT_GUIDANCE
    history[2]["tool_calls"] = first.message["tool_calls"]
    second = agent._chat_completion(history, tools=tools)

    assert first.message["tool_calls"][0]["id"] == "call-1"
    assert history[3] == {"role": "tool", "tool_call_id": "call-1", "content": '{"stdout": "ok"}'}
    assert second.message["reasoning"] == "verified"
    assert sent[1][2]["messages"][1:] == history[1:]
    for _, _, payload, _ in sent:
        assert payload["reasoning_effort"] == "high"
        assert payload["seed"] == 314159
        assert payload["tools"] == tools
        assert payload["tool_choice"] == "auto"
        assert payload["ignore_eos"] is False
        assert "chat_template_kwargs" not in payload
        assert "top_k" not in payload
        assert all(TOOL_CALL_FORMAT_GUIDANCE not in message.get("content", "") for message in payload["messages"])
        assert all(isinstance(message.get("content"), str) or message.get("content") is None for message in payload["messages"])
    assert sent[1][2]["messages"][2]["reasoning_content"] == "tool rationale"


def test_http_500_body_is_bounded_without_headers(monkeypatch):
    agent = _SceneGPTOSSAgent()

    class _Failure:
        status_code = 500
        text = "detail-" + "x" * 5000
        headers = {"Authorization": "secret"}

        def raise_for_status(self):
            raise transport.requests.HTTPError("500 Server Error")

    monkeypatch.setattr(transport.requests, "post", lambda *args, **kwargs: _Failure())
    with pytest.raises(transport.requests.RequestException) as raised:
        agent._chat_completion([{"role": "user", "content": "SCENE_V1"}], tools=None)

    message = str(raised.value)
    assert "detail-" in message
    assert "Authorization" not in message
    assert len(message) < 4200


def test_rejects_multimodal_content_at_payload_boundary(monkeypatch):
    agent = _SceneGPTOSSAgent()
    monkeypatch.setattr("arc3.duck_gptoss_adapter.requests.post", lambda *args, **kwargs: pytest.fail("must not post"))
    with pytest.raises(ValueError, match="text-only"):
        agent._chat_completion(
            [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,x"}}]}],
            tools=None,
        )


def test_http_audit_records_exact_normalized_body_and_response_without_headers(tmp_path, monkeypatch):
    agent = _SceneGPTOSSAgent()
    path = tmp_path / "http" / "game.jsonl"
    agent._gptoss_audit_path = path
    actual = []
    reply = {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}

    def post(url, *, headers, json, timeout):
        # Request evidence must already be durable before the network call.
        actual.append(json)
        assert path.is_file()
        assert __import__("json").loads(path.read_text().splitlines()[0])["payload"] == json
        return _Response(reply)

    monkeypatch.setattr(transport.requests, "post", post)
    agent._chat_completion(_tool_messages(), tools=[])
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [(r["event"], r["sequence"]) for r in rows] == [("request", 1), ("response", 1)]
    assert rows[0]["payload"] == actual[0]
    assert rows[1]["payload"] == reply
    assert "Authorization" not in path.read_text()


def test_omits_seed_when_not_configured(monkeypatch):
    agent = _SceneGPTOSSAgent()
    sent = []
    monkeypatch.setattr(transport._duck_tool_agent, "_LOCAL_ANALYZER_SEED", -1)
    monkeypatch.setattr(
        "arc3.duck_gptoss_adapter.requests.post",
        lambda *args, **kwargs: sent.append(kwargs["json"]) or _Response({"choices": [{"message": {}}]}),
    )
    agent._chat_completion([{"role": "user", "content": "SCENE_V1"}], tools=None)
    assert "seed" not in sent[0]


def test_rejects_xml_tool_markup_instead_of_using_duck_legacy_parser(monkeypatch):
    agent = _SceneGPTOSSAgent()
    monkeypatch.setattr(
        "arc3.duck_gptoss_adapter.requests.post",
        lambda *args, **kwargs: _Response({"choices": [{"message": {"content": "<tool_call><function=python>"}}]}),
    )
    with pytest.raises(Exception, match="expected native tool_calls"):
        agent._chat_completion([{"role": "user", "content": "SCENE_V1"}], tools=None)


def test_accepts_native_tool_call_even_if_reasoning_mentions_xml_markup(monkeypatch):
    agent = _SceneGPTOSSAgent()
    native_call = _tool_messages()[2]["tool_calls"]
    monkeypatch.setattr(
        "arc3.duck_gptoss_adapter.requests.post",
        lambda *args, **kwargs: _Response(
            {"choices": [{"message": {"reasoning": "Do not emit <tool_call> markup.", "tool_calls": native_call}}]}
        ),
    )
    result = agent._chat_completion([{"role": "user", "content": "SCENE_V1"}], tools=None)
    assert result.message["tool_calls"] == native_call

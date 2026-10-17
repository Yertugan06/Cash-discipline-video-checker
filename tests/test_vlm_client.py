"""Unit tests for backend.vlm.client against a mocked vLLM OpenAI-compatible server."""

import json
from pathlib import Path

import httpx
import pytest

from backend.vlm.client import ask_frame, check_ready
from backend.vlm.config import VlmSettings
from backend.vlm.errors import VlmUnavailableError

FIXTURE_IMAGE = (Path(__file__).parent / "fixtures" / "vlm" / "frame.jpg").read_bytes()

VALID_STATE = {
    "cashier_at_desk": True,
    "cashier_in_room": True,
    "people_cashier_side": 1,
    "clients_at_desk": 0,
    "person_at_door": False,
    "collector_present": False,
    "desk_cash": False,
    "desk_bag": False,
    "desk_documents": False,
    "desk_personal_items": False,
    "desk_food_drink": False,
    "phone_in_cashier_hand": False,
    "id_document_visible": False,
    "counting_machine_in_use": False,
    "detector_in_use": False,
    "safe_door": "closed",
    "key_in_safe_lock": "no",
    "laptop_screen": "unlocked",
    "room_door": "closed",
    "cash_in_hands_of": "nobody",
    "cashier_action": "working_on_laptop",
}


def _settings() -> VlmSettings:
    return VlmSettings(model="test-model")


def _schema() -> dict:
    from scripts.gen_form_schema import build_schema

    return build_schema()


def _chat_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def _client_with(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url=_settings().base_url)


def test_valid_answer_is_ok_on_first_try() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return _chat_response(json.dumps(VALID_STATE))

    with _client_with(handler) as client:
        obs = ask_frame(client, _settings(), 4.0, FIXTURE_IMAGE, _schema(), "sys", "q {t}")

    assert len(calls) == 1
    assert obs.ok is True
    assert obs.error is None
    assert obs.state is not None
    assert obs.state.desk_cash is False
    assert obs.t == 4.0


def test_invalid_json_then_valid_is_retried_once_and_ok() -> None:
    responses = iter([_chat_response("not json at all"), _chat_response(json.dumps(VALID_STATE))])
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return next(responses)

    with _client_with(handler) as client:
        obs = ask_frame(client, _settings(), 1.0, FIXTURE_IMAGE, _schema(), "sys", "q {t}")

    assert len(calls) == 2
    assert obs.ok is True
    assert obs.state is not None


def test_invalid_twice_is_counted_as_failed() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return _chat_response("still not json")

    with _client_with(handler) as client:
        obs = ask_frame(client, _settings(), 2.0, FIXTURE_IMAGE, _schema(), "sys", "q {t}")

    assert len(calls) == 2
    assert obs.ok is False
    assert obs.state is None
    assert obs.error is not None


def test_request_puts_text_before_image_and_attaches_schema() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _chat_response(json.dumps(VALID_STATE))

    schema = _schema()
    with _client_with(handler) as client:
        ask_frame(client, _settings(), 7.0, FIXTURE_IMAGE, schema, "sys prompt", "question {t} s")

    body = captured["body"]
    user_content = body["messages"][1]["content"]
    assert user_content[0]["type"] == "text"
    assert "7.0" in user_content[0]["text"]
    assert user_content[-1]["type"] == "image_url"
    assert user_content[-1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert body["response_format"]["json_schema"]["schema"] == schema
    assert body["response_format"]["json_schema"]["strict"] is True


def test_connection_error_raises_vlm_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with _client_with(handler) as client:
        with pytest.raises(VlmUnavailableError):
            ask_frame(client, _settings(), 0.0, FIXTURE_IMAGE, _schema(), "sys", "q {t}")


def test_check_ready_true_on_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "test-model"}]})

    with _client_with(handler) as client:
        assert check_ready(_settings(), client=client) is True


def test_check_ready_false_on_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with _client_with(handler) as client:
        assert check_ready(_settings(), client=client) is False

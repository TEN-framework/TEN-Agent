"""Unit tests for the provider-facing decision layer."""

import asyncio

import httpx2
import pytest
from typesafe_sdk import (
    Choice,
    Noul,
    Score,
    TypeSafeAuthenticationError,
    TypeSafeAPIError,
    TypeSafeRateLimitError,
)

from ten_packages.extension.typesafe_jev_python.decision import (
    DecisionError,
    evaluate,
    parse_request,
)


def request(questions=None):
    return {
        "request_id": "turn-1",
        "state": {"latest_user_text": "Please help."},
        "questions": questions
        or {
            "route": {
                "type": "choice",
                "instructions": "Choose a route",
                "criteria": {"fast": None, "deep": None},
            }
        },
    }


class FakeModel:
    def __init__(self, value):
        self.value = value

    def model_dump(self, mode):
        assert mode == "json"
        return self.value


class FakeResponse:
    model = "jev-1.13.0"
    answers = {
        "route": FakeModel(
            {
                "type": "choice",
                "choice": "fast",
                "confidence": 0.9,
                "probabilities": {"fast": 0.95, "deep": 0.05},
            }
        )
    }
    usage = FakeModel({"input_tokens": 12})


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response or FakeResponse()
        self.error = error
        self.calls = []

    async def system_one(self, state, questions, **kwargs):
        self.calls.append((state, questions, kwargs))
        if self.error:
            raise self.error
        return self.response


def test_all_question_types_are_constructed():
    payload = request(
        {
            "route": {
                "type": "choice",
                "instructions": "Route?",
                "criteria": {"fast": None, "deep": None},
            },
            "urgent": {"type": "noul", "instructions": "Urgent?"},
            "difficulty": {
                "type": "score",
                "instructions": "Difficulty?",
                "criteria": ["easy", "medium", "hard"],
            },
        }
    )
    _, _, questions = parse_request(payload)
    assert isinstance(questions["route"], Choice)
    assert isinstance(questions["urgent"], Noul)
    assert isinstance(questions["difficulty"], Score)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        request({"route": {"type": "other", "instructions": "Route?"}}),
        request(
            {
                "route": {
                    "type": "choice",
                    "instructions": "Route?",
                    "criteria": {"only_one": None},
                }
            }
        ),
        request(
            {
                "difficulty": {
                    "type": "score",
                    "instructions": "Difficulty?",
                    "criteria": ["only_one"],
                }
            }
        ),
        {**request(), "state": ""},
    ],
)
def test_invalid_payload_is_rejected(payload):
    with pytest.raises(DecisionError, match="invalid_request"):
        parse_request(payload)


@pytest.mark.asyncio
async def test_success_returns_structured_answer_and_disables_retries():
    client = FakeClient()
    result = await evaluate(client, request(), 1000)
    assert result["request_id"] == "turn-1"
    assert result["answers"]["route"]["confidence"] == 0.9
    assert result["model"] == "jev-1.13.0"
    assert result["usage"] == {"input_tokens": 12}
    assert result["latency_ms"] >= 0
    assert client.calls[0][2]["retry"].max_retries == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error,code",
    [
        (
            TypeSafeAuthenticationError(401, {}, httpx2.Headers()),
            "authentication_failed",
        ),
        (TypeSafeRateLimitError(429, {}, httpx2.Headers()), "rate_limited"),
        (TypeSafeAPIError(529, {}, httpx2.Headers()), "provider_error"),
        (asyncio.TimeoutError(), "timeout"),
    ],
)
async def test_provider_errors_have_stable_codes(error, code):
    with pytest.raises(DecisionError) as caught:
        await evaluate(FakeClient(error=error), request(), 1000)
    assert caught.value.code == code


@pytest.mark.asyncio
async def test_hard_timeout_and_missing_client():
    class SlowClient:
        async def system_one(self, *_args, **_kwargs):
            await asyncio.sleep(0.1)

    with pytest.raises(DecisionError, match="timeout"):
        await evaluate(SlowClient(), request(), 1)
    with pytest.raises(DecisionError, match="not_configured"):
        await evaluate(None, request(), 1000)

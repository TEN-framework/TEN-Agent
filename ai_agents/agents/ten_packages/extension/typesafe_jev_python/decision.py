"""Provider-facing evaluation logic, independent of the TEN runtime."""

import asyncio
import json
import time
from typing import Any

from typesafe_sdk import (
    Choice,
    Noul,
    RetryPolicy,
    Score,
    TypeSafeAPIError,
    TypeSafeAPITimeoutError,
    TypeSafeAuthenticationError,
    TypeSafeError,
    TypeSafeRateLimitError,
)


class DecisionError(Exception):
    """A safe, stable error to return through the TEN command result."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def parse_request(payload: Any) -> tuple[str, Any, dict[str, Any]]:
    """Validate a TEN payload and construct typed SDK questions."""
    if not isinstance(payload, dict):
        raise DecisionError("invalid_request")

    request_id = payload.get("request_id")
    state = payload.get("state")
    raw_questions = payload.get("questions")
    if not isinstance(request_id, str) or not request_id.strip():
        raise DecisionError("invalid_request")
    if not isinstance(state, (str, dict, list)) or not state:
        raise DecisionError("invalid_request")
    if not isinstance(raw_questions, dict) or not raw_questions:
        raise DecisionError("invalid_request")
    try:
        json.dumps(state, allow_nan=False)
        json.dumps(raw_questions, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise DecisionError("invalid_request") from error

    questions = {}
    for name, question in raw_questions.items():
        if not isinstance(name, str) or not name.strip():
            raise DecisionError("invalid_request")
        if not isinstance(question, dict) or not question.get("instructions"):
            raise DecisionError("invalid_request")
        kind = question.get("type")
        criteria = question.get("criteria")
        try:
            if kind == "choice":
                if (
                    not isinstance(criteria, dict)
                    or not 2 <= len(criteria) <= 255
                ):
                    raise DecisionError("invalid_request")
                questions[name] = Choice(
                    instructions=question["instructions"], criteria=criteria
                )
            elif kind == "score":
                if (
                    not isinstance(criteria, list)
                    or not 2 <= len(criteria) <= 10
                ):
                    raise DecisionError("invalid_request")
                questions[name] = Score(
                    instructions=question["instructions"], criteria=criteria
                )
            elif kind == "noul":
                if criteria is not None and not isinstance(criteria, dict):
                    raise DecisionError("invalid_request")
                questions[name] = Noul(
                    instructions=question["instructions"], criteria=criteria
                )
            else:
                raise DecisionError("invalid_request")
        except (TypeError, ValueError) as error:
            raise DecisionError("invalid_request") from error
    return request_id, state, questions


async def evaluate(client: Any, payload: Any, timeout_ms: int) -> dict:
    """Evaluate a request once, with a hard end-to-end deadline."""
    request_id, state, questions = parse_request(payload)
    if client is None:
        raise DecisionError("not_configured")

    timeout_seconds = timeout_ms / 1000
    started = time.monotonic()
    try:
        response = await asyncio.wait_for(
            client.system_one(
                state,
                questions,
                retry=RetryPolicy(max_retries=0, timeout=timeout_seconds),
                timeout=timeout_seconds,
            ),
            timeout=timeout_seconds,
        )
    except TypeSafeAuthenticationError as error:
        raise DecisionError("authentication_failed") from error
    except TypeSafeRateLimitError as error:
        raise DecisionError("rate_limited") from error
    except (TypeSafeAPITimeoutError, asyncio.TimeoutError) as error:
        raise DecisionError("timeout") from error
    except TypeSafeAPIError as error:
        raise DecisionError("provider_error") from error
    except TypeSafeError as error:
        raise DecisionError("provider_error") from error

    return {
        "request_id": request_id,
        "model": response.model,
        "answers": {
            name: answer.model_dump(mode="json")
            for name, answer in response.answers.items()
        },
        "usage": response.usage.model_dump(mode="json"),
        "latency_ms": round((time.monotonic() - started) * 1000),
    }

"""Provider-independent selection of a target LLM extension."""

import asyncio
import json
import math
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .config import ModelRoutingConfig


@dataclass(frozen=True)
class RoutingDecision:
    destination: str
    status: str
    latency_ms: int
    choice: str | None = None
    confidence: float | None = None


async def resolve_destination(
    config: ModelRoutingConfig,
    text: str,
    request_id: str,
    send_decision: Callable[[dict[str, Any]], Awaitable[tuple[Any, Any]]],
) -> RoutingDecision:
    """Select a target and retain safe metadata for route observability."""
    started = time.monotonic()

    def outcome(
        destination: str,
        status: str,
        choice: str | None = None,
        confidence: float | None = None,
    ) -> RoutingDecision:
        return RoutingDecision(
            destination=destination,
            status=status,
            latency_ms=round((time.monotonic() - started) * 1000),
            choice=choice,
            confidence=confidence,
        )

    if not config.enabled:
        return outcome("llm", "disabled")

    payload = {
        "request_id": request_id,
        "state": {"latest_user_text": text},
        "questions": {"route": config.question},
    }
    try:
        result, error = await asyncio.wait_for(
            send_decision(payload), timeout=config.timeout_ms / 1000
        )
        if error or not result or result.get_status_code() != 0:
            return outcome(config.fast_dest, "provider_error")
        response_json, error = result.get_property_to_json(None)
        if error:
            return outcome(config.fast_dest, "invalid_response")
        decision = json.loads(response_json)
        if not isinstance(decision, dict):
            return outcome(config.fast_dest, "invalid_response")
        if decision.get("request_id") != request_id:
            return outcome(config.fast_dest, "stale_decision")
        answers = decision.get("answers")
        route = answers.get("route") if isinstance(answers, dict) else None
        if not isinstance(route, dict) or route.get("type") != "choice":
            return outcome(config.fast_dest, "invalid_response")
        choice = route.get("choice")
        if choice not in ("fast", "deep"):
            return outcome(config.fast_dest, "invalid_response")
        raw_confidence = route.get("confidence")
        confidence = (
            float(raw_confidence)
            if isinstance(raw_confidence, (int, float))
            and not isinstance(raw_confidence, bool)
            and math.isfinite(raw_confidence)
            and 0 <= raw_confidence <= 1
            else None
        )
        destination = config.select_dest(decision)
        if choice == "fast" and destination == config.fast_dest:
            return outcome(destination, "selected_fast", choice, confidence)
        if choice == "deep":
            return outcome(destination, "selected_deep", choice, confidence)
        return outcome(destination, "below_threshold", choice, confidence)
    except asyncio.TimeoutError:
        return outcome(config.fast_dest, "timeout")
    except Exception:
        # Cancellation is a BaseException and still propagates to the caller.
        return outcome(config.fast_dest, "provider_error")

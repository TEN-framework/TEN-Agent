import json

import httpx
import pytest
from client import SpekoLLMClient, SpekoRouterError


def sse(*events):
    return "".join(
        f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events
    )


@pytest.mark.asyncio
async def test_stream_maps_sse_and_sends_idempotency_key():
    captured = {}

    async def handler(request):
        captured["request"] = request
        return httpx.Response(
            200,
            text=sse(
                ("response.created", {"response_id": "resp_req_1"}),
                (
                    "response.text.delta",
                    {"output_index": 0, "delta": "hello"},
                ),
                (
                    "response.completed",
                    {
                        "stop_reason": "stop",
                        "usage": {"input_tokens": 2, "output_tokens": 1},
                    },
                ),
            ),
            headers={
                "content-type": "text/event-stream",
                "Speko-Provider": "openai",
                "Speko-Model": "gpt-5-mini",
                "Speko-Region": "us-east",
                "Speko-Attempt-ID": "att_1",
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SpekoLLMClient(
        api_key="test-key",
        base_url="https://router.speko.dev",
        timeout_sec=1,
        http_client=http_client,
    )
    events = [
        event
        async for event in client.stream(
            {"input": [], "max_output_tokens": 32, "stream": True},
            idempotency_key="idem-1",
        )
    ]

    assert [event.name for event in events] == [
        "response.created",
        "response.text.delta",
        "response.completed",
    ]
    request = captured["request"]
    assert request.headers["authorization"] == "Bearer test-key"
    assert request.headers["idempotency-key"] == "idem-1"
    assert json.loads(request.content)["max_output_tokens"] == 32
    assert client.route == {
        "provider": "openai",
        "model": "gpt-5-mini",
        "region": "us-east",
        "attempt_id": "att_1",
    }
    await http_client.aclose()


@pytest.mark.asyncio
async def test_http_error_is_normalized():
    async def handler(request):
        del request
        return httpx.Response(
            429,
            json={
                "error": {
                    "code": "rate_limited",
                    "message": "slow down",
                    "hint": "retry",
                    "retryable": True,
                }
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SpekoLLMClient(
        api_key="test-key",
        base_url="https://router.speko.dev",
        timeout_sec=1,
        http_client=http_client,
    )
    with pytest.raises(SpekoRouterError) as caught:
        _ = [
            event
            async for event in client.stream(
                {"input": [], "max_output_tokens": 32, "stream": True},
                idempotency_key="idem-1",
            )
        ]

    assert caught.value.code == "rate_limited"
    assert caught.value.retryable is True
    assert caught.value.status_code == 429
    await http_client.aclose()


@pytest.mark.asyncio
async def test_truncated_stream_is_not_reported_as_success():
    async def handler(request):
        del request
        return httpx.Response(
            200,
            text=sse(("response.created", {"response_id": "resp_req_1"})),
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SpekoLLMClient(
        api_key="test-key",
        base_url="https://router.speko.dev",
        timeout_sec=1,
        http_client=http_client,
    )
    with pytest.raises(SpekoRouterError) as caught:
        _ = [
            event
            async for event in client.stream(
                {"input": [], "max_output_tokens": 32, "stream": True},
                idempotency_key="idem-1",
            )
        ]

    assert caught.value.code == "relay_error"
    assert caught.value.retryable is True
    await http_client.aclose()

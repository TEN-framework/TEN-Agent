"""Use the real Hume SDK over a delayed external HTTP transport."""

import asyncio
import base64
import json
import time
from unittest.mock import patch

import httpx
import pytest

from .test_ttfb_boundary import TimingTester


@pytest.mark.api
def test_ttfb_excludes_sdk_http_connection():
    times = {}

    class Audio(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.sleep(0.02)
            times["received"] = time.monotonic_ns()
            yield (
                json.dumps(
                    {
                        "audio": base64.b64encode(b"\x01\x00" * 1600).decode(),
                        "chunk_index": 0,
                        "generation_id": "mock-generation",
                        "is_last_chunk": True,
                        "snippet_id": "mock-snippet",
                        "text": "Hello.",
                    }
                )
                + "\n"
            ).encode()

    class Provider(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            await asyncio.sleep(0.12)
            times["sent"] = time.monotonic_ns()
            trace = request.extensions.get("trace")
            if trace is not None:
                await trace("http11.send_request_body.started", {})
            return httpx.Response(
                200,
                headers={"content-type": "application/x-ndjson"},
                stream=Audio(),
            )

    original = httpx.AsyncClient

    class Client(original):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = Provider()
            super().__init__(*args, **kwargs)

    with patch("httpx.AsyncClient", Client):
        tester = TimingTester()
        try:
            tester.set_test_mode_single(
                "humeai_tts_python",
                json.dumps(
                    {
                        "params": {
                            "key": "mock",
                            "base_url": "https://mock.example",
                        },
                    }
                ),
            )
            error = tester.run()
            assert error is None, error.error_message()
            expected = (times["received"] - times["sent"]) / 1_000_000
            assert len(tester.reported) == 1
            assert abs(tester.reported[0] - expected) <= 5, (
                tester.reported,
                expected,
            )
        finally:
            if tester.timer:
                tester.timer.cancel()

"""A transport reference must catch delays hidden by the test-side upper bound."""

import pytest

import asyncio
import json

import httpx

from .test_metrics import SequentialTTFBTester
from .ttfb_reference import install_ttfb_reference


def test_ttfb_matches_provider_with_connection_and_tail_delays(monkeypatch):
    class AudioStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.sleep(0.02)
            yield b"\x01\x00" * 1600
            await asyncio.sleep(0.03)
            yield b"\x02\x00" * 1600

    class Provider(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            await asyncio.sleep(0.1)
            trace = request.extensions.get("trace")
            if trace is not None:
                await trace("http11.send_request_body.started", {})
            return httpx.Response(200, stream=AudioStream())

    original = httpx.AsyncClient

    class Client(original):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = Provider()
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    config = {"params": {"api_key": "mock"}}
    with install_ttfb_reference(
        "openai_tts2_python", config, monkeypatch
    ) as reference:
        assert reference is not None
        tester = SequentialTTFBTester(reference)
        tester.set_test_mode_single("openai_tts2_python", json.dumps(config))
        error = tester.run()
        assert error is None, error.error_message()


pytestmark = pytest.mark.api

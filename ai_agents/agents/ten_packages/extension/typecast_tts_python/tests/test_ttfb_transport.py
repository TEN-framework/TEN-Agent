"""Real Typecast SDK with delayed DNS and a local streaming HTTP provider."""

import asyncio
import io
import json
import socket
import threading
import time
from unittest.mock import patch
import wave

import aiohttp
from aiohttp import web
import pytest

from .test_ttfb_boundary import TimingTester


@pytest.mark.api
def test_ttfb_excludes_sdk_dns_wait():
    ready = threading.Event()
    loop = asyncio.new_event_loop()
    port = []
    times = {}
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(32000)
        audio.writeframes(b"\x01\x00" * 1600)

    async def speech(request):
        await request.read()
        times["sent"] = time.monotonic_ns()
        response = web.StreamResponse(headers={"content-type": "audio/wav"})
        await response.prepare(request)
        await asyncio.sleep(0.02)
        times["received"] = time.monotonic_ns()
        await response.write(output.getvalue())
        await response.write_eof()
        return response

    runner = None

    def serve():
        nonlocal runner
        asyncio.set_event_loop(loop)

        async def start():
            nonlocal runner
            app = web.Application()
            app.router.add_post("/v1/text-to-speech/stream", speech)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "127.0.0.1", 0)
            await site.start()
            # Bound listening addresses are public AppRunner state.
            port.append(runner.addresses[0][1])
            ready.set()

        loop.run_until_complete(start())
        loop.run_forever()
        loop.run_until_complete(runner.cleanup())
        loop.close()

    class Resolver(aiohttp.abc.AbstractResolver):
        async def resolve(self, host, port=0, family=socket.AF_INET):
            await asyncio.sleep(0.12)
            return [
                {
                    "hostname": host,
                    "host": "127.0.0.1",
                    "port": port,
                    "family": socket.AF_INET,
                    "proto": 0,
                    "flags": 0,
                }
            ]

        async def close(self):
            pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    assert ready.wait(0.5)
    original = aiohttp.ClientSession

    def session(*args, **kwargs):
        kwargs["connector"] = aiohttp.TCPConnector(resolver=Resolver())
        return original(*args, **kwargs)

    with patch("aiohttp.ClientSession", session):
        tester = TimingTester()
        try:
            tester.set_test_mode_single(
                "typecast_tts_python",
                json.dumps(
                    {
                        "url": f"http://mock.example:{port[0]}",
                        "params": {
                            "api_key": "mock",
                            "voice_id": "tc_62a31c3b13e7a00007f0b7de",
                        },
                    }
                ),
            )
            error = tester.run()
            assert error is None, error.error_message()
            expected = (times["received"] - times["sent"]) / 1_000_000
            assert len(tester.reported) == 1
            assert abs(tester.reported[0] - expected) <= 10, (
                tester.reported,
                expected,
            )
        finally:
            if tester.timer:
                tester.timer.cancel()
            loop.call_soon_threadsafe(loop.stop)
            thread.join(0.5)

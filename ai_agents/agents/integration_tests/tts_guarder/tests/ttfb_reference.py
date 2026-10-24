"""Independent first-text/first-audio observations at public provider boundaries."""

import base64
from contextlib import contextmanager
from importlib import import_module
import json
from threading import RLock
import time

from .timing_hooks.transport import ObservedWebSockets


class TTFBReference:
    def __init__(self):
        self.lock = RLock()
        self.current_request_id = None
        self.sent = {}
        self.received = {}

    def begin_request(self, request_id):
        with self.lock:
            self.current_request_id = request_id

    def text_sent(self):
        timestamp = time.monotonic_ns()
        with self.lock:
            if self.current_request_id is not None:
                self.sent.setdefault(self.current_request_id, timestamp)

    def audio_received(self):
        timestamp = time.monotonic_ns()
        with self.lock:
            request_id = self.current_request_id
            if request_id in self.sent:
                self.received.setdefault(request_id, timestamp)

    def elapsed_ms(self, request_id):
        with self.lock:
            if request_id not in self.sent or request_id not in self.received:
                return None
            return (
                self.received[request_id] - self.sent[request_id]
            ) / 1_000_000


HTTP_MODULES = {
    "openai_tts2_python": "openai_tts",
    "mistral_tts_python": "mistral_tts",
    "smallest_tts_python": "smallest_tts",
    "ezai_tw_tts_python": "ezai_tts",
    "sarvam_http_tts": "sarvam_tts",
    "generic_tts_http_python": "generic_tts",
    "gemini_tts_python": "gemini_tts",
}
WS_MODULES = {
    "bytedance_tts": "bytedance_tts",
    "bytedance_tts_duplex": "bytedance_tts",
    "minimax_tts_websocket": "minimax_tts",
    "minimax_tts_websocket_duplex": "minimax_tts",
    "soul_tts_python": "soul_tts",
    "stepfun_tts_python": "stepfun_tts",
    "murf_tts_python": "murf_tts",
}


def _contains_audio(value):
    match value:
        case dict():
            for key, item in value.items():
                if (
                    key in {"audio", "audio_data"}
                    and isinstance(item, str)
                    and item
                ):
                    return True
                if key == "audios" and isinstance(item, list) and any(item):
                    return True
                if key in {"inlineData", "inline_data"} and item.get("data"):
                    return True
                if _contains_audio(item):
                    return True
        case list():
            return any(_contains_audio(item) for item in value)
    return False


def _install_http(module, patch, reference):
    import httpx

    class Stream(httpx.AsyncByteStream):
        def __init__(self, stream, is_sse, is_json):
            self.stream = stream
            self.is_sse = is_sse
            self.is_json = is_json
            self.pending = b""

        async def __aiter__(self):
            async for chunk in self.stream:
                if chunk:
                    if not self.is_sse and not self.is_json:
                        reference.audio_received()
                    else:
                        self.pending += chunk
                        # Parse complete protocol events; an empty audio field
                        # or a status event is not first audio.
                        documents = []
                        if self.is_sse:
                            while b"\n\n" in self.pending:
                                event, self.pending = self.pending.split(
                                    b"\n\n", 1
                                )
                                body = b"\n".join(
                                    line[5:].lstrip()
                                    for line in event.splitlines()
                                    if line.startswith(b"data:")
                                )
                                if body and body != b"[DONE]":
                                    documents.append(body)
                        else:
                            documents.append(self.pending)
                        for document in documents:
                            try:
                                value = json.loads(document)
                            except (ValueError, UnicodeError):
                                continue
                            if _contains_audio(value):
                                reference.audio_received()
                yield chunk

        async def aclose(self):
            await self.stream.aclose()

    original = httpx.AsyncClient

    class Client(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            async def request_hook(request):
                previous = request.extensions.get("trace")

                async def trace(event, info):
                    if event in (
                        "http11.send_request_body.started",
                        "http2.send_request_body.started",
                    ):
                        reference.text_sent()
                    if previous is not None:
                        await previous(event, info)

                request.extensions["trace"] = trace

            async def response_hook(response):
                response.stream = Stream(
                    response.stream,
                    "text/event-stream"
                    in response.headers.get("content-type", ""),
                    "application/json"
                    in response.headers.get("content-type", ""),
                )

            self.event_hooks["request"].append(request_hook)
            self.event_hooks["response"].append(response_hook)

    if "AsyncClient" in vars(module):
        patch.setattr(module, "AsyncClient", Client)
    else:

        class Library:
            AsyncClient = Client

            def __getattr__(self, name):
                return getattr(httpx, name)

        patch.setattr(module, "httpx", Library())


class WebSocketReference:
    def __init__(self, vendor, reference):
        self.vendor = vendor
        self.reference = reference

    def observe_send(self, raw):
        if self.vendor == "bytedance_tts":
            import gzip

            if isinstance(raw, bytes) and raw[1] >> 4 == 1:
                message = json.loads(gzip.decompress(raw[8:]))
                if message.get("request", {}).get("text"):
                    self.reference.text_sent()
            return
        if self.vendor == "bytedance_tts_duplex":
            if isinstance(raw, bytes) and len(raw) > 8:
                event = int.from_bytes(raw[4:8], "big")
                if event == 200:
                    self.reference.text_sent()
            return
        if isinstance(raw, str):
            message = json.loads(raw)
            if message.get("text") or message.get("data", {}).get("text"):
                self.reference.text_sent()

    def observe_receive(self, raw):
        if self.vendor == "bytedance_tts":
            if isinstance(raw, bytes) and len(raw) > 12 and raw[1] >> 4 == 11:
                if int.from_bytes(raw[8:12], "big") > 0:
                    self.reference.audio_received()
            return
        if self.vendor == "bytedance_tts_duplex":
            if (
                isinstance(raw, bytes)
                and len(raw) > 8
                and int.from_bytes(raw[4:8], "big") == 352
            ):
                self.reference.audio_received()
            return
        if isinstance(raw, str):
            message = json.loads(raw)
            data = message.get("data") or {}
            if (
                message.get("audio")
                or data.get("audio")
                or data.get("audio_data")
            ):
                self.reference.audio_received()


def _install_sdk(extension_name, patch, reference):
    """Use public SDK calls/callbacks where raw HTTP/WebSocket is hidden."""
    if extension_name == "google_tts_python":
        module = import_module("google.cloud.texttospeech")
        original = module.TextToSpeechClient

        class Client(original):
            def streaming_synthesize(self, requests, *args, **kwargs):
                def text_requests():
                    for request in requests:
                        if request.input.text:
                            reference.text_sent()
                        yield request

                for response in super().streaming_synthesize(
                    text_requests(), *args, **kwargs
                ):
                    if response.audio_content:
                        reference.audio_received()
                    yield response

        patch.setattr(module, "TextToSpeechClient", Client)
        return True
    if extension_name == "typecast_tts_python":
        module = import_module(
            "ten_packages.extension.typecast_tts_python.typecast_tts"
        )
        original = module.AsyncTypecast

        class Client(original):
            async def text_to_speech_stream(self, *args, **kwargs):
                reference.text_sent()
                async for chunk in super().text_to_speech_stream(
                    *args, **kwargs
                ):
                    if chunk:
                        reference.audio_received()
                    yield chunk

        patch.setattr(module, "AsyncTypecast", Client)
        return True
    if extension_name == "humeai_tts_python":
        module = import_module(
            "ten_packages.extension.humeai_tts_python.humeTTS"
        )
        original = module.AsyncHumeClient

        class TTS:
            def __init__(self, service):
                self.service = service

            def __getattr__(self, name):
                return getattr(self.service, name)

            async def synthesize_json_streaming(self, *args, **kwargs):
                reference.text_sent()
                async for snippet in self.service.synthesize_json_streaming(
                    *args, **kwargs
                ):
                    if snippet.audio:
                        reference.audio_received()
                    yield snippet

        class Client:
            def __init__(self, *args, **kwargs):
                self.client = original(*args, **kwargs)
                self.tts = TTS(self.client.tts)

            def __getattr__(self, name):
                return getattr(self.client, name)

        patch.setattr(module, "AsyncHumeClient", Client)
        return True
    return False


@contextmanager
def install_ttfb_reference(extension_name, config, monkeypatch):
    """Unsupported transports remain explicitly without a boundary reference."""
    filename = HTTP_MODULES.get(extension_name) or WS_MODULES.get(
        extension_name
    )
    reference = TTFBReference()
    if filename is None:
        with monkeypatch.context() as scoped:
            if _install_sdk(extension_name, scoped, reference):
                yield reference
            else:
                yield None
        return
    module = import_module(
        f"ten_packages.extension.{extension_name}.{filename}"
    )
    with monkeypatch.context() as scoped:
        if extension_name in HTTP_MODULES:
            _install_http(module, scoped, reference)
        else:
            url = (
                config.get("url")
                or config.get("api_url")
                or config.get("base_url")
            )
            if not url:
                params = config.get("params") or {}
                url = (
                    params.get("url")
                    or params.get("api_url")
                    or params.get("base_url")
                )
            if not url:
                yield None
                return
            observer = WebSocketReference(extension_name, reference)
            scoped.setattr(
                module,
                "websockets",
                ObservedWebSockets(module.websockets, url, observer),
            )
        yield reference

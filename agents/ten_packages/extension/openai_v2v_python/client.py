import asyncio
import base64
import json
import os
from typing import Any, AsyncGenerator

import uuid
import aiohttp
from . import messages

from .log import logger

def smart_str(s: str, max_field_len: int = 128) -> str:
    """parse string as json, truncate data field to 128 characters, reserialize"""
    try:
        data = json.loads(s)
        if "delta" in data:
            key = "delta"
        elif "audio" in data:
            key = "audio"
        else:
            return s

        if len(data[key]) > max_field_len:
            data[key] = data[key][:max_field_len] + "..."
        return json.dumps(data)
    except json.JSONDecodeError:
        return s


def generate_client_event_id() -> str:
    return str(uuid.uuid4())

class RealtimeApiConfig:
    def __init__(
            self,
            base_uri: str = "wss://api.openai.com",
            api_key: str | None = None,
            path: str = "/v1/realtime",
            verbose: bool = False,
            model: str="gpt-4o-realtime-preview-2024-10-01",
            language: str = "en-US",
            system_message: str="You are a helpful assistant, you are professional but lively and friendly. User's input will mainly be {language}, and your response must be {language}.",
            temperature: float =0.5,
            max_tokens: int =1024,
            voice: messages.Voices = messages.Voices.Alloy,
            server_vad:bool=True,
        ):
        self.base_uri = base_uri
        self.api_key = api_key
        self.path = path
        self.verbose = verbose
        self.model = model
        self.language = language
        self.system_message = system_message
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.voice = voice
        self.server_vad = server_vad
    
    def build_ctx(self) -> dict:
        return {
            "language": self.language
        }

class RealtimeApiClient:
    def __init__(
        self,
        base_uri: str,
        api_key: str | None = None,
        path: str = "/v1/realtime",
        model: str = "gpt-4o-realtime-preview-2024-10-01",
        verbose: bool = False,
        session: aiohttp.ClientSession | None = None,
    ):
        is_local = (
            base_uri.startswith("localhost")
            or base_uri.startswith("127.0.0.1")
            or base_uri.startswith("0.0.0.0")
        )
        has_scheme = base_uri.startswith("ws://") or base_uri.startswith("wss://")
        self.url = f"{base_uri}{path}"
        if model:
            self.url += f"?model={model}"
        if verbose:
            logger.info(f"URL: {self.url} {is_local=} {has_scheme=}")

        if not has_scheme:
            if is_local:
                self.url = f"ws://{self.url}"
            else:
                self.url = f"wss://{self.url}"

        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.websocket: aiohttp.ClientWebSocketResponse | None = None
        self.verbose = verbose
        self.session = session or aiohttp.ClientSession()

    async def __aenter__(self) -> "RealtimeApiClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        await self.shutdown()
        return False

    async def connect(self):
        auth = aiohttp.BasicAuth("", self.api_key) if self.api_key else None

        headers = {"OpenAI-Beta": "realtime=v1"}
        if "PROD_COMPLETIONS_API_KEY" in os.environ:
            headers["X-Prod-Completions-Api-Key"] = os.environ["PROD_COMPLETIONS_API_KEY"]
        elif "OPENAI_API_KEY" in os.environ:
            headers["X-Prod-Completions-Api-Key"] = os.environ["OPENAI_API_KEY"]
        if "PROD_COMPLETIONS_ORG_ID" in os.environ:
            headers["X-Prod-Completions-Org-Id"] = os.environ["PROD_COMPLETIONS_ORG_ID"]
        if headers:
            logger.debug("Using X-Prod-Completions-* headers for api credentials")

        self.websocket = await self.session.ws_connect(
            url=self.url,
            auth=auth,
            headers=headers,
        )

    async def send_audio_data(self, audio_data: bytes):
        """audio_data is assumed to be pcm16 24kHz mono little-endian"""
        base64_audio_data = base64.b64encode(audio_data).decode("utf-8")
        message = messages.InputAudioBufferAppend(audio=base64_audio_data)
        await self.send_message(message)

    async def send_message(self, message: messages.ClientToServerMessage):
        assert self.websocket is not None
        if message.event_id is None:
            message.event_id = generate_client_event_id()
        message_str = message.model_dump_json()
        if self.verbose:
            logger.info(f"-> {smart_str(message_str)}")
        await self.websocket.send_str(message_str)

    async def listen(self) -> AsyncGenerator[messages.RealtimeMessage, None]:
        assert self.websocket is not None
        if self.verbose:
            logger.info("Listening for realtimeapi messages")
        try:
            async for msg in self.websocket:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if self.verbose:
                        logger.info(f"<- {smart_str(msg.data)}")
                    yield self.handle_server_message(msg.data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error("Error during receive: %s", self.websocket.exception())
                    break
        except asyncio.CancelledError:
            logger.info("Receive messages task cancelled")

    def handle_server_message(self, message: str) -> messages.ServerToClientMessage:
        try:
            return messages.parse_server_message(message)
        except Exception as e:
            logger.error("Error handling message: " + str(e))
            #raise e

    async def shutdown(self):
        # Close the websocket connection if it exists
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from abc import ABC, abstractmethod
import asyncio
import json
import websockets
from websockets.protocol import State
from urllib.parse import urlparse, quote
from email.utils import formatdate

import requests as http_requests
from oci.signer import Signer

from ten_ai_base.timeline import AudioTimeline
from ten_ai_base.const import LOG_CATEGORY_TRANSCRIPTS, LOG_CATEGORY_VENDOR
from ten_runtime import AsyncTenEnv

from .const import TIMEOUT_CODE


class OracleASRRecognitionCallback(ABC):
    """WebSocket Speech Recognition Callback Interface"""

    @abstractmethod
    async def on_open(self):
        pass

    @abstractmethod
    async def on_result(self, message_data):
        pass

    @abstractmethod
    async def on_error(self, error_msg, error_code=None):
        pass

    @abstractmethod
    async def on_close(self):
        pass


class OracleASRRecognition:
    """Async WebSocket client for Oracle Cloud Speech Realtime API"""

    def __init__(
        self,
        ten_env: AsyncTenEnv,
        audio_timeline: AudioTimeline,
        config: dict,
        callback: OracleASRRecognitionCallback,
    ):
        self.ten_env = ten_env
        self.audio_timeline = audio_timeline
        self.config = config or {}
        self.callback = callback

        self.websocket = None
        self.is_started = False
        self._message_task = None
        self._closing = False

        # OCI credentials
        self._tenancy = self.config.get("tenancy", "")
        self._user = self.config.get("user", "")
        self._fingerprint = self.config.get("fingerprint", "")
        self._key_file = self.config.get("key_file", "")
        self._compartment_id = self.config.get("compartment_id", "")
        self._region = self.config.get("region", "us-phoenix-1")

        # Audio parameters
        self._sample_rate = int(self.config.get("sample_rate", 16000))
        self._language = self.config.get("language", "en-US")

    def _build_signer(self) -> Signer:
        return Signer(
            tenancy=self._tenancy,
            user=self._user,
            fingerprint=self._fingerprint,
            private_key_file_location=self._key_file,
        )

    def _build_url(self) -> str:
        base = f"wss://realtime.aiservice.{self._region}.oci.oraclecloud.com"
        path = "/ws/transcribe/stream?"

        params = []
        params.append(f"encoding=audio/raw;rate={self._sample_rate}")
        params.append(f"languageCode={quote(self._language)}")

        final_silence = self.config.get("final_silence_threshold_in_ms", 2000)
        params.append(f"finalSilenceThresholdInMs={final_silence}")

        partial_silence = self.config.get("partial_silence_threshold_in_ms", 0)
        params.append(f"partialSilenceThresholdInMs={partial_silence}")

        model_domain = self.config.get("model_domain", "GENERIC")
        params.append(f"modelDomain={model_domain}")

        stabilize = self.config.get("stabilize_partial_results", "NONE")
        params.append(f"stabilizePartialResults={stabilize}")

        params.append("isAckEnabled=false")
        params.append("shouldIgnoreInvalidCustomizations=false")

        punctuation = self.config.get("punctuation", "NONE")
        if punctuation and punctuation != "NONE":
            params.append(f"punctuation={punctuation}")

        customizations = self.config.get("customizations")
        if customizations:
            params.append(f"customizations={quote(json.dumps(customizations))}")

        return base + path + "&".join(params)

    async def _send_credentials(self):
        """Send OCI authentication message after WebSocket connects."""
        url = self._build_url()
        parsed = urlparse(url)

        signer = self._build_signer()

        headers = {
            "date": formatdate(usegmt=True),
            "host": parsed.hostname,
        }

        sign_url = url.replace("wss://", "https://", 1)
        prepared = http_requests.Request(
            "GET", sign_url, headers=headers
        ).prepare()
        signer(prepared)
        headers = dict(prepared.headers)
        headers["uri"] = url

        auth_message = {
            "authenticationType": "CREDENTIALS",
            "headers": headers,
            "compartmentId": self._compartment_id,
        }

        await self.websocket.send(json.dumps(auth_message))
        self.ten_env.log_info(
            "OCI auth credentials sent",
            category=LOG_CATEGORY_VENDOR,
        )

    async def _handle_message(self, message):
        try:
            data = json.loads(message)

            self.ten_env.log_debug(
                f"vendor_result: {message}",
                category=LOG_CATEGORY_TRANSCRIPTS,
            )

            event = data.get("event", "")

            if event == "RESULT":
                await self.callback.on_result(data)
            elif event == "CONNECT":
                self.ten_env.log_info(
                    "OCI CONNECT event received",
                    category=LOG_CATEGORY_VENDOR,
                )
            elif event == "ACKAUDIO":
                pass
            elif event == "ERROR":
                error_msg = data.get("message", "Unknown OCI error")
                error_code = data.get("code")
                await self.callback.on_error(error_msg, error_code)

        except Exception as e:
            error_msg = f"Error processing message: {e}"
            self.ten_env.log_error(error_msg)
            await self.callback.on_error(error_msg)

    async def _message_handler(self):
        try:
            if self.websocket is None:
                return
            ws = self.websocket
            async for message in ws:
                await self._handle_message(message)
        except websockets.exceptions.ConnectionClosed:
            self.ten_env.log_info("WebSocket connection closed")
        except Exception as e:
            error_msg = f"WebSocket message handler error: {e}"
            self.ten_env.log_error(error_msg)
            await self.callback.on_error(error_msg)
        finally:
            self.is_started = False
            if not self._closing:
                await self.callback.on_close()

    async def start(self, timeout=10):
        if self.is_connected():
            self.ten_env.log_info("Recognition already started")
            return

        try:
            url = self._build_url()
            self.ten_env.log_info(
                f"vendor_status: connecting to Oracle Speech: {url}",
                category=LOG_CATEGORY_VENDOR,
            )

            self.websocket = await websockets.connect(
                url,
                open_timeout=timeout,
                ping_interval=None,
            )

            self.ten_env.log_info(
                "vendor_status: websocket opened, sending auth credentials",
                category=LOG_CATEGORY_VENDOR,
            )
            self.is_started = True

            await self._send_credentials()

            self._message_task = asyncio.create_task(self._message_handler())

            await self.callback.on_open()

        except asyncio.TimeoutError:
            error_msg = f"Connection timeout after {timeout} seconds"
            self.ten_env.log_error(
                f"Failed to start recognition: {error_msg}",
                category=LOG_CATEGORY_VENDOR,
            )
            await self.callback.on_error(error_msg, TIMEOUT_CODE)

        except Exception as e:
            error_msg = f"Failed to start recognition: {e}"
            self.ten_env.log_error(error_msg, category=LOG_CATEGORY_VENDOR)
            await self.callback.on_error(error_msg)

    async def send_audio_frame(self, audio_data: bytes):
        try:
            if self.websocket is None or not self.is_connected():
                self.ten_env.log_warn(
                    "WebSocket not connected, cannot send audio"
                )
                return

            duration_ms = int(len(audio_data) / (self._sample_rate / 1000 * 2))
            self.audio_timeline.add_user_audio(duration_ms)

            await self.websocket.send(audio_data)
        except websockets.exceptions.ConnectionClosed:
            self.ten_env.log_info(
                "vendor_status: websocket connection closed while sending audio",
                category=LOG_CATEGORY_VENDOR,
            )
            self.is_started = False
            await self.callback.on_error(
                "WebSocket connection closed while sending audio"
            )
        except Exception as e:
            self.ten_env.log_error(
                f"Failed to send audio frame: {e}",
                category=LOG_CATEGORY_VENDOR,
            )
            await self.callback.on_error(f"Failed to send audio frame: {e}")

    async def request_final_result(self):
        """Request the server to return a final transcription result."""
        try:
            if self.websocket is None or not self.is_connected():
                return
            msg = json.dumps({"event": "SEND_FINAL_RESULT"})
            await self.websocket.send(msg)
            self.ten_env.log_info(
                f"vendor_cmd: {msg}",
                category=LOG_CATEGORY_VENDOR,
            )
        except Exception as e:
            self.ten_env.log_error(f"Failed to request final result: {e}")

    async def close(self):
        self._closing = True
        if self.websocket:
            try:
                if self.websocket.state == State.OPEN:
                    await self.websocket.close()
            except Exception as e:
                self.ten_env.log_info(f"Error closing websocket: {e}")

        if self._message_task and not self._message_task.done():
            self._message_task.cancel()
            try:
                await self._message_task
            except asyncio.CancelledError:
                pass

        self.is_started = False
        self.ten_env.log_info(
            "vendor_status: websocket connection closed",
            category=LOG_CATEGORY_VENDOR,
        )

    def is_connected(self) -> bool:
        if self.websocket is None:
            return False
        try:
            if hasattr(self.websocket, "state"):
                return self.is_started and self.websocket.state == State.OPEN
            return self.is_started
        except Exception:
            return False

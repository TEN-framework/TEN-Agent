#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

from dataclasses import dataclass
from typing import AsyncIterator, Tuple

from ten_ai_base.config import BaseConfig
from ten import (
    AsyncTenEnv,
)

import copy
import websockets
import ssl
import uuid
import json
import gzip
import asyncio


MESSAGE_TYPES = {
    11: "audio-only server response",
    12: "frontend server response",
    15: "error message from server",
}
MESSAGE_TYPE_SPECIFIC_FLAGS = {
    0: "no sequence number",
    1: "sequence number > 0",
    2: "last message from server (seq < 0)",
    3: "sequence number < 0",
}
MESSAGE_SERIALIZATION_METHODS = {0: "no serialization", 1: "JSON", 15: "custom type"}
MESSAGE_COMPRESSIONS = {0: "no compression", 1: "gzip", 15: "custom compression method"}


@dataclass
class TTSConfig(BaseConfig):
    # Parameters, refer to: https://www.volcengine.com/docs/6561/79823.
    appid: str = ""
    token: str = ""

    # Refer to: https://www.volcengine.com/docs/6561/1257544.
    voice_type: str = "BV001_streaming"
    sample_rate: int = 16000
    api_url: str = "wss://openspeech.bytedance.com/api/v1/tts/ws_binary"
    cluster: str = "volcano_tts"


class TTSClient:
    def __init__(self, config: TTSConfig, ten_env: AsyncTenEnv) -> None:
        self.config = config
        self.websocket = None
        self.ten_env = ten_env

        # Refer to: https://www.volcengine.com/docs/6561/79823.
        self.request_template = {
            "app": {
                "appid": self.config.appid,
                "token": "access_token",
                "cluster": self.config.cluster,
            },
            "user": {"uid": ""},  # Any non-empty string, used for tracing.
            "audio": {
                "rate": self.config.sample_rate,
                "voice_type": self.config.voice_type,
                "encoding": "pcm",
                "speed_ratio": 1.0,
                "volume_ratio": 1.0,
                "pitch_ratio": 1.0,
            },
            "request": {
                "reqid": "",  # Must be unique for each request.
                "text": "",  # Text to be synthesized.
                "text_type": "plain",
                "operation": "submit",
            },
        }

        # version: b0001 (4 bits)
        # header size: b0001 (4 bits)
        # message type: b0001 (Full client request) (4bits)
        # message type specific flags: b0000 (none) (4bits)
        # message serialization method: b0001 (JSON) (4 bits)
        # message compression: b0001 (gzip) (4bits)
        # reserved data: 0x00 (1 byte)
        self.default_header = bytearray(b"\x11\x10\x11\x00")

    async def connect(self) -> None:
        ssl_context = ssl._create_unverified_context()
        header = {"Authorization": f"Bearer; {self.config.token}"}
        self.websocket = await websockets.connect(
            self.config.api_url,
            ssl=ssl_context,
            extra_headers=header,
            ping_interval=None,
        )

    async def close(self) -> None:
        if self.websocket is not None:
            await self.websocket.close()
            self.ten_env.log_info("Websocket connection closed.")
        else:
            self.ten_env.log_info("Websocket is not connected.")

    async def reconnect(self) -> None:
        await self.close()
        await self.connect()

    def parse_response(self, response: websockets.Data) -> Tuple[bytes, bool]:
        protocol_version = response[0] >> 4
        header_size = response[0] & 0x0F
        message_type = response[1] >> 4
        message_type_specific_flags = response[1] & 0x0F
        serialization_method = response[2] >> 4
        message_compression = response[2] & 0x0F
        reserved = response[3]
        header_extensions = response[4 : header_size * 4]
        payload = response[header_size * 4 :]
        self.ten_env.log_info(
            f"Protocol version: {protocol_version:#x} - version {protocol_version}"
        )
        self.ten_env.log_info(
            f"Header size: {header_size:#x} - {header_size * 4} bytes"
        )
        self.ten_env.log_info(
            f"Message type: {message_type:#x} - {MESSAGE_TYPES[message_type]}"
        )
        self.ten_env.log_info(
            f"Message type specific flags: {message_type_specific_flags:#x} - {MESSAGE_TYPE_SPECIFIC_FLAGS[message_type_specific_flags]}"
        )
        self.ten_env.log_info(
            f"Message serialization method: {serialization_method:#x} - {MESSAGE_SERIALIZATION_METHODS[serialization_method]}"
        )
        self.ten_env.log_info(
            f"Message compression: {message_compression:#x} - {MESSAGE_COMPRESSIONS[message_compression]}"
        )
        self.ten_env.log_info(f"Reserved: {reserved:#04x}")

        if header_size != 1:
            self.ten_env.log_info(f"Header extensions: {header_extensions}")

        if message_type == 0xB:  # audio-only server response
            if message_type_specific_flags == 0:  # no sequence number as ACK
                self.ten_env.log_info("Payload size: 0")
                return None, False
            else:
                sequence_number = int.from_bytes(payload[:4], "big", signed=True)
                payload_size = int.from_bytes(payload[4:8], "big", signed=False)
                payload = payload[8:]
                self.ten_env.log_info(f"Sequence number: {sequence_number}")
                self.ten_env.log_info(f"Payload size: {payload_size} bytes")
            if sequence_number < 0:
                return payload, True
            else:
                return payload, False
        elif message_type == 0xF:
            code = int.from_bytes(payload[:4], "big", signed=False)
            msg_size = int.from_bytes(payload[4:8], "big", signed=False)
            error_msg = payload[8:]
            if message_compression == 1:
                error_msg = gzip.decompress(error_msg)
            error_msg = str(error_msg, "utf-8")
            self.ten_env.log_error(f"Error message code: {code}")
            self.ten_env.log_error(f"Error message size: {msg_size} bytes")
            self.ten_env.log_error(f"Error message: {error_msg}")
            return None, True
        elif message_type == 0xC:
            msg_size = int.from_bytes(payload[:4], "big", signed=False)
            payload = payload[4:]
            if message_compression == 1:
                payload = gzip.decompress(payload)
            self.ten_env.log_info(f"Frontend message: {payload}")
        else:
            self.ten_env.log_error("undefined message type!")
            return None, True

    async def text_to_speech_stream(self, text: str) -> AsyncIterator[bytes]:
        request = copy.deepcopy(self.request_template)
        request["request"]["reqid"] = str(uuid.uuid4())
        request["request"]["text"] = text
        request["user"]["uid"] = str(uuid.uuid4())

        request_bytes = str.encode(json.dumps(request))
        request_bytes = gzip.compress(request_bytes)
        full_request = bytearray(self.default_header)

        # payload size(4 bytes)
        full_request.extend((len(request_bytes)).to_bytes(4, "big"))

        # payload
        full_request.extend(request_bytes)

        if self.websocket is not None:
            try:
                await self.websocket.send(full_request)
                self.ten_env.log_info(f"Sent: {request}")

                while True:
                    resp = await self.websocket.recv()
                    payload, done = self.parse_response(resp)
                    if payload:
                        yield payload

                    if done:
                        self.ten_env.log_info(
                            f"Response is completed for request: {request['request']['reqid']}."
                        )
                        break

            except websockets.exceptions.ConnectionClosedError as e:
                self.ten_env.log_info(f"Connection closed with error: {e}.")
                await self.reconnect()
            except asyncio.TimeoutError:
                self.ten_env.log_info("Timeout waiting for response.")
        else:
            self.ten_env.log_error("Websocket is not connected.")

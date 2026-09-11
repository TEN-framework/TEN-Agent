from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from enum import IntEnum
from typing import Any


PROTOCOL_VERSION = 0b0001
HEADER_SIZE = 0b0001


class MessageType(IntEnum):
    FULL_CLIENT_REQUEST = 0b0001
    AUDIO_ONLY_REQUEST = 0b0010
    FULL_SERVER_RESPONSE = 0b1001
    AUDIO_ONLY_RESPONSE = 0b1011
    ERROR = 0b1111


class MessageFlag(IntEnum):
    NO_SEQUENCE = 0b0000
    POSITIVE_SEQUENCE = 0b0001
    LAST_NO_SEQUENCE = 0b0010
    NEGATIVE_SEQUENCE = 0b0011
    WITH_EVENT = 0b0100


class Serialization(IntEnum):
    RAW = 0b0000
    JSON = 0b0001


class Compression(IntEnum):
    NONE = 0b0000
    GZIP = 0b0001


class ClientEvent(IntEnum):
    START_CONNECTION = 1
    FINISH_CONNECTION = 2
    START_SESSION = 100
    FINISH_SESSION = 102
    TASK_REQUEST = 200
    UPDATE_CONFIG = 201
    SAY_HELLO = 300
    END_ASR = 400
    CHAT_TTS_TEXT = 500
    CHAT_TEXT_QUERY = 501
    CLIENT_INTERRUPT = 515


class ServerEvent(IntEnum):
    CONNECTION_STARTED = 50
    CONNECTION_FAILED = 51
    CONNECTION_FINISHED = 52
    SESSION_STARTED = 150
    SESSION_FINISHED = 152
    SESSION_FAILED = 153
    USAGE_RESPONSE = 154
    CONFIG_UPDATED = 251
    TTS_SENTENCE_START = 350
    TTS_SENTENCE_END = 351
    TTS_RESPONSE = 352
    TTS_ENDED = 359
    ASR_INFO = 450
    ASR_RESPONSE = 451
    ASR_ENDED = 459
    CHAT_RESPONSE = 550
    CHAT_TEXT_QUERY_CONFIRMED = 553
    CHAT_ENDED = 559
    DIALOG_COMMON_ERROR = 599


SESSION_EVENTS = {
    ServerEvent.SESSION_STARTED,
    ServerEvent.SESSION_FINISHED,
    ServerEvent.SESSION_FAILED,
    ServerEvent.USAGE_RESPONSE,
    ServerEvent.CONFIG_UPDATED,
    ServerEvent.TTS_SENTENCE_START,
    ServerEvent.TTS_SENTENCE_END,
    ServerEvent.TTS_RESPONSE,
    ServerEvent.TTS_ENDED,
    ServerEvent.ASR_INFO,
    ServerEvent.ASR_RESPONSE,
    ServerEvent.ASR_ENDED,
    ServerEvent.CHAT_RESPONSE,
    ServerEvent.CHAT_TEXT_QUERY_CONFIRMED,
    ServerEvent.CHAT_ENDED,
    ServerEvent.DIALOG_COMMON_ERROR,
}


@dataclass
class Header:
    message_type: int
    flags: int = MessageFlag.WITH_EVENT
    serialization: int = Serialization.JSON
    compression: int = Compression.NONE

    def to_bytes(self) -> bytes:
        return bytes(
            [
                (PROTOCOL_VERSION << 4) | HEADER_SIZE,
                (self.message_type << 4) | self.flags,
                (self.serialization << 4) | self.compression,
                0x00,
            ]
        )


@dataclass
class ServerMessage:
    message_type: int
    flags: int
    serialization: int
    compression: int
    event: int = 0
    session_id: str | None = None
    connection_id: str | None = None
    error_code: int = 0
    payload: bytes = b""
    payload_json: dict[str, Any] | None = None


def _bytes_with_size(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return len(encoded).to_bytes(4, "big", signed=False) + encoded


def build_client_event(
    event: int,
    payload: bytes | dict[str, Any] | None = None,
    session_id: str | None = None,
    message_type: int = MessageType.FULL_CLIENT_REQUEST,
    serialization: int = Serialization.JSON,
) -> bytes:
    header = Header(
        message_type=message_type,
        serialization=serialization,
    ).to_bytes()

    optional = bytearray()
    optional.extend(int(event).to_bytes(4, "big", signed=False))
    if session_id is not None:
        optional.extend(_bytes_with_size(session_id))

    if payload is None:
        payload_bytes = b"{}" if serialization == Serialization.JSON else b""
    elif isinstance(payload, (bytes, bytearray, memoryview)):
        payload_bytes = bytes(payload)
    else:
        payload_bytes = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")

    return b"".join(
        [
            header,
            bytes(optional),
            len(payload_bytes).to_bytes(4, "big", signed=False),
            payload_bytes,
        ]
    )


def read_sized_text(data: bytes, offset: int) -> tuple[str, int]:
    if offset + 4 > len(data):
        return "", offset
    size = int.from_bytes(data[offset : offset + 4], "big", signed=False)
    offset += 4
    if offset + size > len(data):
        return "", offset
    value = data[offset : offset + size].decode("utf-8")
    return value, offset + size


def read_payload(data: bytes, offset: int) -> tuple[bytes, int]:
    if offset + 4 > len(data):
        return b"", offset
    size = int.from_bytes(data[offset : offset + 4], "big", signed=False)
    offset += 4
    if offset + size > len(data):
        return b"", offset
    return data[offset : offset + size], offset + size


def parse_server_message(data: bytes) -> ServerMessage:
    if len(data) < 4:
        raise ValueError("server message is shorter than header")

    header_size = data[0] & 0x0F
    message_type = data[1] >> 4
    flags = data[1] & 0x0F
    serialization = data[2] >> 4
    compression = data[2] & 0x0F
    offset = header_size * 4

    message = ServerMessage(
        message_type=message_type,
        flags=flags,
        serialization=serialization,
        compression=compression,
    )

    if message_type == MessageType.ERROR:
        if offset + 4 <= len(data):
            message.error_code = int.from_bytes(
                data[offset : offset + 4], "big", signed=False
            )
            offset += 4
        message.payload, _ = read_payload(data, offset)
        _decode_payload(message)
        return message

    if flags & MessageFlag.POSITIVE_SEQUENCE:
        offset += 4

    if flags & MessageFlag.WITH_EVENT:
        if offset + 4 > len(data):
            return message
        message.event = int.from_bytes(
            data[offset : offset + 4], "big", signed=False
        )
        offset += 4

    event = _safe_server_event(message.event)
    if event == ServerEvent.CONNECTION_STARTED:
        message.connection_id, offset = read_sized_text(data, offset)
    elif event == ServerEvent.CONNECTION_FAILED:
        message.payload, offset = read_payload(data, offset)
    elif event in SESSION_EVENTS:
        message.session_id, offset = read_sized_text(data, offset)
        message.payload, offset = read_payload(data, offset)
    else:
        message.payload, offset = read_payload(data, offset)

    _decode_payload(message)
    return message


def _safe_server_event(event: int) -> ServerEvent | None:
    try:
        return ServerEvent(event)
    except ValueError:
        return None


def _decode_payload(message: ServerMessage) -> None:
    if message.compression == Compression.GZIP and message.payload:
        message.payload = gzip.decompress(message.payload)

    if message.serialization != Serialization.JSON or not message.payload:
        return

    try:
        payload = message.payload.decode("utf-8")
        message.payload_json = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        message.payload_json = None

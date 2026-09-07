#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import base64
from collections.abc import Mapping
from dataclasses import dataclass, field
import json
from typing import Any

from .config import IFlytekAsrConfig

STATUS_FIRST = 0
STATUS_CONTINUE = 1
STATUS_LAST = 2
FINAL_DUMMY_AUDIO = b"\x00\x00"
MAX_AUDIO_FRAME_BYTES = 16 * 1024


class IFlytekProtocolError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        sid: str = "",
        trace_id: str = "",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.sid = sid
        self.trace_id = trace_id


@dataclass(frozen=True)
class IFlytekWord:
    word: str
    start_ms: int
    duration_ms: int
    stable: bool


@dataclass(frozen=True)
class IFlytekTranscript:
    text: str
    final: bool
    start_ms: int
    duration_ms: int
    language: str
    words: list[IFlytekWord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IFlytekResponse:
    terminal: bool
    transcript: IFlytekTranscript | None
    sid: str = ""
    trace_id: str = ""
    status: int = STATUS_CONTINUE


def build_audio_request(
    config: IFlytekAsrConfig,
    trace_id: str,
    status: int,
    audio: bytes,
) -> dict[str, Any]:
    if status not in (STATUS_FIRST, STATUS_CONTINUE, STATUS_LAST):
        raise ValueError(f"unsupported status: {status}")
    if len(audio) > MAX_AUDIO_FRAME_BYTES:
        raise ValueError("audio frame must not exceed 16 KiB")
    if status == STATUS_LAST and len(audio) % 2 != 0:
        raise ValueError(
            "the final audio frame must contain an even number of bytes"
        )

    header: dict[str, Any] = {
        "traceId": trace_id,
        "bizId": config.biz_id,
        "status": status,
    }
    if config.app_id:
        header["appId"] = config.app_id

    engine: dict[str, str] = {}
    payload: dict[str, Any] = {
        "audio": {"audio": base64.b64encode(audio).decode("ascii")}
    }

    if status == STATUS_FIRST:
        engine = config.engine_parameters()
        if config.res_id_list:
            header["resIdList"] = list(config.res_id_list)
        if config.hotwords:
            payload["text"] = {
                "text": config.hotwords,
                "weight": str(config.hotword_weight),
            }
        if config.voiceprints:
            payload["swk"] = {"swk": dict(config.voiceprints)}

    return {
        "header": header,
        "parameter": {"engine": engine},
        "payload": payload,
    }


def build_finalize_request(
    config: IFlytekAsrConfig, trace_id: str
) -> dict[str, Any]:
    return build_audio_request(
        config=config,
        trace_id=trace_id,
        status=STATUS_LAST,
        audio=FINAL_DUMMY_AUDIO,
    )


def parse_response(
    message: str | bytes | Mapping[str, Any], language: str
) -> IFlytekResponse:
    data = _load_message(message)
    header = _mapping(data.get("header"), "header")

    code = str(header.get("code", "0"))
    vendor_message = str(header.get("message", ""))
    sid = str(header.get("sid", ""))
    trace_id = str(header.get("traceId", ""))
    if "status" not in header:
        raise IFlytekProtocolError(
            "invalid_response", "header.status is required"
        )
    status = _integer(header["status"], "header.status")
    if status not in (STATUS_FIRST, STATUS_CONTINUE, STATUS_LAST):
        raise IFlytekProtocolError(
            "invalid_response", "header.status must be 0, 1, or 2"
        )

    if code != "0":
        raise IFlytekProtocolError(
            code=code,
            message=vendor_message or "iFLYTEK ASR returned an error",
            sid=sid,
            trace_id=trace_id,
        )

    terminal = status == STATUS_LAST
    payload = data.get("payload", {})
    if payload is None:
        payload = {}
    payload_mapping = _mapping(payload, "payload")
    result_value = payload_mapping.get("result")
    if result_value is None:
        return IFlytekResponse(
            terminal=terminal,
            transcript=None,
            sid=sid,
            trace_id=trace_id,
            status=status,
        )

    result = _mapping(result_value, "payload.result")
    message_type = str(result.get("msgtype", ""))
    final_value = result.get("ls", False)
    if not isinstance(final_value, bool):
        raise IFlytekProtocolError(
            "invalid_response", "payload.result.ls must be a boolean"
        )
    final = final_value or terminal or message_type.casefold() == "sentence"

    words, speaker_events = _parse_words(result.get("ws", []), final)
    text = "".join(word.word for word in words)
    start_ms = _integer(result.get("bg", 0), "payload.result.bg")
    end_ms = _integer(result.get("ed", start_ms), "payload.result.ed")

    metadata: dict[str, Any] = {
        "sid": sid,
        "trace_id": trace_id,
        "status": status,
        "message_type": message_type,
    }
    _copy_if_present(result, metadata, "segId", "segment_id")
    _copy_if_present(result, metadata, "sn", "sequence_number")
    _copy_if_present(result, metadata, "nameMapping", "name_mapping")
    temporary_voiceprints = result.get("tmpSwk")
    if isinstance(temporary_voiceprints, Mapping):
        metadata["temporary_voiceprint_ids"] = sorted(
            str(speaker_id) for speaker_id in temporary_voiceprints
        )
    if speaker_events:
        metadata["speaker_events"] = speaker_events

    transcript = IFlytekTranscript(
        text=text,
        final=final,
        start_ms=max(0, start_ms),
        duration_ms=max(0, end_ms - start_ms),
        language=language,
        words=words,
        metadata=metadata,
    )
    return IFlytekResponse(
        terminal=terminal,
        transcript=transcript,
        sid=sid,
        trace_id=trace_id,
        status=status,
    )


def _load_message(message: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(message, Mapping):
        return dict(message)
    try:
        decoded = (
            message.decode("utf-8") if isinstance(message, bytes) else message
        )
        value = json.loads(decoded)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IFlytekProtocolError(
            "invalid_response", f"invalid iFLYTEK ASR response: {error}"
        ) from error
    return dict(_mapping(value, "response"))


def _parse_words(
    groups_value: Any, final: bool
) -> tuple[list[IFlytekWord], list[dict[str, Any]]]:
    if not isinstance(groups_value, list):
        raise IFlytekProtocolError(
            "invalid_response", "payload.result.ws must be an array"
        )

    words: list[IFlytekWord] = []
    speaker_events: list[dict[str, Any]] = []
    for group_value in groups_value:
        group = _mapping(group_value, "payload.result.ws item")
        candidates = group.get("cw", [])
        if not isinstance(candidates, list):
            raise IFlytekProtocolError(
                "invalid_response", "payload.result.ws.cw must be an array"
            )
        for candidate_value in candidates:
            candidate = _mapping(candidate_value, "payload.result.ws.cw item")
            word = str(candidate.get("w", ""))
            start_frame = _integer(candidate.get("wb", 0), "cw.wb")
            end_frame = _integer(candidate.get("we", start_frame), "cw.we")
            word_index = len(words)
            words.append(
                IFlytekWord(
                    word=word,
                    start_ms=max(0, start_frame * 10),
                    duration_ms=max(0, (end_frame - start_frame) * 10),
                    stable=final,
                )
            )
            speaker_id = candidate.get("rl", 0)
            if speaker_id not in (None, 0, "0", ""):
                speaker_events.append(
                    {
                        "word_index": word_index,
                        "speaker_id": str(speaker_id),
                    }
                )
    return words, speaker_events


def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise IFlytekProtocolError(
            "invalid_response", f"{field_name} must be an object"
        )
    return value


def _integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise IFlytekProtocolError(
            "invalid_response", f"{field_name} must be an integer"
        )
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise IFlytekProtocolError(
            "invalid_response", f"{field_name} must be an integer"
        ) from error


def _copy_if_present(
    source: Mapping[str, Any],
    target: dict[str, Any],
    source_key: str,
    target_key: str,
) -> None:
    if source_key in source:
        target[target_key] = source[source_key]

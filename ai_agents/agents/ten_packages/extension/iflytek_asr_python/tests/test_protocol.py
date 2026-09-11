import base64
import json

import pytest

from iflytek_asr_python.config import IFlytekAsrConfig
from iflytek_asr_python.protocol import (
    STATUS_CONTINUE,
    STATUS_FIRST,
    STATUS_LAST,
    IFlytekProtocolError,
    build_audio_request,
    build_finalize_request,
    parse_response,
)


@pytest.fixture
def config() -> IFlytekAsrConfig:
    return IFlytekAsrConfig(
        params={
            "url": "ws://127.0.0.1:9990/tuling/ast/v3",
            "app_id": "app-1",
            "biz_id": "tenant-1",
            "language": "zh|en",
            "engine": {"wfep_param_nOnlineSpkdia_on": "2"},
            "res_id_list": ["tenant-2"],
            "hotwords": "zh-科大讯飞;en-Agora",
            "hotword_weight": 4.0,
            "voiceprints": {"10001": "dm9pY2VwcmludA=="},
        }
    )


def test_first_request_contains_audio_and_session_options(
    config: IFlytekAsrConfig,
) -> None:
    request = build_audio_request(
        config=config,
        trace_id="trace-1",
        status=STATUS_FIRST,
        audio=b"\x01\x02",
    )

    assert request == {
        "header": {
            "traceId": "trace-1",
            "appId": "app-1",
            "bizId": "tenant-1",
            "status": 0,
            "resIdList": ["tenant-2"],
        },
        "parameter": {
            "engine": {
                "wfep_param_nOnlineSpkdia_on": "2",
                "wrec_param_language_name": "zh|en",
            }
        },
        "payload": {
            "audio": {"audio": base64.b64encode(b"\x01\x02").decode()},
            "text": {"text": "zh-科大讯飞;en-Agora", "weight": "4.0"},
            "swk": {"swk": {"10001": "dm9pY2VwcmludA=="}},
        },
    }


def test_intermediate_request_omits_first_frame_options(
    config: IFlytekAsrConfig,
) -> None:
    request = build_audio_request(
        config=config,
        trace_id="trace-1",
        status=STATUS_CONTINUE,
        audio=b"pcm",
    )

    assert request["header"] == {
        "traceId": "trace-1",
        "appId": "app-1",
        "bizId": "tenant-1",
        "status": 1,
    }
    assert request["parameter"] == {"engine": {}}
    assert request["payload"] == {
        "audio": {"audio": base64.b64encode(b"pcm").decode()}
    }


def test_finalize_request_uses_even_length_dummy_audio(
    config: IFlytekAsrConfig,
) -> None:
    request = build_finalize_request(config, "trace-1")

    assert request["header"]["status"] == STATUS_LAST
    encoded = request["payload"]["audio"]["audio"]
    assert base64.b64decode(encoded) == b"\x00\x00"


def test_last_request_rejects_odd_length_audio(
    config: IFlytekAsrConfig,
) -> None:
    with pytest.raises(ValueError, match="even number of bytes"):
        build_audio_request(config, "trace-1", STATUS_LAST, b"\x00")


def test_request_rejects_audio_larger_than_vendor_limit(
    config: IFlytekAsrConfig,
) -> None:
    with pytest.raises(ValueError, match="16 KiB"):
        build_audio_request(
            config,
            "trace-1",
            STATUS_CONTINUE,
            b"\x00" * (16 * 1024 + 1),
        )


def test_parse_sentence_response_maps_words_and_metadata() -> None:
    response = parse_response(
        json.dumps(
            {
                "header": {
                    "code": 0,
                    "message": "success",
                    "sid": "AST-1",
                    "traceId": "trace-1",
                    "status": 1,
                },
                "payload": {
                    "result": {
                        "segId": 3,
                        "sn": 7,
                        "bg": 140,
                        "ed": 3230,
                        "ls": False,
                        "msgtype": "sentence",
                        "ws": [
                            {
                                "cw": [
                                    {
                                        "w": "你好",
                                        "wb": 17,
                                        "we": 56,
                                        "wp": "n",
                                        "sf": 0,
                                        "rl": 10001,
                                    }
                                ]
                            },
                            {
                                "cw": [
                                    {
                                        "w": "。",
                                        "wb": 57,
                                        "we": 58,
                                        "wp": "p",
                                        "sf": 0,
                                        "rl": 0,
                                    }
                                ]
                            },
                        ],
                        "nameMapping": {"10001": "张三"},
                        "tmpSwk": {"1": "dGVtcA=="},
                    }
                },
            },
            ensure_ascii=False,
        ),
        language="zh|en",
    )

    assert response.terminal is False
    assert response.transcript is not None
    assert response.transcript.text == "你好。"
    assert response.transcript.final is True
    assert response.transcript.start_ms == 140
    assert response.transcript.duration_ms == 3090
    assert response.transcript.language == "zh|en"
    assert response.transcript.words[0].word == "你好"
    assert response.transcript.words[0].start_ms == 170
    assert response.transcript.words[0].duration_ms == 390
    assert response.transcript.metadata["sid"] == "AST-1"
    assert response.transcript.metadata["name_mapping"] == {"10001": "张三"}
    assert response.transcript.metadata["speaker_events"] == [
        {"word_index": 0, "speaker_id": "10001"}
    ]


def test_parse_progressive_response_is_interim() -> None:
    response = parse_response(
        {
            "header": {"code": 0, "status": 1},
            "payload": {
                "result": {
                    "bg": 0,
                    "ed": 250,
                    "ls": False,
                    "msgtype": "Progressive",
                    "ws": [{"cw": [{"w": "测试", "wb": 0, "we": 25}]}],
                }
            },
        },
        language="zh",
    )

    assert response.transcript is not None
    assert response.transcript.final is False


def test_parse_terminal_response_without_result() -> None:
    response = parse_response(
        {"header": {"code": 0, "status": 2}, "payload": {}},
        language="zh",
    )

    assert response.terminal is True
    assert response.transcript is None


def test_parse_vendor_error_raises_structured_error() -> None:
    with pytest.raises(IFlytekProtocolError) as error:
        parse_response(
            {
                "header": {
                    "code": 1,
                    "message": "unknown error",
                    "sid": "AST-1",
                    "traceId": "trace-1",
                    "status": 2,
                }
            },
            language="zh",
        )

    assert error.value.code == "1"
    assert error.value.message == "unknown error"
    assert error.value.sid == "AST-1"
    assert error.value.trace_id == "trace-1"


@pytest.mark.parametrize(
    "header",
    [
        {"code": 0, "status": 99},
        {"code": 0},
    ],
)
def test_parse_response_rejects_missing_or_invalid_status(
    header: dict[str, object],
) -> None:
    with pytest.raises(IFlytekProtocolError, match="header.status"):
        parse_response({"header": header, "payload": {}}, language="zh-CN")


def test_parse_response_rejects_non_boolean_final_flag() -> None:
    with pytest.raises(IFlytekProtocolError, match="payload.result.ls"):
        parse_response(
            {
                "header": {"code": 0, "status": 1},
                "payload": {
                    "result": {
                        "bg": 0,
                        "ed": 10,
                        "ls": "false",
                        "msgtype": "Progressive",
                        "ws": [],
                    }
                },
            },
            language="zh-CN",
        )

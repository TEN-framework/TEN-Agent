#!/usr/bin/env python3
"""
Tests for Telnyx Call Control event handling in the SIP example.
"""
import asyncio
import sys
import types
from pathlib import Path


EXTENSION_DIR = Path(__file__).parent / "ten_packages" / "extension"
PACKAGE_DIR = EXTENSION_DIR / "main_python"
main_python = types.ModuleType("main_python")
main_python.__path__ = [str(PACKAGE_DIR)]
sys.modules["main_python"] = main_python

from main_python.config import TelnyxConfig
from main_python.server import TelnyxCallServer


def make_server():
    return TelnyxCallServer(
        TelnyxConfig(
            telnyx_api_key="test-key",
            telnyx_connection_id="connection-id",
            telnyx_from_number="+18005550100",
            telnyx_server_port=9000,
            telnyx_public_server_url="example.com",
            telnyx_use_https=True,
            telnyx_use_wss=True,
        )
    )


def test_url_builders():
    server = make_server()

    assert server._media_ws_url() == "wss://example.com/media"
    assert server._webhook_url() == "https://example.com/webhook/status"
    assert server._streaming_params() == {
        "stream_url": "wss://example.com/media",
        "stream_track": "both_tracks",
        "stream_codec": "PCMU",
        "stream_bidirectional_mode": "rtp",
        "stream_bidirectional_codec": "PCMU",
    }


def test_parse_telnyx_webhook_event():
    event_type, payload = TelnyxCallServer._parse_telnyx_event(
        {
            "data": {
                "event_type": "call.initiated",
                "payload": {
                    "call_control_id": "call-control-id",
                    "direction": "incoming",
                    "state": "parked",
                },
            }
        }
    )

    assert event_type == "call.initiated"
    assert payload["call_control_id"] == "call-control-id"
    assert payload["direction"] == "incoming"


def test_update_session_from_telnyx_events():
    server = make_server()

    call_id = server._update_session_from_event(
        "call.initiated",
        {
            "call_control_id": "call-control-id",
            "call_leg_id": "call-leg-id",
            "call_session_id": "call-session-id",
            "from": "+18005550100",
            "to": "+18005550101",
            "direction": "incoming",
            "state": "parked",
        },
    )

    assert call_id == "call-control-id"
    session = server.active_call_sessions["call-control-id"]
    assert session["status"] == "parked"
    assert session["direction"] == "incoming"
    assert session["phone_number"] == "+18005550101"

    server._update_session_from_event(
        "call.hangup",
        {
            "call_control_id": "call-control-id",
            "state": "hangup",
        },
    )

    assert server.active_call_sessions["call-control-id"]["status"] == "completed"
    assert "ended_at" in server.active_call_sessions["call-control-id"]


def test_dial_payload_uses_telnyx_call_control_fields():
    server = make_server()
    requests = []

    async def fake_post(path, payload):
        requests.append((path, payload))
        return {"data": {"call_control_id": "call-control-id"}}

    server._post_telnyx = fake_post
    asyncio.run(server._dial_call("+18005550101"))

    path, payload = requests[0]
    assert path == "/calls"
    assert payload["to"] == "+18005550101"
    assert payload["from"] == "+18005550100"
    assert payload["connection_id"] == "connection-id"
    assert payload["stream_url"] == "wss://example.com/media"
    assert payload["stream_track"] == "both_tracks"
    assert payload["stream_codec"] == "PCMU"
    assert payload["stream_bidirectional_mode"] == "rtp"
    assert payload["webhook_url"] == "https://example.com/webhook/status"
    assert "answer_url" not in payload


def test_call_control_command_paths_are_encoded():
    server = make_server()
    requests = []

    async def fake_post(path, payload):
        requests.append((path, payload))
        return {"data": {"result": "ok"}}

    server._post_telnyx = fake_post
    asyncio.run(server._answer_call("v3:test/id"))
    asyncio.run(server._hangup_call("v3:test/id"))

    assert requests[0][0] == "/calls/v3%3Atest%2Fid/actions/answer"
    assert requests[1][0] == "/calls/v3%3Atest%2Fid/actions/hangup"


def test_cleanup_hangs_up_active_sessions():
    server = make_server()
    requests = []
    server.active_call_sessions["v3:test/id"] = {
        "call_id": "v3:test/id",
        "status": "answered",
    }

    def fake_post_sync(path, payload):
        requests.append((path, payload))
        return {"data": {"result": "ok"}}

    server._post_telnyx_sync = fake_post_sync
    server.cleanup()

    assert requests == [("/calls/v3%3Atest%2Fid/actions/hangup", {})]


def test_bidirectional_media_omits_stream_id():
    source = (PACKAGE_DIR / "extension.py").read_text()
    send_audio_source = source.split("async def send_audio_to_telnyx", 1)[1]
    send_audio_source = send_audio_source.split(
        "async def _cleanup_call_after_delay", 1
    )[0]

    assert '"event": "media"' in send_audio_source
    assert '"media": {"payload": audio_base64}' in send_audio_source
    assert '"stream_id":' not in send_audio_source


if __name__ == "__main__":
    test_url_builders()
    test_parse_telnyx_webhook_event()
    test_update_session_from_telnyx_events()
    test_dial_payload_uses_telnyx_call_control_fields()
    test_call_control_command_paths_are_encoded()
    test_cleanup_hangs_up_active_sessions()
    test_bidirectional_media_omits_stream_id()
    print("All Telnyx Call Control event tests passed")

#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from spatius import (
    AgoraEgressConfig,
    AudioFormat,
    AvatarSDKError,
    AvatarSDKErrorCode,
    AvatarSession,
    OggOpusEncoderConfig,
    SessionTokenError,
    configure_telemetry,
)
from ten_ai_base.message import ModuleError
from ten_runtime import AsyncTenEnv

from .. import extension as extension_module
from ..extension import SpatiusAvatarExtension, SpatiusConfig


@pytest.fixture
def avatar():
    extension = SpatiusAvatarExtension("spatius-test")
    extension.ten_env = MagicMock(spec=AsyncTenEnv)
    extension.config = SpatiusConfig(
        spatius_api_key="test-api-key",
        spatius_app_id="test-app-id",
        spatius_avatar_id="test-avatar-id",
        agora_appid="test-agora-app-id",
        agora_uid="12345",
        agora_channel="test-channel",
        agora_token="test-agora-token",
    )
    return extension


@pytest.fixture
def sdk(monkeypatch, avatar):
    # Use the released SDK's constructor and config validation, with no network
    # operations or telemetry export during the tests.
    configure_telemetry("")

    async def initialize():
        config = avatar.session.config
        if config.region == "auto":
            config.apply_resolved_region("eu-west")

    mocks = SimpleNamespace(
        factory=MagicMock(wraps=extension_module.new_avatar_session),
        init=AsyncMock(side_effect=initialize),
        start=AsyncMock(return_value="test-connection-id"),
        send_audio=AsyncMock(),
        interrupt=AsyncMock(),
        close=AsyncMock(),
    )
    monkeypatch.setattr(extension_module, "new_avatar_session", mocks.factory)
    for name in ("init", "start", "send_audio", "interrupt", "close"):
        monkeypatch.setattr(AvatarSession, name, getattr(mocks, name))
    return mocks


@pytest.mark.parametrize(
    "region,audio_format,sample_rate,expire_minutes",
    [
        ("", "ogg_opus", 24000, 30),
        (" \t", "pcm_s16le", 16000, 12),
        ("auto", "ogg_opus", 24000, 30),
        (" us-west ", "ogg_opus", 24000, 30),
    ],
)
def test_session_configuration(
    avatar, sdk, region, audio_format, sample_rate, expire_minutes
):
    async def run_test():
        avatar.config.params = {
            "region": region,
            "audio_format": audio_format,
            "sample_rate": sample_rate,
            "session_expire_minutes": expire_minutes,
        }
        avatar.config.update_params()
        avatar.config.validate_params()
        before = datetime.now(timezone.utc)
        await avatar.connect_to_avatar(avatar.ten_env)
        after = datetime.now(timezone.utc)

        sdk.factory.assert_called_once()
        kwargs = sdk.factory.call_args.kwargs
        if region.strip():
            assert kwargs["region"] == region.strip()
        else:
            assert "region" not in kwargs
        config = avatar.session.config
        assert isinstance(avatar.session, AvatarSession)
        assert config.api_key == "test-api-key"
        assert config.app_id == "test-app-id"
        assert config.avatar_id == "test-avatar-id"
        assert config.sample_rate == sample_rate
        assert config.audio_format == AudioFormat(audio_format)
        assert config.expire_at.tzinfo == timezone.utc
        lifetime = timedelta(minutes=expire_minutes)
        assert before + lifetime <= config.expire_at <= after + lifetime
        assert isinstance(config.agora_egress, AgoraEgressConfig)
        assert config.agora_egress.channel_name == "test-channel"
        assert config.agora_egress.token == "test-agora-token"
        assert config.agora_egress.uid == 12345
        assert config.agora_egress.publisher_id == "12345"
        if audio_format == "ogg_opus":
            assert config.ogg_opus_encoder == OggOpusEncoderConfig()
        else:
            assert config.ogg_opus_encoder is None
        sdk.init.assert_awaited_once()
        sdk.start.assert_awaited_once()
        assert avatar.connection_id == "test-connection-id"

    asyncio.run(run_test())


def test_extra_params_are_isolated_from_caller_and_config(avatar, sdk):
    async def run_test():
        extra_params = {"server_post_process": "false"}
        avatar.config.params = {"extra_params": extra_params}
        avatar.config.update_params()
        extra_params["server_post_process"] = "caller-change"

        await avatar.connect_to_avatar(avatar.ten_env)
        forwarded = sdk.factory.call_args.kwargs["extra_params"]
        assert forwarded == {"server_post_process": "false"}
        assert forwarded is not avatar.config.extra_params
        avatar.config.extra_params["server_post_process"] = "config-change"
        assert forwarded == {"server_post_process": "false"}
        assert avatar.session.config.extra_params == {
            "server_post_process": "false"
        }

    asyncio.run(run_test())


@pytest.mark.parametrize("requested", ["", "auto", "us-west"])
@pytest.mark.parametrize("close_fails", [False, True])
def test_region_reporting_and_disconnect(avatar, sdk, requested, close_fails):
    async def run_test():
        avatar.config.region = requested
        resolved = "us-west" if requested == "us-west" else "eu-west"
        await avatar.connect_to_avatar(avatar.ten_env)

        assert avatar.config.region == requested
        assert avatar.get_vendor_metadata()["region"] == resolved
        assert any(
            f"region={resolved}" in logged.args[0]
            and "Connected successfully" in logged.args[0]
            for logged in avatar.ten_env.log_info.call_args_list
        )
        if close_fails:
            sdk.close.side_effect = RuntimeError("connection already closed")
        await avatar.disconnect_from_avatar(avatar.ten_env)

        sdk.close.assert_awaited_once()
        assert avatar.session is None
        assert avatar.connection_id == ""
        metadata = avatar.get_vendor_metadata()
        assert "avatar_session_id" not in metadata
        if requested:
            assert metadata["region"] == requested
        else:
            assert "region" not in metadata

    asyncio.run(run_test())


def test_audio_eof_interrupt_and_shutdown(avatar, sdk):
    async def run_test():
        await avatar.connect_to_avatar(avatar.ten_env)
        await avatar.send_audio_to_avatar(b"\x01\x00\x02\x00")
        await avatar.send_audio_to_avatar(b"\x03\x00")
        await avatar.send_eof_to_avatar()
        await avatar.interrupt_avatar()
        await avatar.on_stop(avatar.ten_env)

        assert sdk.send_audio.await_args_list == [
            call(b"\x01\x00\x02\x00", end=False),
            call(b"\x03\x00", end=False),
            call(b"", end=True),
        ]
        sdk.interrupt.assert_awaited_once()
        sdk.close.assert_awaited_once()
        assert avatar.session is None
        assert avatar.connection_id == ""

    asyncio.run(run_test())


@pytest.mark.parametrize("phase", ["session_token", "websocket_handshake"])
def test_startup_failure_reports_error_without_audio_task(avatar, sdk, phase):
    async def run_test():
        if phase == "session_token":
            error = SessionTokenError(
                "Timed out while creating session token",
                code=AvatarSDKErrorCode.connectionFailed,
            )
            sdk.init.side_effect = error
        else:
            error = AvatarSDKError(
                code=AvatarSDKErrorCode.connectionFailed,
                message="Timed out waiting for server handshake response",
                phase="websocket_handshake",
            )
            sdk.start.side_effect = error
        avatar.config.validate_params()
        avatar._config_valid = True

        with pytest.raises(type(error)) as raised:
            await avatar.on_start(avatar.ten_env)
        assert raised.value is error
        assert avatar._audio_task is None
        sdk.send_audio.assert_not_awaited()
        if phase == "session_token":
            sdk.start.assert_not_awaited()
        avatar.ten_env.send_data.assert_awaited_once()
        data = avatar.ten_env.send_data.await_args.args[0]
        payload_json, property_error = data.get_property_to_json("")
        assert property_error is None
        payload = ModuleError.model_validate_json(payload_json)
        assert payload.module == "avatar"
        assert payload.code == -1
        assert payload.vendor_info.vendor == "spatius"
        assert payload.vendor_info.code == type(error).__name__
        assert payload.vendor_info.message == str(error)
        if phase == "websocket_handshake":
            assert payload.metadata["vendor_metadata"]["region"] == "eu-west"

        await avatar.on_stop(avatar.ten_env)
        sdk.close.assert_awaited_once()

    asyncio.run(run_test())

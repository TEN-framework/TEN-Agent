#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from time import time
from typing import TypedDict

from agora_token_builder import RtcTokenBuilder
from ten_runtime import AsyncTenEnv
from ten_ai_base.config import BaseConfig
from ten_ai_base.utils import encrypt
from spatius import (
    AgoraEgressConfig,
    AudioFormat,
    OggOpusEncoderConfig,
    new_avatar_session,
)

from .avatar_base import AsyncAvatarBaseExtension

DEFAULT_AUDIO_FORMAT = AudioFormat.OGG_OPUS.value
SUPPORTED_OPUS_SAMPLE_RATES = {8000, 12000, 16000, 24000, 48000}


class SpatiusParams(TypedDict, total=False):
    """User-facing params accepted by the Spatius extension."""

    spatius_api_key: str
    spatius_app_id: str
    spatius_avatar_id: str
    agora_uid: str
    agora_token: str
    agora_appid: str
    agora_appcert: str
    agora_channel: str
    region: str
    sample_rate: int | str
    session_expire_minutes: int | str
    audio_format: str
    extra_params: dict[str, str]


@dataclass
class SpatiusConfig(BaseConfig):
    """Configuration for Spatius Avatar Extension."""

    spatius_api_key: str = ""
    spatius_app_id: str = ""
    spatius_avatar_id: str = ""

    agora_uid: str = ""
    agora_token: str = ""
    agora_appid: str = ""
    agora_appcert: str = ""
    agora_channel: str = ""

    region: str = ""
    sample_rate: int = 24000
    session_expire_minutes: int = 30
    audio_format: str = DEFAULT_AUDIO_FORMAT
    extra_params: dict[str, str] = field(default_factory=dict)

    channel: str = ""
    params: SpatiusParams = field(default_factory=dict)

    dump: bool = False
    dump_path: str = ""

    def update_params(self) -> None:
        """Copy user-facing params into normalized config fields."""
        if "spatius_api_key" in self.params:
            self.spatius_api_key = self.params["spatius_api_key"]

        if "spatius_app_id" in self.params:
            self.spatius_app_id = self.params["spatius_app_id"]

        if "spatius_avatar_id" in self.params:
            self.spatius_avatar_id = self.params["spatius_avatar_id"]

        if "agora_uid" in self.params:
            self.agora_uid = self.params["agora_uid"]

        if "agora_token" in self.params:
            self.agora_token = self.params["agora_token"]

        if "agora_appid" in self.params:
            self.agora_appid = self.params["agora_appid"]

        if "agora_appcert" in self.params:
            self.agora_appcert = self.params["agora_appcert"]

        if "agora_channel" in self.params:
            self.agora_channel = self.params["agora_channel"]

        if self._has_value(self.channel):
            self.agora_channel = self.channel

        if "region" in self.params:
            self.region = self.params["region"]

        if "sample_rate" in self.params:
            self.sample_rate = int(self.params["sample_rate"])

        if "session_expire_minutes" in self.params:
            self.session_expire_minutes = int(
                self.params["session_expire_minutes"]
            )

        if "audio_format" in self.params:
            self.audio_format = self.params["audio_format"]

        if "extra_params" in self.params:
            # Copy to avoid aliasing the caller's dict.
            self.extra_params = dict(self.params["extra_params"])

    def validate_params(self) -> None:
        """Validate required configuration parameters."""
        required_fields = {
            "params.spatius_api_key": self.spatius_api_key,
            "params.spatius_app_id": self.spatius_app_id,
            "params.spatius_avatar_id": self.spatius_avatar_id,
            "params.agora_uid": self.agora_uid,
            "params.agora_appid": self.agora_appid,
            "params.agora_channel": self.agora_channel,
        }

        missing_fields = [
            k
            for k, v in required_fields.items()
            if not v or (isinstance(v, str) and not v.strip())
        ]
        if missing_fields:
            raise ValueError(
                f"Missing required fields: {', '.join(missing_fields)}"
            )

        if not self._has_value(self.agora_token) and not self._has_value(
            self.agora_appcert
        ):
            raise ValueError(
                "Either params.agora_token or params.agora_appcert "
                "must be provided"
            )

        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be greater than 0")

        try:
            self.audio_format = AudioFormat(self.audio_format).value
        except ValueError as exc:
            allowed = ", ".join(
                audio_format.value for audio_format in AudioFormat
            )
            raise ValueError(
                f"params.audio_format must be one of: {allowed}"
            ) from exc

        if (
            self.audio_format == AudioFormat.OGG_OPUS.value
            and self.sample_rate not in SUPPORTED_OPUS_SAMPLE_RATES
        ):
            supported_rates = ", ".join(
                str(rate) for rate in sorted(SUPPORTED_OPUS_SAMPLE_RATES)
            )
            raise ValueError(
                "Ogg Opus encoding supports sample rates: "
                f"{supported_rates} Hz; got {self.sample_rate} Hz"
            )

        if self.session_expire_minutes <= 0:
            raise ValueError("session_expire_minutes must be greater than 0")

        try:
            int(self.agora_uid)
        except ValueError as exc:
            raise ValueError("params.agora_uid must be an integer") from exc

    def resolve_agora_token(self) -> str:
        """Return configured Agora token or generate one from app cert."""
        if self._has_value(self.agora_token):
            return self.agora_token

        privilege_expired_ts = int(time()) + (self.session_expire_minutes * 60)
        return RtcTokenBuilder.buildTokenWithUid(
            self.agora_appid,
            self.agora_appcert,
            self.agora_channel,
            int(self.agora_uid),
            1,
            privilege_expired_ts,
        )

    @staticmethod
    def _has_value(value: str) -> bool:
        return bool(value and value.strip())


class SpatiusAvatarExtension(AsyncAvatarBaseExtension):
    """
    Spatius Avatar Extension.

    Implements 7 required methods from AsyncAvatarBaseExtension.
    All lifecycle management is handled by the base class.
    Uses spatius SDK for communication with Spatius avatar service.
    """

    def __init__(self, name: str):
        super().__init__(name)
        self.config: SpatiusConfig | None = None
        self.session = None
        self.ten_env: AsyncTenEnv | None = None
        self.connection_id = ""
        self.event_loop: asyncio.AbstractEventLoop | None = None

    def _on_frame_received(self, frame_data: bytes, is_last: bool) -> None:
        """Handle animation frames received from avatar service."""
        if self.ten_env:
            self.ten_env.log_debug(
                f"[Spatius] Frame received: {len(frame_data)} bytes, "
                f"is_last={is_last}"
            )

    def _on_error(self, error: Exception) -> None:
        """Handle errors from avatar service."""
        if self.ten_env:
            self.ten_env.log_error(f"[Spatius] Session error: {error}")
            if self.event_loop:
                self.event_loop.call_soon_threadsafe(
                    self._report_sdk_error,
                    error,
                )

    def _report_sdk_error(self, error: Exception) -> None:
        if not self.ten_env:
            return
        asyncio.create_task(
            self._send_error(
                self.ten_env,
                f"Spatius session error: {error}",
                code=-1,
                vendor_code=type(error).__name__,
                vendor_message=str(error),
            )
        )

    def _on_close(self) -> None:
        """Handle session close from avatar service."""
        if self.ten_env:
            self.ten_env.log_info("[Spatius] Session closed by server")

    # ========================================================================
    # REQUIRED METHODS - 7 methods to implement
    # ========================================================================

    async def validate_config(self, ten_env: AsyncTenEnv) -> bool:
        """Validate Spatius configuration."""
        try:
            self.event_loop = asyncio.get_running_loop()
            self.config = await SpatiusConfig.create_async(ten_env)
            self.ten_env = ten_env
            self.config.update_params()
            self.config.validate_params()

            ten_env.log_info(
                "config: [Spatius] "
                "api_key="
                f"{self._masked_api_key()}, "
                f"app_id={self.config.spatius_app_id}, "
                f"avatar_id={self.config.spatius_avatar_id}, "
                f"region={self._region() or '(auto)'}, "
                f"agora_uid={self.config.agora_uid}, "
                f"agora_token={self._masked_agora_token()}, "
                f"agora_appid={self.config.agora_appid}, "
                f"agora_appcert={self._masked_agora_appcert()}, "
                f"agora_channel={self.config.agora_channel}, "
                f"sample_rate={self.config.sample_rate}, "
                f"audio_format={self.config.audio_format}, "
                "session_expire_minutes="
                f"{self.config.session_expire_minutes}, "
                f"extra_params={sorted(self.config.extra_params)}"
            )
            return True

        except Exception as e:
            ten_env.log_error(f"[Spatius] Config validation failed: {e}")
            await self._send_error(
                ten_env,
                f"Spatius config validation failed: {e}",
                code=-1012,
                vendor_code=type(e).__name__,
                vendor_message=str(e),
            )
            return False

    def _masked_api_key(self) -> str:
        """Return a redacted Spatius API key for logs."""
        return self._encrypt_config_value(self.config.spatius_api_key)

    def _masked_agora_token(self) -> str:
        """Return a redacted Agora token for logs."""
        if not self.config.agora_token:
            return "(generated from app cert)"
        return self._encrypt_config_value(self.config.agora_token)

    def _masked_agora_appcert(self) -> str:
        """Return a redacted Agora app certificate for logs."""
        return self._encrypt_config_value(self.config.agora_appcert)

    @staticmethod
    def _encrypt_config_value(value: str) -> str:
        if not value:
            return "(empty)"
        return encrypt(value)

    def _region(self) -> str:
        """Return the configured Spatius region."""
        return (self.config.region or "").strip()

    def _reporting_region(self) -> str:
        """Return the SDK session's region when available."""
        if self.session is not None:
            return (self.session.config.region or "").strip()
        return self._region()

    def get_target_sample_rate(self) -> list[int]:
        """Return the configured sample rate expected by spatius SDK."""
        return [self.config.sample_rate]

    async def connect_to_avatar(self, ten_env: AsyncTenEnv) -> None:
        """Connect to Spatius avatar service using spatius SDK."""
        ten_env.log_info(
            f"[Spatius] Connecting (avatar_id={self.config.spatius_avatar_id})"
        )

        # Create avatar session using spatius with Agora egress.
        avatar_uid = int(self.config.agora_uid)
        agora_token = self.config.resolve_agora_token()
        agora_egress = AgoraEgressConfig(
            channel_name=self.config.agora_channel,
            token=agora_token,
            uid=avatar_uid,
            publisher_id=self.config.agora_uid,
        )

        session_kwargs = {
            "api_key": self.config.spatius_api_key,
            "app_id": self.config.spatius_app_id,
            "avatar_id": self.config.spatius_avatar_id,
            "expire_at": datetime.now(timezone.utc)
            + timedelta(minutes=self.config.session_expire_minutes),
            "sample_rate": self.config.sample_rate,
            "audio_format": AudioFormat(self.config.audio_format),
            "ogg_opus_encoder": self._ogg_opus_encoder_config(),
            "agora_egress": agora_egress,
            "extra_params": dict(self.config.extra_params),
            "transport_frames": self._on_frame_received,
            "on_error": self._on_error,
            "on_close": self._on_close,
        }
        region = self._region()
        if region:
            session_kwargs["region"] = region

        self.session = new_avatar_session(**session_kwargs)

        # Initialize session (obtains authentication token)
        await self.session.init()

        # Establish WebSocket connection
        connection_id = await self.session.start()
        self.connection_id = str(connection_id)
        ten_env.log_info(
            f"[Spatius] Connected successfully (connection_id={connection_id}, "
            f"region={self._reporting_region()})"
        )

    def _ogg_opus_encoder_config(self) -> OggOpusEncoderConfig | None:
        """Return encoder config when Opus audio is enabled."""
        if self.config.audio_format != AudioFormat.OGG_OPUS.value:
            return None
        return OggOpusEncoderConfig()

    async def disconnect_from_avatar(self, ten_env: AsyncTenEnv) -> None:
        """Disconnect from Spatius avatar service."""
        if self.session:
            try:
                await self.session.close()
            except Exception as e:
                ten_env.log_warn(f"[Spatius] Error during disconnect: {e}")
            finally:
                self.session = None
                self.connection_id = ""

        ten_env.log_info("[Spatius] Disconnected")

    async def send_audio_to_avatar(self, audio_data: bytes) -> None:
        """Send audio to Spatius"""
        if self.session:
            if self.ten_env:
                self.ten_env.log_debug(
                    f"[Spatius] Sending audio: {len(audio_data)} bytes"
                )
            await self.session.send_audio(bytes(audio_data), end=False)

    async def send_eof_to_avatar(self) -> None:
        """Send EOF marker to Spatius avatar to signal end of audio stream."""
        if self.session:
            if self.ten_env:
                self.ten_env.log_info("[Spatius] Sending EOF")
            await self.session.send_audio(b"", end=True)

    async def interrupt_avatar(self) -> None:
        """Interrupt current Spatius avatar processing."""
        if self.session:
            if self.ten_env:
                self.ten_env.log_info("[Spatius] Interrupting avatar")
            try:
                await self.session.interrupt()
            except Exception as e:
                if self.ten_env:
                    self.ten_env.log_warn(f"[Spatius] Interrupt failed: {e}")

    # ========================================================================
    # OPTIONAL METHODS
    # ========================================================================

    def get_dump_config(self) -> tuple[bool, str]:
        """Return audio dump configuration from config."""
        if self.config:
            return (self.config.dump, self.config.dump_path)
        return (False, "")

    def get_vendor_name(self) -> str:
        return "spatius"

    def get_reporting_session_id(self) -> str:
        return self.config.agora_uid if self.config else ""

    def get_vendor_metadata(self) -> dict:
        if not self.config:
            return {"name": "spatius"}
        vendor_metadata = {
            "name": "spatius",
            "key": (
                encrypt(self.config.spatius_api_key)
                if self.config.spatius_api_key
                else ""
            ),
            "model": self.config.spatius_avatar_id,
            "region": self._reporting_region(),
            "mode": self.config.audio_format,
            "avatar_id": self.config.spatius_avatar_id,
            "avatar_session_id": self.connection_id,
            "app_id": self.config.spatius_app_id,
        }
        return {
            key: value
            for key, value in vendor_metadata.items()
            if value not in ("", None)
        }

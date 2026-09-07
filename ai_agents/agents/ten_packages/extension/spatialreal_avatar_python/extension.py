#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import time

from ten_runtime import AsyncTenEnv
from ten_ai_base.config import BaseConfig
from avatarkit import new_avatar_session, AgoraEgressConfig

from .avatar_base import AsyncAvatarBaseExtension
from .agora_token_builder.RtcTokenBuilder2 import (
    Role_Publisher,
    RtcTokenBuilder,
)


@dataclass
class SpatialRealConfig(BaseConfig):
    """Configuration for SpatialReal Avatar Extension."""

    spatialreal_api_key: str = ""
    spatialreal_app_id: str = ""
    spatialreal_avatar_id: str = ""
    spatialreal_console_endpoint_url: str = (
        "https://console.us-west.spatialwalk.cloud/v1/console"
    )
    spatialreal_ingress_endpoint_url: str = (
        "https://api.us-west.spatialwalk.cloud/v2/driveningress"
    )
    agora_avatar_uid: str = ""
    agora_token: str = ""
    agora_appid: str = ""
    agora_app_certificate: str = ""
    channel: str = ""
    sample_rate: int = 16000
    session_expire_minutes: int = 30
    dump: bool = False
    dump_path: str = ""


class SpatialRealAvatarExtension(AsyncAvatarBaseExtension):
    """
    SpatialReal Avatar Extension.

    Implements 7 required methods from AsyncAvatarBaseExtension.
    All lifecycle management is handled by the base class.
    Uses avatarkit SDK for communication with SpatialReal avatar service.
    """

    def __init__(self, name: str):
        super().__init__(name)
        self.config: SpatialRealConfig | None = None
        self.session = None
        self.ten_env: AsyncTenEnv | None = None

    def _on_frame_received(self, frame_data: bytes, is_last: bool) -> None:
        """Handle animation frames received from avatar service."""
        if self.ten_env:
            self.ten_env.log_debug(
                f"[SpatialReal] Frame received: {len(frame_data)} bytes, is_last={is_last}"
            )

    def _on_error(self, error: Exception) -> None:
        """Handle errors from avatar service."""
        if self.ten_env:
            self.ten_env.log_error(f"[SpatialReal] Session error: {error}")

    def _on_close(self) -> None:
        """Handle session close from avatar service."""
        if self.ten_env:
            self.ten_env.log_info("[SpatialReal] Session closed by server")

    # ========================================================================
    # REQUIRED METHODS - 7 methods to implement
    # ========================================================================

    async def validate_config(self, ten_env: AsyncTenEnv) -> bool:
        """Validate SpatialReal configuration."""
        try:
            self.config = await SpatialRealConfig.create_async(ten_env)
            self.ten_env = ten_env

            # Validate required fields
            required_fields = {
                "spatialreal_api_key": self.config.spatialreal_api_key,
                "spatialreal_app_id": self.config.spatialreal_app_id,
                "spatialreal_avatar_id": self.config.spatialreal_avatar_id,
                "spatialreal_console_endpoint_url": self.config.spatialreal_console_endpoint_url,
                "spatialreal_ingress_endpoint_url": self.config.spatialreal_ingress_endpoint_url,
                "agora_avatar_uid": self.config.agora_avatar_uid,
            }

            missing_fields = [k for k, v in required_fields.items() if not v]
            if missing_fields:
                ten_env.log_error(
                    f"[SpatialReal] Missing required fields: {', '.join(missing_fields)}"
                )
                return False

            ten_env.log_info(
                f"[SpatialReal] Config loaded: "
                f"api_key={'***' + self.config.spatialreal_api_key[-4:] if len(self.config.spatialreal_api_key) > 4 else '(short)'}, "
                f"app_id={self.config.spatialreal_app_id}, "
                f"avatar_id={self.config.spatialreal_avatar_id}, "
                f"console_url={self.config.spatialreal_console_endpoint_url}, "
                f"ingress_url={self.config.spatialreal_ingress_endpoint_url}, "
                f"agora_avatar_uid={self.config.agora_avatar_uid}, "
                f"agora_appid={self.config.agora_appid}, "
                f"channel={self.config.channel}, "
                f"sample_rate={self.config.sample_rate}, "
                f"session_expire_minutes={self.config.session_expire_minutes}"
            )
            return True

        except Exception as e:
            ten_env.log_error(f"[SpatialReal] Config validation failed: {e}")
            return False

    def get_target_sample_rate(self) -> list[int]:
        """Return supported sample rates for avatarkit SDK."""
        return [8000, 16000, 22050, 24000, 32000, 44100, 48000]

    async def connect_to_avatar(self, ten_env: AsyncTenEnv) -> None:
        """Connect to SpatialReal avatar service using avatarkit SDK."""
        ten_env.log_info(
            f"[SpatialReal] Connecting (avatar_id={self.config.spatialreal_avatar_id})"
        )

        self.config.agora_token = RtcTokenBuilder.build_token_with_user_account(
            self.config.agora_appid,
            self.config.agora_app_certificate,
            self.config.channel,
            self.config.agora_avatar_uid,
            Role_Publisher,
            600,
            600,
        )

        ten_env.log_info(
            f"[SpatialReal] Agora token: {self.config.agora_token}"
        )

        # Create avatar session using avatarkit with Agora egress
        agora_egress = AgoraEgressConfig(
            channel_name=self.config.channel,
            token=self.config.agora_token,
            uid=int(self.config.agora_avatar_uid),
            publisher_id=self.config.agora_avatar_uid,
        )

        self.session = new_avatar_session(
            api_key=self.config.spatialreal_api_key,
            app_id=self.config.spatialreal_app_id,
            avatar_id=self.config.spatialreal_avatar_id,
            console_endpoint_url=self.config.spatialreal_console_endpoint_url,
            ingress_endpoint_url=self.config.spatialreal_ingress_endpoint_url,
            expire_at=datetime.now(timezone.utc)
            + timedelta(minutes=self.config.session_expire_minutes),
            agora_egress=agora_egress,
            transport_frames=self._on_frame_received,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        # Initialize session (obtains authentication token)
        await self.session.init()

        # Establish WebSocket connection
        connection_id = await self.session.start()
        ten_env.log_info(
            f"[SpatialReal] Connected successfully (connection_id={connection_id})"
        )

    async def disconnect_from_avatar(self, ten_env: AsyncTenEnv) -> None:
        """Disconnect from SpatialReal avatar service."""
        if self.session:
            try:
                await self.session.close()
            except Exception as e:
                ten_env.log_warn(f"[SpatialReal] Error during disconnect: {e}")
            finally:
                self.session = None

        ten_env.log_info("[SpatialReal] Disconnected")

    async def send_audio_to_avatar(self, audio_data: bytes) -> None:
        """Send audio to SpatialReal"""
        if self.session:
            if self.ten_env:
                self.ten_env.log_debug(
                    f"[SpatialReal] Sending audio: {len(audio_data)} bytes"
                )
            await self.session.send_audio(bytes(audio_data), end=False)

    async def send_eof_to_avatar(self) -> None:
        """Send EOF marker to SpatialReal avatar to signal end of audio stream."""
        if self.session:
            if self.ten_env:
                self.ten_env.log_info("[SpatialReal] Sending EOF")
            await self.session.send_audio(b"", end=True)

    async def interrupt_avatar(self) -> None:
        """Interrupt current SpatialReal avatar processing."""
        if self.session:
            if self.ten_env:
                self.ten_env.log_info("[SpatialReal] Interrupting avatar")
            try:
                await self.session.interrupt()
            except Exception as e:
                if self.ten_env:
                    self.ten_env.log_warn(
                        f"[SpatialReal] Interrupt failed: {e}"
                    )

    # ========================================================================
    # OPTIONAL METHODS
    # ========================================================================

    def get_dump_config(self) -> tuple[bool, str]:
        """Return audio dump configuration from config."""
        if self.config:
            return (self.config.dump, self.config.dump_path)
        return (False, "")

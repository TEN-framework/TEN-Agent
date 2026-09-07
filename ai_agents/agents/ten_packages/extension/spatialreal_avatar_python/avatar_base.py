#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""
Avatar Base Extension for TEN Framework

This module provides a base class for implementing avatar/digital human extensions.
The base class handles ALL lifecycle management - you only implement 7 business methods.

Quick Start - Implement These 7 Methods:
========================================

```python
from avatar_base import AsyncAvatarBaseExtension

class MyAvatarExtension(AsyncAvatarBaseExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.config = None
        self.client = None

    # 1. Validate configuration
    async def validate_config(self, ten_env) -> bool:
        self.config = await MyConfig.create_async(ten_env)
        return bool(self.config.api_key)

    # 2. Target sample rate
    def get_target_sample_rate(self) -> list[int]:
        return [24000]  # Avatar service needs 24kHz

    # 3. Connect to service
    async def connect_to_avatar(self, ten_env) -> None:
        self.client = MyAvatarClient(self.config)
        await self.client.connect()

    # 4. Disconnect from service
    async def disconnect_from_avatar(self, ten_env) -> None:
        if self.client:
            await self.client.disconnect()

    # 5. Send audio (no resampling - sent as-is)
    async def send_audio_to_avatar(self, audio_data: bytes) -> None:
        await self.client.send_audio(audio_data)

    # 6. End of stream (called automatically by base class)
    async def send_eof_to_avatar(self) -> None:
        await self.client.send_eof()

    # 7. Interrupt
    async def interrupt_avatar(self) -> None:
        await self.client.interrupt()

    # OPTIONAL: Enable audio dumping for debugging
    def get_dump_config(self) -> tuple[bool, str]:
        return (self.config.dump, self.config.dump_path)
```

That's it! The base class handles everything else:
- Audio queue management
- Audio processing loop
- Sample rate validation
- Audio dumping (if enabled)
- Command handling (flush)
- Lifecycle management
- Error handling

Lifecycle (Automatic):
=====================
1. on_init() → calls validate_config()
2. on_start() → calls connect_to_avatar() → starts audio loop
3. Audio arrives → sample rate checked → queued → calls send_audio_to_avatar()
4. flush command → calls interrupt_avatar()
5. tts_audio_end event → calls send_eof_to_avatar() (if reason=1)
6. on_stop() → calls disconnect_from_avatar() → cleanup

You don't need to override on_init/on_start/on_stop!
"""

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
import os

from ten_runtime import (
    AsyncExtension,
    AsyncTenEnv,
    AudioFrame,
    Cmd,
    CmdResult,
    Data,
    StatusCode,
    VideoFrame,
)

from ten_ai_base.const import (
    CMD_IN_FLUSH,
    CMD_OUT_FLUSH,
    LOG_CATEGORY_KEY_POINT,
)
from ten_ai_base.message import ErrorMessage, ModuleType

# Avatar-specific constants
MODULE_TYPE_AVATAR = "avatar"


@dataclass
class AudioQueueItem:
    kind: str  # "audio" | "eof"
    audio_data: bytes | None = None
    request_id: str = ""


class AsyncAvatarBaseExtension(AsyncExtension, ABC):
    """
    Base class for Avatar Extensions.

    Handles all lifecycle management automatically.
    Subclasses only need to implement 7 business methods.
    """

    # Log prefix for all avatar extensions
    LOG_PREFIX = "[SpatialReal]"

    def __init__(self, name: str):
        super().__init__(name)
        self.ten_env: AsyncTenEnv | None = None

        # Internal state (managed by base class)
        self._audio_processing_enabled = False
        self._config_valid = False
        self._in_audio_queue: asyncio.Queue[AudioQueueItem] = asyncio.Queue()
        self._audio_task: asyncio.Task | None = None
        self._sample_rate_error_sent = False

    # ========================================================================
    # REQUIRED METHODS - Implement these 6 methods in your subclass
    # ========================================================================

    @abstractmethod
    def get_target_sample_rate(self) -> list[int]:
        """
        [REQUIRED] Return target sample rates for avatar service.

        This tells the base class what sample rates your avatar service supports.
        Audio with unsupported sample rates will be rejected with an error.
        Returns a list of supported sample rates in Hz.

        Examples:
            def get_target_sample_rate(self) -> list[int]:
                return [24000]  # HeyGen/Anam support 24kHz
                return [16000]  # Sensetime supports 16kHz
                return [24000, 48000]  # Multiple sample rates supported
                return [self.config.sample_rate]  # Akool uses config
        """
        raise NotImplementedError()

    @abstractmethod
    async def validate_config(self, ten_env: AsyncTenEnv) -> bool:
        """
        [REQUIRED] Validate your configuration.

        Called automatically during initialization.
        Load and validate your configuration here.

        Returns:
            True if valid, False otherwise

        Example:
            async def validate_config(self, ten_env) -> bool:
                self.config = await MyConfig.create_async(ten_env)
                if not self.config.api_key:
                    ten_env.log_error("api_key required")
                    return False
                return True
        """
        raise NotImplementedError()

    @abstractmethod
    async def connect_to_avatar(self, ten_env: AsyncTenEnv) -> None:
        """
        [REQUIRED] Connect to your avatar service.

        Called automatically after successful config validation.
        Create your client and establish connection here.

        Example:
            async def connect_to_avatar(self, ten_env) -> None:
                self.client = MyAvatarClient(self.config)
                await self.client.connect()
                ten_env.log_info("Connected")
        """
        raise NotImplementedError()

    @abstractmethod
    async def disconnect_from_avatar(self, ten_env: AsyncTenEnv) -> None:
        """
        [REQUIRED] Disconnect from your avatar service.

        Called automatically during shutdown.
        Clean up resources here.

        Example:
            async def disconnect_from_avatar(self, ten_env) -> None:
                if self.client:
                    await self.client.disconnect()
                    ten_env.log_info("Disconnected")
        """
        raise NotImplementedError()

    @abstractmethod
    async def send_audio_to_avatar(self, audio_data: bytes) -> None:
        """
        [REQUIRED] Send audio data to your avatar service.

        Called automatically by audio processing loop.
        Audio data is sent as-is without resampling.

        Args:
            audio_data: Raw PCM audio bytes

        Example:
            async def send_audio_to_avatar(self, audio_data: bytes) -> None:
                base64_audio = base64.b64encode(audio_data).decode("utf-8")
                await self.client.send_audio(base64_audio)
        """
        raise NotImplementedError()

    @abstractmethod
    async def send_eof_to_avatar(self) -> None:
        """
        [REQUIRED] Signal end of audio stream.

        Called automatically in two scenarios:
        1. When drain command is received (manual trigger)
        2. When tts_audio_end event arrives with reason=1 (TTS completion)

        Example:
            async def send_eof_to_avatar(self) -> None:
                await self.client.send_eof()
        """
        raise NotImplementedError()

    @abstractmethod
    async def interrupt_avatar(self) -> None:
        """
        [REQUIRED] Interrupt avatar immediately.

        Called when flush command is received.

        Example:
            async def interrupt_avatar(self) -> None:
                if self.client:
                    await self.client.interrupt()
        """
        raise NotImplementedError()

    def get_dump_config(self) -> tuple[bool, str]:
        """
        [OPTIONAL] Return audio dump configuration.

        Override this method to enable audio dumping for debugging.
        Returns a tuple of (should_dump, dump_path).

        Returns:
            tuple[bool, str]: (should_dump, dump_path)
                - should_dump: Whether to dump audio data to file
                - dump_path: Directory path where audio files will be saved

        Default:
            Returns (False, "") - no dumping

        Example:
            def get_dump_config(self) -> tuple[bool, str]:
                return (True, "/tmp/audio_dump")  # Enable dumping
                return (self.config.dump, self.config.dump_path)  # From config
                return (False, "")  # Disable dumping (default)
        """
        return (False, "")

    # ========================================================================
    # LIFECYCLE METHODS - Managed by base class, DO NOT override
    # ========================================================================

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        """Initialize extension and validate config."""
        ten_env.log_info(f"{self.LOG_PREFIX} on_init started")
        await super().on_init(ten_env)
        self.ten_env = ten_env

        # Validate configuration
        ten_env.log_info(f"{self.LOG_PREFIX} Validating configuration...")
        config_valid = await self.validate_config(ten_env)
        self._audio_processing_enabled = config_valid
        self._config_valid = config_valid

        if not config_valid:
            ten_env.log_error(
                f"{self.LOG_PREFIX} Configuration validation failed"
            )
        else:
            ten_env.log_info(
                f"{self.LOG_PREFIX} Configuration validated successfully"
            )

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        """Start extension, connect to avatar, and start audio processing."""
        ten_env.log_info(f"{self.LOG_PREFIX} on_start started")
        await super().on_start(ten_env)

        if not self._config_valid:
            ten_env.log_warn(
                f"{self.LOG_PREFIX} Skipping connection due to invalid configuration"
            )
            return

        # Connect to avatar service
        ten_env.log_info(f"{self.LOG_PREFIX} Connecting to avatar service...")
        try:
            await self.connect_to_avatar(ten_env)
        except Exception as e:
            ten_env.log_error(f"{self.LOG_PREFIX} Failed to connect: {e}")
            raise

        # Start audio processing loop
        ten_env.log_info(f"{self.LOG_PREFIX} Starting audio processing loop...")
        self._audio_task = asyncio.create_task(
            self._process_audio_loop(ten_env)
        )
        ten_env.log_info(f"{self.LOG_PREFIX} Started successfully")

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        """Stop extension, disconnect from avatar, and cleanup."""
        ten_env.log_info(f"{self.LOG_PREFIX} on_stop started")
        self._audio_processing_enabled = False

        # Cancel audio processing task
        if self._audio_task and not self._audio_task.done():
            ten_env.log_info(
                f"{self.LOG_PREFIX} Cancelling audio processing task..."
            )
            self._audio_task.cancel()
            try:
                await self._audio_task
            except asyncio.CancelledError:
                pass
            ten_env.log_info(
                f"{self.LOG_PREFIX} Audio processing task cancelled"
            )

        # Disconnect from avatar service
        ten_env.log_info(
            f"{self.LOG_PREFIX} Disconnecting from avatar service..."
        )
        try:
            await self.disconnect_from_avatar(ten_env)
        except Exception as e:
            ten_env.log_error(f"{self.LOG_PREFIX} Error disconnecting: {e}")

        await super().on_stop(ten_env)
        ten_env.log_info(f"{self.LOG_PREFIX} Stopped successfully")

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        """Deinitialize extension."""
        ten_env.log_info(f"{self.LOG_PREFIX} on_deinit started")
        await super().on_deinit(ten_env)
        ten_env.log_info(f"{self.LOG_PREFIX} Deinitialized")

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        """Handle incoming commands."""
        cmd_name = cmd.get_name()
        ten_env.log_info(f"{self.LOG_PREFIX} on_cmd received: {cmd_name}")

        if cmd_name == CMD_IN_FLUSH:
            ten_env.log_info(
                f"KEYPOINT [on_cmd:{CMD_IN_FLUSH}]",
                category=LOG_CATEGORY_KEY_POINT,
            )
            await self._handle_flush(ten_env)
            await ten_env.send_cmd(Cmd.create(CMD_OUT_FLUSH))

        cmd_result = CmdResult.create(StatusCode.OK, cmd)
        await ten_env.return_result(cmd_result)
        ten_env.log_info(f"{self.LOG_PREFIX} on_cmd completed: {cmd_name}")

    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        """Handle incoming data events."""
        data_name = data.get_name()
        ten_env.log_info(f"{self.LOG_PREFIX} on_data received: {data_name}")

        if data_name == "tts_audio_end":
            json_str, _ = data.get_property_to_json(None)
            if json_str:
                payload = json.loads(json_str)
                reason = payload.get("reason")
                request_id = payload.get("request_id", "unknown")
                ten_env.log_info(
                    f"{self.LOG_PREFIX} tts_audio_end: reason={reason}, request_id={request_id}"
                )

                # reason=1 means TTS generation complete
                if reason == 1:
                    ten_env.log_info(
                        f"{self.LOG_PREFIX} TTS complete (request_id={request_id}), queueing EOF marker"
                    )
                    await self._on_tts_audio_end(ten_env, request_id)

    # ========================================================================
    # AUDIO HANDLING - Managed by base class
    # ========================================================================

    async def on_audio_frame(
        self, ten_env: AsyncTenEnv, audio_frame: AudioFrame
    ) -> None:
        """Handle incoming audio frames."""
        if not self._audio_processing_enabled:
            ten_env.log_info(
                f"{self.LOG_PREFIX} on_audio_frame: Audio processing disabled, skipping frame"
            )
            return

        # Get audio info
        source_rate = audio_frame.get_sample_rate()
        audio_data = audio_frame.get_buf()

        if not audio_data:
            ten_env.log_warn(f"{self.LOG_PREFIX} Empty audio frame")
            return

        ten_env.log_info(
            f"{self.LOG_PREFIX} on_audio_frame: {len(audio_data)} bytes, sample_rate={source_rate}"
        )

        # Get supported sample rates
        supported_rates = self.get_target_sample_rate()

        # Check if sample rate is supported
        if source_rate not in supported_rates:
            if not self._sample_rate_error_sent:
                error_msg = (
                    f"Unsupported sample rate {source_rate}Hz. "
                    f"Supported rates: {supported_rates}"
                )
                ten_env.log_error(f"{self.LOG_PREFIX} {error_msg}")
                await self._send_error(ten_env, error_msg, code=1001)
                self._sample_rate_error_sent = True
            return

        # Queue audio data
        try:
            self._dump_audio(audio_data, "in")
            queue_size = self._in_audio_queue.qsize()
            self._in_audio_queue.put_nowait(
                AudioQueueItem(kind="audio", audio_data=bytes(audio_data))
            )
            ten_env.log_info(
                f"{self.LOG_PREFIX} Queued audio: {len(audio_data)} bytes, queue_size={queue_size + 1}"
            )
        except Exception as e:
            ten_env.log_warn(f"{self.LOG_PREFIX} Error queuing audio: {e}")

    async def _process_audio_loop(self, ten_env: AsyncTenEnv) -> None:
        """Audio processing loop - calls send_audio_to_avatar()."""
        ten_env.log_info(f"{self.LOG_PREFIX} Audio processing loop started")
        while self._audio_processing_enabled:
            try:
                queue_item = await self._in_audio_queue.get()

                if queue_item.kind == "audio":
                    audio_data = queue_item.audio_data or b""
                    ten_env.log_info(
                        f"{self.LOG_PREFIX} Processing audio from queue: {len(audio_data)} bytes, calling send_audio_to_avatar"
                    )
                    await self.send_audio_to_avatar(audio_data)
                    ten_env.log_info(
                        f"{self.LOG_PREFIX} send_audio_to_avatar completed"
                    )
                elif queue_item.kind == "eof":
                    ten_env.log_info(
                        f"{self.LOG_PREFIX} Processing EOF marker from queue (request_id={queue_item.request_id})"
                    )
                    await self.send_eof_to_avatar()
                    ten_env.log_info(
                        f"{self.LOG_PREFIX} EOF sent successfully (request_id={queue_item.request_id})"
                    )
                else:
                    ten_env.log_warn(
                        f"{self.LOG_PREFIX} Unknown queue item kind: {queue_item.kind}"
                    )
            except asyncio.CancelledError:
                ten_env.log_info(
                    f"{self.LOG_PREFIX} Audio processing loop cancelled"
                )
                break
            except Exception as e:
                ten_env.log_error(
                    f"{self.LOG_PREFIX} Error in audio processing: {e}"
                )
        ten_env.log_info(f"{self.LOG_PREFIX} Audio processing loop ended")

    # ========================================================================
    # INTERNAL METHODS
    # ========================================================================

    async def _handle_flush(self, ten_env: AsyncTenEnv) -> None:
        """Handle flush command."""
        ten_env.log_info(
            f"{self.LOG_PREFIX} Handling flush - clearing queue and interrupting"
        )

        # Clear audio queue
        await self._clear_audio_queue()

        # Interrupt avatar
        ten_env.log_info(f"{self.LOG_PREFIX} Calling interrupt_avatar...")
        try:
            await self.interrupt_avatar()
            ten_env.log_info(f"{self.LOG_PREFIX} Flush completed successfully")
        except Exception as e:
            ten_env.log_error(f"{self.LOG_PREFIX} Error interrupting: {e}")

    async def _on_tts_audio_end(
        self, ten_env: AsyncTenEnv, request_id: str = "unknown"
    ) -> None:
        """Handle tts_audio_end event."""
        if not self._audio_processing_enabled:
            ten_env.log_info(
                f"{self.LOG_PREFIX} Audio processing disabled, skipping EOF"
            )
            return

        ten_env.log_info(
            f"{self.LOG_PREFIX} Queueing EOF marker for request_id={request_id}"
        )
        try:
            queue_size = self._in_audio_queue.qsize()
            self._in_audio_queue.put_nowait(
                AudioQueueItem(kind="eof", request_id=request_id)
            )
            ten_env.log_info(
                f"{self.LOG_PREFIX} EOF marker queued (request_id={request_id}), queue_size={queue_size + 1}"
            )
        except Exception as e:
            ten_env.log_error(
                f"{self.LOG_PREFIX} Error queueing EOF marker: {e}"
            )

    async def _clear_audio_queue(self) -> None:
        """Clear all audio frames from queue."""
        cleared = 0
        while not self._in_audio_queue.empty():
            try:
                self._in_audio_queue.get_nowait()
                cleared += 1
            except asyncio.QueueEmpty:
                break

        if self.ten_env:
            self.ten_env.log_info(
                f"{self.LOG_PREFIX} Cleared {cleared} queued items (audio/eof) from queue"
            )

    async def _send_error(
        self, ten_env: AsyncTenEnv, message: str, code: int = 0
    ) -> None:
        """Send error message."""
        ten_env.log_error(
            f"{self.LOG_PREFIX} Sending error: code={code}, message={message}"
        )

        data = Data.create("message")
        data.set_property_from_json(
            "",
            ErrorMessage(
                module=ModuleType.AVATAR.value,
                message=message,
                code=code,
            ).model_dump_json(),
        )
        await ten_env.send_data(data)
        ten_env.log_info(f"{self.LOG_PREFIX} Error message sent")

    def _dump_audio(self, buf: bytes, suffix: str) -> None:
        """Dump audio data to file if enabled."""
        should_dump, dump_path = self.get_dump_config()

        if not should_dump or not dump_path:
            return

        # Ensure dump directory exists
        os.makedirs(dump_path, exist_ok=True)

        dump_file = os.path.join(dump_path, f"{self.name}_{suffix}.pcm")
        with open(dump_file, "ab") as f:
            f.write(buf)

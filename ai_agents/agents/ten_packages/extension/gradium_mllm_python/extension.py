"""
Gradium real-time speech-to-speech translation extension for TEN.

Wires Gradium's websocket S2S Translation API (see client.py/config.py) into
TEN's AsyncMLLMBaseExtension contract -- the same base class
openai_mllm_python/glm_mllm_python/gemini_mllm_python/etc. use, so this
extension can be dropped into any graph node expecting an "mllm" addon
(e.g. the "v2v" node in the voice-assistant-realtime example graph).

See README.md for what's confirmed vs. still assumed about Gradium's
protocol.
"""

import asyncio
import base64
import traceback

from ten_ai_base.message import ModuleError, ModuleErrorCode, ModuleErrorVendorInfo
from ten_ai_base.mllm import AsyncMLLMBaseExtension
from ten_ai_base.struct import (
    MLLMClientFunctionCallOutput,
    MLLMClientMessageItem,
    MLLMServerOutputTranscript,
    MLLMServerSessionReady,
)
from ten_ai_base.types import LLMToolMetadata
from ten_runtime import AsyncTenEnv, AudioFrame

from .client import GradiumS2SClient
from .config import GradiumMLLMConfig
from .const import (
    GRADIUM_INPUT_SAMPLE_RATE,
    MODULE_NAME_MLLM,
    WS_MSG_TYPE_AUDIO,
    WS_MSG_TYPE_ERROR,
    WS_MSG_TYPE_TEXT,
)


class GradiumMLLMExtension(AsyncMLLMBaseExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.ten_env: AsyncTenEnv | None = None
        self.config: GradiumMLLMConfig | None = None
        self.client: GradiumS2SClient | None = None

        self.stopped: bool = False
        self.connected: bool = False

        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5

        self._response_transcript = ""
        self._receive_task: asyncio.Task | None = None

    # ---------- lifecycle ----------

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        self.ten_env = ten_env

        try:
            properties, _ = await ten_env.get_property_to_json(None)
            self.config = GradiumMLLMConfig.model_validate_json(properties)
            ten_env.log_info(
                f"[gradium] config: {self.config.model_dump(exclude={'api_key'})}"
            )

            if not self.config.api_key:
                raise ValueError("api_key is required")
            if not self.config.voice_id:
                # No default is safe to assume here: Gradium requires
                # voice_id to belong to target_language, and we don't have a
                # voice catalog to validate against. Fail loudly instead of
                # silently pairing a possibly-wrong-language voice.
                raise ValueError(
                    "voice_id is required and must be a voice belonging to "
                    f"target_language={self.config.target_language!r}"
                )
        except Exception as e:
            # Report via TEN's error channel rather than letting on_init
            # raise -- mirrors gradium_tts_python's on_init, and keeps a
            # fixable config mistake from crashing the whole extension
            # process instead of surfacing as a normal `error` Data event.
            ten_env.log_error(f"[gradium] on_init failed: {e}")
            await self.send_mllm_error(
                ModuleError(
                    module=MODULE_NAME_MLLM,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(e),
                ),
                ModuleErrorVendorInfo(vendor=self.vendor(), message=str(e)),
            )

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        # Set before super().on_stop() (which triggers stop_connection())
        # so an in-flight reconnect loop sees `stopped` immediately instead
        # of racing to reconnect once more before noticing.
        self.stopped = True
        await super().on_stop(ten_env)

    def vendor(self) -> str:
        return "gradium"

    def input_audio_sample_rate(self) -> int:
        return (
            self.config.input_sample_rate
            if self.config
            else GRADIUM_INPUT_SAMPLE_RATE
        )

    def synthesize_audio_sample_rate(self) -> int:
        return self.config.output_sample_rate() if self.config else 48000

    # ---------- connection ----------

    async def start_connection(self) -> None:
        # AsyncMLLMBaseExtension.on_start() does `await self.start_connection()`
        # directly -- if this coroutine blocked here for the life of the
        # connection (as openai_mllm_python/glm_mllm_python's do), on_start()
        # would never complete, and the framework would never advance this
        # extension to on_stop(), deadlocking clean shutdown. Match
        # gradium_asr_python's pattern instead: connect, then hand the
        # message loop off to a background task and return promptly.
        assert self.config is not None
        if not self.config.api_key or not self.config.voice_id:
            # on_init already reported this as a fatal error; don't also
            # attempt (and fail) a connection with known-invalid config.
            return
        try:
            self.client = GradiumS2SClient(self.config, self.ten_env)
            await self.client.connect()
            self.connected = True
            self._reconnect_attempts = 0
            self.ten_env.log_info("[gradium] session ready")
            await self.send_server_session_ready(MLLMServerSessionReady())

            self._receive_task = asyncio.create_task(self._receive_loop())
        except Exception as e:
            traceback.print_exc()
            self.ten_env.log_error(f"[gradium] start_connection failed: {e}")
            await self.send_mllm_error(
                ModuleError(
                    module=MODULE_NAME_MLLM,
                    code=ModuleErrorCode.FATAL_ERROR.value,
                    message=str(e),
                ),
                ModuleErrorVendorInfo(vendor=self.vendor(), message=str(e)),
            )
            self.connected = False
            await self._maybe_reconnect()

    async def _receive_loop(self) -> None:
        try:
            async for message in self.client.messages():
                try:
                    await self._handle_server_message(message)
                except Exception as e:
                    traceback.print_exc()
                    self.ten_env.log_error(
                        f"[gradium] error processing message {message}: {e}"
                    )

            self.ten_env.log_info("[gradium] receive loop finished")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            traceback.print_exc()
            self.ten_env.log_error(f"[gradium] receive loop failed: {e}")

        self.connected = False
        await self._maybe_reconnect()

    async def _handle_server_message(self, message: dict) -> None:
        msg_type = message.get("type")

        if msg_type == WS_MSG_TYPE_TEXT:
            text = message.get("text", "")
            final = bool(message.get("final", False))
            self._response_transcript = (
                text if final else self._response_transcript + text
            )
            await self.send_server_output_text(
                MLLMServerOutputTranscript(
                    content=self._response_transcript,
                    delta=text,
                    final=final,
                    metadata={"session_id": self.session_id or "-1"},
                )
            )
            if final:
                self._response_transcript = ""

        elif msg_type == WS_MSG_TYPE_AUDIO:
            audio_b64 = message.get("audio")
            if audio_b64:
                await self.send_server_output_audio_data(
                    base64.b64decode(audio_b64)
                )

        elif msg_type == WS_MSG_TYPE_ERROR:
            err_msg = message.get("message", "Gradium error")
            self.ten_env.log_error(f"[gradium] server error: {err_msg}")
            await self.send_mllm_error(
                ModuleError(
                    module=MODULE_NAME_MLLM,
                    code=ModuleErrorCode.NON_FATAL_ERROR.value,
                    message=err_msg,
                ),
                ModuleErrorVendorInfo(
                    vendor=self.vendor(),
                    code=str(message.get("code", "")),
                    message=err_msg,
                ),
            )

        else:
            self.ten_env.log_debug(f"[gradium] unhandled message: {message}")

    async def stop_connection(self) -> None:
        self.connected = False
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None
        if self.client:
            await self.client.close()
            self.client = None

    async def _maybe_reconnect(self) -> None:
        if self.stopped:
            return
        self._reconnect_attempts += 1
        if self._reconnect_attempts > self._max_reconnect_attempts:
            self.ten_env.log_error(
                f"[gradium] giving up after {self._reconnect_attempts} reconnect attempts"
            )
            return
        delay = min(1.0 * self._reconnect_attempts, 10.0)
        self.ten_env.log_warn(
            f"[gradium] reconnecting in {delay}s (attempt {self._reconnect_attempts})"
        )
        await asyncio.sleep(delay)
        await self.start_connection()

    def is_connected(self) -> bool:
        return self.connected

    # ---------- client -> provider ----------

    async def send_audio(
        self, frame: AudioFrame, session_id: str | None
    ) -> bool:
        self.session_id = session_id
        if not self.connected or not self.client:
            return False
        try:
            await self.client.send_audio(bytes(frame.get_buf()))
            return True
        except Exception as e:
            self.ten_env.log_error(f"[gradium] send_audio failed: {e}")
            return False

    async def send_client_message_item(
        self, item: MLLMClientMessageItem, session_id: str | None = None
    ) -> None:
        # Gradium's S2S translation is a continuous audio pipe, not a
        # tool-calling conversational LLM -- there's no known equivalent of
        # "inject a message item". No-op until Gradium's docs say otherwise.
        self.ten_env.log_debug(
            f"[gradium] send_client_message_item is a no-op for this vendor: {item}"
        )

    async def send_client_create_response(
        self, session_id: str | None = None
    ) -> None:
        self.ten_env.log_debug(
            "[gradium] send_client_create_response is a no-op for this vendor"
        )

    async def send_client_register_tool(self, tool: LLMToolMetadata) -> None:
        self.ten_env.log_debug(
            f"[gradium] send_client_register_tool is a no-op for this vendor: {tool.name}"
        )

    async def send_client_function_call_output(
        self, function_call_output: MLLMClientFunctionCallOutput
    ) -> None:
        self.ten_env.log_debug(
            "[gradium] send_client_function_call_output is a no-op for this vendor"
        )

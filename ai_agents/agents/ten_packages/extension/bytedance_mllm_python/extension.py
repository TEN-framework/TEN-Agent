from __future__ import annotations

import asyncio
import json
import traceback
import uuid

from ten_ai_base.const import LOG_CATEGORY_KEY_POINT, LOG_CATEGORY_VENDOR
from ten_ai_base.message import (
    ModuleError,
    ModuleErrorCode,
    ModuleErrorVendorInfo,
)
from ten_ai_base.mllm import AsyncMLLMBaseExtension
from ten_ai_base.struct import (
    MLLMClientFunctionCallOutput,
    MLLMClientMessageItem,
    MLLMServerInputTranscript,
    MLLMServerInterrupt,
    MLLMServerOutputTranscript,
    MLLMServerSessionReady,
)
from ten_ai_base.types import LLMToolMetadata
from ten_ai_base.utils import encrypt
from ten_runtime import AudioFrame, AsyncTenEnv, Data

from .config import BytedanceMLLMConfig
from .connection import BytedanceRealtimeConnection
from .protocol import ServerEvent, ServerMessage


class BytedanceMLLMExtension(AsyncMLLMBaseExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.ten_env: AsyncTenEnv | None = None
        self.config: BytedanceMLLMConfig | None = None
        self.conn: BytedanceRealtimeConnection | None = None

        self.connected = False
        self.stopped = False
        self.doubao_session_id = str(uuid.uuid4())
        self.request_transcript = ""
        self.response_transcript = ""
        self._session_started = False
        self._response_final_sent = True

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        self.ten_env = ten_env

        properties, _ = await ten_env.get_property_to_json(None)
        self.config = BytedanceMLLMConfig.model_validate_json(properties)
        ten_env.log_info(
            f"config: {self.config.to_str(sensitive_handling=True)}",
            category=LOG_CATEGORY_KEY_POINT,
        )

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)
        self.stopped = True
        if self.conn:
            await self.conn.close()

    def vendor(self) -> str:
        return "bytedance_doubao"

    def input_audio_sample_rate(self) -> int:
        return self.config.input_sample_rate

    def synthesize_audio_sample_rate(self) -> int:
        return self.config.output_sample_rate

    def synthesize_audio_channels(self) -> int:
        return 1

    def synthesize_audio_sample_width(self) -> int:
        return 2

    def is_connected(self) -> bool:
        return self.connected

    async def start_connection(self) -> None:
        try:
            self.conn = BytedanceRealtimeConnection(
                ten_env=self.ten_env,
                config=self.config,
                session_id=self.doubao_session_id,
            )
            await self.conn.connect()
            await self.conn.send_start_connection()

            self.ten_env.log_info("[Doubao] client loop started")
            async for message in self.conn.listen():
                try:
                    await self._handle_server_message(message)
                except Exception as e:
                    traceback.print_exc()
                    self.ten_env.log_error(
                        f"[Doubao] error processing message {message}: {e}"
                    )

            self.ten_env.log_info("[Doubao] client loop finished")
        except Exception as e:
            traceback.print_exc()
            self.ten_env.log_error(f"[Doubao] connection failed: {e}")

        await self._handle_reconnect()

    async def stop_connection(self) -> None:
        self.connected = False
        self._session_started = False
        if self.conn:
            try:
                await self.conn.send_finish_session()
                await self.conn.send_finish_connection()
            except Exception as e:
                self.ten_env.log_warn(f"[Doubao] finish failed: {e}")
            await self.conn.close()

    async def _handle_reconnect(self) -> None:
        await self.stop_connection()
        if not self.stopped:
            await asyncio.sleep(1)
            self.doubao_session_id = str(uuid.uuid4())
            await self.start_connection()

    async def _handle_server_message(self, message: ServerMessage) -> None:
        event = self._server_event(message.event)
        if event is None:
            self.ten_env.log_debug(f"[Doubao] unhandled event {message.event}")
            return

        if event == ServerEvent.CONNECTION_STARTED:
            self.ten_env.log_info(
                f"[Doubao] connection started: {message.connection_id}",
                category=LOG_CATEGORY_VENDOR,
            )
            await self._start_session()
        elif event == ServerEvent.CONNECTION_FAILED:
            await self._send_vendor_error(
                "CONNECTION_FAILED",
                self._payload_error(message),
                fatal=True,
            )
        elif event == ServerEvent.SESSION_STARTED:
            self.connected = True
            self._session_started = True
            self.ten_env.log_info(
                f"[Doubao] session started: {message.session_id}",
                category=LOG_CATEGORY_VENDOR,
            )
            await self.send_server_session_ready(MLLMServerSessionReady())
        elif event == ServerEvent.SESSION_FAILED:
            await self._send_vendor_error(
                "SESSION_FAILED",
                self._payload_error(message),
                fatal=True,
            )
        elif event == ServerEvent.SESSION_FINISHED:
            self.connected = False
            self._session_started = False
        elif event == ServerEvent.ASR_INFO:
            await self.send_server_interrupted(MLLMServerInterrupt())
        elif event == ServerEvent.ASR_RESPONSE:
            await self._handle_asr_response(message)
        elif event == ServerEvent.ASR_ENDED:
            await self._finalize_input_transcript()
        elif event == ServerEvent.CHAT_RESPONSE:
            await self._handle_chat_response(message)
        elif event == ServerEvent.CHAT_ENDED:
            await self._finalize_output_transcript()
        elif event == ServerEvent.TTS_RESPONSE:
            if message.payload:
                await self.send_server_output_audio_data(message.payload)
        elif event == ServerEvent.TTS_ENDED:
            await self._finalize_output_transcript()
        elif event == ServerEvent.DIALOG_COMMON_ERROR:
            await self._send_vendor_error(
                "DIALOG_COMMON_ERROR",
                self._payload_error(message),
                fatal=False,
            )
        elif event == ServerEvent.USAGE_RESPONSE:
            self.ten_env.log_debug(f"[Doubao] usage: {message.payload_json}")
        else:
            self.ten_env.log_debug(
                f"[Doubao] event={event.name} payload={message.payload_json}"
            )

    async def send_audio(
        self, frame: AudioFrame, session_id: str | None
    ) -> bool:
        self.session_id = session_id
        if not self.connected or not self.conn:
            return False
        if frame.get_sample_rate() != self.input_audio_sample_rate():
            self.ten_env.log_warn(
                "[Doubao] dropping audio frame with unsupported sample rate "
                f"{frame.get_sample_rate()}Hz; expected "
                f"{self.input_audio_sample_rate()}Hz"
            )
            return False
        await self.conn.send_audio_data(frame.get_buf())
        return True

    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        await super().on_data(ten_env, data)

    async def send_client_message_item(
        self, item: MLLMClientMessageItem, session_id: str | None = None
    ) -> None:
        if item.role != "user":
            self.ten_env.log_warn(
                f"[Doubao] message role {item.role} is not supported"
            )
            return
        if not self.conn:
            return
        await self.conn.send_text_query(item.content)

    async def send_client_create_response(
        self, session_id: str | None = None
    ) -> None:
        self.ten_env.log_debug("[Doubao] create_response is implicit")

    async def send_client_register_tool(self, _tool: LLMToolMetadata) -> None:
        self.ten_env.log_warn("[Doubao] tool calling is not supported")

    async def send_client_function_call_output(
        self, _function_call_output: MLLMClientFunctionCallOutput
    ) -> None:
        self.ten_env.log_warn("[Doubao] tool calling is not supported")

    async def _start_session(self) -> None:
        payload = self.config.start_session_payload(self.message_context)
        self.ten_env.log_info(
            "[Doubao] start session payload: "
            + json.dumps(self._redact_payload(payload), ensure_ascii=False),
            category=LOG_CATEGORY_VENDOR,
        )
        await self.conn.send_start_session(payload)

    async def _handle_asr_response(self, message: ServerMessage) -> None:
        payload = message.payload_json or {}
        results = payload.get("results", [])
        if not results:
            return

        text = "".join(str(result.get("text", "")) for result in results)
        is_interim = any(bool(result.get("is_interim")) for result in results)
        if not text:
            return

        self.request_transcript = text
        await self.send_server_input_transcript(
            MLLMServerInputTranscript(
                content=text,
                delta=text,
                final=not is_interim,
                metadata={"session_id": self.session_id or "-1"},
            )
        )
        if not is_interim:
            self.request_transcript = ""

    async def _finalize_input_transcript(self) -> None:
        if not self.request_transcript:
            return
        await self.send_server_input_transcript(
            MLLMServerInputTranscript(
                content=self.request_transcript,
                delta="",
                final=True,
                metadata={"session_id": self.session_id or "-1"},
            )
        )
        self.request_transcript = ""

    async def _handle_chat_response(self, message: ServerMessage) -> None:
        payload = message.payload_json or {}
        delta = str(payload.get("content", ""))
        if not delta:
            return
        self.response_transcript += delta
        self._response_final_sent = False
        await self.send_server_output_text(
            MLLMServerOutputTranscript(
                content=self.response_transcript,
                delta=delta,
                final=False,
                metadata={"session_id": self.session_id or "-1"},
            )
        )

    async def _finalize_output_transcript(self) -> None:
        if self._response_final_sent:
            return
        await self.send_server_output_text(
            MLLMServerOutputTranscript(
                content=self.response_transcript,
                delta="",
                final=True,
                metadata={"session_id": self.session_id or "-1"},
            )
        )
        self.response_transcript = ""
        self._response_final_sent = True

    async def _send_vendor_error(
        self, code: str, message: str, fatal: bool
    ) -> None:
        self.ten_env.log_error(f"[Doubao] {code}: {message}")
        await self.send_mllm_error(
            ModuleError(
                code=(
                    ModuleErrorCode.FATAL_ERROR.value
                    if fatal
                    else ModuleErrorCode.NON_FATAL_ERROR.value
                ),
                message=message,
            ),
            ModuleErrorVendorInfo(
                vendor=self.vendor(),
                code=code,
                message=message,
            ),
        )

    def _payload_error(self, message: ServerMessage) -> str:
        if message.payload_json:
            return json.dumps(message.payload_json, ensure_ascii=False)
        if message.payload:
            return message.payload.decode("utf-8", errors="replace")
        if message.error_code:
            return f"error_code={message.error_code}"
        return "unknown error"

    def _server_event(self, event: int) -> ServerEvent | None:
        try:
            return ServerEvent(event)
        except ValueError:
            return None

    def _redact_payload(self, payload):
        if isinstance(payload, dict):
            result = {}
            for key, value in payload.items():
                lower_key = key.lower()
                if "key" in lower_key or "token" in lower_key:
                    result[key] = (
                        encrypt(value) if isinstance(value, str) else "***"
                    )
                else:
                    result[key] = self._redact_payload(value)
            return result
        if isinstance(payload, list):
            return [self._redact_payload(value) for value in payload]
        return payload

#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import asyncio
import base64
import traceback
import time
from typing import Literal

from pydantic import BaseModel

from ten_ai_base.mllm import AsyncMLLMBaseExtension
from ten_ai_base.struct import (
    MLLMClientFunctionCallOutput,
    MLLMClientMessageItem,
    MLLMServerFunctionCall,
    MLLMServerInputTranscript,
    MLLMServerInterrupt,
    MLLMServerOutputTranscript,
    MLLMServerSessionReady,
)
from ten_runtime import (
    AudioFrame,
    AsyncTenEnv,
    Data,
)
from dataclasses import dataclass
from ten_ai_base.types import (
    LLMToolMetadata,
)
from .realtime.connection import RealtimeApiConnection
from .realtime.struct import (
    AssistantMessageItemParam,
    ItemCreate,
    ItemInputAudioTranscriptionDelta,
    SessionCreated,
    ItemCreated,
    SessionUpdated,
    UserMessageItemParam,
    ItemInputAudioTranscriptionCompleted,
    ItemInputAudioTranscriptionFailed,
    ResponseCreated,
    ResponseDone,
    ResponseAudioTranscriptDelta,
    ResponseTextDelta,
    ResponseAudioTranscriptDone,
    ResponseTextDone,
    ResponseOutputItemDone,
    ResponseOutputItemAdded,
    ResponseAudioDelta,
    ResponseAudioDone,
    InputAudioBufferSpeechStarted,
    InputAudioBufferSpeechStopped,
    ResponseFunctionCallArgumentsDone,
    ErrorMessage,
    SessionUpdate,
    SessionUpdateParams,
    InputAudioTranscription,
    ContentType,
    FunctionCallOutputItemParam,
    ResponseCreate,
    ServerVADUpdateParams,
    SemanticVADUpdateParams,
)


@dataclass
class OpenAIRealtimeConfig(BaseModel):
    base_url: str = "wss://api.openai.com"
    api_key: str = ""
    path: str = "/v1/realtime"
    model: str = "gpt-4o"
    language: str = "en"
    prompt: str = ""
    temperature: float = 0.5
    max_tokens: int = 1024
    voice: str = "alloy"
    server_vad: bool = True
    audio_out: bool = True
    sample_rate: int = 24000
    vad_type: Literal["server_vad", "semantic_vad"] = "server_vad"
    vad_eagerness: Literal["low", "medium", "high", "auto"] = "auto"
    vad_threshold: float = 0.5
    vad_prefix_padding_ms: int = 300
    vad_silence_duration_ms: int = 500
    vendor: str = ""
    dump: bool = False
    dump_path: str = ""


class OpenAIRealtime2Extension(AsyncMLLMBaseExtension):

    def __init__(self, name: str):
        super().__init__(name)
        self.ten_env: AsyncTenEnv = None
        self.conn = None
        self.openai_session = None
        self.openai_session_id = None

        self.config: OpenAIRealtimeConfig = None
        self.stopped: bool = False
        self.connected: bool = False

        self.request_transcript: str = ""
        self.response_transcript: str = ""
        self.available_tools: list[LLMToolMetadata] = []
        self.loop: asyncio.AbstractEventLoop = None

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        ten_env.log_debug("on_init")
        self.ten_env = ten_env

        properties, _ = await ten_env.get_property_to_json(None)
        self.config = OpenAIRealtimeConfig.model_validate_json(properties)
        ten_env.log_info(f"config: {self.config}")

        if not self.config.api_key:
            ten_env.log_error("api_key is required")
            raise ValueError("api_key is required")

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)
        self.stopped = True
        if self.conn:
            await self.conn.close()

    def input_audio_sample_rate(self) -> int:
        return self.config.sample_rate

    def synthesize_audio_sample_rate(self) -> int:
        return self.config.sample_rate

    def vendor(self) -> str:
        return "openai"

    async def start_connection(self) -> None:
        try:
            self.conn = RealtimeApiConnection(
                ten_env=self.ten_env,
                base_url=self.config.base_url,
                path=self.config.path,
                api_key=self.config.api_key,
                model=self.config.model,
                vendor=self.config.vendor,
            )

            await self.conn.connect()
            item_id = ""  # For truncate
            response_id = ""
            flushed = set()
            session_start_ms = int(
                time.time() * 1000
            )  # Use proper timestamp in milliseconds

            self.ten_env.log_info("Client loop started")
            async for message in self.conn.listen():
                try:
                    # self.ten_env.log_info(f"Received message: {message.type}")
                    match message:
                        case SessionCreated():
                            self.ten_env.log_info(
                                f"Session is created: {message.session}"
                            )
                            self.connected = True
                            self.openai_session_id = message.session.id
                            self.openai_session = message.session
                            await self._update_session()
                            await self._resume_context(self.message_context)
                        case SessionUpdated():
                            self.ten_env.log_info(
                                f"Session is updated: {message.session}"
                            )
                            await self.send_server_session_ready(
                                MLLMServerSessionReady()
                            )
                        case ItemInputAudioTranscriptionDelta():
                            self.ten_env.log_debug(
                                f"On request transcript delta {message.item_id} {message.content_index}"
                            )
                            self.request_transcript += message.delta
                            await self.send_server_input_transcript(
                                MLLMServerInputTranscript(
                                    content=self.request_transcript,
                                    delta=message.delta,
                                    final=False,
                                    metadata={
                                        "session_id": (
                                            self.session_id
                                            if self.session_id
                                            else "-1"
                                        ),
                                    },
                                )
                            )
                        case ItemInputAudioTranscriptionCompleted():
                            self.ten_env.log_debug(
                                f"On request transcript {message.transcript}"
                            )
                            await self.send_server_input_transcript(
                                MLLMServerInputTranscript(
                                    content=self.request_transcript,
                                    delta=message.transcript,
                                    final=True,
                                    metadata={
                                        "session_id": (
                                            self.session_id
                                            if self.session_id
                                            else "-1"
                                        ),
                                    },
                                )
                            )
                            self.request_transcript = ""
                        case ItemInputAudioTranscriptionFailed():
                            self.ten_env.log_warn(
                                f"On request transcript failed {message.item_id} {message.error}"
                            )
                            self.request_transcript = ""
                        case ItemCreated():
                            self.ten_env.log_debug(
                                f"On item created {message.item}"
                            )
                        case ResponseCreated():
                            response_id = message.response.id
                            self.ten_env.log_debug(
                                f"On response created {response_id}"
                            )
                        case ResponseDone():
                            msg_resp_id = message.response.id
                            status = message.response.status
                            if msg_resp_id == response_id:
                                response_id = ""
                            self.ten_env.log_debug(
                                f"On response done {msg_resp_id} {status} {message.response.usage}"
                            )
                            if message.response.usage:
                                pass
                                # await self._update_usage(message.response.usage)
                        case ResponseAudioTranscriptDelta():
                            self.ten_env.log_debug(
                                f"On response transcript delta {message.response_id} {message.output_index} {message.content_index} {message.delta}"
                            )
                            if message.response_id in flushed:
                                self.ten_env.log_warn(
                                    f"On flushed transcript delta {message.response_id} {message.output_index} {message.content_index} {message.delta}"
                                )
                                continue

                            self.response_transcript += message.delta
                            await self.send_server_output_text(
                                MLLMServerOutputTranscript(
                                    content=self.response_transcript,
                                    delta=message.delta,
                                    final=False,
                                    metadata={
                                        "session_id": (
                                            self.session_id
                                            if self.session_id
                                            else "-1"
                                        ),
                                    },
                                )
                            )
                        case ResponseTextDelta():
                            self.ten_env.log_debug(
                                f"On response text delta {message.response_id} {message.output_index} {message.content_index} {message.delta}"
                            )
                            if message.response_id in flushed:
                                self.ten_env.log_warn(
                                    f"On flushed text delta {message.response_id} {message.output_index} {message.content_index} {message.delta}"
                                )
                                continue
                            if item_id != message.item_id:
                                item_id = message.item_id

                            self.response_transcript += message.delta
                            await self.send_server_output_text(
                                MLLMServerOutputTranscript(
                                    content=self.response_transcript,
                                    delta=message.delta,
                                    final=False,
                                    metadata={
                                        "session_id": (
                                            self.session_id
                                            if self.session_id
                                            else "-1"
                                        ),
                                    },
                                )
                            )
                        case ResponseAudioTranscriptDone():
                            self.ten_env.log_debug(
                                f"On response transcript done {message.output_index} {message.content_index} {message.transcript}"
                            )
                            if message.response_id in flushed:
                                self.ten_env.log_warn(
                                    f"On flushed transcript done {message.response_id}"
                                )
                                continue
                            await self.send_server_output_text(
                                MLLMServerOutputTranscript(
                                    content=self.response_transcript,
                                    delta="",
                                    final=True,
                                    metadata={
                                        "session_id": (
                                            self.session_id
                                            if self.session_id
                                            else "-1"
                                        ),
                                    },
                                )
                            )
                            self.response_transcript = ""
                        case ResponseTextDone():
                            self.ten_env.log_debug(
                                f"On response text done {message.output_index} {message.content_index} {message.text}"
                            )
                            if message.response_id in flushed:
                                self.ten_env.log_warn(
                                    f"On flushed text done {message.response_id}"
                                )
                                continue
                            await self.send_server_output_text(
                                MLLMServerOutputTranscript(
                                    content=self.response_transcript,
                                    delta="",
                                    final=True,
                                    metadata={
                                        "session_id": (
                                            self.session_id
                                            if self.session_id
                                            else "-1"
                                        ),
                                    },
                                )
                            )
                            self.response_transcript = ""
                        case ResponseOutputItemDone():
                            self.ten_env.log_debug(
                                f"Output item done {message.item}"
                            )
                        case ResponseOutputItemAdded():
                            self.ten_env.log_debug(
                                f"Output item added {message.output_index} {message.item}"
                            )
                        case ResponseAudioDelta():
                            if message.response_id in flushed:
                                self.ten_env.log_warn(
                                    f"On flushed audio delta {message.response_id} {message.item_id} {message.content_index}"
                                )
                                continue
                            if item_id != message.item_id:
                                item_id = message.item_id
                            audio_data = base64.b64decode(message.delta)
                            await self.send_server_output_audio_data(audio_data)
                        case ResponseAudioDone():
                            pass
                        case InputAudioBufferSpeechStarted():
                            self.ten_env.log_info(
                                f"On server listening, in response {response_id}, last item {item_id}"
                            )
                            # Calculate proper truncation time - elapsed milliseconds since session start
                            # current_ms = int(time.time() * 1000)
                            # end_ms = current_ms - session_start_ms
                            # if (
                            #     item_id and end_ms > 0
                            # ):  # Only truncate if we have a valid positive timestamp
                            #     self.ten_env.log_info(
                            #         f"Truncating item {item_id} at content index {content_index} with end time {end_ms}"
                            #     )
                            #     truncate = ItemTruncate(
                            #         item_id=item_id,
                            #         content_index=content_index,
                            #         audio_end_ms=end_ms,
                            #     )
                            #     await self.conn.send_request(truncate)
                            if self.config.server_vad:
                                await self.send_server_interrupted(
                                    sos=MLLMServerInterrupt()
                                )
                            if response_id and self.response_transcript:
                                transcript = (
                                    self.response_transcript + "[interrupted]"
                                )
                                await self.send_server_output_text(
                                    MLLMServerOutputTranscript(
                                        content=transcript,
                                        delta=None,
                                        final=True,
                                        metadata={
                                            "session_id": (
                                                self.session_id
                                                if self.session_id
                                                else "-1"
                                            ),
                                        },
                                    )
                                )
                                self.response_transcript = ""
                                # memory leak, change to lru later
                                flushed.add(response_id)
                            item_id = ""
                        case InputAudioBufferSpeechStopped():
                            # Only for server vad
                            # Update session start to properly track relative timing
                            session_start_ms = (
                                int(time.time() * 1000) - message.audio_end_ms
                            )
                            self.ten_env.log_info(
                                f"On server stop listening, audio_end_ms: {message.audio_end_ms}, session_start_ms updated to: {session_start_ms}"
                            )
                        case ResponseFunctionCallArgumentsDone():
                            tool_call_id = message.call_id
                            name = message.name
                            arguments = message.arguments
                            self.ten_env.log_info(f"need to call func {name}")
                            asyncio.create_task(
                                self._handle_tool_call(
                                    tool_call_id, name, arguments
                                )
                            )
                        case ErrorMessage():
                            self.ten_env.log_error(
                                f"Error message received: {message.error}"
                            )
                        case _:
                            self.ten_env.log_debug(
                                f"Not handled message {message}"
                            )
                except Exception as e:
                    traceback.print_exc()
                    self.ten_env.log_error(
                        f"Error processing message: {message} {e}"
                    )

            self.ten_env.log_info("Client loop finished")
        except Exception as e:
            traceback.print_exc()
            self.ten_env.log_error(f"Failed to handle loop {e}")

        await self._handle_reconnect()

    async def stop_connection(self) -> None:
        self.connected = False
        if self.conn is not None:
            await self.conn.close()

    async def _handle_reconnect(self) -> None:
        """Handle reconnection logic with exponential backoff strategy."""
        await self.stop_connection()
        if not self.stopped:
            await asyncio.sleep(1)  # Initial delay before reconnecting
            await self.start_connection()

    def is_connected(self) -> bool:
        return self.connected

    async def send_audio(
        self, frame: AudioFrame, session_id: str | None
    ) -> bool:
        self.session_id = session_id
        await self.conn.send_audio_data(frame.get_buf())
        return True

    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        await super().on_data(ten_env, data)

    async def send_client_message_item(
        self, item: MLLMClientMessageItem, session_id: str | None = None
    ) -> None:
        """
        Send a message item to the MLLM service.
        This method is used to send text messages to the LLM.
        """
        match item.role:
            case "user":
                await self.conn.send_request(
                    ItemCreate(
                        item=UserMessageItemParam(
                            content=[
                                {
                                    "type": ContentType.InputText,
                                    "text": item.content,
                                }
                            ]
                        )
                    )
                )
            case "assistant":
                await self.conn.send_request(
                    ItemCreate(
                        item=AssistantMessageItemParam(
                            content=[
                                {"type": ContentType.Text, "text": item.content}
                            ]
                        )
                    )
                )
            case _:
                self.ten_env.log_error(f"Unknown role: {item.role}")
                return

    async def send_client_create_response(
        self, session_id: str | None = None
    ) -> None:
        """
        Send a create response to the MLLM service.
        This method is used to trigger MLLM to generate a response.
        """
        await self.conn.send_request(ResponseCreate())

    async def send_client_register_tool(self, tool: LLMToolMetadata) -> None:
        """
        Register tools with the MLLM service.
        This method is used to register tools that can be called by the LLM.
        """
        self.available_tools.append(tool)
        await self._update_session()

    async def send_client_function_call_output(
        self, function_call_output: MLLMClientFunctionCallOutput
    ) -> None:
        """
        Send a function call output to the MLLM service.
        This method is used to send the result of a function call made by the LLM.
        """
        self.ten_env.log_info(
            f"Sending function call output: {function_call_output.output}"
        )
        await self.conn.send_request(
            ItemCreate(
                item=FunctionCallOutputItemParam(
                    call_id=function_call_output.call_id,
                    output=function_call_output.output,
                )
            )
        )

    async def _resume_context(
        self, messages: list[MLLMClientMessageItem]
    ) -> None:
        """
        Resume the context with the provided messages.
        This method is used to set the context messages for the LLM.
        """
        for message in messages:
            self.ten_env.log_info(f"Resuming context with messages: {message}")
            await self.send_client_message_item(message)

    async def _update_session(self) -> None:
        if not self.connected:
            self.ten_env.log_warn("Not connected to OpenAI session")
            return

        tools = []

        def tool_dict(tool: LLMToolMetadata):
            t = {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            }

            for param in tool.parameters:
                t["parameters"]["properties"][param.name] = {
                    "type": param.type,
                    "description": param.description,
                }
                if param.required:
                    t["parameters"]["required"].append(param.name)

            return t

        if self.available_tools:
            tools = [tool_dict(t) for t in self.available_tools]
        prompt = self.config.prompt

        if self.config.vad_type == "server_vad":
            vad_params = ServerVADUpdateParams(
                threshold=self.config.vad_threshold,
                prefix_padding_ms=self.config.vad_prefix_padding_ms,
                silence_duration_ms=self.config.vad_silence_duration_ms,
            )
        else:  # semantic vad
            vad_params = SemanticVADUpdateParams(
                eagerness=self.config.vad_eagerness,
            )
        su = SessionUpdate(
            session=SessionUpdateParams(
                instructions=prompt,
                model=self.config.model,
                tool_choice="auto" if self.available_tools else "none",
                tools=tools,
                turn_detection=vad_params,
            )
        )
        if self.config.audio_out:
            su.session.voice = self.config.voice
        else:
            su.session.modalities = {"text"}

        su.session.input_audio_transcription = InputAudioTranscription(
            language=self.config.language,
        )
        self.ten_env.log_info(f"update session {su}")

        await self.conn.send_request(su)

    async def _handle_tool_call(
        self, tool_call_id: str, name: str, arguments: str
    ) -> None:
        self.ten_env.log_info(
            f"_handle_tool_call {tool_call_id} {name} {arguments}"
        )
        await self.send_server_function_call(
            MLLMServerFunctionCall(
                call_id=tool_call_id, name=name, arguments=arguments
            )
        )

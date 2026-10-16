#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""ThunderPhone voice agents as a TEN multimodal (speech-to-speech) LLM.

ThunderPhone's Realtime WebSocket API speaks the OpenAI Realtime protocol,
so this extension follows openai_mllm_python closely. What differs:

* one WebSocket is one billable call. It never reconnects after the
  platform ends the call (``call.ended``), and an inline session starts on
  its first ``session.update``, which freezes instructions, tools and voice;
  the extension therefore sends a single, complete update once audio starts
  (or shortly after the session is created), so tools registered at graph
  start are included;
* a saved agent (``agent_id``) brings its own prompt, voice, engine,
  languages, tools and greeting; nothing is sent to configure it;
* ThunderPhone's ``call.*`` events (hang-up reason, transfer, keypad) are
  logged, and ``call.ended`` stops the extension from reconnecting.
"""
import asyncio
import base64
import traceback

import aiohttp

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
from ten_ai_base.types import LLMToolMetadata
from ten_runtime import AsyncTenEnv, AudioFrame, Data

from .config import ThunderPhoneRealtimeConfig, inline_session_update
from .realtime.connection import ThunderPhoneConnection
from .realtime.struct import (
    CallEvent,
    ContentType,
    ErrorMessage,
    FunctionCallOutputItemParam,
    InputAudioBufferSpeechStarted,
    InputAudioBufferSpeechStopped,
    ItemCreate,
    ItemCreated,
    ItemInputAudioTranscriptionCompleted,
    ItemInputAudioTranscriptionDelta,
    ItemInputAudioTranscriptionFailed,
    ResponseAudioDelta,
    ResponseAudioDone,
    ResponseAudioTranscriptDelta,
    ResponseAudioTranscriptDone,
    ResponseCreate,
    ResponseCreated,
    ResponseDone,
    ResponseFunctionCallArgumentsDone,
    ResponseOutputItemAdded,
    ResponseOutputItemDone,
    ResponseTextDelta,
    ResponseTextDone,
    SessionCreated,
    SessionUpdated,
    UnknownMessage,
    UserMessageItemParam,
)

# How long an inline session waits for tool registrations before starting
# the call on its own. The first audio frame starts it earlier.
INLINE_START_GRACE_S = 0.5
RECONNECT_DELAY_S = 1.0


class ThunderPhoneRealtimeExtension(AsyncMLLMBaseExtension):

    def __init__(self, name: str):
        super().__init__(name)
        self.ten_env: AsyncTenEnv = None
        self.config: ThunderPhoneRealtimeConfig = None
        self.conn: ThunderPhoneConnection | None = None
        self.loop: asyncio.AbstractEventLoop = None

        self.stopped: bool = False
        self.connected: bool = False
        self.call_ended: bool = False
        self.call_id = None
        self.session_ready: bool = False
        # Inline sessions: the call has started once the session.update is out.
        self.started: bool = False
        self._start_task: asyncio.Task | None = None

        self.request_transcript: str = ""
        self.response_transcript: str = ""
        self.available_tools: list[LLMToolMetadata] = []

    # ------------------------------------------------------------ lifecycle

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        ten_env.log_debug("on_init")
        self.ten_env = ten_env

        properties, _ = await ten_env.get_property_to_json(None)
        self.config = ThunderPhoneRealtimeConfig.model_validate_json(properties)
        ten_env.log_info(
            f"config: {self.config.model_copy(update={'api_key': '***'})}"
        )
        try:
            self.config.validate_for_start()
        except ValueError as e:
            ten_env.log_error(str(e))
            raise
        if self.config.saved_agent and (
            self.config.prompt or self.config.voice or self.config.product
        ):
            ten_env.log_info(
                "agent_id is set: prompt, voice and product are ignored, the "
                "saved agent's own configuration is used"
            )

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)
        self.stopped = True
        if self._start_task:
            self._start_task.cancel()
        if self.conn:
            await self.conn.close()

    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        await super().on_data(ten_env, data)

    def vendor(self) -> str:
        return "thunderphone"

    def input_audio_sample_rate(self) -> int:
        return self.config.sample_rate

    def synthesize_audio_sample_rate(self) -> int:
        return self.config.sample_rate

    def is_connected(self) -> bool:
        return self.connected

    # ----------------------------------------------------------- connection

    async def start_connection(self) -> None:
        if self.call_ended:
            self.ten_env.log_info("ThunderPhone call already ended; not starting a new one")
            return
        self.loop = asyncio.get_running_loop()
        try:
            self.conn = ThunderPhoneConnection(
                ten_env=self.ten_env,
                base_url=self.config.base_url,
                path=self.config.path,
                api_key=self.config.api_key,
                query=self.config.query(),
            )
            try:
                await self.conn.connect()
            except aiohttp.WSServerHandshakeError as e:
                # A rejected key or agent never gets better on retry.
                self.ten_env.log_error(
                    f"ThunderPhone refused the connection: {e.status} {e.message}"
                )
                self.stopped = True
                return

            response_id = ""
            flushed: set[str] = set()
            self.ten_env.log_info("Client loop started")
            async for message in self.conn.listen():
                try:
                    match message:
                        case SessionCreated():
                            self.ten_env.log_info(
                                f"Session is created: {message.session}"
                            )
                            self.connected = True
                            self._note_call_id(message.session.call_id)
                            if self.config.saved_agent:
                                # The agent is already live and greets on its own.
                                await self._mark_session_ready()
                            else:
                                self._arm_inline_start()
                            await self._resume_context(self.message_context)
                        case SessionUpdated():
                            self.ten_env.log_info(
                                f"Session is updated: {message.session}"
                            )
                            self._note_call_id(message.session.call_id)
                            await self._mark_session_ready()
                        case ItemInputAudioTranscriptionDelta():
                            self.request_transcript += message.delta
                            await self.send_server_input_transcript(
                                MLLMServerInputTranscript(
                                    content=self.request_transcript,
                                    delta=message.delta,
                                    final=False,
                                    metadata=self._metadata(),
                                )
                            )
                        case ItemInputAudioTranscriptionCompleted():
                            self.ten_env.log_debug(
                                f"On request transcript {message.transcript}"
                            )
                            await self.send_server_input_transcript(
                                MLLMServerInputTranscript(
                                    content=message.transcript,
                                    delta=message.transcript,
                                    final=True,
                                    metadata=self._metadata(),
                                )
                            )
                            self.request_transcript = ""
                        case ItemInputAudioTranscriptionFailed():
                            self.ten_env.log_warn(
                                f"On request transcript failed {message.item_id} {message.error}"
                            )
                            self.request_transcript = ""
                        case ItemCreated():
                            self.ten_env.log_debug(f"On item {message.item}")
                        case ResponseCreated():
                            response_id = message.response.id
                            self.ten_env.log_debug(
                                f"On response created {response_id}"
                            )
                        case ResponseDone():
                            if message.response.id == response_id:
                                response_id = ""
                            self.ten_env.log_debug(
                                f"On response done {message.response.id} {message.response.status}"
                            )
                        case ResponseAudioTranscriptDelta() | ResponseTextDelta():
                            if message.response_id in flushed:
                                continue
                            self.response_transcript += message.delta
                            await self.send_server_output_text(
                                MLLMServerOutputTranscript(
                                    content=self.response_transcript,
                                    delta=message.delta,
                                    final=False,
                                    metadata=self._metadata(),
                                )
                            )
                        case ResponseAudioTranscriptDone() | ResponseTextDone():
                            if message.response_id in flushed:
                                continue
                            await self.send_server_output_text(
                                MLLMServerOutputTranscript(
                                    content=self.response_transcript,
                                    delta="",
                                    final=True,
                                    metadata=self._metadata(),
                                )
                            )
                            self.response_transcript = ""
                        case ResponseOutputItemAdded() | ResponseOutputItemDone():
                            self.ten_env.log_debug(f"Output item {message.item}")
                        case ResponseAudioDelta():
                            if message.response_id in flushed:
                                continue
                            await self.send_server_output_audio_data(
                                base64.b64decode(message.delta)
                            )
                        case ResponseAudioDone():
                            pass
                        case InputAudioBufferSpeechStarted():
                            # Server-side turn detection: the caller took the
                            # turn, so whatever the agent was saying is over.
                            self.ten_env.log_info(
                                f"On server listening, in response {response_id}"
                            )
                            await self.send_server_interrupted(
                                sos=MLLMServerInterrupt()
                            )
                            if response_id and self.response_transcript:
                                await self.send_server_output_text(
                                    MLLMServerOutputTranscript(
                                        content=self.response_transcript
                                        + "[interrupted]",
                                        delta=None,
                                        final=True,
                                        metadata=self._metadata(),
                                    )
                                )
                                self.response_transcript = ""
                                flushed.add(response_id)
                        case InputAudioBufferSpeechStopped():
                            self.ten_env.log_debug("On server stop listening")
                        case ResponseFunctionCallArgumentsDone():
                            self.ten_env.log_info(
                                f"need to call func {message.name}"
                            )
                            asyncio.create_task(
                                self._handle_tool_call(
                                    message.call_id,
                                    message.name,
                                    message.arguments,
                                )
                            )
                        case CallEvent():
                            self._on_call_event(message)
                        case ErrorMessage():
                            # ThunderPhone errors are per-event and non-fatal;
                            # a fatal one is followed by the socket closing.
                            self.ten_env.log_warn(
                                f"Error message received: {message.error}"
                            )
                        case UnknownMessage():
                            self.ten_env.log_debug(
                                f"Not handled message {message.type}"
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
            self.ten_env.log_info(
                f"Client loop finished (close code {self.conn.close_code})"
            )
        except Exception as e:
            traceback.print_exc()
            self.ten_env.log_error(f"Failed to handle loop {e}")

        await self._handle_reconnect()

    async def stop_connection(self) -> None:
        self.connected = False
        if self._start_task:
            self._start_task.cancel()
            self._start_task = None
        if self.conn is not None:
            await self.conn.close()

    async def _handle_reconnect(self) -> None:
        await self.stop_connection()
        if self.stopped:
            return
        if self.call_ended:
            self.ten_env.log_info(
                "ThunderPhone ended the call; not reconnecting (a reconnect "
                "would start a new call)"
            )
            return
        # The socket dropped mid-call. The call is over on ThunderPhone's
        # side, so this starts a fresh one for the participant still here.
        self.started = False
        self.session_ready = False
        await asyncio.sleep(RECONNECT_DELAY_S)
        await self.start_connection()

    # ------------------------------------------------------- inline session

    def _arm_inline_start(self) -> None:
        # Tools register through `tool_register` cmds that may land after
        # the socket is up; wait briefly for them unless audio arrives first.
        if self._start_task is None:
            self._start_task = asyncio.create_task(self._start_after_grace())

    async def _start_after_grace(self) -> None:
        try:
            await asyncio.sleep(INLINE_START_GRACE_S)
            await self._ensure_started()
        except asyncio.CancelledError:
            pass

    async def _ensure_started(self) -> None:
        """Send the session.update that starts an inline call, once."""
        if self.started or self.config.saved_agent or not self.connected:
            return
        self.started = True
        if self._start_task is not None and self._start_task is not asyncio.current_task():
            self._start_task.cancel()
        self._start_task = None
        update = inline_session_update(self.config, self.available_tools)
        self.ten_env.log_info(
            f"update session with {len(self.available_tools)} tool(s)"
        )
        await self.conn.send_request(update)

    async def _mark_session_ready(self) -> None:
        if self.session_ready:
            return
        self.session_ready = True
        await self.send_server_session_ready(MLLMServerSessionReady())

    def _note_call_id(self, call_id) -> None:
        if call_id is not None and call_id != self.call_id:
            self.call_id = call_id
            self.ten_env.log_info(f"ThunderPhone call id: {call_id}")

    def _metadata(self) -> dict:
        return {
            "session_id": self.session_id if self.session_id else "-1",
            "call_id": str(self.call_id) if self.call_id is not None else "",
        }

    def _on_call_event(self, event: CallEvent) -> None:
        self.ten_env.log_info(
            f"ThunderPhone {event.type} reason={event.reason} detail={event.detail}"
        )
        if event.type == "call.ended":
            # The server closes the socket right after this event.
            self.call_ended = True
            self.connected = False

    # ---------------------------------------------------------- client side

    async def send_audio(
        self, frame: AudioFrame, session_id: str | None
    ) -> bool:
        self.session_id = session_id
        if not self.connected or self.conn is None:
            return False
        await self._ensure_started()
        await self.conn.send_audio_data(frame.get_buf())
        return True

    async def send_client_message_item(
        self, item: MLLMClientMessageItem, session_id: str | None = None
    ) -> None:
        match item.role:
            case "user":
                await self._ensure_started()
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
                # ThunderPhone keeps the agent's own words; injected assistant
                # turns are rejected by the server.
                self.ten_env.log_warn(
                    "ThunderPhone does not accept injected assistant messages; "
                    "put the greeting in the prompt or on the saved agent"
                )
            case _:
                self.ten_env.log_error(f"Unknown role: {item.role}")

    async def send_client_create_response(
        self, session_id: str | None = None
    ) -> None:
        if self.config.saved_agent:
            # A saved agent greets and takes turns on its own.
            return
        await self._ensure_started()
        await self.conn.send_request(ResponseCreate())

    async def send_client_register_tool(self, tool: LLMToolMetadata) -> None:
        if self.config.saved_agent:
            self.ten_env.log_warn(
                f"tool {tool.name} ignored: a saved ThunderPhone agent runs "
                "its own tools; use an inline session for graph tools"
            )
            return
        if self.started:
            self.ten_env.log_warn(
                f"tool {tool.name} registered after the call started; "
                "ThunderPhone freezes tools on the first session.update"
            )
            return
        self.available_tools.append(tool)

    async def send_client_function_call_output(
        self, function_call_output: MLLMClientFunctionCallOutput
    ) -> None:
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
        for message in messages:
            self.ten_env.log_info(f"Resuming context with messages: {message}")
            await self.send_client_message_item(message)

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

#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import asyncio
from enum import Enum
import traceback
import time
from datetime import datetime

from ten import (
    AsyncExtension,
    AudioFrame,
    AsyncTenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)
from dataclasses import dataclass
from ten_ai_base.config import BaseConfig
from .realtime.connection import RealtimeApiConnection
from .realtime.struct import (
    ItemInputAudioTranscriptionDelta,
    ItemCreated,
    TranscriptionSessionCreated,
    TranscriptionSessionUpdate,
    TranscriptionSessionUpdateParams,
    ItemInputAudioTranscriptionCompleted,
    ItemInputAudioTranscriptionFailed,
    ResponseCreated,
    ResponseDone,
    ResponseOutputItemDone,
    ResponseOutputItemAdded,
    InputAudioBufferSpeechStarted,
    InputAudioBufferSpeechStopped,
    ErrorMessage,
    InputAudioTranscription,
)


class Role(str, Enum):
    User = "user"
    Assistant = "assistant"


@dataclass
class OpenAIRealtimeASRConfig(BaseConfig):
    base_uri: str = "wss://api.openai.com"
    api_key: str = ""
    path: str = "/v1/realtime"
    model: str = "gpt-4o-transcribe-latest"
    language: str = "en"
    prompt: str = ""
    server_vad: bool = True

    stream_id: int = 0
    dump: bool = False


class OpenAIRealtimeASRExtension(AsyncExtension):

    def __init__(self, name: str):
        super().__init__(name)
        self.ten_env: AsyncTenEnv = None
        self.conn = None
        self.session = None
        self.session_id = None

        self.config: OpenAIRealtimeASRConfig = None
        self.stopped: bool = False
        self.connected: bool = False

        self.stream_id: int = 0
        self.remote_stream_id: int = 0
        self.channel_name: str = ""
        self.audio_len_threshold: int = 5120

        self.buff: bytearray = b""
        self.transcript: str = ""
        self.input_end = time.time()

        self.loop = None

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        ten_env.log_debug("on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        await super().on_start(ten_env)
        ten_env.log_debug("on_start")
        self.ten_env = ten_env

        self.loop = asyncio.get_event_loop()

        self.config = await OpenAIRealtimeASRConfig.create_async(ten_env=ten_env)
        ten_env.log_info(f"config: {self.config}")

        if not self.config.api_key:
            ten_env.log_error("api_key is required")
            return

        try:
            self.conn = RealtimeApiConnection(
                ten_env=ten_env,
                base_uri=self.config.base_uri,
                path=self.config.path,
                api_key=self.config.api_key,
            )
            ten_env.log_info("Finish init client")

            self.loop.create_task(self._loop())
        except Exception as e:
            traceback.print_exc()
            self.ten_env.log_error(f"Failed to init client {e}")

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)
        ten_env.log_info("on_stop")

        self.stopped = True

    async def on_audio_frame(self, _: AsyncTenEnv, audio_frame: AudioFrame) -> None:
        try:
            stream_id = audio_frame.get_property_int("stream_id")
            if self.channel_name == "":
                self.channel_name = audio_frame.get_property_string("channel")

            if self.remote_stream_id == 0:
                self.remote_stream_id = stream_id

            frame_buf = audio_frame.get_buf()
            self._dump_audio_if_need(frame_buf, Role.User)

            await self._on_audio(frame_buf)
            if not self.config.server_vad:
                self.input_end = time.time()
        except Exception as e:
            traceback.print_exc()
            self.ten_env.log_error(f"OpenAIV2VExtension on audio frame failed {e}")

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug("on_cmd name {}".format(cmd_name))

        status = StatusCode.OK
        detail = "success"

        cmd_result = CmdResult.create(status)
        cmd_result.set_property_string("detail", detail)
        await ten_env.return_result(cmd_result, cmd)

    # Not support for now
    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        pass

    async def _loop(self):
        def get_time_ms() -> int:
            current_time = datetime.now()
            return current_time.microsecond // 1000

        try:
            await self.conn.connect()
            item_id = ""  # For truncate
            response_id = ""

            self.ten_env.log_info("Client loop started")
            async for message in self.conn.listen():
                try:
                    # self.ten_env.log_info(f"Received message: {message.type}")
                    match message:
                        case TranscriptionSessionCreated():
                            self.ten_env.log_info(
                                f"Session is created: {message.session}"
                            )
                            self.session_id = message.session.id
                            self.session = message.session
                            await self._update_session()

                            if not self.connected:
                                self.connected = True
                        case ItemInputAudioTranscriptionCompleted():
                            self.ten_env.log_info(
                                f"On request transcript {message.transcript}"
                            )
                            # self.transcript = ""
                            self._send_transcript(message.transcript, Role.User, True)
                        case ItemInputAudioTranscriptionDelta():
                            pass
                            # self.ten_env.log_info(
                            #     f"On request transcript {message.delta}"
                            # )
                            # self.transcript += message.delta
                            # self._send_transcript(self.transcript, Role.User, False)
                        case ItemInputAudioTranscriptionFailed():
                            self.ten_env.log_warn(
                                f"On request transcript failed {message.item_id} {message.error}"
                            )
                        case ItemCreated():
                            self.ten_env.log_info(f"On item created {message.item}")
                        case ResponseCreated():
                            response_id = message.response.id
                            self.ten_env.log_info(f"On response created {response_id}")
                        case ResponseDone():
                            msg_resp_id = message.response.id
                            status = message.response.status
                            if msg_resp_id == response_id:
                                response_id = ""
                            self.ten_env.log_info(
                                f"On response done {msg_resp_id} {status} {message.response.usage}"
                            )
                        case ResponseOutputItemDone():
                            self.ten_env.log_info(f"Output item done {message.item}")
                        case ResponseOutputItemAdded():
                            self.ten_env.log_info(
                                f"Output item added {message.output_index} {message.item}"
                            )
                        case InputAudioBufferSpeechStarted():
                            self.ten_env.log_info(
                                f"On server listening, in response {response_id}, last item {item_id}"
                            )
                            if self.config.server_vad:
                                await self._flush()
                            item_id = ""
                        case InputAudioBufferSpeechStopped():
                            # Only for server vad
                            self.input_end = time.time()
                            relative_start_ms = get_time_ms() - message.audio_end_ms
                            self.ten_env.log_info(
                                f"On server stop listening, {message.audio_end_ms}, relative {relative_start_ms}"
                            )
                        case ErrorMessage():
                            self.ten_env.log_error(
                                f"Error message received: {message.error}"
                            )
                        case _:
                            self.ten_env.log_debug(f"Not handled message {message}")
                except Exception as e:
                    traceback.print_exc()
                    self.ten_env.log_error(f"Error processing message: {message} {e}")

            self.ten_env.log_info("Client loop finished")
        except Exception as e:
            traceback.print_exc()
            self.ten_env.log_error(f"Failed to handle loop {e}")

        # clear so that new session can be triggered
        self.connected = False
        self.remote_stream_id = 0

        if not self.stopped:
            await self.conn.close()
            await asyncio.sleep(0.5)
            self.ten_env.log_info("Reconnect")

            self.conn = RealtimeApiConnection(
                ten_env=self.ten_env,
                base_uri=self.config.base_uri,
                path=self.config.path,
                api_key=self.config.api_key,
            )

            self.loop.create_task(self._loop())

    # Direction: IN
    async def _on_audio(self, buff: bytearray):
        self.buff += buff
        # Buffer audio
        if self.connected and len(self.buff) >= self.audio_len_threshold:
            await self.conn.send_audio_data(self.buff)
            self.buff = b""

    async def _update_session(self) -> None:
        su = TranscriptionSessionUpdate(
            session=TranscriptionSessionUpdateParams(
                input_audio_transcription=InputAudioTranscription(
                    model=self.config.model,
                    prompt=self.config.prompt,
                    language=self.config.language,
                )
            )
        )
        await self.conn.send_request(su)

    def _send_transcript(self, content: str, role: Role, is_final: bool) -> None:
        def is_punctuation(char):
            if char in [",", "，", ".", "。", "?", "？", "!", "！"]:
                return True
            return False

        def parse_sentences(sentence_fragment, content):
            sentences = []
            current_sentence = sentence_fragment
            for char in content:
                current_sentence += char
                if is_punctuation(char):
                    # Check if the current sentence contains non-punctuation characters
                    stripped_sentence = current_sentence
                    if any(c.isalnum() for c in stripped_sentence):
                        sentences.append(stripped_sentence)
                    current_sentence = ""  # Reset for the next sentence

            remain = current_sentence  # Any remaining characters form the incomplete sentence
            return sentences, remain

        def send_data(
            ten_env: AsyncTenEnv,
            sentence: str,
            stream_id: int,
            role: str,
            is_final: bool,
        ):
            try:
                d = Data.create("text_data")
                d.set_property_string("text", sentence)
                d.set_property_bool("end_of_segment", is_final)
                d.set_property_bool("is_final", is_final)
                d.set_property_string("role", role)
                d.set_property_int("stream_id", stream_id)
                ten_env.log_info(
                    f"send transcript text [{sentence}] stream_id {stream_id} is_final {is_final} end_of_segment {is_final} role {role}"
                )
                asyncio.create_task(ten_env.send_data(d))
            except Exception as e:
                ten_env.log_error(
                    f"Error send text data {role}: {sentence} {is_final} {e}"
                )

        stream_id = self.remote_stream_id if role == Role.User else 0
        try:
            if role == Role.Assistant and not is_final:
                sentences, self.transcript = parse_sentences(self.transcript, content)
                for s in sentences:
                    send_data(self.ten_env, s, stream_id, role, is_final)
            else:
                send_data(self.ten_env, content, stream_id, role, is_final)
        except Exception as e:
            self.ten_env.log_error(
                f"Error send text data {role}: {content} {is_final} {e}"
            )

    def _dump_audio_if_need(self, buf: bytearray, role: Role) -> None:
        if not self.config.dump:
            return

        with open("{}_{}.pcm".format(role, self.channel_name), "ab") as dump_file:
            dump_file.write(buf)

    async def _flush(self) -> None:
        try:
            c = Cmd.create("flush")
            await self.ten_env.send_cmd(c)
        except Exception:
            self.ten_env.log_error("Error flush")

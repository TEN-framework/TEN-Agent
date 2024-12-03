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
import numpy as np
from datetime import datetime
from typing import Iterable

from ten import (
    AudioFrame,
    AsyncTenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)
from ten.audio_frame import AudioFrameDataFmt
from ten_ai_base.const import CMD_PROPERTY_RESULT, CMD_TOOL_CALL
from ten_ai_base.llm import AsyncLLMBaseExtension
from dataclasses import dataclass, field
from ten_ai_base import BaseConfig, ChatMemory, EVENT_MEMORY_EXPIRED, EVENT_MEMORY_APPENDED, LLMUsage, LLMCompletionTokensDetails, LLMPromptTokensDetails
from ten_ai_base.types import LLMToolMetadata, LLMToolResult, LLMChatCompletionContentPartParam
from .realtime.connection import RealtimeApiConnection
from .realtime.struct import *

CMD_IN_FLUSH = "flush"
CMD_IN_ON_USER_JOINED = "on_user_joined"
CMD_IN_ON_USER_LEFT = "on_user_left"
CMD_OUT_FLUSH = "flush"

class Role(str, Enum):
    User = "user"
    Assistant = "assistant"

@dataclass
class OpenAIRealtimeConfig(BaseConfig):
    base_uri: str = "wss://api.openai.com"
    api_key: str = ""
    path: str = "/v1/realtime"
    model: str = "gpt-4o-realtime-preview"
    language: str = "en-US"
    prompt: str = ""
    temperature: float = 0.5
    max_tokens: int = 1024
    voice: str = "alloy"
    server_vad: bool = True
    audio_out: bool = True
    input_transcript: bool = True
    sample_rate: int = 24000

    vendor: str = ""
    stream_id: int = 0
    dump: bool = False
    greeting: str = ""
    max_history: int = 20
    enable_storage: bool = False

    def build_ctx(self) -> dict:
        return {
            "language": self.language,
            "model": self.model,
        }

class OpenAIRealtimeExtension(AsyncLLMBaseExtension):
    config: OpenAIRealtimeConfig = None
    stopped: bool = False
    connected: bool = False
    buffer: bytearray = b''
    memory: ChatMemory = None
    total_usage: LLMUsage = LLMUsage()
    users_count = 0

    stream_id: int = 0
    remote_stream_id: int = 0
    channel_name: str = ""
    audio_len_threshold: int = 5120

    completion_times = []
    connect_times = []
    first_token_times = []

    buff: bytearray = b''
    transcript: str = ""
    ctx: dict = {}
    input_end = time.time()

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        ten_env.log_debug("on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        await super().on_start(ten_env)
        ten_env.log_debug("on_start")

        self.loop = asyncio.get_event_loop()

        self.config = OpenAIRealtimeConfig.create(ten_env=ten_env)
        ten_env.log_info(f"config: {self.config}")

        if not self.config.api_key:
            ten_env.log_error("api_key is required")
            return

        try:
            self.memory = ChatMemory(self.config.max_history)

            if self.config.enable_storage:
                result = await ten_env.send_cmd(Cmd.create("retrieve"))
                if result.get_status_code() == StatusCode.OK:
                    try:
                        history = json.loads(result.get_property_string("response"))
                        for i in history:
                            self.memory.put(i)
                        ten_env.log_info(f"on retrieve context {history}")
                    except Exception as e:
                        ten_env.log_error("Failed to handle retrieve result {e}")
                else:
                    ten_env.log_warn("Failed to retrieve content")
            
            self.memory.on(EVENT_MEMORY_EXPIRED, self._on_memory_expired)
            self.memory.on(EVENT_MEMORY_APPENDED, self._on_memory_appended)
        
            self.conn = RealtimeApiConnection(
                ten_env=ten_env,
                base_uri=self.config.base_uri, path=self.config.path, api_key=self.config.api_key, model=self.config.model, vendor=self.config.vendor)
            ten_env.log_info(f"Finish init client")

            self.loop.create_task(self._loop())
        except Exception as e:
            traceback.print_exc()
            self.ten_env.log_error(f"Failed to init client {e}")

        self.ten_env = ten_env

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)
        ten_env.log_info("on_stop")

        self.stopped = True

    async def on_audio_frame(self, ten_env: AsyncTenEnv, audio_frame: AudioFrame) -> None:
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

        if cmd_name == CMD_IN_FLUSH:
            # Will only flush if it is client side vad
            await self._flush()
            await ten_env.send_cmd(Cmd.create(CMD_OUT_FLUSH))
            ten_env.log_info("on flush")
        elif cmd_name == CMD_IN_ON_USER_JOINED:
            self.users_count += 1
            # Send greeting when first user joined
            if self.connected and self.users_count == 1:
                await self._greeting()
        elif cmd_name == CMD_IN_ON_USER_LEFT:
            self.users_count -= 1
        else:
            # Register tool
            await super().on_cmd(ten_env, cmd)
            return

        cmd_result = CmdResult.create(status)
        cmd_result.set_property_string("detail", detail)
        ten_env.return_result(cmd_result, cmd)

    # Not support for now
    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        pass

    async def _loop(self):
        def get_time_ms() -> int:
            current_time = datetime.now()
            return current_time.microsecond // 1000

        try:
            start_time = time.time()
            await self.conn.connect()
            self.connect_times.append(time.time() - start_time)
            item_id = ""  # For truncate
            response_id = ""
            content_index = 0
            relative_start_ms = get_time_ms()
            flushed = set()

            self.ten_env.log_info("Client loop started")
            async for message in self.conn.listen():
                try:
                    # self.ten_env.log_info(f"Received message: {message.type}")
                    match message:
                        case SessionCreated():
                            self.connected = True
                            self.ten_env.log_info(f"Session is created: {message.session}")
                            self.session_id = message.session.id
                            self.session = message.session
                            await self._update_session()

                            history = self.memory.get()
                            for h in history:
                                if h["role"] == "user":
                                    await self.conn.send_request(ItemCreate(item=UserMessageItemParam(content=[{"type": ContentType.InputText, "text": h["content"]}])))
                                elif h["role"] == "assistant":
                                    await self.conn.send_request(ItemCreate(item=AssistantMessageItemParam(content=[{"type": ContentType.InputText, "text": h["content"]}])))
                            self.ten_env.log_info(f"Finish send history {history}")
                            self.memory.clear()

                            if not self.connected:
                                self.connected = True
                                await self._greeting()
                        case ItemInputAudioTranscriptionCompleted():
                            self.ten_env.log_info(f"On request transcript {message.transcript}")
                            self._send_transcript(message.transcript, Role.User, True)
                            self.memory.put({"role": "user", "content": message.transcript, "id": message.item_id})
                        case ItemInputAudioTranscriptionFailed():
                            self.ten_env.log_warn(f"On request transcript failed {message.item_id} {message.error}")
                        case ItemCreated():
                            self.ten_env.log_info(f"On item created {message.item}")
                        case ResponseCreated():
                            response_id = message.response.id
                            self.ten_env.log_info(
                                f"On response created {response_id}")
                        case ResponseDone():
                            id = message.response.id
                            status = message.response.status
                            if id == response_id:
                                response_id = ""
                            self.ten_env.log_info(
                                f"On response done {id} {status} {message.response.usage}")
                            if message.response.usage:
                                await self._update_usage(message.response.usage)
                        case ResponseAudioTranscriptDelta():
                            self.ten_env.log_info(
                                f"On response transcript delta {message.response_id} {message.output_index} {message.content_index} {message.delta}")
                            if message.response_id in flushed:
                                self.ten_env.log_warn(
                                    f"On flushed transcript delta {message.response_id} {message.output_index} {message.content_index} {message.delta}")
                                continue
                            self._send_transcript(message.delta, Role.Assistant, False)
                        case ResponseTextDelta():
                            self.ten_env.log_info(
                                f"On response text delta {message.response_id} {message.output_index} {message.content_index} {message.delta}")
                            if message.response_id in flushed:
                                self.ten_env.log_warn(
                                    f"On flushed text delta {message.response_id} {message.output_index} {message.content_index} {message.delta}")
                                continue
                            if item_id != message.item_id:
                                item_id = message.item_id
                                self.first_token_times.append(time.time() - self.input_end)
                            self._send_transcript(message.delta, Role.Assistant, False)
                        case ResponseAudioTranscriptDone():
                            self.ten_env.log_info(
                                f"On response transcript done {message.output_index} {message.content_index} {message.transcript}")
                            if message.response_id in flushed:
                                self.ten_env.log_warn(
                                    f"On flushed transcript done {message.response_id}")
                                continue
                            self.memory.put({"role": "assistant", "content": message.transcript, "id": message.item_id})
                            self.transcript = ""
                            self._send_transcript("", Role.Assistant, True)
                        case ResponseTextDone():
                            self.ten_env.log_info(
                                f"On response text done {message.output_index} {message.content_index} {message.text}")
                            if message.response_id in flushed:
                                self.ten_env.log_warn(
                                    f"On flushed text done {message.response_id}")
                                continue
                            self.completion_times.append(time.time() - self.input_end)
                            self.transcript = ""
                            self._send_transcript("", Role.Assistant, True)
                        case ResponseOutputItemDone():
                            self.ten_env.log_info(f"Output item done {message.item}")
                        case ResponseOutputItemAdded():
                            self.ten_env.log_info(
                                f"Output item added {message.output_index} {message.item}")
                        case ResponseAudioDelta():
                            if message.response_id in flushed:
                                self.ten_env.log_warn(
                                    f"On flushed audio delta {message.response_id} {message.item_id} {message.content_index}")
                                continue
                            if item_id != message.item_id:
                                item_id = message.item_id
                                self.first_token_times.append(time.time() - self.input_end)
                            content_index = message.content_index
                            self._on_audio_delta(message.delta)
                        case ResponseAudioDone():
                            self.completion_times.append(time.time() - self.input_end)
                        case InputAudioBufferSpeechStarted():
                            self.ten_env.log_info(
                                f"On server listening, in response {response_id}, last item {item_id}")
                            # Tuncate the on-going audio stream
                            end_ms = get_time_ms() - relative_start_ms
                            if item_id:
                                truncate = ItemTruncate(
                                    item_id=item_id, content_index=content_index, audio_end_ms=end_ms)
                                await self.conn.send_request(truncate)
                            if self.config.server_vad:
                                await self._flush()
                            if response_id and self.transcript:
                                transcript = self.transcript + "[interrupted]"
                                self._send_transcript(transcript, Role.Assistant, True)
                                self.transcript = ""
                                # memory leak, change to lru later
                                flushed.add(response_id)
                            item_id = ""
                        case InputAudioBufferSpeechStopped():
                            # Only for server vad
                            self.input_end = time.time()
                            relative_start_ms = get_time_ms() - message.audio_end_ms
                            self.ten_env.log_info(
                                f"On server stop listening, {message.audio_end_ms}, relative {relative_start_ms}")
                        case ResponseFunctionCallArgumentsDone():
                            tool_call_id = message.call_id
                            name = message.name
                            arguments = message.arguments
                            self.ten_env.log_info(f"need to call func {name}")
                            self.loop.create_task(self._handle_tool_call(tool_call_id, name, arguments))
                        case ErrorMessage():
                            self.ten_env.log_error(
                                f"Error message received: {message.error}")
                        case _:
                            self.ten_env.log_debug(f"Not handled message {message}")
                except Exception as e:
                    traceback.print_exc()
                    self.ten_env.log_error(
                        f"Error processing message: {message} {e}")

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
                base_uri=self.config.base_uri, path=self.config.path, api_key=self.config.api_key, model=self.config.model, vendor=self.config.vendor)
            
            self.loop.create_task(self._loop())
    
    async def _on_memory_expired(self, message: dict) -> None:
        self.ten_env.log_info(f"Memory expired: {message}")
        item_id = message.get("item_id")
        if item_id:
            await self.conn.send_request(ItemDelete(item_id=item_id))

    async def _on_memory_appended(self, message: dict) -> None:
        self.ten_env.log_info(f"Memory appended: {message}")
        if not self.config.enable_storage:
            return
        
        role = message.get("role")
        stream_id = self.remote_stream_id if role == Role.User else 0
        try:
            d = Data.create("append")
            d.set_property_string("text", message.get("content"))
            d.set_property_string("role", role)
            d.set_property_int("stream_id", stream_id)
            self.ten_env.send_data(d)
        except Exception as e:
            self.ten_env.log_error(f"Error send append_context data {message} {e}")

    # Direction: IN
    async def _on_audio(self, buff: bytearray):
        self.buff += buff
        # Buffer audio
        if self.connected and len(self.buff) >= self.audio_len_threshold:
            await self.conn.send_audio_data(self.buff)
            self.buff = b''

        self.ctx = self.config.build_ctx()
        self.ctx["greeting"] = self.config.greeting

    async def _update_session(self) -> None:
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
                    "additionalProperties": False
                }
            }

            for param in tool.parameters:
                t["parameters"]["properties"][param.name] = {
                    "type": param.type,
                    "description": param.description
                }
                if param.required:
                    t["parameters"]["required"].append(param.name)

            return t
        
        if self.available_tools:
            tool_prompt = "You have several tools that you can get help from:\n"
            for t in self.available_tools:
                tool_prompt += f"- ***{t.name}***: {t.description}"
            self.ctx["tools"] = tool_prompt
            tools = [tool_dict(t) for t in self.available_tools]
        prompt = self._replace(self.config.prompt)
        
        self.ten_env.log_info(f"update session {prompt} {tools}")
        su = SessionUpdate(session=SessionUpdateParams(
                instructions=prompt,
                model=self.config.model,
                tool_choice="auto" if self.available_tools else "none",
                tools=tools
            ))
        if self.config.audio_out:
            su.session.voice=self.config.voice
        else:
            su.session.modalities=["text"]
        
        if self.config.input_transcript:
            su.session.input_audio_transcription=InputAudioTranscription(
                    model="whisper-1")
        await self.conn.send_request(su)
    
    async def on_tools_update(self, ten_env: AsyncTenEnv, tool: LLMToolMetadata) -> None:
        """Called when a new tool is registered. Implement this method to process the new tool."""
        self.ten_env.log_info(f"on tools update {tool}")
        await self._update_session()
    
    def _replace(self, prompt: str) -> str:
        result = prompt
        for token, value in self.ctx.items():
            result = result.replace("{"+token+"}", value)
        return result

    # Direction: OUT
    def _on_audio_delta(self, delta: bytes) -> None:
        audio_data = base64.b64decode(delta)
        self.ten_env.log_debug(f"on_audio_delta audio_data len {len(audio_data)} samples {len(audio_data) // 2}")
        self._dump_audio_if_need(audio_data, Role.Assistant)

        f = AudioFrame.create("pcm_frame")
        f.set_sample_rate(self.config.sample_rate)
        f.set_bytes_per_sample(2)
        f.set_number_of_channels(1)
        f.set_data_fmt(AudioFrameDataFmt.INTERLEAVE)
        f.set_samples_per_channel(len(audio_data) // 2)
        f.alloc_buf(len(audio_data))
        buff = f.lock_buf()
        buff[:] = audio_data
        f.unlock_buf(buff)
        self.ten_env.send_audio_frame(f)

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

        def send_data(ten_env: AsyncTenEnv, sentence: str, stream_id: int, role: str, is_final: bool):
            try:
                d = Data.create("text_data")
                d.set_property_string("text", sentence)
                d.set_property_bool("end_of_segment", is_final)
                d.set_property_string("role", role)
                d.set_property_int("stream_id", stream_id)
                ten_env.log_info(
                    f"send transcript text [{sentence}] stream_id {stream_id} is_final {is_final} end_of_segment {is_final} role {role}")
                ten_env.send_data(d)
            except Exception as e:
                ten_env.log_error(f"Error send text data {role}: {sentence} {is_final} {e}")

        stream_id = self.remote_stream_id if role == Role.User else 0
        try:
            if role == Role.Assistant and not is_final:
                sentences, self.transcript = parse_sentences(self.transcript, content)
                for s in sentences:
                    send_data(self.ten_env, s, stream_id, role, is_final)
            else:
                send_data(self.ten_env, content, stream_id, role, is_final)
        except Exception as e:
            self.ten_env.log_error(f"Error send text data {role}: {content} {is_final} {e}")

    def _dump_audio_if_need(self, buf: bytearray, role: Role) -> None:
        if not self.config.dump:
            return

        with open("{}_{}.pcm".format(role, self.channel_name), "ab") as dump_file:
            dump_file.write(buf)

    async def _handle_tool_call(self, tool_call_id: str, name: str, arguments: str) -> None:
        self.ten_env.log_info(f"_handle_tool_call {tool_call_id} {name} {arguments}")
        cmd: Cmd = Cmd.create(CMD_TOOL_CALL)
        cmd.set_property_string("name", name)
        cmd.set_property_from_json("arguments", arguments)
        result: CmdResult = await self.ten_env.send_cmd(cmd)

        tool_response = ItemCreate(
            item=FunctionCallOutputItemParam(
                call_id=tool_call_id,
                output="{\"success\":false}",
            )
        )
        if result.get_status_code() == StatusCode.OK:
            tool_result: LLMToolResult = json.loads(
                result.get_property_to_json(CMD_PROPERTY_RESULT))
        
            result_content = tool_result["content"]
            tool_response.item.output = json.dumps(self._convert_to_content_parts(result_content))
            self.ten_env.log_info(f"tool_result: {tool_call_id} {tool_result}")
        else:
            self.ten_env.log_error(f"Tool call failed")
        
        await self.conn.send_request(tool_response)
        await self.conn.send_request(ResponseCreate())
        self.ten_env.log_info(f"_remote_tool_call finish {name} {arguments}")
    
    def _greeting_text(self) -> str:
        text = "Hi, there."
        if self.config.language == "zh-CN":
            text = "你好。"
        elif self.config.language == "ja-JP":
            text = "こんにちは"
        elif self.config.language == "ko-KR":
            text = "안녕하세요"
        return text

    
    def _convert_tool_params_to_dict(self, tool: LLMToolMetadata):
        json = {
            "type": "object",
            "properties": {},
            "required": []
        }

        for param in tool.parameters:
            json["properties"][param.name] = {
                "type": param.type,
                "description": param.description
            }
            if param.required:
                json["required"].append(param.name)

        return json
    
    
    def _convert_to_content_parts(self, content: Iterable[LLMChatCompletionContentPartParam]):
        content_parts = []


        if isinstance(content, str):
            content_parts.append({
                "type": "text",
                "text": content
            })
        else:
            for part in content:
                # Only text content is supported currently for v2v model
                if part["type"] == "text":
                    content_parts.append(part)
        return content_parts
    
    async def _greeting(self) -> None:
        if self.config.greeting:
            text = self._greeting_text()
            await self.conn.send_request(ItemCreate(item=UserMessageItemParam(content=[{"type": ContentType.InputText, "text": text}])))
            await self.conn.send_request(ResponseCreate())

    async def _flush(self) -> None:
        try:
            c = Cmd.create("flush")
            await self.ten_env.send_cmd(c)
        except:
            self.ten_env.log_error(f"Error flush")
        
    async def _update_usage(self, usage: dict) -> None:
        self.total_usage.completion_tokens += usage.get("output_tokens")
        self.total_usage.prompt_tokens += usage.get("input_tokens")
        self.total_usage.total_tokens += usage.get("total_tokens")
        if not self.total_usage.completion_tokens_details:
            self.total_usage.completion_tokens_details = LLMCompletionTokensDetails()
        if not self.total_usage.prompt_tokens_details:
            self.total_usage.prompt_tokens_details = LLMPromptTokensDetails()

        if usage.get("output_token_details"):
            self.total_usage.completion_tokens_details.accepted_prediction_tokens += usage["output_token_details"].get("text_tokens")
            self.total_usage.completion_tokens_details.audio_tokens += usage["output_token_details"].get("audio_tokens")
        
        if usage.get("input_token_details:"):
            self.total_usage.prompt_tokens_details.audio_tokens += usage["input_token_details"].get("audio_tokens")
            self.total_usage.prompt_tokens_details.cached_tokens += usage["input_token_details"].get("cached_tokens")
            self.total_usage.prompt_tokens_details.text_tokens += usage["input_token_details"].get("text_tokens")

        self.ten_env.log_info(f"total usage: {self.total_usage}")

        data = Data.create("llm_stat")
        data.set_property_from_json("usage", json.dumps(self.total_usage.model_dump()))
        if self.connect_times and self.completion_times and self.first_token_times:
            data.set_property_from_json("latency", json.dumps({
                "connection_latency_95": np.percentile(self.connect_times, 95),
                "completion_latency_95": np.percentile(self.completion_times, 95),
                "first_token_latency_95": np.percentile(self.first_token_times, 95),
                "connection_latency_99": np.percentile(self.connect_times, 99),
                "completion_latency_99": np.percentile(self.completion_times, 99),
                "first_token_latency_99": np.percentile(self.first_token_times, 99)
            }))
        self.ten_env.send_data(data)

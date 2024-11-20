#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import asyncio
import threading
import base64
from datetime import datetime
from typing import Awaitable
from functools import partial

from ten import (
    AudioFrame,
    VideoFrame,
    Extension,
    TenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)
from ten.audio_frame import AudioFrameDataFmt
from .log import logger

from .tools import ToolRegistry
from .conf import RealtimeApiConfig, BASIC_PROMPT, DEFAULT_GREETING
from .realtime.connection import RealtimeApiConnection
from .realtime.struct import *
from .tools import ToolRegistry

# properties
PROPERTY_API_KEY = "api_key"  # Required
PROPERTY_BASE_URI = "base_uri"  # Optional
PROPERTY_PATH = "path"  # Optional
PROPERTY_VENDOR = "vendor"  # Optional
PROPERTY_MODEL = "model"  # Optional
PROPERTY_SYSTEM_MESSAGE = "system_message"  # Optional
PROPERTY_TEMPERATURE = "temperature"  # Optional
PROPERTY_MAX_TOKENS = "max_tokens"  # Optional
PROPERTY_ENABLE_STORAGE = "enable_storage"  # Optional
PROPERTY_VOICE = "voice"  # Optional
PROPERTY_AUDIO_OUT = "audio_out"  # Optional
PROPERTY_INPUT_TRANSCRIPT = "input_transcript"
PROPERTY_SERVER_VAD = "server_vad"  # Optional
PROPERTY_STREAM_ID = "stream_id"
PROPERTY_LANGUAGE = "language"
PROPERTY_DUMP = "dump"
PROPERTY_GREETING = "greeting"
PROPERTY_HISTORY = "history"

DEFAULT_VOICE = Voices.Alloy

CMD_TOOL_REGISTER = "tool_register"
CMD_TOOL_CALL = "tool_call"
CMD_PROPERTY_NAME = "name"
CMD_PROPERTY_ARGS = "args"

TOOL_REGISTER_PROPERTY_NAME = "name"
TOOL_REGISTER_PROPERTY_DESCRIPTON = "description"
TOOL_REGISTER_PROPERTY_PARAMETERS = "parameters"


class Role(str, Enum):
    User = "user"
    Assistant = "assistant"


class OpenAIV2VExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)

        # handler
        self.loop = asyncio.new_event_loop()
        self.thread: threading.Thread = None

        # openai related
        self.config: RealtimeApiConfig = RealtimeApiConfig()
        self.conn: RealtimeApiConnection = None
        self.connected: bool = False
        self.session_id: str = ""
        self.session: SessionUpdateParams = None
        self.last_updated = None
        self.ctx: dict = {}

        # audo related
        self.sample_rate: int = 24000
        self.out_audio_buff: bytearray = b''
        self.audio_len_threshold: int = 10240
        self.transcript: str = ''

        # misc.
        self.greeting : str = ""
        self.vendor: str = ""
        # max history store in context
        self.max_history = 0
        self.history = []
        self.enable_storage: bool = False
        self.retrieved = []
        self.remote_stream_id: int = 0
        self.stream_id: int = 0
        self.channel_name: str = ""
        self.dump: bool = False
        self.registry = ToolRegistry()

    def on_start(self, ten_env: TenEnv) -> None:
        logger.info("OpenAIV2VExtension on_start")

        self._fetch_properties(ten_env)

        # Start async handler
        def start_event_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        self.thread = threading.Thread(
            target=start_event_loop, args=(self.loop,))
        self.thread.start()

        if self.enable_storage:
            r = Cmd.create("retrieve")
            ten_env.send_cmd(r, self.on_retrieved)

        # self._register_local_tools()

        asyncio.run_coroutine_threadsafe(self._init_connection(), self.loop)

        ten_env.on_start_done()

    def on_stop(self, ten_env: TenEnv) -> None:
        logger.info("OpenAIV2VExtension on_stop")

        self.connected = False

        if self.thread:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join()
            self.thread = None

        ten_env.on_stop_done()

    def on_retrieved(self, ten_env:TenEnv, result:CmdResult) -> None:
        if result.get_status_code() == StatusCode.OK:
            try:
                history = json.loads(result.get_property_string("response"))
                if not self.last_updated:
                    # cache the history
                    # FIXME need to have json
                    if self.max_history and len(history) > self.max_history:
                        self.retrieved = history[len(history) - self.max_history:]
                    else:
                        self.retrieved = history
                logger.info(f"on retrieve context {history} {self.retrieved}")
            except:
                logger.exception("Failed to handle retrieve result")
        else:
            logger.warning("Failed to retrieve content")

    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        try:
            stream_id = audio_frame.get_property_int("stream_id")
            # logger.debug(f"on_audio_frame {stream_id}")
            if self.channel_name == "":
                self.channel_name = audio_frame.get_property_string("channel")

            if self.remote_stream_id == 0:
                self.remote_stream_id = stream_id
                asyncio.run_coroutine_threadsafe(
                    self._run_client_loop(ten_env), self.loop)
                logger.info(f"Start session for {stream_id}")

            frame_buf = audio_frame.get_buf()
            self._dump_audio_if_need(frame_buf, Role.User)

            asyncio.run_coroutine_threadsafe(
                self._on_audio(frame_buf), self.loop)
        except:
            logger.exception(f"OpenAIV2VExtension on audio frame failed")

    # Should not be here
    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        pass

    # Should not be here
    def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()

        if cmd_name == CMD_TOOL_REGISTER:
            self._on_tool_register(ten_env, cmd)

        cmd_result = CmdResult.create(StatusCode.OK)
        ten_env.return_result(cmd_result, cmd)

    # Should not be here
    def on_data(self, ten_env: TenEnv, data: Data) -> None:
        # text input
        text = data.get_property_string("text")
        
        asyncio.run_coroutine_threadsafe(self._send_text_item(text), self.loop)

    async def _send_text_item(self, text: str):
        await self.conn.send_request(ItemCreate(item=UserMessageItemParam(content=[{"type": ContentType.InputText, "text": text}])))
        await self.conn.send_request(ResponseCreate())

    def on_config_changed(self) -> None:
        # update session again
        return

    async def _init_connection(self):
        try:
            self.conn = RealtimeApiConnection(
                base_uri=self.config.base_uri, path=self.config.path, api_key=self.config.api_key, model=self.config.model, vendor=self.vendor, verbose=False)
            logger.info(f"Finish init client {self.config} {self.conn}")
        except:
            logger.exception(f"Failed to create client {self.config}")

    async def _run_client_loop(self, ten_env: TenEnv):
        def get_time_ms() -> int:
            current_time = datetime.now()
            return current_time.microsecond // 1000

        try:
            await self.conn.connect()
            self.connected = True
            item_id = ""  # For truncate
            response_id = ""
            content_index = 0
            relative_start_ms = get_time_ms()
            flushed = set()

            logger.info("Client loop started")
            async for message in self.conn.listen():
                try:
                    logger.info(f"Received message: {message.type}")
                    match message:
                        case SessionCreated():
                            logger.info(
                                f"Session is created: {message.session}")
                            self.session_id = message.session.id
                            self.session = message.session
                            update_msg = self._update_session()
                            await self.conn.send_request(update_msg)

                            if self.retrieved:
                                await self._append_retrieve()
                                logger.info(f"after append retrieve: {len(self.retrieved)}")

                            text = self._greeting_text()
                            if self.greeting:
                                text = self.greeting
                            await self.conn.send_request(ItemCreate(item=UserMessageItemParam(content=[{"type": ContentType.InputText, "text": text}])))
                            await self.conn.send_request(ResponseCreate())

                            # update_conversation = self.update_conversation()
                            # await self.conn.send_request(update_conversation)
                        case ItemInputAudioTranscriptionCompleted():
                            logger.info(
                                f"On request transcript {message.transcript}")
                            self._send_transcript(
                                ten_env, message.transcript, Role.User, True)
                            self._append_context(ten_env, message.transcript, self.remote_stream_id, Role.User)
                        case ItemInputAudioTranscriptionFailed():
                            logger.warning(
                                f"On request transcript failed {message.item_id} {message.error}")
                        case ItemCreated():
                            logger.info(f"On item created {message.item}")

                            if self.max_history and ("status" not in message.item or message.item["status"] == "completed"):
                                # need maintain the history
                                await self._append_history(message.item)
                        case ResponseCreated():
                            response_id = message.response.id
                            logger.info(
                                f"On response created {response_id}")
                        case ResponseDone():
                            id = message.response.id
                            status = message.response.status
                            logger.info(
                                f"On response done {id} {status}")
                            for item in message.response.output:
                                await self._append_history(item)
                            if id == response_id:
                                response_id = ""
                        case ResponseAudioTranscriptDelta():
                            logger.info(
                                f"On response transcript delta {message.response_id} {message.output_index} {message.content_index} {message.delta}")
                            if message.response_id in flushed:
                                logger.warning(
                                    f"On flushed transcript delta {message.response_id} {message.output_index} {message.content_index} {message.delta}")
                                continue
                            self._send_transcript(
                                ten_env, message.delta, Role.Assistant, False)
                        case ResponseTextDelta():
                            logger.info(
                                f"On response text delta {message.response_id} {message.output_index} {message.content_index} {message.delta}")
                            if message.response_id in flushed:
                                logger.warning(
                                    f"On flushed text delta {message.response_id} {message.output_index} {message.content_index} {message.delta}")
                                continue
                            self._send_transcript(
                                ten_env, message.delta, Role.Assistant, False)
                        case ResponseAudioTranscriptDone():
                            logger.info(
                                f"On response transcript done {message.output_index} {message.content_index} {message.transcript}")
                            if message.response_id in flushed:
                                logger.warning(
                                    f"On flushed transcript done {message.response_id}")
                                continue
                            self._append_context(ten_env, message.transcript, self.stream_id, Role.Assistant)
                            self.transcript = ""
                            self._send_transcript(
                                ten_env, "", Role.Assistant, True)
                        case ResponseTextDone():
                            logger.info(
                                f"On response text done {message.output_index} {message.content_index} {message.text}")
                            if message.response_id in flushed:
                                logger.warning(
                                    f"On flushed text done {message.response_id}")
                                continue
                            self.transcript = ""
                            self._send_transcript(
                                ten_env, "", Role.Assistant, True)
                        case ResponseOutputItemDone():
                            logger.info(f"Output item done {message.item}")
                        case ResponseOutputItemAdded():
                            logger.info(
                                f"Output item added {message.output_index} {message.item}")
                        case ResponseAudioDelta():
                            if message.response_id in flushed:
                                logger.warning(
                                    f"On flushed audio delta {message.response_id} {message.item_id} {message.content_index}")
                                continue
                            item_id = message.item_id
                            content_index = message.content_index
                            self._on_audio_delta(ten_env, message.delta)
                        case InputAudioBufferSpeechStarted():
                            logger.info(
                                f"On server listening, in response {response_id}, last item {item_id}")
                            # Tuncate the on-going audio stream
                            end_ms = get_time_ms() - relative_start_ms
                            if item_id:
                                truncate = ItemTruncate(
                                    item_id=item_id, content_index=content_index, audio_end_ms=end_ms)
                                await self.conn.send_request(truncate)
                            self._flush(ten_env)
                            if response_id and self.transcript:
                                transcript = self.transcript + "[interrupted]"
                                self._send_transcript(
                                    ten_env, transcript, Role.Assistant, True)
                                self.transcript = ""
                                # memory leak, change to lru later
                                flushed.add(response_id)
                            item_id = ""
                        case InputAudioBufferSpeechStopped():
                            relative_start_ms = get_time_ms() - message.audio_end_ms
                            logger.info(
                                f"On server stop listening, {message.audio_end_ms}, relative {relative_start_ms}")
                        case ResponseFunctionCallArgumentsDone():
                            tool_call_id = message.call_id
                            name = message.name
                            arguments = message.arguments
                            logger.info(f"need to call func {name}")
                            # TODO rebuild this into async, or it will block the thread
                            await self.registry.on_func_call(tool_call_id, name, arguments, self._on_tool_output)
                        case ErrorMessage():
                            logger.error(
                                f"Error message received: {message.error}")
                        case _:
                            logger.debug(f"Not handled message {message}")
                except:
                    logger.exception(
                        f"Error processing message: {message}")

            logger.info("Client loop finished")
        except:
            logger.exception(f"Failed to handle loop")

        # clear so that new session can be triggered
        self.connected = False
        self.remote_stream_id = 0
    
    async def _append_history(self, item: ItemParam) -> None:
        logger.info(f"append item {item}")
        self.history.append(item["id"])
        if len(self.history) > self.max_history:
            to_remove = self.history[0]
            logger.info(f"remove history {to_remove}")
            await self.conn.send_request(ItemDelete(item_id=to_remove))
            self.history = self.history[1:]

    async def _on_audio(self, buff: bytearray):
        self.out_audio_buff += buff
        # Buffer audio
        if len(self.out_audio_buff) >= self.audio_len_threshold and self.session_id != "":
            await self.conn.send_audio_data(self.out_audio_buff)
            # logger.info(
            #     f"Send audio frame to OpenAI: {len(self.out_audio_buff)}")
            self.out_audio_buff = b''

    def _fetch_properties(self, ten_env: TenEnv):
        try:
            api_key = ten_env.get_property_string(PROPERTY_API_KEY)
            self.config.api_key = api_key
        except Exception as err:
            logger.info(
                f"GetProperty required {PROPERTY_API_KEY} failed, err: {err}")
            return

        try:
            base_uri = ten_env.get_property_string(PROPERTY_BASE_URI)
            if base_uri:
                self.config.base_uri = base_uri
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_BASE_URI} error: {err}")
        
        try:
            path = ten_env.get_property_string(PROPERTY_PATH)
            if path:
                self.config.path = path
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_PATH} error: {err}")
        
        try:
            self.vendor = ten_env.get_property_string(PROPERTY_VENDOR)
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_VENDOR} error: {err}") 

        try:
            model = ten_env.get_property_string(PROPERTY_MODEL)
            if model:
                self.config.model = model
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_MODEL} error: {err}")

        try:
            system_message = ten_env.get_property_string(
                PROPERTY_SYSTEM_MESSAGE)
            if system_message:
                self.config.instruction = BASIC_PROMPT + "\n" + system_message
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_SYSTEM_MESSAGE} error: {err}")

        try:
            temperature = ten_env.get_property_float(PROPERTY_TEMPERATURE)
            self.config.temperature = float(temperature)
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_TEMPERATURE} failed, err: {err}"
            )

        try:
            audio_out = ten_env.get_property_bool(PROPERTY_AUDIO_OUT)
            self.config.audio_out = audio_out
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_AUDIO_OUT} failed, err: {err}"
            )

        try:
            input_transcript = ten_env.get_property_bool(PROPERTY_INPUT_TRANSCRIPT)
            self.config.input_transcript = input_transcript
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_INPUT_TRANSCRIPT} failed, err: {err}"
            )

        try:
            max_tokens = ten_env.get_property_int(PROPERTY_MAX_TOKENS)
            if max_tokens > 0:
                self.config.max_tokens = int(max_tokens)
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_MAX_TOKENS} failed, err: {err}"
            )
        
        try:
            self.enable_storage = ten_env.get_property_bool(PROPERTY_ENABLE_STORAGE)
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_ENABLE_STORAGE} failed, err: {err}"
            )

        try:
            voice = ten_env.get_property_string(PROPERTY_VOICE)
            if voice:
                # v = DEFAULT_VOICE
                # if voice == "alloy":
                #     v = Voices.Alloy
                # elif voice == "echo":
                #     v = Voices.Echo
                # elif voice == "shimmer":
                #     v = Voices.Shimmer
                self.config.voice = voice
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_VOICE} error: {err}")

        try:
            language = ten_env.get_property_string(PROPERTY_LANGUAGE)
            if language:
                self.config.language = language
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_LANGUAGE} error: {err}")

        try:
            greeting = ten_env.get_property_string(PROPERTY_GREETING)
            if greeting:
                self.greeting = greeting
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_GREETING} error: {err}")

        try:
            server_vad = ten_env.get_property_bool(PROPERTY_SERVER_VAD)
            self.config.server_vad = server_vad
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_SERVER_VAD} failed, err: {err}"
            )

        try:
            self.dump = ten_env.get_property_bool(PROPERTY_DUMP)
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_DUMP} error: {err}")
        
        try:
            history = ten_env.get_property_int(PROPERTY_HISTORY)
            if history:
                self.max_history = history
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_HISTORY} error: {err}")

        self.ctx = self.config.build_ctx()
        self.ctx["greeting"] = self.greeting

    def _update_session(self) -> SessionUpdate:
        self.ctx["tools"] = self.registry.to_prompt()
        prompt = self._replace(self.config.instruction)
        self.last_updated = datetime.now()
        su = SessionUpdate(session=SessionUpdateParams(
                instructions=prompt,
                model=self.config.model,
                tool_choice="auto",
                tools=self.registry.get_tools()
            ))
        if self.config.audio_out:
            su.session.voice=self.config.voice
        else:
            su.session.modalities=["text"]
        
        if self.config.input_transcript:
            su.session.input_audio_transcription=InputAudioTranscription(
                    model="whisper-1")
        return su
    
    async def _append_retrieve(self):
        if self.retrieved:
            for r in self.retrieved:
                if r["role"] == MessageRole.User:
                    await self.conn.send_request(ItemCreate(item=UserMessageItemParam(content=[{"type": ContentType.InputText, "text": r["input"]}])))
                elif r["role"] == MessageRole.Assistant:
                    await self.conn.send_request(ItemCreate(item=AssistantMessageItemParam(content=[{"type": ContentType.InputText, "text": r["input"]}])))

    '''
    def _update_conversation(self) -> UpdateConversationConfig:
        prompt = self._replace(self.config.system_message)
        conf = UpdateConversationConfig()
        conf.system_message = prompt
        conf.temperature = self.config.temperature
        conf.max_tokens = self.config.max_tokens
        conf.tool_choice = "none"
        conf.disable_audio = False
        conf.output_audio_format = AudioFormats.PCM16
        return conf
    '''

    def _replace(self, prompt: str) -> str:
        result = prompt
        for token, value in self.ctx.items():
            result = result.replace("{"+token+"}", value)
        return result

    def _on_audio_delta(self, ten_env: TenEnv, delta: bytes) -> None:
        audio_data = base64.b64decode(delta)
        logger.debug("on_audio_delta audio_data len {} samples {}".format(
            len(audio_data), len(audio_data) // 2))
        self._dump_audio_if_need(audio_data, Role.Assistant)

        f = AudioFrame.create("pcm_frame")
        f.set_sample_rate(self.sample_rate)
        f.set_bytes_per_sample(2)
        f.set_number_of_channels(1)
        f.set_data_fmt(AudioFrameDataFmt.INTERLEAVE)
        f.set_samples_per_channel(len(audio_data) // 2)
        f.alloc_buf(len(audio_data))
        buff = f.lock_buf()
        buff[:] = audio_data
        f.unlock_buf(buff)
        ten_env.send_audio_frame(f)

    def _append_context(self, ten_env: TenEnv, sentence: str, stream_id: int, role: str):
        if not self.enable_storage:
            return
        
        try:
            d = Data.create("append")
            d.set_property_string("text", sentence)
            d.set_property_string("role", role)
            d.set_property_int("stream_id", stream_id)
            logger.info(f"append_contexttext [{sentence}] stream_id {stream_id} role {role}")
            ten_env.send_data(d)
        except:
            logger.exception(f"Error send append_context data {role}: {sentence}")

    def _send_transcript(self, ten_env: TenEnv, content: str, role: Role, is_final: bool) -> None:
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

        def send_data(ten_env: TenEnv, sentence: str, stream_id: int, role: str, is_final: bool):
            try:
                d = Data.create("text_data")
                d.set_property_string("text", sentence)
                d.set_property_bool("end_of_segment", is_final)
                d.set_property_string("role", role)
                d.set_property_int("stream_id", stream_id)
                logger.info(
                    f"send transcript text [{sentence}] stream_id {stream_id} is_final {is_final} end_of_segment {is_final} role {role}")
                ten_env.send_data(d)
            except:
                logger.exception(
                    f"Error send text data {role}: {sentence} {is_final}")

        stream_id = self.remote_stream_id if role == Role.User else 0
        try:
            if role == Role.Assistant and not is_final:
                sentences, self.transcript = parse_sentences(self.transcript, content)
                for s in sentences:
                    send_data(ten_env, s, stream_id, role, is_final)
            else:
                send_data(ten_env, content, stream_id, role, is_final)
        except:
            logger.exception(f"Error send text data {role}: {content} {is_final}")

    def _flush(self, ten_env: TenEnv) -> None:
        try:
            c = Cmd.create("flush")
            ten_env.send_cmd(c, lambda ten, result: logger.info("flush done"))
        except:
            logger.exception(f"Error flush")

    def _dump_audio_if_need(self, buf: bytearray, role: Role) -> None:
        if not self.dump:
            return

        with open("{}_{}.pcm".format(role, self.channel_name), "ab") as dump_file:
            dump_file.write(buf)

    #def _register_local_tools(self) -> None:
    #    self.ctx["tools"] = self.registry.to_prompt()

    def _on_tool_register(self, ten_env: TenEnv, cmd: Cmd):
        try:
            name = cmd.get_property_string(TOOL_REGISTER_PROPERTY_NAME)
            description = cmd.get_property_string(
                TOOL_REGISTER_PROPERTY_DESCRIPTON)
            pstr = cmd.get_property_string(TOOL_REGISTER_PROPERTY_PARAMETERS)
            parameters = json.loads(pstr)
            p = partial(self._remote_tool_call, ten_env)
            self.registry.register(
                name=name, description=description,
                callback=p,
                parameters=parameters)
            logger.info(f"on tool register {name} {description}")
            self.on_config_changed()
        except:
            logger.exception(f"Failed to register")

    async def _remote_tool_call(self, ten_env: TenEnv, name: str, args: str, callback: Awaitable):
        logger.info(f"_remote_tool_call bw {name} {args}")
        c = Cmd.create(f"{CMD_TOOL_CALL}_{name}")
        c.set_property_string(CMD_PROPERTY_NAME, name)
        c.set_property_string(CMD_PROPERTY_ARGS, args)
        ten_env.send_cmd(c, lambda ten, result: asyncio.run_coroutine_threadsafe(
                callback(result), self.loop))
        logger.info(f"_remote_tool_call finish {name} {args}")
    
    async def _on_tool_output(self, tool_call_id:str,  result:CmdResult):
        state = result.get_status_code()
        tool_response = ItemCreate(
            item=FunctionCallOutputItemParam(
                call_id=tool_call_id,
                output="{\"success\":false}",
            )
        )
        try:
            if state == StatusCode.OK:
                response = result.get_property_string("response")
                logger.info(f"_on_tool_output {tool_call_id} {response}")
            
                tool_response = ItemCreate(
                    item=FunctionCallOutputItemParam(
                        call_id=tool_call_id,
                        output=response,
                    )
                )
            else:
                logger.error(f"Failed to call function {tool_call_id}")
                
            await self.conn.send_request(tool_response)
            await self.conn.send_request(ResponseCreate())
        except:
            logger.exception("Failed to handle tool output")

    def _greeting_text(self) -> str:
        text = "Hi, there."
        if self.config.language == "zh-CN":
            text = "你好。"
        elif self.config.language == "ja-JP":
            text = "こんにちは"
        elif self.config.language == "ko-KR":
            text = "안녕하세요"
        return text

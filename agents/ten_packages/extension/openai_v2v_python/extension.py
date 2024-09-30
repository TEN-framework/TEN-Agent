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
from .client import RealtimeApiClient, RealtimeApiConfig
from .messages import *

# properties
PROPERTY_API_KEY = "api_key"  # Required
PROPERTY_MODEL = "model"  # Optional
PROPERTY_SYSTEM_MESSAGE = "system_message"  # Optional
PROPERTY_TEMPERATURE = "temperature"  # Optional
PROPERTY_MAX_TOKENS = "max_tokens"  # Optional
PROPERTY_VOICE = "voice" #Optional
PROPERTY_SERVER_VAD = "server_vad" #Optional
PROPERTY_STREAM_ID = "stream_id"
PROPERTY_LANGUAGE = "language"

DATA_TEXT_DATA = "text_data"
CMD_FLUSH = "flush"
AUDIO_PCM_FRAME = "pcm_frame"

ROLE_ASSISTANT = "assistant"
ROLE_USER = "user"

class OpenAIV2VExtension(Extension):
    # handler
    queue = asyncio.Queue(maxsize=3000)
    loop = None
    thread: threading.Thread = None
    client: RealtimeApiClient = None
    connected: bool = False
    
    # openai related
    config: RealtimeApiConfig = None
    session_id: str = ""

    # audo related
    sample_rate : int = 24000
    out_audio_buff: bytearray = b''
    audio_len_threshold : int = 10240
    transcript: str = ''

    # agora related
    stream_id: int = 0
    remote_stream_id: int = 0
    ctx: dict = {}

    def on_init(self, ten_env: TenEnv) -> None:
        logger.info("OpenAIV2VExtension on_init")
        self.config = RealtimeApiConfig()
        self.loop = asyncio.new_event_loop()
        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        logger.info("OpenAIV2VExtension on_start")

        self.fetch_properties(ten_env)

        # Start async handler
        def start_event_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()
        
        self.thread = threading.Thread(target=start_event_loop, args=(self.loop,))
        self.thread.start()

        asyncio.run_coroutine_threadsafe(self.init_client(), self.loop)

        ten_env.on_start_done()

    def on_stop(self, ten_env: TenEnv) -> None:
        logger.info("OpenAIV2VExtension on_stop")

        self.connected = False

        if self.thread:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join()

        ten_env.on_stop_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        logger.info("OpenAIV2VExtension on_deinit")
        ten_env.on_deinit_done()

    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        try:
            # frame_name = audio_frame.get_name()
            stream_id = audio_frame.get_property_int("stream_id")
            # logger.info(f"OpenAIV2VExtension on_audio_frame {frame_name} {stream_id}")
            if self.remote_stream_id == 0:
                self.remote_stream_id = stream_id
                asyncio.run_coroutine_threadsafe(self.run_client_loop(ten_env), self.loop)
                logger.info(f"Start session for {stream_id}")
            
            frame_buf = audio_frame.get_buf()
            with open("audio_stt_in.pcm", "ab") as dump_file:
                dump_file.write(frame_buf)
            asyncio.run_coroutine_threadsafe(self.on_audio(frame_buf), self.loop)
        except:
            logger.exception(f"OpenAIV2VExtension on audio frame failed")

    # Should not be here
    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        pass

    # Should not be here
    def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        cmd_result = CmdResult.create(StatusCode.OK)
        ten_env.return_result(cmd_result, cmd)

    # Should not be here
    def on_data(self, ten_env: TenEnv, data: Data) -> None:
        pass

    async def init_client(self):
        try:
            self.client = RealtimeApiClient(base_uri=self.config.base_uri, api_key=self.config.api_key, model=self.config.model)
            logger.info(f"Finish init client {self.config} {self.client}")
        except:
            logger.exception(f"Failed to create client {self.config}")

    async def run_client_loop(self, ten_env: TenEnv):
        def get_time_ms() -> int:
            current_time = datetime.now()
            return current_time.microsecond // 1000

        try:
            await self.client.connect()
            self.connected = True
            item_id = "" # For truncate
            response_id = ""
            content_index = 0
            relative_start_ms = get_time_ms()
            flushed = set()

            logger.info("Client loop started")
            async for message in self.client.listen():
                try:
                    logger.info(f"Received message: {message.type}")
                    match message:
                        case SessionCreated():
                            logger.info(f"Session is created: {message.session.id}")
                            self.session_id = message.session.id
                            update_msg = self.update_session()
                            await self.client.send_message(update_msg)

                            update_conversation = self.update_conversation()
                            await self.client.send_message(update_conversation)
                        case ItemInputAudioTranscriptionCompleted():
                            logger.info(f"On request transript {message.transcript}")
                            self.send_transcript(ten_env, message.transcript, ROLE_USER, True)
                        case ItemInputAudioTranscriptionFailed():
                            logger.warning(f"On request transript failed {message.item_id} {message.error}")
                        case ItemCreated():
                            logger.info(f"On item created {message.item}")
                        case ResponseCreated():
                            logger.info(f"On response created {message.response.id}")
                            response_id = message.response.id
                        case ResponseDone():
                            logger.info(f"On response done {message.response.id} {message.response.status}")
                            if message.response.id == response_id:
                                response_id = ""
                        case ResponseAudioTranscriptDelta():
                            logger.info(f"On response transript delta {message.response_id} {message.output_index} {message.content_index} {message.delta}")
                            if message.response_id in flushed:
                                logger.warning(f"On flushed transript delta {message.response_id} {message.output_index} {message.content_index} {message.delta}")
                                continue
                            self.transcript += message.delta
                            self.send_transcript(ten_env, self.transcript, ROLE_ASSISTANT, False)
                        case ResponseAudioTranscriptDone():
                            logger.info(f"On response transript done {message.output_index} {message.content_index} {message.transcript}")
                            if message.response_id in flushed:
                                logger.warning(f"On flushed transript done {message.response_id}")
                                continue
                            self.transcript = ""
                            self.send_transcript(ten_env, message.transcript, ROLE_ASSISTANT, True)
                        case ResponseOutputItemDone():
                            logger.info(f"Output item done {message.item}")
                        case ResponseOutputItemAdded():
                            logger.info(f"Output item added {message.output_index} {message.item.id}")
                        case ResponseAudioDelta():
                            if message.response_id in flushed:
                                logger.warning(f"On flushed audio delta {message.response_id} {message.item_id} {message.content_index}")
                                continue
                            item_id = message.item_id
                            content_index = message.content_index
                            self.on_audio_delta(ten_env, message.delta)
                        case InputAudioBufferSpeechStarted():
                            logger.info(f"On server listening, in response {response_id}, last item {item_id}")
                            # Tuncate the on-going audio stream
                            end_ms = get_time_ms() - relative_start_ms
                            if item_id:
                                truncate = ItemTruncate(item_id=item_id, content_index=content_index, audio_end_ms=end_ms)
                                await self.client.send_message(truncate)
                            self.flush(ten_env)
                            if response_id:
                                transcript = self.transcript + "[interrupted]"
                                self.send_transcript(ten_env, transcript, ROLE_ASSISTANT, True)
                                self.transcript = ""
                                flushed.add(response_id) # memory leak, change to lru later
                            item_id = ""
                        case InputAudioBufferSpeechStopped():
                            relative_start_ms = get_time_ms() - message.audio_end_ms
                            logger.info(f"On server stop listening, {message.audio_end_ms}, relative {relative_start_ms}")
                        case ErrorMessage():
                            logger.error(f"Error message received: {message.error}")
                        case _:
                            logger.debug(f"Not handled message {message}")
                except:
                    logger.exception(f"Error processing message: {message.type}")
            
            logger.info("Client loop finished")
        except:
            logger.exception(f"Failed to handle loop")

    async def on_audio(self, buff: bytearray):
        self.out_audio_buff += buff
        # Buffer audio
        if len(self.out_audio_buff) >= self.audio_len_threshold and self.session_id != "":
            await self.client.send_audio_data(self.out_audio_buff)
            logger.info(f"Send audio frame to OpenAI: {len(self.out_audio_buff)}")
            self.out_audio_buff = b''

    def fetch_properties(self, ten_env: TenEnv):
        try:
            api_key = ten_env.get_property_string(PROPERTY_API_KEY)
            self.config.api_key = api_key
        except Exception as err:
            logger.info(f"GetProperty required {PROPERTY_API_KEY} failed, err: {err}")
            return

        try:
            model = ten_env.get_property_string(PROPERTY_MODEL)
            if model:
                self.config.model = model
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_MODEL} error: {err}")

        try:
            system_message = ten_env.get_property_string(PROPERTY_SYSTEM_MESSAGE)
            if system_message:
                self.config.system_message = system_message
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_SYSTEM_MESSAGE} error: {err}")

        try:
            temperature = ten_env.get_property_float(PROPERTY_TEMPERATURE)
            self.config.temperature = float(temperature)
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_TEMPERATURE} failed, err: {err}"
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
            voice = ten_env.get_property_string(PROPERTY_VOICE)
            if voice:
                v = DEFAULT_VOICE
                if voice == "alloy":
                    v = Voices.Alloy
                elif voice == "echo":
                    v = Voices.Echo
                elif voice == "shimmer":
                    v = Voices.Shimmer
                self.config.voice = v
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_VOICE} error: {err}")
        
        try:
            language = ten_env.get_property_string(PROPERTY_LANGUAGE)
            if language:
                self.config.language = language
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_LANGUAGE} error: {err}")

        try:
            server_vad = ten_env.get_property_bool(PROPERTY_SERVER_VAD)
            self.config.server_vad = server_vad
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_SERVER_VAD} failed, err: {err}"
            )

        try:
            self.stream_id = ten_env.get_property_int(PROPERTY_STREAM_ID)
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_STREAM_ID} failed, err: {err}"
            )

        self.ctx = self.config.build_ctx()

    def update_session(self) -> SessionUpdate:
        params = SessionUpdateParams()
        params.model = self.config.model
        params.modalities = set(["audio", "text"])
        params.instructions = ""
        params.voice = self.config.voice
        params.input_audio_format = AudioFormats.PCM16
        params.output_audio_format = AudioFormats.PCM16
        params.turn_detection = DEFAULT_TURN_DETECTION
        params.input_audio_transcription = InputAudioTranscription(enabled=True, model='whisper-1')
        params.temperature = self.config.temperature
        # params.max_response_output_tokens = self.config.max_tokens
        return SessionUpdate(session=params)

    def update_conversation(self) -> UpdateConversationConfig:
        prompt = self.replace(self.config.system_message)
        conf = UpdateConversationConfig()
        conf.system_message = prompt
        conf.temperature = self.config.temperature
        conf.max_tokens = self.config.max_tokens
        conf.tool_choice = "none"
        conf.disable_audio = False
        conf.output_audio_format = AudioFormats.PCM16
        return conf

    def replace(self, prompt:str) -> str:
        result = prompt
        for token, value in self.ctx.items():
            result = result.replace(f"{token}", value)
        return result

    def on_audio_delta(self, ten_env: TenEnv, delta: bytes) -> None:
        audio_data = base64.b64decode(delta)
        with open("audio_stt_out.pcm", "ab") as dump_file:
            dump_file.write(audio_data)
        f = AudioFrame.create(AUDIO_PCM_FRAME)
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
    
    def send_transcript(self, ten_env: TenEnv, transcript: str, role: str, is_final: bool) -> None:
        try:
            d = Data.create(DATA_TEXT_DATA)
            d.set_property_string("text", transcript)
            d.set_property_bool("end_of_segment", is_final)
            d.set_property_int("stream_id", self.stream_id if role == ROLE_ASSISTANT else self.remote_stream_id)
            d.set_property_bool("is_final", is_final)
            ten_env.send_data(d)
        except:
            logger.exception(f"Error send text data {role}: {transcript} {is_final}")
    
    def flush(self, ten_env: TenEnv) -> None:
        try:
            c = Cmd.create(CMD_FLUSH)
            ten_env.send_cmd(c, lambda ten, result: logger.info("flush done"))
        except:
            logger.exception(f"Error flush")
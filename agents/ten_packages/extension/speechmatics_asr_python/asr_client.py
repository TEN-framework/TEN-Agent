#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#

import asyncio
from datetime import datetime
import os
from typing import List, Optional, Dict, Any
from speechmatics.client import WebsocketClient
from speechmatics.models import (
    AudioSettings,
    ConnectionSettings,
    ServerMessageType,
    TranscriptionConfig,
)
from ten import AsyncTenEnv, AudioFrame, Data
from .audio_stream import AudioStream, AudioStreamEventType
from .config import SpeechmaticsASRConfig
from .word import (
    SpeechmaticsASRWord,
    convert_words_to_sentence,
    get_sentence_duration_ms,
    get_sentence_start_ms,
)
from .timeline import AudioTimeline
from .language_utils import get_speechmatics_language
from .dumper import Dumper


async def run_asr_client(client: "SpeechmaticsASRClient"):
    await client.client.run(
        client.audio_stream,
        client.transcription_config,
        client.audio_settings,
    )


class SpeechmaticsASRClient:
    def __init__(self, config: SpeechmaticsASRConfig, ten_env: AsyncTenEnv):
        self.config = config
        self.ten_env = ten_env
        self.task = None
        self.audio_queue = asyncio.Queue()
        self.timeline = AudioTimeline()
        self.audio_stream = AudioStream(
            self.audio_queue, self.config, self.timeline, ten_env
        )
        self.stream_id = (
            0  # The stream id will be set once receive the first audio frame
        )
        self.user_id = ""
        self.client_running_task: asyncio.Task = None
        self.client_needs_stopping = False
        self.sent_user_audio_duration_ms_before_last_reset = 0
        self.last_drain_timestamp: int = 0

        # Cache the words for sentence final mode
        self.cache_words = []  # type: List[SpeechmaticsASRWord]

        if self.config.dump:
            dump_file_path = os.path.join(
                self.config.dump_path, "speechmatics_asr_in.pcm"
            )
            self.audio_dumper = Dumper(dump_file_path)

    async def start(self) -> None:
        """Initialize and start the recognition session"""
        connection_settings = ConnectionSettings(
            url=self.config.uri,
            auth_token=self.config.key,
        )

        # sample_rate * bytes_per_sample * chunk_ms / 1000
        chunk_len = self.config.sample_rate * 2 / 1000 * self.config.chunk_ms

        self.audio_settings = AudioSettings(
            chunk_size=chunk_len,
            encoding=self.config.encoding,
            sample_rate=self.config.sample_rate,
        )

        additional_vocab = []
        if self.config.hotwords:
            for hw in self.config.hotwords:
                tokens = hw.split("|")
                if len(tokens) == 2 and tokens[1].isdigit():
                    additional_vocab.append({"content": tokens[0]})
                else:
                    self.ten_env.log_warn("invalid hotword format: " + hw)
        self.transcription_config = TranscriptionConfig(
            enable_partials=self.config.enable_partials,
            language=get_speechmatics_language(self.config.language),
            max_delay=self.config.max_delay,
            max_delay_mode=self.config.max_delay_mode,
            additional_vocab=additional_vocab,
            operating_point=(
                self.config.operating_point if self.config.operating_point else None
            ),
        )

        # Initialize client
        self.client = WebsocketClient(connection_settings)

        # Set up callbacks
        self.client.add_event_handler(
            ServerMessageType.RecognitionStarted, self._handle_recognition_started
        )
        self.client.add_event_handler(
            ServerMessageType.EndOfTranscript, self._handle_end_transcript
        )
        self.client.add_event_handler(
            ServerMessageType.AudioEventStarted, self._handle_audio_event_started
        )
        self.client.add_event_handler(
            ServerMessageType.AudioEventEnded, self._handle_audio_event_ended
        )
        self.client.add_event_handler(ServerMessageType.Info, self._handle_info)
        self.client.add_event_handler(ServerMessageType.Warning, self._handle_warning)
        self.client.add_event_handler(ServerMessageType.Error, self._handle_error)

        if self.config.enable_word_final_mode:
            self.client.add_event_handler(
                ServerMessageType.AddTranscript,
                self._handle_transcript_word_final_mode,
            )
            self.client.add_event_handler(
                ServerMessageType.AddPartialTranscript,
                self._handle_partial_transcript,
            )
        else:
            self.client.add_event_handler(
                ServerMessageType.AddTranscript,
                self._handle_transcript_sentence_final_mode,
            )
            # Ignore partial transcript

        self.client_needs_stopping = False
        self.client_running_task = asyncio.create_task(self._client_run())

        if self.config.dump:
            await self.audio_dumper.start()

    async def recv_audio_frame(self, frame: AudioFrame) -> None:
        frame_buf = frame.get_buf()
        if not frame_buf:
            self.ten_env.log_warn("send_frame: empty audio_frame detected.")
            return

        self.stream_id = frame.get_property_int("stream_id")
        self.user_id = frame.get_property_string("remote_user_id")

        try:
            await self.audio_queue.put(frame_buf)
            if self.config.dump:
                await self.audio_dumper.push_bytes(frame_buf)
        except Exception as e:
            self.ten_env.log_error(f"Error sending audio frame: {e}")

    async def stop(self) -> None:
        self.ten_env.log_info("call stop")
        self.client_needs_stopping = True

        self.client.stop()

        await self.audio_queue.put(AudioStreamEventType.FLUSH)
        await self.audio_queue.put(AudioStreamEventType.CLOSE)

        if self.client_running_task:
            await self.client_running_task

        self.client_running_task = None

        if self.config.dump:
            await self.audio_dumper.stop()

    async def _send_asr_result(self, text: str, is_final: bool, stream_id: str) -> None:
        self.ten_env.log_info(
            f"send asr result text [{text}] is_final [{is_final}] stream_id [{stream_id}]"
        )

        stable_data = Data.create("text_data")
        stable_data.set_property_bool("is_final", is_final)
        stable_data.set_property_string("text", text)
        stable_data.set_property_int("stream_id", stream_id)
        stable_data.set_property_bool("end_of_segment", is_final)
        await self.ten_env.send_data(stable_data)

    async def _client_run(self):
        self.ten_env.log_info(f"SpeechmaticsASRClient run start")

        last_connect_time = 0
        retry_interval = 0.5
        max_retry_interval = 30.0

        while not self.client_needs_stopping:
            try:
                current_time = asyncio.get_event_loop().time()
                if current_time - last_connect_time < retry_interval:
                    await asyncio.sleep(retry_interval)

                last_connect_time = current_time
                await run_asr_client(self)

                retry_interval = 0.5

            except Exception as e:
                self.ten_env.log_error(f"Error running client: {e}")
                retry_interval = min(retry_interval * 2, max_retry_interval)

            self.ten_env.log_info(
                "run end, client_needs_stopping:{}".format(self.client_needs_stopping)
            )

            if self.client_needs_stopping:
                break

        self.ten_env.log_info(f"SpeechmaticsASRClient run end")

    async def _internal_drain_mute_pkg(self):
        # we push some silence pkg to the queue
        # to trigger the final recognition result.
        await self.audio_stream.push_mute_pkg()

    async def _internal_drain_disconnect(self):
        await self.audio_queue.put(AudioStreamEventType.FLUSH)
        await self.audio_queue.put(AudioStreamEventType.CLOSE)

        # wait for the client to auto reconnect

    def _handle_recognition_started(self, msg):
        self.ten_env.log_info(f"_handle_recognition_started, msg: {msg}")
        self.sent_user_audio_duration_ms_before_last_reset += (
            self.timeline.get_total_user_audio_duration()
        )
        self.timeline.reset()

    def _handle_partial_transcript(self, msg):
        try:
            metadata = msg.get("metadata", {})
            text = metadata.get("transcript", "")
            start_ms = metadata.get("start_time", 0) * 1000
            end_ms = metadata.get("end_time", 0) * 1000
            duration_ms = int(end_ms - start_ms)

            actual_start_ms = int(
                self.timeline.get_audio_duration_before_time(start_ms)
                + self.sent_user_audio_duration_ms_before_last_reset
            )

            if text:
                asyncio.create_task(self._send_asr_result(text=text, is_final=False, stream_id=self.stream_id))
        except Exception as e:
            self.ten_env.log_error(f"Error processing transcript: {e}")

    def _handle_transcript_word_final_mode(self, msg):
        try:
            metadata = msg.get("metadata", {})
            text = metadata.get("transcript", "")
            if text:
                start_ms = metadata.get("start_time", 0) * 1000
                end_ms = metadata.get("end_time", 0) * 1000
                duration_ms = int(end_ms - start_ms)
                actual_start_ms = int(
                    self.timeline.get_audio_duration_before_time(start_ms)
                    + self.sent_user_audio_duration_ms_before_last_reset
                )

                asyncio.create_task(self._send_asr_result(text=text, is_final=True, stream_id=self.stream_id))
        except Exception as e:
            self.ten_env.log_error(f"Error processing transcript: {e}")

    def _handle_transcript_sentence_final_mode(self, msg):
        self.ten_env.log_info(f"_handle_transcript_sentence_final_mode, msg: {msg}")

        try:
            results = msg.get("results", {})

            for result in results:
                # Get the first candidate
                alternatives = result.get("alternatives", [])
                if alternatives:
                    text = alternatives[0].get("content", "")
                    if text:
                        start_ms = result.get("start_time", 0) * 1000
                        end_ms = result.get("end_time", 0) * 1000
                        duration_ms = int(end_ms - start_ms)
                        actual_start_ms = int(
                            self.timeline.get_audio_duration_before_time(start_ms)
                            + self.sent_user_audio_duration_ms_before_last_reset
                        )
                        type = result.get("type", "")
                        is_punctuation = type == "punctuation"

                        word = SpeechmaticsASRWord(
                            word=text,
                            start_ms=actual_start_ms,
                            duration_ms=duration_ms,
                            is_punctuation=is_punctuation,
                        )
                        self.cache_words.append(word)

                if result.get("is_eos") == True:
                    sentence = convert_words_to_sentence(self.cache_words, self.config)
                    start_ms = get_sentence_start_ms(self.cache_words)
                    duration_ms = get_sentence_duration_ms(self.cache_words)
                    asyncio.create_task(self._send_asr_result(text=sentence, is_final=True, stream_id=self.stream_id))
                    self.cache_words = []

            # if the transcript is not empty, send it as a partial transcript
            if self.cache_words:
                sentence = convert_words_to_sentence(self.cache_words, self.config)
                start_ms = get_sentence_start_ms(self.cache_words)
                duration_ms = get_sentence_duration_ms(self.cache_words)
                asyncio.create_task(self._send_asr_result(text=sentence, is_final=False, stream_id=self.stream_id))
        except Exception as e:
            self.ten_env.log_error(f"Error processing transcript: {e}")

    def _handle_end_transcript(self, msg):
        self.ten_env.log_info(f"_handle_end_transcript, msg: {msg}")

    def _handle_info(self, msg):
        self.ten_env.log_info(f"_handle_info, msg: {msg}")

    def _handle_warning(self, msg):
        self.ten_env.log_warn(f"_handle_warning, msg: {msg}")

    def _handle_error(self, error):
        self.ten_env.log_error(f"_handle_error, error: {error}")

    def _handle_audio_event_started(self, msg):
        self.ten_env.log_info(f"_handle_audio_event_started, msg: {msg}")

    def _handle_audio_event_ended(self, msg):
        self.ten_env.log_info(f"_handle_audio_event_ended, msg: {msg}")


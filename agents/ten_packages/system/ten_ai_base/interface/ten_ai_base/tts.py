#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from abc import ABC, abstractmethod
import asyncio
import traceback

from ten import (
    AsyncExtension,
    Data,
)
from ten.async_ten_env import AsyncTenEnv
from ten.audio_frame import AudioFrame, AudioFrameDataFmt
from ten.cmd import Cmd
from ten.cmd_result import CmdResult, StatusCode
from ten_ai_base.const import CMD_IN_FLUSH, CMD_OUT_FLUSH, DATA_IN_PROPERTY_END_OF_SEGMENT, DATA_IN_PROPERTY_TEXT
from ten_ai_base.types import TTSPcmOptions
from .helper import AsyncQueue, get_property_bool, get_property_string


class AsyncTTSBaseExtension(AsyncExtension, ABC):
    """
    Base class for implementing a Text-to-Speech Extension.
    This class provides a basic implementation for converting text to speech.
    It automatically handles the processing of tts requests.
    Use begin_send_audio_out, send_audio_out, end_send_audio_out to send the audio data to the output.
    Override on_request_tts to implement the TTS logic.
    """
    # Create the queue for message processing

    def __init__(self, name: str):
        super().__init__(name)
        self.queue = AsyncQueue()
        self.current_task = None
        self.loop_task = None
        self.bytes = b""
        self.bytes_cursor = 0
        self.sample_rate = 16000
        self.bytes_per_sample = 2
        self.number_of_channels = 1

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        await super().on_start(ten_env)

        if self.loop_task is None:
            self.loop = asyncio.get_event_loop()
            self.loop_task = self.loop.create_task(self._process_queue(ten_env))

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)

    async def on_cmd(self, async_ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        async_ten_env.log_info(f"on_cmd name: {cmd_name}")

        if cmd_name == CMD_IN_FLUSH:
            await self.flush_input_items(async_ten_env)
            await self.on_cancel_tts(async_ten_env)
            await async_ten_env.send_cmd(Cmd.create(CMD_OUT_FLUSH))
            async_ten_env.log_info("on_cmd sent flush")
            status_code, detail = StatusCode.OK, "success"
            cmd_result = CmdResult.create(status_code)
            cmd_result.set_property_string("detail", detail)
            async_ten_env.return_result(cmd_result, cmd)

    async def on_data(self, async_ten_env: AsyncTenEnv, data: Data) -> None:
        # Get the necessary properties
        async_ten_env.log_info(f"on_data name: {data.get_name()}")
        input_text = get_property_string(data, DATA_IN_PROPERTY_TEXT)
        end_of_segment = get_property_bool(data, DATA_IN_PROPERTY_END_OF_SEGMENT)

        if not input_text:
            async_ten_env.log_warn("ignore empty text")
            return

        # Start an asynchronous task for handling tts
        await self.queue.put([input_text, end_of_segment])

    async def flush_input_items(self, ten_env: AsyncTenEnv):
        """Flushes the self.queue and cancels the current task."""
        # Flush the queue using the new flush method
        await self.queue.flush()

        # Cancel the current task if one is running
        if self.current_task:
            ten_env.log_info("Cancelling the current task during flush.")
            self.current_task.cancel()

    def begin_send_audio_out(self, ten_env: AsyncTenEnv, **args: TTSPcmOptions) -> None:
        """Begin sending audio out."""
        self.bytes = b""
        self.bytes_cursor = 0
        self.sample_rate = args.get("sample_rate", 16000)
        self.bytes_per_sample = args.get("bytes_per_sample", 2)
        self.number_of_channels = args.get("number_of_channels", 1)

    def send_audio_out(self, ten_env: AsyncTenEnv, audio_data: bytes) -> None:
        try:
            sample_rate = self.sample_rate
            bytes_per_sample = self.bytes_per_sample
            number_of_channels = self.number_of_channels
            samples_per_channel_per_10ms = sample_rate // 100 * number_of_channels

            frame_size = samples_per_channel_per_10ms * bytes_per_sample

            self.bytes += audio_data

            while len(self.bytes) - self.bytes_cursor >= frame_size:
                audio_data = self.bytes[self.bytes_cursor:self.bytes_cursor + frame_size]
                self.bytes_cursor += frame_size

                f = AudioFrame.create("pcm_frame")
                f.set_sample_rate(sample_rate)
                f.set_bytes_per_sample(bytes_per_sample)
                f.set_number_of_channels(number_of_channels)
                f.set_data_fmt(AudioFrameDataFmt.INTERLEAVE)
                f.set_samples_per_channel(samples_per_channel_per_10ms)
                f.alloc_buf(frame_size)
                buff = f.lock_buf()
                buff[:] = audio_data
                f.unlock_buf(buff)
                ten_env.send_audio_frame(f)
        except Exception as e:
            ten_env.log_error(f"error send audio frame, {traceback.format_exc()}")

    def end_send_audio_out(self, ten_env: AsyncTenEnv) -> None:
        """End sending audio out."""
        sample_rate = self.sample_rate
        bytes_per_sample = self.bytes_per_sample
        number_of_channels = self.number_of_channels
        if self.bytes_cursor < len(self.bytes):
            try:
                audio_data = self.bytes[self.bytes_cursor:]

                f = AudioFrame.create("pcm_frame")
                f.set_sample_rate(sample_rate)
                f.set_bytes_per_sample(bytes_per_sample)
                f.set_number_of_channels(number_of_channels)
                f.set_data_fmt(AudioFrameDataFmt.INTERLEAVE)
                f.set_samples_per_channel(len(audio_data) // (bytes_per_sample * number_of_channels))
                f.alloc_buf(len(audio_data))
                buff = f.lock_buf()
                buff[:] = audio_data
                f.unlock_buf(buff)
                ten_env.send_audio_frame(f)
            except Exception as e:
                ten_env.log_error(f"error send audio frame, {traceback.format_exc()}")    
        self.bytes = b""
        self.bytes_cursor = 0

    @abstractmethod
    async def on_request_tts(self, ten_env: AsyncTenEnv, input_text: str, end_of_segment: bool) -> None:
        """
        Called when a new input item is available in the queue. Override this method to implement the TTS request logic.
        Use send_audio_out to send the audio data to the output when the audio data is ready.
        """
        pass

    @abstractmethod
    async def on_cancel_tts(self, ten_env: AsyncTenEnv) -> None:
        """Called when the TTS request is cancelled."""
        pass


    async def _process_queue(self, ten_env: AsyncTenEnv):
        """Asynchronously process queue items one by one."""
        while True:
            # Wait for an item to be available in the queue
            [text, end_of_segment] = await self.queue.get()
            try:
                ten_env.log_info(f"Processing queue item: {text}")
                self.current_task = asyncio.create_task(
                    self.on_request_tts(ten_env, text, end_of_segment))
                await self.current_task  # Wait for the current task to finish or be cancelled
            except asyncio.CancelledError:
                ten_env.log_info(f"Task cancelled: {text}")
            except Exception as err:
                ten_env.log_error(f"Task failed: {text}, err: {traceback.format_exc()}")

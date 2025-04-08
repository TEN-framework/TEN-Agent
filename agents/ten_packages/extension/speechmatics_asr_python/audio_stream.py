#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#

import asyncio
from enum import Enum
from ten import AsyncTenEnv
from .config import SpeechmaticsASRConfig
from .timeline import AudioTimeline


# Define a enum class for the event type
class AudioStreamEventType(Enum):
    FLUSH = 0
    CLOSE = 1
    MUTE_PKG = 2


class AudioStream:
    def __init__(
        self,
        audio_frame_queue: asyncio.Queue,
        config: SpeechmaticsASRConfig,
        timeline: AudioTimeline,
        ten_env: AsyncTenEnv,
    ):
        self.audio_frame_queue = audio_frame_queue
        self.config = config
        self.ten_env = ten_env
        self.timeline = timeline

    async def push_mute_pkg(self):
        # flush the queue
        await self.audio_frame_queue.put(AudioStreamEventType.FLUSH)
        # push the mute pkg event
        await self.audio_frame_queue.put(AudioStreamEventType.MUTE_PKG)

    async def read(self, chunk_size: int):
        data = bytearray()
        while len(data) < chunk_size:
            frame = await self.audio_frame_queue.get()

            if isinstance(frame, AudioStreamEventType):
                if frame == AudioStreamEventType.FLUSH:
                    # if data is empty, do nothing, else consume the cache frame
                    if len(data) == 0:
                        continue
                    else:
                        break
                elif frame == AudioStreamEventType.CLOSE:
                    # empty data will trigger the end of the stream
                    data = bytearray()
                    return data
                elif frame == AudioStreamEventType.MUTE_PKG:
                    empty_audio_bytes_len = int(
                        self.config.mute_pkg_duration_ms
                        * self.config.sample_rate
                        / 1000
                        * 2
                    )
                    frame = bytearray(empty_audio_bytes_len)
                    self.timeline.add_silence_audio(self.config.mute_pkg_duration_ms)
            else:
                self.timeline.add_user_audio(
                    len(frame) / (self.config.sample_rate / 1000 * 2)
                )

            data.extend(frame)

        self.ten_env.log_verbose(
            f"AudioStream read, chunk_size: {chunk_size}, data_size: {len(data)}"
        )

        return data

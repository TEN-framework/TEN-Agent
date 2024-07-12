#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024-07.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

import logging
from typing import Iterator
from rte_runtime_python import PcmFrame, Rte, RTE_PCM_FRAME_DATA_FMT


class Pcm:
    def __init__(self, config) -> None:
        self.config = config

    def get_pcm_frame(self, buf: memoryview) -> PcmFrame:
        frame = PcmFrame.create(self.config.name)
        frame.set_bytes_per_sample(self.config.bytes_per_sample)
        frame.set_sample_rate(self.config.sample_rate)
        frame.set_number_of_channels(self.config.num_channels)
        frame.set_timestamp(self.config.timestamp)
        frame.set_data_fmt(RTE_PCM_FRAME_DATA_FMT.RTE_PCM_FRAME_DATA_FMT_NON_INTERLEAVE)
        frame.set_samples_per_channel(
            self.config.samples_per_channel // self.config.channel
        )

        frame.alloc_buf(self.get_pcm_frame_size())
        frame_buf = frame.lock_buf()
        # copy data
        frame_buf[:] = buf
        frame.unlock_buf(frame_buf)

        return frame

    def get_pcm_frame_size(self) -> int:
        return (
            self.config.samples_per_channel
            * self.config.channel
            * self.config.bytes_per_sample
        )

    def new_buf(self) -> bytearray:
        return bytearray(self.get_pcm_frame_size())

    def read_pcm_stream(
        self, stream: Iterator[bytes], chunk_size: int
    ) -> Iterator[bytes]:
        chunk = b""
        for data in stream:
            chunk += data
            while len(chunk) >= chunk_size:
                yield chunk[:chunk_size]
                chunk = chunk[chunk_size:]
        if chunk:
            yield chunk

    def send(self, rte: Rte, buf: memoryview) -> None:
        try:
            frame = self.get_pcm_frame(buf)
            rte.send_pcm_frame(frame)
        except Exception as e:
            logging.error(f"send frame failed, {e}")


class PcmConfig:
    def __init__(self) -> None:
        self.bytes_per_sample = 2
        self.channel = 1
        self.name = "pcm_frame"
        self.sample_rate = 16000
        self.samples_per_channel = 16000 // 100
        self.timestamp = 0

#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import struct

BYTES_PER_SAMPLE = 2
NUMBER_OF_CHANNELS = 1
WAV_HEADER_BYTES = 44


class StreamingWavToPcm16:
    """Strip the first WAV header and return PCM16-aligned chunks."""

    def __init__(self) -> None:
        self._header = bytearray()
        self._remainder = bytearray()
        self._header_stripped = False

    def feed(self, chunk: bytes) -> bytes:
        if not chunk:
            return b""

        if not self._header_stripped:
            needed = WAV_HEADER_BYTES - len(self._header)
            self._header.extend(chunk[:needed])
            chunk = chunk[needed:]
            if len(self._header) < WAV_HEADER_BYTES:
                return b""
            if (
                self._header[:4] != b"RIFF"
                or self._header[8:16] != b"WAVEfmt "
                or self._header[36:40] != b"data"
                or struct.unpack_from("<IHHIIHH", self._header, 16)
                != (16, 1, 1, 32000, 64000, 2, 16)
            ):
                raise ValueError("Expected a 32 kHz mono PCM16 WAV stream")
            self._header_stripped = True

        if self._remainder:
            chunk = bytes(self._remainder) + chunk
            self._remainder.clear()

        frame_size = BYTES_PER_SAMPLE * NUMBER_OF_CHANNELS
        left_size = len(chunk) % frame_size
        if left_size:
            self._remainder.extend(chunk[-left_size:])
            chunk = chunk[:-left_size]

        return bytes(chunk)

    def finish(self) -> None:
        if self._header and not self._header_stripped:
            raise ValueError("Incomplete WAV header")
        if self._remainder:
            raise ValueError("Incomplete PCM16 sample")

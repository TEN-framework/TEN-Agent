#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#

import aiofiles
from typing import Optional
import os


class Dumper:
    def __init__(self, dump_file_path: str):
        self.dump_file_path = dump_file_path
        self._file: Optional[aiofiles.threadpool.binary.AsyncBufferedIOBase] = None

    async def start(self):
        os.makedirs(os.path.dirname(self.dump_file_path), exist_ok=True)

        self._file = await aiofiles.open(self.dump_file_path, mode="wb")

    async def stop(self):
        if self._file:
            await self._file.close()
            self._file = None

    async def push_bytes(self, data: bytes):
        if not self._file:
            raise RuntimeError(
                "Dumper for {} is not opened. Please start the Dumper first.".format(
                    self.dump_file_path
                )
            )
        await self._file.write(data)

    async def push_text(self, text: str):
        if not self._file:
            raise RuntimeError(
                "Dumper for {} is not opened. Please start the Dumper first.".format(
                    self.dump_file_path
                )
            )

        await self._file.write(text.encode("utf-8"))

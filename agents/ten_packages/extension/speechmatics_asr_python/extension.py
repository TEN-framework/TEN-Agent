#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#

import json

from ten import (
    AsyncExtension,
    AsyncTenEnv,
    Cmd,
    AudioFrame,
    StatusCode,
    CmdResult,
)
from .asr_client import SpeechmaticsASRClient, SpeechmaticsASRConfig


class SpeechmaticsASRExtension(AsyncExtension):
    def __init__(self, name: str):
        super().__init__(name)

        self.client: SpeechmaticsASRClient = None
        self.ten_env: AsyncTenEnv = None
        self.config: SpeechmaticsASRConfig = None

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_start")
        self.ten_env = ten_env

        config = await SpeechmaticsASRConfig.create_async(ten_env=ten_env)
        ten_env.log_debug(f"config: {config.to_str(sensitive_handling=True)}")

        if not config.key:
            ten_env.log_error("get property api_key failed")
            raise Exception("get property api_key failed")

        self.config = config

        self.client = SpeechmaticsASRClient(self.config, ten_env)
        await self.client.start()

    async def on_audio_frame(self, ten_env: AsyncTenEnv, frame: AudioFrame) -> None:
        await self.client.recv_audio_frame(frame)

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_stop")
        await self.client.stop()

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_deinit")

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug(f"on_cmd: {cmd_name}")

        cmd_result = CmdResult.create(StatusCode.OK)
        await ten_env.return_result(cmd_result, cmd)

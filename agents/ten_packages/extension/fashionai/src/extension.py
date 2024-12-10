#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import traceback
from ten import (
    AudioFrame,
    VideoFrame,
    Extension,
    AsyncTenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)
from ten.async_extension import AsyncExtension

from .log import logger
import asyncio
from .fashionai_client import FashionAIClient
import threading
from datetime import datetime

class FashionAIExtension(AsyncExtension):
    app_id = ""
    token = ""
    channel = ""
    stream_id = 0
    service_id = "agora"

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        logger.info("FASHION_AI on_init *********************************************************")
        self.stopped = False
        self.queue = asyncio.Queue(maxsize=3000)

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        logger.info("FASHION_AI on_start *********************************************************")

        # TODO: read properties, initialize resources
        try:
            self.app_id = ten_env.get_property_string("app_id")
            self.token = ten_env.get_property_string("token")
            self.channel = ten_env.get_property_string("channel")
            self.stream_id = str(ten_env.get_property_int("stream_id"))
            self.service_id = ten_env.get_property_string("service_id")

            logger.info(f"FASHION_AI on_start: app_id = {self.app_id}, token = {self.token}, channel = {self.channel}, stream_id = {self.stream_id}, service_id = {self.service_id}")
        except Exception as e:
            logger.warning(f"get_property err: {e}")

        if len(self.token) > 0:
            self.app_id = self.token
        self.client = FashionAIClient("wss://ingress.service.fasionai.com/websocket/node5/agoramultimodel2", self.service_id)
        asyncio.create_task(self.process_input_text())
        await self.init_fashionai(self.app_id, self.channel, self.stream_id)

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        logger.info("FASHION_AI on_stop")
        self.stopped = True
        await self.queue.put(None)

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        logger.info("FASHION_AI on_deinit")

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        logger.info("FASHION_AI on_cmd name {}".format(cmd_name))

        # TODO: process cmd
        if cmd_name == "flush":
            self.outdate_ts = datetime.now()
            try:
                await self.client.send_interrupt()

            except Exception as e:
                logger.warning(f"flush err: {traceback.format_exc()}")

            cmd_out = Cmd.create("flush")
            await ten_env.send_cmd(cmd_out)
            # ten_env.send_cmd(cmd_out, lambda ten, result: logger.info("send_cmd flush done"))
        else:
            logger.info("unknown cmd {}".format(cmd_name))

        logger.info("FASHION_AI on_cmd done")
        cmd_result = CmdResult.create(StatusCode.OK)
        ten_env.return_result(cmd_result, cmd)

    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        # TODO: process data
        inputText = data.get_property_string("text")
        if len(inputText) == 0:
            logger.info("FASHION_AI ignore empty text")
            return

        logger.info("FASHION_AI on data %s", inputText)
        try:
            await self.queue.put(inputText)
        except asyncio.TimeoutError:
            logger.warning(f"FASHION_AI put inputText={inputText} queue timed out")
        except Exception as e:
            logger.warning(f"FASHION_AI put inputText={inputText} queue err: {e}")
        logger.info("FASHION_AI send_inputText %s", inputText)

    async def on_audio_frame(self, ten_env: AsyncTenEnv, audio_frame: AudioFrame) -> None:
        # TODO: process pcm frame
        pass

    async def on_video_frame(self, ten_env: AsyncTenEnv, video_frame: VideoFrame) -> None:
        # TODO: process image frame
        pass            

    async def init_fashionai(self, app_id, channel, stream_id):
        await self.client.connect()
        await self.client.stream_start(app_id, channel, stream_id)
        await self.client.render_start()
        
    async def process_input_text(self):
        while True:
            inputText = await self.queue.get() 
            if inputText is None:
                logger.info("Stopping async_polly_handler...")
                break

            logger.info(f"async_polly_handler: loop fashion ai polly.{inputText}")

            if len(inputText) > 0:
                try:
                    await self.client.send_inputText(inputText)
                except Exception as e:
                    logger.exception(e)

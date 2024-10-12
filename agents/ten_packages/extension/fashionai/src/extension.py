#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
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

from .log import logger
import asyncio
from .fashionai_client import FashionAIClient
import threading
from datetime import datetime

class FashionAIExtension(Extension):
    app_id = ""
    token = ""
    channel = ""
    stream_id = 0

    def on_init(self, ten_env: TenEnv) -> None:
        logger.info("FASHION_AI on_init *********************************************************")
        self.stopped = False
        self.queue = asyncio.Queue(maxsize=3000)
        self.client = FashionAIClient("wss://ingress.service.fasionai.com/websocket/node7/server1")
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        logger.info("FASHION_AI on_start *********************************************************")

        # TODO: read properties, initialize resources
        try:
            self.app_id = ten_env.get_property_string("app_id")
            self.token = ten_env.get_property_string("token")
            self.channel = ten_env.get_property_string("channel")
            self.stream_id = str(ten_env.get_property_int("stream_id"))
            if len(self.token) > 0 :
                self.app_id = self.token
            logger.info(f"FASHION_AI on_start: app_id = {self.app_id}, token = {self.token}, channel = {self.channel}, stream_id = {self.stream_id}")
        except Exception as e:
            logger.warning(f"get_property err: {e}")

        def thread_target():
            self.loop.run_until_complete(self.init_fashionai(ten_env, self.app_id, self.channel, self.stream_id))

        self.threadWebsocket = threading.Thread(target=thread_target)
        self.threadWebsocket.start()

        ten_env.on_start_done()

    def on_stop(self, ten_env: TenEnv) -> None:
        logger.info("FASHION_AI on_stop")
        self.stopped = True
        asyncio.run(self.queue.put(None))
        self.flush()
        self.threadWebsocket.join()

        # TODO: clean up resources

        ten_env.on_stop_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        logger.info("FASHION_AI on_deinit")
        ten_env.on_deinit_done()

    def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        logger.info("FASHION_AI on_cmd name {}".format(cmd_name))

        # TODO: process cmd
        if cmd_name == "flush":
            self.outdate_ts = datetime.now()
            try:
                asyncio.run_coroutine_threadsafe(
                    self.flush(), self.loop
                ).result(timeout=0.1)
            except Exception as e:
                ten_env.return_result(CmdResult.create(StatusCode.ERROR), cmd)

            cmd_out = Cmd.create("flush")
            ten_env.send_cmd(cmd_out, lambda ten, result: logger.info("send_cmd flush done"))
        else:
            logger.info("unknown cmd {}".format(cmd_name))

        cmd_result = CmdResult.create(StatusCode.OK)
        ten_env.return_result(cmd_result, cmd)

    def on_data(self, ten_env: TenEnv, data: Data) -> None:
        # TODO: process data
        inputText = data.get_property_string("text")
        if len(inputText) == 0:
            logger.info("FASHION_AI ignore empty text")
            return

        logger.info("FASHION_AI on data %s", inputText)
        try:        
            asyncio.run_coroutine_threadsafe(
                    self.queue.put((inputText, datetime.now())), self.loop
            ).result(timeout=0.1)
        except Exception as e:
            logger.warning(f"FASHION_AI put inputText={inputText} queue err: {e}")
        logger.info("FASHION_AI send_inputText %s", inputText)

        pass

    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        # TODO: process pcm frame
        pass

    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        # TODO: process image frame
        pass            

    async def init_fashionai(self, ten_env: TenEnv, app_id, channel, stream_id):
        await self.client.connect()
        await self.client.stream_start(app_id, channel, stream_id)
        await self.client.render_start()
        await self.create_task()
        
    async def create_task(self):
        while True:
            value = await self.queue.get()  # 从队列中获取值
            logger.info(f"async_polly_handler: loop fashion ai polly.{value}")

            inputText, ts = value
            if len(inputText) > 0:
                try:
                    await self.client.send_inputText(inputText)
                except Exception as e:
                    logger.exception(e)

    async def flush(self):
        logger.info("FASHION_AI flush")
        while not self.queue.empty():
            value = await self.queue.get()
            logger.info(f"Flushing value: {value}")

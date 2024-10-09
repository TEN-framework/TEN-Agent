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
import json
import ssl
import queue

import websockets
import threading
from datetime import datetime
import time


APP_ID = ""
CHANNEL = ""
STREAM_ID = "0"
TOKEN = ""

class FashionAIExtension(Extension):


    def on_init(self, ten_env: TenEnv) -> None:
        logger.info("FASHION_AI on_init *********************************************************")
        self.stopped = False
        self.queue = queue.Queue()
        self.client = WebSocketClient("wss://ingress.service.fasionai.com/websocket/node7/server1")

        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        logger.info("FASHION_AI on_start *********************************************************")

        # TODO: read properties, initialize resources
        APP_ID = ten_env.get_property_string("app_id")
        TOKEN = ten_env.get_property_string("token")
        CHANNEL = ten_env.get_property_string("channel")
        STREAM_ID = str(ten_env.get_property_int("stream_id"))
        if len(TOKEN) > 0 :
            APP_ID = TOKEN
        logger.info(f"FASHION_AI on_start: app_id = {APP_ID}, token = {TOKEN}, channel = {CHANNEL}, stream_id = {STREAM_ID}")

        new_loop = asyncio.new_event_loop()

        self.threadWebsocket = threading.Thread(target=self.thread_target, args=(new_loop,ten_env,APP_ID ,CHANNEL,STREAM_ID))
        self.threadWebsocket.start()

        threading.Thread(target=self.async_polly_handler, args=[ten_env]).start()

        ten_env.on_start_done()

    def on_stop(self, ten_env: TenEnv) -> None:
        logger.info("FASHION_AI on_stop")
        self.stopped = True
        self.queue.put(None)
        self.flush()
        self.thread.join()

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
            self.flush()
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
        self.queue.put((inputText, datetime.now()))
        # asyncio.get_event_loop().run_until_complete(self.client.send_inputText(inputText))
        logger.info("FASHION_AI send_inputText %s", inputText)

        # self.queue.put((inputText, datetime.now()))

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
        # asyncio.create_task(self.client.heartbeat(10))
        await self.client.render_start()
        while True:
            await self.async_polly_handler()

    def thread_target(self, loop, ten_env: TenEnv, app_id, channel, stream_id):
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.init_fashionai(ten_env, app_id, channel, stream_id))

        
    async def async_polly_handler(self):
        value = self.queue.get()
        logger.info(f"async_polly_handler: loop fashion ai polly.{value}")

        inputText, ts = value
        if len(inputText) > 0:
            try:
                await self.client.send_inputText(inputText)
            except Exception as e:
                logger.exception(e)

    def flush(self):
        logger.info("FASHION_AI flush")
        while not self.queue.empty():
            self.queue.get()


class WebSocketClient:
    def __init__(self, uri):
        self.uri = uri
        self.websocket = None

    async def connect(self):
        ssl_context = ssl._create_unverified_context()
        self.websocket = await websockets.connect(self.uri, ssl=ssl_context)

    async def stream_start(self, app_id, channel, stream_id):
        await self.send_message(
                {
                    "request_id": "1",
                    "service_id": "agora",
                    "token": app_id,
                    "channel_id": channel,
                    "user_id": stream_id,
                    "signal": "STREAM_START",
                }
            )

    async def render_start(self):
        await self.send_message(
            {
                "request_id": "3",
                "service_id": "agora",
                "signal": "RENDER_START",
            }
        )

    async def send_inputText(self, inputText):
        await self.send_message(
           {
                "request_id": "4",
                "service_id": "agora",
                "signal": "RENDER_CONTENT",
                "text": inputText,
            }
        )


    async def send_message(self, message):
        if self.websocket is not None:
            try:
                await self.websocket.send(json.dumps(message))
                logger.info(f"FASHION_AI Sent: {message}")
                response = await asyncio.wait_for(self.websocket.recv(), timeout=2)
                logger.info(f"FASHION_AI Received: {response}")
            except websockets.exceptions.ConnectionClosedError as e:
                logger.info(f"FASHION_AI Connection closed with error: {e}")
                await self.reconnect()
            except asyncio.TimeoutError:
                logger.info("FASHION_AI Timeout waiting for response")
        else:
            logger.info("FASHION_AI WebSocket is not connected.")

    async def receive_message(self):
        if self.websocket is not None:
            try:
                response = await self.websocket.recv()
                logger.info(f"FASHION_AI Received: {response}")
                return response
            except websockets.exceptions.ConnectionClosedError as e:
                logger.info(f"FASHION_AI Connection closed with error: {e}")
                await self.reconnect()
                return None
        else:
            logger.info("FASHION_AI WebSocket is not connected.")
            return None

    async def close(self):
        if self.websocket is not None:
            await self.websocket.close()
            logger.info("FASHION_AI WebSocket connection closed.")
        else:
            logger.info("FASHION_AI WebSocket is not connected.")

    async def reconnect(self):
        logger.info("FASHION_AI Reconnecting...")
        await self.close()
        await self.connect()

    async def heartbeat(self, interval):
        while True:
            await asyncio.sleep(interval)
            try:
                await self.send_inputText("ping")
            except websockets.exceptions.ConnectionClosedError:
                break

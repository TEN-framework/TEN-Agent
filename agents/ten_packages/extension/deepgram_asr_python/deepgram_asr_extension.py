from ten import (
    Extension,
    TenEnv,
    Cmd,
    AudioFrame,
    StatusCode,
    CmdResult,
)

import asyncio
import threading

from .log import logger
from .deepgram_wrapper import AsyncDeepgramWrapper, DeepgramConfig

PROPERTY_API_KEY = "api_key"  # Required
PROPERTY_LANG = "language"  # Optional
PROPERTY_MODEL = "model"  # Optional
PROPERTY_SAMPLE_RATE = "sample_rate"  # Optional


class DeepgramASRExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)

        self.stopped = False
        self.queue = asyncio.Queue(maxsize=3000)  # about 3000 * 10ms = 30s input
        self.deepgram = None
        self.thread = None

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def on_start(self, ten: TenEnv) -> None:
        logger.info("on_start")

        deepgram_config = DeepgramConfig.default_config()

        try:
            deepgram_config.api_key = ten.get_property_string(PROPERTY_API_KEY).strip()
        except Exception as e:
            logger.error(f"get property {PROPERTY_API_KEY} error: {e}")
            return

        for optional_param in [
            PROPERTY_LANG,
            PROPERTY_MODEL,
            PROPERTY_SAMPLE_RATE,
        ]:
            try:
                value = ten.get_property_string(optional_param).strip()
                if value:
                    deepgram_config.__setattr__(optional_param, value)
            except Exception as err:
                logger.debug(
                    f"get property optional {optional_param} failed, err: {err}. Using default value: {deepgram_config.__getattribute__(optional_param)}"
                )

        self.deepgram = AsyncDeepgramWrapper(
            deepgram_config, self.queue, ten, self.loop
        )

        logger.info("starting async_deepgram_wrapper thread")
        self.thread = threading.Thread(target=self.deepgram.run, args=[])
        self.thread.start()

        ten.on_start_done()

    def put_pcm_frame(self, pcm_frame: AudioFrame) -> None:
        try:
            asyncio.run_coroutine_threadsafe(
                self.queue.put(pcm_frame), self.loop
            ).result(timeout=0.5)
        except asyncio.QueueFull:
            logger.exception("queue is full, dropping frame")
        except Exception as e:
            logger.exception(f"error putting frame in queue: {e}")

    def on_audio_frame(self, ten: TenEnv, frame: AudioFrame) -> None:
        self.put_pcm_frame(pcm_frame=frame)

    def on_stop(self, ten: TenEnv) -> None:
        logger.info("on_stop")

        # put an empty frame to stop deepgram_wrapper
        self.put_pcm_frame(None)
        self.stopped = True
        self.thread.join()
        self.loop.stop()
        self.loop.close()

        ten.on_stop_done()

    def on_cmd(self, ten: TenEnv, cmd: Cmd) -> None:
        logger.info("on_cmd")
        cmd_json = cmd.to_json()
        logger.info("on_cmd json: " + cmd_json)

        cmdName = cmd.get_name()
        logger.info("got cmd %s" % cmdName)

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "success")
        ten.return_result(cmd_result, cmd)

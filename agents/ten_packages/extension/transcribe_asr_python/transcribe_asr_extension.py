from rte import (
    Extension,
    RteEnv,
    Cmd,
    PcmFrame,
    StatusCode,
    CmdResult,
)

import asyncio
import threading

from .log import logger
from .transcribe_wrapper import AsyncTranscribeWrapper, TranscribeConfig

PROPERTY_REGION = "region"  # Optional
PROPERTY_ACCESS_KEY = "access_key"  # Optional
PROPERTY_SECRET_KEY = "secret_key"  # Optional
PROPERTY_SAMPLE_RATE = 'sample_rate'# Optional
PROPERTY_LANG_CODE = 'lang_code'    # Optional


class TranscribeAsrExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)

        self.stopped = False
        self.queue = asyncio.Queue(maxsize=3000) # about 3000 * 10ms = 30s input
        self.transcribe = None
        self.thread = None

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def on_start(self, rte: RteEnv) -> None:
        logger.info("TranscribeAsrExtension on_start")

        transcribe_config = TranscribeConfig.default_config()

        for optional_param in [PROPERTY_REGION, PROPERTY_SAMPLE_RATE, PROPERTY_LANG_CODE, 
                PROPERTY_ACCESS_KEY, PROPERTY_SECRET_KEY]:
            try:
                value = rte.get_property_string(optional_param).strip()
                if value:
                    transcribe_config.__setattr__(optional_param, value)
            except Exception as err:
                logger.debug(f"GetProperty optional {optional_param} failed, err: {err}. Using default value: {transcribe_config.__getattribute__(optional_param)}")

        self.transcribe = AsyncTranscribeWrapper(transcribe_config, self.queue, rte, self.loop)

        logger.info("Starting async_transcribe_wrapper thread")
        self.thread = threading.Thread(target=self.transcribe.run, args=[])
        self.thread.start()

        rte.on_start_done()

    def put_pcm_frame(self, pcm_frame: PcmFrame) -> None:
        try:
            asyncio.run_coroutine_threadsafe(self.queue.put(pcm_frame), self.loop).result(timeout=0.1)
        except asyncio.QueueFull:
            logger.exception("Queue is full, dropping frame")
        except Exception as e:
            logger.exception(f"Error putting frame in queue: {e}")

    def on_pcm_frame(self, rte: RteEnv, pcm_frame: PcmFrame) -> None:
        self.put_pcm_frame(pcm_frame=pcm_frame)

    def on_stop(self, rte: RteEnv) -> None:
        logger.info("TranscribeAsrExtension on_stop")

        # put an empty frame to stop transcribe_wrapper
        self.put_pcm_frame(None)
        self.stopped = True
        self.thread.join()
        self.loop.stop()
        self.loop.close()

        rte.on_stop_done()

    def on_cmd(self, rte: RteEnv, cmd: Cmd) -> None:
        logger.info("TranscribeAsrExtension on_cmd")
        cmd_json = cmd.to_json()
        logger.info("TranscribeAsrExtension on_cmd json: " + cmd_json)

        cmdName = cmd.get_name()
        logger.info("got cmd %s" % cmdName)

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "success")
        rte.return_result(cmd_result, cmd)

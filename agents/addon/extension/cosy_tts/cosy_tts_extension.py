#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-05.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import traceback
from rte import (
    Extension,
    RteEnv,
    Cmd,
    PcmFrame,
    PcmFrameDataFmt,
    Data,
    StatusCode,
    CmdResult,
)
from typing import List, Any
import dashscope
import queue
import threading
from datetime import datetime
from dashscope.audio.tts_v2 import ResultCallback, SpeechSynthesizer, AudioFormat
from .log import logger


class CosyTTSCallback(ResultCallback):
    def __init__(self, rte: RteEnv, sample_rate: int, need_interrupt_callback):
        super().__init__()
        self.rte = rte
        self.sample_rate = sample_rate
        self.frame_size = int(self.sample_rate * 1 * 2 / 100)
        self.ts = datetime.now()  # current task ts
        self.init_ts = datetime.now()
        self.ttfb = None  # time to first byte
        self.need_interrupt_callback = need_interrupt_callback
        self.closed = False

    def need_interrupt(self) -> bool:
        return self.need_interrupt_callback(self.ts)

    def set_input_ts(self, ts: datetime):
        self.ts = ts

    def on_open(self):
        logger.info("websocket is open.")

    def on_complete(self):
        logger.info("speech synthesis task complete successfully.")

    def on_error(self, message: str):
        logger.info(f"speech synthesis task failed, {message}")

    def on_close(self):
        logger.info("websocket is closed.")
        self.closed = True

    def on_event(self, message):
        pass
        # logger.info(f"recv speech synthsis message {message}")

    def get_frame(self, data: bytes) -> PcmFrame:
        f = PcmFrame.create("pcm_frame")
        f.set_sample_rate(self.sample_rate)
        f.set_bytes_per_sample(2)
        f.set_number_of_channels(1)
        # f.set_timestamp = 0
        f.set_data_fmt(PcmFrameDataFmt.INTERLEAVE)
        f.set_samples_per_channel(len(data) // 2)
        f.alloc_buf(len(data))
        buff = f.lock_buf()
        buff[:] = data
        f.unlock_buf(buff)
        return f

    def on_data(self, data: bytes) -> None:
        if self.need_interrupt():
            return
        if self.ttfb is None:
            self.ttfb = datetime.now() - self.init_ts
            logger.info("TTS TTFB {}ms".format(int(self.ttfb.total_seconds() * 1000)))

        # logger.info("audio result length: %d, %d", len(data), self.frame_size)
        try:
            f = self.get_frame(data)
            self.rte.send_pcm_frame(f)
        except Exception as e:
            logger.exception(e)


class CosyTTSExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)
        self.api_key = ""
        self.voice = ""
        self.model = ""
        self.sample_rate = 16000
        self.tts = None
        self.callback = None
        self.format = None

        self.outdate_ts = datetime.now()

        self.stopped = False
        self.thread = None
        self.queue = queue.Queue()

    def on_start(self, rte: RteEnv) -> None:
        logger.info("on_start")
        self.api_key = rte.get_property_string("api_key")
        self.voice = rte.get_property_string("voice")
        self.model = rte.get_property_string("model")
        self.sample_rate = rte.get_property_int("sample_rate")

        dashscope.api_key = self.api_key
        f = AudioFormat.PCM_16000HZ_MONO_16BIT
        if self.sample_rate == 8000:
            f = AudioFormat.PCM_8000HZ_MONO_16BIT
        elif self.sample_rate == 16000:
            f = AudioFormat.PCM_16000HZ_MONO_16BIT
        elif self.sample_rate == 22050:
            f = AudioFormat.PCM_22050HZ_MONO_16BIT
        elif self.sample_rate == 24000:
            f = AudioFormat.PCM_24000HZ_MONO_16BIT
        elif self.sample_rate == 44100:
            f = AudioFormat.PCM_44100HZ_MONO_16BIT
        elif self.sample_rate == 48000:
            f = AudioFormat.PCM_48000HZ_MONO_16BIT
        else:
            logger.error("unknown sample rate %d", self.sample_rate)
            exit()

        self.format = f

        self.thread = threading.Thread(target=self.async_handle, args=[rte])
        self.thread.start()
        rte.on_start_done()

    def on_stop(self, rte: RteEnv) -> None:
        logger.info("on_stop")

        self.stopped = True
        self.flush()
        self.queue.put(None)
        if self.thread is not None:
            self.thread.join()
            self.thread = None
        rte.on_stop_done()

    def need_interrupt(self, ts: datetime.time) -> bool:
        return self.outdate_ts > ts

    def async_handle(self, rte: RteEnv):
        try:
            tts = None
            callback = None
            while not self.stopped:
                try:
                    value = self.queue.get()
                    if value is None:
                        break
                    input_text, ts, end_of_segment = value

                    # clear tts if old one is closed already
                    if callback is not None and callback.closed is True:
                        tts = None
                        callback = None

                    # cancel last streaming call to avoid unprocessed audio coming back
                    if (
                        callback is not None
                        and tts is not None
                        and callback.need_interrupt()
                    ):
                        tts.streaming_cancel()
                        tts = None
                        callback = None

                    if self.need_interrupt(ts):
                        logger.info("drop outdated input")
                        continue

                    # create new tts if needed
                    if tts is None or callback is None:
                        logger.info("creating tts")
                        callback = CosyTTSCallback(
                            rte, self.sample_rate, self.need_interrupt
                        )
                        tts = SpeechSynthesizer(
                            model=self.model,
                            voice=self.voice,
                            format=self.format,
                            callback=callback,
                        )

                    logger.info(
                        "on message [{}] ts [{}] end_of_segment [{}]".format(
                            input_text, ts, end_of_segment
                        )
                    )

                    # make sure new data won't be marked as outdated
                    callback.set_input_ts(ts)

                    if len(input_text) > 0:
                        # last segment may have empty text but is_end is true
                        tts.streaming_call(input_text)

                    # complete the streaming call to drain remained audio
                    if True:  # end_of_segment:
                        try:
                            tts.streaming_complete()
                        except Exception as e:
                            logger.warning(e)
                        tts = None
                        callback = None
                except Exception as e:
                    logger.exception(e)
                    logger.exception(traceback.format_exc())
        finally:
            if tts is not None:
                tts.streaming_cancel()
                tts = None
                callback = None

    def flush(self):
        while not self.queue.empty():
            self.queue.get()

    def on_data(self, rte: RteEnv, data: Data) -> None:
        inputText = data.get_property_string("text")
        end_of_segment = data.get_property_bool("end_of_segment")

        logger.info("on data {} {}".format(inputText, end_of_segment))
        self.queue.put((inputText, datetime.now(), end_of_segment))

    def on_cmd(self, rte: RteEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        logger.info("on_cmd {}".format(cmd_name))
        if cmd_name == "flush":
            self.outdate_ts = datetime.now()
            self.flush()
            cmd_out = Cmd.create("flush")
            rte.send_cmd(cmd_out, lambda rte, result: print("send_cmd flush done"))
        else:
            logger.info("unknown cmd {}".format(cmd_name))

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "success")
        rte.return_result(cmd_result, cmd)

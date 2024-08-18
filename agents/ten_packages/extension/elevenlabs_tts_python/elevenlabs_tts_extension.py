#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024-07.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

import queue
import threading
import time

from ten import (
    Extension,
    TenEnv,
    Cmd,
    CmdResult,
    StatusCode,
    Data,
)
from .elevenlabs_tts import default_elevenlabs_tts_config, ElevenlabsTTS
from .pcm import PcmConfig, Pcm
from .log import logger

CMD_IN_FLUSH = "flush"
CMD_OUT_FLUSH = "flush"

DATA_IN_TEXT_DATA_PROPERTY_TEXT = "text"

PROPERTY_API_KEY = "api_key"  # Required
PROPERTY_MODEL_ID = "model_id"  # Optional
PROPERTY_OPTIMIZE_STREAMING_LATENCY = "optimize_streaming_latency"  # Optional
PROPERTY_REQUEST_TIMEOUT_SECONDS = "request_timeout_seconds"  # Optional
PROPERTY_SIMILARITY_BOOST = "similarity_boost"  # Optional
PROPERTY_SPEAKER_BOOST = "speaker_boost"  # Optional
PROPERTY_STABILITY = "stability"  # Optional
PROPERTY_STYLE = "style"  # Optional


class Message:
    def __init__(self, text: str, received_ts: int) -> None:
        self.text = text
        self.received_ts = received_ts


class ElevenlabsTTSExtension(Extension):
    def on_start(self, ten: TenEnv) -> None:
        logger.info("on_start")

        self.elevenlabs_tts = None
        self.outdate_ts = 0
        self.pcm = None
        self.pcm_frame_size = 0
        self.text_queue = queue.Queue(maxsize=1024)

        # prepare configuration
        elevenlabs_tts_config = default_elevenlabs_tts_config()

        try:
            elevenlabs_tts_config.api_key = ten.get_property_string(PROPERTY_API_KEY)
        except Exception as e:
            logger.warning(f"on_start get_property_string {PROPERTY_API_KEY} error: {e}")
            return

        try:
            model_id = ten.get_property_string(PROPERTY_MODEL_ID)
            if len(model_id) > 0:
                elevenlabs_tts_config.model_id = model_id
        except Exception as e:
            logger.warning(f"on_start get_property_string {PROPERTY_MODEL_ID} error: {e}")

        try:
            optimize_streaming_latency = ten.get_property_int(PROPERTY_OPTIMIZE_STREAMING_LATENCY)
            if optimize_streaming_latency > 0:
                elevenlabs_tts_config.optimize_streaming_latency = optimize_streaming_latency
        except Exception as e:
            logger.warning(f"on_start get_property_int {PROPERTY_OPTIMIZE_STREAMING_LATENCY} error: {e}")

        try:
            request_timeout_seconds = ten.get_property_int(PROPERTY_REQUEST_TIMEOUT_SECONDS)
            if request_timeout_seconds > 0:
                elevenlabs_tts_config.request_timeout_seconds = request_timeout_seconds
        except Exception as e:
            logger.warning(f"on_start get_property_int {PROPERTY_REQUEST_TIMEOUT_SECONDS} error: {e}")

        try:
            elevenlabs_tts_config.similarity_boost = ten.get_property_float(PROPERTY_SIMILARITY_BOOST)
        except Exception as e:
            logger.warning(f"on_start get_property_float {PROPERTY_SIMILARITY_BOOST} error: {e}")

        try:
            elevenlabs_tts_config.speaker_boost = ten.get_property_bool(PROPERTY_SPEAKER_BOOST)
        except Exception as e:
            logger.warning(f"on_start get_property_bool {PROPERTY_SPEAKER_BOOST} error: {e}")

        try:
            elevenlabs_tts_config.stability = ten.get_property_float(PROPERTY_STABILITY)
        except Exception as e:
            logger.warning(f"on_start get_property_float {PROPERTY_STABILITY} error: {e}")

        try:
            elevenlabs_tts_config.style = ten.get_property_float(PROPERTY_STYLE)
        except Exception as e:
            logger.warning(f"on_start get_property_float {PROPERTY_STYLE} error: {e}")

        # create elevenlabsTTS instance
        self.elevenlabs_tts = ElevenlabsTTS(elevenlabs_tts_config)

        logger.info(f"ElevenlabsTTS succeed with model_id: {self.elevenlabs_tts.config.model_id}, VoiceId: {self.elevenlabs_tts.config.voice_id}")

        # create pcm instance
        self.pcm = Pcm(PcmConfig())
        self.pcm_frame_size = self.pcm.get_pcm_frame_size()

        threading.Thread(target=self.process_text_queue, args=(ten,)).start()

        ten.on_start_done()

    def on_stop(self, ten: TenEnv) -> None:
        logger.info("on_stop")
        ten.on_stop_done()

    def on_cmd(self, ten: TenEnv, cmd: Cmd) -> None:
        """
        on_cmd receives cmd from ten graph.
        current supported cmd:
          - name: flush
            example:
            {"name": "flush"}
        """
        logger.info("on_cmd")
        cmd_name = cmd.get_name()

        logger.info(f"on_cmd [{cmd_name}]")

        if cmd_name is CMD_IN_FLUSH:
            self.outdate_ts = int(time.time() * 1000000)

            # send out
            out_cmd = Cmd.create(CMD_OUT_FLUSH)
            ten.send_cmd(out_cmd)

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "success")
        ten.return_result(cmd_result, cmd)

    def on_data(self, ten: TenEnv, data: Data) -> None:
        """
        on_data receives data from ten graph.
        current supported data:
          - name: text_data
            example:
            {name: text_data, properties: {text: "hello"}
        """
        logger.info("on_data")

        try:
            text = data.get_property_string(DATA_IN_TEXT_DATA_PROPERTY_TEXT)
        except Exception as e:
            logger.warning(f"on_data get_property_string {DATA_IN_TEXT_DATA_PROPERTY_TEXT} error: {e}")
            return

        if len(text) == 0:
            logger.debug("on_data text is empty, ignored")
            return

        logger.info(f"OnData input text: [{text}]")

        self.text_queue.put(Message(text, int(time.time() * 1000000)))

    def process_text_queue(self, ten: TenEnv):
        logger.info("process_text_queue")

        while True:
            msg = self.text_queue.get()
            logger.debug(f"process_text_queue, text: [{msg.text}]")

            if msg.received_ts < self.outdate_ts:
                logger.info(f"textChan interrupt and flushing for input text: [{msg.text}], received_ts: {msg.received_ts}, outdate_ts: {self.outdate_ts}")
                continue

            start_time = time.time()
            buf = self.pcm.new_buf()
            first_frame_latency = 0
            n = 0
            pcm_frame_read = 0
            read_bytes = 0
            sent_frames = 0

            audio_stream = self.elevenlabs_tts.text_to_speech_stream(msg.text)

            for chunk in self.pcm.read_pcm_stream(audio_stream, self.pcm_frame_size):
                if msg.received_ts < self.outdate_ts:
                    logger.info(f"textChan interrupt and flushing for input text: [{msg.text}], received_ts: {msg.received_ts}, outdate_ts: {self.outdate_ts}")
                    break

                if not chunk:
                    logger.info("read pcm stream EOF")
                    break

                n = len(chunk)
                read_bytes += n
                pcm_frame_read += n

                if pcm_frame_read != self.pcm.get_pcm_frame_size():
                    logger.debug(f"the number of bytes read is [{pcm_frame_read}] inconsistent with pcm frame size")
                    continue

                self.pcm.send(ten, buf)
                buf = self.pcm.new_buf()
                pcm_frame_read = 0
                sent_frames += 1

                if first_frame_latency == 0:
                    first_frame_latency = int((time.time() - start_time) * 1000)
                    logger.info(f"first frame available for text: [{msg.text}], received_ts: {msg.received_ts}, first_frame_latency: {first_frame_latency}ms")

                logger.debug(f"sending pcm data, text: [{msg.text}]")

            if pcm_frame_read > 0:
                self.pcm.send(ten, buf)
                sent_frames += 1
                logger.info(f"sending pcm remain data, text: [{msg.text}], pcm_frame_read: {pcm_frame_read}")

            finish_latency = int((time.time() - start_time) * 1000)
            logger.info(f"send pcm data finished, text: [{msg.text}], received_ts: {msg.received_ts}, read_bytes: {read_bytes}, sent_frames: {sent_frames},
                first_frame_latency: {first_frame_latency}ms, finish_latency: {finish_latency}ms"
            )

#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024-07.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

import logging
import queue
import threading
import time

from rte_runtime_python import (
    Addon,
    Extension,
    register_addon_as_extension,
    Rte,
    Cmd,
    CmdResult,
    StatusCode,
    Data,
    MetadataInfo,
)
from elevenlabs_tts import default_elevenlabs_tts_config, ElevenlabsTTS
from pcm import PcmConfig, Pcm

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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(process)d - [%(filename)s:%(lineno)d] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
    encoding="utf-8",
)


class Message:
    def __init__(self, text: str, received_ts: int) -> None:
        self.text = text
        self.received_ts = received_ts


class ElevenlabsTTSExtension(Extension):
    def on_init(self, rte: Rte, manifest: MetadataInfo, property: MetadataInfo) -> None:
        logging.info("on_init")

        self.elevenlabs_tts = None
        self.outdate_ts = 0
        self.pcm = None
        self.pcm_frame_size = 0
        self.text_queue = queue.Queue(maxsize=1024)

        rte.on_init_done(manifest, property)

    def on_start(self, rte: Rte) -> None:
        logging.info("on_start")

        # prepare configuration
        elevenlabs_tts_config = default_elevenlabs_tts_config()

        try:
            elevenlabs_tts_config.api_key = rte.get_property_string(PROPERTY_API_KEY)
        except Exception as e:
            logging.warning(
                f"on_start get_property_string {PROPERTY_API_KEY} error: {e}"
            )
            return

        try:
            model_id = rte.get_property_string(PROPERTY_MODEL_ID)
            if len(model_id) > 0:
                elevenlabs_tts_config.model_id = model_id
        except Exception as e:
            logging.warning(
                f"on_start get_property_string {PROPERTY_MODEL_ID} error: {e}"
            )

        try:
            optimize_streaming_latency = rte.get_property_int(
                PROPERTY_OPTIMIZE_STREAMING_LATENCY
            )
            if optimize_streaming_latency > 0:
                elevenlabs_tts_config.optimize_streaming_latency = (
                    optimize_streaming_latency
                )
        except Exception as e:
            logging.warning(
                f"on_start get_property_int {PROPERTY_OPTIMIZE_STREAMING_LATENCY} error: {e}"
            )

        try:
            request_timeout_seconds = rte.get_property_int(
                PROPERTY_REQUEST_TIMEOUT_SECONDS
            )
            if request_timeout_seconds > 0:
                elevenlabs_tts_config.request_timeout_seconds = request_timeout_seconds
        except Exception as e:
            logging.warning(
                f"on_start get_property_int {PROPERTY_REQUEST_TIMEOUT_SECONDS} error: {e}"
            )

        try:
            elevenlabs_tts_config.similarity_boost = rte.get_property_float(
                PROPERTY_SIMILARITY_BOOST
            )
        except Exception as e:
            logging.warning(
                f"on_start get_property_float {PROPERTY_SIMILARITY_BOOST} error: {e}"
            )

        try:
            elevenlabs_tts_config.speaker_boost = rte.get_property_bool(
                PROPERTY_SPEAKER_BOOST
            )
        except Exception as e:
            logging.warning(
                f"on_start get_property_bool {PROPERTY_SPEAKER_BOOST} error: {e}"
            )

        try:
            elevenlabs_tts_config.stability = rte.get_property_float(PROPERTY_STABILITY)
        except Exception as e:
            logging.warning(
                f"on_start get_property_float {PROPERTY_STABILITY} error: {e}"
            )

        try:
            elevenlabs_tts_config.style = rte.get_property_float(PROPERTY_STYLE)
        except Exception as e:
            logging.warning(f"on_start get_property_float {PROPERTY_STYLE} error: {e}")

        # create elevenlabsTTS instance
        self.elevenlabs_tts = ElevenlabsTTS(elevenlabs_tts_config)

        logging.info(
            f"ElevenlabsTTS succeed with model_id: {self.elevenlabs_tts.config.model_id}, VoiceId: {self.elevenlabs_tts.config.voice_id}"
        )

        # create pcm instance
        self.pcm = Pcm(PcmConfig())
        self.pcm_frame_size = self.pcm.get_pcm_frame_size()

        threading.Thread(target=self.process_text_queue, args=(rte,)).start()

        rte.on_start_done()

    def on_stop(self, rte: Rte) -> None:
        logging.info("on_stop")
        rte.on_stop_done()

    def on_deinit(self, rte: Rte) -> None:
        logging.info("on_deinit")
        rte.on_deinit_done()

    def on_cmd(self, rte: Rte, cmd: Cmd) -> None:
        """
        on_cmd receives cmd from rte graph.
        current supported cmd:
          - name: flush
            example:
            {"name": "flush"}
        """
        logging.info("on_cmd")
        cmd_name = cmd.get_name()

        logging.info(f"on_cmd [{cmd_name}]")

        if cmd_name is CMD_IN_FLUSH:
            self.outdate_ts = int(time.time() * 1000000)

            # send out
            out_cmd = cmd.create(CMD_OUT_FLUSH)
            rte.send_cmd(out_cmd)

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "success")
        rte.return_result(cmd_result, cmd)

    def on_data(self, rte: Rte, data: Data) -> None:
        """
        on_data receives data from rte graph.
        current supported data:
          - name: text_data
            example:
            {name: text_data, properties: {text: "hello"}
        """
        logging.info("on_data")

        try:
            text = data.get_property_string(DATA_IN_TEXT_DATA_PROPERTY_TEXT)
        except Exception as e:
            logging.warning(
                f"on_data get_property_string {DATA_IN_TEXT_DATA_PROPERTY_TEXT} error: {e}"
            )
            return

        if len(text) == 0:
            logging.debug("on_data text is empty, ignored")
            return

        logging.info(f"OnData input text: [{text}]")

        self.text_queue.put(Message(text, int(time.time() * 1000000)))

    def process_text_queue(self, rte: Rte):
        logging.info("process_text_queue")

        while True:
            msg = self.text_queue.get()
            if msg.received_ts < self.outdate_ts:
                logging.info(
                    f"textChan interrupt and flushing for input text: [{msg.text}], received_ts: {msg.received_ts}, outdate_ts: {self.outdate_ts}"
                )
                continue

            start_time = time.time()
            buf = self.pcm.new_buf()
            first_frame_latency = 0
            n = 0
            pcm_frame_read = 0
            read_bytes = 0
            sent_frames = 0

            audio_stream = self.elevenlabs_tts.text_to_speech_stream(msg)

            for chunk in self.pcm.read_pcm_stream(audio_stream, self.pcm_frame_size):
                if msg.received_ts < self.outdate_ts:
                    logging.info(
                        f"textChan interrupt and flushing for input text: [{msg.text}], received_ts: {msg.received_ts}, outdate_ts: {self.outdate_ts}"
                    )
                    break

                if not chunk:
                    logging.info("read pcm stream EOF")
                    break

                n = len(chunk)
                read_bytes += n
                pcm_frame_read += n

                if pcm_frame_read != self.pcm.get_pcm_frame_size():
                    logging.debug(
                        f"the number of bytes read is [{pcm_frame_read}] inconsistent with pcm frame size",
                    )
                    continue

                self.pcm.send(rte, buf)
                buf = self.pcm.new_buf()
                pcm_frame_read = 0
                sent_frames += 1

                if first_frame_latency == 0:
                    first_frame_latency = int((time.time() - start_time) * 1000)
                    logging.info(
                        f"first frame available for text: [{msg.text}], received_ts: {msg.received_ts}, first_frame_latency: {first_frame_latency}ms",
                    )

                logging.debug(f"sending pcm data, text: [{msg.text}]")

            if pcm_frame_read > 0:
                self.pcm.send(rte, buf)
                sent_frames += 1
                logging.info(
                    f"sending pcm remain data, text: [{msg.text}], pcm_frame_read: {pcm_frame_read}"
                )

            finish_latency = int((time.time() - start_time) * 1000)
            logging.info(
                f"send pcm data finished, text: [{msg.text}], received_ts: {msg.received_ts}, read_bytes: {read_bytes}, sent_frames: {sent_frames}, \
                first_frame_latency: {first_frame_latency}ms, finish_latency: {finish_latency}ms"
            )


@register_addon_as_extension("elevenlabs_tts_python")
class ElevenlabsTTSExtensionAddon(Addon):
    def on_init(self, rte: Rte, manifest, property) -> None:
        logging.info("on_init")
        rte.on_init_done(manifest, property)
        return

    def on_create_instance(self, rte: Rte, addon_name: str) -> Extension:
        logging.info("on_create_instance")
        return ElevenlabsTTSExtension(addon_name)

    def on_deinit(self, rte: Rte) -> None:
        logging.info("on_deinit")
        rte.on_deinit_done()
        return

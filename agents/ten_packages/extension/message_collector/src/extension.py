#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import json
import time
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



CMD_NAME_FLUSH = "flush"

TEXT_DATA_TEXT_FIELD = "text"
TEXT_DATA_FINAL_FIELD = "is_final"
TEXT_DATA_STREAM_ID_FIELD = "stream_id"
TEXT_DATA_END_OF_SEGMENT_FIELD = "end_of_segment"

# record the cached text data for each stream id
cached_text_map = {}


class MessageCollectorExtension(Extension):
    def on_init(self, ten_env: TenEnv) -> None:
        logger.info("MessageCollectorExtension on_init")
        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        logger.info("MessageCollectorExtension on_start")

        # TODO: read properties, initialize resources

        ten_env.on_start_done()

    def on_stop(self, ten_env: TenEnv) -> None:
        logger.info("MessageCollectorExtension on_stop")

        # TODO: clean up resources

        ten_env.on_stop_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        logger.info("MessageCollectorExtension on_deinit")
        ten_env.on_deinit_done()

    def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        logger.info("on_cmd name {}".format(cmd_name))

        # TODO: process cmd

        cmd_result = CmdResult.create(StatusCode.OK)
        ten_env.return_result(cmd_result, cmd)

    def on_data(self, ten_env: TenEnv, data: Data) -> None:
        """
        on_data receives data from ten graph.
        current suppotend data:
          - name: text_data
            example:
            {"name": "text_data", "properties": {"text": "hello", "is_final": true, "stream_id": 123, "end_of_segment": true}}
        """
        logger.info(f"on_data")

        text = ""
        final = True
        stream_id = 0
        end_of_segment = False

        try:
            text = data.get_property_string(TEXT_DATA_TEXT_FIELD)
        except Exception as e:
            logger.exception(
                f"on_data get_property_string {TEXT_DATA_TEXT_FIELD} error: {e}"
            )

        try:
            final = data.get_property_bool(TEXT_DATA_FINAL_FIELD)
        except Exception as e:
            logger.exception(
                f"on_data get_property_bool {TEXT_DATA_FINAL_FIELD} error: {e}"
            )

        try:
            stream_id = data.get_property_int(TEXT_DATA_STREAM_ID_FIELD)
        except Exception as e:
            logger.exception(
                f"on_data get_property_int {TEXT_DATA_STREAM_ID_FIELD} error: {e}"
            )

        try:
            end_of_segment = data.get_property_bool(TEXT_DATA_END_OF_SEGMENT_FIELD)
        except Exception as e:
            logger.exception(
                f"on_data get_property_bool {TEXT_DATA_END_OF_SEGMENT_FIELD} error: {e}"
            )

        logger.debug(
            f"on_data {TEXT_DATA_TEXT_FIELD}: {text} {TEXT_DATA_FINAL_FIELD}: {final} {TEXT_DATA_STREAM_ID_FIELD}: {stream_id} {TEXT_DATA_END_OF_SEGMENT_FIELD}: {end_of_segment}"
        )

        # We cache all final text data and append the non-final text data to the cached data
        # until the end of the segment.
        if end_of_segment:
            if stream_id in cached_text_map:
                text = cached_text_map[stream_id] + text
                del cached_text_map[stream_id]
        else:
            if final:
                if stream_id in cached_text_map:
                    text = cached_text_map[stream_id] + text

                cached_text_map[stream_id] = text

        msg_data = json.dumps({
            "text": text,
            "is_final": end_of_segment,
            "stream_id": stream_id,
            "data_type": "transcribe",
            "text_ts": int(time.time() * 1000),  # Convert to milliseconds
        })

        try:
            # convert the origin text data to the protobuf data and send it to the graph.
            ten_data = Data.create("data")
            ten_data.set_property_buf("data", msg_data.encode())
            ten_env.send_data(ten_data)
        except Exception as e:
            logger.warning(f"on_data new_data error: {e}")
            return

    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        # TODO: process pcm frame
        pass

    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        # TODO: process image frame
        pass

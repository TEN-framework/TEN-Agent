#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024-07.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

import json
from ten import (
    Extension,
    TenEnv,
    Cmd,
    Data,
    StatusCode,
    CmdResult,
    MetadataInfo,
)
import time
from .pb import chat_text_pb2 as pb
from .log import logger

CMD_NAME_FLUSH = "flush"

TEXT_DATA_TEXT_FIELD = "text"
TEXT_DATA_FINAL_FIELD = "is_final"
TEXT_DATA_STREAM_ID_FIELD = "stream_id"
TEXT_DATA_END_OF_SEGMENT_FIELD = "end_of_segment"

# record the cached text data for each stream id
cached_text_map = {}


class ChatTranscriberExtension(Extension):
    def on_start(self, ten: TenEnv) -> None:
        logger.info("on_start")
        ten.on_start_done()

    def on_stop(self, ten: TenEnv) -> None:
        logger.info("on_stop")
        ten.on_stop_done()

    def on_cmd(self, ten: TenEnv, cmd: Cmd) -> None:
        logger.info("on_cmd")
        cmd_json = cmd.to_json()
        logger.info("on_cmd json: {}".format(cmd_json))

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "success")
        ten.return_result(cmd_result, cmd)

    def on_data(self, ten: TenEnv, data: Data) -> None:
        """
        on_data receives data from ten graph.
        current suppotend data:
          - name: text_data
            example:
            {"name": "text_data", "properties": {"text": "hello", "is_final": true, "stream_id": 123, "end_of_segment": true}}
        """
        logger.info(f"on_data")

        try:
            text = data.get_property_string(TEXT_DATA_TEXT_FIELD)
        except Exception as e:
            logger.exception(
                f"on_data get_property_string {TEXT_DATA_TEXT_FIELD} error: {e}"
            )
            return

        try:
            final = data.get_property_bool(TEXT_DATA_FINAL_FIELD)
        except Exception as e:
            logger.exception(
                f"on_data get_property_bool {TEXT_DATA_FINAL_FIELD} error: {e}"
            )
            return

        try:
            stream_id = data.get_property_int(TEXT_DATA_STREAM_ID_FIELD)
        except Exception as e:
            logger.exception(
                f"on_data get_property_int {TEXT_DATA_STREAM_ID_FIELD} error: {e}"
            )
            return

        try:
            end_of_segment = data.get_property_bool(TEXT_DATA_END_OF_SEGMENT_FIELD)
        except Exception as e:
            logger.exception(
                f"on_data get_property_bool {TEXT_DATA_END_OF_SEGMENT_FIELD} error: {e}"
            )
            return

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

        pb_text = pb.Text(
            uid=stream_id,
            data_type="transcribe",
            texttime=int(time.time() * 1000),  # Convert to milliseconds
            words=[
                pb.Word(
                    text=text,
                    is_final=end_of_segment,
                ),
            ],
        )

        try:
            pb_serialized_text = pb_text.SerializeToString()
        except Exception as e:
            logger.warning(f"on_data SerializeToString error: {e}")
            return

        try:
            # convert the origin text data to the protobuf data and send it to the graph.
            ten_data = Data.create("data")
            ten_data.set_property_buf("data", pb_serialized_text)
            ten.send_data(ten_data)
            logger.info("data sent")
        except Exception as e:
            logger.warning(f"on_data new_data error: {e}")
            return

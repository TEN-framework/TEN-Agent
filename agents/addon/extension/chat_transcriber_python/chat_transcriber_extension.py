#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024-07.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

from rte_runtime_python import (
    Addon,
    Extension,
    register_addon_as_extension,
    Rte,
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
    def on_init(self, rte: Rte, manifest: MetadataInfo, property: MetadataInfo) -> None:
        logger.info("on_init")
        rte.on_init_done(manifest, property)

    def on_start(self, rte: Rte) -> None:
        logger.info("on_start")
        rte.on_start_done()

    def on_stop(self, rte: Rte) -> None:
        logger.info("on_stop")
        rte.on_stop_done()

    def on_deinit(self, rte: Rte) -> None:
        logger.info("on_deinit")
        rte.on_deinit_done()

    def on_cmd(self, rte: Rte, cmd: Cmd) -> None:
        logger.info("on_cmd")
        cmd_json = cmd.to_json()
        logger.info("on_cmd json: {}".format(cmd_json))

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "success")
        rte.return_result(cmd_result, cmd)

    def on_data(self, rte: Rte, data: Data) -> None:
        """
        on_data receives data from rte graph.
        current supported data:
          - name: text_data
            example:
            {"name": "text_data", "properties": {"text": "hello", "is_final": true, "stream_id": 123, "end_of_segment": true}}
        """
        logger.info(f"on_data")

        try:
            text = data.get_property_string(TEXT_DATA_TEXT_FIELD)
        except Exception as e:
            logger.warning(
                f"on_data get_property_string {TEXT_DATA_TEXT_FIELD} error: {e}"
            )
            return

        try:
            final = data.get_property_bool(TEXT_DATA_FINAL_FIELD)
        except Exception as e:
            logger.warning(
                f"on_data get_property_bool {TEXT_DATA_FINAL_FIELD} error: {e}"
            )
            return

        try:
            stream_id = data.get_property_int(TEXT_DATA_STREAM_ID_FIELD)
        except Exception as e:
            logger.warning(
                f"on_data get_property_int {TEXT_DATA_STREAM_ID_FIELD} error: {e}"
            )
            return

        try:
            end_of_segment = data.get_property_bool(TEXT_DATA_END_OF_SEGMENT_FIELD)
        except Exception as e:
            logger.warning(
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
            rte_data = Data.create("data")
            # rte_data.set_property_string("data", pb_serialized_text)
            rte_data.alloc_buf(len(pb_serialized_text))
            buf = rte_data.lock_buf()
            buf[:] = pb_serialized_text[:]
            rte_data.unlock_buf(buf)
            rte.send_data(rte_data)
            logger.info("data sent")
        except Exception as e:
            logger.warning(f"on_data new_data error: {e}")
            return

@register_addon_as_extension("chat_transcriber_python")
class ChatTranscriberExtensionAddon(Addon):
    def on_init(self, rte: Rte, manifest, property) -> None:
        logger.info("on_init")
        rte.on_init_done(manifest, property)
        return

    def on_create_instance(self, rte: Rte, addon_name: str, context) -> None:
        logger.info("on_create_instance")
        rte.on_create_instance_done(ChatTranscriberExtension(addon_name), context)

    def on_deinit(self, rte: Rte) -> None:
        logger.info("on_deinit")
        rte.on_deinit_done()
        return

#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import json
import time
import uuid
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

MAX_SIZE = 800  # 1 KB limit
OVERHEAD_ESTIMATE = 200  # Estimate for the overhead of metadata in the JSON

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
            pass

        try:
            stream_id = data.get_property_int(TEXT_DATA_STREAM_ID_FIELD)
        except Exception as e:
            pass

        try:
            end_of_segment = data.get_property_bool(TEXT_DATA_END_OF_SEGMENT_FIELD)
        except Exception as e:
            logger.warning(
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

        # Generate a unique message ID for this batch of parts
        message_id = str(uuid.uuid4())

        # Prepare the main JSON structure without the text field
        base_msg_data = {
            "is_final": end_of_segment,
            "stream_id": stream_id,
            "message_id": message_id,  # Add message_id to identify the split message
            "data_type": "transcribe",
            "text_ts": int(time.time() * 1000),  # Convert to milliseconds
        }

        try:
            # Convert the text to UTF-8 bytes
            text_bytes = text.encode('utf-8')

            # If the text + metadata fits within the size limit, send it directly
            if len(text_bytes) + OVERHEAD_ESTIMATE <= MAX_SIZE:
                base_msg_data["text"] = text
                msg_data = json.dumps(base_msg_data)
                ten_data = Data.create("data")
                ten_data.set_property_buf("data", msg_data.encode())
                ten_env.send_data(ten_data)
            else:
                # Split the text bytes into smaller chunks, ensuring safe UTF-8 splitting
                max_text_size = MAX_SIZE - OVERHEAD_ESTIMATE
                total_length = len(text_bytes)
                total_parts = (total_length + max_text_size - 1) // max_text_size  # Calculate number of parts
                
                def get_valid_utf8_chunk(start, end):
                    """Helper function to ensure valid UTF-8 chunks."""
                    while end > start:
                        try:
                            # Decode to check if this chunk is valid UTF-8
                            text_part = text_bytes[start:end].decode('utf-8')
                            return text_part, end
                        except UnicodeDecodeError:
                            # Reduce the end point to avoid splitting in the middle of a character
                            end -= 1
                    # If no valid chunk is found (shouldn't happen with valid UTF-8 input), return an empty string
                    return "", start

                part_number = 0
                start_index = 0
                while start_index < total_length:
                    part_number += 1
                    # Get a valid UTF-8 chunk
                    text_part, end_index = get_valid_utf8_chunk(start_index, min(start_index + max_text_size, total_length))
                    
                    # Prepare the part data with metadata
                    part_data = base_msg_data.copy()
                    part_data.update({
                        "text": text_part,
                        "part_number": part_number,
                        "total_parts": total_parts,
                    })
                    
                    # Send each part
                    part_msg_data = json.dumps(part_data)
                    ten_data = Data.create("data")
                    ten_data.set_property_buf("data", part_msg_data.encode())
                    ten_env.send_data(ten_data)

                    # Move to the next chunk
                    start_index = end_index

        except Exception as e:
            logger.warning(f"on_data new_data error: {e}")
            return

    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        # TODO: process pcm frame
        pass

    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        # TODO: process image frame
        pass

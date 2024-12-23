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
import asyncio

from ten import (
    AudioFrame,
    VideoFrame,
    AsyncExtension,
    AsyncTenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)

TEXT_DATA_TEXT_FIELD = "text"
TEXT_DATA_FINAL_FIELD = "is_final"
TEXT_DATA_STREAM_ID_FIELD = "stream_id"
TEXT_DATA_END_OF_SEGMENT_FIELD = "end_of_segment"


class MessageCollectorRTMExtension(AsyncExtension):
    # Create the queue for message processing
    def __init__(self, name: str):
        super().__init__(name)
        self.queue = asyncio.Queue()
        self.cached_text_map = {}
        self.loop = None
        self.ten_env = None
        self.stopped = False

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("MessageCollectorRTMExtension on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("MessageCollectorRTMExtension on_start")
        self.loop = asyncio.get_event_loop()
        self.ten_env = ten_env
        self.loop.create_task(self._process_queue())

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("on_stop")
        self.stopped = True
        await self.queue.put(None)

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("MessageCollectorRTMExtension on_deinit")

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_info("on_cmd name {}".format(cmd_name))
        try:
            if cmd_name == "on_user_audio_track_state_changed":
                await self.handle_user_state_changed(cmd)
            else:
                ten_env.log_warn(f"unsupported cmd {cmd_name}")

            cmd_result = CmdResult.create(StatusCode.OK)
            await ten_env.return_result(cmd_result, cmd)
        except Exception as e:
            ten_env.log_error(f"on_cmd error: {e}")
            cmd_result = CmdResult.create(StatusCode.ERROR)
            await ten_env.return_result(cmd_result, cmd)

    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        """
        on_data receives data from ten graph.
        current suppotend data:
          - name: text_data
            example:
            {"name": "text_data", "properties": {"text": "hello", "is_final": true, "stream_id": 123, "end_of_segment": true}}
          - name: rtm_message_event
            example:
            {"name": "rtm_message_event", "properties": {"message": "hello"}}
        """
        data_name = data.get_name()
        if data_name == "text_data":
            await self.on_text_data(data)
        elif data_name == "rtm_message_event":
            await self.on_rtm_message_event(data)
        else:
            ten_env.log_warn(f"unsupported data {data_name}")

    async def on_audio_frame(
        self, ten_env: AsyncTenEnv, audio_frame: AudioFrame
    ) -> None:
        pass

    async def on_video_frame(
        self, ten_env: AsyncTenEnv, video_frame: VideoFrame
    ) -> None:
        pass

    async def on_text_data(self, data: Data) -> None:
        text = ""
        final = True
        stream_id = 0
        end_of_segment = False

        try:
            text = data.get_property_string(TEXT_DATA_TEXT_FIELD)
        except Exception as e:
            self.ten_env.log_error(
                f"on_data get_property_string {TEXT_DATA_TEXT_FIELD} error: {e}"
            )

        try:
            final = data.get_property_bool(TEXT_DATA_FINAL_FIELD)
        except Exception:
            pass

        try:
            stream_id = data.get_property_int(TEXT_DATA_STREAM_ID_FIELD)
        except Exception:
            pass

        try:
            end_of_segment = data.get_property_bool(TEXT_DATA_END_OF_SEGMENT_FIELD)
        except Exception as e:
            self.ten_env.log_error(
                f"on_data get_property_bool {TEXT_DATA_END_OF_SEGMENT_FIELD} error: {e}"
            )

        self.ten_env.log_debug(
            f"on_data {TEXT_DATA_TEXT_FIELD}: {text} {TEXT_DATA_FINAL_FIELD}: {final} {TEXT_DATA_STREAM_ID_FIELD}: {stream_id} {TEXT_DATA_END_OF_SEGMENT_FIELD}: {end_of_segment}"
        )

        # We cache all final text data and append the non-final text data to the cached data
        # until the end of the segment.
        if end_of_segment:
            if stream_id in self.cached_text_map:
                text = self.cached_text_map[stream_id] + text
                del self.cached_text_map[stream_id]
        else:
            if final:
                if stream_id in self.cached_text_map:
                    text = self.cached_text_map[stream_id] + text

                self.cached_text_map[stream_id] = text

        # Generate a unique message ID for this batch of parts
        message_id = str(uuid.uuid4())[:8]
        # Prepare the main JSON structure without the text field
        text_data = {
            "is_final": end_of_segment,
            "stream_id": stream_id,
            "message_id": message_id,  # Add message_id to identify the split message
            "type": "transcribe",
            "ts": int(time.time() * 1000),  # Convert to milliseconds
            "text": text,
        }
        await self._queue_message("text_data", text_data)

    async def on_rtm_message_event(self, data: Data) -> None:
        self.ten_env.log_debug("on_data rtm_message_event")
        try:
            text = data.get_property_string("message")
            data = Data.create("text_data")
            data.set_property_string("text", text)
            data.set_property_bool("is_final", True)
            asyncio.create_task(self.ten_env.send_data(data))
        except Exception as e:
            self.ten_env.log_error(f"Failed to handle on_rtm_message_event data: {e}")

    async def handle_user_state_changed(self, cmd: Cmd) -> None:
        try:
            remote_user_id = cmd.get_property_string("remote_user_id")
            state = cmd.get_property_int("state")
            reason = cmd.get_property_int("reason")
            self.ten_env.log_info(
                f"handle_user_state_changed user_id: {remote_user_id} state: {state} reason: {reason}"
            )
            user_state = {
                "remote_user_id": remote_user_id,
                "state": str(state),
                "reason": str(reason),
            }
            await self._queue_message("user_state", user_state)
        except Exception as e:
            self.ten_env.log_error(f"handle_user_state_changed error: {e}")

    async def _queue_message(self, data_type: str, data: dict):
        await self.queue.put({"type": data_type, "data": data})

    async def _process_queue(self):
        self.ten_env.log_info("start async loop")
        while not self.stopped:
            try:
                item = await self.queue.get()
                if item is None:
                    break
                data_type = item["type"]
                data = item["data"]
                # process data
                if data_type == "text_data":
                    await self._handle_text_data(data)
                elif data_type == "user_state":
                    await self._handle_user_state(data)
                self.queue.task_done()
                await asyncio.sleep(0.04)
            except Exception as e:
                self.ten_env.log_error(f"Failed to process queue: {e}")

    async def _handle_text_data(self, data: dict):
        try:
            self.ten_env.log_debug(f"Handling text data: {data}")
            json_bytes = json.dumps(data).encode("utf-8")
            cmd = Cmd.create("publish")
            cmd.set_property_buf("message", json_bytes)
            cmd_result: CmdResult = await self.ten_env.send_cmd(cmd)
            self.ten_env.log_info(f"send_cmd result {cmd_result.to_json()}")
        except Exception as e:
            self.ten_env.log_error(f"Failed to handle text data: {e}")

    async def _handle_user_state(self, data: dict):
        try:
            json_bytes = json.dumps(data)
            cmd = Cmd.create("set_presence_state")
            cmd.set_property_string("states", json_bytes)
            cmd_result: CmdResult = await self.ten_env.send_cmd(cmd)
            self.ten_env.log_info(f"send_cmd result {cmd_result.to_json()}")
        except Exception as e:
            self.ten_env.log_error(f"Failed to handle user state: {e}")

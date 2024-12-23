#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from ten import (
    AudioFrame,
    VideoFrame,
    AudioFrameDataFmt,
    AsyncExtension,
    AsyncTenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)
from .util import duration_in_ms, duration_in_ms_since, Role
from .chat_memory import ChatMemory
from dataclasses import dataclass, fields
import builtins
import httpx
from datetime import datetime
import aiofiles
import asyncio
from typing import List, Dict, Tuple, Any
import base64
import json


@dataclass
class MinimaxV2VConfig:
    token: str = ""
    max_tokens: int = 1024
    model: str = "abab6.5s-chat"
    voice_model: str = "speech-01-turbo-240228"
    voice_id: str = "female-tianmei"
    in_sample_rate: int = 16000
    out_sample_rate: int = 32000
    prompt: str = (
        "You are a voice assistant who talks in a conversational way and can chat with me like my friends. I will speak to you in English or Chinese, and you will answer in the corrected and improved version of my text with the language I use. Don’t talk like a robot, instead I would like you to talk like a real human with emotions. I will use your answer for text-to-speech, so don’t return me any meaningless characters. I want you to be helpful, when I’m asking you for advice, give me precise, practical and useful advice instead of being vague. When giving me a list of options, express the options in a narrative way instead of bullet points."
    )
    greeting: str = ""
    max_memory_length: int = 10
    dump: bool = False

    def read_from_property(self, ten_env: AsyncTenEnv):
        for field in fields(self):
            # 'is_property_exist' has a bug that can not be used in async extension currently, use it instead of try .. except once fixed
            # if not ten_env.is_property_exist(field.name):
            #     continue
            try:
                match field.type:
                    case builtins.str:
                        val = ten_env.get_property_string(field.name)
                        if val:
                            setattr(self, field.name, val)
                            ten_env.log_info(f"{field.name}={val}")
                    case builtins.int:
                        val = ten_env.get_property_int(field.name)
                        setattr(self, field.name, val)
                        ten_env.log_info(f"{field.name}={val}")
                    case builtins.bool:
                        val = ten_env.get_property_bool(field.name)
                        setattr(self, field.name, val)
                        ten_env.log_info(f"{field.name}={val}")
                    case _:
                        pass
            except Exception as e:
                ten_env.log_warn(f"get property for {field.name} failed, err {e}")


class MinimaxV2VExtension(AsyncExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)

        self.config = MinimaxV2VConfig()
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(5))
        self.memory = ChatMemory(self.config.max_memory_length)
        self.remote_stream_id = 0
        self.ten_env = None

        # able to cancel
        self.curr_task = None

        # make sure tasks processing in order
        self.process_input_task = None
        self.queue = asyncio.Queue()

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        self.config.read_from_property(ten_env=ten_env)
        ten_env.log_info(f"config: {self.config}")

        self.memory = ChatMemory(self.config.max_memory_length)
        self.ten_env = ten_env

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        self.process_input_task = asyncio.create_task(
            self._process_input(ten_env=ten_env, queue=self.queue), name="process_input"
        )

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:

        await self._flush(ten_env=ten_env)
        self.queue.put_nowait(None)
        if self.process_input_task:
            self.process_input_task.cancel()
            await asyncio.gather(self.process_input_task, return_exceptions=True)
            self.process_input_task = None

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_deinit")

        if self.client:
            await self.client.aclose()
            self.client = None
        self.ten_env = None

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        try:
            cmd_name = cmd.get_name()
            ten_env.log_debug("on_cmd name {}".format(cmd_name))

            # process cmd
            match cmd_name:
                case "flush":
                    await self._flush(ten_env=ten_env)
                    _result = await ten_env.send_cmd(Cmd.create("flush"))
                    ten_env.log_debug("flush done")
                case _:
                    pass
            await ten_env.return_result(CmdResult.create(StatusCode.OK), cmd)
        except asyncio.CancelledError:
            ten_env.log_warn(f"cmd {cmd_name} cancelled")
            await ten_env.return_result(CmdResult.create(StatusCode.ERROR), cmd)
            raise
        except Exception as e:
            ten_env.log_warn(f"cmd {cmd_name} failed, err {e}")
        finally:
            pass

    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        pass

    async def on_audio_frame(
        self, ten_env: AsyncTenEnv, audio_frame: AudioFrame
    ) -> None:

        try:
            ts = datetime.now()
            stream_id = audio_frame.get_property_int("stream_id")
            if not self.remote_stream_id:
                self.remote_stream_id = stream_id

            frame_buf = audio_frame.get_buf()
            ten_env.log_debug(f"on audio frame {len(frame_buf)} {stream_id}")

            # process audio frame, must be after vad
            # put_nowait to make sure put in_order
            self.queue.put_nowait((ts, frame_buf))
            # await self._complete_with_history(ts, frame_buf)

            # dump input audio if need
            await self._dump_audio_if_need(frame_buf, "in")

            # ten_env.log_debug(f"on audio frame {len(frame_buf)} {stream_id} put done")
        except asyncio.CancelledError:
            ten_env.log_warn("on audio frame cancelled")
            raise
        except Exception as e:
            ten_env.log_error(f"on audio frame failed, err {e}")

    async def on_video_frame(
        self, ten_env: AsyncTenEnv, video_frame: VideoFrame
    ) -> None:
        pass

    async def _process_input(self, ten_env: AsyncTenEnv, queue: asyncio.Queue):
        ten_env.log_info("process_input started")

        while True:
            item = await queue.get()
            if not item:
                break

            (ts, frame_buf) = item
            ten_env.log_debug(f"start process task {ts} {len(frame_buf)}")

            try:
                self.curr_task = asyncio.create_task(
                    self._complete_with_history(ts, frame_buf)
                )
                await self.curr_task
                self.curr_task = None
            except asyncio.CancelledError:
                ten_env.log_warn("task cancelled")
            except Exception as e:
                ten_env.log_warn(f"task failed, err {e}")
            finally:
                queue.task_done()

        ten_env.log_info("process_input exit")

    async def _complete_with_history(self, ts: datetime, buff: bytearray):
        start_time = datetime.now()
        ten_env = self.ten_env
        ten_env.log_debug(
            f"start request, buff len {len(buff)}, queued_time {duration_in_ms(ts, start_time)}ms"
        )

        # prepare messages with prompt and history
        messages = []
        if self.config.prompt:
            messages.append({"role": Role.System, "content": self.config.prompt})
        messages.extend(self.memory.get())
        ten_env.log_debug(f"messages without audio: [{messages}]")
        messages.append(
            self._create_input_audio_message(buff=buff)
        )  # don't print audio message

        # prepare request
        url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
        (headers, payload) = self._create_request(messages)

        # vars to calculate Time to first byte
        user_transcript_ttfb = None
        assistant_transcript_ttfb = None
        assistant_audio_ttfb = None

        # vars for transcript
        user_transcript = ""
        assistant_transcript = ""

        try:
            # send POST request
            async with self.client.stream(
                "POST", url, headers=headers, json=payload
            ) as response:
                trace_id = response.headers.get("Trace-Id", "")
                alb_receive_time = response.headers.get("alb_receive_time", "")
                ten_env.log_info(
                    f"Get response trace-id: {trace_id}, alb_receive_time: {alb_receive_time}, cost_time {duration_in_ms_since(start_time)}ms"
                )

                response.raise_for_status()  # check response

                i = 0
                async for line in response.aiter_lines():
                    # logger.info(f"-> line {line}")
                    # if self._need_interrupt(ts):
                    #     ten_env.log_warn(f"trace-id: {trace_id}, interrupted")
                    #     if self.transcript:
                    #         self.transcript += "[interrupted]"
                    #         self._append_message("assistant", self.transcript)
                    #         self._send_transcript("", "assistant", True)
                    #     break

                    if not line.startswith("data:"):
                        ten_env.log_debug(f"ignore line {len(line)}")
                        continue
                    i += 1

                    resp = json.loads(line.strip("data:"))
                    if resp.get("choices") and resp["choices"][0].get("delta"):
                        delta = resp["choices"][0]["delta"]
                        if delta.get("role") == "assistant":
                            # text content
                            if delta.get("content"):
                                content = delta["content"]
                                assistant_transcript += content
                                if not assistant_transcript_ttfb:
                                    assistant_transcript_ttfb = duration_in_ms_since(
                                        start_time
                                    )
                                    ten_env.log_info(
                                        f"trace-id {trace_id} chunck-{i} get assistant_transcript_ttfb {assistant_transcript_ttfb}ms, assistant transcript [{content}]"
                                    )
                                else:
                                    ten_env.log_info(
                                        f"trace-id {trace_id} chunck-{i} get assistant transcript [{content}]"
                                    )

                                # send out for transcript display
                                self._send_transcript(
                                    ten_env=ten_env,
                                    content=content,
                                    role=Role.Assistant,
                                    end_of_segment=False,
                                )

                            # audio content
                            if (
                                delta.get("audio_content")
                                and delta["audio_content"] != ""
                            ):
                                ten_env.log_info(
                                    f"trace-id {trace_id} chunck-{i} get audio_content"
                                )
                                if not assistant_audio_ttfb:
                                    assistant_audio_ttfb = duration_in_ms_since(
                                        start_time
                                    )
                                    ten_env.log_info(
                                        f"trace-id {trace_id} chunck-{i} get assistant_audio_ttfb {assistant_audio_ttfb}ms"
                                    )

                                # send out
                                base64_str = delta["audio_content"]
                                buff = base64.b64decode(base64_str)
                                await self._dump_audio_if_need(buff, "out")
                                await self._send_audio_frame(
                                    ten_env=ten_env, audio_data=buff
                                )

                            # tool calls
                            if delta.get("tool_calls"):
                                ten_env.log_warn(f"ignore tool call {delta}")
                                # TODO: add tool calls
                                continue

                        if delta.get("role") == "user":
                            if delta.get("content"):
                                content = delta["content"]
                                user_transcript += content
                                if not user_transcript_ttfb:
                                    user_transcript_ttfb = duration_in_ms_since(
                                        start_time
                                    )
                                    ten_env.log_info(
                                        f"trace-id: {trace_id} chunck-{i} get user_transcript_ttfb {user_transcript_ttfb}ms, user transcript [{content}]"
                                    )
                                else:
                                    ten_env.log_info(
                                        f"trace-id {trace_id} chunck-{i} get user transcript [{content}]"
                                    )

                                # send out for transcript display
                                self._send_transcript(
                                    ten_env=ten_env,
                                    content=content,
                                    role=Role.User,
                                    end_of_segment=True,
                                )

        except httpx.TimeoutException:
            ten_env.log_warn("http timeout")
        except httpx.HTTPStatusError as e:
            ten_env.log_warn(f"http status error: {e}")
        except httpx.RequestError as e:
            ten_env.log_warn(f"http request error: {e}")
        finally:
            ten_env.log_info(
                f"http loop done, cost_time {duration_in_ms_since(start_time)}ms"
            )
            if user_transcript:
                self.memory.put({"role": Role.User, "content": user_transcript})
            if assistant_transcript:
                self.memory.put(
                    {"role": Role.Assistant, "content": assistant_transcript}
                )
                self._send_transcript(
                    ten_env=ten_env,
                    content="",
                    role=Role.Assistant,
                    end_of_segment=True,
                )

    def _create_input_audio_message(self, buff: bytearray) -> Dict[str, Any]:
        message = {
            "role": "user",
            "content": [
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": base64.b64encode(buff).decode("utf-8"),
                        "format": "pcm",
                        "sample_rate": self.config.in_sample_rate,
                        "bit_depth": 16,
                        "channel": 1,
                        "encode": "base64",
                    },
                }
            ],
        }
        return message

    def _create_request(
        self, messages: List[Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        config = self.config

        headers = {
            "Authorization": f"Bearer {config.token}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": config.model,
            "messages": messages,
            "tool_choice": "none",
            "stream": True,
            "stream_options": {"speech_output": True},  # 开启语音输出
            "voice_setting": {
                "model": config.voice_model,
                "voice_id": config.voice_id,
            },
            "audio_setting": {
                "sample_rate": config.out_sample_rate,
                "format": "pcm",
                "channel": 1,
                "encode": "base64",
            },
            "tools": [{"type": "web_search"}],
            "max_tokens": config.max_tokens,
            "temperature": 0.8,
            "top_p": 0.95,
        }

        return (headers, payload)

    async def _send_audio_frame(
        self, ten_env: AsyncTenEnv, audio_data: bytearray
    ) -> None:
        try:
            f = AudioFrame.create("pcm_frame")
            f.set_sample_rate(self.config.out_sample_rate)
            f.set_bytes_per_sample(2)
            f.set_number_of_channels(1)
            f.set_data_fmt(AudioFrameDataFmt.INTERLEAVE)
            f.set_samples_per_channel(len(audio_data) // 2)
            f.alloc_buf(len(audio_data))
            buff = f.lock_buf()
            buff[:] = audio_data
            f.unlock_buf(buff)
            await ten_env.send_audio_frame(f)
        except Exception as e:
            ten_env.log_error(f"send audio frame failed, err {e}")

    def _send_transcript(
        self,
        ten_env: AsyncTenEnv,
        content: str,
        role: str,
        end_of_segment: bool,
    ) -> None:
        stream_id = self.remote_stream_id if role == "user" else 0

        try:
            d = Data.create("text_data")
            d.set_property_string("text", content)
            d.set_property_bool("is_final", True)
            d.set_property_bool("end_of_segment", end_of_segment)
            d.set_property_string("role", role)
            d.set_property_int("stream_id", stream_id)
            ten_env.log_info(
                f"send transcript text [{content}] {stream_id} end_of_segment {end_of_segment} role {role}"
            )
            asyncio.create_task(self.ten_env.send_data(d))
        except Exception as e:
            ten_env.log_warn(
                f"send transcript text [{content}] {stream_id} end_of_segment {end_of_segment} role {role} failed, err {e}"
            )

    async def _flush(self, ten_env: AsyncTenEnv) -> None:
        # clear queue
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except Exception as e:
                ten_env.log_warn(f"flush queue error {e}")

        # cancel current task
        if self.curr_task:
            self.curr_task.cancel()
            await asyncio.gather(self.curr_task, return_exceptions=True)
            self.curr_task = None

    async def _dump_audio_if_need(self, buf: bytearray, suffix: str) -> None:
        if not self.config.dump:
            return

        async with aiofiles.open(f"minimax_v2v_{suffix}.pcm", "ab") as f:
            await f.write(buf)

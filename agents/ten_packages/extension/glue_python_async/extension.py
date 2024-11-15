#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import traceback
import aiohttp

from datetime import datetime
from typing import List

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

PROPERTY_API_URL = "api_url"
PROPERTY_USER_ID = "user_id"
PROPERTY_PROMPT = "prompt"
PROPERTY_TOKEN = "token"

DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_IN_TEXT_DATA_PROPERTY_TEXT = "text"

DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT = "end_of_segment"

def is_punctuation(char):
    if char in [",", "，", ".", "。", "?", "？", "!", "！"]:
        return True
    return False

def parse_sentences(sentence_fragment, content):
    sentences = []
    current_sentence = sentence_fragment
    for char in content:
        current_sentence += char
        if is_punctuation(char):
            stripped_sentence = current_sentence
            if any(c.isalnum() for c in stripped_sentence):
                sentences.append(stripped_sentence)
            current_sentence = ""

    remain = current_sentence
    return sentences, remain

class AsyncGlueExtension(AsyncExtension):
    api_url: str = "http://localhost:8000/chat/completions"
    user_id: str = "TenAgent"
    prompt: str = ""
    token: str = ""
    outdate_ts = datetime.now()
    sentence_fragment: str = ""
    ten_env: AsyncTenEnv = None
    loop: asyncio.AbstractEventLoop = None
    stopped: bool = False
    queue = asyncio.Queue()
    history: List[dict] = []
    max_history: int = 10
    session: aiohttp.ClientSession = None

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_init")
        ten_env.on_init_done()

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_start")

        self.loop = asyncio.get_event_loop()

        try:
            self.api_url = ten_env.get_property_string(PROPERTY_API_URL)
        except Exception as err:
            ten_env.log_error(f"GetProperty optional {PROPERTY_API_URL} failed, err: {err}")
            return

        try:
            self.user_id = ten_env.get_property_string(PROPERTY_USER_ID)
        except Exception as err:
            ten_env.log_error(f"GetProperty optional {PROPERTY_USER_ID} failed, err: {err}")

        try:
            self.prompt = ten_env.get_property_string(PROPERTY_PROMPT)
        except Exception as err:
            ten_env.log_error(f"GetProperty optional {PROPERTY_PROMPT} failed, err: {err}")

        try:
            self.token = ten_env.get_property_string(PROPERTY_TOKEN)
        except Exception as err:
            ten_env.log_error(f"GetProperty optional {PROPERTY_TOKEN} failed, err: {err}")

        try:
            self.max_history = ten_env.get_property_int("max_memory_length")
        except Exception as err:
            ten_env.log_error(f"GetProperty optional max_memory_length failed, err: {err}")

        self.ten_env = ten_env
        self.loop.create_task(self._consume())

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_stop")

        self.stopped = True
        await self.queue.put(None)
        await self._flush()

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_deinit")

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug("on_cmd name {}".format(cmd_name))

        if cmd_name == "flush":
            try:
                await self._flush()
                await ten_env.send_cmd(Cmd.create("flush"))
                ten_env.log_info("on flush")
            except Exception as e:
                ten_env.log_error(f"{traceback.format_exc()} \n Failed to handle {e}")

        cmd_result = CmdResult.create(StatusCode.OK)
        ten_env.return_result(cmd_result, cmd)

    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        data_name = data.get_name()
        ten_env.log_debug("on_data name {}".format(data_name))

        is_final = False
        input_text = ""
        try:
            is_final = data.get_property_bool(DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL)
        except Exception as err:
            ten_env.log_info(f"GetProperty optional {DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL} failed, err: {err}")

        try:
            input_text = data.get_property_string(DATA_IN_TEXT_DATA_PROPERTY_TEXT)
        except Exception as err:
            ten_env.log_info(f"GetProperty optional {DATA_IN_TEXT_DATA_PROPERTY_TEXT} failed, err: {err}")

        if not is_final:
            ten_env.log_info("ignore non-final input")
            return
        if not input_text:
            ten_env.log_info("ignore empty text")
            return

        ten_env.log_info(f"OnData input text: [{input_text}]")

        ts = datetime.now()
        await self.queue.put((input_text, ts))

    async def on_audio_frame(self, ten_env: AsyncTenEnv, audio_frame: AudioFrame) -> None:
        pass

    async def on_video_frame(self, ten_env: AsyncTenEnv, video_frame: VideoFrame) -> None:
        pass

    async def _flush(self):
        # self.ten_env.log_info("flush")
        self.outdate_ts = datetime.now()
        if self.session:
            await self.session.close()
            self.session = None

    def _need_interrrupt(self, ts: datetime) -> bool:
        return self.outdate_ts > ts

    async def _send_text(self, text: str) -> None:
        data = Data.create("text_data")
        data.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, text)
        data.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT, True)
        self.ten_env.send_data(data)

    async def _consume(self) -> None:
        self.ten_env.log_info("start async loop")
        while not self.stopped:
            try:
                value = await self.queue.get()
                if value is None:
                    self.ten_env.log_info("async loop exit")
                    break
                input, ts = value
                if self._need_interrrupt(ts):
                    continue

                await self._chat(input, ts)
            except Exception as e:
                self.ten_env.log_error(f"Failed to handle {e}")

    async def _add_to_history(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        if len(self.history) > self.max_history:
            self.history = self.history[1:]

    async def _get_messages(self) -> List[dict]:
        messages = []
        if self.prompt:
            messages.append({"role": "system", "content": self.prompt})
        messages.extend(self.history)
        return messages

    async def _chat(self, input: str, ts: datetime) -> None:
        self.session = aiohttp.ClientSession()
        try:
            messages = await self._get_messages()
            messages.append({"role": "user", "content": input})
            await self._add_to_history("user", input)
            payload = {
                "messages": [{"role": msg["role"], "content": {"type": "text", "text": msg["content"]}} for msg in messages],
                "model": "gpt-3.5-turbo",
                "temperature": 1.0,
                "stream": True
            }
            self.ten_env.log_info(f"payload before sending: {payload}")
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            total_output = ""
            async with self.session.post(self.api_url, json=payload, headers=headers) as response:
                async for line in response.content:
                    if self._need_interrrupt(ts):
                        self.ten_env.log_info("interrupted")
                        total_output += "[interrupted]"
                        break

                    if line:
                        l = line.decode('utf-8').strip()
                        if l.startswith("data:"):
                            content = l[5:].strip()
                            if content == "[DONE]":
                                break
                            self.ten_env.log_info(f"content: {content}")
                            sentences, self.sentence_fragment = parse_sentences(self.sentence_fragment, content)
                            for s in sentences:
                                await self._send_text(s)
                                total_output += s
            self.ten_env.log_info(f"total_output: {total_output}")
            await self._add_to_history("assistant", total_output)
        except Exception as e:
            traceback.print_exc()
            self.ten_env.log_error(f"Failed to handle {e}")
        finally:
            await self.session.close()
            self.session = None

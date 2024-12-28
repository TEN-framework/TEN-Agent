#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import json
import time
import traceback
from dataclasses import dataclass
from typing import AsyncGenerator

import aiohttp
from ten import AsyncTenEnv, AudioFrame, Cmd, CmdResult, Data, StatusCode, VideoFrame
from ten_ai_base.config import BaseConfig
from ten_ai_base import (
    AsyncLLMBaseExtension,
)
from ten_ai_base.types import LLMChatCompletionUserMessageParam, LLMDataCompletionArgs

CMD_IN_FLUSH = "flush"
CMD_IN_ON_USER_JOINED = "on_user_joined"
CMD_IN_ON_USER_LEFT = "on_user_left"
CMD_OUT_FLUSH = "flush"
CMD_OUT_TOOL_CALL = "tool_call"

DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_IN_TEXT_DATA_PROPERTY_TEXT = "text"

DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT = "end_of_segment"

CMD_PROPERTY_RESULT = "tool_result"


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


@dataclass
class DifyConfig(BaseConfig):
    base_url: str = "https://api.dify.ai/v1"
    api_key: str = ""
    user_id: str = "TenAgent"
    greeting: str = ""
    failure_info: str = ""
    max_history: int = 32


class DifyExtension(AsyncLLMBaseExtension):
    config: DifyConfig = None
    ten_env: AsyncTenEnv = None
    loop: asyncio.AbstractEventLoop = None
    stopped: bool = False
    users_count = 0
    conversational_id = ""

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        ten_env.log_debug("on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        await super().on_start(ten_env)
        ten_env.log_debug("on_start")
        self.loop = asyncio.get_event_loop()

        self.config = await DifyConfig.create_async(ten_env=ten_env)
        ten_env.log_info(f"config: {self.config}")

        if not self.config.api_key:
            ten_env.log_error("Missing required configuration")
            return

        self.ten_env = ten_env

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)
        ten_env.log_debug("on_stop")

        self.stopped = True

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_debug("on_deinit")

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug("on_cmd name {}".format(cmd_name))

        status = StatusCode.OK
        detail = "success"

        if cmd_name == CMD_IN_FLUSH:
            await self.flush_input_items(ten_env)
            await ten_env.send_cmd(Cmd.create(CMD_OUT_FLUSH))
            ten_env.log_info("on flush")
        elif cmd_name == CMD_IN_ON_USER_JOINED:
            self.users_count += 1
            # Send greeting when first user joined
            if self.config.greeting and self.users_count == 1:
                self.send_text_output(ten_env, self.config.greeting, True)
        elif cmd_name == CMD_IN_ON_USER_LEFT:
            self.users_count -= 1
        else:
            await super().on_cmd(ten_env, cmd)
            return

        cmd_result = CmdResult.create(status)
        cmd_result.set_property_string("detail", detail)
        await ten_env.return_result(cmd_result, cmd)

    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        data_name = data.get_name()
        ten_env.log_info("on_data name {}".format(data_name))

        is_final = False
        input_text = ""
        try:
            is_final = data.get_property_bool(DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL)
        except Exception as err:
            ten_env.log_info(
                f"GetProperty optional {DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL} failed, err: {err}"
            )

        try:
            input_text = data.get_property_string(DATA_IN_TEXT_DATA_PROPERTY_TEXT)
        except Exception as err:
            ten_env.log_info(
                f"GetProperty optional {DATA_IN_TEXT_DATA_PROPERTY_TEXT} failed, err: {err}"
            )

        if not is_final:
            ten_env.log_info("ignore non-final input")
            return
        if not input_text:
            ten_env.log_info("ignore empty text")
            return

        ten_env.log_info(f"OnData input text: [{input_text}]")

        # Start an asynchronous task for handling chat completion
        message = LLMChatCompletionUserMessageParam(role="user", content=input_text)
        await self.queue_input_item(False, messages=[message])

    async def on_audio_frame(
        self, ten_env: AsyncTenEnv, audio_frame: AudioFrame
    ) -> None:
        pass

    async def on_video_frame(
        self, ten_env: AsyncTenEnv, video_frame: VideoFrame
    ) -> None:
        pass

    async def on_call_chat_completion(self, async_ten_env, **kargs):
        raise NotImplementedError

    async def on_tools_update(self, async_ten_env, tool):
        raise NotImplementedError

    async def on_data_chat_completion(
        self, ten_env: AsyncTenEnv, **kargs: LLMDataCompletionArgs
    ) -> None:
        input_messages: LLMChatCompletionUserMessageParam = kargs.get("messages", [])
        if not input_messages:
            ten_env.log_warn("No message in data")

        total_output = ""
        sentence_fragment = ""
        calls = {}

        sentences = []
        self.ten_env.log_info(f"messages: {input_messages}")
        response = self._stream_chat(query=input_messages[0]["content"])
        async for message in response:
            self.ten_env.log_info(f"content: {message}")
            message_type = message.get("event")
            if message_type == "message":
                if not self.conversational_id and message.get("conversation_id"):
                    self.conversational_id = message["conversation_id"]
                    ten_env.log_info(f"conversation_id: {self.conversational_id}")

                total_output += message.get("answer", "")
                sentences, sentence_fragment = parse_sentences(
                    sentence_fragment, message.get("answer", "")
                )
                for s in sentences:
                    await self._send_text(s, False)
            elif message_type == "message_end":
                metadata = message.get("metadata", {})
                ten_env.log_info(f"metadata: {metadata}")

            # data: {"event": "message", "task_id": "900bbd43-dc0b-4383-a372-aa6e6c414227", "id": "663c5084-a254-4040-8ad3-51f2a3c1a77c", "answer": "Hi", "created_at": 1705398420}\n\n

            # try:
            #     if message.event == ChatEventType.CONVERSATION_MESSAGE_DELTA:
            #         total_output += message.message.content
            #         sentences, sentence_fragment = parse_sentences(
            #                 sentence_fragment, message.message.content)
            #         for s in sentences:
            #             await self._send_text(s, False)
            #     elif message.event == ChatEventType.CONVERSATION_MESSAGE_COMPLETED:
            #         if sentence_fragment:
            #             await self._send_text(sentence_fragment, True)
            #         else:
            #             await self._send_text("", True)
            #     elif message.event == ChatEventType.CONVERSATION_CHAT_FAILED:
            #         last_error = message.chat.last_error
            #         if last_error and last_error.code == 4011:
            #             await self._send_text("The Coze token has been depleted. Please check your token usage.", True)
            #         else:
            #             await self._send_text(last_error.msg, True)
            # except Exception as e:
            #     self.ten_env.log_error(f"Failed to parse response: {message} {e}")
            #     traceback.print_exc()
        await self._send_text(sentence_fragment, True)
        self.ten_env.log_info(f"total_output: {total_output} {calls}")

    async def _stream_chat(self, query: str) -> AsyncGenerator[dict, None]:
        async with aiohttp.ClientSession() as session:
            try:
                payload = {
                    "inputs": {},
                    "query": query,
                    "response_mode": "streaming",
                }
                if self.conversational_id:
                    payload["conversation_id"] = self.conversational_id
                if self.config.user_id:
                    payload["user"] = self.config.user_id
                self.ten_env.log_info(f"payload before sending: {json.dumps(payload)}")
                headers = {
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                }
                url = f"{self.config.base_url}/chat-messages"
                start_time = time.time()
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        r = await response.json()
                        self.ten_env.log_error(
                            f"Received unexpected status {r} from the server."
                        )
                        if self.config.failure_info:
                            await self._send_text(self.config.failure_info, True)
                        return
                    end_time = time.time()
                    self.ten_env.log_info(f"connect time {end_time - start_time} s")

                    async for line in response.content:
                        if line:
                            l = line.decode("utf-8").strip()
                            if l.startswith("data:"):
                                content = l[5:].strip()
                                if content == "[DONE]":
                                    break
                                self.ten_env.log_debug(f"content: {content}")
                                yield json.loads(content)
            except Exception as e:
                traceback.print_exc()
                self.ten_env.log_error(f"Failed to handle {e}")
            finally:
                await session.close()
                session = None

    async def _send_text(self, text: str, end_of_segment: bool) -> None:
        data = Data.create("text_data")
        data.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, text)
        data.set_property_bool(
            DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT, end_of_segment
        )
        asyncio.create_task(self.ten_env.send_data(data))

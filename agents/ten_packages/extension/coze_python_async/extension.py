#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import traceback
import aiohttp
import json
import copy

from typing import List, Any, AsyncGenerator
from dataclasses import dataclass

from cozepy import ChatEventType, Message, TokenAuth, AsyncCoze, ChatEvent, Chat

from ten import (
    AudioFrame,
    VideoFrame,
    AsyncTenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)

from ten_ai_base import BaseConfig, ChatMemory
from ten_ai_base.llm import (
    AsyncLLMBaseExtension,
    LLMCallCompletionArgs,
    LLMDataCompletionArgs,
    LLMToolMetadata,
)
from ten_ai_base.types import LLMChatCompletionUserMessageParam

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
class CozeConfig(BaseConfig):
    base_url: str = "https://api.acoze.com"
    bot_id: str = ""
    token: str = ""
    user_id: str = "TenAgent"
    greeting: str = ""
    max_history: int = 32


class AsyncCozeExtension(AsyncLLMBaseExtension):
    config: CozeConfig = None
    sentence_fragment: str = ""
    ten_env: AsyncTenEnv = None
    loop: asyncio.AbstractEventLoop = None
    stopped: bool = False
    users_count = 0
    memory: ChatMemory = None

    acoze: AsyncCoze = None
    # conversation: str = ""

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        ten_env.log_debug("on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        await super().on_start(ten_env)
        ten_env.log_debug("on_start")

        self.loop = asyncio.get_event_loop()

        self.config = CozeConfig.create(ten_env=ten_env)
        ten_env.log_info(f"config: {self.config}")

        if not self.config.bot_id or not self.config.token:
            ten_env.log_error("Missing required configuration")
            return

        self.memory = ChatMemory(self.config.max_history)
        try:
            self.acoze = AsyncCoze(
                auth=TokenAuth(token=self.config.token), base_url=self.config.base_url
            )

            # self.conversation = await self.acoze.conversations.create(messages = [
            #        Message.build_user_question_text(self.config.prompt)
            #    ] if self.config.prompt else [])

        except Exception as e:
            ten_env.log_error(f"Failed to create conversation {e}")

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

    async def on_call_chat_completion(
        self, ten_env: AsyncTenEnv, **kargs: LLMCallCompletionArgs
    ) -> any:
        raise RuntimeError("Not implemented")

    async def on_data_chat_completion(
        self, ten_env: AsyncTenEnv, **kargs: LLMDataCompletionArgs
    ) -> None:
        if not self.acoze:
            await self._send_text(
                "Coze is not connected. Please check your configuration.", True
            )
            return

        input_messages: LLMChatCompletionUserMessageParam = kargs.get("messages", [])
        messages = copy.copy(self.memory.get())
        if not input_messages:
            ten_env.log_warn("No message in data")
        else:
            messages.extend(input_messages)
            for i in input_messages:
                self.memory.put(i)

        total_output = ""
        sentence_fragment = ""
        calls = {}

        sentences = []
        self.ten_env.log_info(f"messages: {messages}")
        response = self._stream_chat(messages=messages)
        async for message in response:
            self.ten_env.log_info(f"content: {message}")
            try:
                if message.event == ChatEventType.CONVERSATION_MESSAGE_DELTA:
                    total_output += message.message.content
                    sentences, sentence_fragment = parse_sentences(
                        sentence_fragment, message.message.content
                    )
                    for s in sentences:
                        await self._send_text(s, False)
                elif message.event == ChatEventType.CONVERSATION_MESSAGE_COMPLETED:
                    if sentence_fragment:
                        await self._send_text(sentence_fragment, True)
                    else:
                        await self._send_text("", True)
                elif message.event == ChatEventType.CONVERSATION_CHAT_FAILED:
                    last_error = message.chat.last_error
                    if last_error and last_error.code == 4011:
                        await self._send_text(
                            "The Coze token has been depleted. Please check your token usage.",
                            True,
                        )
                    else:
                        await self._send_text(last_error.msg, True)
            except Exception as e:
                self.ten_env.log_error(f"Failed to parse response: {message} {e}")
                traceback.print_exc()

        self.memory.put({"role": "assistant", "content": total_output})
        self.ten_env.log_info(f"total_output: {total_output} {calls}")

    async def on_tools_update(
        self, ten_env: AsyncTenEnv, tool: LLMToolMetadata
    ) -> None:
        # Implement the logic for tool updates
        return await super().on_tools_update(ten_env, tool)

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

    async def _send_text(self, text: str, end_of_segment: bool) -> None:
        data = Data.create("text_data")
        data.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, text)
        data.set_property_bool(
            DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT, end_of_segment
        )
        asyncio.create_task(self.ten_env.send_data(data))

    async def _stream_chat(
        self, messages: List[Any]
    ) -> AsyncGenerator[ChatEvent, None]:
        additionals = []
        for m in messages:
            if m["role"] == "user":
                additionals.append(
                    Message.build_user_question_text(m["content"]).model_dump()
                )
            elif m["role"] == "assistant":
                additionals.append(
                    Message.build_assistant_answer(m["content"]).model_dump()
                )

        def chat_stream_handler(event: str, event_data: Any) -> ChatEvent:
            if event == ChatEventType.DONE:
                raise StopAsyncIteration
            elif event == ChatEventType.ERROR:
                raise RuntimeError(f"error event: {event_data}")
            elif event in [
                ChatEventType.CONVERSATION_MESSAGE_DELTA,
                ChatEventType.CONVERSATION_MESSAGE_COMPLETED,
            ]:
                return ChatEvent(
                    event=event, message=Message.model_validate_json(event_data)
                )
            elif event in [
                ChatEventType.CONVERSATION_CHAT_CREATED,
                ChatEventType.CONVERSATION_CHAT_IN_PROGRESS,
                ChatEventType.CONVERSATION_CHAT_COMPLETED,
                ChatEventType.CONVERSATION_CHAT_FAILED,
                ChatEventType.CONVERSATION_CHAT_REQUIRES_ACTION,
            ]:
                return ChatEvent(event=event, chat=Chat.model_validate_json(event_data))
            else:
                raise ValueError(f"invalid chat.event: {event}, {event_data}")

        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self.config.base_url}/v3/chat"
                headers = {
                    "Authorization": f"Bearer {self.config.token}",
                }
                params = {
                    "bot_id": self.config.bot_id,
                    "user_id": self.config.user_id,
                    "additional_messages": additionals,
                    "stream": True,
                    "auto_save_history": True,
                    # "conversation_id": self.conversation.id
                }
                event = ""
                async with session.post(url, json=params, headers=headers) as response:
                    async for line in response.content:
                        if line:
                            try:
                                self.ten_env.log_info(f"line: {line}")
                                decoded_line = line.decode("utf-8").strip()
                                if decoded_line:
                                    if decoded_line.startswith("data:"):
                                        data = decoded_line[5:].strip()
                                        yield chat_stream_handler(
                                            event=event, event_data=data.strip()
                                        )
                                    elif decoded_line.startswith("event:"):
                                        event = decoded_line[6:]
                                        self.ten_env.log_info(f"event: {event}")
                                        if event == "done":
                                            break
                                    else:
                                        result = json.loads(decoded_line)
                                        code = result.get("code", 0)
                                        if code == 4000:
                                            await self._send_text(
                                                "Coze bot is not published.", True
                                            )
                                        else:
                                            self.ten_env.log_error(
                                                f"Failed to stream chat: {result['code']}"
                                            )
                                            await self._send_text(
                                                "Coze bot is not connected. Please check your configuration.",
                                                True,
                                            )
                            except Exception as e:
                                self.ten_env.log_error(f"Failed to stream chat: {e}")
            except Exception as e:
                traceback.print_exc()
                self.ten_env.log_error(f"Failed to stream chat: {e}")
            finally:
                await session.close()

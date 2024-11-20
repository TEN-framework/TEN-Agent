#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import traceback
import aiohttp

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

from ten_ai_base import BaseConfig
from ten_ai_base.llm import AsyncLLMBaseExtension, LLMCallCompletionArgs, LLMDataCompletionArgs, LLMToolMetadata
from ten_ai_base.types import LLMChatCompletionUserMessageParam, LLMToolResult

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
    prompt: str = ""
    greeting: str = ""

class AsyncCozeExtension(AsyncLLMBaseExtension):
    config : CozeConfig = None
    sentence_fragment: str = ""
    ten_env: AsyncTenEnv = None
    loop: asyncio.AbstractEventLoop = None
    stopped: bool = False
    users_count = 0

    acoze: AsyncCoze = None
    conversation: str = ""

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
    
        self.acoze = AsyncCoze(auth=TokenAuth(token=self.config.token), base_url=self.config.base_url)
        self.conversation = await self.acoze.conversations.create(messages = [
                Message.build_user_question_text(self.config.prompt)
            ] if self.config.prompt else [])

        self.ten_env = ten_env

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)
        ten_env.log_debug("on_stop")

        self.stopped = True
        await self.queue.put(None)

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_debug("on_deinit")

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug("on_cmd name {}".format(cmd_name))

        status = StatusCode.OK
        detail = "success"

        if cmd_name == CMD_IN_FLUSH:
            pass
            #await self.flush_input_items(ten_env)
            #await ten_env.send_cmd(Cmd.create(CMD_OUT_FLUSH))
            #ten_env.log_info("on flush")
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
        ten_env.return_result(cmd_result, cmd)

    async def on_call_chat_completion(self, ten_env: AsyncTenEnv, **kargs: LLMCallCompletionArgs) -> any:
        raise Exception("Not implemented")

    async def on_data_chat_completion(self, ten_env: AsyncTenEnv, **kargs: LLMDataCompletionArgs) -> None:
        if not self.conversation:
            self._send_text("Coze is not connected. Please check your configuration.")
            return

        input: LLMChatCompletionUserMessageParam = kargs.get("messages", [])

        total_output = ""
        sentence_fragment = ""
        calls = {}

        sentences = []
        response = self._stream_chat(messages=input)
        async for message in response:
            self.ten_env.log_info(f"content: {message}")
            try:
                if message.event == ChatEventType.CONVERSATION_MESSAGE_DELTA:
                    total_output += message.message.content
                    sentences, sentence_fragment = parse_sentences(
                            sentence_fragment, message.message.content)
                    for s in sentences:
                        await self._send_text(s)
            except Exception as e:
                self.ten_env.log_error(f"Failed to parse response: {message} {e}")
                traceback.print_exc()
        
        self.ten_env.log_info(f"total_output: {total_output} {calls}")

    async def on_tools_update(self, ten_env: AsyncTenEnv, tool: LLMToolMetadata) -> None:
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

        # Start an asynchronous task for handling chat completion
        message = LLMChatCompletionUserMessageParam(
            role="user", content=input_text)
        await self.queue_input_item(False, messages=[message])

    async def on_audio_frame(self, ten_env: AsyncTenEnv, audio_frame: AudioFrame) -> None:
        pass

    async def on_video_frame(self, ten_env: AsyncTenEnv, video_frame: VideoFrame) -> None:
        pass

    async def _send_text(self, text: str) -> None:
        data = Data.create("text_data")
        data.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, text)
        data.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT, True)
        self.ten_env.send_data(data)

    async def _stream_chat(self, messages: List[Any]) -> AsyncGenerator[ChatEvent, None]:
        additionals = [Message.build_user_question_text(m["content"]).model_dump() for m in messages]

        def chat_stream_handler(event:str, event_data:Any) -> ChatEvent:
            if event == ChatEventType.DONE:
                raise StopAsyncIteration
            elif event == ChatEventType.ERROR:
                raise Exception(f"error event: {event_data}")  # TODO: error struct format
            elif event in [
                ChatEventType.CONVERSATION_MESSAGE_DELTA,
                ChatEventType.CONVERSATION_MESSAGE_COMPLETED,
            ]:
                return ChatEvent(event=event, message=Message.model_validate_json(event_data))
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
                    "conversation_id": self.conversation.id
                }
                async with session.post(url, json=params, headers=headers) as response:
                    async for line in response.content:
                        if line:
                            self.ten_env.log_info(f"line: {line}")
                            decoded_line = line.decode('utf-8').strip()
                            if decoded_line:
                                event_data = decoded_line.split(":", 1)
                                if len(event_data) == 2:
                                    if event_data[0] == "event":
                                        event = event_data[1]
                                        continue
                                    elif event_data[0] == "data":
                                        data = event_data[1]
                                        yield chat_stream_handler(event=event.strip(), event_data=data.strip())
            except Exception as e:
                traceback.print_exc()
                self.ten_env.log_error(f"Failed to stream chat: {e}")
            finally:
                await session.close()

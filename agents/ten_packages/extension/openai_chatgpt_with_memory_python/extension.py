#
#
# Agora Real Time Engagement
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import asyncio
import json
import time
import traceback
from typing import Iterable
import uuid

from ten.async_ten_env import AsyncTenEnv  
from ten_ai_base.const import CMD_PROPERTY_RESULT, CMD_TOOL_CALL, CONTENT_DATA_OUT_NAME, DATA_OUT_PROPERTY_END_OF_SEGMENT, DATA_OUT_PROPERTY_TEXT  
from ten_ai_base.helper import (  
    AsyncEventEmitter,
    get_property_bool,
    get_property_string,
)
from ten_ai_base.types import (  
    LLMCallCompletionArgs,
    LLMChatCompletionContentPartParam,
    LLMChatCompletionUserMessageParam,
    LLMChatCompletionMessageParam,
    LLMDataCompletionArgs,
    LLMToolMetadata,
    LLMToolResult,
)
from ten_ai_base.llm import AsyncLLMBaseExtension  

from .helper import parse_sentences  
from .openai import OpenAIChatGPT, OpenAIChatGPTWithMemoryConfig  
from .memory import AsyncMemory,MemoryManager  
from mem0.configs.base import MemoryConfig,VectorStoreConfig 
from ten import (  
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)

CMD_IN_FLUSH = "flush"
CMD_IN_ON_USER_JOINED = "on_user_joined"
CMD_IN_ON_USER_LEFT = "on_user_left"
CMD_OUT_FLUSH = "flush"
DATA_IN_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT = "end_of_segment"


class OpenAIChatGPTWithMemoryExtension(AsyncLLMBaseExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.memory = []  # 添加memory列表用于存储历史消息
        self.memory_cache = []  # 添加memory_cache用于临时存储当前对话消息
        self.config = None
        self.client = None
        self.memory_manager = None
        self.sentence_fragment = ""
        self.tool_task_future: asyncio.Future | None = None
        self.users_count = 0
        self.last_reasoning_ts = 0
        self.last_user_message = ""
        self.last_assistant_message = ""

    async def on_init(self, async_ten_env: AsyncTenEnv) -> None:
        async_ten_env.log_info("on_init")
        await super().on_init(async_ten_env)

    async def on_start(self, async_ten_env: AsyncTenEnv) -> None:
        async_ten_env.log_info("on_start")
        await super().on_start(async_ten_env)

        self.config = await OpenAIChatGPTWithMemoryConfig.create_async(ten_env=async_ten_env)
        async_ten_env.log_info(f"OpenAIChatGPTWithMemoryConfig:{self.config}")

        # Mandatory properties
        if not self.config.api_key:
            async_ten_env.log_info("API key is missing, exiting on_start")
            return

        # Create instance
        try:
            self.client = OpenAIChatGPT(async_ten_env, self.config)
            async_ten_env.log_info(
                f"initialized with config: {self.config}"
            )
            user_id = self.config.user_id
            # 初始化记忆管理器 - 使用AsyncMemoryWrapper替代MemoryManager
            mem_config = MemoryConfig(
                vector_store=VectorStoreConfig(
                    provider="qdrant",
                    config={
                        "host": self.config.qdrant_host,  # 远程 Qdrant 服务器地址
                        "port": self.config.qdrant_port,             # 远程 Qdrant 服务器端口
                        "collection_name": f"mem0_{user_id}"  # 集合名称
                    }
                )
            )
            memory = AsyncMemory(
                async_ten_env,
                config=mem_config,
                max_workers=5,
                loop=asyncio.get_event_loop()
            )
            self.memory_manager = MemoryManager(async_ten_env,memory)
            await self.memory_manager.initialize(user_id=user_id)
            async_ten_env.log_info("Memory manager initialized with AsyncMemory")
            
        except Exception as err:
            async_ten_env.log_info(f"Failed to initialize: {err}")
            async_ten_env.log_info(traceback.format_exc())

    async def on_stop(self, async_ten_env: AsyncTenEnv) -> None:
        async_ten_env.log_info("on_stop")
        # 关闭记忆管理器的资源
        if self.memory_manager:
            self.memory_manager.close()
            async_ten_env.log_info("Memory manager resources released")
        await super().on_stop(async_ten_env)

    async def on_deinit(self, async_ten_env: AsyncTenEnv) -> None:
        async_ten_env.log_info("on_deinit")
        await super().on_deinit(async_ten_env)

    async def on_cmd(self, async_ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        async_ten_env.log_info(f"on_cmd name: {cmd_name}")

        if cmd_name == CMD_IN_FLUSH:
            await self.flush_input_items(async_ten_env)
            await async_ten_env.send_cmd(Cmd.create(CMD_OUT_FLUSH))
            async_ten_env.log_info("on_cmd sent flush")
            status_code, detail = StatusCode.OK, "success"
            cmd_result = CmdResult.create(status_code)
            cmd_result.set_property_string("detail", detail)
            await async_ten_env.return_result(cmd_result, cmd)
        elif cmd_name == CMD_IN_ON_USER_JOINED:
            self.users_count += 1
            # Send greeting when first user joined
            if self.config.greeting and self.users_count == 1:
                self.send_text_output(async_ten_env, self.config.greeting, True)

            status_code, detail = StatusCode.OK, "success"
            cmd_result = CmdResult.create(status_code)
            cmd_result.set_property_string("detail", detail)
            await async_ten_env.return_result(cmd_result, cmd)
        elif cmd_name == CMD_IN_ON_USER_LEFT:
            self.users_count -= 1
            status_code, detail = StatusCode.OK, "success"
            cmd_result = CmdResult.create(status_code)
            cmd_result.set_property_string("detail", detail)
            await async_ten_env.return_result(cmd_result, cmd)
        else:
            await super().on_cmd(async_ten_env, cmd)

    async def on_data(self, async_ten_env: AsyncTenEnv, data: Data) -> None:
        data_name = data.get_name()
        async_ten_env.log_debug("on_data name {}".format(data_name))

        # Get the necessary properties
        is_final = get_property_bool(data, "is_final")
        input_text = get_property_string(data, "text")

        if not is_final:
            async_ten_env.log_debug("ignore non-final input")
            return
        if not input_text:
            async_ten_env.log_warn("ignore empty text")
            return

        async_ten_env.log_info(f"OnData input text: [{input_text}]")

        # Start an asynchronous task for handling chat completion
        message = LLMChatCompletionUserMessageParam(role="user", content=input_text)
        await self.queue_input_item(False, messages=[message])

    async def on_tools_update(
        self, async_ten_env: AsyncTenEnv, tool: LLMToolMetadata
    ) -> None:
        return await super().on_tools_update(async_ten_env, tool)

    async def on_call_chat_completion(
        self, async_ten_env: AsyncTenEnv, **kargs: LLMCallCompletionArgs
    ) -> any:
        kmessages: LLMChatCompletionUserMessageParam = kargs.get("messages", [])

        async_ten_env.log_info(f"on_call_chat_completion: {kmessages}")
        response = await self.client.get_chat_completions(kmessages, None)
        return response.to_json()

    async def on_data_chat_completion(
        self, async_ten_env: AsyncTenEnv, **kargs: LLMDataCompletionArgs
    ) -> None:
        """Run the chatflow asynchronously."""
        kmessages: Iterable[LLMChatCompletionUserMessageParam] = kargs.get(
            "messages", []
        )

        if len(kmessages) == 0:
            async_ten_env.log_error("No message in data")
            return

        messages = []
        for message in kmessages:
            messages = messages + [self.message_to_dict(message)]
            
        self.memory_cache = []  # 初始化memory_cache
        memory = self.memory  # 使用当前memory作为历史消息

        try:
            # 查找相关记忆
            relevant_memories = []
            if self.memory_manager:
                user_message = messages[-1].get("content", "") if messages else ""
                self.last_user_message = user_message
                if isinstance(user_message, str) and user_message:
                    relevant_memories = await self.memory_manager.search_memories(user_message, limit=self.config.max_memory_length)

            async_ten_env.log_info(f"relevant_memories: {relevant_memories}")
            # 如果找到相关记忆，添加到系统提示中
            memory_context = ""
            if relevant_memories:
                memory_context = await self.memory_manager.format_context(relevant_memories)
            
            # 将记忆上下文添加到第一条消息中（如果是系统消息）
            system_prompt = self.config.prompt
            if memory_context:
                # 修改系统提示，添加记忆上下文
                system_prompt = self.config.prompt + "\nAnswer the question based on query and memories.\nUser Memories:\n" + memory_context
            # 更新模型的system prompt
            async_ten_env.log_info(f"Memory context: {memory_context}")
            self.client.config.prompt = system_prompt
            
            async_ten_env.log_info(f"for input text: [{messages}] memory: {memory}")
            tools = None
            no_tool = kargs.get("no_tool", False)

            # 处理消息并添加到memory_cache
            for message in messages:
                if (
                    not isinstance(message.get("content"), str)
                    and message.get("role") == "user"
                ):
                    non_artifact_content = [
                        item
                        for item in message.get("content", [])
                        if item.get("type") == "text"
                    ]
                    non_artifact_message = {
                        "role": message.get("role"),
                        "content": non_artifact_content,
                    }
                    self.memory_cache = self.memory_cache + [
                        non_artifact_message,
                    ]
                    self.memory_cache = self.memory_cache + [
                        non_artifact_message,
                    ]
                else:
                    self.memory_cache = self.memory_cache + [
                        message,
                    ]
            
            # 添加空的助手消息到memory_cache
            self.memory_cache = self.memory_cache + [{"role": "assistant", "content": ""}]
            
            async_ten_env.log_info(f"memory_cache: {self.memory_cache}")
            
            tools = None
            if not no_tool and len(self.available_tools) > 0:
                tools = []
                for tool in self.available_tools:
                    tools.append(self._convert_tools_to_dict(tool))
                    async_ten_env.log_info(f"tool: {tool}")
            
            self.sentence_fragment = ""

            # Create an asyncio.Event to signal when content is finished
            content_finished_event = asyncio.Event()
            # Create a future to track the single tool call task
            self.tool_task_future = None

            message_id = str(uuid.uuid4())[:8]
            self.last_reasoning_ts = int(time.time() * 1000)

            # Create an async listener to handle tool calls and content updates
            async def handle_tool_call(tool_call):
                self.tool_task_future = asyncio.get_event_loop().create_future()
                async_ten_env.log_info(f"tool_call: {tool_call}")
                for tool in self.available_tools:
                    if tool_call["function"]["name"] == tool.name:
                        cmd: Cmd = Cmd.create(CMD_TOOL_CALL)
                        cmd.set_property_string("name", tool.name)
                        cmd.set_property_from_json(
                            "arguments", tool_call["function"]["arguments"]
                        )
                        # cmd.set_property_from_json("arguments", json.dumps([]))

                        # Send the command and handle the result through the future
                        [result, _] = await async_ten_env.send_cmd(cmd)
                        if result.get_status_code() == StatusCode.OK:
                            tool_result: LLMToolResult = json.loads(
                                result.get_property_to_json(CMD_PROPERTY_RESULT)
                            )

                            async_ten_env.log_info(f"tool_result: {tool_result}")

                            
                            if tool_result["type"] == "llmresult":
                                result_content = tool_result["content"]
                                if isinstance(result_content, str):
                                    tool_message = {
                                        "role": "assistant",
                                        "tool_calls": [tool_call],
                                    }
                                    new_message = {
                                        "role": "tool",
                                        "content": result_content,
                                        "tool_call_id": tool_call["id"],
                                    }
                                    await self.queue_input_item(
                                        True, messages=[tool_message, new_message], no_tool=True
                                    )
                                else:
                                    async_ten_env.log_error(
                                        f"Unknown tool result content: {result_content}"
                                    )
                            elif tool_result["type"] == "requery":
                                # self.memory_cache = []
                                self.memory_cache.pop()
                                result_content = tool_result["content"]
                                nonlocal message
                                new_message = {
                                    "role": "user",
                                    "content": self._convert_to_content_parts(
                                        message["content"]
                                    ),
                                }
                                new_message["content"] = new_message[
                                    "content"
                                ] + self._convert_to_content_parts(result_content)
                                await self.queue_input_item(
                                    True, messages=[new_message], no_tool=True
                                )
                            else:
                                async_ten_env.log_error(
                                    f"Unknown tool result type: {tool_result}"
                                )
                        else:
                            async_ten_env.log_error("Tool call failed")
                self.tool_task_future.set_result(None)

            async def handle_content_update(content: str):
                # Append the content to the last assistant message
                # 同时更新memory_cache和last_assistant_message
                for item in reversed(self.memory_cache):
                    if item.get("role") == "assistant":
                        item["content"] = item["content"] + content
                        break
                
                sentences, self.sentence_fragment = parse_sentences(
                    self.sentence_fragment, content
                )
                for sentence in sentences:
                    self.last_assistant_message += sentence
                    self.send_text_output(async_ten_env, sentence, False)

            async def handle_reasoning_update(think: str):
                ts = int(time.time() * 1000)
                if ts - self.last_reasoning_ts >= 200:
                    self.last_reasoning_ts = ts
                    self.send_reasoning_text_output(async_ten_env, message_id, think, False)

            async def handle_reasoning_update_finish(think: str):
                self.last_reasoning_ts = int(time.time() * 1000)
                self.send_reasoning_text_output(async_ten_env, message_id, think, True)

            async def handle_content_finished(_: str):
                # Wait for the single tool task to complete (if any)
                if self.tool_task_future:
                    await self.tool_task_future
                self.tool_task_future = None

                # Signal that the content is finished
                content_finished_event.set()

            # Create the event emitter
            listener = AsyncEventEmitter()
            listener.on("tool_call", handle_tool_call)
            listener.on("content_update", handle_content_update)
            listener.on("reasoning_update", handle_reasoning_update)
            listener.on("reasoning_update_finish", handle_reasoning_update_finish)
            listener.on("content_finished", handle_content_finished)


             # Make an async API call to get chat completions
            await self.client.get_chat_completions_stream(
                memory + messages, tools, listener
            )

            # Wait for the content to finish
            await content_finished_event.wait()

            async_ten_env.log_info(
                f"Chat completion finished for input text: {messages}"
            )

        except Exception as e:
            async_ten_env.log_error(f"Error in chat completion: {e}")
            async_ten_env.log_error(traceback.format_exc())
        finally:
            self.send_text_output(async_ten_env, "", True)
            async_ten_env.log_info(f"prepare store memory: last_user_message:{self.last_user_message},last_assistant_message:{self.last_assistant_message}")
            if self.memory_manager and self.last_user_message and self.last_assistant_message:
                async_ten_env.log_info("store conversation in memory")
                asyncio.create_task(self.memory_manager.store_memory(
                        self.last_user_message,
                        self.last_assistant_message
                    ))
            else:
                async_ten_env.log_info("not store conversation in memory")
            # always append the memory
            for m in self.memory_cache:
                self._append_memory(m)
            # 重置最后的消息缓存
            self.last_user_message = ""
            self.last_assistant_message = ""

    
    def _append_memory(self, message: str):
        """将消息添加到memory中，并维护最大长度限制"""
        if len(self.memory) > self.config.max_memory_length:
            removed_item = self.memory.pop(0)
            # 如果删除的是工具调用，可能需要同时删除对应的工具回复
            if removed_item.get("tool_calls") and len(self.memory) > 0 and self.memory[0].get("role") == "tool":
                self.memory.pop(0)
        self.memory.append(message)
    
    def send_reasoning_text_output(
        self, async_ten_env: AsyncTenEnv, msg_id:str, sentence: str, end_of_segment: bool
    ):
        """发送推理文本输出"""
        try:
            output_data = Data.create(CONTENT_DATA_OUT_NAME)
            output_data.set_property_string(DATA_OUT_PROPERTY_TEXT, json.dumps({
                "id":msg_id,
                "data": {
                    "text": sentence
                },
                "type": "reasoning"
            }))
            output_data.set_property_bool(
                DATA_OUT_PROPERTY_END_OF_SEGMENT, end_of_segment
            )
            asyncio.create_task(async_ten_env.send_data(output_data))
        except Exception as e:
            async_ten_env.log_warn(
                f"发送推理文本失败 [{sentence}]，错误: {e}"
            )

    def _convert_to_content_parts(
        self, content: Iterable[LLMChatCompletionContentPartParam]
    ):
        """Convert content parts to the required format."""
        result = []
        for part in content:
            if part["type"] == "text":
                result.append({"type": "text", "text": part["text"]})
            else:
                pass
        return result

    def _convert_tools_to_dict(self, tool: LLMToolMetadata):
        """Convert the tool to the expected format."""
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }

    def message_to_dict(self, message: LLMChatCompletionMessageParam):
        """Convert the message to a dict."""
        if isinstance(message.get("content"), list):
            return {
                "role": message.get("role"),
                "content": self._convert_to_content_parts(message.get("content")),
            }
        return message
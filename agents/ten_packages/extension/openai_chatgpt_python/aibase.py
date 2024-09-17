#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

from abc import abstractmethod
import asyncio
from collections import deque
import json
import threading
import traceback
from typing import Any, Dict, List, Union
from ten.audio_frame import AudioFrame
from ten.cmd import Cmd
from ten.cmd_result import CmdResult, StatusCode
from ten.data import Data
from ten.ten_env import TenEnv
from ten.video_frame import VideoFrame
from .log import logger
from ten.extension import Extension




class AsyncEventEmitter:
    def __init__(self):
        self.listeners = {}

    def on(self, event_name, listener):
        """Register an event listener."""
        if event_name not in self.listeners:
            self.listeners[event_name] = []
        self.listeners[event_name].append(listener)

    def emit(self, event_name, *args, **kwargs):
        """Fire the event without waiting for listeners to finish."""
        if event_name in self.listeners:
            for listener in self.listeners[event_name]:
                asyncio.create_task(listener(*args, **kwargs))


class AsyncQueue:
    def __init__(self):
        self._queue = deque()  # Use deque for efficient prepend and append
        self._condition = asyncio.Condition()  # Use Condition to manage access

    async def put(self, item, prepend=False):
        """Add an item to the queue (prepend if specified)."""
        async with self._condition:
            if prepend:
                self._queue.appendleft(item)  # Prepend item to the front
            else:
                self._queue.append(item)  # Append item to the back
            self._condition.notify() 

    async def get(self):
        """Remove and return an item from the queue."""
        async with self._condition:
            while not self._queue:
                await self._condition.wait()  # Wait until an item is available
            return self._queue.popleft()  # Pop from the front of the deque

    async def flush(self):
        """Flush all items from the queue."""
        async with self._condition:
            while self._queue:
                self._queue.popleft()  # Clear the queue
            self._condition.notify_all()  # Notify all consumers that the queue is empty

    def __len__(self):
        """Return the current size of the queue."""
        return len(self._queue)

class LLMExtension(Extension):

    # Create the queue for message processing
    queue = AsyncQueue()
    current_task = None
    available_tools = []
    available_tools_lock = asyncio.Lock()  # Lock to ensure thread-safe access

    def __init__(self, name: str):
        super().__init__(name)

    def on_init(self, ten_env: TenEnv) -> None:
        pass

    def on_start(self, ten_env: TenEnv) -> None:
        logger.info("on_start")

        self.loop = asyncio.new_event_loop()
        def start_loop():
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        threading.Thread(target=start_loop, args=[]).start()

        self.loop.create_task(self._process_queue(ten_env))

        async def _on_register_tool(result):
            tool = TenLLMTool.tool_from_json(json.loads(self.get_property_to_json(result, "data")))
            async with self.available_tools_lock:
                self.available_tools.append(tool)
            logger.info("register_tool result: " + json.dumps(tool.getManifest()))

        # Register the tool
        logger.info("register_tool started..")
        ten_env.send_cmd(Cmd.create("register_tool"), lambda ten_env, result: asyncio.run_coroutine_threadsafe(_on_register_tool(result), self.loop))

    def on_stop(self, ten_env: TenEnv) -> None:
        pass

    def on_deinit(self, ten_env: TenEnv) -> None:
        pass

    def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        pass

    def on_data(self, ten_env: TenEnv, data: Data) -> None:
        pass

    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        # TODO: process pcm frame
        pass

    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        pass

    """
    Extension enhanced APIs on top of base Extension
    """
    def queue_data_frame(self, ten_env: TenEnv, data: any, prepend=False):
        future = None
        if not prepend:
            future = asyncio.run_coroutine_threadsafe(self.queue.put(data), self.loop)
        else:
            future = asyncio.run_coroutine_threadsafe(self.queue.put(data, prepend=True), self.loop)
        try:
            result = future.result()  # This will wait for the result (blocking) or raise an exception if one occurred
        except Exception as exc:
            logger.error(f"Error occurred while queue_data_frame: {traceback.format_exc()}")

    def flush_data_frame_queue(self):
        future = asyncio.run_coroutine_threadsafe(self._flush_queue(), self.loop)
        try:
            result = future.result()  # This will wait for the result (blocking) or raise an exception if one occurred
        except Exception as exc:
            logger.error(f"Error occurred while flush_data_frame_queue: {exc}")

    @abstractmethod
    async def on_process_data_frame(self, ten_env: TenEnv, data: any) -> None:
        pass
    def get_property(self, ten_env: TenEnv, property_name: str, getter_name: str):
        """Generalized helper to get a property with error handling."""
        try:
            # Dynamically call the appropriate getter function
            getter_func = getattr(ten_env, getter_name)
            return getter_func(property_name)
        except Exception as err:
            logger.warning(f"GetProperty {property_name} failed: {err}")
            return None
    # Wrapper functions for each property type
    def get_property_bool(self, ten_env: 'TenEnv', property_name: str) -> bool:
        return self.get_property(ten_env, property_name, "get_property_bool")

    def get_property_string(self, ten_env: 'TenEnv', property_name: str) -> str:
        return self.get_property(ten_env, property_name, "get_property_string")

    def get_property_int(self, ten_env: 'TenEnv', property_name: str) -> int:
        return self.get_property(ten_env, property_name, "get_property_int")

    def get_property_float(self, ten_env: 'TenEnv', property_name: str) -> float:
        return self.get_property(ten_env, property_name, "get_property_float")
    
    def get_property_to_json(self, ten_env: 'TenEnv', property_name: str) -> str:
        return self.get_property(ten_env, property_name, "get_property_to_json")

    """
    private apis
    """

    async def _process_queue(self, ten_env: TenEnv):
        """Asynchronously process queue items one by one."""
        while True:
            # Wait for an item to be available in the queue
            data = await self.queue.get()
            try:
                # Create a new task for the new message
                self.current_task = asyncio.create_task(self.on_process_data_frame(ten_env, data))
                await self.current_task  # Wait for the current task to finish or be cancelled
            except asyncio.CancelledError:
                logger.info(f"Task cancelled")

    async def _flush_queue(self):
        """Flushes the self.queue and cancels the current task."""
        # Flush the queue using the new flush method
        await self.queue.flush()

        # Cancel the current task if one is running
        if self.current_task:
            logger.info("Cancelling the current task during flush.")
            self.current_task.cancel()



class TenLLMTool:
    name: str
    description: str
    arguments: any = []

    def __init__(self, name: str, description: str, arguments: any):
        self.name = name
        self.description = description
        self.arguments = arguments

    @staticmethod
    def tool_from_json(data: dict):
        """Create a TenLLMTool instance from a JSON-like dictionary."""
        try:
            # Extract required fields from the input data
            name = data.get('name')
            description = data.get('description')
            arguments = data.get('arguments')

            # Check if essential fields are present
            if not all([name, description]):
                raise ValueError("Missing required fields in JSON data")

            # Return the constructed TenLLMTool object
            return TenLLMTool(name, description, arguments)

        except Exception as e:
            logger.error(f"Error creating TenLLMTool from JSON: {e}")
            return None

    def getManifest(self):
        return {
            "name": self.name,
            "description": self.description,
            "arguments": self.arguments
        }
    

class TenLLMToolResultItem:
    def __init__(self, type: str, value: Union[str, Any]):
        self.type = type
        self.value = value

    # Convert to a JSON string directly
    def to_json(self) -> Dict[str, Any]:
        if self.type == "text":
            return {"type": self.type, "text": self.value}
        elif self.type == "image":
            return {"type": self.type, "image": self.value}
        else:
            raise ValueError(f"Unsupported type: {self.type}")

    # Create an object from a JSON string
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'TenLLMToolResultItem':
        item_type = data["type"]
        if item_type == "text":
            return cls(type=item_type, value=data["text"])
        elif item_type == "image":
            return cls(type=item_type, value=data["image"])
        else:
            raise ValueError(f"Unsupported type: {item_type}")

class TenLLMToolResult:
    variables: List[TenLLMToolResultItem]

    def __init__(self):
        self.variables: List[TenLLMToolResultItem] = []

    def add_value(self, type: str, value: Union[str, Any]) -> None:
        # Add a TenLLMToolResultItem to the variables list
        item = TenLLMToolResultItem(type=type, value=value)
        self.variables.append(item)

    # Access items based on type
    def get_items_by_type(self, type: str) -> List[TenLLMToolResultItem]:
        return [item for item in self.variables if item.type == type]

    # Convert to a JSON string directly
    def to_json(self) -> List[Dict[str, Any]]:
        return [item.to_json() for item in self.variables]

    # Create an object from a JSON string
    @classmethod
    def from_json(cls, data: List[Dict[str, Any]]) -> 'TenLLMToolResult':
        instance = cls()
        instance.variables = [TenLLMToolResultItem.from_json(item) for item in data]
        return instance

class LLMToolExtension(Extension):

    # Create the queue for message processing
    queue = AsyncQueue()
    current_task = None

    def __init__(self, name: str):
        super().__init__(name)

    def on_init(self, ten_env: TenEnv) -> None:
        pass

    def on_start(self, ten_env: TenEnv) -> None:
        logger.info("on_start")

        self.loop = asyncio.new_event_loop()
        def start_loop():
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        threading.Thread(target=start_loop, args=[]).start()

    def on_stop(self, ten_env: TenEnv) -> None:
        pass

    def on_deinit(self, ten_env: TenEnv) -> None:
        pass

    def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        logger.info("on_cmd name {}".format(cmd_name))

        result = None
        err = None
        if cmd_name == "register_tool":
            future = asyncio.run_coroutine_threadsafe(self.on_register_tool(ten_env, None), self.loop)
            try:
                tool = future.result()  # This will wait for the result (blocking) or raise an exception if one occurred
                result = tool.getManifest()
                status_code = StatusCode.OK
            except Exception as exc:
                logger.error(f"Error occurred while on_register_tool: {traceback.format_exc()}")
                status_code = StatusCode.ERROR
                err = {"message": f"Error occurred while on_register_tool: {exc}"}
            
        elif cmd_name == "run_tool":
            future = asyncio.run_coroutine_threadsafe(self.on_run_tool(ten_env, None), self.loop)
            try:
                tool_result = future.result()  # This will wait for the result (blocking) or raise an exception if one occurred
                result = tool_result.to_json()
                status_code = StatusCode.OK
            except Exception as exc:
                logger.error(f"Error occurred while on_run_tool: {exc}")
                status_code = StatusCode.ERROR
                err = {"message": f"Error occurred while on_run_tool: {exc}"}
        else:
            logger.info(f"on_cmd unknown cmd: {cmd_name}")
            status_code, err = StatusCode.ERROR, {"message": f"unknown cmd"}
        
        cmd_result = CmdResult.create(status_code)
        if status_code == StatusCode.ERROR:
            cmd_result.set_property_from_json("error", json.dumps(err))
        else:
            cmd_result.set_property_from_json("data", json.dumps(result))
        ten_env.return_result(cmd_result, cmd)

    """
    Extension enhanced APIs on top of base Extension
    """
    @abstractmethod
    async def on_register_tool(self, ten_env: TenEnv, data: any) -> TenLLMTool:
        pass

    @abstractmethod
    async def on_run_tool(self, ten_env: TenEnv, data: any) -> TenLLMToolResult:
        pass
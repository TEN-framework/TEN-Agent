#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import json
from base64 import b64encode
from io import BytesIO
from typing import Any, Dict
import threading
from ten_ai_base.llm_tool import AsyncLLMToolBaseExtension
from ten_ai_base.types import LLMToolMetadata, LLMToolMetadataParameter, LLMToolResult, LLMDataCompletionArgs
from .openai import OpenAIChatGPT, OpenAIChatGPTConfig

from PIL import Image
from ten_ai_base.helper import AsyncEventEmitter

import traceback
from ten import (
    AsyncTenEnv,
    AudioFrame,
    VideoFrame,
    Cmd,
    Data
)

START_APP_TOOL_NAME = "start_app"
START_APP_TOOL_DESCRIPTION = "start an application with name"

SAVE_TO_NOTEBOOK_TOOL_NAME = "save_to_notebook"
SAVE_TO_NOTEBOOK_TOOL_DESCRIPTION = "call this whenever you need to save anything to notebook"    

GENERATE_SOURCE_CODE_TOOL_NAME = "generate_source_code"
GENERATE_SOURCE_CODE_TOOL_DESCRIPTION = "Use this tool whenever the user requests to generate or write source code. Examples include: 'Can you generate a function to get the current time?', 'Generate a shopping cart list using Swift.', 'Write a Python script to fetch weather data.', 'Create a Java class for a user profile.'"

GET_SOURCE_CODE_TOOL_NAME = "get_source_code"
GET_SOURCE_CODE_TOOL_DESCRIPTION = "call this whenever you need to get source code for evaluation or refactoring, for example when user asks 'Can you help me with the code?', 'Can you help take a look at my code?', 'Take a look at my source code', You can use screenshare or not to get code"

def rgb2base64jpeg(rgb_data, width, height):
    # Convert the RGB image to a PIL Image
    pil_image = Image.frombytes("RGBA", (width, height), bytes(rgb_data))
    pil_image = pil_image.convert("RGB")

    # Resize the image while maintaining its aspect ratio
    pil_image = resize_image_keep_aspect(pil_image, 1080)

    # Save the image to a BytesIO object in JPEG format
    buffered = BytesIO()
    pil_image.save(buffered, format="png")
    pil_image.save("test.png", format="png")

    # Get the byte data of the JPEG image
    jpeg_image_data = buffered.getvalue()

    # Convert the JPEG byte data to a Base64 encoded string
    base64_encoded_image = b64encode(jpeg_image_data).decode("utf-8")

    # Create the data URL
    mime_type = "image/png"
    base64_url = f"data:{mime_type};base64,{base64_encoded_image}"
    return base64_url


def resize_image_keep_aspect(image, max_size=512):
    """
    Resize an image while maintaining its aspect ratio, ensuring the larger dimension is max_size.
    If both dimensions are smaller than max_size, the image is not resized.

    :param image: A PIL Image object
    :param max_size: The maximum size for the larger dimension (width or height)
    :return: A PIL Image object (resized or original)
    """
    # Get current width and height
    width, height = image.size

    # If both dimensions are already smaller than max_size, return the original image
    if width <= max_size and height <= max_size:
        return image

    # Calculate the aspect ratio
    aspect_ratio = width / height

    # Determine the new dimensions
    if width > height:
        new_width = max_size
        new_height = int(max_size / aspect_ratio)
    else:
        new_height = max_size
        new_width = int(max_size * aspect_ratio)

    # Resize the image with the new dimensions
    resized_image = image.resize((new_width, new_height))

    return resized_image

class ComputerToolExtension(AsyncLLMToolBaseExtension):
    
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.openai_chatgpt = None
        self.config = None
        self.coding_text_queue = asyncio.Queue()    
        self.loop = None
        self.memory = []
        self.max_memory_length = 10
        self.image_data = None
        self.image_width = 0
        self.image_height = 0
        self.coding_text = ""
        self.apps_list = {
            "WeChat": "com.tencent.xinWeChat",
            "Xcode": "com.apple.dt.Xcode",
            "Safari": "com.apple.Safari",
            "Word": "com.microsoft.Word",
            "Excel": "com.microsoft.Excel",
            "PowerPoint": "com.microsoft.PowerPoint",
            "Pages": "com.apple.Pages",
            "Numbers": "com.apple.Numbers",
            "Keynote": "com.apple.Keynote",
            "AppleMusic": "com.apple.Music",
            "Photos": "com.apple.Photos",
            "Mail": "com.apple.mail",
            "Messages": "com.apple.Messages",
            "Calendar": "com.apple.Calendar",
            "Notes": "com.apple.Notes",
        }

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_init")
        await super().on_init(ten_env)

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_start")
        self.loop = asyncio.new_event_loop()

        def start_loop():
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()

        threading.Thread(target=start_loop, args=[]).start()
        asyncio.run_coroutine_threadsafe(self.process_coding_text_queue(ten_env), self.loop)
        await super().on_start(ten_env)

        # Prepare configuration
        self.config = OpenAIChatGPTConfig.create(ten_env=ten_env)

        # Mandatory properties
        if not self.config.api_key:
            ten_env.log_info(f"API key is missing, exiting on_start")
            return
        
        self.openai_chatgpt = OpenAIChatGPT(ten_env, self.config)   

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_stop")
        await super().on_stop(ten_env)

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_deinit")
        await super().on_deinit(ten_env)

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug("on_cmd name {}".format(cmd_name))
        await super().on_cmd(ten_env, cmd)
        if cmd_name == "coding_text":
            self.coding_text = cmd.get_property_string("text")
        elif cmd_name == "flush":
            asyncio.run_coroutine_threadsafe(self.flush_coding_text_queue(), self.loop)

    async def on_audio_frame(self, ten_env: AsyncTenEnv, audio_frame: AudioFrame) -> None:
        audio_frame_name = audio_frame.get_name()
        ten_env.log_debug("on_audio_frame name {}".format(audio_frame_name))

        # TODO: process audio frame
        pass

    async def on_video_frame(self, ten_env: AsyncTenEnv, video_frame: VideoFrame) -> None:
        video_frame_name = video_frame.get_name()
        ten_env.log_debug("on_video_frame name {}".format(video_frame_name))

        self.image_data = video_frame.get_buf()
        self.image_width = video_frame.get_width()
        self.image_height = video_frame.get_height()

    def get_tool_metadata(self, ten_env: AsyncTenEnv) -> list[LLMToolMetadata]:
        return [
            LLMToolMetadata(
                name=START_APP_TOOL_NAME,
                description=START_APP_TOOL_DESCRIPTION,
                parameters=[
                    LLMToolMetadataParameter(
                        name="name",
                        type="string",
                        description="The application name to start",
                        required=True,
                    )
                ]
            ),
            LLMToolMetadata(
                name=SAVE_TO_NOTEBOOK_TOOL_NAME,
                description=SAVE_TO_NOTEBOOK_TOOL_DESCRIPTION,
                parameters=[
                    LLMToolMetadataParameter(
                        name="text",
                        type="string",
                        description="The text to save",
                        required=True,
                    )
                ]
            ),
            LLMToolMetadata(
                name=GENERATE_SOURCE_CODE_TOOL_NAME,
                description=GENERATE_SOURCE_CODE_TOOL_DESCRIPTION,
                parameters=[
                    LLMToolMetadataParameter(
                        name="name",
                        type="string",
                        description="What code do you want to generate?",
                        required=True,
                    )
                ]
            ),
            LLMToolMetadata(
                name=GET_SOURCE_CODE_TOOL_NAME,
                description=GET_SOURCE_CODE_TOOL_DESCRIPTION,
                parameters=[
                    LLMToolMetadataParameter(
                        name="use_screenshare",
                        type="boolean",
                        description="use screenshare to get the code, if false, use the code from clipboard",
                        required=True,
                    ),
                    LLMToolMetadataParameter(
                        name="name",
                        type="string",
                        description="What do you want to do with the code?",
                        required=True,
                    )
                ]
            )
        ]

    async def run_tool(self, ten_env: AsyncTenEnv, name: str, args: dict) -> LLMToolResult:
        if name == START_APP_TOOL_NAME:
            app_name = args.get("name")
            if app_name not in self.apps_list:
                return {"content": json.dumps({"text": f"app {app_name} not found"})}
            result = await self._start_application(args, ten_env)
            return {"content": json.dumps(result)}
        elif name == SAVE_TO_NOTEBOOK_TOOL_NAME:
            result = await self._save_to_notebook(args, ten_env)
            return {"content": json.dumps(result)}
        elif name == GET_SOURCE_CODE_TOOL_NAME:
            use_screenshare = args.get("use_screenshare")
            name = args.get("name")
            if not use_screenshare:
                if self.coding_text is not None:
                    asyncio.create_task(self.coding_completion(ten_env, ["coding", [{
                        "type": "text",
                        "text": self.coding_text
                    }, {
                        "type": "text",
                        "text": name
                    }], self.memory], "generate_source"))
                    return {"content": json.dumps({"text": f"just say 'just say 'the coding assistance has been provided'"})}
                else:
                    return {"content": json.dumps({"text": f"just say 'i can't find code in your clipboard'"})}
            else:
                if self.image_data is not None: 
                    base64_image = rgb2base64jpeg(self.image_data, self.image_width, self.image_height)
                    asyncio.create_task(self.coding_completion(ten_env, ["coding", [{
                        "type": "image_url",
                        "image_url": {"url": base64_image}
                    }, {
                        "type": "text",
                        "text": name
                    }], self.memory], "generate_source"))
                    return {"content": json.dumps({"text": f"just say 'just say 'the coding assistance has been provided'"})}
                else:
                    return {"content": json.dumps({"text": f"just say 'screenshare is not visible to me'"})}
        elif name == GENERATE_SOURCE_CODE_TOOL_NAME:
            generate_name = args.get("name")
            asyncio.create_task(self.coding_completion(ten_env, ["coding", [{
                "type": "text",
                "text": generate_name
            }], self.memory], "generate_source"))
            return {"content": json.dumps({"text": f"just say 'the coding assistance has been provided'"})}

    async def _start_application(self, args: dict, ten_env: AsyncTenEnv) -> Any:
        app_name = args.get("name")
        app_bundle_id = self.apps_list.get(app_name)
        self._send_data(ten_env, "start_app", {"bundle_id": app_bundle_id, "app_name": app_name})
        return {"text": f"just say '{app_name} is starting'"}

    async def _save_to_notebook(self, args: dict, ten_env: AsyncTenEnv) -> Any:
        text = args.get("text")
        self._send_data(ten_env, "save_to_notebook", args)
        return {"text": f"just say 'the content has been saved to notebook'"}

    def _send_data(self, ten_env: AsyncTenEnv, action: str, data: Dict[str, Any]):
        try:
            action_data = json.dumps({
                "data_type": "action",
                "action": action,
                "data": data
            })
            output_data = Data.create("data")
            output_data.set_property_buf("data", action_data.encode("utf-8"))
            ten_env.send_data(output_data)
        except Exception as err:
            ten_env.log_warn(f"send data error {err}")

    async def coding_completion(self, ten_env: AsyncTenEnv, data: any, action: str) -> None:
        """Run the chatflow asynchronously."""
        [task_type, content, memory] = data
        try:
            message = None
            tools = None

            message = {"role": "user", "content": content}
            non_artifact_content = [item for item in content if item.get("type") != "image_url"]
            non_artifact_message = {"role": "user", "content": non_artifact_content}

            response_text = ""

            # Create an asyncio.Event to signal when content is finished
            content_finished_event = asyncio.Event()

            async def handle_content_update(content:str):
                nonlocal response_text
                # Append the content to the last assistant message
                try:
                    await self.coding_text_queue.put({"text":content, "is_final": False, "action": action})
                except Exception as e:
                    ten_env.log_error(f"Error in handle_content_update: {traceback.format_exc()} for input text: {content}")
                response_text += content

            async def handle_content_finished(full_content:str):
                # Wait for the single tool task to complete (if any)
                try:
                    await self.coding_text_queue.put({"text":"", "is_final": True, "action": action})
                except Exception as e:
                    ten_env.log_error(f"Error in handle_content_finished: {traceback.format_exc()} for input text: {full_content}")
                content_finished_event.set()

            listener = AsyncEventEmitter()
            listener.on("content_update", handle_content_update)
            listener.on("content_finished", handle_content_finished)

            # Make an async API call to get chat completions
            await self.openai_chatgpt.get_chat_completions_stream(memory + [message], tools, listener)

            # Wait for the content to be finished
            await content_finished_event.wait()

            self._append_memory(non_artifact_message)
            self._append_memory({"role": "assistant", "content": response_text})
        except asyncio.CancelledError:
            ten_env.log_info(f"Task cancelled: {content}")
        except Exception as e:
            ten_env.log_error(f"Error in chat_completion: {traceback.format_exc()} for input text: {content}")
        finally:
            ten_env.log_info(f"Task completed: {content}")

    def _append_memory(self, message: Dict[str, Any]):
        if len(self.memory) > self.max_memory_length:
            self.memory.pop(0)
        self.memory.append(message)    
    
    async def flush_coding_text_queue(self):
        while not self.coding_text_queue.empty():
            await self.coding_text_queue.get()
            self.coding_text_queue.task_done()
    
    async def process_coding_text_queue(self, ten_env: AsyncTenEnv):
        while True:
            if self.coding_text_queue.empty():
                await asyncio.sleep(0.1)
                continue
            try:
                coding_text = await self.coding_text_queue.get()
                self._send_data(ten_env, coding_text["action"], {"text": coding_text["text"], "is_final": coding_text["is_final"]})
            except Exception as e:
                ten_env.log_error(f"Error in process_coding_text_queue: {traceback.format_exc()} for input text: {coding_text}")
            self.coding_text_queue.task_done()
            await asyncio.sleep(0.1)
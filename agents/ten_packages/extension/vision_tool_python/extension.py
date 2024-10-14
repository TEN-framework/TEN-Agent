#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import json
import functools

from datetime import datetime
from queue import Queue
from threading import Event, Thread
from typing import Any, List, Tuple, Union
from PIL import Image
from io import BytesIO
from base64 import b64encode

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

PROPERTY_HISTORY = "history"
PROPERTY_FREQUENCY_MS = "frequency_ms"
PROPERTY_USE_LLM = "use_llm"

CMD_TOOL_REGISTER = "tool_register"
CMD_TOOL_CALL = "tool_call"
CMD_PROPERTY_NAME = "name"
CMD_PROPERTY_ARGS = "args"

CMD_CHAT_COMPLETION = "chat_completion"

TOOL_REGISTER_PROPERTY_NAME = "name"
TOOL_REGISTER_PROPERTY_DESCRIPTON = "description"
TOOL_REGISTER_PROPERTY_PARAMETERS = "parameters"
TOOL_CALLBACK = "callback"

# TODO auto register and unregister
SINGLE_FRAME_TOOL_NAME = "query_single_image"
SINGLE_FRAME_TOOL_DESCRIPTION = "Query to the latest frame from camera. The camera is always on, always use latest frame to answer user's question. Call this whenever you need to understand the input camera image like you have vision capability, for example when user asks 'What can you see?', 'Can you see me?', 'take a look.'"
SINGLE_FRAME_TOOL_PARAMETERS = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The detail infomation use is interested in. You need to summary the conversation context first and ask for detail information, e.g. We saw a laptop on the desk just now, can you identify what language is the code shown in the laptop screen?"
            }
        },
        "required": ["query"],
}

SINGLE_FRAME_TOOL_NON_LLM_PARAMETERS = {}

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

def rgb2base64jpeg(rgb_data: bytes, width: int, height: int, raw: bool = False) -> Union[bytes, str]:
    # Convert the RGB image to a PIL Image
    pil_image = Image.frombytes("RGBA", (width, height), bytes(rgb_data))
    pil_image = pil_image.convert("RGB")

    # Resize the image while maintaining its aspect ratio
    pil_image = resize_image_keep_aspect(pil_image, 320)

    # Save the image to a BytesIO object in JPEG format
    buffered = BytesIO()
    pil_image.save(buffered, format="JPEG")
    # pil_image.save("test.jpg", format="JPEG")

    # Get the byte data of the JPEG image
    jpeg_image_data = buffered.getvalue()
    if raw:
        return jpeg_image_data

    # Convert the JPEG byte data to a Base64 encoded string
    base64_encoded_image = b64encode(jpeg_image_data).decode("utf-8")

    # Create the data URL
    mime_type = "image/jpeg"
    base64_url = f"data:{mime_type};base64,{base64_encoded_image}"
    return base64_url

class VisionToolExtension(Extension):
    max_history: int = 1
    frequency_ms: int = 60
    use_llm: bool = True

    history: list = []
    queue: Queue = Queue()
    last_capture: datetime = None
    llm_tools = {}
    tools = {}

    thread: Thread = None
    stopped: bool = False

    ten_env: TenEnv = None

    def on_init(self, ten_env: TenEnv) -> None:
        logger.info("VisionToolExtension on_init")

        # Change tool!
        self.tools = {
            SINGLE_FRAME_TOOL_NAME: {
                TOOL_REGISTER_PROPERTY_NAME: SINGLE_FRAME_TOOL_NAME,
                TOOL_REGISTER_PROPERTY_DESCRIPTON: SINGLE_FRAME_TOOL_DESCRIPTION,
                TOOL_REGISTER_PROPERTY_PARAMETERS: SINGLE_FRAME_TOOL_NON_LLM_PARAMETERS,
                TOOL_CALLBACK: functools.partial(self._ask_to_latest_frames, 1)
            }
        }

        self.llm_tools = {
            SINGLE_FRAME_TOOL_NAME: {
                TOOL_REGISTER_PROPERTY_NAME: SINGLE_FRAME_TOOL_NAME,
                TOOL_REGISTER_PROPERTY_DESCRIPTON: SINGLE_FRAME_TOOL_DESCRIPTION,
                TOOL_REGISTER_PROPERTY_PARAMETERS: SINGLE_FRAME_TOOL_PARAMETERS,
                TOOL_CALLBACK: functools.partial(self._ask_to_latest_frames, 1)
            }
        }

        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        logger.info("VisionToolExtension on_start")

        self.ten_env = ten_env

        self.thread = Thread(target=self.loop)
        self.thread.start()

        try:
            self.max_history = ten_env.get_property_string(PROPERTY_HISTORY)
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_HISTORY} error: {err}")
        
        try:
            self.frequency_ms = ten_env.get_property_int(PROPERTY_FREQUENCY_MS)
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_FREQUENCY_MS} error: {err}")
        
        try:
            self.use_llm = ten_env.get_property_bool(PROPERTY_USE_LLM)
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_USE_LLM} error: {err}")

        ten_env.on_start_done()

    def on_stop(self, ten_env: TenEnv) -> None:
        logger.info("VisionToolExtension on_stop")

        self.stopped = True
        self.queue.put(None)
        self.thread.join()
        
        ten_env.on_stop_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        logger.info("VisionToolExtension on_deinit")
        ten_env.on_deinit_done()

    def loop(self) -> None:
        while not self.stopped:
            t = self.queue.get()
            if t is None:
                break

            try:
                # unpack
                callback, args, cmd = t
                logger.info(f"before callback {args}")
                resp = callback(args)
                logger.info(f"after callback {resp}")
                cmd_result = CmdResult.create(StatusCode.OK)
                cmd_result.set_property_string("response", json.dumps(resp))
                self.ten_env.return_result(cmd_result, cmd)
            except:
                logger.exception(f"Failed to fetch from queue")
                if cmd:
                    cmd_result = CmdResult.create(StatusCode.ERROR)
                    self.ten_env.return_result(cmd_result, cmd)

    def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        logger.info("on_cmd name {}".format(cmd_name))

        # FIXME need to handle async
        try:
            name = cmd.get_property_string(CMD_PROPERTY_NAME)
            if name in self.tools:
                try:
                    tool = self.tools[name]
                    args = cmd.get_property_string(CMD_PROPERTY_ARGS)
                    arg_dict = json.loads(args)
                    self.queue.put((tool[TOOL_CALLBACK], arg_dict, cmd))
                    # will return result later
                    return
                except:
                    logger.exception("Failed to callback")
                    cmd_result = CmdResult.create(StatusCode.ERROR)
                    ten_env.return_result(cmd_result, cmd)
                    return
            else:
                logger.error(f"unknown tool name {name}")
        except:
            logger.exception("Failed to get tool name")
            cmd_result = CmdResult.create(StatusCode.ERROR)
            ten_env.return_result(cmd_result, cmd)
            return

        cmd_result = CmdResult.create(StatusCode.OK)
        ten_env.return_result(cmd_result, cmd)

    def on_data(self, ten_env: TenEnv, data: Data) -> None:
        pass

    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        pass

    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        if self.last_capture is None:
            # Register func after video is captured
            tool_targets = self.tools
            if self.use_llm:
                tool_targets = self.llm_tools

            for name, tool in tool_targets.items():
                c = Cmd.create(CMD_TOOL_REGISTER)
                c.set_property_string(TOOL_REGISTER_PROPERTY_NAME, name)
                c.set_property_string(TOOL_REGISTER_PROPERTY_DESCRIPTON, tool[TOOL_REGISTER_PROPERTY_DESCRIPTON])
                c.set_property_string(TOOL_REGISTER_PROPERTY_PARAMETERS, json.dumps(tool[TOOL_REGISTER_PROPERTY_PARAMETERS]))
                ten_env.send_cmd(c, lambda ten, result: logger.info(f"register done, {result}"))

        now = datetime.now()
        if self.frequency_ms and (not self.last_capture or (now - self.last_capture).total_seconds() * 1000 > self.frequency_ms):
            self.history.append((now, video_frame.get_buf(), video_frame.get_width(), video_frame.get_height()))
            self.last_capture = now
            
            diff = len(self.history) > self.max_history
            if diff > 0:
                self.history = self.history[diff:]

    def _get_latest_frames(self, count:int = 3, raw: bool = False) -> Tuple[datetime, List[Union[bytes, str]]]:
        start = len(self.history) - count
        if start < 0:
            start = 0
        
        result = []
        min_ts = None
        for i in range(start, len(self.history)):
            ts, buff, width, height = self.history[i]
            if not min_ts or ts < min_ts:
                min_ts = ts
            result.append(rgb2base64jpeg(buff, width, height, raw = raw))
        
        return min_ts, result
    
    def _ask_to_latest_frames(self, count:int, args:dict = {}) -> Any:
        if not self.history:
            raise Exception("Failed to get frames")
        
        if self.use_llm:
            min_ts, frames = self._get_latest_frames(count=count)
            ts = min_ts.strftime("%Y-%m-%d %H:%M:%S")
            cmd = self._chat_completion(args, frames, ts)
        else:
            _, frames = self._get_latest_frames(count=1, raw=True)
            cmd = self._analyze_frame(frames[0])
        
        e = Event()
        rst = None
        failed = True
        def on_result(evt:Event, ten_env: TenEnv, result: CmdResult) -> None:
            nonlocal rst
            nonlocal failed
            try:
                if result.get_status_code() == StatusCode.OK:
                    rst = result.get_property_string("response")
                    # rst = json.loads(resp_str)
                    failed = False
                else:
                    logger.error(f"Failed to get ok result")
                    rst = result.get_property_string("reason")
            except:
                logger.exception(f"Failed to get response")
            finally:
                evt.set()

        self.ten_env.send_cmd(cmd, functools.partial(on_result, e))
        e.wait()
        if failed:
            raise Exception("Failed to get resp")
        else:
            return rst
        
    def _analyze_frame(self, frame: bytes) -> Cmd:
        cmd = Cmd.create("image_analyze")
        cmd.set_property_buf("image_data", frame)
        # TODO What to analyze
        return cmd
    
    def _chat_completion(self, args:dict, frames: List[str], ts: datetime) -> Cmd:
        if "query" not in args:
            raise Exception("Failed to get property")

        query = args["query"]
        contents = [{"type": "text", "text": f"This is the image captured within {self.frequency_ms} ms at {ts}. {query}"}]
        for f in frames:
            contents.append({"type": "image_url", "image_url": {"url": f}})

        messages = [{
            "role": "system",
            "content": "You need to describe all the object in this image first, and then focus on the user's query. Keep your response short and simple unless the query ask you to."
        },{
            "role": "user",
            "content": contents,
        }]

        # logger.debug(f"after prepare message: {messages}")
        # Send message
        cmd = Cmd.create("chat_completion")
        cmd.set_property_string("messages", json.dumps(messages))
        cmd.set_property_bool("stream", False) # this is function call, we need to have complete result
        # cmd.set_property_bool("json", True)
        return cmd
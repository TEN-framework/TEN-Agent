#!/usr/bin/env python3
#
# Agora Real Time Engagement
# Created by Cline in 2024-03.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
import asyncio
import json
import os
import time
import traceback
from enum import Enum
from typing import Optional, List, Dict, Any

import boto3
from ten import (
    AsyncTenEnv,
    Extension,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)
from ten_ai_base import BaseConfig, ChatMemory, EVENT_MEMORY_EXPIRED, EVENT_MEMORY_APPENDED
from ten_ai_base.llm import AsyncLLMBaseExtension
from dataclasses import dataclass

from .utils import (
    rgb2base64jpeg,
    filter_images,
    parse_sentence,
    get_greeting_text,
    merge_images
)

# Constants
MAX_IMAGE_COUNT = 20
ONE_BATCH_SEND_COUNT = 6
VIDEO_FRAME_INTERVAL = 0.5

# Command definitions
CMD_IN_FLUSH = "flush"
CMD_IN_ON_USER_JOINED = "on_user_joined"
CMD_IN_ON_USER_LEFT = "on_user_left"
CMD_OUT_FLUSH = "flush"

# Data property definitions
DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_IN_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT = "end_of_segment"

class Role(str, Enum):
    """Role definitions for chat participants."""
    User = "user"
    Assistant = "assistant"

@dataclass
class BedrockLLMConfig(BaseConfig):
    """Configuration for BedrockV2V extension."""
    region: str = "us-east-1"
    model_id: str = "us.amazon.nova-lite-v1:0"
    access_key_id: str = ""
    secret_access_key: str = ""
    language: str = "en-US"
    prompt: str = "You are an intelligent assistant with real-time interaction capabilities. You will be presented with a series of images that represent a video sequence. Describe what you see directly, as if you were observing the scene in real-time. Do not mention that you are looking at images or a video. Instead, narrate the scene and actions as they unfold. Engage in conversation with the user based on this visual input and their questions, maintaining a concise and clear."
    temperature: float = 0.7
    max_tokens: int = 256
    tokP: str = 0.5
    topK: str = 10
    max_duration: int = 30
    vendor: str = ""
    stream_id: int = 0
    dump: bool = False
    max_history: int = 10
    is_memory_enabled: bool = False
    is_enable_video: bool = False
    greeting: str = "Hello, I'm here to help you. How can I assist you today?"

    def build_ctx(self) -> dict:
        """Build context dictionary from configuration."""
        return {
            "language": self.language,
            "model": self.model_id,
        }

class BedrockLLMExtension(AsyncLLMBaseExtension):
    """Extension for handling video-to-video processing using AWS Bedrock."""
    
    def __init__(self, name: str):
        super().__init__(name)
        self.config: Optional[BedrockLLMConfig] = None
        self.stopped: bool = False
        self.memory: list = []
        self.users_count: int = 0
        self.bedrock_client = None
        self.image_buffers: list = []
        self.image_queue = asyncio.Queue()
        self.text_buffer: str = ""
        self.input_start_time: float = 0
        self.processing_times = []
        self.ten_env = None

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        """Initialize the extension."""
        await super().on_init(ten_env)
        ten_env.log_info("BedrockV2VExtension initialized")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        """Start the extension and set up required components."""
        await super().on_start(ten_env)
        ten_env.log_info("BedrockV2VExtension starting")
        
        try:
            self.config = await BedrockLLMConfig.create_async(ten_env=ten_env)
            ten_env.log_info(f"Configuration: {self.config}")
            
            if not self.config.access_key_id or not self.config.secret_access_key:
                ten_env.log_error("AWS credentials (access_key_id and secret_access_key) are required")
                return
            
            await self._setup_components(ten_env)
            
        except Exception as e:
            traceback.print_exc()
            ten_env.log_error(f"Failed to initialize: {e}")

    async def _setup_components(self, ten_env: AsyncTenEnv) -> None:
        """Set up extension components."""
        self.memory = []
        self.ctx = self.config.build_ctx()
        self.ten_env = ten_env
        
        self.loop = asyncio.get_event_loop()
        self.loop.create_task(self._on_video(ten_env))

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        """Stop the extension."""
        await super().on_stop(ten_env)
        ten_env.log_info("BedrockV2VExtension stopping")
        self.stopped = True

    async def on_data(self, ten_env: AsyncTenEnv, data) -> None:
        """Handle incoming data."""
        ten_env.log_info("on_data receive begin...")
        data_name = data.get_name()
        ten_env.log_info(f"on_data name {data_name}")

        try:
            is_final = data.get_property_bool(DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL)
            input_text = data.get_property_string(DATA_IN_TEXT_DATA_PROPERTY_TEXT)
            
            if not is_final:
                ten_env.log_info("ignore non-final input")
                return
                
            if not input_text:
                ten_env.log_info("ignore empty text")
                return

            ten_env.log_info(f"OnData input text: [{input_text}]")
            self.text_buffer = input_text
            await self._handle_input_truncation("is_final")
            
        except Exception as err:
            ten_env.log_info(f"Error processing data: {err}")

    async def on_video_frame(self, ten_env: AsyncTenEnv, video_frame) -> None:
        """Handle incoming video frames."""
        if not self.config.is_enable_video:
            return
        image_data = video_frame.get_buf()
        image_width = video_frame.get_width()
        image_height = video_frame.get_height()
        await self.image_queue.put([image_data, image_width, image_height])

    async def _on_video(self, ten_env: AsyncTenEnv):
        """Process video frames from the queue."""
        while True:
            try:
                [image_data, image_width, image_height] = await self.image_queue.get()

                #ten_env.log_info(f"image_width: {image_width}, image_height: {image_height}, image_size: {len(bytes(image_data)) / 1024 / 1024}MB")
                
                frame_buffer = rgb2base64jpeg(image_data, image_width, image_height)
                
                self.image_buffers.append(frame_buffer)
               
                #ten_env.log_info(f"Processed frame, width: {image_width}, height: {image_height}, frame_buffer_size: {len(frame_buffer) / 1024 / 1024}MB")
                
                while len(self.image_buffers) > MAX_IMAGE_COUNT:
                    self.image_buffers.pop(0)
                
                # Skip remaining frames for the interval
                while not self.image_queue.empty():
                    await self.image_queue.get()
                    
                await asyncio.sleep(VIDEO_FRAME_INTERVAL)
                
            except Exception as e:
                traceback.print_exc()
                ten_env.log_error(f"Error processing video frame: {e}")

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        """Handle incoming commands."""
        cmd_name = cmd.get_name()
        ten_env.log_info(f"Command received: {cmd_name}")
        
        try:
            if cmd_name == CMD_IN_FLUSH:
                await ten_env.send_cmd(Cmd.create(CMD_OUT_FLUSH))
            elif cmd_name == CMD_IN_ON_USER_JOINED:
                await self._handle_user_joined()
            elif cmd_name == CMD_IN_ON_USER_LEFT:
                self.users_count -= 1
            else:
                await super().on_cmd(ten_env, cmd)
                return
                
            cmd_result = CmdResult.create(StatusCode.OK)
            cmd_result.set_property_string("detail", "success")
            await ten_env.return_result(cmd_result, cmd)
            
        except Exception as e:
            traceback.print_exc()
            ten_env.log_error(f"Error handling command {cmd_name}: {e}")
            cmd_result = CmdResult.create(StatusCode.ERROR)
            cmd_result.set_property_string("detail", str(e))
            await ten_env.return_result(cmd_result, cmd)

    async def _handle_user_joined(self) -> None:
        """Handle user joined event."""
        self.users_count += 1
        if self.users_count == 1:
            await self._greeting()

    async def _handle_input_truncation(self, reason: str):
        """Handle input truncation events."""
        try:
            self.ten_env.log_info(f"Input truncated due to: {reason}")
            
            if self.text_buffer:
                await self._call_nova_model(self.text_buffer, self.image_buffers)
            
            self._reset_state()
            
        except Exception as e:
            traceback.print_exc()
            self.ten_env.log_error(f"Error handling input truncation: {e}")

    def _reset_state(self):
        """Reset internal state."""
        self.text_buffer = ""
        self.image_buffers = []
        self.input_start_time = 0

    async def _initialize_aws_clients(self):
        """Initialize AWS clients."""
        try:
            if not self.bedrock_client:
                self.bedrock_client = boto3.client('bedrock-runtime',
                    aws_access_key_id=self.config.access_key_id,
                    aws_secret_access_key=self.config.secret_access_key,
                    region_name=self.config.region
                )
        except Exception as e:
            traceback.print_exc()
            self.ten_env.log_error(f"Error initializing AWS clients: {e}")
            raise

    async def _greeting(self) -> None:
        """Send greeting message to the user."""
        if self.users_count == 1:
            text = self.config.greeting or get_greeting_text(self.config.language)
            self.ten_env.log_info(f"send greeting {text}")
            await self._send_text_data(text, True, Role.Assistant)

    async def _send_text_data(self, text: str, end_of_segment: bool, role: Role):
        """Send text data to the user."""
        try:
            d = Data.create("text_data")
            d.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, text)
            d.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT, end_of_segment)
            d.set_property_string("role", role)
            asyncio.create_task(self.ten_env.send_data(d))
        except Exception as e:
            self.ten_env.log_error(f"Error sending text data: {e}")

    async def _call_nova_model(self, input_text: str, image_buffers: List[bytes]) -> None:
        """Call Bedrock's Nova model with text and video input."""
        try:
            if not self.bedrock_client:
                await self._initialize_aws_clients()

            if not input_text:
                self.ten_env.log_info("Text input is empty")
                return

            contents = []
            
            # Process images
            if image_buffers:
                filtered_buffers = filter_images(image_buffers, ONE_BATCH_SEND_COUNT)
                for image_data in filtered_buffers:
                    contents.append({
                        "image": {
                            "format": 'jpeg',
                            "source": {
                                "bytes": image_data
                            }
                        }
                    })
            # Prepare memory
            while len(self.memory) > self.config.max_history:
                self.memory.pop(0)
            while len(self.memory) > 0 and self.memory[0]["role"] == "assistant":
                self.memory.pop(0)
            while len(self.memory) > 0 and self.memory[-1]["role"] == "user":
                self.memory.pop(-1)
            
            # Prepare request
            contents.append({"text": input_text})
            messages = []
            for m in self.memory:
                # Convert string content to list format if needed
                m_content = m["content"]
                if isinstance(m_content, str):
                    m_content = [{"text": m_content}]
                messages.append({
                    "role": m["role"],
                    "content": m_content
                })
            messages.append({
                "role": "user",
                "content": contents
            })

            inf_params = {
                "maxTokens": self.config.max_tokens,
                "topP": self.config.tokP,
                "temperature": self.config.temperature
            }
            
            additional_config = {
                "inferenceConfig": {
                    "topK": self.config.topK
                }
            }

            system = [{
                "text": self.config.prompt
            }]

            # Make API call
            start_time = time.time()
            response = self.bedrock_client.converse_stream(
                modelId=self.config.model_id,
                system=system,
                messages=messages,
                inferenceConfig=inf_params,
                additionalModelRequestFields=additional_config,
            )
            full_content = await self._process_stream_response(response, start_time)
            # async append memory
            async def async_append_memory():
                if not self.config.is_memory_enabled:
                    return
                image = merge_images(image_buffers)
                contents = []
                if image:
                    contents.append({
                        "image": {
                            "format": 'jpeg',
                            "source": {
                                "bytes": image
                            }
                        }
                    })
                contents.append({"text": input_text})
                self.memory.append({"role": Role.User, "content": contents})
                self.memory.append({"role": Role.Assistant, "content": [{"text": full_content}]})
            
            asyncio.create_task(async_append_memory())
        except Exception as e:
            traceback.print_exc()
            self.ten_env.log_error(f"Error calling Nova model: {e}")

        except Exception as e:
            self.ten_env.log_error(f"Error appending memory: {e}")

    async def _process_stream_response(self, response: Dict, start_time: float):
        """Process streaming response from Nova model."""
        sentence = ""
        full_content = ""
        first_sentence_sent = False

        for event in response.get('stream'):
            if "contentBlockDelta" in event:
                if "text" in event["contentBlockDelta"]["delta"]:
                    content = event["contentBlockDelta"]["delta"]["text"]
                    full_content += content
                    
                    while True:
                        sentence, content, sentence_is_final = parse_sentence(sentence, content)
                        if not sentence or not sentence_is_final:
                            break
                            
                        self.ten_env.log_info(f"Processing sentence: [{sentence}]")
                        await self._send_text_data(sentence, False, Role.Assistant)
                        
                        if not first_sentence_sent:
                            first_sentence_sent = True
                            self.ten_env.log_info(f"First sentence latency: {(time.time() - start_time)*1000}ms")
                            
                        sentence = ""

            elif any(key in event for key in ["internalServerException", "modelStreamErrorException", 
                                            "throttlingException", "validationException"]):
                self.ten_env.log_error(f"Stream error: {event}")
                break
                
            elif 'metadata' in event:
                if 'metrics' in event['metadata']:
                    self.ten_env.log_info(f"Nova model latency: {event['metadata']['metrics']['latencyMs']}ms")

        # Send final sentence
        await self._send_text_data(sentence, True, Role.Assistant)
        self.ten_env.log_info(f"Final sentence sent: [{sentence}]")
        # Update metrics
        self.processing_times.append(time.time() - start_time)
        return full_content

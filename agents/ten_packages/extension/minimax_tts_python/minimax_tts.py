import asyncio
from dataclasses import dataclass
import aiohttp
import json
from datetime import datetime
from typing import AsyncIterator

from ten.async_ten_env import AsyncTenEnv
from ten_ai_base.config import BaseConfig


@dataclass
class MinimaxTTSConfig(BaseConfig):
    api_key: str = ""
    model: str = "speech-01-turbo"
    voice_id: str = "male-qn-qingse"
    sample_rate: int = 32000
    url: str = "https://api.minimax.chat/v1/t2a_v2"
    group_id: str = ""
    request_timeout_seconds: int = 10


class MinimaxTTS:
    def __init__(self, config: MinimaxTTSConfig):
        self.config = config

    async def get(self, ten_env: AsyncTenEnv, text: str) -> AsyncIterator[bytes]:
        payload = json.dumps(
            {
                "model": self.config.model,
                "text": text,
                "stream": True,
                "voice_setting": {
                    "voice_id": self.config.voice_id,
                    "speed": 1.0,
                    "vol": 1.0,
                    "pitch": 0,
                },
                "pronunciation_dict": {"tone": []},
                "audio_setting": {
                    "sample_rate": self.config.sample_rate,
                    "format": "pcm",
                    "channel": 1,
                },
            }
        )

        url = f"{self.config.url}?GroupId={self.config.group_id}"
        headers = {
            "accept": "application/json, text/plain, */*",
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        start_time = datetime.now()
        ten_env.log_info(f"Start request, url: {self.config.url}, text: {text}")
        ttfb = None

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=headers, data=payload) as response:
                    trace_id = ""
                    alb_receive_time = ""

                    try:
                        trace_id = response.headers.get("Trace-Id")
                    except Exception:
                        ten_env.log_warn("get response, no Trace-Id")
                    try:
                        alb_receive_time = response.headers.get("alb_receive_time")
                    except Exception:
                        ten_env.log_warn("get response, no alb_receive_time")

                    ten_env.log_info(
                        f"get response trace-id: {trace_id}, alb_receive_time: {alb_receive_time}, cost_time {self._duration_in_ms_since(start_time)}ms"
                    )

                    if response.status != 200:
                        raise RuntimeError(
                            f"Request failed with status {response.status}"
                        )

                    buffer = b""
                    async for chunk in response.content.iter_chunked(
                        1024
                    ):  # Read in 1024 byte chunks
                        buffer += chunk

                        # Split the buffer into lines based on newline character
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)

                            # Process only lines that start with "data:"
                            if line.startswith(b"data:"):
                                try:
                                    json_data = json.loads(
                                        line[5:].decode("utf-8").strip()
                                    )

                                    # Check for the required keys in the JSON data
                                    if (
                                        "data" in json_data
                                        and "extra_info" not in json_data
                                    ):
                                        audio = json_data["data"].get("audio")
                                        if audio:
                                            decoded_hex = bytes.fromhex(audio)
                                            yield decoded_hex
                                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                                    # Handle malformed JSON or decoding errors
                                    ten_env.log_warn(f"Error decoding line: {e}")
                                    continue
                        if not ttfb:
                            ttfb = self._duration_in_ms_since(start_time)
                            ten_env.log_info(f"trace-id: {trace_id}, ttfb {ttfb}ms")
            except aiohttp.ClientError as e:
                ten_env.log_error(f"Client error occurred: {e}")
            except asyncio.TimeoutError:
                ten_env.log_error("Request timed out")
            finally:
                ten_env.log_info(
                    f"http loop done, cost_time {self._duration_in_ms_since(start_time)}ms"
                )

    def _duration_in_ms(self, start: datetime, end: datetime) -> int:
        return int((end - start).total_seconds() * 1000)

    def _duration_in_ms_since(self, start: datetime) -> int:
        return self._duration_in_ms(start, datetime.now())

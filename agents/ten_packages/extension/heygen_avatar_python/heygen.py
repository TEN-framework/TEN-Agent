#!/usr/bin/env python3

import os
import time
import argparse
import logging
import json
import traceback
import wave
import base64
import uuid
import asyncio
import threading
import requests
from datetime import datetime
import numpy as np
import websocket

from livekit import rtc

from ten import AsyncTenEnv, AudioFrame, AudioFrameDataFmt, VideoFrame
from ten_ai_base.types import TTSPcmOptions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HeyGenMinimal")


class HeyGenRecorder:
    def __init__(
        self,
        api_key,
        avatar_name,
        ten_env: AsyncTenEnv,
        video_queue: asyncio.Queue,
        audio_queue: asyncio.Queue[bytes],
    ):
        self.api_key = api_key
        self.avatar_name = avatar_name
        self.ten_env = ten_env

        self.session_id = None
        self.realtime_endpoint = None
        self.ws = None
        self.video_queue = video_queue
        self.audio_queue = audio_queue
        self.leftover_bytes = b""

        self.room = rtc.Room()

        # Timer to send agent.speak_end after 500 ms of no new agent.speak
        self.speak_end_timer = None

    def get_heygen_token(self):
        """Get a HeyGen token for streaming."""
        url = "https://api.heygen.com/v1/streaming.create_token"
        resp = requests.post(url, headers={"x-api-key": self.api_key})
        data = resp.json()

        if resp.status_code != 200 or data.get("error"):
            raise Exception(f"Failed to get HeyGen token: {data}")

        token = data["data"].get("token")
        if not token:
            raise Exception(f"No token in response: {data}")
        return token

    def create_streaming_session(self, token):
        """Create a new streaming session and get LiveKit creds (URL + token)."""
        url = "https://api.heygen.com/v1/streaming.new"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        payload = {
            "avatar_name": self.avatar_name,
            "quality": "high",
            "voice": {},
            "version": "v2",
            "video_encoding": "H264",
            "source": "sdk",
            "disable_idle_timeout": False,
        }

        resp = requests.post(url, headers=headers, json=payload)
        data = resp.json()
        if resp.status_code != 200 or data.get("code") != 100:
            raise Exception(f"Failed to create streaming session: {data}")

        session_data = data["data"]
        self.session_id = session_data["session_id"]
        self.realtime_endpoint = session_data.get("realtime_endpoint")
        self.leftover_bytes = b""

        return session_data["url"], session_data["access_token"]

    def start_streaming_session(self, token):
        """Tell HeyGen to begin the streaming session."""
        url = "https://api.heygen.com/v1/streaming.start"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        payload = {"session_id": self.session_id}
        resp = requests.post(url, headers=headers, json=payload)
        data = resp.json()
        if resp.status_code != 200 or data.get("code") != 100:
            raise Exception(f"Failed to start streaming session: {data}")

    def connect_to_websocket(self):
        """Open a WebSocket to send user audio to HeyGen."""
        if not self.realtime_endpoint:
            raise Exception("No realtime_endpoint in session data.")

        self.ten_env.log_info(f"Connecting to {self.realtime_endpoint}")
        self.ws = websocket.create_connection(self.realtime_endpoint, timeout=5)
        self.ten_env.log_info("WebSocket connected.")

        self.ws.settimeout(1.0)

        def read_thread():
            while True:
                try:
                    msg = self.ws.recv()
                    if not msg:
                        break
                except (websocket.WebSocketTimeoutException, OSError):
                    pass
                except Exception as e:
                    logger.warning(f"WebSocket read error: {e}")
                    break

        t = threading.Thread(target=read_thread, daemon=True)
        t.start()

    def _schedule_speak_end(self):
        """Schedule sending `agent.speak_end` 500ms from now, cancelling any previous timer."""
        if self.speak_end_timer is not None:
            self.speak_end_timer.cancel()

        def do_speak_end():
            try:
                end_evt_id = str(uuid.uuid4())
                self.ws.send(json.dumps({"type": "agent.speak_end", "event_id": end_evt_id}))
                self.ten_env.log_info("Sent agent.speak_end.")
            except Exception as e:
                logger.error(f"Error sending agent.speak_end: {e}")
            finally:
                self.speak_end_timer = None

        self.speak_end_timer = threading.Timer(0.5, do_speak_end)
        self.speak_end_timer.daemon = True
        self.speak_end_timer.start()

    async def send_audio(self, frame_buf: bytearray):
        """Send WAV audio downsampled from 44.1kHz to 24kHz in chunks to HeyGen.
        Uses naive decimation by discarding samples (nearest-neighbor approach).
        Then schedules sending agent.speak_end if there's no new audio for 500ms.
        """
        if not self.ws:
            logger.error("No WebSocket to send audio.")
            return

        try:
            # Assume frame_buf contains 44.1kHz PCM audio
            original_rate = 48000
            target_rate = 24000
            decimation_factor = original_rate / target_rate

            audio_data = np.frombuffer(frame_buf, dtype=np.int16)
            if len(audio_data) == 0:
                return

            indices = np.round(np.arange(0, len(audio_data), decimation_factor)).astype(int)
            indices = indices[indices < len(audio_data)]
            downsampled_audio = audio_data[indices]

            downsampled_frame_buf = downsampled_audio.tobytes()

            evt_id = str(uuid.uuid4())
            audio_b64 = base64.b64encode(downsampled_frame_buf).decode("utf-8")
            msg = {"type": "agent.speak", "audio": audio_b64, "event_id": evt_id}
            self.ws.send(json.dumps(msg))
            #self.ten_env.log_info("Sent agent.speak.")

            # Schedule agent.speak_end for 500ms from now
            self._schedule_speak_end()

        except Exception as e:
            logger.error(f"Error sending audio: {e}")

    async def record(self, livekit_url, livekit_token):
        """Connect to LiveKit, subscribe to audio/video."""

        @self.room.on("track_subscribed")
        def when_track_subscribed(track, pub, participant):
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                self.ten_env.log_info("Subscribed to audio track.")
                asyncio.create_task(
                    self.handle_audio(
                        rtc.AudioStream(track, sample_rate=16000, num_channels=1)
                    )
                )
            elif track.kind == rtc.TrackKind.KIND_VIDEO:
                self.ten_env.log_info("Subscribed to video track.")
                vs = rtc.VideoStream(track, format=rtc.VideoBufferType.I420)
                asyncio.create_task(self.handle_video(vs))

        await self.room.connect(livekit_url, livekit_token)
        self.ten_env.log_info("Connected to LiveKit. Starting track subscriptions...")

    async def disconnect(self):
        await self.room.disconnect()

    def _dump_audio_if_need(self, buf: bytearray) -> None:
        with open("{}_{}.pcm".format("heygen", self.session_id), "ab") as dump_file:
            dump_file.write(buf)

    async def handle_audio(self, audio_stream: rtc.AudioStream):
        """Append raw int16 samples to .pcm file."""
        async for frame_evt in audio_stream:
            samples = np.array(frame_evt.frame.data, dtype=np.int16)
            bytes_data = samples.tobytes()
            await self.send_audio_out(
                self.ten_env,
                bytes_data,
                sample_rate=16000,
                bytes_per_sample=2,
                number_of_channels=1,
            )

    async def handle_video(self, video_stream: rtc.VideoStream):
        """Write each I420 frame to a .yuv file with timestamp."""
        async for frame_evt in video_stream:
            buffer = frame_evt.frame
            frame = VideoFrame.create("video_frame")
            frame.set_width(buffer.width)
            frame.set_height(buffer.height)
            frame.alloc_buf(len(buffer.data))
            frame.set_pixel_fmt(6)
            buff = frame.lock_buf()
            buff[:] = buffer.data
            frame.unlock_buf(buff)
            await self.ten_env.send_video_frame(frame)

    async def send_audio_out(
        self, ten_env: AsyncTenEnv, audio_data: bytes, **args: TTSPcmOptions
    ) -> None:
        """Send audio frames along to ten_env."""
        sample_rate = args.get("sample_rate", 16000)
        bytes_per_sample = args.get("bytes_per_sample", 2)
        number_of_channels = args.get("number_of_channels", 1)
        try:
            combined_data = self.leftover_bytes + audio_data

            frame_size = bytes_per_sample * number_of_channels
            if len(combined_data) % frame_size != 0:
                valid_length = len(combined_data) - (len(combined_data) % frame_size)
                self.leftover_bytes = combined_data[valid_length:]
                combined_data = combined_data[:valid_length]
            else:
                self.leftover_bytes = b""

            if combined_data:
                f = AudioFrame.create("pcm_frame")
                f.set_sample_rate(sample_rate)
                f.set_bytes_per_sample(bytes_per_sample)
                f.set_number_of_channels(number_of_channels)
                f.set_data_fmt(AudioFrameDataFmt.INTERLEAVE)
                f.set_samples_per_channel(len(combined_data) // frame_size)
                f.alloc_buf(len(combined_data))
                buff = f.lock_buf()
                buff[:] = combined_data
                f.unlock_buf(buff)
                await ten_env.send_audio_frame(f)
        except Exception as e:
            ten_env.log_error(f"error send audio frame, {traceback.format_exc()}")

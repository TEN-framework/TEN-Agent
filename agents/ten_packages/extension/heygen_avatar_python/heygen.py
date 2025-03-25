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
    # def __init__(self, api_key, avatar_name, output_dir, wav_file):
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
        # self.output_dir = output_dir
        # self.wav_file = wav_file
        # os.makedirs(self.output_dir, exist_ok=True)

        # Will be filled in once we create a streaming session
        self.session_id = None
        self.realtime_endpoint = None
        self.ws = None
        self.video_queue = video_queue
        self.audio_queue = audio_queue
        self.leftover_bytes = b""

        # We'll store recorded raw audio in a single .pcm file
        # ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        # self.pcm_path = os.path.join(self.output_dir, f"{avatar_name}_{ts}.pcm")

        # Keep a handle to the LiveKit Room so we can disconnect on exit
        self.room = rtc.Room()

    def get_heygen_token(self):
        """Get a HeyGen token for streaming."""
        url = "https://api.heygen.com/v1/streaming.create_token"
        resp = requests.post(url, headers={"x-api-key": self.api_key})
        data = resp.json()

        # Only fail if HTTP != 200 or data["error"] is a non-null value
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
        """Open a WebSocket to send user WAV audio to HeyGen."""
        if not self.realtime_endpoint:
            raise Exception("No realtime_endpoint in session data.")

        self.ten_env.log_info(f"Connecting to {self.realtime_endpoint}")
        self.ws = websocket.create_connection(self.realtime_endpoint, timeout=5)
        self.ten_env.log_info("WebSocket connected.")

        # Continuously read in a background thread so we don't fill up WS buffers
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

    async def send_audio(self, frame_buf: bytearray):
        #     """Send WAV audio (already correct format) in chunks to HeyGen."""
        if not self.ws:
            logger.error("No WebSocket to send audio.")
            return

        # self.ten_env.log_info(f"Sending audio from {self.wav_file}")
        #     try:
        #         with wave.open(self.wav_file, 'rb') as wf:
        #             sr = wf.getframerate()
        #             ch = wf.getnchannels()
        #             sw = wf.getsampwidth()
        #             chunk_samples = int(sr * 0.5)
        #             chunk_bytes = chunk_samples * ch * sw
        #             raw_audio = wf.readframes(wf.getnframes())

        try:
            # offset = 0
            # while offset < len(frame_buf):
            #     chunk = frame_buf[offset : offset + chunk_bytes]
            #     offset += chunk_bytes
            # self._dump_audio_if_need(frame_buf)
            evt_id = str(uuid.uuid4())
            audio_b64 = base64.b64encode(frame_buf).decode("utf-8")
            msg = {"type": "agent.speak", "audio": audio_b64, "event_id": evt_id}
            self.ws.send(json.dumps(msg))

            # After sending all chunks, signal speak_end
            # end_evt_id = str(uuid.uuid4())
            # self.ws.send(json.dumps({"type": "agent.speak_end", "event_id": end_evt_id}))
            # self.ten_env.log_info("Sent agent.speak_end.")
        except Exception as e:
            logger.error(f"Error sending audio: {e}")

    async def record(self, livekit_url, livekit_token):
        """Connect to LiveKit, subscribe to audio/video, and record until Ctrl-C."""

        # Define track subscription callbacks
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
                # Request I420
                vs = rtc.VideoStream(track, format=rtc.VideoBufferType.I420)
                asyncio.create_task(self.handle_video(vs))

        # Connect to LiveKit
        await self.room.connect(livekit_url, livekit_token)
        self.ten_env.log_info("Connected to LiveKit. Starting track subscriptions...")

        # Send the user's WAV audio in a separate thread
        # audio_thread = threading.Thread(target=self.send_audio, daemon=True)
        # audio_thread.start()

        # # Run forever, or until KeyboardInterrupt
        # self.ten_env.log_info("Recording indefinitely; press Ctrl-C to stop.")
        # try:
        #     while True:
        #         await asyncio.sleep(1)
        # except asyncio.CancelledError:
        #     # If we ever explicitly cancel, just exit
        #     pass
        # except KeyboardInterrupt:
        #     self.ten_env.log_info("KeyboardInterrupt received. Exiting...")
        # finally:
        #     # Disconnect from LiveKit
        #     await self.room.disconnect()
        #     self.ten_env.log_info("Disconnected from LiveKit.")

    async def disconnect(self):
        await self.room.disconnect()

    def _dump_audio_if_need(self, buf: bytearray) -> None:
        with open("{}_{}.pcm".format("heygen", self.session_id), "ab") as dump_file:
            dump_file.write(buf)

    async def handle_audio(self, audio_stream: rtc.AudioStream):
        """Append raw int16 samples to .pcm file."""
        async for frame_evt in audio_stream:
            samples = np.array(frame_evt.frame.data, dtype=np.int16)
            # self.ten_env.log_info(f"audio frame audio num_channels  {frame_evt.frame.num_channels} sample_rate {frame_evt.frame.sample_rate}")
            bytes = samples.tobytes()
            # self._dump_audio_if_need(bytes)
            await self.send_audio_out(
                self.ten_env,
                bytes,
                sample_rate=16000,
                bytes_per_sample=2,
                number_of_channels=1,
            )
        # with open(self.pcm_path, 'ab') as pcm:
        #     async for frame_evt in audio_stream:
        #         samples = np.array(frame_evt.frame.data, dtype=np.int16)
        #         #self.ten_env.log_info(f"audio frame audio num_channels  {frame_evt.frame.num_channels} sample_rate {frame_evt.frame.sample_rate}")
        #         pcm.write(samples.tobytes())

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
        # async for frame_evt in video_stream:
        #     buffer = frame_evt.frame
        #     ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        #     yuv_path = os.path.join(self.output_dir, f"frame_{ts}.yuv")
        #     with open(yuv_path, 'wb') as f:
        #         f.write(buffer.data)

    async def send_audio_out(
        self, ten_env: AsyncTenEnv, audio_data: bytes, **args: TTSPcmOptions
    ) -> None:
        """End sending audio out."""
        sample_rate = args.get("sample_rate", 16000)
        bytes_per_sample = args.get("bytes_per_sample", 2)
        number_of_channels = args.get("number_of_channels", 1)
        try:
            # Combine leftover bytes with new audio data
            combined_data = self.leftover_bytes + audio_data

            # Check if combined_data length is odd
            if len(combined_data) % (bytes_per_sample * number_of_channels) != 0:
                # Save the last incomplete frame
                valid_length = len(combined_data) - (
                    len(combined_data) % (bytes_per_sample * number_of_channels)
                )
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
                f.set_samples_per_channel(
                    len(combined_data) // (bytes_per_sample * number_of_channels)
                )
                f.alloc_buf(len(combined_data))
                buff = f.lock_buf()
                buff[:] = combined_data
                f.unlock_buf(buff)
                await ten_env.send_audio_frame(f)
        except Exception as e:
            ten_env.log_error(f"error send audio frame, {traceback.format_exc()}")


# async def main():
#     parser = argparse.ArgumentParser()
#     parser.add_argument("--api-key", required=True)
#     parser.add_argument("--avatar-name", default="Wayne_20240711")
#     parser.add_argument("--output-dir", default="recordings")
#     parser.add_argument("--wav-file", default="input.wav")
#     args = parser.parse_args()

#     recorder = HeyGenRecorder(
#         args.api_key,
#         args.avatar_name,
#         args.output_dir,
#         args.wav_file
#     )

#     # 1) Get the HeyGen token
#     token = recorder.get_heygen_token()
#     # 2) Create a streaming session => get LiveKit URL/token
#     lk_url, lk_token = recorder.create_streaming_session(token)
#     # 3) Start session
#     recorder.start_streaming_session(token)
#     # 4) Connect to WebSocket to feed audio
#     recorder.connect_to_websocket()
#     # 5) Enter indefinite recording loop
#     await recorder.record(lk_url, lk_token)


# if __name__ == "__main__":
#     # This is the modern approach: no DeprecationWarning, no manual loop creation.
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         self.ten_env.log_info("Stopped by user (Ctrl-C).")

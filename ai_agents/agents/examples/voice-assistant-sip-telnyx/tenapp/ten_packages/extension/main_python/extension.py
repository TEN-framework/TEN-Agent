import asyncio
import json
import time
import base64
import os
import audioop
import aiohttp
from datetime import datetime
from typing import Literal, Dict, Any, Optional
from .server import TelnyxCallServer

from .agent.decorators import agent_event_handler
from ten_runtime import (
    AsyncExtension,
    AsyncTenEnv,
    Cmd,
    Data,
    AudioFrame,
    Loc,
)
from ten_runtime.audio_frame import AudioFrameDataFmt

from .agent.agent import Agent
from .agent.events import (
    ASRResultEvent,
    LLMResponseEvent,
    ToolRegisterEvent,
    UserJoinedEvent,
    UserLeftEvent,
)
from .helper import _send_cmd, _send_data, parse_sentences
from .config import TelnyxConfig

import uuid


class TelnyxControlExtension(AsyncExtension):
    """
    The entry point of the agent module.
    Consumes semantic AgentEvents from the Agent class and drives the runtime behavior.
    """

    def __init__(self, name: str):
        super().__init__(name)
        self.ten_env: AsyncTenEnv = None
        self.agent: Agent = None
        self.config: TelnyxConfig = None

        # WebSocket and audio processing
        self.audio_dump_files: Dict[str, str] = {}  # call_id -> filepath

        # Server management
        self.server_task: Optional[asyncio.Task] = None
        self.server_instance: Optional[TelnyxCallServer] = None
        self.audio_dump_dir: str = ""

        self.stopped: bool = False
        self.sentence_fragment: str = ""
        self.turn_id: int = 0
        self.session_id: str = "0"

    def _current_metadata(self) -> dict:
        return {"session_id": self.session_id, "turn_id": self.turn_id}

    async def on_init(self, ten_env: AsyncTenEnv):
        self.ten_env = ten_env

        # Load config from runtime properties
        config_json, _ = await ten_env.get_property_to_json(None)

        self.ten_env.log_info(f"Config: {config_json}")

        self.config = TelnyxConfig.model_validate_json(config_json)

        self.ten_env.log_info(f"Config: {self.config}")

        self.agent = Agent(ten_env)

        # Now auto-register decorated methods
        for attr_name in dir(self):
            fn = getattr(self, attr_name)
            event_type = getattr(fn, "_agent_event_type", None)
            if event_type:
                self.agent.on(event_type, fn)

        # Start the Telnyx call server
        await self._start_server()

    async def _start_server(self):
        """Start the Telnyx call server in the same process"""
        try:
            # Create server instance with config and ten_env
            self.server_instance = TelnyxCallServer(self.config, self.ten_env)

            # Set extension instance reference for audio forwarding
            self.server_instance.extension_instance = self

            # Start the server as a background task using configured port
            self.server_task = asyncio.create_task(
                self.server_instance.start_server(
                    port=self.config.telnyx_server_port
                )
            )

            self.ten_env.log_info(
                f"Started Telnyx call server on port {self.config.telnyx_server_port} (HTTP + WebSocket)"
            )

            # Wait a moment for the server to start
            await asyncio.sleep(1)

            self.ten_env.log_info("Telnyx call server started successfully")

        except Exception as e:
            self.ten_env.log_error(f"Failed to start server: {str(e)}")
            raise

    async def _stop_server(self):
        """Stop the Telnyx call server"""
        try:
            if self.server_task and not self.server_task.done():
                self.ten_env.log_info("Stopping Telnyx call server")

                # Cancel the server task
                self.server_task.cancel()

                # Wait for task to complete
                try:
                    await asyncio.wait_for(self.server_task, timeout=5.0)
                except asyncio.TimeoutError:
                    self.ten_env.log_warn("Server task didn't stop gracefully")
                except asyncio.CancelledError:
                    pass  # Expected when cancelling

                self.ten_env.log_info("Telnyx call server stopped successfully")

            # Cleanup server instance
            if self.server_instance:
                self.server_instance.cleanup()
                self.server_instance = None

            self.server_task = None

        except Exception as e:
            self.ten_env.log_error(f"Error stopping server: {str(e)}")

    async def _end_call_and_cleanup(self, call_id: str):
        """End a call and cleanup resources"""
        try:
            # First, try to end the call via API
            if call_id in self.server_instance.active_call_sessions:
                self.ten_env.log_info(f"Ending call {call_id} via API")

                # Make API call to end the call
                async with aiohttp.ClientSession() as session:
                    async with session.delete(
                        f"http://localhost:{self.config.telnyx_server_port}/api/call/{call_id}"
                    ) as response:
                        if response.status == 200:
                            self.ten_env.log_info(
                                f"Call {call_id} ended successfully"
                            )
                        else:
                            self.ten_env.log_warn(
                                f"Failed to end call {call_id} via API: {response.status}"
                            )

            # Cleanup local resources
            if call_id in self.server_instance.active_call_sessions:
                del self.server_instance.active_call_sessions[call_id]

            if call_id in self.audio_dump_files:
                # Clean up audio dump file
                try:
                    os.remove(self.audio_dump_files[call_id])
                    del self.audio_dump_files[call_id]
                except Exception as e:
                    self.ten_env.log_warn(
                        f"Failed to cleanup audio file for {call_id}: {str(e)}"
                    )

        except Exception as e:
            self.ten_env.log_error(
                f"Error during call cleanup for {call_id}: {str(e)}"
            )

    # === Register handlers with decorators ===
    @agent_event_handler(ToolRegisterEvent)
    async def _on_tool_register(self, event: ToolRegisterEvent):
        await self.agent.register_llm_tool(event.tool, event.source)

    @agent_event_handler(ASRResultEvent)
    async def _on_asr_result(self, event: ASRResultEvent):
        self.ten_env.log_info(
            f"[TelnyxControlExtension] ASR Result: {event.text}"
        )
        self.session_id = event.metadata.get("session_id", "100")
        stream_id = int(self.session_id)
        if not event.text:
            return
        if event.final or len(event.text) > 2:
            await self._interrupt()
        if event.final:
            self.turn_id += 1
            await self.agent.queue_llm_input(event.text)
        await self._send_transcript("user", event.text, event.final, stream_id)

    @agent_event_handler(LLMResponseEvent)
    async def _on_llm_response(self, event: LLMResponseEvent):
        if not event.is_final and event.type == "message":
            sentences, self.sentence_fragment = parse_sentences(
                self.sentence_fragment, event.delta
            )
            for s in sentences:
                await self._send_to_tts(s, False)

        if event.is_final and event.type == "message":
            remaining_text = self.sentence_fragment or ""
            self.sentence_fragment = ""
            await self._send_to_tts(remaining_text, True)

        await self._send_transcript(
            "assistant",
            event.text,
            event.is_final,
            100,
            data_type=("reasoning" if event.type == "reasoning" else "text"),
        )

    async def on_start(self, ten_env: AsyncTenEnv):
        ten_env.log_info("[TelnyxControlExtension] on_start")

        # Initialize WebSocket and audio processing
        if self.config:
            self._setup_audio_dump_directory()

            # WebSocket server is now handled by the main server in server.py
            ten_env.log_info(
                "WebSocket server is integrated with the main HTTP server"
            )

    async def on_stop(self, ten_env: AsyncTenEnv):
        ten_env.log_info("[TelnyxControlExtension] on_stop")
        self.stopped = True

        # End all active calls and cleanup
        for call_id in list(self.server_instance.active_call_sessions.keys()):
            await self._end_call_and_cleanup(call_id)

        # Stop the server
        await self._stop_server()

        await self.agent.stop()

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd):
        await self.agent.on_cmd(cmd)

    async def on_data(self, ten_env: AsyncTenEnv, data: Data):
        await self.agent.on_data(data)

    async def on_audio_frame(
        self, ten_env: AsyncTenEnv, audio_frame: AudioFrame
    ) -> None:
        """Handle outgoing audio frames from TEN framework"""
        try:
            if audio_frame.get_name() == "pcm_frame":
                audio_data = audio_frame.get_buf()
                # Send audio to all active Telnyx calls
                for call_id in self.server_instance.active_call_sessions.keys():
                    await self.send_audio_to_telnyx(audio_data, call_id)
        except Exception as e:
            ten_env.log_error(f"Failed to handle audio frame: {e}")

    # === helpers ===
    async def _send_transcript(
        self,
        role: str,
        text: str,
        final: bool,
        stream_id: int,
        data_type: Literal["text", "reasoning"] = "text",
    ):
        """
        Sends the transcript (ASR or LLM output) to the message collector.
        """
        if data_type == "text":
            await _send_data(
                self.ten_env,
                "message",
                "message_collector",
                {
                    "data_type": "transcribe",
                    "role": role,
                    "text": text,
                    "text_ts": int(time.time() * 1000),
                    "is_final": final,
                    "stream_id": stream_id,
                },
            )
        elif data_type == "reasoning":
            await _send_data(
                self.ten_env,
                "message",
                "message_collector",
                {
                    "data_type": "raw",
                    "role": role,
                    "text": json.dumps(
                        {
                            "type": "reasoning",
                            "data": {
                                "text": text,
                            },
                        }
                    ),
                    "text_ts": int(time.time() * 1000),
                    "is_final": final,
                    "stream_id": stream_id,
                },
            )
        self.ten_env.log_info(
            f"[TelnyxControlExtension] Sent transcript: {role}, final={final}, text={text}"
        )

    async def _send_to_tts(self, text: str, is_final: bool):
        """
        Sends a sentence to the TTS system.
        """
        request_id = f"tts-request-{self.turn_id}"
        await _send_data(
            self.ten_env,
            "tts_text_input",
            "tts",
            {
                "request_id": request_id,
                "text": text,
                "text_input_end": is_final,
                "metadata": self._current_metadata(),
            },
        )
        self.ten_env.log_info(
            f"[TelnyxControlExtension] Sent to TTS: is_final={is_final}, text={text}"
        )

    async def _interrupt(self):
        """
        Interrupts ongoing LLM and TTS generation. Typically called when user speech is detected.
        """
        self.sentence_fragment = ""
        await self.agent.flush_llm()
        await _send_data(
            self.ten_env, "tts_flush", "tts", {"flush_id": str(uuid.uuid4())}
        )
        await _send_cmd(self.ten_env, "flush", "agora_rtc")
        self.ten_env.log_info("[TelnyxControlExtension] Interrupt signal sent")

    # WebSocket and audio processing methods
    def _setup_audio_dump_directory(self):
        """Setup directory for audio dump files"""
        # Use configured directory or default
        self.audio_dump_dir = getattr(
            self.config, "audio_dump_directory", "/tmp/telnyx_audio_dumps"
        )
        os.makedirs(self.audio_dump_dir, exist_ok=True)
        if self.ten_env:
            self.ten_env.log_info(
                f"Audio dump directory created: {self.audio_dump_dir}"
            )

    async def _forward_audio_to_ten(self, audio_payload: str, call_id: str):
        """Forward audio data to TEN framework and dump PCM audio"""
        try:
            if not self.ten_env:
                return

            # Decode base64 audio data (this is μ-law encoded)
            mulaw_data = base64.b64decode(audio_payload)

            # Convert μ-law to PCM
            pcm_data = audioop.ulaw2lin(
                mulaw_data, 2
            )  # 2 bytes per sample (16-bit)

            # Create AudioFrame and send to TEN framework
            audio_frame = AudioFrame.create("pcm_frame")
            audio_frame.alloc_buf(len(pcm_data))
            buf = audio_frame.lock_buf()
            buf[:] = pcm_data
            audio_frame.unlock_buf(buf)
            audio_frame.set_sample_rate(8000)  # Telnyx's fixed sample rate
            audio_frame.set_number_of_channels(1)
            audio_frame.set_bytes_per_sample(2)
            audio_frame.set_data_fmt(AudioFrameDataFmt.INTERLEAVE)
            audio_frame.set_samples_per_channel(len(pcm_data) // (2 * 1))
            audio_frame.set_property_int("stream_id", 54321)
            audio_frame.set_dests(
                [
                    Loc(
                        app_uri="",
                        graph_id="",
                        extension_name="streamid_adapter",
                    )
                ]
            )

            await self.ten_env.send_audio_frame(audio_frame)

        except Exception as e:
            if self.ten_env:
                self.ten_env.log_error(f"Failed to forward audio to TEN: {e}")

    def _init_audio_dump_file(self, call_id: str):
        """Initialize audio dump file for a call"""
        try:
            if call_id in self.audio_dump_files:
                return  # File already initialized

            # Create filename with timestamp and call_id
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"telnyx_audio_{call_id}_{timestamp}.pcm"
            filepath = os.path.join(self.audio_dump_dir, filename)

            # Create empty file to initialize
            with open(filepath, "wb") as f:
                pass  # Create empty file

            self.audio_dump_files[call_id] = filepath

            if self.ten_env:
                self.ten_env.log_info(
                    f"Initialized audio dump file: {filepath}"
                )

        except Exception as e:
            if self.ten_env:
                self.ten_env.log_error(
                    f"Failed to initialize audio dump file: {e}"
                )

    async def _dump_pcm_audio(self, audio_data: bytes, call_id: str):
        """Dump PCM audio data to file"""
        try:
            # Initialize file if not exists
            if call_id not in self.audio_dump_files:
                self._init_audio_dump_file(call_id)

            # Get filepath for this call
            filepath = self.audio_dump_files.get(call_id)
            if not filepath:
                return

            # Write PCM audio data to file
            with open(
                filepath, "ab"
            ) as f:  # 'ab' mode for appending binary data
                f.write(audio_data)

            if self.ten_env:
                self.ten_env.log_info(
                    f"Dumped {len(audio_data)} bytes of PCM audio (converted from μ-law) to {filepath}"
                )

        except Exception as e:
            if self.ten_env:
                self.ten_env.log_error(f"Failed to dump PCM audio: {e}")

    def _downsample_audio(
        self, audio_data: bytes, source_rate: int, target_rate: int
    ) -> bytes:
        """Downsample audio data from source rate to target rate"""
        try:
            if source_rate == target_rate:
                return audio_data

            # Convert bytearray to bytes if needed
            if isinstance(audio_data, bytearray):
                audio_data = bytes(audio_data)

            # For 16000 Hz to 8000 Hz, use simple decimation (take every 2nd sample)
            if source_rate == 16000 and target_rate == 8000:
                # Simple decimation: take every 2nd sample (16-bit = 2 bytes per sample)
                decimated_audio = bytearray()
                for i in range(
                    0, len(audio_data), 4
                ):  # Skip every 2nd sample (4 bytes = 2 samples)
                    if i + 1 < len(audio_data):
                        decimated_audio.extend(
                            audio_data[i : i + 2]
                        )  # Take first sample (2 bytes)

                return bytes(decimated_audio)

            # For other conversions, use audioop.ratecv
            import math

            # Calculate the conversion ratio
            gcd_rate = math.gcd(source_rate, target_rate)
            old_rate = source_rate // gcd_rate
            new_rate = target_rate // gcd_rate

            # Convert audio using ratecv
            converted_audio, _ = audioop.ratecv(
                audio_data, 2, 1, old_rate, new_rate, None, None
            )

            return converted_audio

        except Exception as e:
            if self.ten_env:
                self.ten_env.log_error(f"Failed to downsample audio: {e}")
            return audio_data  # Return original data if conversion fails

    async def send_audio_to_telnyx(self, audio_data: bytes, call_id: str):
        """Send audio data to Telnyx via WebSocket"""
        try:
            if call_id not in self.server_instance.active_call_sessions:
                return

            websocket = self.server_instance.active_call_sessions[call_id].get(
                "websocket"
            )
            if not websocket:
                return

            # Downsample audio from 16000 Hz to 8000 Hz for Telnyx
            source_rate = 16000  # TTS generated audio sample rate
            target_rate = 8000  # Telnyx required sample rate
            downsampled_audio = self._downsample_audio(
                audio_data, source_rate, target_rate
            )

            # Convert PCM to μ-law for Telnyx
            mulaw_data = audioop.lin2ulaw(
                downsampled_audio, 2
            )  # 2 bytes per sample (16-bit)

            # Encode μ-law audio data to base64
            audio_base64 = base64.b64encode(mulaw_data).decode("utf-8")

            message = {
                "event": "media",
                "media": {"payload": audio_base64},
            }

            await websocket.send_text(json.dumps(message))

        except Exception as e:
            if self.ten_env:
                self.ten_env.log_error(f"Failed to send audio to Telnyx: {e}")

    async def _cleanup_call_after_delay(self, call_id: str, delay_seconds: int):
        """Clean up call session after a delay"""
        await asyncio.sleep(delay_seconds)

        # Use the new cleanup method
        await self._end_call_and_cleanup(call_id)

    async def on_websocket_connected(self, call_id: str):
        """Called when websocket connection is established for a call"""
        try:
            self.ten_env.log_info(
                f"WebSocket connected for call {call_id}, sending greeting TTS"
            )

            # Send greeting TTS using the configured greeting message
            greeting_text = self.config.greeting
            await self._send_to_tts(greeting_text, True)

            self.ten_env.log_info(
                f"Greeting TTS sent for call {call_id}: {greeting_text}"
            )
        except Exception as e:
            self.ten_env.log_error(f"Failed to send greeting TTS: {str(e)}")

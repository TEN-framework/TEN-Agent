"""
WebSocket Server Manager for receiving audio data
"""

import asyncio
import json
import base64
from typing import Awaitable, Callable, Optional, Any
from dataclasses import dataclass
import websockets
from ten_runtime.async_ten_env import AsyncTenEnv


@dataclass
class AudioData:
    """Container for audio data with metadata"""

    pcm_data: bytes
    client_id: str
    metadata: dict[str, Any]


class WebSocketServerManager:
    """Manages WebSocket server and client connections"""

    def __init__(
        self,
        host: str,
        port: int,
        ten_env: AsyncTenEnv,
        on_audio_callback: Optional[
            Callable[[AudioData], Awaitable[None]]
        ] = None,
        on_cmd_callback: Optional[
            Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]
        ] = None,
    ):
        """
        Initialize WebSocket server manager

        Args:
            host: Server host address
            port: Server port
            ten_env: TEN environment for logging
            on_audio_callback: Callback when audio data is received
            on_cmd_callback: Callback for commands routed through the TEN graph
        """
        self.host = host
        self.port = port
        self.ten_env = ten_env
        self.on_audio_callback = on_audio_callback
        self.on_cmd_callback = on_cmd_callback

        self.server = None
        self.current_client: Optional[Any] = None
        self.running = False
        self._server_task: Optional[asyncio.Task] = None
        # Protects access to current_client during accept/cleanup
        self._client_lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the WebSocket server"""
        if self.running:
            self.ten_env.log_warn("WebSocket server already running")
            return

        self.running = True
        try:
            self.server = await websockets.serve(
                self._handle_client, self.host, self.port
            )
            self.ten_env.log_info(
                f"WebSocket server started on ws://{self.host}:{self.port}"
            )
        except Exception as e:
            self.ten_env.log_error(f"Failed to start WebSocket server: {e}")
            self.running = False
            raise

    async def stop(self) -> None:
        """Stop the WebSocket server and close all connections"""
        if not self.running:
            return

        self.running = False
        self.ten_env.log_info("Stopping WebSocket server...")

        # Close client connection
        if self.current_client:
            await self._close_client(self.current_client)
            self.current_client = None

        # Close server
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        self.ten_env.log_info("WebSocket server stopped")

    async def _handle_client(self, websocket: Any) -> None:
        """
        Handle a single WebSocket client connection

        Args:
            websocket: WebSocket connection
        """
        client_id = (
            f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        )

        # Reject connection if one already exists (protect with lock)
        reject = False
        async with self._client_lock:
            if self.current_client is not None:
                reject = True
            else:
                self.current_client = websocket

        if reject:
            self.ten_env.log_warn(
                f"Rejecting new connection from {client_id} - only one connection allowed"
            )
            await self._send_error(
                websocket,
                "Connection rejected: server only accepts one connection at a time",
            )
            await websocket.close(1008, "Only one connection allowed")
            return
        self.ten_env.log_info(f"Client connected: {client_id}")

        try:
            async for message in websocket:
                if not self.running:
                    break

                await self._process_message(message, websocket, client_id)

        except websockets.exceptions.ConnectionClosed:
            self.ten_env.log_info(f"Client disconnected: {client_id}")
        except Exception as e:
            self.ten_env.log_error(f"Error handling client {client_id}: {e}")
            await self._send_error(websocket, f"Server error: {str(e)}")
        finally:
            async with self._client_lock:
                if self.current_client == websocket:
                    self.current_client = None
            self.ten_env.log_info(f"Client removed: {client_id}")

    async def _process_message(
        self, message: str, websocket: Any, client_id: str
    ) -> None:
        """
        Process incoming message from client

        Args:
            message: Raw message string
            websocket: Client WebSocket connection
            client_id: Client identifier
        """
        try:
            # Parse JSON message
            data = json.loads(message)

            if not isinstance(data, dict):
                raise ValueError("message must be a JSON object")

            if data.get("type") == "cmd":
                name = data.get("name")
                properties = data.get("data", {})
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("command name must be a non-empty string")
                if not isinstance(properties, dict):
                    raise ValueError("command data must be a JSON object")
                if self.on_cmd_callback is None:
                    raise ValueError("commands are not enabled")
                result = await self.on_cmd_callback(name, properties)
                await websocket.send(
                    json.dumps(
                        {
                            "type": "cmd_result",
                            "name": name,
                            "request_id": data.get("request_id"),
                            **result,
                        }
                    )
                )
                return

            # Validate message format
            if "audio" not in data:
                await self._send_error(
                    websocket,
                    'Missing required field: "audio" with base64 data',
                )
                return

            # Decode base64 audio
            try:
                audio_base64 = data["audio"]
                if not isinstance(audio_base64, str):
                    raise ValueError("audio must be a base64 string")
                pcm_data = base64.b64decode(audio_base64, validate=True)
            except Exception as e:
                await self._send_error(
                    websocket, f"Invalid base64 audio data: {e}"
                )
                return

            # Extract metadata
            metadata = data.get("metadata", {})
            if not isinstance(metadata, dict):
                raise ValueError("metadata must be a JSON object")
            metadata = dict(metadata)
            metadata["client_id"] = client_id

            # Create audio data container
            audio_data = AudioData(
                pcm_data=pcm_data, client_id=client_id, metadata=metadata
            )

            # Call callback to process audio
            if self.on_audio_callback:
                try:
                    await self.on_audio_callback(audio_data)
                except Exception as e:
                    self.ten_env.log_error(f"Error in audio callback: {e}")
                    await self._send_error(
                        websocket, f"Processing error: {str(e)}"
                    )

        except json.JSONDecodeError as e:
            await self._send_error(websocket, f"Invalid JSON: {e}")
        except Exception as e:
            self.ten_env.log_error(
                f"Error processing message from {client_id}: {e}"
            )
            await self._send_error(websocket, f"Processing error: {str(e)}")

    async def _send_error(self, websocket: Any, error: str) -> None:
        """
        Send error message to client

        Args:
            websocket: Client WebSocket connection
            error: Error message
        """
        try:
            error_msg = json.dumps({"type": "error", "error": error})
            await websocket.send(error_msg)
        except Exception as e:
            self.ten_env.log_error(f"Failed to send error to client: {e}")

    async def broadcast(self, message: dict[str, Any]) -> None:
        """
        Broadcast message to connected client

        Args:
            message: Message dictionary to send
        """
        if not self.current_client:
            return

        message_str = json.dumps(message)
        await self._send_to_client(self.current_client, message_str)

    async def send_audio_to_clients(
        self, pcm_data: bytes, metadata: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Send audio data to connected WebSocket client

        Args:
            pcm_data: Raw PCM audio bytes
            metadata: Optional metadata to include with the audio
        """
        if not self.current_client:
            self.ten_env.log_debug("No client connected, skipping audio send")
            return

        try:
            # Encode PCM to base64
            audio_base64 = base64.b64encode(pcm_data).decode("utf-8")

            # Build message
            message = {"type": "audio", "audio": audio_base64}

            if metadata:
                message["metadata"] = metadata

            # Send to client
            await self.broadcast(message)

            self.ten_env.log_debug(
                f"Sent {len(pcm_data)} bytes of audio to client"
            )

        except Exception as e:
            self.ten_env.log_error(f"Error sending audio to client: {e}")

    async def send_to_client(
        self, client_id: str, message: dict[str, Any]
    ) -> bool:
        """
        Send message to a specific client

        Args:
            client_id: Client identifier
            message: Message dictionary to send

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.current_client:
            self.ten_env.log_warn("No client connected")
            return False

        current_client_id = f"{self.current_client.remote_address[0]}:{self.current_client.remote_address[1]}"
        if current_client_id != client_id:
            self.ten_env.log_warn(
                f"Client {client_id} not found (current: {current_client_id})"
            )
            return False

        message_str = json.dumps(message)
        return await self._send_to_client(self.current_client, message_str)

    async def _send_to_client(self, websocket: Any, message: str) -> bool:
        """
        Send message to a WebSocket client

        Args:
            websocket: Client WebSocket connection
            message: Message string

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            await websocket.send(message)
            return True
        except Exception as e:
            self.ten_env.log_error(f"Failed to send message to client: {e}")
            return False

    async def _close_client(self, websocket: Any) -> None:
        """
        Close a client connection gracefully

        Args:
            websocket: Client WebSocket connection
        """
        try:
            await websocket.close()
        except Exception as e:
            self.ten_env.log_error(f"Error closing client connection: {e}")

    def get_client_count(self) -> int:
        """Get number of connected clients (0 or 1)"""
        return 1 if self.current_client else 0

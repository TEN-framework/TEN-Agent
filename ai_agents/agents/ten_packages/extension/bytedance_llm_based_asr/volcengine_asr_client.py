import asyncio
import json
import struct
import gzip
import uuid
import logging
from typing import Any, Optional, Callable, Dict, Awaitable
from dataclasses import dataclass

import websockets
from ten_runtime import LogLevel

from .config import BytedanceASRLLMConfig
from .const import (
    PROTOCOL_VERSION,
    MESSAGE_TYPE_CLIENT_FULL_REQUEST,
    MESSAGE_TYPE_CLIENT_AUDIO_ONLY_REQUEST,
    MESSAGE_TYPE_SERVER_FULL_RESPONSE,
    MESSAGE_TYPE_SERVER_ERROR_RESPONSE,
    MESSAGE_TYPE_SPECIFIC_FLAGS_POS_SEQUENCE,
    MESSAGE_TYPE_SPECIFIC_FLAGS_LAST_AUDIO,
    SERIALIZATION_TYPE_JSON,
    SERIALIZATION_TYPE_NO_SERIALIZATION,
    COMPRESSION_TYPE_GZIP,
)


class ServerErrorResponse(Exception):
    """Exception for server error responses with error code."""

    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


@dataclass
class Utterance:
    """Single utterance in ASR result."""

    text: str = ""
    start_time: int = 0
    end_time: int = 0
    definite: bool = False
    additions: Optional[Dict[str, Any]] = None


@dataclass
class ASRResponse:
    """ASR response data structure matching Volcengine ASR API."""

    # Protocol fields
    code: int = 0
    event: int = 0
    is_last_package: bool = False
    payload_sequence: int = 0
    payload_size: int = 0
    payload_msg: Optional[Dict[str, Any]] = None

    # ASR result fields (matching the image structure)
    result: Optional[Dict[str, Any]] = None
    text: str = ""  # Complete audio recognition result text
    utterances: list[Utterance] = None  # type: ignore[assignment]

    # Computed fields for compatibility with ASRResult
    start_ms: int = 0
    duration_ms: int = 0
    language: str = "zh-CN"
    confidence: float = 0.0

    def __post_init__(self):
        if self.utterances is None:
            self.utterances = []


class ASRRequestHeader:
    """ASR request header builder."""

    def __init__(self):
        self.message_type = MESSAGE_TYPE_CLIENT_FULL_REQUEST
        self.message_type_specific_flags = (
            MESSAGE_TYPE_SPECIFIC_FLAGS_POS_SEQUENCE
        )
        self.serialization_type = SERIALIZATION_TYPE_JSON
        self.compression_type = COMPRESSION_TYPE_GZIP
        self.reserved_data = bytes([0x00])

    def with_message_type(self, message_type: int) -> "ASRRequestHeader":
        self.message_type = message_type
        return self

    def with_message_type_specific_flags(
        self, flags: int
    ) -> "ASRRequestHeader":
        self.message_type_specific_flags = flags
        return self

    def with_serialization_type(
        self, serialization_type: int
    ) -> "ASRRequestHeader":
        self.serialization_type = serialization_type
        return self

    def with_compression_type(
        self, compression_type: int
    ) -> "ASRRequestHeader":
        self.compression_type = compression_type
        return self

    def with_reserved_data(self, reserved_data: bytes) -> "ASRRequestHeader":
        self.reserved_data = reserved_data
        return self

    def to_bytes(self) -> bytes:
        header = bytearray()
        # Protocol version (4 bits) | Header size (4 bits) = 0b0001 | 0b0001 = 0b00010001
        header.append((PROTOCOL_VERSION << 4) | 0b0001)
        # Message type (4 bits) | Message type specific flags (4 bits)
        header.append(
            (self.message_type << 4) | self.message_type_specific_flags
        )
        # Serialization method (4 bits) | Compression (4 bits)
        header.append((self.serialization_type << 4) | self.compression_type)
        # Reserved (8 bits)
        header.extend(self.reserved_data)
        return bytes(header)

    @staticmethod
    def default_header() -> "ASRRequestHeader":
        return ASRRequestHeader()


class RequestBuilder:
    """Request builder for ASR messages."""

    @staticmethod
    def new_auth_headers(
        app_key: str,
        access_key: str,
        resource_id: str,
    ) -> Dict[str, str]:
        """Create authentication headers for WebSocket connection."""
        connect_id = str(uuid.uuid4())  # Generate connection tracking ID
        return {
            "X-Api-App-Key": app_key,  # APP ID
            "X-Api-Access-Key": access_key,  # Access Token
            "X-Api-Resource-Id": resource_id,  # Resource information ID
            "X-Api-Connect-Id": connect_id,  # Connection tracking ID (UUID)
        }

    @staticmethod
    def new_api_key_headers(
        api_key: str,
        resource_id: str,
    ) -> Dict[str, str]:
        """Create authentication headers for WebSocket connection."""
        connect_id = str(uuid.uuid4())  # Generate connection tracking ID
        return {
            "x-api-key": api_key,  # APP ID
            "X-Api-Resource-Id": resource_id,  # Resource information ID
            "X-Api-Connect-Id": connect_id,  # Connection tracking ID (UUID)
        }

    @staticmethod
    def new_full_client_request(
        seq: int, config: BytedanceASRLLMConfig
    ) -> bytes:
        """Create full client request."""
        header = (
            ASRRequestHeader.default_header().with_message_type_specific_flags(
                MESSAGE_TYPE_SPECIFIC_FLAGS_POS_SEQUENCE
            )
        )

        payload = {
            "audio": config.get_audio_config(),
            "request": config.get_request_config(),
        }

        # Add user config only if it's provided
        user_config = config.get_user_config()
        if user_config is not None:
            payload["user"] = user_config

        payload_bytes = json.dumps(payload).encode("utf-8")
        compressed_payload = gzip.compress(payload_bytes)
        payload_size = len(compressed_payload)

        request = bytearray()
        request.extend(header.to_bytes())
        request.extend(struct.pack(">i", seq))
        request.extend(struct.pack(">I", payload_size))
        request.extend(compressed_payload)

        return bytes(request)

    @staticmethod
    def new_audio_only_request(
        seq: int, segment: bytes, is_last: bool = False
    ) -> bytes:
        """Create audio-only request."""
        header = ASRRequestHeader.default_header()
        if is_last:
            # According to ByteDance documentation, last packet uses specific flag
            header.with_message_type_specific_flags(
                MESSAGE_TYPE_SPECIFIC_FLAGS_LAST_AUDIO
            )
            # Last packet doesn't need sequence number, use 0
            seq = 0
        else:
            header.with_message_type_specific_flags(
                MESSAGE_TYPE_SPECIFIC_FLAGS_POS_SEQUENCE
            )

        # Set message type to audio request
        header.with_message_type(MESSAGE_TYPE_CLIENT_AUDIO_ONLY_REQUEST)

        # According to ByteDance documentation, audio request uses raw bytes, not JSON serialization
        header.with_serialization_type(SERIALIZATION_TYPE_NO_SERIALIZATION)

        request = bytearray()
        request.extend(header.to_bytes())

        # Only non-last packets include sequence number
        if not is_last:
            request.extend(struct.pack(">i", seq))

        compressed_segment = gzip.compress(segment)
        request.extend(struct.pack(">I", len(compressed_segment)))
        request.extend(compressed_segment)

        return bytes(request)


class ResponseParser:
    """Parser for ASR response messages."""

    @staticmethod
    def parse_response(
        msg: bytes, config: Optional["BytedanceASRLLMConfig"] = None
    ) -> ASRResponse:
        """Parse ASR response message."""
        response = ASRResponse()
        if config:
            response.language = config.language

        if len(msg) < 4:
            return response

        header_size = msg[0] & 0x0F
        message_type = msg[1] >> 4
        message_type_specific_flags = msg[1] & 0x0F
        serialization_method = msg[2] >> 4
        message_compression = msg[2] & 0x0F

        payload = msg[header_size * 4 :]

        # Parse message_type_specific_flags
        if message_type_specific_flags & 0x01:
            if len(payload) >= 4:
                response.payload_sequence = struct.unpack(">i", payload[:4])[0]
                payload = payload[4:]
        if message_type_specific_flags & 0x02:
            response.is_last_package = True
        if message_type_specific_flags & 0x04:
            if len(payload) >= 4:
                response.event = struct.unpack(">i", payload[:4])[0]
                payload = payload[4:]

        # Parse message_type
        if message_type == MESSAGE_TYPE_SERVER_FULL_RESPONSE:
            if len(payload) >= 4:
                response.payload_size = struct.unpack(">I", payload[:4])[0]
                payload = payload[4:]
        elif message_type == MESSAGE_TYPE_SERVER_ERROR_RESPONSE:
            if len(payload) >= 8:
                response.code = struct.unpack(">i", payload[:4])[
                    0
                ]  # Error message code
                error_message_size = struct.unpack(">I", payload[4:8])[
                    0
                ]  # Error message size
                payload = payload[8:]

                # Parse error message if available
                if (
                    error_message_size > 0
                    and len(payload) >= error_message_size
                ):
                    try:
                        error_message = payload[:error_message_size].decode(
                            "utf-8"
                        )
                        response.payload_msg = {"error_message": error_message}
                    except UnicodeDecodeError:
                        # Fallback: use raw bytes
                        response.payload_msg = {
                            "error_message": str(payload[:error_message_size])
                        }
                    payload = payload[error_message_size:]

        if not payload:
            return response

        # Decompress
        if message_compression == COMPRESSION_TYPE_GZIP:
            try:
                payload = gzip.decompress(payload)
            except Exception as e:
                logging.error(f"Failed to decompress payload: {e}")
                return response

        # Parse payload
        try:
            if serialization_method == SERIALIZATION_TYPE_JSON and payload:
                payload_data = json.loads(payload.decode("utf-8"))
                response.payload_msg = payload_data

                # Parse the nested ASR result structure
                if isinstance(payload_data, dict):
                    # Extract the result field - it's a dict, not a list
                    result_data = payload_data.get("result")
                    if result_data and isinstance(result_data, dict):
                        response.result = result_data

                        # Extract overall text
                        response.text = result_data.get("text", "")

                        # Parse utterances
                        utterances_data = result_data.get("utterances", [])
                        # Ensure utterances list is initialized (handled by __post_init__ but check for type safety)
                        if response.utterances is None:
                            response.utterances = []
                        for utterance_data in utterances_data:
                            utterance = Utterance(
                                text=utterance_data.get("text", ""),
                                start_time=utterance_data.get("start_time", 0),
                                end_time=utterance_data.get("end_time", 0),
                                definite=utterance_data.get("definite", False),
                                additions=utterance_data.get("additions"),
                            )
                            response.utterances.append(utterance)

                        # Set computed fields for compatibility
                        if response.utterances:
                            first_utt = response.utterances[0]
                            response.start_ms = first_utt.start_time
                            response.duration_ms = (
                                first_utt.end_time - first_utt.start_time
                            )
                    else:
                        # Fallback for simple structure
                        response.text = payload_data.get("text", "")

        except Exception as e:
            # For error responses, this might be normal - don't log as error
            if response.code != 0:
                logging.info(
                    f"Error response with non-JSON payload (code: {response.code})"
                )
            else:
                logging.error(f"Failed to parse payload: {e}")

        return response


class VolcengineASRClient:
    """Volcengine ASR WebSocket client."""

    def __init__(
        self,
        url: str,
        app_key: str,
        access_key: str,
        api_key: str,
        auth_method: str,
        config: BytedanceASRLLMConfig,
        ten_env=None,
    ):
        self.url = url
        self.app_key = app_key
        self.access_key = access_key
        self.api_key = api_key
        self.auth_method = auth_method
        self.config = config
        self.ten_env = ten_env
        self.websocket = None
        self.connected = False
        self.seq = 1
        # Separate callbacks for different error types
        self.connection_error_callback: Optional[
            Callable[[Exception], Optional[tuple[int, str]]]
        ] = None
        self.asr_error_callback: Optional[
            Callable[[Exception], Optional[tuple[int, str]]]
        ] = None
        self.result_callback: Optional[
            Callable[[ASRResponse], Awaitable[None]]
        ] = None
        self.connected_callback: Optional[
            Callable[[], None | Awaitable[None]]
        ] = None
        self.disconnected_callback: Optional[
            Callable[[int, str, str, str], None | Awaitable[None]]
        ] = None

        # Track first response for connection state management (callback-driven pattern)
        self._first_response_received = False

        # Audio buffer for segmentation
        self.audio_buffer = bytearray()
        self.segment_size = self._calculate_segment_size()

    def _calculate_segment_size(self) -> int:
        """Calculate audio segment size based on configuration."""
        # Calculate bytes per second
        # Get audio parameters from params.audio
        bytes_per_sec = (
            (self.config.get_bits() // 8)
            * self.config.get_channel()
            * self.config.get_sample_rate()
        )
        # Calculate segment size in bytes
        segment_size = (
            bytes_per_sec * self.config.get_segment_duration_ms() // 1000
        )
        return segment_size

    async def connect(self) -> None:
        """Connect to Volcengine ASR service."""
        if self.connected:
            return

        # Reset first response tracking for new connection attempt
        self._first_response_received = False

        if self.auth_method == "api_key":
            headers = RequestBuilder.new_api_key_headers(
                self.api_key, self.config.get_resource_id()
            )
        else:
            headers = RequestBuilder.new_auth_headers(
                self.app_key, self.access_key, self.config.get_resource_id()
            )
        try:
            self.websocket = await websockets.connect(
                self.url,
                additional_headers=headers,
                max_size=100_000_000,  # 100MB
                compression=None,
            )

            # Send initial request
            await self._send_full_client_request()

            # Start listening for responses
            asyncio.create_task(self._listen_for_responses())

            # Do NOT set self.connected = True here (callback-driven pattern)
            # Connection state will be set via connected_callback() when server confirms
            # This matches azure_asr_python pattern where state is set in event handler

        except Exception as e:
            # Connection error - use dedicated connection error callback
            if self.ten_env:
                self.ten_env.log_error(f"Connection failed: {e}")
            else:
                logging.error(f"Connection failed: {e}")

            callback_close = self._handle_connection_error_callback(e)
            vendor_code, vendor_message = (
                callback_close if callback_close is not None else (0, "closed")
            )
            if not self.connection_error_callback and self.ten_env:
                # Fallback logging if no connection error callback is set
                self.ten_env.log_error(f"Connection failed: {e}")
            elif not self.connection_error_callback:
                logging.error(f"Connection failed: {e}")

            await self.disconnect(
                1000, "closed", str(vendor_code), vendor_message
            )
            raise

    async def disconnect(
        self,
        close_code: int = 1000,
        close_message: str = "closed",
        vendor_code: str = "",
        vendor_message: str = "",
    ) -> None:
        """Disconnect from ASR service."""
        self.connected = False
        # Reset first response tracking for reconnection
        self._first_response_received = False

        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logging.error(f"Error closing websocket: {e}")
            finally:
                self.websocket = None

        # Call disconnected callback
        await self._notify_disconnected(
            close_code,
            close_message,
            vendor_code=vendor_code,
            vendor_message=vendor_message,
        )

    async def _invoke_callback(
        self, callback: Callable[..., Any], *args: Any
    ) -> None:
        try:
            result = callback(*args)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            if self.ten_env:
                self.ten_env.log_error(f"Error in callback: {e}")
            else:
                logging.error(f"Error in callback: {e}")

    async def _notify_disconnected(
        self,
        code: int,
        message: str,
        *,
        vendor_code: str = "",
        vendor_message: str = "",
    ) -> None:
        if self.disconnected_callback:
            await self._invoke_callback(
                self.disconnected_callback,
                code,
                message,
                str(vendor_code) if vendor_code else "",
                vendor_message,
            )

    def _handle_asr_error_callback(
        self, exception: Exception
    ) -> Optional[tuple[int, str]]:
        return self._handle_error_callback(
            self.asr_error_callback, exception, "ASR error"
        )

    def _handle_connection_error_callback(
        self, exception: Exception
    ) -> Optional[tuple[int, str]]:
        return self._handle_error_callback(
            self.connection_error_callback, exception, "connection error"
        )

    def _handle_error_callback(
        self,
        callback: Optional[Callable[[Exception], Optional[tuple[int, str]]]],
        exception: Exception,
        callback_name: str,
    ) -> Optional[tuple[int, str]]:
        if not callback:
            return None

        try:
            callback_result = callback(exception)
        except Exception as callback_error:
            if self.ten_env:
                self.ten_env.log_error(
                    f"Error in {callback_name} callback: {callback_error}"
                )
            else:
                logging.error(
                    f"Error in {callback_name} callback: {callback_error}"
                )
            return None

        if callback_result is None:
            return None

        try:
            error_code, error_message = callback_result
            return int(error_code), str(error_message)
        except (TypeError, ValueError):
            if self.ten_env:
                self.ten_env.log_error(
                    f"Invalid {callback_name} callback result: "
                    f"{callback_result}"
                )
            else:
                logging.error(
                    f"Invalid {callback_name} callback result: "
                    f"{callback_result}"
                )
            return None

    async def _send_full_client_request(self) -> None:
        """Send full client request."""
        if not self.websocket:
            raise RuntimeError("WebSocket not connected")

        request_payload = {
            "request": self.config.get_request_config(),
        }
        if self.ten_env:
            self.ten_env.log_info(
                "full_client_request params (request section): "
                + json.dumps(request_payload, ensure_ascii=False),
            )
        request = RequestBuilder.new_full_client_request(self.seq, self.config)
        self.seq += 1
        await self.websocket.send(request)

    async def send_audio(self, audio_data: bytes) -> None:
        """Send audio data to ASR service."""
        if not self.connected:
            if self.ten_env:
                self.ten_env.log(LogLevel.ERROR, "Not connected to ASR service")
            else:
                logging.error("Not connected to ASR service")
            raise RuntimeError("Not connected to ASR service")

        # Add audio data to buffer
        self.audio_buffer.extend(audio_data)

        # Send complete segments
        while len(self.audio_buffer) >= self.segment_size:
            segment = bytes(self.audio_buffer[: self.segment_size])
            self.audio_buffer = self.audio_buffer[self.segment_size :]

            await self._send_audio_segment(segment, False)

    async def finalize(self) -> None:
        if not self.connected:
            return

        # Send remaining audio data first
        if self.audio_buffer:
            await self._send_audio_segment(bytes(self.audio_buffer), False)
            self.audio_buffer.clear()

        # For 16kHz, 16-bit, mono: 800ms = 0.8 * 16000 * 2 = 25600 bytes
        mute_pkg_duration_ms = self.config.get_mute_pkg_duration_ms()
        bytes_per_sample = self.config.get_bits() // 8  # bits to bytes
        samples_per_ms = (
            self.config.get_sample_rate() // 1000
        )  # samples per millisecond
        silence_bytes = mute_pkg_duration_ms * samples_per_ms * bytes_per_sample

        # Generate silence (zeros)
        silence_data = bytes(silence_bytes)

        # Send silence in chunks
        chunk_size = self.segment_size

        for i in range(0, len(silence_data), chunk_size):
            chunk = silence_data[i : i + chunk_size]
            await self._send_audio_segment(chunk, False)

    def _parse_message_type(self, msg: bytes) -> int:
        """Parse message type from response header.

        Args:
            msg: Raw message bytes

        Returns:
            Message type value (4 bits from second byte, upper 4 bits)
        """
        if len(msg) < 2:
            return 0
        return msg[1] >> 4

    async def _check_first_response(
        self, msg: bytes, response: ASRResponse
    ) -> None:
        """Handle first response from server (callback-driven connection state).

        Called when receiving the first response after sending FULL_REQUEST.
        If server confirms connection (FULL_RESPONSE with code=0), sets connected=True
        and calls connected_callback. Error responses are handled by the general
        error handling flow below.

        Args:
            msg: Raw message bytes (for parsing message_type)
            response: Parsed ASRResponse
        """
        message_type = self._parse_message_type(msg)

        # Server confirmed connection - set connected=True and call connected_callback
        # Extension's _on_connected() will also set extension.connected=True
        if (
            message_type == MESSAGE_TYPE_SERVER_FULL_RESPONSE
            and response.code == 0
        ):
            # Set client's connected state (required for send_audio checks)
            self.connected = True
            if self.connected_callback:
                await self._invoke_callback(self.connected_callback)
        # Error responses (ERROR_RESPONSE or FULL_RESPONSE with code!=0)
        # are handled by the general error handling flow below

    async def _send_audio_segment(self, segment: bytes, is_last: bool) -> None:
        """Send audio segment."""
        if not self.websocket:
            return

        request = RequestBuilder.new_audio_only_request(
            self.seq, segment, is_last
        )

        if not is_last:
            self.seq += 1

        await self.websocket.send(request)

    async def _listen_for_responses(self) -> None:
        """Listen for ASR responses."""
        if not self.websocket:
            return

        close_code = 1000
        close_message = "closed"
        vendor_code = ""
        vendor_message = ""
        try:
            async for msg in self.websocket:
                # websockets directly returns data, no need to check type
                if isinstance(msg, bytes):
                    response = ResponseParser.parse_response(msg, self.config)

                    # Handle first response (callback-driven connection state)
                    if not self._first_response_received:
                        self._first_response_received = True
                        await self._check_first_response(msg, response)

                    await self._handle_response(response)

                    # Handle error responses from server
                    if response.code != 0:
                        error_message = (
                            response.payload_msg.get("error_message")
                            if isinstance(response.payload_msg, dict)
                            else None
                        )
                        error = ServerErrorResponse(
                            error_message
                            or f"Server error response: code={response.code}",
                            response.code,
                        )
                        callback_close = self._handle_asr_error_callback(error)
                        if callback_close is not None:
                            vendor_code, vendor_message = callback_close

                        # Don't break - continue listening for more responses in streaming mode
                    elif response.is_last_package:
                        # Don't break - continue listening for more responses in streaming mode
                        pass
        except BaseException as e:
            if self.ten_env:
                self.ten_env.log_error(f"Error listening for responses: {e}")
            else:
                logging.error(f"Error listening for responses: {e}")

            # ASR communication error - use dedicated ASR error callback
            callback_close = self._handle_asr_error_callback(e)
            if callback_close is not None:
                vendor_code, vendor_message = callback_close
        finally:
            self.connected = False
            # Reset first response tracking for reconnection
            self._first_response_received = False
            await self._notify_disconnected(
                close_code,
                close_message,
                vendor_code=vendor_code,
                vendor_message=vendor_message,
            )

    async def _handle_response(self, response: ASRResponse) -> None:
        """Handle ASR response."""
        # Call result callback if set
        if self.result_callback:
            try:
                await self.result_callback(response)
            except Exception as e:
                if self.ten_env:
                    self.ten_env.log_error(f"Error in result callback: {e}")
                else:
                    logging.error(f"Error in result callback: {e}")
        elif self.ten_env:
            self.ten_env.log_warn("result_callback is not set")
        else:
            logging.warning("result_callback is not set")

    def set_on_connection_error_callback(
        self, callback: Callable[[Exception], Optional[tuple[int, str]]]
    ) -> None:
        """Set callback for connection errors (HTTP stage)."""
        self.connection_error_callback = callback

    def set_on_asr_error_callback(
        self, callback: Callable[[Exception], Optional[tuple[int, str]]]
    ) -> None:
        """Set callback for ASR business errors (WebSocket stage)."""
        self.asr_error_callback = callback

    def set_on_result_callback(
        self, callback: Callable[[ASRResponse], Awaitable[None]]
    ) -> None:
        """Set callback for ASR results (alias for set_result_callback)."""
        self.result_callback = callback

    def set_on_connected_callback(
        self, callback: Callable[[], None | Awaitable[None]]
    ) -> None:
        """Set callback for connection events."""
        self.connected_callback = callback

    def set_on_disconnected_callback(
        self, callback: Callable[[int, str, str, str], None | Awaitable[None]]
    ) -> None:
        """Set callback for disconnection events."""
        self.disconnected_callback = callback

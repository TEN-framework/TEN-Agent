# coding=utf-8

"""
Bytedance ASR WebSocket Client

Requires Python 3.9 or later for modern typing features.

Dependencies:
    websockets>=14.0
    pydantic
"""

import asyncio
import base64
import gzip
import hmac
import json
import logging
import uuid
from hashlib import sha256
from typing import Any
from urllib.parse import urlparse
import websockets

from ten_runtime import AsyncTenEnv

PROTOCOL_VERSION = 0b0001
DEFAULT_HEADER_SIZE = 0b0001

PROTOCOL_VERSION_BITS = 4
HEADER_BITS = 4
MESSAGE_TYPE_BITS = 4
MESSAGE_TYPE_SPECIFIC_FLAGS_BITS = 4
MESSAGE_SERIALIZATION_BITS = 4
MESSAGE_COMPRESSION_BITS = 4
RESERVED_BITS = 8

# Message Type:
CLIENT_FULL_REQUEST = 0b0001
CLIENT_AUDIO_ONLY_REQUEST = 0b0010
SERVER_FULL_RESPONSE = 0b1001
SERVER_ACK = 0b1011
SERVER_ERROR_RESPONSE = 0b1111

# Message Type Specific Flags
NO_SEQUENCE = 0b0000  # no check sequence
POS_SEQUENCE = 0b0001
NEG_SEQUENCE = 0b0010
NEG_SEQUENCE_1 = 0b0011

# Message Serialization
NO_SERIALIZATION = 0b0000
JSON = 0b0001
THRIFT = 0b0011
CUSTOM_TYPE = 0b1111

# Message Compression
NO_COMPRESSION = 0b0000
GZIP = 0b0001
CUSTOM_COMPRESSION = 0b1111


def generate_header(
    version=PROTOCOL_VERSION,
    message_type=CLIENT_FULL_REQUEST,
    message_type_specific_flags=NO_SEQUENCE,
    serial_method=JSON,
    compression_type=GZIP,
    reserved_data=0x00,
    extension_header=bytes(),
):
    """
    protocol_version(4 bits), header_size(4 bits),
    message_type(4 bits), message_type_specific_flags(4 bits)
    serialization_method(4 bits) message_compression(4 bits)
    reserved (8bits) reserved field
    header_extensions extension header (size equals 8 * 4 * (header_size - 1))
    """
    header = bytearray()
    header_size = int(len(extension_header) / 4) + 1
    header.append((version << 4) | header_size)
    header.append((message_type << 4) | message_type_specific_flags)
    header.append((serial_method << 4) | compression_type)
    header.append(reserved_data)
    header.extend(extension_header)
    return header


def generate_full_default_header():
    return generate_header()


def generate_audio_default_header():
    return generate_header(message_type=CLIENT_AUDIO_ONLY_REQUEST)


def generate_last_audio_default_header():
    return generate_header(
        message_type=CLIENT_AUDIO_ONLY_REQUEST,
        message_type_specific_flags=NEG_SEQUENCE,
    )


def parse_response(res):
    """
    protocol_version(4 bits), header_size(4 bits),
    message_type(4 bits), message_type_specific_flags(4 bits)
    serialization_method(4 bits) message_compression(4 bits)
    reserved (8bits) reserved field
    header_extensions extension header (size equals 8 * 4 * (header_size - 1))
    payload similar to http request body
    """
    header_size = res[0] & 0x0F
    message_type = res[1] >> 4
    serialization_method = res[2] >> 4
    message_compression = res[2] & 0x0F
    payload = res[header_size * 4 :]
    result = {}
    payload_msg = None
    payload_size = 0
    if message_type == SERVER_FULL_RESPONSE:
        payload_size = int.from_bytes(payload[:4], "big", signed=True)
        payload_msg = payload[4:]
    elif message_type == SERVER_ACK:
        seq = int.from_bytes(payload[:4], "big", signed=True)
        result["seq"] = seq
        if len(payload) >= 8:
            payload_size = int.from_bytes(payload[4:8], "big", signed=False)
            payload_msg = payload[8:]
    elif message_type == SERVER_ERROR_RESPONSE:
        code = int.from_bytes(payload[:4], "big", signed=False)
        result["code"] = code
        payload_size = int.from_bytes(payload[4:8], "big", signed=False)
        payload_msg = payload[8:]
    if payload_msg is None:
        return result
    if message_compression == GZIP:
        payload_msg = gzip.decompress(payload_msg)
    if serialization_method == JSON:
        payload_msg = json.loads(str(payload_msg, "utf-8"))
    elif serialization_method != NO_SERIALIZATION:
        payload_msg = str(payload_msg, "utf-8")
    result["payload_msg"] = payload_msg
    result["payload_size"] = payload_size
    return result


class AsrWsClient:
    def __init__(self, ten_env: AsyncTenEnv, cluster, **kwargs):
        """
        :param ten_env: AsyncTenEnv instance
        :param cluster: cluster name
        :param kwargs: Additional parameters including appid, token, ws_url, workflow, auth_method, api_key, handle_received_message, on_finalize_complete, on_error, pass_through_params, vad_silence_time, secret
        """
        self.cluster = cluster
        self.success_code = 1000  # success code, default is 1000
        self.appid = kwargs.get("appid", "")
        self.token = kwargs.get("token", "")
        self.api_key = kwargs.get("api_key", "")
        self.ws_url = kwargs.get(
            "ws_url", "wss://openspeech.bytedance.com/api/v2/asr"
        )
        self.secret = kwargs.get("secret", "access_secret")
        self.auth_method = kwargs.get("auth_method", "token")
        # vad_silence_time is used directly in finalize() method, so it needs to be kept
        self.vad_silence_time = kwargs.get("silence_pkg_length_ms", "800")

        # Store pass-through params for flexible parameter configuration
        # This allows vendor parameters to be changed without code modification
        self.pass_through_params = kwargs.get("pass_through_params", {})

        self.websocket = None
        self.handle_received_message = kwargs.get(
            "handle_received_message", self.default_handler
        )
        self.ten_env = ten_env

        # Add finalize-related state management
        self._finalize_requested = False
        self._neg_sequence_sent = False
        self._finalize_completed = False
        self._finalize_event = asyncio.Event()

        # Add finalize completion callback
        self.on_finalize_complete = kwargs.get("on_finalize_complete", None)

        # Add error callback for handling non-1000 error codes
        self.on_error = kwargs.get("on_error", None)

    def default_handler(self, result):
        # Default handler if none is provided
        logging.warning("Received message but no handler is set: %s", result)

    async def receive_messages(self):
        while True:
            try:
                if not self.websocket:
                    self.ten_env.log_error(
                        "Websocket is None, cannot receive messages"
                    )
                    break
                res = await self.websocket.recv()
                result = parse_response(res)

                # Check business status code from payload_msg, trigger error handling if not 1000
                payload_msg = result.get("payload_msg", {})
                if isinstance(payload_msg, dict):
                    result_code = payload_msg.get("code")
                    if (
                        result_code is not None
                        and result_code != self.success_code
                    ):
                        error_msg = (
                            f"ASR server returned error code: {result_code}"
                        )
                        # Add detailed error information for debugging
                        if "message" in payload_msg:
                            error_msg += f", message: {payload_msg['message']}"
                        if "reqid" in payload_msg:
                            error_msg += f", reqid: {payload_msg['reqid']}"
                        self.ten_env.log_error(error_msg)
                        self.ten_env.log_error(
                            f"Full payload_msg: {payload_msg}",
                            category=LOG_CATEGORY_TRANSCRIPTS,
                        )
                        # Use error callback to handle non-1000 error codes
                        if self.on_error:
                            try:
                                await self.on_error(result_code, error_msg)
                            except Exception as callback_error:
                                self.ten_env.log_error(
                                    f"Error in error callback: {callback_error}"
                                )
                        continue  # Continue listening, don't interrupt connection

                # Process received message
                result_data = result["payload_msg"].get("result")
                await self.handle_received_message(result_data)

                # Check if final result is received
                if self._finalize_requested and result["payload_msg"].get(
                    "result"
                ):
                    for item in result["payload_msg"]["result"]:
                        if "utterances" in item and item["utterances"]:
                            for utterance in item["utterances"]:
                                if utterance.get("definite", False):
                                    self._finalize_completed = True
                                    self._finalize_event.set()

                                    # Reset finalize state after receiving final result
                                    self._finalize_requested = False
                                    self._neg_sequence_sent = False

                                    # Call finalize completion callback
                                    if self.on_finalize_complete:
                                        try:
                                            await self.on_finalize_complete()
                                        except Exception as e:
                                            self.ten_env.log_error(
                                                f"Error in finalize complete callback: {e}"
                                            )

                                    # Don't return here - continue listening for new messages
                                    # This allows the same connection to handle multiple speech recognition sessions
                                    self.ten_env.log_info(
                                        "Finalize completed, continuing to listen for new messages"
                                    )

            except websockets.ConnectionClosed as e:
                self.ten_env.log_info(f"WebSocket connection closed: {e}")
                # Trigger reconnection if connection closes unexpectedly
                if self.on_error:
                    try:
                        await self.on_error(
                            2001, f"WebSocket connection closed: {e}"
                        )
                    except Exception as callback_error:
                        self.ten_env.log_error(
                            f"Error in connection closed callback: {callback_error}"
                        )
                break
            except websockets.InvalidState as e:
                self.ten_env.log_error(f"WebSocket invalid state: {e}")
                if self.on_error:
                    try:
                        await self.on_error(
                            2002, f"WebSocket invalid state: {e}"
                        )
                    except Exception as callback_error:
                        self.ten_env.log_error(
                            f"Error in invalid state callback: {callback_error}"
                        )
                break
            except websockets.ProtocolError as e:
                self.ten_env.log_error(f"WebSocket protocol error: {e}")
                if self.on_error:
                    try:
                        await self.on_error(
                            2003, f"WebSocket protocol error: {e}"
                        )
                    except Exception as callback_error:
                        self.ten_env.log_error(
                            f"Error in protocol error callback: {callback_error}"
                        )
                break
            except asyncio.TimeoutError:
                self.ten_env.log_error("WebSocket receive timeout")
                if self.on_error:
                    try:
                        await self.on_error(1008, "WebSocket receive timeout")
                    except Exception as callback_error:
                        self.ten_env.log_error(
                            f"Error in timeout callback: {callback_error}"
                        )
                break
            except Exception as e:
                self.ten_env.log_error(
                    f"Unexpected error in receive_messages: {e}"
                )
                if self.on_error:
                    try:
                        await self.on_error(1007, f"Unexpected error: {e}")
                    except Exception as callback_error:
                        self.ten_env.log_error(
                            f"Error in unexpected error callback: {callback_error}"
                        )
                break

    async def finalize(self) -> None:
        """Send finalize signal to indicate end of audio input"""
        if not self.websocket:
            self.ten_env.log_warn("Websocket not connected, cannot finalize")
            return

        self._finalize_requested = True
        self.ten_env.log_info("Sending finalize signal to ASR server")

        # Send a silence frame based on vad_silence_time configuration
        # This approach avoids NEG_SEQUENCE issues while providing sufficient silence
        try:
            # Convert vad_silence_time from string to milliseconds, then to samples
            silence_ms = int(self.vad_silence_time)
            silence_samples = int(
                16000 * silence_ms / 1000
            )  # Convert ms to samples at 16kHz
            silence_data = b"\x00" * (silence_samples * 2)  # 16-bit samples

            # Compress the silence data
            payload_bytes = gzip.compress(silence_data)

            # Create normal audio-only request (without NEG_SEQUENCE flag)
            audio_only_request = bytearray(generate_audio_default_header())
            audio_only_request.extend(
                (len(payload_bytes)).to_bytes(4, "big")
            )  # payload size
            audio_only_request.extend(payload_bytes)  # payload

            self.ten_env.log_info(
                f"Sending {silence_ms}ms silence frame for finalize"
            )
            await self.websocket.send(bytes(audio_only_request))
            self.ten_env.log_info(
                f"{silence_ms}ms silence frame sent successfully"
            )

        except Exception as e:
            silence_ms = int(self.vad_silence_time)
            self.ten_env.log_error(
                f"Failed to send {silence_ms}ms silence frame: {e}"
            )
            if self.on_error:
                try:
                    await self.on_error(
                        2001,
                        f"Failed to send {silence_ms}ms silence frame: {e}",
                    )
                except Exception as callback_error:
                    self.ten_env.log_error(
                        f"Error in silence frame error callback: {callback_error}"
                    )

    def is_finalized(self) -> bool:
        """Check if finalize has been completed"""
        return self._finalize_completed

    async def wait_for_finalize(self, timeout: float = 3.0) -> bool:
        """Wait for finalize completion with timeout"""
        try:
            self.ten_env.log_info(
                f"Waiting for finalize completion with timeout: {timeout}s"
            )
            await asyncio.wait_for(self._finalize_event.wait(), timeout=timeout)
            self.ten_env.log_info("Finalize completed successfully")
            return True
        except asyncio.TimeoutError:
            self.ten_env.log_warn(f"Finalize timeout after {timeout}s")
            return False

    async def start(self):
        # Reset finalize state for new connection
        self._finalize_requested = False
        self._finalize_completed = False
        self._neg_sequence_sent = False
        self._finalize_event.clear()

        reqid = str(uuid.uuid4())
        # Build full client request and serialize with compression
        request_params = self.construct_request(reqid)
        payload_bytes = str.encode(json.dumps(request_params))
        payload_bytes = gzip.compress(payload_bytes)
        full_client_request = bytearray(generate_full_default_header())
        full_client_request.extend(
            (len(payload_bytes)).to_bytes(4, "big")
        )  # payload size(4 bytes)
        full_client_request.extend(payload_bytes)  # payload
        header = None
        if self.auth_method == "token":
            header = self.token_auth()
        elif self.auth_method == "signature":
            header = self.signature_auth(full_client_request)
        elif self.auth_method == "api_key":
            header = self.api_key_auth()
        self.websocket = await websockets.connect(
            self.ws_url,
            additional_headers=header,
            max_size=1000000000,
            ping_interval=15,  # Send ping every 15 seconds (more frequent for stability)
            ping_timeout=5,  # Wait 5 seconds for pong response
            close_timeout=5,  # Wait 5 seconds for close frame
        )
        self.ten_env.log_info("WebSocket connected")

        # Start ping monitoring task
        asyncio.create_task(self._monitor_ping_pong())
        # Send full client request
        await self.websocket.send(bytes(full_client_request))
        # Start receiving messages coroutine
        asyncio.create_task(self.receive_messages())

    async def finish(self) -> None:
        if self.websocket is not None:
            await self.websocket.close()
            self.websocket = None

    async def _monitor_ping_pong(self):
        """Monitor WebSocket ping/pong activity"""
        try:
            while self.websocket and self.websocket.state.name == "OPEN":
                await asyncio.sleep(30)
                if self.websocket:
                    self.ten_env.log_debug("WebSocket connection active")
        except Exception as e:
            self.ten_env.log_error(f"Error in ping/pong monitor: {e}")

    async def send(self, chunk: bytes):
        if not self.websocket:
            self.ten_env.log_error("Websocket is None, cannot send audio")
            return

        # Skip empty chunks to avoid 1007 errors
        if not chunk or len(chunk) == 0:
            self.ten_env.log_debug("Skipping empty audio chunk")
            return

        # Check WebSocket state before sending
        if self.websocket.state.name != "OPEN":
            self.ten_env.log_warn(
                f"WebSocket not in OPEN state: {self.websocket.state.name}"
            )
            # Don't send data if WebSocket is not in OPEN state
            # Let the calling code handle reconnection
            return

        payload_bytes = gzip.compress(chunk)

        # All audio packets use normal header (no NEG_SEQUENCE flag)
        # This avoids connection issues while maintaining ASR functionality
        audio_only_request = bytearray(generate_audio_default_header())
        if self._finalize_requested:
            self.ten_env.log_debug(
                f"Audio packet during finalize: _finalize_requested={self._finalize_requested}, _neg_sequence_sent={self._neg_sequence_sent}"
            )

        audio_only_request.extend(
            (len(payload_bytes)).to_bytes(4, "big")
        )  # payload size(4 bytes)
        audio_only_request.extend(payload_bytes)  # payload

        # Send audio-only client request
        try:
            await self.websocket.send(bytes(audio_only_request))
        except websockets.exceptions.ConnectionClosed as e:
            self.ten_env.log_error(
                f"WebSocket connection closed during send: {e}"
            )
            if self.on_error:
                try:
                    await self.on_error(
                        2001, f"WebSocket connection closed: {e}"
                    )
                except Exception as callback_error:
                    self.ten_env.log_error(
                        f"Error in send error callback: {callback_error}"
                    )
        except Exception as e:
            self.ten_env.log_error(f"Failed to send audio via WebSocket: {e}")
            # Don't raise exception, let error callback handle reconnection
            if self.on_error:
                try:
                    await self.on_error(2001, f"Failed to send audio: {e}")
                except Exception as callback_error:
                    self.ten_env.log_error(
                        f"Error in send error callback: {callback_error}"
                    )
            return

    def construct_request(self, reqid):
        req = {
            "app": {
                "appid": self.appid,
                "cluster": self.cluster,
                "token": self.token,
            },
            "request": {
                "reqid": reqid,
                "sequence": 1,
            },
            "user": {},
            "audio": {},
        }

        # Add request parameters from pass_through_params (except reqid and sequence)
        # Only add parameters that are explicitly provided in pass_through_params
        if self.pass_through_params and "request" in self.pass_through_params:
            request_params = self.pass_through_params["request"]
            if isinstance(request_params, dict):
                for key, value in request_params.items():
                    # Skip reqid and sequence as they are already set
                    if key not in ("reqid", "sequence"):
                        req["request"][key] = value

        # Add user parameters from pass_through_params (uid is already set above, but will be overridden if provided)
        # Only add parameters that are explicitly provided in pass_through_params
        if self.pass_through_params and "user" in self.pass_through_params:
            user_params = self.pass_through_params["user"]
            if isinstance(user_params, dict):
                for key, value in user_params.items():
                    # Include all parameters including uid (uid will override the default if provided)
                    req["user"][key] = value

        # Add audio parameters from pass_through_params (format is already set above, but will be overridden if provided)
        # Only add parameters that are explicitly provided in pass_through_params
        if self.pass_through_params and "audio" in self.pass_through_params:
            audio_params = self.pass_through_params["audio"]
            if isinstance(audio_params, dict):
                for key, value in audio_params.items():
                    # Include all parameters including format (format will override the default if provided)
                    req["audio"][key] = value

        # Deep merge pass-through params for app field only
        # This allows parameters to be changed through configuration without code modification
        if self.pass_through_params:
            if "app" in self.pass_through_params:
                if isinstance(self.pass_through_params["app"], dict):
                    # Deep merge nested dictionaries
                    req["app"] = self._deep_merge_dict(
                        req["app"], self.pass_through_params["app"]
                    )
                else:
                    # If not a dict, override directly
                    req["app"] = self.pass_through_params["app"]

        self.ten_env.log_info(
            f"Final request: {json.dumps(req, indent=2, ensure_ascii=False)}"
        )

        return req

    def _deep_merge_dict(
        self, base: dict[str, Any], override: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Deep merge override dict into base dict.
        Override values take precedence over base values.

        :param base: Base dictionary
        :param override: Override dictionary (values from this dict take precedence)
        :return: Merged dictionary
        """
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                # Recursively merge nested dictionaries
                result[key] = self._deep_merge_dict(result[key], value)
            else:
                # Override value (or add new key)
                result[key] = value

        return result

    def token_auth(self):
        self.ten_env.log_info(f"token_auth: {self.token}")
        return {"Authorization": "Bearer; {}".format(self.token)}

    def api_key_auth(self):
        self.ten_env.log_info(f"api_key_auth: {self.api_key}")
        return {"x-api-key": "{}".format(self.api_key)}

    def signature_auth(self, data):
        header_dicts = {
            "Custom": "auth_custom",
        }

        url_parse = urlparse(self.ws_url)
        input_str = "GET {} HTTP/1.1\n".format(url_parse.path)
        auth_headers = "Custom"
        for header in auth_headers.split(","):
            input_str += "{}\n".format(header_dicts[header])
        input_data = bytearray(input_str, "utf-8")
        input_data += data
        mac = base64.urlsafe_b64encode(
            hmac.new(
                self.secret.encode("utf-8"), input_data, digestmod=sha256
            ).digest()
        )
        header_dicts["Authorization"] = (
            'HMAC256; access_token="{}"; mac="{}"; h="{}"'.format(
                self.token, str(mac, "utf-8"), auth_headers
            )
        )
        return header_dicts

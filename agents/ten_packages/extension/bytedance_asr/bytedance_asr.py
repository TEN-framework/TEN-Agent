# coding=utf-8

"""
requires Python 3.6 or later

pip install asyncio
pip install websockets
"""

import asyncio
import base64
import gzip
import hmac
import json
import logging
import uuid
from hashlib import sha256
from urllib.parse import urlparse
import websockets

from ten import AsyncTenEnv

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
    reserved （8bits) 保留字段
    header_extensions 扩展头(大小等于 8 * 4 * (header_size - 1) )
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
        message_type=CLIENT_AUDIO_ONLY_REQUEST, message_type_specific_flags=NEG_SEQUENCE
    )


def parse_response(res):
    """
    protocol_version(4 bits), header_size(4 bits),
    message_type(4 bits), message_type_specific_flags(4 bits)
    serialization_method(4 bits) message_compression(4 bits)
    reserved （8bits) 保留字段
    header_extensions 扩展头(大小等于 8 * 4 * (header_size - 1) )
    payload 类似与http 请求体
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
        :param config: config
        """
        self.cluster = cluster
        self.success_code = 1000  # success code, default is 1000
        self.seg_duration = int(kwargs.get("seg_duration", 15000))
        self.nbest = int(kwargs.get("nbest", 1))
        self.appid = kwargs.get("appid", "")
        self.token = kwargs.get("token", "")
        self.ws_url = kwargs.get("ws_url", "wss://openspeech.bytedance.com/api/v2/asr")
        self.uid = kwargs.get("uid", "streaming_asr_demo")
        self.workflow = kwargs.get(
            "workflow", "audio_in,resample,partition,vad,fe,decode,itn,nlu_punctuate"
        )
        self.show_language = kwargs.get("show_language", False)
        self.show_utterances = kwargs.get("show_utterances", True)
        self.result_type = kwargs.get("result_type", "single")
        self.format = kwargs.get("format", "raw")
        self.rate = kwargs.get("sample_rate", 16000)
        self.language = kwargs.get("language", "zh-CN")
        self.bits = kwargs.get("bits", 16)
        self.channel = kwargs.get("channel", 1)
        self.codec = kwargs.get("codec", "raw")
        self.secret = kwargs.get("secret", "access_secret")
        self.auth_method = kwargs.get("auth_method", "token")
        self.mp3_seg_size = int(kwargs.get("mp3_seg_size", 10000))

        self.websocket = None
        self.handle_received_message = kwargs.get(
            "handle_received_message", self.default_handler
        )
        self.ten_env = ten_env

    def default_handler(self, result):
        # Default handler if none is provided
        logging.warning("Received message but no handler is set: %s", result)

    async def receive_messages(self):
        while True:
            try:
                res = await self.websocket.recv()
                result = parse_response(res)
                # self.ten_env.log_info(f"{result}")
                # 处理接收到的消息
                await self.handle_received_message(result["payload_msg"].get("result"))
            except websockets.ConnectionClosed:
                self.ten_env.log_info("ConnectionClosed")
                break

    async def start(self):
        reqid = str(uuid.uuid4())
        # 构建 full client request，并序列化压缩
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
        self.websocket = await websockets.connect(
            self.ws_url, additional_headers=header, max_size=1000000000
        )

        # 发送 full client request
        await self.websocket.send(full_client_request)
        # 启动接收消息的协程
        asyncio.create_task(self.receive_messages())

    async def finish(self) -> None:
        if self.websocket is not None:
            await self.websocket.close()
            self.websocket = None
            self.ten_env.log_info("Websocket connection closed.")
        else:
            self.ten_env.log_info("Websocket is not connected.")

    async def send(self, chunk: bytes):
        # if no compression, comment this line
        payload_bytes = gzip.compress(chunk)
        audio_only_request = bytearray(generate_audio_default_header())
        audio_only_request.extend(
            (len(payload_bytes)).to_bytes(4, "big")
        )  # payload size(4 bytes)
        audio_only_request.extend(payload_bytes)  # payload
        # 发送 audio-only client request
        await self.websocket.send(audio_only_request)

    def construct_request(self, reqid):
        req = {
            "app": {
                "appid": self.appid,
                "cluster": self.cluster,
                "token": self.token,
            },
            "user": {"uid": self.uid},
            "request": {
                "reqid": reqid,
                "nbest": self.nbest,
                "workflow": self.workflow,
                "show_language": self.show_language,
                "show_utterances": self.show_utterances,
                "result_type": self.result_type,
                "sequence": 1,
            },
            "audio": {
                "format": self.format,
                "rate": self.rate,
                "language": self.language,
                "bits": self.bits,
                "channel": self.channel,
                "codec": self.codec,
            },
        }
        return req

    def token_auth(self):
        return {"Authorization": "Bearer; {}".format(self.token)}

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
            hmac.new(self.secret.encode("utf-8"), input_data, digestmod=sha256).digest()
        )
        header_dicts["Authorization"] = (
            'HMAC256; access_token="{}"; mac="{}"; h="{}"'.format(
                self.token, str(mac, "utf-8"), auth_headers
            )
        )
        return header_dicts

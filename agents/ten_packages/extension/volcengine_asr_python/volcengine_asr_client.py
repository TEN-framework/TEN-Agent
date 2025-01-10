import asyncio
import gzip
import json
import time
import uuid
import wave
from io import BytesIO
from typing import Dict, Union, Optional, cast, Any, Callable
import websockets

PROTOCOL_VERSION = 0b0001
DEFAULT_HEADER_SIZE = 0b0001

# Message Type:
FULL_CLIENT_REQUEST = 0b0001
AUDIO_ONLY_REQUEST = 0b0010
FULL_SERVER_RESPONSE = 0b1001
SERVER_ACK = 0b1011
SERVER_ERROR_RESPONSE = 0b1111

# Message Type Specific Flags
NO_SEQUENCE = 0b0000  # no check sequence
POS_SEQUENCE = 0b0001
NEG_SEQUENCE = 0b0010
NEG_WITH_SEQUENCE = 0b0011
NEG_SEQUENCE_1 = 0b0011

# Message Serialization
NO_SERIALIZATION = 0b0000
JSON = 0b0001

# Message Compression
NO_COMPRESSION = 0b0000
GZIP = 0b0001


def generate_header(
        message_type=FULL_CLIENT_REQUEST,
        message_type_specific_flags=NO_SEQUENCE,
        serial_method=JSON,
        compression_type=GZIP,
        reserved_data=0x00
):
    """
    protocol_version(4 bits), header_size(4 bits),
    message_type(4 bits), message_type_specific_flags(4 bits)
    serialization_method(4 bits) message_compression(4 bits)
    reserved （8bits) 保留字段
    """
    header = bytearray()
    header_size = 1
    header.append((PROTOCOL_VERSION << 4) | header_size)
    header.append((message_type << 4) | message_type_specific_flags)
    header.append((serial_method << 4) | compression_type)
    header.append(reserved_data)
    return header


def generate_before_payload(sequence: int):
    before_payload = bytearray()
    before_payload.extend(sequence.to_bytes(4, 'big', signed=True))  # sequence
    return before_payload


def parse_response(res):
    """
    protocol_version(4 bits), header_size(4 bits),
    message_type(4 bits), message_type_specific_flags(4 bits)
    serialization_method(4 bits) message_compression(4 bits)
    reserved （8bits) 保留字段
    header_extensions 扩展头(大小等于 8 * 4 * (header_size - 1) )
    payload 类似与http 请求体
    """
    protocol_version = res[0] >> 4
    header_size = res[0] & 0x0f
    message_type = res[1] >> 4
    message_type_specific_flags = res[1] & 0x0f
    serialization_method = res[2] >> 4
    message_compression = res[2] & 0x0f
    reserved = res[3]
    header_extensions = res[4:header_size * 4]
    payload = res[header_size * 4:]
    result = {
        'is_last_package': False,
    }
    payload_msg = None
    payload_size = 0
    if message_type_specific_flags & 0x01:
        # receive frame with sequence
        seq = int.from_bytes(payload[:4], "big", signed=True)
        result['payload_sequence'] = seq
        payload = payload[4:]

    if message_type_specific_flags & 0x02:
        # receive last package
        result['is_last_package'] = True

    if message_type == FULL_SERVER_RESPONSE:
        payload_size = int.from_bytes(payload[:4], "big", signed=True)
        payload_msg = payload[4:]
    elif message_type == SERVER_ACK:
        seq = int.from_bytes(payload[:4], "big", signed=True)
        result['seq'] = seq
        if len(payload) >= 8:
            payload_size = int.from_bytes(payload[4:8], "big", signed=False)
            payload_msg = payload[8:]
    elif message_type == SERVER_ERROR_RESPONSE:
        code = int.from_bytes(payload[:4], "big", signed=False)
        result['code'] = code
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
    result['payload_msg'] = payload_msg
    result['payload_size'] = payload_size
    return result


def read_wav_info(data: bytes = None) -> (int, int, int, int, bytes): # type: ignore
    with BytesIO(data) as _f:
        wave_fp = wave.open(_f, 'rb')
        nchannels, sampwidth, framerate, nframes = wave_fp.getparams()[:4]
        wave_bytes = wave_fp.readframes(nframes)
    return nchannels, sampwidth, framerate, nframes, wave_bytes


def judge_wav(ori_date):
    if len(ori_date) < 44:
        return False
    if ori_date[0:4] == b"RIFF" and ori_date[8:12] == b"WAVE":
        return True
    return False


class VolcengineAsrClient:
    def __init__(self, **kwargs):
        """
        :param config: config
        """
        self.success_code = 1000  # success code, default is 1000
        self.app_id = kwargs.get("app_id", "")  # app_id
        self.access_token = kwargs.get("access_token", "")  # access_token 
        self.resource_id = kwargs.get("resource_id", "")   # resource_id
        self.seg_duration = int(kwargs.get("seg_duration", 100))
        self.ws_url = kwargs.get("ws_url", "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel")
        self.uid = kwargs.get("uid", "test")
        self.format = kwargs.get("format", "pcm")
        self.rate = kwargs.get("rate", 16000) 
        self.bits = kwargs.get("bits", 16)
        self.channel = kwargs.get("channel", 1)
        self.codec = kwargs.get("codec", "raw")
        self.auth_method = kwargs.get("auth_method", "none")
        self.hot_words = kwargs.get("hot_words", None)
        self.streaming = kwargs.get("streaming", True)
        self.mp3_seg_size = kwargs.get("mp3_seg_size", 1000)
        self.req_event = 1
        self._on_open:Callable = None
        self._on_close:Callable = None
        self._on_error:Callable = None
        self._on_transcript:Callable = None
        self.loop = None

    def on(self,on_open:Callable,on_close:Callable,on_error:Callable,on_transcript:Callable):
        self._on_open = on_open
        self._on_close = on_close
        self._on_error = on_error
        self._on_transcript = on_transcript


    def construct_request(self, reqid, data=None):
        req = {
            "user": {
                "uid": self.uid,
            },
            "audio": {
                'format': self.format,
                "sample_rate": self.rate,
                "bits": self.bits,
                "channel": self.channel,
                "codec": self.codec,
            },
            "request":{
                "model_name": "bigmodel",
                "enable_punc": True,
                "result_type": "single",
                "vad_segment_duration": 800,
            }
        }
        return req

    async def start(self):
        self.loop = asyncio.get_event_loop()  # 创建新的事件循环
        reqid = str(uuid.uuid4())
        header = {}
        # print("reqid", reqid)
        # header["X-Tt-Logid"] = reqid
        header["X-Api-Resource-Id"] = self.resource_id
        header["X-Api-Access-Key"] = self.access_token
        header["X-Api-App-Key"] = self.app_id
        header["X-Api-Request-Id"] = reqid
        self.websocket = await websockets.connect(self.ws_url, extra_headers=header, max_size=1000000000)
        if self._on_open is not None:
            await self._on_open()
        # 启动接收数据的协程
        self.loop.create_task(self.receive())
        return True

    async def receive(self):
        while True:
            try:
                message = await self.websocket.recv()
                # print(f"接收到type:{type(message)},content:{message}")
                message = parse_response(message)
                payload_msg = message.get("payload_msg")
                if payload_msg is None:
                    # print(f"payload_msg is None")
                    continue
                result = payload_msg.get("result")
                if result is None:
                    # print(f"result is None")
                    continue
                text = result.get("text")
                if len(text) == 0 :
                    continue
                utterances = result.get("utterances")
                if len(utterances) == 0:
                    # print(f"utterances len is 0")
                    continue
                first_utterance = utterances[0]
                definite = first_utterance.get("definite")
                if definite is None or definite is False:
                    # print(f"definite len is None or false")
                    continue
                if self._on_transcript is not None:
                    await self._on_transcript({
                        "text":text,
                        "is_final":definite,
                    })
            except websockets.exceptions.ConnectionClosed as e:
                print("连接已关闭")
                if self._on_error is not None:
                    await self._on_error(e)
                break
            except Exception as e:
                print(f"接收消息时发生错误: {e}")
                if self._on_error is not None:
                    await self._on_error(e)
                break
    
    async def send_full_client_request(self):
        reqid = str(uuid.uuid4())
        request_params = self.construct_request(reqid)
        payload_bytes = str.encode(json.dumps(request_params))
        payload_bytes = gzip.compress(payload_bytes)
        full_client_request = bytearray(generate_header(message_type_specific_flags=NO_SEQUENCE))
        # full_client_request.extend(generate_before_payload(sequence=seq))
        full_client_request.extend((len(payload_bytes)).to_bytes(
            4, 'big'))  # payload size(4 bytes)
        # req_str = ' '.join(format(byte, '02x') for byte in full_client_request)
        # print(f"{time.time()}, seq", seq, "req", req_str)
        full_client_request.extend(payload_bytes)  # payload
        await self.websocket.send(full_client_request)

    
    async def send(self,data:bytes):
            # if no compression, comment this line
        start = time.time()
        payload_bytes = gzip.compress(data)
        audio_only_request = bytearray(generate_header(message_type=AUDIO_ONLY_REQUEST, message_type_specific_flags=NO_SEQUENCE))
        # if last:
        #     audio_only_request = bytearray(generate_header(message_type=AUDIO_ONLY_REQUEST, message_type_specific_flags=NEG_WITH_SEQUENCE))
        # audio_only_request.extend(generate_before_payload(sequence=seq))
        audio_only_request.extend((len(payload_bytes)).to_bytes(4, 'big'))  # payload size(4 bytes)
        # req_str = ' '.join(format(byte, '02x') for byte in audio_only_request)
        # print("seq", seq, "req", req_str)
        audio_only_request.extend(payload_bytes)  # payload
        await self.websocket.send(audio_only_request)
        # print(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}, seq", seq, "res", result)
        # if 'payload_msg' in result and result['payload_msg']['code'] != self.success_code:
        #     return result
        if self.streaming:
            sleep_time = max(0, (self.seg_duration / 1000.0 - (time.time() - start)))
            await asyncio.sleep(sleep_time)
        # print(f'result:${result}')
    
    async def close(self):
        print(f"WebSocket连接关闭: {self.ws_url}")
        if self.websocket:
            await self.websocket.close()
        # if self.loop:
        #     self.loop.stop()
        if self._on_close is not None:
            await self._on_close()
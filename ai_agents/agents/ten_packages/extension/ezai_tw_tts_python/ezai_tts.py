import base64
import io
import wave
from typing import Any, AsyncIterator, Tuple

from httpx import AsyncClient, Timeout, Limits
import soundfile
import opencc
from text_utils.segmenter import SentenceSegmenter
from tn.chinese.normalizer import Normalizer as ZhNormalizer

from .config import EZAITWTTSConfig
from ten_runtime import AsyncTenEnv
from ten_ai_base.const import LOG_CATEGORY_TRANSCRIPTS, LOG_CATEGORY_VENDOR
from ten_ai_base.struct import TTS2HttpResponseEventType
from ten_ai_base.tts2_http import AsyncTTS2HttpClient


BYTES_PER_SAMPLE = 2
NUMBER_OF_CHANNELS = 1

zh_tn_model = ZhNormalizer()
converter = opencc.OpenCC("s2t.json")
segmenter = SentenceSegmenter(token_limits=15)


class EZAITWTTSClient(AsyncTTS2HttpClient):
    def __init__(
        self,
        config: EZAITWTTSConfig,
        ten_env: AsyncTenEnv,
    ):
        super().__init__()
        self.config = config
        self.api_key = config.api_key
        self.ten_env: AsyncTenEnv = ten_env
        self._is_cancelled = False
        self.endpoint = config.url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self.base_payload = {
            "language": "zh",
            "b64enc": True,
            "tw_convert": True,
            "autosplit": False,
            "speed": config.speed,
            "denoise": config.denoise,
            "speaker": config.voice,
            "zh_model": config.zh_model,
        }
        self.client = AsyncClient(
            timeout=Timeout(timeout=60.0),
            limits=Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=600.0,  # 10 minutes keepalive
            ),
            http2=True,  # Enable HTTP/2 if server supports it
        )

    async def cancel(self):
        self.ten_env.log_debug("EZAITWTTSClient: cancel() called.")
        self._is_cancelled = True

    async def get(
        self, text: str, request_id: str
    ) -> AsyncIterator[Tuple[bytes | None, TTS2HttpResponseEventType]]:
        """Process a single TTS request in serial manner"""
        self._is_cancelled = False
        if not self.client:
            self.ten_env.log_error(
                f"EZAITWTTSClient: client not initialized for request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            raise RuntimeError(
                f"EZAITWTTSClient: client not initialized for request_id: {request_id}."
            )

        if len(text.strip()) == 0:
            self.ten_env.log_warn(
                f"EZAITWTTSClient: empty text for request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            yield None, TTS2HttpResponseEventType.END
            return

        try:
            # Pre-process text: normalize → Simplified-to-Traditional → segment sentences
            normalized = zh_tn_model.normalize(text)
            normalized = converter.convert(normalized)
            sentences = []
            for line in normalized.splitlines():
                sentences.extend(segmenter.segment(line))

            for sent in sentences:
                if self._is_cancelled:
                    self.ten_env.log_debug(
                        f"Cancellation flag detected, sending flush event and stopping TTS stream of request_id: {request_id}."
                    )
                    yield None, TTS2HttpResponseEventType.FLUSH
                    return

                payload = {**self.base_payload, "text": sent}

                response = await self.client.post(
                    self.endpoint,
                    headers=self.headers,
                    json=payload,
                )

                self.ten_env.log_debug(
                    f"EZAITWTTSClient: sending EVENT_TTS_RESPONSE, length: {len(response.content)} of request_id: {request_id}."
                )

                if response.status_code != 200:
                    raise RuntimeError(
                        "401 "
                        if response.status_code in (401, 403)
                        else f"HTTP {response.status_code}: {response.text}"
                    )

                j = response.json()
                if "audio" not in j:
                    raise RuntimeError(
                        "No audio returned from EZAI TTS service"
                    )

                # Decode WAV (PCM24) → PCM16 raw frames
                audio_bytes = base64.b64decode(j["audio"])
                pcm16_bytes = self.pcm24topcm16(audio_bytes)
                self.ten_env.log_info(
                    f"EZAITWTTSClient: tts input:|{sent}| output:{j.get('text', '')}",
                    category=LOG_CATEGORY_TRANSCRIPTS,
                )

                if len(pcm16_bytes) > 0:
                    yield bytes(pcm16_bytes), TTS2HttpResponseEventType.RESPONSE
                else:
                    yield None, TTS2HttpResponseEventType.END

            if not self._is_cancelled:
                self.ten_env.log_debug(
                    f"EZAITWTTSClient: sending EVENT_TTS_END of request_id: {request_id}."
                )
                yield None, TTS2HttpResponseEventType.END

        except Exception as e:
            # Check if it's an API key authentication error
            error_message = str(e)
            self.ten_env.log_error(
                f"vendor_error: {error_message} of request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            if "401" in error_message:
                yield error_message.encode(
                    "utf-8"
                ), TTS2HttpResponseEventType.INVALID_KEY_ERROR
            else:
                yield error_message.encode(
                    "utf-8"
                ), TTS2HttpResponseEventType.ERROR

    async def clean(self):
        # In this new model, most cleanup is handled by the connection object's lifecycle.
        # This can be used for any additional cleanup if needed.
        self.ten_env.log_debug("EZAITWTTSClient: clean() called.")
        try:
            await self.client.aclose()
        finally:
            pass

    def get_extra_metadata(self) -> dict[str, Any]:
        """Return extra metadata for TTFB metrics."""
        return {
            "speaker": getattr(self.config, "voice", ""),
        }

    def pcm24topcm16(self, audio_bytes):
        pcm24io = io.BytesIO(audio_bytes)
        pcm24io.name = "pcm24.wav"
        data, samplerate = soundfile.read(pcm24io)
        newio = io.BytesIO()
        newio.name = "file16.wav"
        soundfile.write(newio, data, samplerate, subtype="PCM_16")
        newio.seek(0)

        with wave.open(newio) as w:
            chunk = w.readframes(w.getnframes())
        return chunk

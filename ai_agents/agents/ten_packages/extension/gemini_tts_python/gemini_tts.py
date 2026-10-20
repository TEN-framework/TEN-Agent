import base64
from typing import AsyncIterator, Tuple, Any
from google import genai
from ten_runtime import AsyncTenEnv
from ten_ai_base.tts2_http import AsyncTTS2HttpClient
from ten_ai_base.struct import TTS2HttpResponseEventType
from ten_ai_base.const import LOG_CATEGORY_TRANSCRIPTS, LOG_CATEGORY_VENDOR
from .config import GeminiTTSConfig


class GeminiTTSClient(AsyncTTS2HttpClient):
    def __init__(
        self,
        config: GeminiTTSConfig,
        ten_env: AsyncTenEnv,
    ):
        super().__init__()
        self.config: GeminiTTSConfig = config
        self.ten_env: AsyncTenEnv = ten_env
        self.client = None
        self._is_cancelled = False

    async def get(
        self, text: str, request_id: str
    ) -> AsyncIterator[Tuple[bytes | None, TTS2HttpResponseEventType]]:
        """Generate TTS audio for the given text using Gemini API"""

        if self._is_cancelled:
            self.ten_env.log_debug("Request cancelled before starting")
            return

        try:
            # Initialize Gemini client
            if not self.client:
                api_key = self.config.params.get("api_key")
                self.client = genai.Client(api_key=api_key)
                self.ten_env.log_debug("Gemini TTS client initialized")

            # Prepare request parameters
            model = self.config.params.get(
                "model", "gemini-2.5-flash-preview-tts"
            )
            voice = self.config.params.get("voice", "Kore")
            language_code = self.config.params.get("language_code", "en-US")
            style_prompt = self.config.params.get("style_prompt", "")

            # Build speech config
            speech_config = {
                "voice_config": {"prebuilt_voice_config": {"voice_name": voice}}
            }

            # Build generation config
            generation_config = {
                "response_modalities": ["AUDIO"],
                "speech_config": speech_config,
            }

            self.ten_env.log_debug(
                f"Generating speech: text_length={len(text)} "
                f"(model: {model}, voice: {voice}, "
                f"language: {language_code})"
            )
            self.ten_env.log_debug(
                f"Generating speech for text: '{text[:100]}...'",
                category=LOG_CATEGORY_TRANSCRIPTS,
            )

            # Prepare contents
            contents = text
            if style_prompt:
                contents = f"{style_prompt}\n\n{text}"

            # Make API request
            response = self.client.models.generate_content(
                model=model,
                contents=contents,
                config=generation_config,
            )

            # Extract audio data from response
            if (
                response.candidates
                and len(response.candidates) > 0
                and response.candidates[0].content.parts
                and len(response.candidates[0].content.parts) > 0
            ):
                part = response.candidates[0].content.parts[0]

                if hasattr(part, "inline_data") and part.inline_data:
                    # Decode base64 audio data
                    audio_bytes = base64.b64decode(part.inline_data.data)

                    if self._is_cancelled:
                        self.ten_env.log_debug(
                            "Request cancelled after receiving response"
                        )
                        return

                    self.ten_env.log_debug(
                        f"Received {len(audio_bytes)} bytes of audio data"
                    )

                    # Yield audio data
                    yield audio_bytes, TTS2HttpResponseEventType.RESPONSE

                    # Signal completion
                    yield None, TTS2HttpResponseEventType.END
                else:
                    error_msg = "No audio data in response from Gemini TTS"
                    self.ten_env.log_error(error_msg)
                    yield error_msg.encode(
                        "utf-8"
                    ), TTS2HttpResponseEventType.ERROR
            else:
                error_msg = "Empty response received from Gemini TTS"
                self.ten_env.log_error(error_msg)
                yield error_msg.encode("utf-8"), TTS2HttpResponseEventType.ERROR

        except Exception as e:
            error_message = str(e)
            self.ten_env.log_error(
                f"vendor_error: reason_type={type(e).__name__}",
                category=LOG_CATEGORY_VENDOR,
            )
            self.ten_env.log_debug(
                f"vendor_error details: {error_message}",
                category=LOG_CATEGORY_TRANSCRIPTS,
            )

            # Check if it's an authentication error
            if (
                "401" in error_message
                or "403" in error_message
                or "authentication" in error_message.lower()
                or "api_key" in error_message.lower()
                or "unauthorized" in error_message.lower()
            ):
                yield error_message.encode(
                    "utf-8"
                ), TTS2HttpResponseEventType.INVALID_KEY_ERROR
            else:
                yield error_message.encode(
                    "utf-8"
                ), TTS2HttpResponseEventType.ERROR

    async def cancel(self):
        """Cancel ongoing request"""
        self.ten_env.log_info("Cancelling Gemini TTS request")
        self._is_cancelled = True

    async def clean(self):
        """Clean up resources"""
        self.ten_env.log_info("Cleaning up Gemini TTS client")
        self._is_cancelled = False
        self.client = None

    def get_extra_metadata(self) -> dict[str, Any]:
        """Return model/voice for TTFB metrics"""
        return {
            "model": self.config.params.get("model"),
            "voice": self.config.params.get("voice"),
        }

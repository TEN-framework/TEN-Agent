import asyncio
from typing import AsyncIterator, Iterator
from google.cloud import texttospeech
from google.api_core.client_options import ClientOptions
from ten_runtime import AsyncTenEnv
from .config import GoogleTTSConfig
from google.oauth2 import service_account
import json
import time
from ten_ai_base.const import LOG_CATEGORY_TRANSCRIPTS, LOG_CATEGORY_VENDOR

# Custom event types to communicate status back to the extension
EVENT_TTS_RESPONSE = 1
EVENT_TTS_REQUEST_END = 2
EVENT_TTS_ERROR = 3
EVENT_TTS_INVALID_KEY_ERROR = 4
EVENT_TTS_FLUSH = 5


class GoogleTTS:
    def __init__(
        self,
        config: GoogleTTSConfig,
        ten_env: AsyncTenEnv,
    ):
        self.config = config
        self.ten_env = ten_env
        self.client = None
        self._initialize_client()
        self.credentials = None
        self.send_text_in_connection = False
        self.cur_request_id = ""
        self.streaming_enabled = False
        self.streaming_config = None
        self._should_stop_streaming = False

    def _initialize_client(self):
        """Initialize Google TTS client with credentials"""
        try:
            # Parse JSON credentials
            try:
                self.credentials = json.loads(self.config.credentials)
                self.ten_env.log_info("JSON credentials parsed successfully")
            except json.JSONDecodeError as e:
                self.ten_env.log_error(f"Failed to parse credentials JSON: {e}")
                # pylint: disable=raise-missing-from
                raise ValueError(f"Invalid JSON format in credentials: {e}")

            # Validate required fields
            required_fields = [
                "type",
                "project_id",
                "private_key_id",
                "private_key",
                "client_email",
                "client_id",
            ]
            missing_fields = [
                field
                for field in required_fields
                if field not in self.credentials
            ]
            if missing_fields:
                self.ten_env.log_error(
                    f"Missing required fields in credentials: {missing_fields}"
                )
                raise ValueError(
                    f"Missing required fields in credentials: {missing_fields}"
                )

            # Create credentials object
            try:
                credentials = (
                    service_account.Credentials.from_service_account_info(
                        self.credentials
                    )
                )
                self.ten_env.log_info(
                    "Service account credentials created successfully"
                )
                self.send_text_in_connection = False
            except Exception as e:
                self.ten_env.log_error(
                    f"Failed to create service account credentials: {e}"
                )
                # pylint: disable=raise-missing-from
                raise ValueError(f"Invalid credentials format: {e}")

            # Check for custom API endpoint in params
            api_endpoint = self.config.params.get("api_endpoint")
            client_options = None
            if api_endpoint:
                client_options = ClientOptions(api_endpoint=api_endpoint)
                self.ten_env.log_info(
                    f"Using custom API endpoint: {api_endpoint}"
                )

            # Create TTS client
            if client_options:
                self.client = texttospeech.TextToSpeechClient(
                    credentials=credentials, client_options=client_options
                )
            else:
                self.client = texttospeech.TextToSpeechClient(
                    credentials=credentials
                )
            self.ten_env.log_debug("Google TTS client initialized successfully")

        except Exception as e:
            self.ten_env.log_error(
                f"Failed to initialize Google TTS client: {e}"
            )
            raise

    def _get_ssml_gender_from_params(
        self, ssml_gender: str = None
    ) -> texttospeech.SsmlVoiceGender:
        """Convert string gender from params to Google TTS enum"""
        gender_map = {
            "NEUTRAL": texttospeech.SsmlVoiceGender.NEUTRAL,
            "MALE": texttospeech.SsmlVoiceGender.MALE,
            "FEMALE": texttospeech.SsmlVoiceGender.FEMALE,
            "UNSPECIFIED": texttospeech.SsmlVoiceGender.SSML_VOICE_GENDER_UNSPECIFIED,
        }
        if ssml_gender is None:
            ssml_gender = "NEUTRAL"
        return gender_map.get(
            ssml_gender.upper(), texttospeech.SsmlVoiceGender.NEUTRAL
        )

    def _create_streaming_config(
        self,
    ) -> texttospeech.StreamingSynthesizeConfig:
        """Create streaming configuration from config params"""
        # Build the voice request from VoiceSelectionParams
        voice_params = self.config.params.get("VoiceSelectionParams", {})

        # Get language code and set default voice name based on language
        language_code = voice_params.get("language_code", "en-US")

        voice_name = voice_params.get("name")
        self.ten_env.log_debug(
            f"Using voice: {voice_name} for language: {language_code}"
        )

        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            ssml_gender=self._get_ssml_gender_from_params(
                voice_params.get("ssml_gender")
            ),
            name=voice_name,  # Always specify a voice name
        )

        # Add optional voice parameters
        if voice_params.get("custom_voice"):
            voice.custom_voice = voice_params.get("custom_voice")
        if voice_params.get("voice_clone"):
            voice.voice_clone = voice_params.get("voice_clone")

        # Get audio parameters for streaming audio config
        audio_params = self.config.params.get("AudioConfig", {})

        streaming_audio_config = texttospeech.StreamingAudioConfig(
            audio_encoding=texttospeech.AudioEncoding.PCM
        )

        # Add sample_rate if specified, otherwise use default
        if audio_params.get("sample_rate_hertz"):
            streaming_audio_config.sample_rate_hertz = audio_params.get(
                "sample_rate_hertz"
            )

        # Add optional audio parameters
        if audio_params.get("speaking_rate") is not None:
            streaming_audio_config.speaking_rate = audio_params.get(
                "speaking_rate"
            )

        return texttospeech.StreamingSynthesizeConfig(
            voice=voice, streaming_audio_config=streaming_audio_config
        )

    def _create_request_generator(
        self, text: str
    ) -> Iterator[texttospeech.StreamingSynthesizeRequest]:
        """Create request generator for streaming synthesis"""
        # First request contains the config
        config_request = texttospeech.StreamingSynthesizeRequest(
            streaming_config=self.streaming_config
        )
        yield config_request

        # Split text into chunks for streaming (optional - can send as single chunk)
        # For now, we'll send the entire text as one chunk, but this can be optimized
        text_chunks = [
            text
        ]  # Can be modified to split text into smaller chunks

        for chunk in text_chunks:
            if chunk.strip():  # Only send non-empty chunks
                yield texttospeech.StreamingSynthesizeRequest(
                    input=texttospeech.StreamingSynthesisInput(text=chunk)
                )

    async def get_streaming(
        self, text: str, request_id: str
    ) -> AsyncIterator[tuple[bytes | None, int, int | None]]:
        """Generate TTS audio using streaming synthesis for the given text"""

        if not self.client:
            error_msg = "Google TTS client not initialized"
            self.ten_env.log_error(error_msg)
            yield error_msg.encode("utf-8"), EVENT_TTS_ERROR
            return

        # Initialize streaming config if not already done
        if not self.streaming_config:
            self.streaming_config = self._create_streaming_config()

        # Retry configuration
        max_retries = 3
        retry_delay = 1.0  # seconds

        # Retry loop for network issues
        for attempt in range(max_retries):
            ttfb_ms = None
            try:
                start_ts = None
                if request_id != self.cur_request_id:
                    start_ts = time.time()
                    self.cur_request_id = request_id

                # Create request generator
                request_generator = self._create_request_generator(text)

                # Debug: Log the request details
                self.ten_env.log_debug(
                    f"Starting streaming synthesis for text: '{text[:100]}...' (request_id: {request_id})",
                    category=LOG_CATEGORY_TRANSCRIPTS,
                )

                # Perform the streaming text-to-speech request
                try:
                    streaming_responses = self.client.streaming_synthesize(
                        request_generator
                    )
                except Exception as e:
                    self.ten_env.log_error(
                        f"Error calling streaming_synthesize: {e}"
                    )
                    raise

                if start_ts is not None:
                    ttfb_ms = int((time.time() - start_ts) * 1000)
                self.send_text_in_connection = True

                # Process streaming responses
                audio_received = False
                try:
                    for response in streaming_responses:
                        # Check if we should stop streaming
                        if self._should_stop_streaming:
                            self.ten_env.log_debug(
                                "Stopping streaming synthesis due to flush request"
                            )
                            break

                        if response.audio_content:
                            audio_received = True
                            yield response.audio_content, EVENT_TTS_RESPONSE, ttfb_ms
                            # Reset ttfb_ms after first chunk
                            ttfb_ms = None

                        # Yield control to event loop to allow on_data to process flush messages
                        await asyncio.sleep(0)
                except Exception as e:
                    self.ten_env.log_error(
                        f"Error processing streaming responses: {e}"
                    )
                    raise

                if audio_received:
                    yield None, EVENT_TTS_REQUEST_END, ttfb_ms
                    return  # Success, exit retry loop
                else:
                    error_msg = (
                        "No audio content received from Google TTS streaming"
                    )
                    yield error_msg.encode("utf-8"), EVENT_TTS_ERROR, ttfb_ms
                    return

            except Exception as e:
                error_message = str(e)
                self.ten_env.log_error(
                    f"vendor_error: reason: {error_message}",
                    category=LOG_CATEGORY_VENDOR,
                )

                # Check if it's a retryable network error
                is_retryable = (
                    ("503" in error_message and "UNAVAILABLE" in error_message)
                    or ("failed to connect" in error_message.lower())
                    or ("socket closed" in error_message.lower())
                    or ("timeout" in error_message.lower())
                )

                if is_retryable and attempt < max_retries - 1:
                    self.ten_env.log_debug(
                        f"Network error (attempt {attempt + 1}/{max_retries}): {error_message}"
                    )
                    self.ten_env.log_debug(
                        f"Retrying in {retry_delay} seconds..."
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    # Final attempt failed or non-retryable error
                    self.ten_env.log_error(
                        f"Google TTS streaming synthesis failed: {e}"
                    )

                    # Check if it's an authentication error
                    if (
                        (
                            "401" in error_message
                            and "Unauthorized" in error_message
                        )
                        or (
                            "403" in error_message
                            and "Forbidden" in error_message
                        )
                        or ("authentication" in error_message.lower())
                        or ("credentials" in error_message.lower())
                    ):
                        yield error_message.encode(
                            "utf-8"
                        ), EVENT_TTS_INVALID_KEY_ERROR, ttfb_ms
                    # Check if it's a network error
                    elif (
                        (
                            "503" in error_message
                            and "UNAVAILABLE" in error_message
                        )
                        or ("failed to connect" in error_message.lower())
                        or ("socket closed" in error_message.lower())
                        or ("network" in error_message.lower())
                    ):
                        network_error = f"Network connection failed after {max_retries} attempts: {error_message}. Please check your internet connection and Google Cloud service availability."
                        yield network_error.encode(
                            "utf-8"
                        ), EVENT_TTS_ERROR, ttfb_ms
                    else:
                        yield error_message.encode(
                            "utf-8"
                        ), EVENT_TTS_ERROR, ttfb_ms
                    return

    async def get(
        self, text: str, request_id: str
    ) -> AsyncIterator[tuple[bytes | None, int, int | None]]:
        """Generate TTS audio for the given text using streaming synthesis"""

        # Use streaming synthesis by default
        async for result in self.get_streaming(text, request_id):
            yield result

    def clean(self):
        """Clean up resources"""
        self.ten_env.log_info("GoogleTTS: clean() called.")
        # Set flag to stop any ongoing streaming
        self._should_stop_streaming = True
        if self.client:
            self.client = None
            self.ten_env.log_debug("Google TTS client cleaned")
        # Reset streaming config
        self.streaming_config = None

    async def reset(self):
        """Reset the client"""
        self.ten_env.log_info("Resetting Google TTS client")
        self.client = None
        self.streaming_config = None
        # Reset the stop flag for new requests
        self._should_stop_streaming = False
        self._initialize_client()
        self.ten_env.log_debug("Google TTS client reset completed")

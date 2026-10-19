import asyncio
import os
import json
from collections.abc import Awaitable, Callable

from google.cloud import speech_v2 as speech
from google.cloud.speech_v2.types import (
    StreamingRecognitionConfig,
    StreamingRecognizeRequest,
)

from ten_ai_base.const import (
    LOG_CATEGORY_VENDOR,
    LOG_CATEGORY_TRANSCRIPTS,
)

from google.api_core import exceptions as gcp_exceptions
from google.api_core.client_options import ClientOptions
import grpc
from google.oauth2 import service_account

from ten_ai_base.struct import ASRResult, ASRWord

from ten_runtime import AsyncTenEnv

from .config import GoogleASRConfig


class GoogleASRClient:
    """Google Cloud Speech-to-Text V2 streaming client"""

    def __init__(
        self,
        config: GoogleASRConfig,
        ten_env: AsyncTenEnv,
        on_result_callback: Callable[[ASRResult], Awaitable[None]],
        on_error_callback: Callable[[int, str], Awaitable[None]],
    ):
        self.config = config
        self.ten_env = ten_env
        self.on_result_callback = on_result_callback
        self.on_error_callback = on_error_callback

        self.speech_client: speech.SpeechAsyncClient | None = None
        self._audio_queue: asyncio.Queue = asyncio.Queue()
        self._recognition_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self.is_finalizing = False
        self._has_sent_final_result = False
        self._stream_start_time: float = 0.0
        self._restarting: bool = False

    def _normalize_language_code(self, code: str | None) -> str:
        """Normalize provider language codes to framework-expected ones.

        - Map Google V2 Chinese codes like `cmn-Hans-CN`/`cmn-Hans` to `zh-CN`
        - Preserve known English code `en-US`
        - Fallback to original code if no mapping is needed
        """
        if not code:
            return ""
        lowered = code.strip()
        if lowered.startswith("cmn-Hans"):
            return "zh-CN"
        return lowered

    async def start(self, session_id: str | None) -> None:
        """Initializes the client and starts the recognition stream."""
        self.ten_env.log_info("Starting Google ASR client...")
        try:
            await self._initialize_google_client()
            self._stop_event.clear()
            self.is_finalizing = False
            self._recognition_task = asyncio.create_task(
                self._run_recognition()
            )
            self.ten_env.log_info(
                f"vendor_status_changed: start, session_id: {session_id}",
                category=LOG_CATEGORY_VENDOR,
            )
        except Exception as e:
            self.ten_env.log_error(f"Failed to start Google ASR client: {e}")
            await self.on_error_callback(
                500, f"Failed to start client: {str(e)}"
            )
            raise

    async def _initialize_google_client(self) -> None:
        """Initializes the Google Speech async client using ADC."""
        try:
            # Check credentials from config or environment
            credentials_path = self.config.adc_credentials_path or os.getenv(
                "GOOGLE_APPLICATION_CREDENTIALS"
            )
            credentials_string = getattr(
                self.config, "adc_credentials_string", ""
            ) or os.getenv("GOOGLE_APPLICATION_CREDENTIALS_STRING", "")

            self.ten_env.log_debug(f"ADC credentials path: {credentials_path}")
            if credentials_string:
                # Do not log raw credential content
                self.ten_env.log_debug("ADC credentials JSON string provided.")

            if credentials_path:
                self.ten_env.log_debug(
                    f"Using Service Account credentials from: {credentials_path}"
                )
                if not os.path.exists(credentials_path):
                    raise FileNotFoundError(
                        f"Service Account file not found: {credentials_path}"
                    )

                # Set the environment variable for Google Cloud SDK
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
            elif credentials_string:
                # Build credentials directly from JSON string (no temp file needed)
                try:
                    service_account_info = json.loads(credentials_string)
                    credentials = (
                        service_account.Credentials.from_service_account_info(
                            service_account_info
                        )
                    )
                except Exception as cred_err:
                    raise ValueError(
                        f"Invalid adc_credentials_string JSON: {cred_err}"
                    ) from cred_err
            else:
                self.ten_env.log_info(
                    "No ADC credentials path specified, using default ADC"
                )

            # Choose regional endpoint if location is set and not global
            api_endpoint: str | None = None
            if (
                getattr(self.config, "location", "global")
                and self.config.location != "global"
            ):
                api_endpoint = f"{self.config.location}-speech.googleapis.com"
                self.ten_env.log_info(
                    f"Using regional endpoint: {api_endpoint}"
                )

            client_options = (
                ClientOptions(api_endpoint=api_endpoint)
                if api_endpoint
                else None
            )

            # Create client with the determined credentials
            # Priority: path > JSON string > default ADC
            if credentials_path:
                from google.auth import default

                adc_credentials, _project = default()
                if client_options:
                    self.speech_client = speech.SpeechAsyncClient(
                        credentials=adc_credentials,
                        client_options=client_options,
                    )
                else:
                    self.speech_client = speech.SpeechAsyncClient(
                        credentials=adc_credentials
                    )
                self.ten_env.log_info(
                    "Initialized Google Speech V2 client with explicit credentials"
                )
            elif credentials_string:
                if client_options:
                    self.speech_client = speech.SpeechAsyncClient(
                        credentials=credentials, client_options=client_options
                    )
                else:
                    self.speech_client = speech.SpeechAsyncClient(
                        credentials=credentials
                    )
                self.ten_env.log_info(
                    "Initialized Google Speech V2 client with explicit credentials"
                )
            else:
                # Use default ADC
                if client_options:
                    self.speech_client = speech.SpeechAsyncClient(
                        client_options=client_options
                    )
                else:
                    self.speech_client = speech.SpeechAsyncClient()
                self.ten_env.log_info(
                    "Initialized Google Speech V2 client with Application Default Credentials"
                )
        except Exception as e:
            self.ten_env.log_error(
                f"Failed to initialize Google Speech client: {e}"
            )
            raise

    async def stop(self, session_id: str | None) -> None:
        """Stops the recognition stream and cleans up resources."""
        self.ten_env.log_info("Stopping Google ASR client...")
        self._restarting = (
            False  # Ensure we don't restart after an explicit stop
        )
        if self._recognition_task and not self._recognition_task.done():
            self._stop_event.set()
            # Drain the queue to unblock the generator
            while not self._audio_queue.empty():
                try:
                    await self._audio_queue.get()
                except Exception:
                    break
            await self._audio_queue.put(None)  # Signal generator to stop
            try:
                await asyncio.wait_for(self._recognition_task, timeout=1.0)
            except asyncio.TimeoutError:
                self.ten_env.log_warn(
                    "Recognition task did not stop gracefully, cancelling."
                )
                self._recognition_task.cancel()
        self.speech_client = None
        self.ten_env.log_info(
            f"vendor_status_changed: stoped, session_id: {session_id}",
            category=LOG_CATEGORY_VENDOR,
        )

    async def send_audio(self, chunk: bytes) -> None:
        """Adds an audio chunk to the processing queue."""
        if not self._stop_event.is_set():
            await self._audio_queue.put(chunk)

    async def finalize(self) -> None:
        """Signals that the current utterance is complete by sending silence packets."""
        self.ten_env.log_debug("Finalizing utterance with silence packets.")
        self.is_finalizing = True

        # Generate silence packets to trigger final recognition
        silence_duration = (
            self.config.finalize_grace_seconds
        )  # Default 0.5 seconds
        sample_rate = self.config.sample_rate
        channels = self.config.channels

        # Calculate number of samples needed for silence duration
        samples_needed = int(silence_duration * sample_rate)

        # Generate silence data (16-bit PCM, 0 amplitude)
        silence_data = b"\x00\x00" * samples_needed * channels

        # Send silence packets in chunks to simulate natural audio flow
        chunk_size = int(sample_rate * 0.1) * channels * 2  # 100ms chunks
        for i in range(0, len(silence_data), chunk_size):
            chunk = silence_data[i : i + chunk_size]
            if not self._stop_event.is_set():
                await self._audio_queue.put(chunk)
                # Small delay between chunks to simulate real audio timing
                await asyncio.sleep(0.01)

    async def _audio_generator(self):
        """Yields audio chunks from the queue for the gRPC stream."""
        try:
            # First request contains the configuration
            config = self.config.get_recognition_config()
            streaming_config = StreamingRecognitionConfig(
                config=config,
                streaming_features={
                    "interim_results": self.config.interim_results,
                },
            )
            recognizer_path = self.config.get_recognizer_path()
            if getattr(self.config, "enable_detailed_logging", False):
                self.ten_env.log_debug(f"Streaming config: {streaming_config}")

            # First request must contain recognizer and streaming_config, not audio
            # recognizer format: projects/{project}/locations/{location}/recognizers/{recognizer}
            # According to Google Cloud Speech V2 docs, recognizer is required
            recognizer_path = self.config.get_recognizer_path()
            if recognizer_path:
                self.ten_env.log_debug(f"Using recognizer: {recognizer_path}")
                yield StreamingRecognizeRequest(
                    recognizer=recognizer_path,
                    streaming_config=streaming_config,
                )
            else:
                # If no recognizer path, we need to get project_id from ADC
                # This is a fallback for when project_id is not provided in config
                self.ten_env.log_error(
                    "No recognizer path available. Please provide project_id in config."
                )
                raise ValueError(
                    "Recognizer path is required for Google Cloud Speech V2 API"
                )

            while not self._stop_event.is_set():
                chunk = await self._audio_queue.get()
                if chunk is None:
                    self.ten_env.log_debug("Received end-of-stream signal")
                    break
                yield speech.StreamingRecognizeRequest(audio=chunk)
        except Exception as e:
            self.ten_env.log_error(f"Error in audio generator: {e}")
            await self.on_error_callback(500, str(e))

    async def _run_recognition(self) -> None:
        """Run the streaming recognition loop with retry and restart logic."""
        while not self._stop_event.is_set():
            retry_count = 0
            self._restarting = False
            self._stream_start_time = asyncio.get_event_loop().time()

            while (
                not self._stop_event.is_set()
                and not self._restarting
                and retry_count < self.config.max_retry_attempts
            ):
                try:
                    if not self.speech_client:
                        raise ConnectionError(
                            "Google Speech client is not initialized."
                        )

                    requests = self._audio_generator()
                    self.ten_env.log_info("Starting streaming recognition...")

                    responses = await self.speech_client.streaming_recognize(
                        requests=requests
                    )

                    async for response in responses:
                        if self._stop_event.is_set() or self._restarting:
                            break

                        elapsed_time = (
                            asyncio.get_event_loop().time()
                            - self._stream_start_time
                        )
                        if elapsed_time > self.config.stream_max_duration:
                            self.ten_env.log_warn(
                                f"Stream duration limit ({self.config.stream_max_duration}s) reached. Restarting stream."
                            )
                            self._restarting = True
                            break

                        await self._process_response(response)

                    if not self._restarting:
                        # If the loop finishes without exceptions, reset retry count
                        retry_count = 0

                except (gcp_exceptions.GoogleAPICallError, grpc.RpcError) as e:
                    error_code = 500
                    error_message = str(e)
                    await self.on_error_callback(error_code, error_message)

                    if self._is_retryable_error(e):
                        retry_count += 1
                        self.ten_env.log_warn(
                            f"Retryable error encountered. Attempt {retry_count}/{self.config.max_retry_attempts}. Retrying in {self.config.retry_delay}s..."
                        )
                        await asyncio.sleep(self.config.retry_delay)
                    else:
                        self.ten_env.log_error(
                            "Non-retryable error encountered. Stopping recognition."
                        )
                        self._stop_event.set()  # Stop on non-retryable error
                        break
                except Exception as e:
                    self.ten_env.log_error(
                        f"Unexpected error in recognition loop: {e}"
                    )
                    await self.on_error_callback(500, str(e))
                    self._stop_event.set()  # Stop on other unexpected errors
                    break

            if self.is_finalizing and not self._restarting:
                break

            if self._restarting:
                self.ten_env.log_info("Restarting recognition stream...")
                await asyncio.sleep(1)  # Brief pause before restarting
            else:
                break

    async def _process_response(
        self, response: speech.StreamingRecognizeResponse
    ) -> None:
        """Process a streaming recognition response and trigger callbacks."""
        for result in response.results:
            if not result.alternatives:
                self.ten_env.log_debug("Skipping result with no alternatives")
                continue

            # We'll use the first alternative as the primary result.
            first_alt = result.alternatives[0]
            words = []
            for w in first_alt.words:
                start_ms = int(w.start_offset.total_seconds() * 1000)
                duration_ms = int(
                    (w.end_offset - w.start_offset).total_seconds() * 1000
                )
                # Align with ASRWord schema used elsewhere in the project
                words.append(
                    ASRWord(
                        word=w.word,
                        start_ms=start_ms,
                        duration_ms=duration_ms,
                        stable=bool(result.is_final),
                    )
                )

            normalized_lang = self._normalize_language_code(
                result.language_code
            )
            if not normalized_lang:
                normalized_lang = self._normalize_language_code(
                    self.config.language
                )

            self.ten_env.log_debug(
                f"vendor_result: on_recognized: {first_alt.transcript}, language: {normalized_lang}, full_json: {result}",
                category=LOG_CATEGORY_TRANSCRIPTS,
            )

            asr_result = ASRResult(
                final=result.is_final,
                text=first_alt.transcript,
                words=words,
                confidence=first_alt.confidence,
                language=normalized_lang,
                start_ms=(int(words[0].start_ms) if words else 0),
                duration_ms=(
                    int(result.result_end_offset.total_seconds() * 1000)
                    if hasattr(result, "result_end_offset")
                    and result.result_end_offset
                    else 0
                ),
            )
            await self.on_result_callback(asr_result)
            if result.is_final:
                self._has_sent_final_result = True

    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if a gRPC/API error is retryable."""
        if isinstance(error, gcp_exceptions.RetryError):
            return True
        if isinstance(error, grpc.RpcError):
            # List of retryable gRPC status codes
            retryable_codes = [
                grpc.StatusCode.UNAVAILABLE,
                grpc.StatusCode.DEADLINE_EXCEEDED,
                grpc.StatusCode.RESOURCE_EXHAUSTED,
                grpc.StatusCode.INTERNAL,
            ]
            # Don't retry permission denied errors
            if error.code() == grpc.StatusCode.PERMISSION_DENIED:
                return False
            return error.code() in retryable_codes
        return False

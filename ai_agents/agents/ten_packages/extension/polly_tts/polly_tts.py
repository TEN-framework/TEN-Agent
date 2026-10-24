import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from typing import Any, AsyncIterator, Iterator, Tuple

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError
from ten_runtime import AsyncTenEnv
from ten_ai_base.const import LOG_CATEGORY_VENDOR
from ten_ai_base.struct import TTS2HttpResponseEventType
from ten_ai_base.tts2_http import AsyncTTS2HttpClient

from .config import PollyTTSConfig


class PollyTTSClient(AsyncTTS2HttpClient):
    def __init__(
        self,
        config: PollyTTSConfig,
        ten_env: AsyncTenEnv,
    ):
        super().__init__()
        self.config = config
        self.ten_env: AsyncTenEnv = ten_env
        self._is_cancelled = False

        # Get sample rate for frame size calculation
        sample_rate = int(config.params.get("sample_rate", "16000"))
        chunk_interval_ms = 50  # Hardcoded chunk interval
        self.frame_size = int(sample_rate * 1 * 2 * chunk_interval_ms / 1000)

        self.thread_pool = ThreadPoolExecutor(max_workers=1)
        self._closed = False

        # Build session params
        session_params = {}
        if config.params.get("aws_access_key_id"):
            session_params["aws_access_key_id"] = config.params[
                "aws_access_key_id"
            ]
        if config.params.get("aws_secret_access_key"):
            session_params["aws_secret_access_key"] = config.params[
                "aws_secret_access_key"
            ]
        if config.params.get("aws_session_token"):
            session_params["aws_session_token"] = config.params[
                "aws_session_token"
            ]
        if config.params.get("region_name"):
            session_params["region_name"] = config.params["region_name"]
        if config.params.get("profile_name"):
            session_params["profile_name"] = config.params["profile_name"]
        if config.params.get("aws_account_id"):
            session_params["aws_account_id"] = config.params["aws_account_id"]

        try:
            self.session = boto3.Session(**session_params)
            client_config = Config(tcp_keepalive=True)
            client_params = {"service_name": "polly", "config": client_config}
            # Add endpoint_url if provided
            if config.params.get("endpoint_url"):
                client_params["endpoint_url"] = config.params["endpoint_url"]
            self.client = self.session.client(**client_params)
        except NoCredentialsError as e:
            ten_env.log_error(
                f"error when initializing PollyTTS: {e}",
                category=LOG_CATEGORY_VENDOR,
            )
            raise ValueError(f"error when initializing PollyTTS: {e}") from e

    async def cancel(self):
        self.ten_env.log_debug("PollyTTS: cancel() called.")
        self._is_cancelled = True

    async def get(
        self, text: str, request_id: str
    ) -> AsyncIterator[Tuple[bytes | None, TTS2HttpResponseEventType]]:
        """Process a single TTS request"""
        self._is_cancelled = False
        if not self.client:
            self.ten_env.log_error(
                f"PollyTTS: client not initialized for request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            raise RuntimeError(
                f"PollyTTS: client not initialized for request_id: {request_id}."
            )

        if len(text.strip()) == 0:
            self.ten_env.log_warn(
                f"PollyTTS: empty text for request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            yield None, TTS2HttpResponseEventType.END
            return

        try:
            # Build synthesize speech params
            synthesize_params = {
                "Text": text,
                "Engine": self.config.params.get("engine", "neural"),
                "VoiceId": self.config.params.get("voice", "Joanna"),
                "OutputFormat": self.config.params.get("audio_format", "pcm"),
                "SampleRate": str(
                    self.config.params.get("sample_rate", "16000")
                ),
                "LanguageCode": self.config.params.get("lang_code", "en-US"),
            }

            # Synthesize speech
            sync_iter = self._synthesize_speech(synthesize_params)
            async for chunk in self._async_iter_from_sync(sync_iter):
                if self._is_cancelled:
                    self.ten_env.log_debug(
                        f"Cancellation flag detected, sending flush event and stopping TTS stream of request_id: {request_id}."
                    )
                    yield None, TTS2HttpResponseEventType.FLUSH
                    break

                self.ten_env.log_debug(
                    f"PollyTTS: sending EVENT_TTS_RESPONSE, length: {len(chunk)} of request_id: {request_id}."
                )

                if len(chunk) > 0:
                    yield bytes(chunk), TTS2HttpResponseEventType.RESPONSE

            if not self._is_cancelled:
                self.ten_env.log_debug(
                    f"PollyTTS: sending EVENT_TTS_END of request_id: {request_id}."
                )
                yield None, TTS2HttpResponseEventType.END

        except NoCredentialsError as e:
            error_message = f"AWS credentials error: {str(e)}"
            self.ten_env.log_error(
                f"vendor_error: {error_message} of request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            yield error_message.encode(
                "utf-8"
            ), TTS2HttpResponseEventType.INVALID_KEY_ERROR
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = str(e)
            self.ten_env.log_error(
                f"vendor_error: {error_message} of request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            # Fatal errors: authentication issues and configuration errors
            fatal_error_codes = [
                "InvalidClientTokenId",
                "SignatureDoesNotMatch",
                "AccessDenied",
                "InvalidParameterValue",  # Invalid configuration (e.g., invalid voice, engine)
                "InvalidParameterCombination",
                "ValidationError",
            ]
            if error_code in fatal_error_codes:
                yield error_message.encode(
                    "utf-8"
                ), TTS2HttpResponseEventType.INVALID_KEY_ERROR
            else:
                yield error_message.encode(
                    "utf-8"
                ), TTS2HttpResponseEventType.ERROR
        except Exception as e:
            error_message = str(e)
            self.ten_env.log_error(
                f"vendor_error: {error_message} of request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            if "validation failed" in error_message.lower():
                yield error_message.encode(
                    "utf-8"
                ), TTS2HttpResponseEventType.INVALID_KEY_ERROR
            else:

                yield error_message.encode(
                    "utf-8"
                ), TTS2HttpResponseEventType.ERROR

    def _synthesize_speech(self, synthesize_params: dict) -> Iterator[bytes]:
        """Synchronous synthesis"""
        self.record_text_sent()
        response = self.client.synthesize_speech(**synthesize_params)

        if "AudioStream" not in response:
            raise ValueError("No audio stream in response")

        with closing(response["AudioStream"]) as stream:
            for chunk in stream.iter_chunks(chunk_size=self.frame_size):
                if chunk:
                    self.record_audio_received()
                yield chunk

    async def _async_iter_from_sync(
        self, sync_iterator: Iterator[bytes]
    ) -> AsyncIterator[bytes]:
        """Convert the sync iterator to an async iterator, support cancel operation"""
        try:
            for chunk in sync_iterator:
                # check if the task is cancelled
                current_task = asyncio.current_task()
                if current_task and current_task.cancelled():
                    logging.info("task is cancelled")
                    break

                # return the control to the event loop
                await asyncio.sleep(0)
                yield chunk
        except Exception as e:
            logging.error(f"error when iterating audio stream: {e}")
            raise

    async def clean(self):
        """Clean up resources"""
        self.ten_env.log_debug("PollyTTS: clean() called.")
        try:
            if not self._closed:
                self.thread_pool.shutdown(wait=True)
                self._closed = True
        finally:
            pass

    def get_extra_metadata(self) -> dict[str, Any]:
        """Return extra metadata for TTFB metrics."""
        return {
            "engine": self.config.params.get("engine", ""),
            "voice": self.config.params.get("voice", ""),
        }

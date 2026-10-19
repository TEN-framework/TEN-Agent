import asyncio
from datetime import datetime


from .config import TencentTTSConfig
from ten_ai_base.const import LOG_CATEGORY_TRANSCRIPTS
from ten_runtime.async_ten_env import AsyncTenEnv
from .src.flowing_speech_synthesizer import (
    FlowingSpeechSynthesizer,
    FlowingSpeechSynthesisListener,
)
from .src.common import credential

MESSAGE_TYPE_PCM = 1
MESSAGE_TYPE_CMD_COMPLETE = 2
MESSAGE_TYPE_CMD_ERROR = 3
MESSAGE_TYPE_CMD_METRIC = 4


class TencentTTSTaskFailedException(Exception):
    def __init__(self, error_code: int, error_message: str):
        self.error_code = error_code
        self.error_message = error_message

    def __str__(self):
        return f"TencentTTSTaskFailedException: {self.error_code}, {self.error_message}"


class TencentTTSAuthenticationException(Exception):
    """Exception raised when authentication error (code 10001) occurs."""

    def __init__(
        self, message: str = "Authentication error - reconnection not allowed"
    ):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"TencentTTSAuthenticationException: {self.message}"


class AsyncIteratorCallback(FlowingSpeechSynthesisListener):
    """Callback class for handling TTS synthesis results asynchronously."""

    def __init__(
        self,
        ten_env: AsyncTenEnv,
        queue: asyncio.Queue[
            tuple[
                bool,
                int,
                str | bytes | TencentTTSTaskFailedException | int | None,
            ]
        ],
    ) -> None:
        self.ten_env = ten_env

        self._loop = asyncio.get_event_loop()
        self._queue = queue
        self.sent_ts: datetime | None = None
        self.ttfb_sent: bool = False
        self.auth_error: bool = False  # Flag to track authentication errors

    def set_sent_ts(self):
        if self.sent_ts:
            return
        self.sent_ts = datetime.now()

    def on_close(self):
        super().on_close()
        self.ten_env.log_debug("WebSocket connection closed.")

    def on_synthesis_start(self, session_id) -> None:
        super().on_synthesis_start(session_id)
        self.ten_env.log_debug(
            f"TTS synthesis task started, session_id: {session_id}"
        )

    def on_synthesis_end(self) -> None:
        super().on_synthesis_end()
        self.ten_env.log_debug("TTS synthesis task completed")
        asyncio.run_coroutine_threadsafe(
            self._queue.put((True, MESSAGE_TYPE_CMD_COMPLETE, None)), self._loop
        )

    def on_audio_result(self, audio_bytes):
        super().on_audio_result(audio_bytes)
        if self.sent_ts and not self.ttfb_sent:
            ttfb_ms = int(
                (datetime.now() - self.sent_ts).total_seconds() * 1000
            )
            self.ttfb_sent = True
            asyncio.run_coroutine_threadsafe(
                self._queue.put((False, MESSAGE_TYPE_CMD_METRIC, ttfb_ms)),
                self._loop,
            )
        self.ten_env.log_debug(f"Received audio data: {len(audio_bytes)} bytes")
        # Send audio data to queue
        asyncio.run_coroutine_threadsafe(
            self._queue.put((False, MESSAGE_TYPE_PCM, audio_bytes)), self._loop
        )

    def on_synthesis_fail(self, response):
        super().on_synthesis_fail(response)

        err_code = response["code"]
        message = response["message"]

        # Error code 10001 is authentication/key error, no need to reconnect
        if err_code == 10001:
            self.auth_error = (
                True  # Mark authentication error to prevent reconnection
            )
            self.ten_env.log_error(
                f"Authentication error (code 10001): {message}. ",
            )
        else:
            self.ten_env.log_error(
                f"TTS synthesis task failed: {err_code}, {message}"
            )

        # Send error signal
        asyncio.run_coroutine_threadsafe(
            self._queue.put(
                (
                    True,
                    MESSAGE_TYPE_CMD_ERROR,
                    TencentTTSTaskFailedException(err_code, message),
                )
            ),
            self._loop,
        )

    def on_data(self, data: bytes) -> None:
        """Called when receiving audio data from TTS service."""
        self.ten_env.log_debug(f"Received audio data: {len(data)} bytes")
        # Send audio data to queue
        asyncio.run_coroutine_threadsafe(
            self._queue.put((False, MESSAGE_TYPE_PCM, data)), self._loop
        )


class TencentTTSClient:
    """Client for Tencent TTS service."""

    def __init__(
        self,
        config: TencentTTSConfig,
        ten_env: AsyncTenEnv,
        vendor: str,
    ):
        # Configuration and environment
        self.config = config
        self.ten_env = ten_env
        self.vendor = vendor
        self.conn_ready_event = asyncio.Event()

        # TTS synthesizer
        self._callback: AsyncIteratorCallback | None = None
        self.synthesizer: FlowingSpeechSynthesizer | None = None
        # Communication queue for audio data
        self._receive_queue: asyncio.Queue[
            tuple[
                bool,
                int,
                str | bytes | TencentTTSTaskFailedException | int | None,
            ]
        ] = asyncio.Queue()

    async def start(self) -> None:
        """Start the TTS client and initialize components."""

        # Create synthesizer with configuration
        self._callback = AsyncIteratorCallback(
            self.ten_env, self._receive_queue
        )

        credential_var = credential.Credential(
            self.config.secret_id, self.config.secret_key
        )

        synthesizer = FlowingSpeechSynthesizer(
            self.config.app_id, credential_var, self._callback
        )

        synthesizer.set_voice_type(self.config.voice_type)
        synthesizer.set_codec(self.config.codec)
        synthesizer.set_sample_rate(self.config.sample_rate)
        synthesizer.set_enable_subtitle(self.config.enable_subtitle)
        synthesizer.set_speed(self.config.speed)
        synthesizer.set_volume(self.config.volume)
        synthesizer.set_emotion_category(self.config.emotion_category)
        synthesizer.set_emotion_intensity(self.config.emotion_intensity)

        try:
            synthesizer.start()
            # wait_ready uses threading.Event.wait() which blocks the current
            # thread.  Running it on the event-loop thread would freeze the
            # entire asyncio loop and prevent other extensions from
            # initialising.  Offload to a worker thread so the loop stays
            # responsive.
            ready = await asyncio.get_event_loop().run_in_executor(
                None, synthesizer.wait_ready, 5000
            )
            if not ready:
                raise TimeoutError(
                    "Tencent TTS synthesizer wait_ready timed out"
                )
            # ready_event is now also set on synthesis failure (e.g. invalid
            # voice_type), so double-check the actual ready flag.
            if not synthesizer.ready:
                raise RuntimeError(
                    "Tencent TTS synthesizer failed during startup "
                    "(check voice_type and credentials)"
                )
        except Exception as e:
            self.ten_env.log_error(f"Error starting TTS: {e}")
            raise e

        self.synthesizer = synthesizer
        self.conn_ready_event.set()

        self.ten_env.log_debug("Tencent TTS client started successfully")

    async def stop(self) -> None:
        """Stop the TTS client and clean up resources."""
        # Check for fatal conditions before restarting
        has_auth_error = self._callback and self._callback.auth_error
        self.close()
        if has_auth_error:
            self.ten_env.log_warn(
                "Not restarting TTS client due to authentication error"
            )
            return
        # restart the synthesizer
        asyncio.create_task(self.start())

    def close(self) -> None:
        """
        Close the TTS client and clean up resources.
        """
        if self.synthesizer:
            try:
                if self.synthesizer.is_alive():
                    self.synthesizer.close()
                else:
                    self.ten_env.log_debug(
                        "Synthesizer is not alive, skipping close"
                    )
                self.ten_env.log_debug("TTS operation closed")
            except Exception as e:
                self.ten_env.log_error(f"Error cancelling TTS: {e}")

            # Clean up synthesizer
            self.synthesizer = None
            self.conn_ready_event.clear()

    def complete(self) -> None:
        """
        Complete current TTS operation.
        """
        self.ten_env.log_debug("TTS operation completed")
        if self.synthesizer and self.synthesizer.is_alive():
            try:
                self.synthesizer.complete()
                self.conn_ready_event.clear()

                self.ten_env.log_debug("TTS operation completed")
            except Exception as e:
                self.ten_env.log_error(f"Error completing TTS: {e}")

    async def synthesize_audio(self, text: str, text_input_end: bool):
        """
        Start audio synthesis for the given text.
        This method only initiates synthesis and returns immediately.
        Audio data should be consumed from the queue independently.
        """
        self.ten_env.log_debug(
            f"Starting TTS synthesis, text: {text}, input_end: {text_input_end},conn_ready_event: {self.conn_ready_event.is_set()}",
            category=LOG_CATEGORY_TRANSCRIPTS,
        )

        await self.conn_ready_event.wait()

        # Check for authentication error - do not attempt to reconnect
        if self._callback and self._callback.auth_error:
            self.ten_env.log_error(
                "Cannot synthesize audio: Authentication error (code 10001) occurred. ",
            )
            raise TencentTTSAuthenticationException(
                "Authentication error (code 10001) - reconnection not allowed"
            )

        if not self.synthesizer or not self.synthesizer.is_alive():
            self.ten_env.log_error("Synthesizer is not alive, reinitializing")
            await self.start()

        # Start streaming TTS synthesis
        self._callback.set_sent_ts()
        self.synthesizer.process(text)

        self.ten_env.log_debug(
            f"TTS synthesis initiated for text: {text}",
            category=LOG_CATEGORY_TRANSCRIPTS,
        )

    async def get_audio_data(self):
        """
        Get audio data from the queue. This is a separate method that can be called
        independently to consume audio data.
        Returns: (done, message_type, data)
        """
        return await self._receive_queue.get()

    def _duration_in_ms(self, start: datetime, end: datetime) -> int:
        """
        Calculate duration between two timestamps in milliseconds.

        Args:
            start: Start timestamp
            end: End timestamp

        Returns:
            Duration in milliseconds
        """
        return int((end - start).total_seconds() * 1000)

    def _duration_in_ms_since(self, start: datetime) -> int:
        """
        Calculate duration from a timestamp to now in milliseconds.

        Args:
            start: Start timestamp

        Returns:
            Duration in milliseconds from start to now
        """
        return self._duration_in_ms(start, datetime.now())

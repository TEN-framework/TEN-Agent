import asyncio
import json
import threading
import time
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any

import dashscope
from dashscope.audio.tts_v2 import (
    AudioFormat,
    ResultCallback,
    SpeechSynthesizer,
    SpeechSynthesizerObjectPool,
)
from ten_runtime.async_ten_env import AsyncTenEnv

from .config import CosyTTSConfig

MESSAGE_TYPE_PCM = 1
MESSAGE_TYPE_CMD_COMPLETE = 2
MESSAGE_TYPE_CMD_ERROR = 3
MESSAGE_TYPE_TEXT_RESULT = 4
COSY_TTS_POOL_SIZE = 2
# The extension always requests mono 16-bit PCM from DashScope, so the
# byte-to-sample conversion below is fixed.
BYTES_PER_SAMPLE = 2
SAMPLES_PER_SECOND_SCALE = 1000
# A provider that counted word times from the start of each sentence would
# report small values for later sentences. Times that reach the sentence's own
# audio position are counted from the request audio instead.
SENTENCE_TIME_TOLERANCE_MS = 200
# DashScope keeps revising the last word of every event until the next batch of
# audio is generated, so the newest word is held back and published one event
# later (or by `sentence-end`, which always reports the complete list).
SUBTITLE_LAG_WORDS = 1

# DashScope reports sentence lifecycle events in `payload.output.type`.
SENTENCE_EVENT_TYPES = frozenset(
    {"sentence-begin", "sentence-synthesis", "sentence-end"},
)

AUDIO_FORMAT_MAPPING = {
    8000: AudioFormat.PCM_8000HZ_MONO_16BIT,
    16000: AudioFormat.PCM_16000HZ_MONO_16BIT,
    22050: AudioFormat.PCM_22050HZ_MONO_16BIT,
    24000: AudioFormat.PCM_24000HZ_MONO_16BIT,
    44100: AudioFormat.PCM_44100HZ_MONO_16BIT,
    48000: AudioFormat.PCM_48000HZ_MONO_16BIT,
}


@dataclass(frozen=True)
class ProviderError:
    code: str
    message: str
    task_id: str = ""
    request_uuid: str = ""


@dataclass(frozen=True)
class ProviderCompletion:
    billed_characters: int
    task_id: str
    request_uuid: str = ""


@dataclass(frozen=True)
class SubtitleWord:
    """One provider word, positioned relative to the request audio origin."""

    word: str
    start_ms: int
    duration_ms: int


@dataclass(frozen=True)
class ProviderSubtitle:
    """One subtitle sentence, positioned relative to the request audio origin."""

    text: str
    start_ms: int
    duration_ms: int
    words: tuple[SubtitleWord, ...]


@dataclass(frozen=True)
class _RawWord:
    """Provider word timing as reported, before timeline alignment."""

    word: str
    begin_ms: int
    end_ms: int


@dataclass(frozen=True)
class QueueItem:
    done: bool
    message_type: int
    payload: (
        bytes | ProviderError | ProviderCompletion | ProviderSubtitle | None
    )
    request_id: str
    task_id: str
    ttfb_ms: int | None = None
    # PCM position of this chunk relative to the request audio origin.
    audio_start_ms: int | None = None


class CosyTTSProviderError(RuntimeError):
    def __init__(self, error: ProviderError) -> None:
        self.error = error
        super().__init__(error.message)


def _as_milliseconds(value: Any) -> int | None:
    """Return a provider timestamp as whole milliseconds, or None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0:
        return None
    return int(value)


@dataclass(frozen=True)
class _PoolLease:
    pool: SpeechSynthesizerObjectPool
    synthesizer: SpeechSynthesizer


class SharedPool:
    """Own the process-wide preconnected DashScope pool."""

    _lock = threading.Lock()
    _pool: SpeechSynthesizerObjectPool | None = None
    _signature: tuple[Any, ...] | None = None
    _clients = 0
    _synthesizers: dict[int, SpeechSynthesizer] = {}

    @classmethod
    def _signature_for(cls, config: CosyTTSConfig) -> tuple[Any, ...]:
        return (
            config.api_key,
            config.url,
            tuple(sorted(config.headers.items())),
        )

    @classmethod
    def _headers(cls, config: CosyTTSConfig) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "User-Agent": "ten-cosy-tts/0.4.6",
        }
        headers.update(config.headers)
        return headers

    @classmethod
    def _ensure_pool_locked(
        cls,
        config: CosyTTSConfig,
    ) -> SpeechSynthesizerObjectPool:
        signature = cls._signature_for(config)
        if cls._pool is None:
            dashscope.api_key = config.api_key
            cls._pool = SpeechSynthesizerObjectPool(
                max_size=COSY_TTS_POOL_SIZE,
                url=config.url or None,
                headers=cls._headers(config),
            )
            cls._signature = signature
            cls._synthesizers = {}
            for pool_object in getattr(cls._pool, "_pool", ()):
                synthesizer = getattr(pool_object, "synthesizer", None)
                if isinstance(synthesizer, SpeechSynthesizer):
                    cls._synthesizers[id(synthesizer)] = synthesizer
        elif cls._signature != signature:
            raise ValueError(
                "Cosy TTS pool is already initialized with different credentials, "
                "URL or headers",
            )

        return cls._pool

    @classmethod
    def register(cls, config: CosyTTSConfig) -> None:
        with cls._lock:
            cls._ensure_pool_locked(config)
            cls._clients += 1

    @classmethod
    def borrow(
        cls,
        config: CosyTTSConfig,
        callback: ResultCallback,
    ) -> _PoolLease:
        with cls._lock:
            pool = cls._ensure_pool_locked(config)

        borrow_params: dict[str, Any] = {
            "callback": callback,
            "format": AUDIO_FORMAT_MAPPING[config.sample_rate],
            "model": config.model,
            "voice": config.voice,
            "additional_params": config.provider_params(),
        }
        # These are SDK constructor parameters; the SDK translates them to the
        # wire names (`speech_rate` -> `rate`, `pitch_rate` -> `pitch`). Passing
        # them through `additional_params` instead would be ignored.
        for field_name in (
            "volume",
            "speech_rate",
            "pitch_rate",
            "seed",
            "instruction",
            "language_hints",
        ):
            value = getattr(config, field_name)
            if value is not None:
                borrow_params[field_name] = value

        synthesizer = pool.borrow_synthesizer(**borrow_params)
        with cls._lock:
            cls._synthesizers[id(synthesizer)] = synthesizer

        return _PoolLease(pool, synthesizer)

    @classmethod
    def return_lease(cls, lease: _PoolLease) -> None:
        with cls._lock:
            current_pool = cls._pool
        if lease.pool is current_pool:
            returned = lease.pool.return_synthesizer(lease.synthesizer)
            if returned is False:
                # The SDK can create an unpooled cold object while a closed
                # pooled object is reconnecting. Such an object doesn't
                # affect the SDK's borrowed count and must be closed here.
                lease.synthesizer.close()
        else:
            lease.synthesizer.close()

    @classmethod
    def discard_lease(cls, lease: _PoolLease) -> None:
        """Return a closed lease so the SDK pool can replace its connection."""
        lease.synthesizer.close()
        with cls._lock:
            current_pool = cls._pool
        if lease.pool is current_pool:
            # The SDK pool's maintenance thread replaces disconnected
            # objects. Returning the closed object also balances the SDK's
            # internal borrowed-object count without disrupting other
            # requests which may be using the same singleton pool.
            lease.pool.return_synthesizer(lease.synthesizer)

    @classmethod
    def release_client(cls) -> None:
        pool_to_shutdown: SpeechSynthesizerObjectPool | None = None
        synthesizers_to_close: list[SpeechSynthesizer] = []
        with cls._lock:
            if cls._clients == 0:
                return
            cls._clients -= 1
            if cls._clients == 0:
                pool_to_shutdown = cls._pool
                synthesizers = dict(cls._synthesizers)
                if pool_to_shutdown is not None:
                    for pool_object in getattr(pool_to_shutdown, "_pool", ()):
                        synthesizer = getattr(pool_object, "synthesizer", None)
                        if isinstance(synthesizer, SpeechSynthesizer):
                            synthesizers[id(synthesizer)] = synthesizer
                synthesizers_to_close = list(synthesizers.values())
                cls._pool = None
                cls._signature = None
                cls._synthesizers = {}
        if pool_to_shutdown is not None:
            pool_to_shutdown.shutdown()
            # DashScope's pool shutdown drops its references without closing
            # their WebSocket-client threads. Close the tracked objects after
            # the maintenance thread stops so a subsequent test/app can start
            # from a clean networking state.
            for synthesizer in synthesizers_to_close:
                synthesizer.close()
                thread = getattr(synthesizer, "thread", None)
                if (
                    thread is not None
                    and thread is not threading.current_thread()
                ):
                    thread.join(timeout=1.0)
            # The SDK stores its pool in a singleton. Drop the stopped
            # instance so a later extension instance initializes a fresh pool
            # instead of reinitializing the old one in place.
            instance = getattr(SpeechSynthesizerObjectPool, "_instance", None)
            if instance is pool_to_shutdown:
                setattr(SpeechSynthesizerObjectPool, "_instance", None)


class AsyncIteratorCallback(ResultCallback):
    """Bridge DashScope's callback thread to the extension event loop."""

    def __init__(
        self,
        ten_env: AsyncTenEnv,
        queue: asyncio.Queue[QueueItem],
        loop: asyncio.AbstractEventLoop,
        request_id: str,
        *,
        sample_rate: int,
        words_enabled: bool,
    ) -> None:
        self.ten_env = ten_env
        self._queue = queue
        self._loop = loop
        self.request_id = request_id
        self._sample_rate = sample_rate
        self._words_enabled = words_enabled
        self.task_id = ""
        self.cancelled = False
        self.closed = False
        self.error: ProviderError | None = None
        self.billed_characters = 0
        self.request_uuid = ""
        self.first_audio_received = threading.Event()
        self.task_started_ns: int | None = None
        self.first_request_sent_ns: int | None = None
        self.first_audio_ns: int | None = None
        # Subtitle alignment state. DashScope reports word times per sentence,
        # so every sentence is anchored to the PCM position where its audio
        # starts and each word keeps only its offset inside that sentence.
        self._pcm_samples = 0
        self._sentence_origin_samples: dict[int, int] = {}
        self._sentence_time_offset: dict[int, int] = {}
        self._emitted_words: dict[int, int] = {}
        self._current_sentence_index: int | None = None

    def bind_task(self, task_id: str) -> None:
        self.task_id = task_id

    def cancel(self) -> None:
        self.cancelled = True

    def close(self) -> None:
        self.closed = True
        self.cancelled = True

    def on_open(self) -> None:
        self.task_started_ns = time.perf_counter_ns()

    def on_complete(self) -> None:
        # The client returns the object only after streaming_complete() returns.
        # This callback alone isn't a safe object-pool release boundary.
        return

    def on_error(self, message: str) -> None:
        if self.cancelled or self.closed or self._loop.is_closed():
            return
        self.error = self._parse_error(message)
        self._put(
            QueueItem(
                done=True,
                message_type=MESSAGE_TYPE_CMD_ERROR,
                payload=self.error,
                request_id=self.request_id,
                task_id=self.error.task_id,
            ),
        )

    def on_close(self) -> None:
        self.closed = True

    def on_event(self, message: str) -> None:
        if self.cancelled or self.closed or self._loop.is_closed():
            return
        try:
            event_data = json.loads(message)
        except json.JSONDecodeError:
            self.ten_env.log_error("Failed to decode Cosy TTS event JSON")
            return

        header = event_data.get("header", {})
        event_task_id = str(header.get("task_id", ""))
        if self.task_id and event_task_id and event_task_id != self.task_id:
            self.ten_env.log_warn(
                "Discarded Cosy TTS event for a stale task, "
                f"expected_task_id: {self.task_id}, task_id: {event_task_id}",
            )
            return

        attributes = header.get("attributes", {})
        if isinstance(attributes, dict):
            self.request_uuid = str(attributes.get("request_uuid", ""))

        usage = event_data.get("payload", {}).get("usage", {})
        characters = (
            usage.get("characters") if isinstance(usage, dict) else None
        )
        if isinstance(characters, int):
            self.billed_characters = max(self.billed_characters, characters)

        self._handle_output(event_data.get("payload"))

    def _handle_output(self, payload: Any) -> None:
        """Track sentence word timings reported inside `result-generated`."""
        if not self._words_enabled or not isinstance(payload, dict):
            return

        output = payload.get("output")
        if not isinstance(output, dict):
            return

        event_type = output.get("type")
        if event_type not in SENTENCE_EVENT_TYPES:
            return

        sentence = output.get("sentence")
        if not isinstance(sentence, dict):
            sentence = {}

        index = self._sentence_index(event_type, sentence)
        words = self._parse_words(sentence.get("words"))
        if not words:
            # An empty list marks an audio chunk; it carries no word data.
            return

        # The first event of a sentence arrives before that sentence's audio,
        # so the samples counted so far are that sentence's audio origin.
        origin_samples = self._sentence_origin_samples.setdefault(
            index,
            self._pcm_samples,
        )
        emitted = self._emitted_words.get(index, 0)
        if len(words) < emitted:
            # A shorter list would reopen published words; wait for the complete
            # list in `sentence-end` instead of publishing them twice.
            return

        limit = (
            len(words)
            if event_type == "sentence-end"
            else max(0, len(words) - SUBTITLE_LAG_WORDS)
        )
        if limit <= emitted:
            return

        subtitle = self._build_subtitle(
            index,
            words[emitted:limit],
            origin_samples,
        )
        self._emitted_words[index] = limit
        if subtitle is None:
            return
        self._put(
            QueueItem(
                done=False,
                message_type=MESSAGE_TYPE_TEXT_RESULT,
                payload=subtitle,
                request_id=self.request_id,
                task_id=self.task_id,
            ),
        )

    def _sentence_index(self, event_type: str, sentence: dict[str, Any]) -> int:
        raw_index = sentence.get("index")
        if isinstance(raw_index, int) and not isinstance(raw_index, bool):
            self._current_sentence_index = raw_index
            return raw_index

        # `index` is expected but not guaranteed; fall back to arrival order.
        if (
            event_type == "sentence-begin"
            or self._current_sentence_index is None
        ):
            self._current_sentence_index = (
                0
                if self._current_sentence_index is None
                else self._current_sentence_index + 1
            )
        return self._current_sentence_index

    @staticmethod
    def _parse_words(raw_words: Any) -> list[_RawWord]:
        if not isinstance(raw_words, list):
            return []

        words: list[_RawWord] = []
        for entry in raw_words:
            if not isinstance(entry, dict):
                continue
            text = entry.get("text")
            if not isinstance(text, str) or text == "":
                continue
            begin_ms = _as_milliseconds(entry.get("begin_time"))
            end_ms = _as_milliseconds(entry.get("end_time"))
            if begin_ms is None or end_ms is None or end_ms < begin_ms:
                continue
            words.append(_RawWord(word=text, begin_ms=begin_ms, end_ms=end_ms))
        return words

    def _build_subtitle(
        self,
        index: int,
        raw_words: list[_RawWord],
        origin_samples: int,
    ) -> ProviderSubtitle | None:
        if not raw_words:
            return None

        offset_ms = self._sentence_word_offset(index, raw_words, origin_samples)
        words = tuple(
            SubtitleWord(
                word=raw.word,
                start_ms=raw.begin_ms + offset_ms,
                duration_ms=raw.end_ms - raw.begin_ms,
            )
            for raw in raw_words
        )
        start_ms = words[0].start_ms
        end_ms = max(word.start_ms + word.duration_ms for word in words)
        # The published text is exactly the words it describes, so a consumer
        # that highlights words stays in sync with the caption text.
        text = "".join(word.word for word in words)
        return ProviderSubtitle(
            text=text,
            start_ms=start_ms,
            duration_ms=max(0, end_ms - start_ms),
            words=words,
        )

    def _sentence_word_offset(
        self,
        index: int,
        raw_words: list[_RawWord],
        origin_samples: int,
    ) -> int:
        """Offset that maps provider word times onto the request PCM timeline.

        DashScope reports word times against the request audio timeline, so the
        offset is zero. A provider that counted from each sentence instead
        reports a small value for a sentence that starts later; those words are
        anchored to their own sentence. The decision is taken from the first
        words of the sentence and reused for its later batches.
        """
        known = self._sentence_time_offset.get(index)
        if known is not None:
            return known

        origin_ms = self._samples_to_ms(origin_samples)
        first_begin_ms = raw_words[0].begin_ms
        offset_ms = (
            0
            if index == 0
            or first_begin_ms >= origin_ms - SENTENCE_TIME_TOLERANCE_MS
            else origin_ms - first_begin_ms
        )
        self._sentence_time_offset[index] = offset_ms
        return offset_ms

    def _samples_to_ms(self, samples: int) -> int:
        if self._sample_rate <= 0:
            return 0
        return samples * SAMPLES_PER_SECOND_SCALE // self._sample_rate

    def on_data(self, data: bytes) -> None:
        if self.cancelled or self.closed:
            return
        ttfb_ms: int | None = None
        if not self.first_audio_received.is_set():
            self.first_audio_ns = time.perf_counter_ns()
            self.first_audio_received.set()
            if self.first_request_sent_ns is not None:
                ttfb_ms = int(
                    (self.first_audio_ns - self.first_request_sent_ns)
                    / 1_000_000,
                )
        audio_start_ms = self._samples_to_ms(self._pcm_samples)
        self._pcm_samples += len(data) // BYTES_PER_SAMPLE
        self._put(
            QueueItem(
                done=False,
                message_type=MESSAGE_TYPE_PCM,
                payload=bytes(data),
                request_id=self.request_id,
                task_id=self.task_id,
                ttfb_ms=ttfb_ms,
                audio_start_ms=audio_start_ms,
            ),
        )

    def _parse_error(self, message: str) -> ProviderError:
        try:
            event_data = json.loads(message)
            header = event_data.get("header", {})
            attributes = header.get("attributes", {})
            request_uuid = (
                str(attributes.get("request_uuid", ""))
                if isinstance(attributes, dict)
                else ""
            )
            return ProviderError(
                code=str(header.get("error_code", "ProviderError")),
                message=str(header.get("error_message", message)),
                task_id=str(header.get("task_id", self.task_id)),
                request_uuid=request_uuid,
            )
        except (json.JSONDecodeError, AttributeError):
            return ProviderError(
                code="ProviderError",
                message=message,
                task_id=self.task_id,
            )

    def _put(self, item: QueueItem) -> None:
        try:
            asyncio.run_coroutine_threadsafe(self._queue.put(item), self._loop)
        except RuntimeError:
            # The DashScope callback thread can outlive the TEN test/app
            # runtime. Do not touch `ten_env` after its loop has closed.
            self.cancelled = True


@dataclass
class _ActiveTask:
    request_id: str
    lease: _PoolLease
    callback: AsyncIteratorCallback
    completion_started: bool = False


class CosyTTSClient:
    """DashScope SDK client with preconnected object-pool leases."""

    def __init__(
        self,
        config: CosyTTSConfig,
        ten_env: AsyncTenEnv,
        vendor: str,
    ) -> None:
        self.config = config
        self.ten_env = ten_env
        self.vendor = vendor
        self._loop: asyncio.AbstractEventLoop | None = None
        self._active: _ActiveTask | None = None
        self._active_lock = asyncio.Lock()
        self._receive_queue: asyncio.Queue[QueueItem] = asyncio.Queue()
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._registered = False

    async def start(self) -> int:
        """Preconnect the configured pool and return pool-ready latency."""
        self._loop = asyncio.get_running_loop()
        started_ns = time.perf_counter_ns()
        await asyncio.to_thread(SharedPool.register, self.config)
        self._registered = True
        connect_delay_ms = int(
            (time.perf_counter_ns() - started_ns) / 1_000_000
        )
        self.ten_env.log_info(
            "Cosy TTS connection pool ready, "
            f"size: {COSY_TTS_POOL_SIZE}, connect_delay_ms: {connect_delay_ms}",
        )
        return connect_delay_ms

    async def stop(self) -> None:
        await self.cancel()
        if self._background_tasks:
            await asyncio.gather(
                *tuple(self._background_tasks),
                return_exceptions=True,
            )
        if self._registered:
            await asyncio.to_thread(SharedPool.release_client)
            self._registered = False

    async def synthesize_audio(self, text: str, request_id: str) -> None:
        active = await self._get_or_create_active(request_id)
        try:
            await asyncio.to_thread(self._send_text, active, text)
        except Exception as exc:
            error = active.callback.error or ProviderError(
                code=type(exc).__name__,
                message=str(exc),
                task_id=active.callback.task_id,
            )
            await self._abort_active(active, error, emit_error=False)
            raise CosyTTSProviderError(error) from exc

    @staticmethod
    def _send_text(active: _ActiveTask, text: str) -> None:
        if active.callback.first_request_sent_ns is None:
            active.callback.first_request_sent_ns = time.perf_counter_ns()
        active.lease.synthesizer.streaming_call(text)

    async def complete(self, request_id: str) -> None:
        async with self._active_lock:
            active = self._active
            if active is None:
                return
            if active.request_id != request_id:
                raise RuntimeError(
                    "Cosy TTS active request mismatch, "
                    f"active: {active.request_id}, completing: {request_id}",
                )
            if active.completion_started:
                return
            active.completion_started = True

        self._start_background_task(self._complete_active(active))

    async def _complete_active(self, active: _ActiveTask) -> None:
        """Wait for provider completion without blocking the input queue."""

        try:
            await asyncio.to_thread(active.lease.synthesizer.streaming_complete)
        except Exception as exc:
            error = active.callback.error or ProviderError(
                code=type(exc).__name__,
                message=str(exc),
                task_id=active.callback.task_id,
            )
            await self._abort_active(active, error, emit_error=True)
            return

        if active.callback.error is not None:
            await self._abort_active(
                active, active.callback.error, emit_error=True
            )
            return

        if not await self._clear_if_active(active):
            return

        response = active.lease.synthesizer.get_response() or {}
        completion = self._completion_from_response(active, response)
        active.callback.close()
        await asyncio.to_thread(SharedPool.return_lease, active.lease)
        await self._receive_queue.put(
            QueueItem(
                done=True,
                message_type=MESSAGE_TYPE_CMD_COMPLETE,
                payload=completion,
                request_id=active.request_id,
                task_id=active.callback.task_id,
            ),
        )

    async def cancel(self) -> None:
        async with self._active_lock:
            active = self._active
            self._active = None
        if active is None:
            return

        active.callback.cancel()
        self._start_background_task(self._cancel_active(active))

    async def _cancel_active(self, active: _ActiveTask) -> None:
        """Clean up an interrupted provider task without blocking a new turn."""
        try:
            await asyncio.to_thread(active.lease.synthesizer.streaming_cancel)
            if active.callback.error is not None:
                raise CosyTTSProviderError(active.callback.error)
        except Exception as exc:
            self.ten_env.log_warn(
                f"Cosy TTS cancel discarded connection: {exc}"
            )
        finally:
            await asyncio.to_thread(SharedPool.discard_lease, active.lease)

    def _start_background_task(
        self,
        coroutine: Coroutine[Any, Any, None],
    ) -> None:
        task = asyncio.create_task(coroutine)
        self._background_tasks.add(task)
        task.add_done_callback(self._on_background_task_done)

    def _on_background_task_done(self, task: asyncio.Task[None]) -> None:
        self._background_tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            self.ten_env.log_error(
                f"Cosy TTS background task failed: {type(error).__name__}: {error}",
            )

    async def get_audio_data(self) -> QueueItem:
        return await self._receive_queue.get()

    async def _get_or_create_active(self, request_id: str) -> _ActiveTask:
        async with self._active_lock:
            if self._active is not None:
                if self._active.request_id != request_id:
                    raise RuntimeError(
                        "Cosy TTS already has an active request, "
                        f"active: {self._active.request_id}, new: {request_id}",
                    )
                return self._active

            loop = self._loop
            if loop is None:
                raise RuntimeError("Cosy TTS client is not started")
            callback = AsyncIteratorCallback(
                self.ten_env,
                self._receive_queue,
                loop,
                request_id,
                sample_rate=self.config.sample_rate,
                words_enabled=self.config.enable_words,
            )
            lease = await asyncio.to_thread(
                SharedPool.borrow, self.config, callback
            )
            callback.bind_task(lease.synthesizer.get_last_request_id())
            active = _ActiveTask(request_id, lease, callback)
            self._active = active
            self.ten_env.log_info(
                "Cosy TTS task lease acquired, "
                f"request_id: {request_id}, task_id: {callback.task_id}",
            )
            return active

    async def _abort_active(
        self,
        active: _ActiveTask,
        error: ProviderError,
        emit_error: bool,
    ) -> None:
        if not await self._clear_if_active(active):
            return
        active.callback.cancel()
        await asyncio.to_thread(SharedPool.discard_lease, active.lease)
        if emit_error:
            await self._receive_queue.put(
                QueueItem(
                    done=True,
                    message_type=MESSAGE_TYPE_CMD_ERROR,
                    payload=error,
                    request_id=active.request_id,
                    task_id=active.callback.task_id,
                ),
            )

    async def _clear_if_active(self, active: _ActiveTask) -> bool:
        async with self._active_lock:
            if self._active is not active:
                return False
            self._active = None
            return True

    @staticmethod
    def _completion_from_response(
        active: _ActiveTask,
        response: dict[str, Any],
    ) -> ProviderCompletion:
        header = (
            response.get("header", {}) if isinstance(response, dict) else {}
        )
        attributes = (
            header.get("attributes", {}) if isinstance(header, dict) else {}
        )
        payload = (
            response.get("payload", {}) if isinstance(response, dict) else {}
        )
        usage = payload.get("usage", {}) if isinstance(payload, dict) else {}
        characters = (
            usage.get("characters") if isinstance(usage, dict) else None
        )
        billed_characters = (
            characters
            if isinstance(characters, int)
            else active.callback.billed_characters
        )
        request_uuid = (
            str(attributes.get("request_uuid", ""))
            if isinstance(attributes, dict)
            else active.callback.request_uuid
        )
        return ProviderCompletion(
            billed_characters=billed_characters,
            task_id=active.callback.task_id,
            request_uuid=request_uuid or active.callback.request_uuid,
        )

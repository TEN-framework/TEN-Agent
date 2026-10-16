"""Word-level subtitle alignment against a scripted DashScope server.

The provider grows a sentence's word list event by event and keeps revising the
newest word. The extension publishes each word once, as soon as it is stable,
and anchors it to the PCM clock the audio frames use.
"""

import json
import socket
import threading
from dataclasses import dataclass, field
from typing import Any

import pytest
from pytest_ten import TenTestContext, ten_test
from ten_ai_base.struct import TTSTextInput
from ten_runtime import AudioFrame, Data
from websockets.sync.server import Server, ServerConnection, serve

SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2
CHUNK_AUDIO_MS = 400
CHUNK_BYTES = SAMPLE_RATE * CHUNK_AUDIO_MS // 1000 * BYTES_PER_SAMPLE
SENTENCE_AUDIO_MS = 2 * CHUNK_AUDIO_MS


def _find_available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.bind(("127.0.0.1", 0))
        return candidate.getsockname()[1]


SERVER_PORT = _find_available_port()

Word = tuple[str, int, int]


@dataclass(frozen=True)
class SentencePlan:
    """One sentence the fake provider synthesizes.

    `begin_words` is the partial list carried by `sentence-begin`,
    `synthesis_words` a longer one carried by `sentence-synthesis`, and `words`
    the complete list carried by `sentence-end`. `malformed` adds rows the
    extension must drop.
    """

    text: str
    begin_words: tuple[Word, ...]
    synthesis_words: tuple[Word, ...]
    words: tuple[Word, ...]
    malformed: tuple[dict[str, Any], ...] = field(default=())
    # Offset the extension must add: providers that count from the sentence
    # start are anchored to the position where that sentence's audio begins.
    anchor_ms: int = 0


SENTENCE_PLANS = (
    # Word times count from the request audio; the newest word is revised.
    SentencePlan(
        text="The castle's shadow stretched over the moat.",
        begin_words=(("The", 0, 200), (" castle", 200, 400)),
        synthesis_words=(
            ("The", 0, 200),
            (" castle's", 200, 400),
            (" shadow", 400, 600),
        ),
        words=(
            ("The", 0, 200),
            (" castle's", 200, 400),
            (" shadow", 400, 600),
            (" moat", 600, 800),
        ),
    ),
    SentencePlan(
        text="Nobody moved away.",
        begin_words=(("Nobody", 800, 1000), (" moved", 1000, 1200)),
        synthesis_words=(
            ("Nobody", 800, 1000),
            (" moved", 1000, 1200),
            (" away", 1200, 1400),
        ),
        words=(
            ("Nobody", 800, 1000),
            (" moved", 1000, 1200),
            (" away", 1200, 1400),
            (".", 1400, 1600),
        ),
    ),
    # A provider that counts from the sentence start still lands on the audio.
    SentencePlan(
        text="低头思故乡。",
        begin_words=(("低", 0, 200), ("头", 200, 400)),
        synthesis_words=(("低", 0, 200), ("头", 200, 400), ("思", 400, 600)),
        words=(
            ("低", 0, 200),
            ("头", 200, 400),
            ("思", 400, 600),
            ("故", 600, 800),
        ),
        malformed=({"text": "乡", "begin_time": 700},),
        anchor_ms=2 * SENTENCE_AUDIO_MS,
    ),
)


class FakeWordTimestampServer:
    """Serve the DashScope protocol with scripted sentence events."""

    def __init__(self, port: int, plans: tuple[SentencePlan, ...]) -> None:
        self.port = port
        self.plans = plans
        self.task_parameters: list[dict[str, Any]] = []
        self._server: Server | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._error: Exception | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        assert self._ready.wait(1.0)
        if self._error is not None:
            raise self._error

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        try:
            with serve(self._handle, "127.0.0.1", self.port) as server:
                self._server = server
                self._ready.set()
                server.serve_forever()
        except Exception as exc:  # surfaced through the test fixture
            self._error = exc
            self._ready.set()

    def _handle(self, websocket: ServerConnection) -> None:
        for raw_message in websocket:
            if not isinstance(raw_message, str):
                continue
            message = json.loads(raw_message)
            action = message["header"]["action"]
            task_id = message["header"]["task_id"]

            if action == "run-task":
                self.task_parameters.append(message["payload"]["parameters"])
                websocket.send(self._event("task-started", task_id))
            elif action == "continue-task":
                self._synthesize(websocket, task_id)
            elif action == "finish-task":
                websocket.send(self._event("task-finished", task_id))

    def _synthesize(self, websocket: ServerConnection, task_id: str) -> None:
        for index, plan in enumerate(self.plans):
            websocket.send(
                self._event(
                    "result-generated",
                    task_id,
                    payload={
                        "output": {
                            "type": "sentence-begin",
                            "original_text": plan.text,
                            "sentence": {
                                "index": index,
                                "words": self._words(plan.begin_words),
                            },
                        },
                    },
                ),
            )
            websocket.send(b"\x01\x00" * (CHUNK_BYTES // BYTES_PER_SAMPLE))
            websocket.send(
                self._event(
                    "result-generated",
                    task_id,
                    payload={
                        "output": {
                            "type": "sentence-synthesis",
                            "sentence": {
                                "index": index,
                                "words": self._words(plan.synthesis_words),
                            },
                        },
                    },
                ),
            )
            websocket.send(b"\x01\x00" * (CHUNK_BYTES // BYTES_PER_SAMPLE))
            websocket.send(
                self._event(
                    "result-generated",
                    task_id,
                    payload={
                        "output": {
                            "type": "sentence-end",
                            "original_text": plan.text,
                            "normalized_text": plan.text,
                            "sentence": {
                                "index": index,
                                "words": self._words(plan.words)
                                + [dict(row) for row in plan.malformed],
                            },
                        },
                        "usage": {"characters": len(plan.text) * (index + 1)},
                    },
                ),
            )

    @staticmethod
    def _words(entries: tuple[Word, ...]) -> list[dict[str, Any]]:
        return [
            {"text": text, "begin_time": begin, "end_time": end}
            for text, begin, end in entries
        ]

    @staticmethod
    def _event(
        event: str,
        task_id: str,
        payload: dict[str, Any] | None = None,
    ) -> str:
        return json.dumps(
            {
                "header": {"event": event, "task_id": task_id},
                "payload": payload or {},
            },
        )


@pytest.fixture
def word_server() -> FakeWordTimestampServer:
    server = FakeWordTimestampServer(SERVER_PORT, SENTENCE_PLANS)
    server.start()
    try:
        yield server
    finally:
        server.stop()


BASE_PARAMS = {
    "api_key": "test-key",
    "model": "cosyvoice-v3-flash",
    "pool_size": 1,
    "sample_rate": SAMPLE_RATE,
    "url": f"ws://127.0.0.1:{SERVER_PORT}",
    "voice": "longanyang",
}


def _property(enable_words: bool, params: dict[str, Any]) -> str:
    return json.dumps({"enable_words": enable_words, "params": params})


WORDS_ENABLED_PROPERTY = _property(
    True,
    # A stale provider switch must not win over enable_words.
    {**BASE_PARAMS, "word_timestamp_enabled": False},
)
WORDS_DISABLED_PROPERTY = _property(
    False,
    # Neither must a provider switch that tries to turn words on.
    {**BASE_PARAMS, "word_timestamp_enabled": True},
)


async def _send_request(
    ctx: TenTestContext,
    request_id: str,
    session_id: str = "words-session",
    turn_id: int = 1,
) -> None:
    request = TTSTextInput(
        request_id=request_id,
        text="The castle's shadow. Nobody moved away. 低头思故乡。",
        text_input_end=True,
        metadata={"session_id": session_id, "turn_id": turn_id},
    )
    data = Data.create("tts_text_input")
    data.set_property_from_json("", request.model_dump_json())
    await ctx.send_data(data)


async def _expect_text_result(ctx: TenTestContext) -> dict[str, Any]:
    data = await ctx.expect_data("tts_text_result", timeout=2.0)
    payload, error = data.get_property_to_json("")
    assert error is None
    return json.loads(payload)


async def _collect_results(
    ctx: TenTestContext,
    count: int,
) -> list[dict[str, Any]]:
    return [await _expect_text_result(ctx) for _ in range(count)]


async def _collect_audio_frames(
    ctx: TenTestContext,
    count: int,
) -> list[AudioFrame]:
    return [await ctx.expect_audio_frame(timeout=2.0) for _ in range(count)]


def _expected_batches() -> list[tuple[str, list[Word]]]:
    """Batches the extension must publish, in order, with anchored times.

    Every event publishes the words it has that were not published yet, minus
    the newest word, which the next event (or `sentence-end`) publishes.
    """
    batches: list[tuple[str, list[Word]]] = []
    for plan in SENTENCE_PLANS:
        anchor = plan.anchor_ms

        def anchored(entries: list[Word]) -> list[Word]:
            return [
                (text, begin + anchor, end + anchor)
                for text, begin, end in entries
            ]

        batches.append(
            ("sentence-begin", anchored([plan.begin_words[0]])),
        )
        batches.append(
            ("sentence-synthesis", anchored([plan.synthesis_words[1]])),
        )
        batches.append(("sentence-end", anchored(list(plan.words[2:]))))
    return batches


@ten_test(
    "cosy_tts_python",
    property_json_str=WORDS_ENABLED_PROPERTY,
    timeout=6.0,
)
async def test_words_are_published_once_on_the_pcm_clock(
    ctx: TenTestContext,
    word_server: FakeWordTimestampServer,
) -> None:
    await _send_request(ctx, "aligned-request")

    frames = await _collect_audio_frames(ctx, 2 * len(SENTENCE_PLANS))
    results = await _collect_results(ctx, 3 * len(SENTENCE_PLANS))
    terminal = await _expect_text_result(ctx)
    await ctx.expect_data("tts_audio_end", timeout=1.0)

    origin = frames[0].get_timestamp()
    # Audio frames advance with cumulative PCM samples.
    assert [frame.get_timestamp() - origin for frame in frames] == [
        index * CHUNK_AUDIO_MS for index in range(2 * len(SENTENCE_PLANS))
    ]

    expected = _expected_batches()
    starts: list[int] = []
    for index, (result, (event, batch_words)) in enumerate(
        zip(results, expected),
    ):
        words = result["words"]
        assert [word["word"] for word in words] == [
            text for text, _, _ in batch_words
        ], f"batch {index} ({event}) published other words"
        # The published text is exactly the words of this batch.
        assert result["text"] == "".join(word["word"] for word in words)
        # Word times are the provider's request-relative times plus origin.
        for word, (_, begin, end) in zip(words, batch_words):
            assert word["start_ms"] - origin == begin
            assert word["duration_ms"] == end - begin
        starts.append(result["start_ms"] - origin)

    # Each sentence's words are published once, in order, across its batches.
    for batch_index, plan in enumerate(SENTENCE_PLANS):
        published_words = [
            word["word"]
            for result in results[batch_index * 3 : batch_index * 3 + 3]
            for word in result["words"]
        ]
        assert published_words == [text for text, _, _ in plan.words]

    # Captions start strictly ascending, and the anchors follow the audio.
    assert starts == sorted(starts) and len(set(starts)) == len(starts)
    assert starts[:3] == [0, 200, 400]
    assert starts[3:6] == [800, 1000, 1200]
    # The sentence that counts from its own start is anchored to its audio.
    assert starts[6:] == [1600, 1800, 2000]

    for result in results:
        assert result["request_id"] == "aligned-request"
        assert result["text_result_end"] is False
        assert result["metadata"]["session_id"] == "words-session"
        assert result["metadata"]["turn_id"] == 1
        assert result["metadata"]["turn_status"] == 0
    assert [result["metadata"]["turn_seq_id"] for result in results] == list(
        range(len(results)),
    )

    assert terminal["words"] == []
    assert terminal["text"] == ""
    assert terminal["text_result_end"] is True
    assert terminal["metadata"]["turn_status"] == 1
    assert terminal["metadata"]["turn_seq_id"] == len(results)


@ten_test(
    "cosy_tts_python",
    property_json_str=WORDS_ENABLED_PROPERTY,
    timeout=6.0,
)
async def test_enable_words_forces_the_provider_switch_on(
    ctx: TenTestContext,
    word_server: FakeWordTimestampServer,
) -> None:
    await _send_request(ctx, "force-on-request")
    await ctx.expect_data("tts_audio_end", timeout=2.0)

    assert word_server.task_parameters[0]["word_timestamp_enabled"] is True


@ten_test(
    "cosy_tts_python",
    property_json_str=WORDS_DISABLED_PROPERTY,
    timeout=6.0,
)
async def test_enable_words_forces_the_provider_switch_off(
    ctx: TenTestContext,
    word_server: FakeWordTimestampServer,
) -> None:
    await _send_request(ctx, "force-off-request")
    await ctx.expect_data("tts_audio_end", timeout=2.0)

    assert word_server.task_parameters[0]["word_timestamp_enabled"] is False
    await ctx.assert_no_data("tts_text_result", timeout=0.5)


@ten_test(
    "cosy_tts_python",
    property_json_str=json.dumps({"params": BASE_PARAMS}),
    timeout=6.0,
)
async def test_words_are_off_by_default(
    ctx: TenTestContext,
    word_server: FakeWordTimestampServer,
) -> None:
    await _send_request(ctx, "default-words-request")
    await ctx.expect_data("tts_audio_end", timeout=2.0)

    assert word_server.task_parameters[0]["word_timestamp_enabled"] is False
    await ctx.assert_no_data("tts_text_result", timeout=0.5)


@ten_test(
    "cosy_tts_python",
    property_json_str=json.dumps(
        {
            "params": {
                **BASE_PARAMS,
                "enable_words": True,
                "word_timestamp_enabled": False,
            },
        },
    ),
    timeout=6.0,
)
async def test_nested_enable_words_is_not_forwarded(
    ctx: TenTestContext,
    word_server: FakeWordTimestampServer,
) -> None:
    await _send_request(ctx, "nested-enable-request")
    await ctx.expect_data("tts_audio_end", timeout=2.0)

    parameters = word_server.task_parameters[0]
    # Only the top-level property decides, and the nested copy never reaches
    # the provider as an unknown parameter.
    assert parameters["word_timestamp_enabled"] is False
    assert "enable_words" not in parameters

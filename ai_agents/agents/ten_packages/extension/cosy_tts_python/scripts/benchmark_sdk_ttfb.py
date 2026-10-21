"""Benchmark CosyVoice TTFB through the DashScope Python SDK.

Dependency:
    uv run --no-project --with 'dashscope==1.26.4' python benchmark_sdk_ttfb.py --help

The default pooled mode mirrors the repository extension. The primary
comparison metric is task_ttfb_ms: time immediately before streaming_call()
until the first audio callback. Use --mode fresh to include SDK WebSocket setup
inside each task.
"""

import argparse
import json
import os
import statistics
import threading
import time
from pathlib import Path
from typing import Any

import dashscope
from dashscope.audio.tts_v2 import (
    AudioFormat,
    ResultCallback,
    SpeechSynthesizer,
    SpeechSynthesizerObjectPool,
)


DEFAULT_TEXT = "你好，这是一次语音合成首包延迟测试。"
AUDIO_FORMATS = {
    ("pcm", 8000): AudioFormat.PCM_8000HZ_MONO_16BIT,
    ("pcm", 16000): AudioFormat.PCM_16000HZ_MONO_16BIT,
    ("pcm", 22050): AudioFormat.PCM_22050HZ_MONO_16BIT,
    ("pcm", 24000): AudioFormat.PCM_24000HZ_MONO_16BIT,
    ("pcm", 44100): AudioFormat.PCM_44100HZ_MONO_16BIT,
    ("pcm", 48000): AudioFormat.PCM_48000HZ_MONO_16BIT,
}


class BenchmarkError(RuntimeError):
    """Raised when the SDK cannot complete a benchmark task."""


class BenchmarkCallback(ResultCallback):
    def __init__(self) -> None:
        self.task_start_ns: int | None = None
        self.task_started_ns: int | None = None
        self.first_audio_ns: int | None = None
        self.task_finished_ns: int | None = None
        self.audio_chunks: list[bytes] = []
        self.error_message: str | None = None
        self.finished = threading.Event()

    def on_open(self) -> None:
        self.task_started_ns = time.perf_counter_ns()

    def on_complete(self) -> None:
        self.task_finished_ns = time.perf_counter_ns()
        self.finished.set()

    def on_error(self, message: str) -> None:
        self.error_message = message
        self.task_finished_ns = time.perf_counter_ns()
        self.finished.set()

    def on_close(self) -> None:
        return

    def on_event(self, message: str) -> None:
        del message

    def on_data(self, data: bytes) -> None:
        if self.first_audio_ns is None:
            self.first_audio_ns = time.perf_counter_ns()
        self.audio_chunks.append(bytes(data))


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _milliseconds(start_ns: int, end_ns: int) -> float:
    return round((end_ns - start_ns) / 1_000_000, 3)


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return round(
        ordered[lower] * (1 - weight) + ordered[upper] * weight,
        3,
    )


def _metric_summary(
    results: list[dict[str, Any]], key: str
) -> dict[str, float]:
    values = [float(result[key]) for result in results]
    return {
        "min": round(min(values), 3),
        "mean": round(statistics.mean(values), 3),
        "median": round(statistics.median(values), 3),
        "p95": _percentile(values, 0.95),
        "max": round(max(values), 3),
    }


def _audio_format(name: str, sample_rate: int) -> AudioFormat:
    audio_format = AUDIO_FORMATS.get((name, sample_rate))
    if audio_format is None:
        raise SystemExit(
            "The benchmark currently supports PCM at 8000, 16000, 22050, "
            "24000, 44100, or 48000 Hz",
        )
    return audio_format


def _borrow_or_create(
    args: argparse.Namespace,
    callback: BenchmarkCallback,
    pool: SpeechSynthesizerObjectPool | None,
) -> SpeechSynthesizer:
    common = {
        "callback": callback,
        "format": _audio_format(args.audio_format, args.sample_rate),
        "model": args.model,
        "voice": args.voice,
        "volume": args.volume,
        "speech_rate": args.rate,
        "pitch_rate": args.pitch,
    }
    if pool is not None:
        return pool.borrow_synthesizer(**common)
    return SpeechSynthesizer(
        **common,
        url=args.url or None,
        headers=_headers(args),
    )


def _headers(args: argparse.Namespace) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {args.api_key}",
        "User-Agent": "cosy-ttfb-dashscope-sdk/1.0",
    }


def _run_task(
    args: argparse.Namespace,
    pool: SpeechSynthesizerObjectPool | None,
    iteration: int,
    warmup: bool,
) -> tuple[dict[str, Any], bytes]:
    callback = BenchmarkCallback()
    end_to_end_start_ns = time.perf_counter_ns()
    create_start_ns = time.perf_counter_ns()
    synthesizer = _borrow_or_create(args, callback, pool)
    create_end_ns = time.perf_counter_ns()

    callback.task_start_ns = time.perf_counter_ns()
    streaming_call_start_ns = callback.task_start_ns
    try:
        synthesizer.streaming_call(args.text)
        streaming_call_end_ns = time.perf_counter_ns()
        synthesizer.async_streaming_complete(
            complete_timeout_millis=int(args.timeout_seconds * 1000),
        )
        if not callback.finished.wait(args.timeout_seconds):
            raise BenchmarkError(
                f"Timed out after {args.timeout_seconds}s waiting for task completion",
            )
        if callback.error_message:
            raise BenchmarkError(
                f"CosyVoice task failed: {callback.error_message}"
            )
        if callback.first_audio_ns is None or callback.task_finished_ns is None:
            raise BenchmarkError(
                "Task completed without audio or completion timestamp"
            )

        first_audio_ns = callback.first_audio_ns
        task_finished_ns = callback.task_finished_ns
        task_started_ns = callback.task_started_ns
        if task_started_ns is None:
            raise BenchmarkError("SDK did not invoke on_open/task-started")

        sdk_ttfb_ms = synthesizer.get_first_package_delay()
        audio = b"".join(callback.audio_chunks)
        result = {
            "implementation": "dashscope_sdk",
            "mode": args.mode,
            "iteration": iteration,
            "warmup": warmup,
            "vendor_request_id": synthesizer.get_last_request_id(),
            "object_acquire_ms": _milliseconds(create_start_ns, create_end_ns),
            "streaming_call_ms": _milliseconds(
                streaming_call_start_ns,
                streaming_call_end_ns,
            ),
            "task_start_ack_ms": _milliseconds(
                streaming_call_start_ns,
                task_started_ns,
            ),
            "task_ttfb_ms": _milliseconds(
                streaming_call_start_ns,
                first_audio_ns,
            ),
            "end_to_end_ttfb_ms": _milliseconds(
                end_to_end_start_ns,
                first_audio_ns,
            ),
            "sdk_reported_ttfb_ms": round(float(sdk_ttfb_ms), 3),
            "task_total_ms": _milliseconds(
                streaming_call_start_ns,
                task_finished_ns,
            ),
            "audio_chunks": len(callback.audio_chunks),
            "audio_bytes": len(audio),
        }
    except Exception:
        synthesizer.close()
        raise
    else:
        if pool is not None:
            pool.return_synthesizer(synthesizer)
        else:
            synthesizer.close()
        return result, audio


def _write_audio(output_dir: str, result: dict[str, Any], audio: bytes) -> None:
    if not output_dir or result["warmup"]:
        return
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    output_file = path / f"sdk_{result['mode']}_{result['iteration']:03d}.pcm"
    output_file.write_bytes(audio)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure CosyVoice TTFB through the DashScope Python SDK.",
    )
    parser.add_argument(
        "--url",
        default=_first_env("COSY_TTS_URL", "DASHSCOPE_WEBSOCKET_URL"),
        help="Full wss://.../api-ws/v1/inference URL.",
    )
    parser.add_argument(
        "--api-key",
        default=_first_env("COSY_TTS_API_KEY", "DASHSCOPE_API_KEY"),
    )
    parser.add_argument("--mode", choices=("pooled", "fresh"), default="pooled")
    parser.add_argument("--pool-size", type=int, default=2)
    parser.add_argument("--model", default="cosyvoice-v3-flash")
    parser.add_argument("--voice", default="longanyang")
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--audio-format", choices=("pcm",), default="pcm")
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--volume", type=int, default=50)
    parser.add_argument("--rate", type=float, default=1.0)
    parser.add_argument("--pitch", type=float, default=1.0)
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--output-dir", default="")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    if not args.url:
        raise SystemExit("Missing --url or COSY_TTS_URL")
    if not args.api_key:
        raise SystemExit(
            "Missing --api-key or COSY_TTS_API_KEY/DASHSCOPE_API_KEY"
        )
    if args.iterations <= 0 or args.warmup < 0:
        raise SystemExit(
            "--iterations must be positive and --warmup non-negative"
        )
    if not 1 <= args.pool_size <= 100:
        raise SystemExit("--pool-size must be between 1 and 100")

    dashscope.api_key = args.api_key
    pool: SpeechSynthesizerObjectPool | None = None
    pool_init_ms = 0.0
    if args.mode == "pooled":
        pool_start_ns = time.perf_counter_ns()
        pool = SpeechSynthesizerObjectPool(
            max_size=args.pool_size,
            url=args.url or None,
            headers=_headers(args),
        )
        pool_init_ms = _milliseconds(pool_start_ns, time.perf_counter_ns())
        print(json.dumps({"event": "pool_ready", "pool_init_ms": pool_init_ms}))

    measured_results: list[dict[str, Any]] = []
    try:
        total_iterations = args.warmup + args.iterations
        for index in range(total_iterations):
            warmup = index < args.warmup
            result, audio = _run_task(
                args,
                pool,
                iteration=index - args.warmup + 1,
                warmup=warmup,
            )
            print(json.dumps(result, ensure_ascii=False))
            _write_audio(args.output_dir, result, audio)
            if not warmup:
                measured_results.append(result)
    finally:
        if pool is not None:
            pool.shutdown()

    summary = {
        "implementation": "dashscope_sdk",
        "mode": args.mode,
        "iterations": len(measured_results),
        "pool_init_ms": pool_init_ms,
        "object_acquire_ms": _metric_summary(
            measured_results,
            "object_acquire_ms",
        ),
        "task_ttfb_ms": _metric_summary(measured_results, "task_ttfb_ms"),
        "end_to_end_ttfb_ms": _metric_summary(
            measured_results,
            "end_to_end_ttfb_ms",
        ),
        "sdk_reported_ttfb_ms": _metric_summary(
            measured_results,
            "sdk_reported_ttfb_ms",
        ),
        "task_total_ms": _metric_summary(measured_results, "task_total_ms"),
    }
    print(json.dumps({"summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Benchmark CosyVoice TTFB through the public WebSocket protocol.

Dependency:
    uv run --no-project --with websocket-client python benchmark_websocket_ttfb.py --help

The primary comparison metric is task_ttfb_ms: time immediately before
run-task is sent until the first binary audio frame is received.
"""

import argparse
import json
import os
import statistics
import time
import uuid
from pathlib import Path
from typing import Any

import websocket


DEFAULT_TEXT = "你好，这是一次语音合成首包延迟测试。"


class BenchmarkError(RuntimeError):
    """Raised when the provider protocol cannot complete a benchmark task."""


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


def _send_json(
    connection: websocket.WebSocket, message: dict[str, Any]
) -> None:
    connection.send(json.dumps(message, ensure_ascii=False))


def _parse_event(raw_message: str, expected_task_id: str) -> str:
    message = json.loads(raw_message)
    header = message.get("header", {})
    task_id = header.get("task_id")
    if task_id and task_id != expected_task_id:
        raise BenchmarkError(
            f"Received event for unexpected task_id {task_id}; "
            f"expected {expected_task_id}",
        )

    event = header.get("event", "")
    if event == "task-failed":
        raise BenchmarkError(
            "CosyVoice task failed: "
            f"{header.get('error_code', 'unknown')} "
            f"{header.get('error_message', '')}",
        )
    return event


def _connect(args: argparse.Namespace) -> tuple[websocket.WebSocket, float]:
    headers = {
        "Authorization": f"Bearer {args.api_key}",
        "User-Agent": "cosy-ttfb-direct-websocket/1.0",
    }

    started_ns = time.perf_counter_ns()
    connection = websocket.create_connection(
        args.url,
        header=headers,
        timeout=args.timeout_seconds,
        enable_multithread=True,
    )
    return connection, _milliseconds(started_ns, time.perf_counter_ns())


def _run_task(
    connection: websocket.WebSocket,
    args: argparse.Namespace,
    iteration: int,
    warmup: bool,
    end_to_end_start_ns: int,
) -> tuple[dict[str, Any], bytes]:
    task_id = str(uuid.uuid4())
    run_task = {
        "header": {
            "action": "run-task",
            "task_id": task_id,
            "streaming": "duplex",
        },
        "payload": {
            "task_group": "audio",
            "task": "tts",
            "function": "SpeechSynthesizer",
            "model": args.model,
            "parameters": {
                "text_type": "PlainText",
                "voice": args.voice,
                "format": args.audio_format,
                "sample_rate": args.sample_rate,
                "volume": args.volume,
                "rate": args.rate,
                "pitch": args.pitch,
                "enable_ssml": False,
            },
            "input": {},
        },
    }

    task_start_ns = time.perf_counter_ns()
    _send_json(connection, run_task)

    task_started_ns: int | None = None
    while task_started_ns is None:
        raw_message = connection.recv()
        match raw_message:
            case str():
                if _parse_event(raw_message, task_id) == "task-started":
                    task_started_ns = time.perf_counter_ns()
            case bytes():
                raise BenchmarkError("Received audio before task-started")
            case _:
                raise BenchmarkError("WebSocket closed before task-started")

    text_send_ns = time.perf_counter_ns()
    _send_json(
        connection,
        {
            "header": {
                "action": "continue-task",
                "task_id": task_id,
                "streaming": "duplex",
            },
            "payload": {"input": {"text": args.text}},
        },
    )
    _send_json(
        connection,
        {
            "header": {
                "action": "finish-task",
                "task_id": task_id,
                "streaming": "duplex",
            },
            "payload": {"input": {}},
        },
    )

    first_audio_ns: int | None = None
    task_finished_ns: int | None = None
    audio_chunks: list[bytes] = []
    while task_finished_ns is None:
        raw_message = connection.recv()
        match raw_message:
            case bytes():
                if first_audio_ns is None:
                    first_audio_ns = time.perf_counter_ns()
                audio_chunks.append(raw_message)
            case str():
                if _parse_event(raw_message, task_id) == "task-finished":
                    task_finished_ns = time.perf_counter_ns()
            case _:
                raise BenchmarkError("WebSocket closed before task-finished")

    if first_audio_ns is None:
        raise BenchmarkError("Task finished without binary audio")

    audio = b"".join(audio_chunks)
    result = {
        "implementation": "direct_websocket",
        "iteration": iteration,
        "warmup": warmup,
        "task_id": task_id,
        "task_start_ack_ms": _milliseconds(task_start_ns, task_started_ns),
        "task_ttfb_ms": _milliseconds(task_start_ns, first_audio_ns),
        "text_ttfb_ms": _milliseconds(text_send_ns, first_audio_ns),
        "end_to_end_ttfb_ms": _milliseconds(
            end_to_end_start_ns, first_audio_ns
        ),
        "task_total_ms": _milliseconds(task_start_ns, task_finished_ns),
        "audio_chunks": len(audio_chunks),
        "audio_bytes": len(audio),
    }
    return result, audio


def _write_audio(output_dir: str, result: dict[str, Any], audio: bytes) -> None:
    if not output_dir or result["warmup"]:
        return
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    output_file = path / f"direct_{result['iteration']:03d}.pcm"
    output_file.write_bytes(audio)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure CosyVoice TTFB through direct WebSocket calls.",
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
    parser.add_argument("--fresh-connection-per-task", action="store_true")
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

    connection: websocket.WebSocket | None = None
    measured_results: list[dict[str, Any]] = []
    connection_times: list[float] = []
    try:
        if not args.fresh_connection_per_task:
            connection, connect_ms = _connect(args)
            connection_times.append(connect_ms)
            print(
                json.dumps(
                    {"event": "connection_ready", "connect_ms": connect_ms}
                )
            )

        total_iterations = args.warmup + args.iterations
        for index in range(total_iterations):
            warmup = index < args.warmup
            trial_start_ns = time.perf_counter_ns()
            if connection is None:
                connection, connect_ms = _connect(args)
                if not warmup:
                    connection_times.append(connect_ms)
            else:
                connect_ms = 0.0

            result, audio = _run_task(
                connection,
                args,
                iteration=index - args.warmup + 1,
                warmup=warmup,
                end_to_end_start_ns=trial_start_ns,
            )
            result["connect_ms"] = connect_ms
            print(json.dumps(result, ensure_ascii=False))
            _write_audio(args.output_dir, result, audio)
            if not warmup:
                measured_results.append(result)

            if args.fresh_connection_per_task:
                connection.close()
                connection = None
    finally:
        if connection is not None:
            connection.close()

    summary = {
        "implementation": "direct_websocket",
        "mode": (
            "fresh_connection_per_task"
            if args.fresh_connection_per_task
            else "reused_connection"
        ),
        "iterations": len(measured_results),
        "connect_ms": {
            "mean": round(statistics.mean(connection_times), 3),
            "max": round(max(connection_times), 3),
        },
        "task_ttfb_ms": _metric_summary(measured_results, "task_ttfb_ms"),
        "text_ttfb_ms": _metric_summary(measured_results, "text_ttfb_ms"),
        "end_to_end_ttfb_ms": _metric_summary(
            measured_results,
            "end_to_end_ttfb_ms",
        ),
        "task_total_ms": _metric_summary(measured_results, "task_total_ms"),
    }
    print(json.dumps({"summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()

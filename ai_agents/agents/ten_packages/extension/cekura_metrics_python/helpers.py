"""
Helper functions for other TEN extensions to send metrics to the Cekura Metrics extension.

Usage in your extension:

    from cekura_metrics_python.helpers import (
        send_transcript,
        send_llm_response,
        send_tts_latency,
        send_asr_result,
        send_tool_call,
        start_session,
        end_session,
    )

    # In your on_start or when a call begins:
    await start_session(ten_env, session_id="call-123", channel_name="room-abc")

    # When you have transcript data:
    await send_transcript(ten_env, text="Hello!", role="assistant", is_final=True)

    # When LLM responds:
    await send_llm_response(ten_env, text="Response", latency_ms=250, model="gpt-4o")

    # When TTS generates audio:
    await send_tts_latency(ten_env, latency_ms=150, vendor="elevenlabs")

    # When ASR transcribes speech:
    await send_asr_result(ten_env, text="User said this", latency_ms=200, confidence=0.95)

    # When a tool is called:
    await send_tool_call(ten_env, name="get_weather", arguments='{"city":"NYC"}', result='{"temp":72}', success=True)

    # When the call ends:
    await end_session(ten_env, session_id="call-123", ended_reason="customer-hangup")
"""

import json
from typing import Optional, Any

from ten_runtime import AsyncTenEnv, Data, Cmd


async def send_transcript(
    ten_env: AsyncTenEnv,
    text: str,
    role: str = "assistant",
    is_final: bool = True,
    start_time: float = 0.0,
    end_time: float = 0.0,
) -> None:
    """Send a transcript message to the Cekura Metrics extension."""
    data = Data.create("transcript")
    data.set_property_string("text", text)
    data.set_property_string("role", role)
    data.set_property_bool("is_final", is_final)
    data.set_property_float("start_time", start_time)
    data.set_property_float("end_time", end_time)
    await ten_env.send_data(data)


async def send_llm_response(
    ten_env: AsyncTenEnv,
    text: str = "",
    latency_ms: float = 0.0,
    tokens_in: int = 0,
    tokens_out: int = 0,
    model: str = "",
) -> None:
    """Send LLM response metrics to the Cekura Metrics extension."""
    data = Data.create("llm_response")
    if text:
        data.set_property_string("text", text)
    data.set_property_float("latency_ms", latency_ms)
    data.set_property_int("tokens_in", tokens_in)
    data.set_property_int("tokens_out", tokens_out)
    if model:
        data.set_property_string("model", model)
    await ten_env.send_data(data)


async def send_tts_latency(
    ten_env: AsyncTenEnv,
    latency_ms: float,
    text: str = "",
    duration_ms: float = 0.0,
    vendor: str = "",
) -> None:
    """Send TTS latency metrics to the Cekura Metrics extension."""
    data = Data.create("tts_audio")
    data.set_property_float("latency_ms", latency_ms)
    if text:
        data.set_property_string("text", text)
    if duration_ms > 0:
        data.set_property_float("duration_ms", duration_ms)
    if vendor:
        data.set_property_string("vendor", vendor)
    await ten_env.send_data(data)


async def send_asr_result(
    ten_env: AsyncTenEnv,
    text: str,
    is_final: bool = True,
    latency_ms: float = 0.0,
    confidence: float = 0.0,
    vendor: str = "",
) -> None:
    """Send ASR result to the Cekura Metrics extension."""
    data = Data.create("asr_result")
    data.set_property_string("text", text)
    data.set_property_bool("is_final", is_final)
    data.set_property_float("latency_ms", latency_ms)
    if confidence > 0:
        data.set_property_float("confidence", confidence)
    if vendor:
        data.set_property_string("vendor", vendor)
    await ten_env.send_data(data)


async def send_tool_call(
    ten_env: AsyncTenEnv,
    name: str,
    arguments: str = "",
    result: str = "",
    success: bool = True,
    latency_ms: float = 0.0,
) -> None:
    """Send a tool call event to the Cekura Metrics extension."""
    data = Data.create("tool_call")
    data.set_property_string("name", name)
    data.set_property_string("arguments", arguments)
    data.set_property_string("result", result)
    data.set_property_bool("success", success)
    data.set_property_float("latency_ms", latency_ms)
    await ten_env.send_data(data)


async def start_session(
    ten_env: AsyncTenEnv,
    session_id: str,
    channel_name: str = "",
    customer_number: str = "",
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Start a new metrics collection session."""
    cmd = Cmd.create("session_start")
    cmd.set_property_string("session_id", session_id)
    if channel_name:
        cmd.set_property_string("channel_name", channel_name)
    if customer_number:
        cmd.set_property_string("customer_number", customer_number)
    if metadata:
        cmd.set_property_string("metadata", json.dumps(metadata))
    await ten_env.send_cmd(cmd)


async def end_session(
    ten_env: AsyncTenEnv,
    session_id: str,
    ended_reason: str = "",
) -> None:
    """End the current session and flush metrics to Cekura."""
    cmd = Cmd.create("session_end")
    cmd.set_property_string("session_id", session_id)
    if ended_reason:
        cmd.set_property_string("ended_reason", ended_reason)
    await ten_env.send_cmd(cmd)


async def flush_session(ten_env: AsyncTenEnv) -> None:
    """Manually flush the current session to Cekura."""
    cmd = Cmd.create("flush")
    await ten_env.send_cmd(cmd)

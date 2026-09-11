"""
Cekura Metrics Extension for TEN Framework

This extension collects metrics from various TEN components (ASR, STT, TTS, LLM, etc.)
and sends them to Cekura's observability API for analysis and evaluation.

Supported data inputs:
- transcript: Text from ASR/STT with role and timing
- llm_response: LLM responses with latency and token counts (if connected)
- tts_audio: TTS synthesis events with latency (if connected)
- asr_result: ASR transcripts (JSON root from ten_ai_base ASRResult)
- metrics: ModuleMetrics from STT/TTS/LLM (ttfw, ttlw, ttfb, ttft, …) when connected
- tool_call: Tool/function call events with success status

Commands:
- session_start: Begin a new metrics collection session (starts periodic auto-flush when enabled)
- session_end: End session and flush metrics to Cekura
- flush: Manually flush current session to Cekura (final send; clears session)
- on_user_joined / on_user_left: Optional RTC lifecycle from `agora_rtc` (same as main control);
  first join starts a session with a generated call id; last leave ends and flushes.

Auto-flush (when `auto_flush` is true) POSTs a full session snapshot on each interval while the
session is active, so data is pushed before `session_end` if the call is long.
"""

import asyncio
import json
import uuid
from typing import Any, Optional
from datetime import datetime

from ten_runtime import (
    AsyncExtension,
    AsyncTenEnv,
    Cmd,
    CmdResult,
    Data,
    StatusCode,
)

from .config import CekuraMetricsConfig
from .session import Session
from .client import CekuraClient, CekuraAPIError


def _msg_prop_str(msg: Cmd | Data, key: str, default: str = "") -> str:
    """Msg.get_property_string returns (value, TenError | None), not a bare string."""
    v, err = msg.get_property_string(key)
    return default if err is not None else v


def _msg_prop_bool(msg: Cmd | Data, key: str, default: bool = False) -> bool:
    v, err = msg.get_property_bool(key)
    return default if err is not None else v


def _msg_prop_float(msg: Cmd | Data, key: str, default: float = 0.0) -> float:
    v, err = msg.get_property_float(key)
    return default if err is not None else float(v)


def _msg_json_root_dict(msg: Cmd | Data) -> dict[str, Any] | None:
    """Payload from set_property_from_json(None, json). STT sends ASRResult this way (no flat keys)."""
    raw, err = msg.get_property_to_json(None)
    if err is not None or not raw:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None


class CekuraMetricsExtension(AsyncExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: Optional[CekuraMetricsConfig] = None
        self.client: Optional[CekuraClient] = None
        self.current_session: Optional[Session] = None
        self._auto_flush_task: Optional[asyncio.Task] = None
        self._ten_env: Optional[AsyncTenEnv] = None
        self._rtc_user_count: int = 0

    async def on_configure(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("Cekura Metrics: on_configure")

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("Cekura Metrics: on_init")
        await super().on_init(ten_env)

        config_str, prop_err = await ten_env.get_property_to_json("")
        if prop_err is not None:
            raise RuntimeError(f"get_property_to_json: {prop_err}")

        self.config = None
        self.client = None
        try:
            cfg = CekuraMetricsConfig.from_json(config_str)
            if not (cfg.api_key or "").strip():
                ten_env.log_warn(
                    "Cekura Metrics: no api_key (e.g. CEKURA_API_KEY); extension disabled for this run."
                )
                return
            cfg.validate()
            self.config = cfg
            self.client = CekuraClient(self.config)
            ten_env.log_info(
                f"Cekura Metrics: configured with agent_id={self.config.agent_id}"
            )
        except Exception as e:
            ten_env.log_error(
                f"Cekura Metrics: invalid configuration — extension disabled: {e}"
            )
            self.config = None
            self.client = None

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("Cekura Metrics: on_start")
        self._ten_env = ten_env

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("Cekura Metrics: on_stop")
        
        if self._auto_flush_task and not self._auto_flush_task.done():
            self._auto_flush_task.cancel()
            try:
                await self._auto_flush_task
            except asyncio.CancelledError:
                pass
        
        if self.current_session:
            await self._flush_session(ten_env)
        self._rtc_user_count = 0

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("Cekura Metrics: on_deinit")
        if self.client:
            await self.client.close()

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug(f"Cekura Metrics: on_cmd - {cmd_name}")

        if not self.client:
            cmd_result = CmdResult.create(StatusCode.OK, cmd)
            await ten_env.return_result(cmd_result)
            return

        try:
            if cmd_name == "session_start":
                await self._handle_session_start(ten_env, cmd)
            elif cmd_name == "session_end":
                await self._handle_session_end(ten_env, cmd)
            elif cmd_name == "flush":
                await self._handle_flush(ten_env, cmd)
            elif cmd_name == "on_user_joined":
                await self._handle_agora_user_joined(ten_env, cmd)
            elif cmd_name == "on_user_left":
                await self._handle_agora_user_left(ten_env, cmd)
            else:
                ten_env.log_warn(f"Cekura Metrics: unknown command - {cmd_name}")
                cmd_result = CmdResult.create(StatusCode.ERROR, cmd)
                cmd_result.set_property_string("error", f"Unknown command: {cmd_name}")
                await ten_env.return_result(cmd_result)
                return

            cmd_result = CmdResult.create(StatusCode.OK, cmd)
            await ten_env.return_result(cmd_result)
        except Exception as e:
            ten_env.log_error(f"Cekura Metrics: error handling command {cmd_name} - {e}")
            cmd_result = CmdResult.create(StatusCode.ERROR, cmd)
            cmd_result.set_property_string("error", str(e))
            await ten_env.return_result(cmd_result)

    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        data_name = data.get_name()
        ten_env.log_debug(f"Cekura Metrics: on_data - {data_name}")

        if not self.client:
            return

        if not self.current_session:
            ten_env.log_warn(f"Cekura Metrics: received data '{data_name}' but no active session")
            return

        try:
            if data_name == "transcript":
                await self._handle_transcript(ten_env, data)
            elif data_name == "llm_response":
                await self._handle_llm_response(ten_env, data)
            elif data_name == "tts_audio":
                await self._handle_tts_audio(ten_env, data)
            elif data_name == "asr_result":
                await self._handle_asr_result(ten_env, data)
            elif data_name == "text_data":
                await self._handle_text_data(ten_env, data)
            elif data_name == "metrics":
                await self._handle_module_metrics(ten_env, data)
            elif data_name == "tool_call":
                await self._handle_tool_call(ten_env, data)
            else:
                ten_env.log_debug(f"Cekura Metrics: ignoring unknown data type - {data_name}")
        except Exception as e:
            ten_env.log_error(f"Cekura Metrics: error handling data {data_name} - {e}")

    async def _handle_session_start(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        if self.current_session:
            ten_env.log_warn("Cekura Metrics: starting new session while previous session active, flushing previous")
            await self._flush_session(ten_env)

        session_id = _msg_prop_str(cmd, "session_id")
        channel_name = _msg_prop_str(cmd, "channel_name")
        customer_number = _msg_prop_str(cmd, "customer_number")
        metadata = {}
        metadata_str = _msg_prop_str(cmd, "metadata")
        if metadata_str:
            try:
                metadata = json.loads(metadata_str)
            except Exception:
                pass

        self.current_session = Session(
            session_id=session_id,
            channel_name=channel_name,
            customer_number=customer_number,
            metadata=metadata,
        )
        
        ten_env.log_info(f"Cekura Metrics: session started - {session_id}")

        if self.config.auto_flush:
            self._start_auto_flush(ten_env)

    async def _handle_session_end(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        if not self.current_session:
            ten_env.log_warn("Cekura Metrics: session_end received but no active session")
            return

        ended_reason = _msg_prop_str(cmd, "ended_reason")

        self.current_session.end(ended_reason)
        await self._flush_session(ten_env)

    async def _handle_flush(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        if not self.current_session:
            ten_env.log_warn("Cekura Metrics: flush received but no active session")
            return
        
        await self._flush_session(ten_env)

    def _channel_name_from_rtc_cmd(self, cmd: Cmd) -> str:
        """Best-effort channel name from Agora RTC on_user_* cmd payload (if present)."""
        try:
            raw, err = cmd.get_property_to_json(None)
            if err or not raw:
                return ""
            if isinstance(raw, str):
                data = json.loads(raw)
            else:
                data = raw
            if isinstance(data, dict):
                return str(
                    data.get("channel") or data.get("channel_name") or ""
                )
        except Exception:
            pass
        return ""

    async def _handle_agora_user_joined(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        """Mirror main_control: first RTC user starts a Cekura call session (no other extension edits)."""
        self._rtc_user_count += 1
        if self._rtc_user_count != 1:
            return

        if self.current_session:
            ten_env.log_warn(
                "Cekura Metrics: on_user_joined while session active; flushing previous"
            )
            await self._flush_session(ten_env)

        channel = self._channel_name_from_rtc_cmd(cmd)
        session_id = str(uuid.uuid4())
        metadata = {"session_source": "agora_rtc"}
        if channel:
            metadata["rtc_channel"] = channel

        self.current_session = Session(
            session_id=session_id,
            channel_name=channel,
            customer_number="",
            metadata=metadata,
        )
        ten_env.log_info(f"Cekura Metrics: RTC session started (auto) — {session_id}")

        if self.config.auto_flush:
            self._start_auto_flush(ten_env)

    async def _handle_agora_user_left(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        """Last RTC user left: end and flush (matches single-user voice agent)."""
        self._rtc_user_count -= 1
        if self._rtc_user_count > 0:
            return
        self._rtc_user_count = 0

        if not self.current_session:
            ten_env.log_warn("Cekura Metrics: on_user_left but no active session")
            return

        self.current_session.end("agora_on_user_left")
        await self._flush_session(ten_env)

    async def _handle_transcript(self, ten_env: AsyncTenEnv, data: Data) -> None:
        if not self.config.collect_transcripts:
            return

        text = _msg_prop_str(data, "text")
        role = _msg_prop_str(data, "role")

        is_final = _msg_prop_bool(data, "is_final", True)

        if not is_final:
            return

        start_time = _msg_prop_float(data, "start_time")
        end_time = _msg_prop_float(data, "end_time")

        cekura_role = "Main Agent" if role.lower() in ["bot", "assistant", "agent", "ai"] else "Testing Agent"
        
        self.current_session.add_transcript(
            role=cekura_role,
            content=text,
            start_time=start_time,
            end_time=end_time,
        )
        ten_env.log_debug(f"Cekura Metrics: transcript added - role={cekura_role}, len={len(text)}")

    async def _handle_module_metrics(self, ten_env: AsyncTenEnv, data: Data) -> None:
        """TEN AI base sends ModuleMetrics as data name \"metrics\" (ttfb, ttfw, ttft, etc.)."""
        if not self.config.collect_latency:
            return
        root = _msg_json_root_dict(data)
        if not root:
            return
        module = str(root.get("module", "") or "")
        vendor = str(root.get("vendor", "") or "")
        m = root.get("metrics")
        if not isinstance(m, dict):
            return

        metadata: dict[str, Any] = {}
        if vendor:
            metadata["vendor"] = vendor
        meta = root.get("metadata")
        if isinstance(meta, dict):
            for k in ("session_id", "turn_id", "model_id", "voice_id"):
                if k in meta and meta[k] is not None:
                    metadata[k] = meta[k]

        def _emit(kind: str, ms: float) -> None:
            self.current_session.add_latency_metric(kind, ms, **metadata)
            ten_env.log_debug(
                f"Cekura Metrics: {kind} latency from metrics msg: {ms}ms module={module}"
            )

        if module == "asr":
            # Prefer word-timing; skip actual_send / vendor_metrics (noisy or huge dicts).
            for key in ("ttfw", "ttlw"):
                v = m.get(key)
                if isinstance(v, (int, float)) and float(v) > 0:
                    _emit("asr", float(v))
                    return
        elif module == "tts":
            v = m.get("ttfb")
            if isinstance(v, (int, float)) and float(v) > 0:
                _emit("tts", float(v))
        elif module == "llm":
            for key in ("ttft", "ttfs"):
                v = m.get(key)
                if isinstance(v, (int, float)) and float(v) > 0:
                    _emit("llm", float(v))
                    return

    async def _handle_llm_response(self, ten_env: AsyncTenEnv, data: Data) -> None:
        if not self.config.collect_latency:
            return

        latency_ms = _msg_prop_float(data, "latency_ms")

        metadata = {}
        ti, err_ti = data.get_property_int("tokens_in")
        if err_ti is None:
            metadata["tokens_in"] = ti
        to, err_to = data.get_property_int("tokens_out")
        if err_to is None:
            metadata["tokens_out"] = to
        model = _msg_prop_str(data, "model")
        if model:
            metadata["model"] = model

        if latency_ms > 0:
            self.current_session.add_latency_metric("llm", latency_ms, **metadata)
            ten_env.log_debug(f"Cekura Metrics: LLM latency recorded - {latency_ms}ms")

    async def _handle_tts_audio(self, ten_env: AsyncTenEnv, data: Data) -> None:
        if not self.config.collect_latency:
            return

        latency_ms = _msg_prop_float(data, "latency_ms")

        metadata = {}
        dur, err_dur = data.get_property_float("duration_ms")
        if err_dur is None:
            metadata["duration_ms"] = dur
        vendor = _msg_prop_str(data, "vendor")
        if vendor:
            metadata["vendor"] = vendor

        if latency_ms > 0:
            self.current_session.add_latency_metric("tts", latency_ms, **metadata)
            ten_env.log_debug(f"Cekura Metrics: TTS latency recorded - {latency_ms}ms")

    async def _handle_asr_result(self, ten_env: AsyncTenEnv, data: Data) -> None:
        root = _msg_json_root_dict(data)
        if root:
            text = str(root.get("text", "") or "")
            is_final = bool(root.get("final", False))
            latency_ms = float(root.get("latency_ms", 0) or 0)
        else:
            text = _msg_prop_str(data, "text")
            is_final = _msg_prop_bool(data, "is_final", False)
            latency_ms = _msg_prop_float(data, "latency_ms")

        if self.config.collect_transcripts and is_final and text:
            self.current_session.add_transcript(
                role="Testing Agent",
                content=text,
                start_time=datetime.now().timestamp(),
                end_time=datetime.now().timestamp(),
            )

        if self.config.collect_latency and latency_ms > 0:
            metadata = {}
            if root:
                c = root.get("confidence")
                if isinstance(c, (int, float)):
                    metadata["confidence"] = float(c)
                v = root.get("vendor")
                if isinstance(v, str) and v:
                    metadata["vendor"] = v
            else:
                conf, err_conf = data.get_property_float("confidence")
                if err_conf is None:
                    metadata["confidence"] = conf
                vendor = _msg_prop_str(data, "vendor")
                if vendor:
                    metadata["vendor"] = vendor

            self.current_session.add_latency_metric("asr", latency_ms, **metadata)
            ten_env.log_debug(f"Cekura Metrics: ASR latency recorded - {latency_ms}ms")

    async def _handle_text_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        """
        Handle `text_data` emitted by ten_ai_base TTS (AssistantTranscription JSON).

        TTS base classes call send_data(Data.create("text_data")) without
        set_dests, so the runtime routes via graph connections. Subscribing to
        text_data from the TTS extension gives us the assistant-spoken
        transcript without touching main_python.
        """
        if not self.config.collect_transcripts:
            return

        root = _msg_json_root_dict(data)
        if not root:
            return

        obj = str(root.get("object", "") or "")
        if obj and obj != "assistant.transcription":
            ten_env.log_debug(
                f"Cekura Metrics: ignoring text_data with object={obj}"
            )
            return

        text = str(root.get("text", "") or "").strip()
        is_final = bool(root.get("is_final", False)) or bool(
            root.get("final", False)
        )
        if not text or not is_final:
            return

        start_ms = root.get("start_ms")
        duration_ms = root.get("duration_ms")
        now = datetime.now().timestamp()
        try:
            start_time = float(start_ms) / 1000.0 if start_ms is not None else now
        except Exception:
            start_time = now
        try:
            end_time = (
                start_time + (float(duration_ms) / 1000.0)
                if duration_ms is not None
                else now
            )
        except Exception:
            end_time = now

        self.current_session.add_transcript(
            role="Main Agent",
            content=text,
            start_time=start_time,
            end_time=end_time,
        )
        ten_env.log_debug(
            f"Cekura Metrics: assistant transcript added via text_data - len={len(text)}"
        )

    async def _handle_tool_call(self, ten_env: AsyncTenEnv, data: Data) -> None:
        if not self.config.collect_tool_calls:
            return

        name = _msg_prop_str(data, "name")
        arguments = _msg_prop_str(data, "arguments")
        result = _msg_prop_str(data, "result")
        success = _msg_prop_bool(data, "success", True)
        latency_ms = _msg_prop_float(data, "latency_ms")

        self.current_session.add_tool_call(
            name=name,
            arguments=arguments,
            result=result,
            success=success,
            latency_ms=latency_ms,
        )
        ten_env.log_debug(f"Cekura Metrics: tool call recorded - {name}, success={success}")

    def _start_auto_flush(self, ten_env: AsyncTenEnv) -> None:
        if not self.config or not self.config.auto_flush:
            return
        if self._auto_flush_task and not self._auto_flush_task.done():
            self._auto_flush_task.cancel()

        async def auto_flush_loop() -> None:
            while self.current_session and not self.current_session.ended_at:
                await asyncio.sleep(self.config.auto_flush_interval_ms / 1000)
                if not self.current_session or self.current_session.ended_at:
                    break
                if not self.current_session.has_observe_payload():
                    continue
                ten_env.log_debug("Cekura Metrics: auto-flush sending snapshot")
                await self._post_session(ten_env, self.current_session)

        self._auto_flush_task = asyncio.create_task(auto_flush_loop())

    async def _post_session(self, ten_env: AsyncTenEnv, session: Session) -> None:
        """POST one session snapshot to Cekura and emit metrics_sent (success or failure)."""
        if not self.client:
            return
        try:
            ten_env.log_info(f"Cekura Metrics: sending session {session.session_id}")
            result = await self.client.send_session(session)

            call_log_id = result.get("id", 0)
            ten_env.log_info(
                f"Cekura Metrics: session sent successfully, call_log_id={call_log_id}"
            )

            out_cmd = Cmd.create("metrics_sent")
            out_cmd.set_property_string("session_id", session.session_id)
            out_cmd.set_property_bool("success", True)
            out_cmd.set_property_int("call_log_id", call_log_id)
            await ten_env.send_cmd(out_cmd)

        except CekuraAPIError as e:
            ten_env.log_error(f"Cekura Metrics: API error - {e}")

            out_cmd = Cmd.create("metrics_sent")
            out_cmd.set_property_string("session_id", session.session_id)
            out_cmd.set_property_bool("success", False)
            await ten_env.send_cmd(out_cmd)

        except Exception as e:
            ten_env.log_error(f"Cekura Metrics: unexpected error - {e}")

            out_cmd = Cmd.create("metrics_sent")
            out_cmd.set_property_string("session_id", session.session_id)
            out_cmd.set_property_bool("success", False)
            await ten_env.send_cmd(out_cmd)

    async def _flush_session(self, ten_env: AsyncTenEnv) -> None:
        if not self.current_session:
            return

        if self._auto_flush_task and not self._auto_flush_task.done():
            self._auto_flush_task.cancel()
            try:
                await self._auto_flush_task
            except asyncio.CancelledError:
                pass

        session = self.current_session
        self.current_session = None

        if not session.has_observe_payload():
            ten_env.log_warn(
                f"Cekura Metrics: session {session.session_id} has no data to send"
            )
            return

        await self._post_session(ten_env, session)

"""TEN graph adapter for the Agora Mind Rust extension.

The bridge deliberately keeps the Agora Mind wire protocol in the existing
``agora_mind_extension_rust`` extension. It only translates ASR final results
to ``submit_user_input`` and completed top-level turns to TTS input.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from ten_runtime import (
    AsyncExtension,
    AsyncTenEnv,
    Cmd,
    CmdResult,
    Data,
    Loc,
    StatusCode,
)

from .config import AgoraMindBridgeConfig
from .protocol import (
    asr_final_key,
    pure_text_input,
    session_id_from_response,
    turn_key,
    turn_text_from_event,
)

FORWARDED_COMMANDS = {
    "create_workspace",
    "create_session",
    "flush_session",
    "set_session_debug",
    "delete_session",
}


class AgoraMindBridgeExtension(AsyncExtension):
    """Translate TEN ASR/TTS messages around Agora Mind's TEN extension."""

    def __init__(self, name: str):
        super().__init__(name)
        self.config = AgoraMindBridgeConfig()
        self.ten_env: AsyncTenEnv | None = None
        self.session_id: int | None = None
        self._last_final_text: str | None = None
        self._completed_turns: set[tuple[Any, ...]] = set()
        self._submitted_finals: set[tuple[str, int, int, str]] = set()
        self._session_epoch = 0

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        self.ten_env = ten_env
        config_json, error = await ten_env.get_property_to_json("")
        if error:
            raise ValueError(f"failed to read bridge properties: {error}")
        self.config = AgoraMindBridgeConfig.model_validate_json(config_json)
        self._reset_session(self.config.session_id)
        ten_env.log_info(
            "config: "
            + json.dumps(
                self.config.model_dump(exclude={"session_id"}),
                sort_keys=True,
            )
        )

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("Agora Mind bridge started")

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        session_id = self.session_id
        self._reset_session()
        if session_id is not None:
            result, error = await self._send_command(
                "delete_session", {"session_id": session_id}
            )
            if (
                error is not None
                or result is None
                or result.get_status_code() != StatusCode.OK
            ):
                ten_env.log_warn("could not delete Agora Mind Session on stop")

    def _reset_session(self, session_id: int | None = None) -> None:
        self._session_epoch += 1
        self.session_id = session_id
        self._last_final_text = None
        self._completed_turns.clear()
        self._submitted_finals.clear()

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        name = cmd.get_name()
        if name not in FORWARDED_COMMANDS:
            await self._return_error(
                ten_env, cmd, f"unsupported bridge command: {name}"
            )
            return

        payload, error = cmd.get_property_to_json(None)
        if error:
            await self._return_error(ten_env, cmd, str(error))
            return
        try:
            properties = json.loads(payload or "{}")
        except ValueError as error:
            await self._return_error(ten_env, cmd, str(error))
            return
        if not isinstance(properties, dict):
            await self._return_error(
                ten_env, cmd, "command properties must be an object"
            )
            return

        session_epoch = self._session_epoch
        result, send_error = await self._send_command(name, properties)
        if send_error is not None or result is None:
            await self._return_error(
                ten_env,
                cmd,
                str(send_error or "Agora Mind command returned no result"),
            )
            return
        if session_epoch != self._session_epoch:
            await self._return_error(
                ten_env, cmd, "Session changed while command was pending"
            )
            return

        response_json = self._result_property(result, "response_json")
        if (
            name == "create_session"
            and result.get_status_code() == StatusCode.OK
        ):
            self._reset_session(session_id_from_response(response_json or ""))
        elif (
            name in {"create_workspace", "delete_session"}
            and result.get_status_code() == StatusCode.OK
            and (
                name == "create_workspace"
                or properties.get("session_id") == self.session_id
            )
        ):
            self._reset_session()

        forwarded_result = CmdResult.create(result.get_status_code(), cmd)
        forwarded_result.set_property_string(
            "response_json",
            response_json
            or json.dumps(
                {
                    "type": "error",
                    "error": {
                        "kind": "bridge",
                        "message": "Agora Mind result omitted response_json",
                    },
                }
            ),
        )
        await ten_env.return_result(forwarded_result)

    async def on_data(self, ten_env: AsyncTenEnv, data: Data) -> None:
        name = data.get_name()
        payload_json, error = data.get_property_to_json(None)
        if error:
            ten_env.log_warn(f"bridge could not read {name}: {error}")
            return
        try:
            payload = json.loads(payload_json or "{}")
        except ValueError as error:
            ten_env.log_warn(f"bridge received invalid {name}: {error}")
            return
        if not isinstance(payload, dict):
            ten_env.log_warn(f"bridge received non-object {name}")
            return

        if name == "asr_result":
            await self._handle_asr_result(ten_env, payload)
        elif name == "agora_mind_event":
            await self._handle_agora_event(ten_env, payload)

    async def _handle_asr_result(
        self, ten_env: AsyncTenEnv, payload: dict[str, Any]
    ) -> None:
        if payload.get("final") is not True:
            return
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            return
        normalized = text.strip()
        key = asr_final_key(payload, normalized)
        if key in self._submitted_finals or (
            key is None and normalized == self._last_final_text
        ):
            ten_env.log_debug("duplicate ASR final ignored")
            return
        if self.session_id is None:
            ten_env.log_warn("ASR final ignored before a Session is created")
            return

        metadata = payload.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        input_payload = pure_text_input(normalized, metadata.get("created_at"))
        # Reserve before awaiting: concurrent duplicate finals and ambiguous
        # command timeouts must not resubmit an input that may be accepted.
        self._last_final_text = normalized
        if key is not None:
            self._submitted_finals.add(key)
        session_id = self.session_id
        session_epoch = self._session_epoch
        result, error = await self._send_command(
            "submit_user_input",
            {
                "session_id": session_id,
                "input_json": json.dumps(input_payload, ensure_ascii=False),
            },
        )
        if session_epoch != self._session_epoch:
            return
        if error is not None or result is None:
            await self._report_input_error(
                ten_env,
                session_id,
                f"submit_user_input failed: {error or 'missing result'}",
            )
            return
        if result.get_status_code() != StatusCode.OK:
            await self._report_input_error(
                ten_env,
                session_id,
                "Agora Mind rejected ASR final",
                self._result_property(result, "response_json"),
            )

    async def _report_input_error(
        self,
        ten_env: AsyncTenEnv,
        session_id: int,
        message: str,
        response_json: str | None = None,
    ) -> None:
        ten_env.log_error(message)
        metadata = {
            "session_id": str(session_id),
            "example_id": self.config.example_id,
        }
        if response_json is not None:
            metadata["response_json"] = response_json
        output = Data.create("error")
        output.set_property_from_json(
            None,
            json.dumps(
                {
                    "module": "agora_mind_bridge",
                    "code": 1000,  # TEN NON_FATAL_ERROR; the bridge stays usable.
                    "message": message,
                    "metadata": metadata,
                }
            ),
        )
        await ten_env.send_data(output)

    async def _handle_agora_event(
        self, ten_env: AsyncTenEnv, payload: dict[str, Any]
    ) -> None:
        event_json = payload.get("event_json")
        if not isinstance(event_json, str):
            ten_env.log_warn("agora_mind_event omitted event_json")
            return
        try:
            event_payload = json.loads(event_json)
        except ValueError:
            ten_env.log_warn("agora_mind_event contained invalid event_json")
            return
        if not isinstance(event_payload, dict):
            ten_env.log_warn("agora_mind_event was not a JSON object")
            return
        if event_payload.get("type") == "extension.connection_state":
            if event_payload.get("state") == "disconnected":
                self._reset_session()
            return
        event = event_payload.get("event")
        if (
            isinstance(event, dict)
            and event.get("type") in {"session_failed", "session_deleted"}
            and event.get("session_id") == self.session_id
        ):
            self._reset_session()
            return
        if self.session_id is None:
            return

        key = turn_key(event_json)
        if key is None:
            return
        if key in self._completed_turns:
            ten_env.log_debug("duplicate Agora Mind turn ignored")
            return
        completed = turn_text_from_event(event_json, self.session_id)
        if completed is None:
            return
        session_id, text = completed
        self.session_id = session_id
        turn_index = len(self._completed_turns) + 1
        output = Data.create("tts_text_input")
        output.set_dests([Loc("", "", self.config.tts_extension)])
        output.set_property_from_json(
            None,
            json.dumps(
                {
                    "request_id": f"fdb-tts-{session_id}-{turn_index}",
                    "text": text,
                    "text_input_end": True,
                    "metadata": {
                        "session_id": str(session_id),
                        "example_id": self.config.example_id,
                        "turn_id": turn_index,
                    },
                },
                ensure_ascii=False,
            ),
        )
        # Reserve before sending so overlapping or delayed completion events
        # cannot synthesize a response twice.
        self._completed_turns.add(key)
        self._last_final_text = None
        await ten_env.send_data(output)

    async def _send_command(
        self, name: str, properties: dict[str, Any]
    ) -> tuple[Any, Any]:
        if self.ten_env is None:
            return None, RuntimeError("bridge is not initialized")
        command = Cmd.create(name)
        command.set_dests([Loc("", "", self.config.agora_mind_extension)])
        command.set_property_from_json(None, json.dumps(properties))
        try:
            return await asyncio.wait_for(
                self.ten_env.send_cmd(command),
                timeout=self.config.command_timeout_ms / 1000,
            )
        except asyncio.TimeoutError:
            return None, TimeoutError(f"{name} timed out")
        except Exception as error:
            return None, error

    async def _return_error(
        self, ten_env: AsyncTenEnv, cmd: Cmd, detail: str
    ) -> None:
        result = CmdResult.create(StatusCode.ERROR, cmd)
        result.set_property_string(
            "response_json",
            json.dumps(
                {
                    "type": "error",
                    "error": {"kind": "bridge", "message": detail},
                }
            ),
        )
        await ten_env.return_result(result)

    @staticmethod
    def _result_property(result: Any, name: str) -> str | None:
        try:
            value = result.get_property_string(name)
        except (AttributeError, TypeError):
            return None
        if isinstance(value, tuple):
            value, error = value
            if error:
                return None
        return value if isinstance(value, str) else None

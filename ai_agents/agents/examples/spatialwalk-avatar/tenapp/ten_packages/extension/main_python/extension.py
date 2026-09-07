import asyncio
import json
import time
from typing import Literal

from .agent.decorators import agent_event_handler
from ten_runtime import (
    AsyncExtension,
    AsyncTenEnv,
    Cmd,
    Data,
)
from ten_runtime.msg import Loc

from .agent.agent import Agent
from .agent.events import (
    ASRResultEvent,
    LLMResponseEvent,
    ToolRegisterEvent,
    UserJoinedEvent,
    UserLeftEvent,
)
from .helper import _send_cmd, _send_data, parse_sentences
from .config import MainControlConfig  # assume extracted from your base model
from ten_ai_base.types import (
    LLMToolMetadata,
    LLMToolMetadataParameter,
    LLMToolResult,
    LLMToolResultLLMResult,
)

import uuid

TOOL_TRIGGER_EFFECT = "trigger_effect"
TOOL_SHOW_FORTUNE_RESULT = "show_fortune_result"
EFFECT_NAMES = {"gold_rain", "fireworks"}
FORTUNE_IMAGE_IDS = {
    "fortune_rich",
    "fortune_love",
    "fortune_lazy",
    "fortune_body",
    "fortune_career",
}


class MainControlExtension(AsyncExtension):
    """
    The entry point of the agent module.
    Consumes semantic AgentEvents from the Agent class and drives the runtime behavior.
    """

    def __init__(self, name: str):
        super().__init__(name)
        self.ten_env: AsyncTenEnv = None
        self.agent: Agent = None
        self.config: MainControlConfig = None

        self.stopped: bool = False
        self._rtc_user_count: int = 0
        self.sentence_fragment: str = ""
        self.turn_id: int = 0
        self.session_id: str = "0"
        self._transcript_batch_interval_ms: int = 120
        self._pending_transcript_payloads: dict[str, dict] = {}
        self._pending_transcript_lock = asyncio.Lock()
        self._transcript_flush_task: asyncio.Task | None = None

    def _current_metadata(self) -> dict:
        return {"session_id": self.session_id, "turn_id": self.turn_id}

    async def on_init(self, ten_env: AsyncTenEnv):
        self.ten_env = ten_env

        # Load config from runtime properties
        config_json, _ = await ten_env.get_property_to_json(None)
        self.config = MainControlConfig.model_validate_json(config_json)

        self.agent = Agent(ten_env)

        # Now auto-register decorated methods
        for attr_name in dir(self):
            fn = getattr(self, attr_name)
            event_type = getattr(fn, "_agent_event_type", None)
            if event_type:
                self.agent.on(event_type, fn)

        for tool in self._build_local_tool_metadata():
            if tool.name == TOOL_TRIGGER_EFFECT:
                await self.agent.register_local_tool(
                    tool, self.name, self._run_trigger_effect_tool
                )
            elif tool.name == TOOL_SHOW_FORTUNE_RESULT:
                await self.agent.register_local_tool(
                    tool, self.name, self._run_show_fortune_result_tool
                )

    # === Register handlers with decorators ===
    @agent_event_handler(UserJoinedEvent)
    async def _on_user_joined(self, event: UserJoinedEvent):
        self._rtc_user_count += 1
        if self._rtc_user_count == 1 and self.config and self.config.greeting:
            await self._send_to_tts(self.config.greeting, True)
            await self._send_transcript(
                "assistant", self.config.greeting, True, 100
            )

    @agent_event_handler(UserLeftEvent)
    async def _on_user_left(self, event: UserLeftEvent):
        self._rtc_user_count -= 1

    @agent_event_handler(ToolRegisterEvent)
    async def _on_tool_register(self, event: ToolRegisterEvent):
        await self.agent.register_llm_tool(event.tool, event.source)

    @agent_event_handler(ASRResultEvent)
    async def _on_asr_result(self, event: ASRResultEvent):
        self.session_id = event.metadata.get("session_id", "100")
        stream_id = int(self.session_id)
        if not event.text:
            return
        if event.final or len(event.text) > 2:
            await self._interrupt()
        if event.final:
            self.turn_id += 1
            await self.agent.queue_llm_input(event.text)
        await self._send_transcript("user", event.text, event.final, stream_id)

    @agent_event_handler(LLMResponseEvent)
    async def _on_llm_response(self, event: LLMResponseEvent):
        if not event.is_final and event.type == "message":
            sentences, self.sentence_fragment = parse_sentences(
                self.sentence_fragment, event.delta
            )
            for s in sentences:
                await self._send_to_tts(s, False)

        if event.is_final and event.type == "message":
            remaining_text = self.sentence_fragment or ""
            self.sentence_fragment = ""
            await self._send_to_tts(remaining_text, True)

        await self._send_transcript(
            "assistant",
            event.text,
            event.is_final,
            100,
            data_type=("reasoning" if event.type == "reasoning" else "text"),
        )

    async def on_start(self, ten_env: AsyncTenEnv):
        ten_env.log_info("[MainControlExtension] on_start")
        self._transcript_flush_task = asyncio.create_task(
            self._transcript_flush_loop()
        )

    async def on_stop(self, ten_env: AsyncTenEnv):
        ten_env.log_info("[MainControlExtension] on_stop")
        self.stopped = True
        if self._transcript_flush_task:
            self._transcript_flush_task.cancel()
            try:
                await self._transcript_flush_task
            except asyncio.CancelledError:
                pass
            self._transcript_flush_task = None
        await self._flush_pending_transcripts()
        await self.agent.stop()

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd):
        await self.agent.on_cmd(cmd)

    async def on_data(self, ten_env: AsyncTenEnv, data: Data):
        await self.agent.on_data(data)

    # === helpers ===
    async def _send_transcript(
        self,
        role: str,
        text: str,
        final: bool,
        stream_id: int,
        data_type: Literal["text", "reasoning"] = "text",
    ):
        """
        Sends the transcript (ASR or LLM output) through RTM.
        """
        if not text:
            return
        payload: dict
        if data_type == "text":
            payload = {
                "data_type": "transcribe",
                "role": role,
                "text": text,
                "text_ts": int(time.time() * 1000),
                "is_final": final,
                "stream_id": stream_id,
            }
        elif data_type == "reasoning":
            payload = {
                "data_type": "raw",
                "role": role,
                "text": json.dumps(
                    {
                        "type": "reasoning",
                        "data": {
                            "text": text,
                        },
                    }
                ),
                "text_ts": int(time.time() * 1000),
                "is_final": final,
                "stream_id": stream_id,
            }
        else:
            return
        if final:
            # Ensure final update is emitted immediately and in order.
            await self._flush_pending_transcripts_for_key(
                role=role, stream_id=stream_id, data_type=data_type
            )
            await self._publish_rtm_message(payload)
        else:
            await self._enqueue_pending_transcript(
                role=role,
                stream_id=stream_id,
                data_type=data_type,
                payload=payload,
            )
        self.ten_env.log_info(
            f"[MainControlExtension] Sent transcript: {role}, final={final}, text={text}"
        )

    def _transcript_pending_key(
        self, role: str, stream_id: int, data_type: str
    ) -> str:
        return f"{role}:{stream_id}:{data_type}"

    async def _enqueue_pending_transcript(
        self, role: str, stream_id: int, data_type: str, payload: dict
    ) -> None:
        key = self._transcript_pending_key(role, stream_id, data_type)
        async with self._pending_transcript_lock:
            self._pending_transcript_payloads[key] = payload

    async def _flush_pending_transcripts_for_key(
        self, role: str, stream_id: int, data_type: str
    ) -> None:
        key = self._transcript_pending_key(role, stream_id, data_type)
        payload = None
        async with self._pending_transcript_lock:
            payload = self._pending_transcript_payloads.pop(key, None)
        if payload:
            await self._publish_rtm_message(payload)

    async def _flush_pending_transcripts(self) -> None:
        async with self._pending_transcript_lock:
            payloads = list(self._pending_transcript_payloads.values())
            self._pending_transcript_payloads.clear()
        for payload in payloads:
            await self._publish_rtm_message(payload)

    async def _transcript_flush_loop(self) -> None:
        interval = max(20, self._transcript_batch_interval_ms) / 1000
        try:
            while not self.stopped:
                await asyncio.sleep(interval)
                await self._flush_pending_transcripts()
        except asyncio.CancelledError:
            return

    async def _publish_rtm_message(self, payload: dict) -> None:
        """
        Publish a JSON message to agora_rtm. The extension expects binary payload in "message".
        """
        cmd = Cmd.create("publish")
        cmd.set_dests([Loc("", "", "agora_rtm")])
        cmd.set_property_buf("message", json.dumps(payload).encode())
        _, err = await self.ten_env.send_cmd(cmd)
        if err:
            self.ten_env.log_error(
                f"[MainControlExtension] Failed to publish RTM message: {err}"
            )

    async def _send_to_tts(self, text: str, is_final: bool):
        """
        Sends a sentence to the TTS system.
        """
        request_id = f"tts-request-{self.turn_id}"
        await _send_data(
            self.ten_env,
            "tts_text_input",
            "tts",
            {
                "request_id": request_id,
                "text": text,
                "text_input_end": is_final,
                "metadata": self._current_metadata(),
            },
        )
        self.ten_env.log_info(
            f"[MainControlExtension] Sent to TTS: is_final={is_final}, text={text}"
        )

    async def _interrupt(self):
        """
        Interrupts ongoing LLM and TTS generation. Typically called when user speech is detected.
        """
        self.sentence_fragment = ""
        await self.agent.flush_llm()
        await _send_data(
            self.ten_env, "tts_flush", "tts", {"flush_id": str(uuid.uuid4())}
        )
        await _send_cmd(self.ten_env, "flush", "avatar")
        await _send_cmd(self.ten_env, "flush", "agora_rtc")
        self.ten_env.log_info("[MainControlExtension] Interrupt signal sent")

    def _build_local_tool_metadata(self) -> list[LLMToolMetadata]:
        return [
            LLMToolMetadata(
                name=TOOL_TRIGGER_EFFECT,
                description="Trigger a festive screen effect overlay.",
                parameters=[
                    LLMToolMetadataParameter(
                        name="name",
                        type="string",
                        description="Effect name: gold_rain or fireworks.",
                        required=True,
                    )
                ],
            ),
            LLMToolMetadata(
                name=TOOL_SHOW_FORTUNE_RESULT,
                description="Show fortune card modal with image id.",
                parameters=[
                    LLMToolMetadataParameter(
                        name="image_id",
                        type="string",
                        description=(
                            "Fortune card id: fortune_rich, fortune_love, "
                            "fortune_lazy, fortune_body, fortune_career."
                        ),
                        required=True,
                    )
                ],
            ),
        ]

    async def _emit_ui_action(self, action: str, data: dict) -> None:
        await self._publish_rtm_message(
            {
                "data_type": "raw",
                "role": "assistant",
                "text": json.dumps(
                    {
                        "type": "action",
                        "data": {
                            "action": action,
                            "data": data,
                        },
                    }
                ),
                "text_ts": int(time.time() * 1000),
                "is_final": True,
                "stream_id": 100,
            }
        )

    async def _run_trigger_effect_tool(
        self, args: dict
    ) -> LLMToolResult | None:
        effect_name = str(args.get("name", "")).strip()
        if effect_name not in EFFECT_NAMES:
            self.ten_env.log_warn(
                f"[MainControlExtension] Invalid effect name: {effect_name}"
            )
            return LLMToolResultLLMResult(
                type="llmresult",
                content=(
                    f"Unsupported effect name: {effect_name}. "
                    "Use gold_rain or fireworks."
                ),
            )

        await self._emit_ui_action(TOOL_TRIGGER_EFFECT, {"name": effect_name})
        return LLMToolResultLLMResult(
            type="llmresult",
            content=f"effect {effect_name} triggered",
        )

    async def _run_show_fortune_result_tool(
        self, args: dict
    ) -> LLMToolResult | None:
        image_id = str(args.get("image_id", "")).strip()
        if image_id not in FORTUNE_IMAGE_IDS:
            self.ten_env.log_warn(
                f"[MainControlExtension] Invalid fortune image_id: {image_id}"
            )
            return LLMToolResultLLMResult(
                type="llmresult",
                content=(
                    f"Unsupported fortune image_id: {image_id}. "
                    "Use a supported fortune card id."
                ),
            )

        await self._emit_ui_action(
            TOOL_SHOW_FORTUNE_RESULT, {"image_id": image_id}
        )
        return LLMToolResultLLMResult(
            type="llmresult",
            content=f"fortune card {image_id} displayed",
        )

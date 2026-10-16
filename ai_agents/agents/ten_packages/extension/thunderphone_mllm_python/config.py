#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""Extension configuration and the session.update it turns into.

Kept free of ten_runtime imports so it can be unit-tested anywhere.
"""
from typing import Any, Union

from pydantic import BaseModel, field_validator

from .realtime.struct import SessionUpdate, SessionUpdateParams

DEFAULT_BASE_URL = "wss://api.thunderphone.com"
DEFAULT_PATH = "/v1/realtime"
API_KEY_PREFIX = "sk_live_"
SUPPORTED_SAMPLE_RATES = (16000, 24000)


class ThunderPhoneRealtimeConfig(BaseModel):
    api_key: str = ""
    base_url: str = DEFAULT_BASE_URL
    path: str = DEFAULT_PATH
    # A saved ThunderPhone agent: prompt, voice, engine, languages, tools and
    # greeting live on ThunderPhone. Leave empty for an inline session.
    agent_id: Union[str, int] = ""
    # Inline sessions only.
    product: str = ""
    voice: str = ""
    language: str = ""
    prompt: str = ""
    # Recorded on the call when the graph fronts a phone line.
    from_number: str = ""
    to_number: str = ""
    # Stream caller transcript fragments mid-utterance (billed extra).
    live_transcripts: bool = False
    sample_rate: int = 24000
    dump: bool = False
    dump_path: str = ""

    @field_validator("agent_id", mode="before")
    @classmethod
    def _agent_id_as_str(cls, value: Any) -> str:
        return "" if value is None else str(value).strip()

    @property
    def saved_agent(self) -> bool:
        return bool(self.agent_id)

    def validate_for_start(self) -> None:
        """Raise ValueError for a configuration the server would reject."""
        if not self.api_key.startswith(API_KEY_PREFIX):
            raise ValueError(
                f"api_key must be a ThunderPhone secret key ({API_KEY_PREFIX}...)"
            )
        if not self.saved_agent and not self.prompt.strip():
            raise ValueError(
                "prompt is required for an inline session (or set agent_id)"
            )
        if self.sample_rate not in SUPPORTED_SAMPLE_RATES:
            raise ValueError(
                f"sample_rate must be one of {SUPPORTED_SAMPLE_RATES}"
            )

    def query(self) -> dict[str, str]:
        """Connect-URL query: who to call, wire audio, and call.* events."""
        query: dict[str, str] = {}
        if self.saved_agent:
            query["agent_id"] = self.agent_id
        else:
            if self.product:
                query["product"] = self.product
            if self.language:
                query["language"] = self.language
        if self.from_number:
            query["from_number"] = self.from_number
        if self.to_number:
            query["to_number"] = self.to_number
        rate = str(self.sample_rate)
        query.update(
            {
                "input_audio_format": "pcm16",
                "input_rate": rate,
                "output_audio_format": "pcm16",
                "output_rate": rate,
                # Hang-up reason, transfer and keypad events. For a saved
                # agent this is the only way to opt in; inline sessions also
                # set it in session.config below.
                "call_events": "1",
            }
        )
        return query


def tool_dict(tool: Any) -> dict[str, Any]:
    """An LLMToolMetadata as an OpenAI function tool."""
    t: dict[str, Any] = {
        "type": "function",
        "name": tool.name,
        "description": tool.description,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    }
    for param in tool.parameters:
        t["parameters"]["properties"][param.name] = {
            "type": param.type,
            "description": param.description,
        }
        if param.required:
            t["parameters"]["required"].append(param.name)
    return t


def inline_session_update(
    config: ThunderPhoneRealtimeConfig, tools: list[Any]
) -> SessionUpdate:
    """The one session.update that starts an inline call.

    ThunderPhone freezes instructions, tools and voice on this event, so
    everything the session needs goes into it at once.
    """
    params = SessionUpdateParams(
        instructions=config.prompt,
        tools=[tool_dict(t) for t in tools] if tools else None,
        tool_choice="auto" if tools else None,
        voice=config.voice or None,
        config={"call_events": True},
        live_transcripts=True if config.live_transcripts else None,
    )
    return SessionUpdate(session=params)

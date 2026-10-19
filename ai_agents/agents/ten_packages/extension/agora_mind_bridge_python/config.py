"""Configuration for the Agora Mind TEN bridge."""

from pydantic import BaseModel, Field, field_validator


class AgoraMindBridgeConfig(BaseModel):
    """Names and limits used by the graph-local bridge."""

    agora_mind_extension: str = Field(default="agora_mind", min_length=1)
    tts_extension: str = Field(default="tts", min_length=1)
    example_id: str = ""
    session_id: int | None = Field(default=None, ge=1)
    command_timeout_ms: int = Field(default=30_000, ge=1)

    @field_validator("agora_mind_extension", "tts_extension")
    @classmethod
    def validate_extension_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("extension name must not be empty")
        return value

    @field_validator("example_id")
    @classmethod
    def normalize_example_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("session_id", mode="before")
    @classmethod
    def normalize_session_id(cls, value):
        if value in (None, "", 0, "0"):
            return None
        return value

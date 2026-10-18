"""Configuration for the Jev decision extension."""

from pydantic import BaseModel, Field


class JevParams(BaseModel):
    api_key: str = ""
    base_url: str = "https://api.typesafe.ai"
    model: str = "jev-1.13.0"
    timeout_ms: int = Field(default=1000, ge=1, le=30000)


class JevConfig(BaseModel):
    params: JevParams = JevParams()

    def safe_summary(self) -> str:
        """Return a loggable summary without credentials."""
        return (
            f"model={self.params.model}, "
            f"timeout_ms={self.params.timeout_ms}, "
            f"api_key_configured={bool(self.params.api_key)}"
        )

"""
WebSocket Server Extension Configuration
"""

from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field


class WebSocketServerConfig(BaseModel):
    """Configuration for WebSocket server extension"""

    # Server settings
    port: int = Field(default=8765, description="WebSocket server port")
    host: str = Field(default="0.0.0.0", description="WebSocket server host")
    command_timeout_ms: int = Field(default=30000, ge=1)

    # Fixed audio parameters (16kHz mono 16-bit PCM)
    sample_rate: int = Field(
        default=16000, description="Audio sample rate in Hz"
    )
    channels: int = Field(default=1, description="Number of audio channels")
    bytes_per_sample: int = Field(
        default=2, description="Bytes per sample (2 for 16-bit)"
    )

    # Debug settings
    dump: bool = Field(
        default=False, description="Enable audio dump for debugging"
    )
    dump_path: str = Field(
        default_factory=lambda: str(
            Path(__file__).parent / "websocket_server_dump.pcm"
        ),
        description="Path to dump audio data",
    )
    dump_max_bytes: int = Field(
        default=50 * 1024 * 1024,
        description="Maximum dump file size in bytes before truncation (default 50MB)",
    )

    # Additional params (for future extensibility)
    params: dict[str, Any] = Field(
        default_factory=dict, description="Additional parameters"
    )

    def validate_config(self) -> None:
        """Validate configuration parameters"""
        if self.port < 1 or self.port > 65535:
            raise ValueError(f"Invalid port number: {self.port}")

        if self.sample_rate <= 0:
            raise ValueError(f"Invalid sample rate: {self.sample_rate}")

        if self.channels <= 0:
            raise ValueError(f"Invalid number of channels: {self.channels}")

        if self.bytes_per_sample not in [1, 2, 4]:
            raise ValueError(
                f"Invalid bytes_per_sample: {self.bytes_per_sample} (must be 1, 2, or 4)"
            )
        if self.dump_max_bytes <= 0:
            raise ValueError(f"Invalid dump_max_bytes: {self.dump_max_bytes}")

    def to_str(self) -> str:
        """
        Convert config to string for logging

        Returns:
            String representation of config
        """
        # No sensitive data in this config currently
        return f"{self.model_dump()}"

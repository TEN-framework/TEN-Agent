from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class CekuraMetricsConfig:
    api_key: str = ""
    agent_id: int = 0
    assistant_id: str = ""
    base_url: str = "https://api.cekura.ai"
    auto_flush: bool = True
    auto_flush_interval_ms: int = 5000
    metric_ids: str = ""
    collect_latency: bool = True
    collect_transcripts: bool = True
    collect_tool_calls: bool = True

    @classmethod
    def from_json(cls, json_str: str) -> "CekuraMetricsConfig":
        data = json.loads(json_str)
        if isinstance(data, dict):
            inner = data.get("property")
            if isinstance(inner, dict) and (
                "api_key" in inner
                or "agent_id" in inner
                or "assistant_id" in inner
            ):
                data = inner
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def validate(self) -> None:
        if not self.api_key:
            raise ValueError("api_key is required for Cekura metrics")
        if not self.agent_id and not self.assistant_id:
            raise ValueError("Either agent_id or assistant_id must be provided")

    @property
    def observe_endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/observability/v1/observe/"

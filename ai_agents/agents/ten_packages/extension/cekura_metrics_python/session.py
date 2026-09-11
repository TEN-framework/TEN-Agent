from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import datetime
import json


@dataclass
class TranscriptMessage:
    role: str
    content: str
    start_time: float = 0.0
    end_time: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }


@dataclass
class ToolCallRecord:
    name: str
    arguments: str
    result: str
    success: bool
    latency_ms: float
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    
    def to_dict(self) -> dict:
        ts = self.timestamp
        return {
            "role": "function_call",
            "content": f"Tool: {self.name}",
            "start_time": ts,
            "end_time": ts,
            "data": {
                "name": self.name,
                "arguments": self.arguments,
                "result": self.result,
                "success": self.success,
                "latency_ms": self.latency_ms,
                "timestamp": ts,
            },
        }


@dataclass
class LatencyMetric:
    component: str
    latency_ms: float
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    metadata: dict = field(default_factory=dict)


@dataclass 
class Session:
    session_id: str
    channel_name: str = ""
    customer_number: str = ""
    metadata: dict = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
    ended_reason: str = ""
    
    transcripts: list[TranscriptMessage] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    latency_metrics: list[LatencyMetric] = field(default_factory=list)
    
    llm_latencies: list[float] = field(default_factory=list)
    tts_latencies: list[float] = field(default_factory=list)
    asr_latencies: list[float] = field(default_factory=list)
    
    def add_transcript(self, role: str, content: str, start_time: float = 0.0, end_time: float = 0.0) -> None:
        self.transcripts.append(TranscriptMessage(
            role=role,
            content=content,
            start_time=start_time,
            end_time=end_time,
        ))
    
    def add_tool_call(self, name: str, arguments: str, result: str, success: bool, latency_ms: float) -> None:
        self.tool_calls.append(ToolCallRecord(
            name=name,
            arguments=arguments,
            result=result,
            success=success,
            latency_ms=latency_ms,
        ))
    
    def add_latency_metric(self, component: str, latency_ms: float, **metadata) -> None:
        self.latency_metrics.append(LatencyMetric(
            component=component,
            latency_ms=latency_ms,
            metadata=metadata,
        ))
        if component == "llm":
            self.llm_latencies.append(latency_ms)
        elif component == "tts":
            self.tts_latencies.append(latency_ms)
        elif component == "asr":
            self.asr_latencies.append(latency_ms)
    
    def end(self, reason: str = "") -> None:
        self.ended_at = datetime.now()
        self.ended_reason = reason

    def has_observe_payload(self) -> bool:
        """True if there is data to POST (transcripts, tool calls, or latency samples)."""
        return bool(
            self.transcripts or self.tool_calls or self.latency_metrics
        )

    def build_transcript_json(self) -> list[dict]:
        messages = []
        for t in self.transcripts:
            messages.append(t.to_dict())
        for tc in self.tool_calls:
            messages.append(tc.to_dict())
        messages.sort(key=lambda x: float(x.get("start_time", 0) or 0))
        return messages
    
    def build_metadata(self) -> dict:
        meta = dict(self.metadata)
        meta["channel_name"] = self.channel_name
        
        if self.llm_latencies:
            meta["llm_avg_latency_ms"] = sum(self.llm_latencies) / len(self.llm_latencies)
            meta["llm_max_latency_ms"] = max(self.llm_latencies)
            meta["llm_min_latency_ms"] = min(self.llm_latencies)
        
        if self.tts_latencies:
            meta["tts_avg_latency_ms"] = sum(self.tts_latencies) / len(self.tts_latencies)
            meta["tts_max_latency_ms"] = max(self.tts_latencies)
            meta["tts_min_latency_ms"] = min(self.tts_latencies)
        
        if self.asr_latencies:
            meta["asr_avg_latency_ms"] = sum(self.asr_latencies) / len(self.asr_latencies)
            meta["asr_max_latency_ms"] = max(self.asr_latencies)
            meta["asr_min_latency_ms"] = min(self.asr_latencies)
        
        meta["total_tool_calls"] = len(self.tool_calls)
        meta["failed_tool_calls"] = sum(1 for tc in self.tool_calls if not tc.success)
        
        return meta
    
    def to_observe_payload(self, agent_id: int = 0, assistant_id: str = "", metric_ids: str = "") -> dict:
        payload = {
            "call_id": self.session_id,
            "transcript_type": "cekura",
            "transcript_json": self.build_transcript_json(),
            "timestamp": self.started_at.isoformat() + "Z",
            "metadata": self.build_metadata(),
        }
        
        if agent_id:
            payload["agent"] = agent_id
        if assistant_id:
            payload["assistant_id"] = assistant_id
        if self.customer_number:
            payload["customer_number"] = self.customer_number
        if self.ended_reason:
            payload["call_ended_reason"] = self.ended_reason
        if metric_ids:
            payload["metric_ids"] = metric_ids
        
        return payload

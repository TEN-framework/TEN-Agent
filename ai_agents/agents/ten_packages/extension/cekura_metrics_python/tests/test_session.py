import pytest
from datetime import datetime

from ..session import Session, TranscriptMessage, ToolCallRecord


class TestSession:
    def test_create_session(self):
        session = Session(
            session_id="test-123",
            channel_name="room-abc",
            customer_number="+1234567890",
        )
        
        assert session.session_id == "test-123"
        assert session.channel_name == "room-abc"
        assert session.customer_number == "+1234567890"
        assert session.ended_at is None
        assert len(session.transcripts) == 0
        assert len(session.tool_calls) == 0

    def test_add_transcript(self):
        session = Session(session_id="test-123")
        
        session.add_transcript(
            role="Main Agent",
            content="Hello, how can I help?",
            start_time=1.0,
            end_time=2.5,
        )
        
        assert len(session.transcripts) == 1
        assert session.transcripts[0].role == "Main Agent"
        assert session.transcripts[0].content == "Hello, how can I help?"

    def test_add_tool_call(self):
        session = Session(session_id="test-123")
        
        session.add_tool_call(
            name="get_weather",
            arguments='{"city": "NYC"}',
            result='{"temp": 72}',
            success=True,
            latency_ms=250.0,
        )
        
        assert len(session.tool_calls) == 1
        assert session.tool_calls[0].name == "get_weather"
        assert session.tool_calls[0].success is True

    def test_add_latency_metrics(self):
        session = Session(session_id="test-123")
        
        session.add_latency_metric("llm", 250.0, model="gpt-4o")
        session.add_latency_metric("llm", 300.0, model="gpt-4o")
        session.add_latency_metric("tts", 150.0, vendor="elevenlabs")
        session.add_latency_metric("asr", 200.0, vendor="deepgram")
        
        assert len(session.llm_latencies) == 2
        assert len(session.tts_latencies) == 1
        assert len(session.asr_latencies) == 1
        
        metadata = session.build_metadata()
        assert metadata["llm_avg_latency_ms"] == 275.0
        assert metadata["llm_max_latency_ms"] == 300.0
        assert metadata["llm_min_latency_ms"] == 250.0

    def test_end_session(self):
        session = Session(session_id="test-123")
        assert session.ended_at is None
        
        session.end("customer-hangup")
        
        assert session.ended_at is not None
        assert session.ended_reason == "customer-hangup"

    def test_has_observe_payload(self):
        empty = Session(session_id="empty")
        assert empty.has_observe_payload() is False

        t = Session(session_id="t")
        t.add_transcript("Main Agent", "Hi")
        assert t.has_observe_payload() is True

        tc = Session(session_id="tc")
        tc.add_tool_call("x", "", "", True, 0.0)
        assert tc.has_observe_payload() is True

        lat = Session(session_id="lat")
        lat.add_latency_metric("llm", 100.0)
        assert lat.has_observe_payload() is True

    def test_build_transcript_json(self):
        session = Session(session_id="test-123")
        
        session.add_transcript("Main Agent", "Hello!", start_time=1.0, end_time=2.0)
        session.add_transcript("Testing Agent", "Hi there", start_time=2.5, end_time=3.5)
        
        transcript_json = session.build_transcript_json()
        
        assert len(transcript_json) == 2
        assert transcript_json[0]["role"] == "Main Agent"
        assert transcript_json[1]["role"] == "Testing Agent"

    def test_to_observe_payload(self):
        session = Session(
            session_id="test-123",
            channel_name="room-abc",
            customer_number="+1234567890",
        )
        
        session.add_transcript("Main Agent", "Hello!", start_time=1.0, end_time=2.0)
        session.end("completed")
        
        payload = session.to_observe_payload(
            agent_id=123,
            metric_ids="1,2,3",
        )
        
        assert payload["call_id"] == "test-123"
        assert payload["agent"] == 123
        assert payload["customer_number"] == "+1234567890"
        assert payload["call_ended_reason"] == "completed"
        assert payload["metric_ids"] == "1,2,3"
        assert payload["transcript_type"] == "cekura"
        assert len(payload["transcript_json"]) == 1


class TestTranscriptMessage:
    def test_to_dict(self):
        msg = TranscriptMessage(
            role="Main Agent",
            content="Hello",
            start_time=1.0,
            end_time=2.0,
        )
        
        d = msg.to_dict()
        
        assert d["role"] == "Main Agent"
        assert d["content"] == "Hello"
        assert d["start_time"] == 1.0
        assert d["end_time"] == 2.0


class TestToolCallRecord:
    def test_to_dict(self):
        tc = ToolCallRecord(
            name="get_weather",
            arguments='{"city": "NYC"}',
            result='{"temp": 72}',
            success=True,
            latency_ms=250.0,
        )
        
        d = tc.to_dict()
        
        assert d["role"] == "function_call"
        assert "get_weather" in d["content"]
        assert "start_time" in d and d["start_time"] == tc.timestamp
        assert d["data"]["name"] == "get_weather"
        assert d["data"]["success"] is True
        assert d["data"]["timestamp"] == tc.timestamp

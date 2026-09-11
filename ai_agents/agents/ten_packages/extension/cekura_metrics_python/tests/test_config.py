import pytest

from ..config import CekuraMetricsConfig


class TestCekuraMetricsConfig:
    def test_from_json(self):
        json_str = '''
        {
            "api_key": "test-key",
            "agent_id": 123,
            "base_url": "https://api.cekura.ai",
            "auto_flush": true,
            "collect_latency": true
        }
        '''
        
        config = CekuraMetricsConfig.from_json(json_str)
        
        assert config.api_key == "test-key"
        assert config.agent_id == 123
        assert config.base_url == "https://api.cekura.ai"
        assert config.auto_flush is True
        assert config.collect_latency is True

    def test_validate_requires_api_key(self):
        config = CekuraMetricsConfig(
            api_key="",
            agent_id=123,
        )
        
        with pytest.raises(ValueError, match="api_key is required"):
            config.validate()

    def test_validate_requires_agent_or_assistant(self):
        config = CekuraMetricsConfig(
            api_key="test-key",
            agent_id=0,
            assistant_id="",
        )
        
        with pytest.raises(ValueError, match="agent_id or assistant_id"):
            config.validate()

    def test_validate_success_with_agent_id(self):
        config = CekuraMetricsConfig(
            api_key="test-key",
            agent_id=123,
        )
        
        config.validate()

    def test_validate_success_with_assistant_id(self):
        config = CekuraMetricsConfig(
            api_key="test-key",
            assistant_id="asst_abc123",
        )
        
        config.validate()

    def test_observe_endpoint(self):
        config = CekuraMetricsConfig(
            api_key="test-key",
            agent_id=123,
            base_url="https://api.cekura.ai",
        )
        
        assert config.observe_endpoint == "https://api.cekura.ai/observability/v1/observe/"
        
        config.base_url = "https://api.cekura.ai/"
        assert config.observe_endpoint == "https://api.cekura.ai/observability/v1/observe/"

    def test_default_values(self):
        config = CekuraMetricsConfig()
        
        assert config.base_url == "https://api.cekura.ai"
        assert config.auto_flush is True
        assert config.auto_flush_interval_ms == 5000
        assert config.collect_latency is True
        assert config.collect_transcripts is True
        assert config.collect_tool_calls is True

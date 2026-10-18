"""Static checks for the optional Jev voice-assistant graph."""

import hashlib
import json
from pathlib import Path


TENAPP = Path(__file__).resolve().parents[1] / "tenapp"


def test_jev_graph_is_optional_and_has_required_nodes():
    app = json.loads((TENAPP / "property.json").read_text())
    graphs = {graph["name"]: graph for graph in app["ten"]["predefined_graphs"]}
    assert graphs["voice_assistant"]["auto_start"] is True
    assert graphs["voice_assistant_jev_router"]["auto_start"] is False
    default_llm = next(
        node
        for node in graphs["voice_assistant"]["graph"]["nodes"]
        if node["name"] == "llm"
    )
    assert default_llm["property"]["model"] == "${env:OPENAI_MODEL}"
    assert default_llm["property"]["base_url"] == "https://api.openai.com/v1"
    assert default_llm["property"]["api_key"] == "${env:OPENAI_API_KEY}"

    nodes = {
        node["name"]: node
        for node in graphs["voice_assistant_jev_router"]["graph"]["nodes"]
    }
    assert nodes["jev"]["addon"] == "typesafe_jev_python"
    assert nodes["llm_fast"]["addon"] == "deepseek_llm2_python"
    assert nodes["llm_deep"]["addon"] == "deepseek_llm2_python"
    assert nodes["main_control"]["addon"] == "main_jev_python"
    assert nodes["stt"]["property"]["params"]["language"] == "en-US"
    assert nodes["stt"]["property"]["params"]["endpointing"] == 500
    assert nodes["jev"]["property"]["params"]["api_key"] == (
        "${env:TYPESAFE_API_KEY}"
    )
    assert nodes["jev"]["property"]["params"]["timeout_ms"] == 2000
    for node_name in ("llm_fast", "llm_deep"):
        properties = nodes[node_name]["property"]
        assert properties["base_url"] == "https://api.deepseek.com"
        assert properties["api_key"] == "${env:DEEPSEEK_API_KEY}"
        assert properties["proxy_url"] == "${env:DEEPSEEK_PROXY_URL|}"
    assert nodes["llm_fast"]["property"]["model"] == "deepseek-flash"
    assert nodes["llm_deep"]["property"]["model"] == "deepseek-flash"
    assert nodes["llm_deep"]["property"]["max_tokens"] > 512
    deep_prompt = nodes["llm_deep"]["property"]["prompt"]
    assert "it is delivered separately" in deep_prompt
    assert "Never reveal internal reasoning" not in deep_prompt
    assert "weatherapi_tool_python" not in nodes
    routing = nodes["main_control"]["property"]["model_routing"]
    assert (
        nodes["main_control"]["property"]["turn_detection_mode"]
        == "speech_final"
    )
    assert nodes["main_control"]["property"]["asr_final_fallback_ms"] == 1000
    assert routing["enabled"] is True
    assert routing["decision_dest"] == "jev"
    assert routing["fast_dest"] == "llm_fast"
    assert routing["deep_dest"] == "llm_deep"
    assert routing["timeout_ms"] == 2300
    main_cmds = next(
        connection["cmd"]
        for connection in graphs["voice_assistant_jev_router"]["graph"][
            "connections"
        ]
        if connection["extension"] == "main_control"
    )
    assert all("tool_register" not in cmd["names"] for cmd in main_cmds)


def test_jev_dependency_is_declared():
    app = json.loads((TENAPP / "manifest.json").read_text())
    assert {
        "path": "../../../ten_packages/extension/typesafe_jev_python"
    } in app["dependencies"]
    assert {
        "path": "../../../ten_packages/extension/deepseek_llm2_python"
    } in app["dependencies"]


def test_other_graphs_match_pre_jev_commit():
    current = json.loads((TENAPP / "property.json").read_text())
    current_graphs = [
        graph
        for graph in current["ten"]["predefined_graphs"]
        if graph["name"] != "voice_assistant_jev_router"
    ]
    # Canonical SHA-256 of predefined_graphs at 70e4d8da7^.
    encoded = json.dumps(
        current_graphs, sort_keys=True, separators=(",", ":")
    ).encode()
    assert hashlib.sha256(encoded).hexdigest() == (
        "312a4f54b9f68f4bbb94c09df9e9bca3be585a712cb106083e95dc8aec837650"
    )

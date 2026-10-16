# 03 Code Map

> Directory tree, module responsibilities, and key file locations.

## Top-Level Structure

All AI agent development happens inside `ai_agents/`:

```
ai_agents/
├── agents/
│   ├── ten_packages/
│   │   ├── extension/           # 90+ extensions (ASR, TTS, LLM, tools, avatar)
│   │   └── system/              # Core runtime packages
│   │       ├── ten_ai_base/     # Base classes and API interface definitions
│   │       ├── ten_runtime_python/
│   │       └── ten_runtime_go/
│   ├── examples/                # 24+ example agent configurations
│   │   ├── voice-assistant/
│   │   ├── voice-assistant-advanced/
│   │   ├── voice-assistant-realtime/
│   │   ├── voice-assistant-video/
│   │   ├── doodler/
│   │   └── ...
│   ├── integration_tests/       # Test frameworks
│   │   ├── asr_guarder/         # ASR integration tests
│   │   └── tts_guarder/         # TTS integration tests
│   └── scripts/                 # Build and packaging scripts
├── server/                      # Go API server
│   ├── main.go
│   └── internal/
│       ├── http_server.go       # REST endpoints, property injection
│       └── config.go            # Parameter mapping (startPropMap)
├── playground/                  # Next.js frontend UI (port 3000)
│   └── src/                     # React components
├── esp32-client/                # ESP32 hardware client
├── Taskfile.yml                 # Root-level build/test tasks
├── docker-compose.yml           # Container config
├── .env                         # Environment variables (single source)
└── .env.example                 # Template with all variables
```

Other repo-root directories: `core/` (C runtime), `packages/` (example/core extensions),
`docs/` (framework docs), `tools/` (Grafana monitoring, profilers).

## Extension Categories

| Category  | Count | Examples                                                    |
| --------- | ----- | ----------------------------------------------------------- |
| ASR       | 10+   | `deepgram_asr_python`, `azure_asr_python`, `aws_asr_python`, `speko_asr_python` |
| TTS       | 15+   | `deepgram_tts`, `elevenlabs_tts2_python`, `cartesia_tts`, `speko_tts2_python`    |
| LLM       | 9+    | `openai_llm2_python`, `anthropic_llm2_python`, `gemini_llm2_python`, `bedrock_llm_python`, `speko_llm2_python` |
| Avatar    | 5+    | `heygen_avatar_python`, `anam_avatar_python`                |
| Tools     | 8+    | `bingsearch_tool_python`, `vision_tool_python`              |
| Transport | 3+    | `agora_rtc`, `websocket_server`, `http_server_python`       |
| Other     | 10+   | `message_collector2`, `ten_vad_python`, `mcp_client_python` |

## Extension File Structure

Every extension follows this layout:

| File               | Purpose                                        |
| ------------------ | ---------------------------------------------- |
| `__init__.py`      | Package marker                                 |
| `addon.py`         | `@register_addon_as_extension` registration    |
| `extension.py`     | Main logic, inherits from base class           |
| `config.py`        | Pydantic config model (optional but common)    |
| `manifest.json`    | Metadata, dependencies, API interface imports  |
| `property.json`    | Default config values with `${env:VAR}` syntax |
| `requirements.txt` | Python dependencies                            |
| `README.md`        | Usage documentation (often multilingual)       |
| `tests/`           | Standalone tests with `bin/start` entry point  |

## Base Classes

Located in example tenapp directories under `ten_packages/system/ten_ai_base/interface/ten_ai_base/`:

| File       | Class                        | Purpose                    |
| ---------- | ---------------------------- | -------------------------- |
| `asr.py`   | `AsyncASRBaseExtension`      | Speech recognition         |
| `tts.py`   | `AsyncTTSBaseExtension`      | Text-to-speech (basic)     |
| `tts2.py`  | `AsyncTTS2BaseExtension`     | Text-to-speech (advanced)  |
| `llm.py`   | `AsyncLLMBaseExtension`      | Language model completion   |
| `llm2.py`  | `AsyncLLM2BaseExtension`     | Language model v2           |
| `llm_tool.py` | `AsyncLLMToolBaseExtension` | LLM function calling tools |
| `mllm.py`  | `AsyncMLLMBaseExtension`     | Multimodal LLM             |

## API Interface Definitions

Standard interfaces in `ten_ai_base/api/`:

| File                    | Defines                           |
| ----------------------- | --------------------------------- |
| `asr-interface.json`    | ASR data/cmd/audio_frame schemas  |
| `tts-interface.json`    | TTS data/cmd/audio_frame schemas  |
| `llm-interface.json`    | LLM data/cmd schemas              |
| `mllm-interface.json`   | Multimodal LLM schemas            |

Extensions reference these via `manifest.json`:
```json
{"api": {"interface": [{"import_uri": "../../system/ten_ai_base/api/tts-interface.json"}]}}
```

## Key Files Quick Reference

| When working on...         | Look at                                            |
| -------------------------- | -------------------------------------------------- |
| New extension              | Similar extension in `agents/ten_packages/extension/` |
| API interface changes      | `ten_ai_base/api/*.json`                           |
| Graph configuration        | `agents/examples/*/tenapp/property.json`           |
| Server endpoints           | `server/internal/http_server.go`                   |
| Build/test tasks           | `Taskfile.yml` (root) and per-example              |
| Test setup                 | `agents/ten_packages/extension/*/tests/bin/start`  |

## Related Deep Dives

- [Extension Development](L2/extension_development.md) — Full creation guide with base class details

# Voice Assistant Companion

A personalized AI companion with real-time voice interaction, emotional intelligence, and contextual memory for natural, engaging conversations.

## Features

- **Personalized Conversations**: Remembers your preferences and conversation history
- **Emotional Intelligence**: Responds with empathy and contextual awareness
- **Ultra-Low Latency Voice Interaction**: Direct speech-to-speech conversation with minimal delay
- **Multi-Provider Support**: Compatible with OpenAI GPT Realtime, Azure Voice AI, Gemini 2.0 Flash, GLM, StepFun, and other voice-to-voice models
- **Contextual Memory**: Maintains conversation context for natural dialogue flow

## Prerequisites

### Required Environment Variables

1. **Agora Account**: Get credentials from [Agora Console](https://console.agora.io/)
   - `AGORA_APP_ID` - Your Agora App ID (required)

2. **Voice-to-Voice Model Provider** (choose one):
   - **OpenAI**: `OPENAI_API_KEY` - For GPT Realtime
   - **Azure**: `AZURE_AI_FOUNDRY_API_KEY` and `AZURE_AI_FOUNDRY_BASE_URI` - For Azure Voice AI
   - **Gemini**: `GEMINI_API_KEY` - For Gemini 2.0 Flash
   - **GLM**: `GLM_API_KEY` - For GLM voice models
   - **StepFun**: `STEPFUN_API_KEY` - For StepFun voice models

### Optional Environment Variables

- `AGORA_APP_CERTIFICATE` - Agora App Certificate (optional)
- `WEATHERAPI_API_KEY` - Weather API key for weather tool (optional)

## Setup

### 1. Set Environment Variables

Add to your `.env` file:

```bash
# Agora (required for audio streaming)
AGORA_APP_ID=your_agora_app_id_here
AGORA_APP_CERTIFICATE=your_agora_certificate_here

# Voice-to-Voice Model Provider (choose one)
OPENAI_API_KEY=your_openai_api_key_here
# OR
AZURE_AI_FOUNDRY_API_KEY=your_azure_api_key_here
AZURE_AI_FOUNDRY_BASE_URI=your_azure_base_uri_here
# OR
GEMINI_API_KEY=your_gemini_api_key_here
# OR
GLM_API_KEY=your_glm_api_key_here
# OR
STEPFUN_API_KEY=your_stepfun_api_key_here

# Optional
WEATHERAPI_API_KEY=your_weather_api_key_here
```

### 2. Install Dependencies

```bash
cd agents/examples/voice-assistant-companion
task install
```

This installs Python dependencies and frontend components.

### 3. Run the Voice Assistant Companion

```bash
cd agents/examples/voice-assistant-companion
task run
```

The voice assistant companion starts with all capabilities enabled.

### 4. Access the Application

- **Frontend**: http://localhost:3000
- **API Server**: http://localhost:8080
- **TMAN Designer**: http://localhost:49483

## Configuration

The voice assistant companion is configured in `tenapp/property.json`:

```json
{
  "ten": {
    "predefined_graphs": [
      {
        "name": "voice_assistant_companion",
        "auto_start": true,
        "graph": {
          "nodes": [
            {
              "name": "agora_rtc",
              "addon": "agora_rtc",
              "property": {
                "app_id": "${env:AGORA_APP_ID}",
                "app_certificate": "${env:AGORA_APP_CERTIFICATE|}",
                "channel": "companion_channel",
                "subscribe_audio": true,
                "publish_audio": true,
                "publish_data": true
              }
            },
            {
              "name": "v2v",
              "addon": "openai_mllm_python",
              "property": {
                "api_key": "${env:OPENAI_API_KEY}",
                "model": "gpt-realtime-2.1",
                "voice": "shimmer",
                "language": "en",
                "vad_type": "semantic_vad",
                "vad_eagerness": "auto"
              }
            }
          ]
        }
      }
    ]
  }
}
```

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `AGORA_APP_ID` | string | - | Your Agora App ID (required) |
| `AGORA_APP_CERTIFICATE` | string | - | Your Agora App Certificate (optional) |
| `OPENAI_API_KEY` | string | - | OpenAI API key (required for GPT Realtime) |
| `AZURE_AI_FOUNDRY_API_KEY` | string | - | Azure AI Foundry API key (required for Azure Voice AI) |
| `AZURE_AI_FOUNDRY_BASE_URI` | string | - | Azure AI Foundry base URI (required for Azure Voice AI) |
| `GEMINI_API_KEY` | string | - | Gemini API key (required for Gemini 2.0 Flash) |
| `GLM_API_KEY` | string | - | GLM API key (required for GLM voice models) |
| `STEPFUN_API_KEY` | string | - | StepFun API key (required for StepFun voice models) |
| `WEATHERAPI_API_KEY` | string | - | Weather API key (optional) |

## Customization

The voice assistant companion uses a modular design that allows you to easily replace components using TMAN Designer.

Access the visual designer at http://localhost:49483 to customize your AI companion. For detailed usage instructions, see the [TMAN Designer documentation](https://theten.ai/docs/ten_agent/customize_agent/tman-designer).

## Release as Docker image

**Note**: The following commands need to be executed outside of any Docker container.

### Build image

```bash
cd ai_agents
docker build -f agents/examples/voice-assistant-companion/Dockerfile -t voice-assistant-companion-app .
```

### Run

```bash
docker run --rm -it --env-file .env -p 8080:8080 -p 3000:3000 voice-assistant-companion-app
```

### Access

- Frontend: http://localhost:3000
- API Server: http://localhost:8080

## Learn More

- [OpenAI GPT Realtime Documentation](https://platform.openai.com/docs/guides/realtime)
- [Azure Speech Services Documentation](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/)
- [Gemini AI Documentation](https://ai.google.dev/gemini)
- [GLM Documentation](https://glm.ai/docs)
- [StepFun Documentation](https://stepfun.com/docs)
- [Agora RTC Documentation](https://docs.agora.io/en/rtc/overview/product-overview)
- [TEN Framework Documentation](https://doc.theten.ai)

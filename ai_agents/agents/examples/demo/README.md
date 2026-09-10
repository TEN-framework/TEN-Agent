# Agent Demo

Comprehensive demo showcasing TEN Framework's AI agent capabilities with multiple LLM providers and real-time voice interaction.

**🌐 Live Demo**: [https://agent.theten.ai](https://agent.theten.ai)

## Features

- **Multiple AI Agent Types**: Support for different AI agent configurations
  - **Voice AI (STT + LLM + TTS)**: OpenAI GPT 5, Llama 4, Qwen 3 Reasoning, OrcaRouter
  - **Speech to Speech Voice AI**: OpenAI GPT Realtime, OpenAI GPT Realtime 1.5, Gemini 2.0/2.5 Flash, Azure Voice AI API
  - **AI Platform Integrations**: OceanBase PowerRAG, Dify Agent, Coze Bot
- **Multi-language Support**: English, Chinese, Korean, Japanese
- **Real-time Voice Interaction**: Natural speech conversation with AI agents
- **Agora RTC Integration**: High-quality real-time audio streaming
- **Video Support**: Camera and screen sharing capabilities
- **Voice Customization**: Male and female voice options
- **UI Customization**: Multiple color themes and visual options
- **Chat Interface**: Text-based conversation alongside voice interaction
- **Settings Management**: Configurable agent settings, prompts, and greetings

## Prerequisites

### Required Environment Variables

1. **Agora Account**: Get credentials from [Agora Console](https://console.agora.io/)
   - `AGORA_APP_ID` - Your Agora App ID (required for all configurations)

2. **Azure Speech Services**: For speech-to-text and text-to-speech
   - `AZURE_STT_KEY` - Azure Speech-to-Text API key
   - `AZURE_STT_REGION` - Azure Speech-to-Text region
   - `AZURE_TTS_API_KEY` - Azure Text-to-Speech API key
   - `AZURE_TTS_REGION` - Azure Text-to-Speech region

3. **LLM Provider API Keys** (choose based on which agents you want to use):
   - `GROK_API_KEY` - For Grok 4 agent
   - `GROQ_CLOUD_API_KEY` - For Llama 4 agent
   - `QWEN_API_KEY` - For Qwen 3 agent
   - `DEEPSEEK_API_KEY` - For DeepSeek V3.1 agent
   - `ORCAROUTER_API_KEY` - For OrcaRouter agent
   - `GEMINI_API_KEY` - For Gemini 2.0/2.5 agents
   - `AZURE_AI_FOUNDRY_API_KEY` - For Azure Voice AI agent
   - `AZURE_AI_FOUNDRY_BASE_URI` - For Azure Voice AI agent
   - `OPENAI_API_KEY` - For OpenAI GPT agents
   - `COZE_TOKEN` - For Coze Bot agent
   - `COZE_BOT_ID` - For Coze Bot agent
   - `DIFY_API_KEY` - For Dify Agent
   - `OCEANBASE_API_KEY` - For OceanBase PowerRAG agent
   - `OCEANBASE_BASE_URL` - For OceanBase PowerRAG agent
   - `OCEANBASE_AI_DATABASE_NAME` - For OceanBase PowerRAG agent
   - `OCEANBASE_COLLECTION_ID` - For OceanBase PowerRAG agent

### Optional Environment Variables

- `AGORA_APP_CERTIFICATE` - Agora App Certificate (optional)
- `GROK_PROXY_URL` - Proxy URL for Grok API (optional)
- `OPENAI_PROXY_URL` - Proxy URL for OpenAI API (optional)
- `OPENAI_MODEL` - OpenAI model name (optional, defaults to configured model)
- `WEATHERAPI_API_KEY` - Weather API key for weather tool (optional)

## Setup

### 1. Set Environment Variables

Add to your `.env` file:

```bash
# Agora (required for audio streaming)
AGORA_APP_ID=your_agora_app_id_here
AGORA_APP_CERTIFICATE=your_agora_certificate_here

# Azure Speech Services (required for STT and TTS)
AZURE_STT_KEY=your_azure_stt_key_here
AZURE_STT_REGION=your_azure_stt_region_here
AZURE_TTS_API_KEY=your_azure_tts_key_here
AZURE_TTS_REGION=your_azure_tts_region_here

# LLM Provider (choose one or more)
GROK_API_KEY=your_grok_api_key_here
GROQ_CLOUD_API_KEY=your_groq_api_key_here
QWEN_API_KEY=your_qwen_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
ORCAROUTER_API_KEY=your_orcarouter_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# AI Platform Integrations (optional)
COZE_TOKEN=your_coze_token_here
COZE_BOT_ID=your_coze_bot_id_here
DIFY_API_KEY=your_dify_api_key_here
OCEANBASE_API_KEY=your_oceanbase_api_key_here
OCEANBASE_BASE_URL=your_oceanbase_base_url_here
OCEANBASE_AI_DATABASE_NAME=your_oceanbase_database_name_here
OCEANBASE_COLLECTION_ID=your_oceanbase_collection_id_here
AZURE_AI_FOUNDRY_API_KEY=your_azure_ai_foundry_api_key_here
AZURE_AI_FOUNDRY_BASE_URI=your_azure_ai_foundry_base_uri_here

# Optional
WEATHERAPI_API_KEY=your_weather_api_key_here
```

### 2. Install Dependencies

```bash
cd agents/examples/demo
task install
```

This installs Python dependencies and frontend components.

### 3. Run the Demo

```bash
cd agents/examples/demo
task run
```

The demo starts with all capabilities enabled.

### 4. Access the Application

- **Frontend**: http://localhost:3000
- **API Server**: http://localhost:8080
- **TMAN Designer**: http://localhost:49483

## Configuration

The demo is configured in `property.json`:

```json
{
  "ten": {
    "predefined_graphs": [
      {
        "name": "grok4",
        "auto_start": true,
        "graph": {
          "nodes": [
            {
              "name": "agora_rtc",
              "addon": "agora_rtc",
              "property": {
                "app_id": "${env:AGORA_APP_ID}",
                "channel": "ten_agent_test",
                "subscribe_audio": true,
                "publish_audio": true,
                "publish_data": true
              }
            },
            {
              "name": "stt",
              "addon": "azure_asr_python",
              "property": {
                "params": {
                  "key": "${env:AZURE_STT_KEY}",
                  "region": "${env:AZURE_STT_REGION}"
                }
              }
            },
            {
              "name": "llm",
              "addon": "openai_llm2_python",
              "property": {
                "api_key": "${env:GROK_API_KEY}",
                "base_url": "https://api.x.ai/v1/",
                "model": "grok-4-0709"
              }
            },
            {
              "name": "tts",
              "addon": "azure_tts_python",
              "property": {
                "params": {
                  "subscription": "${env:AZURE_TTS_API_KEY}",
                  "region": "${env:AZURE_TTS_REGION}",
                  "output_format": "Raw16Khz16BitMonoPcm"
                }
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
| `AZURE_STT_KEY` | string | - | Azure Speech-to-Text API key (required) |
| `AZURE_STT_REGION` | string | - | Azure Speech-to-Text region (required) |
| `AZURE_TTS_API_KEY` | string | - | Azure Text-to-Speech API key (required) |
| `AZURE_TTS_REGION` | string | - | Azure Text-to-Speech region (required) |
| `GROK_API_KEY` | string | - | Grok API key (required for Grok agent) |
| `GROQ_CLOUD_API_KEY` | string | - | Groq API key (required for Llama agent) |
| `QWEN_API_KEY` | string | - | Qwen API key (required for Qwen agent) |
| `DEEPSEEK_API_KEY` | string | - | DeepSeek API key (required for DeepSeek agent) |
| `ORCAROUTER_API_KEY` | string | - | OrcaRouter API key (required for OrcaRouter agent) |
| `GEMINI_API_KEY` | string | - | Gemini API key (required for Gemini agents) |
| `OPENAI_API_KEY` | string | - | OpenAI API key (required for OpenAI agents) |
| `COZE_TOKEN` | string | - | Coze token (required for Coze agent) |
| `COZE_BOT_ID` | string | - | Coze bot ID (required for Coze agent) |
| `DIFY_API_KEY` | string | - | Dify API key (required for Dify agent) |
| `OCEANBASE_API_KEY` | string | - | OceanBase API key (required for OceanBase agent) |
| `OCEANBASE_BASE_URL` | string | - | OceanBase base URL (required for OceanBase agent) |
| `OCEANBASE_AI_DATABASE_NAME` | string | - | OceanBase database name (required for OceanBase agent) |
| `OCEANBASE_COLLECTION_ID` | string | - | OceanBase collection ID (required for OceanBase agent) |
| `AZURE_AI_FOUNDRY_API_KEY` | string | - | Azure AI Foundry API key (required for Azure agent) |
| `AZURE_AI_FOUNDRY_BASE_URI` | string | - | Azure AI Foundry base URI (required for Azure agent) |
| `WEATHERAPI_API_KEY` | string | - | Weather API key (optional) |


## Release as Docker image

**Note**: The following commands need to be executed outside of any Docker container.

### Build image

```bash
cd ai_agents
docker build -f agents/examples/demo/Dockerfile -t demo-app .
```

### Run

```bash
docker run --rm -it --env-file .env -p 8080:8080 -p 3000:3000 demo-app
```

### Access

- Frontend: http://localhost:3000
- API Server: http://localhost:8080

## Learn More

- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Azure Speech Services](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/)
- [Agora RTC Documentation](https://docs.agora.io/en/rtc/overview/product-overview)
- [TEN Framework Documentation](https://doc.theten.ai)

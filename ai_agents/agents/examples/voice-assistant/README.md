# Voice Assistant

A configurable voice assistant with real-time conversation capabilities using Agora RTC, interchangeable STT/TTS providers, and an OpenAI-compatible LLM.

## Features

- **Chained Model Real-time Voice Interaction**: Complete voice conversation pipeline with STT → LLM → TTS processing

## Prerequisites

### Required Environment Variables

1. **Agora Account**: Get credentials from [Agora Console](https://console.agora.io/)
   - `AGORA_APP_ID` - Your Agora App ID (required)

2. **STT Provider**: choose the graph you want to run
   - `DEEPGRAM_API_KEY` for the default `voice_assistant` graph
   - `XAI_API_KEY` for `voice_assistant_xai_asr` or `voice_assistant_xai_full`

3. **OpenAI Account**: Get credentials from [OpenAI Platform](https://platform.openai.com/)
   - `OPENAI_API_KEY` - Your OpenAI API key (required)

4. **TTS Provider**: choose the graph you want to run
   - `ELEVENLABS_TTS_KEY` for the default `voice_assistant` graph or `voice_assistant_xai_asr`
   - `GRADIUM_API_KEY` for `voice_assistant_gradium`
   - `XAI_API_KEY` for `voice_assistant_xai_tts` or `voice_assistant_xai_full`

### Provider-specific keys

- **Deepgram Account**: Get credentials from [Deepgram Console](https://console.deepgram.com/)
   - `DEEPGRAM_API_KEY` - Your Deepgram API key (required)
- **ElevenLabs Account**: Get credentials from [ElevenLabs](https://elevenlabs.io/)
   - `ELEVENLABS_TTS_KEY` - Your ElevenLabs API key (required)
- **Gradium Account**: Get credentials from [Gradium](https://gradium.ai/)
   - `GRADIUM_API_KEY` - Your Gradium API key (required for the Gradium TTS graph)
- **xAI Account**: Get credentials from [xAI Console](https://console.x.ai/)
   - `XAI_API_KEY` - Your xAI Voice API key (required for xAI STT/TTS graphs)

### Optional Environment Variables

- `AGORA_APP_CERTIFICATE` - Agora App Certificate (optional)
- `OPENAI_MODEL` - OpenAI model name (optional, defaults to configured model)
- `OPENAI_PROXY_URL` - Proxy URL for OpenAI API (optional)
- `WEATHERAPI_API_KEY` - Weather API key for weather tool (optional)

### Optional: Cekura observability

The default `voice_assistant` graph includes the **`cekura_metrics`** extension. If `CEKURA_API_KEY` is not set, it stays disabled and the demo runs unchanged.

When enabled, set:

- `CEKURA_API_KEY` — required to POST observability payloads.
- **`CEKURA_ASSISTANT_ID`** *or* set numeric `agent_id` in `tenapp/property.json` on the `cekura_metrics` node (the example uses `assistant_id`: `${env:CEKURA_ASSISTANT_ID|}` with `agent_id` 0).
- `CEKURA_METRIC_IDS` — optional comma-separated Cekura metric ids.

See `ten_packages/extension/cekura_metrics_python/README.md` for graph details and notes on what is and isn't captured when `main_python` is left unmodified.

## Setup

### 1. Set Environment Variables

Add to your `.env` file:

```bash
# Agora (required for audio streaming)
AGORA_APP_ID=your_agora_app_id_here
AGORA_APP_CERTIFICATE=your_agora_certificate_here

# Deepgram (required for speech-to-text)
DEEPGRAM_API_KEY=your_deepgram_api_key_here

# OpenAI (required for language model)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4
OPENAI_PROXY_URL=your_proxy_url_here

# ElevenLabs (required for text-to-speech)
ELEVENLABS_TTS_KEY=your_elevenlabs_api_key_here

# Gradium (required for the Gradium TTS graph)
GRADIUM_API_KEY=your_gradium_api_key_here

# xAI (required for xAI speech-to-text and/or text-to-speech graphs)
XAI_API_KEY=your_xai_api_key_here

# Optional
WEATHERAPI_API_KEY=your_weather_api_key_here
```

### 2. Install Dependencies

```bash
cd agents/examples/voice-assistant
task install
```

This installs Python dependencies and frontend components.

### 3. Run the Voice Assistant

```bash
cd agents/examples/voice-assistant
task run
```

The stack starts the TEN app, API server, frontend, and TMAN Designer.

### 4. Access the Application

- **Frontend**: http://localhost:3000
- **API Server**: http://localhost:8080
- **TMAN Designer**: http://localhost:49483

### 5. Choose a Graph

The frontend reads the `graph` URL query parameter and matches it against
`tenapp/property.json` `predefined_graphs[].name`.

Available graph names:

- `voice_assistant` - Deepgram STT + OpenAI-compatible LLM + ElevenLabs TTS
- `voice_assistant_gradium` - Deepgram STT + OpenAI-compatible LLM + Gradium TTS
- `voice_assistant_xai_asr` - xAI STT + OpenAI-compatible LLM + ElevenLabs TTS
- `voice_assistant_xai_tts` - Deepgram STT + OpenAI-compatible LLM + xAI TTS
- `voice_assistant_xai_full` - xAI STT + OpenAI-compatible LLM + xAI TTS

Examples:

```text
http://localhost:3000/?graph=voice_assistant_xai_full
https://ten-demo.agora.io/?graph=voice_assistant_xai_full
```

## Configuration

The voice assistant is configured in `tenapp/property.json`:

```json
{
  "ten": {
    "predefined_graphs": [
      {
        "name": "voice_assistant",
        "auto_start": true,
        "graph": {
          "nodes": [
            {
              "name": "agora_rtc",
              "addon": "agora_rtc",
              "property": {
                "app_id": "${env:AGORA_APP_ID}",
                "app_certificate": "${env:AGORA_APP_CERTIFICATE|}",
                "channel": "ten_agent_test",
                "subscribe_audio": true,
                "publish_audio": true,
                "publish_data": true
              }
            },
            {
              "name": "stt",
              "addon": "deepgram_asr_python",
              "property": {
                "params": {
                  "api_key": "${env:DEEPGRAM_API_KEY}",
                  "language": "en-US"
                }
              }
            },
            {
              "name": "llm",
              "addon": "openai_llm2_python",
              "property": {
                "api_key": "${env:OPENAI_API_KEY}",
                "model": "${env:OPENAI_MODEL}",
                "max_tokens": 512,
                "greeting": "TEN Agent connected. How can I help you today?"
              }
            },
            {
              "name": "tts",
              "addon": "elevenlabs_tts2_python",
              "property": {
                "params": {
                  "key": "${env:ELEVENLABS_TTS_KEY}",
                  "model_id": "eleven_multilingual_v2",
                  "voice_id": "pNInz6obpgDQGcFmaJgB",
                  "output_format": "pcm_16000"
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
| `DEEPGRAM_API_KEY` | string | - | Deepgram API key (required) |
| `OPENAI_API_KEY` | string | - | OpenAI API key (required) |
| `GRADIUM_API_KEY` | string | - | Gradium API key (required for `voice_assistant_gradium`) |
| `OPENAI_MODEL` | string | - | OpenAI model name (optional) |
| `OPENAI_PROXY_URL` | string | - | Proxy URL for OpenAI API (optional) |
| `ELEVENLABS_TTS_KEY` | string | - | ElevenLabs API key (required) |
| `WEATHERAPI_API_KEY` | string | - | Weather API key (optional) |

## Customization

The voice assistant uses a modular design that allows you to easily replace STT, LLM, or TTS modules with other providers using TMAN Designer.

Access the visual designer at http://localhost:49483 to customize your voice agent. For detailed usage instructions, see the [TMAN Designer documentation](https://theten.ai/docs/ten_agent/customize_agent/tman-designer).

## Release as Docker image

**Note**: The following commands need to be executed outside of any Docker container.

### Build image

```bash
cd ai_agents
docker build -f agents/examples/voice-assistant/Dockerfile -t voice-assistant-app .
```

### Run

```bash
docker run --rm -it --env-file .env -p 8080:8080 -p 3000:3000 voice-assistant-app
```

### Access

- Frontend: http://localhost:3000
- API Server: http://localhost:8080

## Learn More

- [Agora RTC Documentation](https://docs.agora.io/en/rtc/overview/product-overview)
- [Deepgram API Documentation](https://developers.deepgram.com/)
- [xAI API Documentation](https://docs.x.ai/)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [ElevenLabs API Documentation](https://docs.elevenlabs.io/)
- [TEN Framework Documentation](https://doc.theten.ai)

# Voice Assistant (SIP/Telnyx)

A voice assistant that supports both inbound and outbound calls using Telnyx SIP integration with real-time voice conversation capabilities.

## Features

- **Inbound Call Handling**: Automatically handles incoming calls with real-time speech recognition
- **Outbound Call Management**: RESTful API to start, monitor, and stop outbound calls
- **Real-time Voice Interaction**: Complete voice conversation pipeline with STT → LLM → TTS processing

## Prerequisites

### Required Environment Variables

1. **Telnyx Account**: Get credentials from [Telnyx Mission Control](https://portal.telnyx.com/)
   - `TELNYX_API_KEY` - Your Telnyx API key (required)
   - `TELNYX_CONNECTION_ID` - Your Telnyx Connection ID for SIP trunking (required)
   - `TELNYX_FROM_NUMBER` - Your Telnyx phone number (required)
   - `TELNYX_PUBLIC_SERVER_URL` - Your public server URL for webhooks and WebSocket connections (required) - Telnyx uses this URL to send webhook requests and establish WebSocket connections for audio streaming. For local testing, you can use ngrok to get a public domain for your local port

2. **Deepgram Account**: Get credentials from [Deepgram Console](https://console.deepgram.com/)
   - `DEEPGRAM_API_KEY` - Your Deepgram API key (required)

3. **OpenAI Account**: Get credentials from [OpenAI Platform](https://platform.openai.com/)
   - `OPENAI_API_KEY` - Your OpenAI API key (required)

4. **ElevenLabs Account**: Get credentials from [ElevenLabs](https://elevenlabs.io/)
   - `ELEVENLABS_TTS_KEY` - Your ElevenLabs API key (required)

### Optional Environment Variables

- `OPENAI_MODEL` - OpenAI model name (optional, defaults to configured model)
- `OPENAI_PROXY_URL` - Proxy URL for OpenAI API (optional)
- `WEATHERAPI_API_KEY` - Weather API key for weather tool (optional)
- `NGROK_AUTHTOKEN` - Ngrok auth token for local development (optional)

## Setup

### 1. Set Environment Variables

Add to your `.env` file:

```bash
# Telnyx (required for call handling)
TELNYX_API_KEY=your_telnyx_api_key_here
TELNYX_CONNECTION_ID=your_telnyx_connection_id_here
TELNYX_FROM_NUMBER=+1234567890
TELNYX_PUBLIC_SERVER_URL=https://your-domain.com

# Deepgram (required for speech-to-text)
DEEPGRAM_API_KEY=your_deepgram_api_key_here

# OpenAI (required for language model)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4
OPENAI_PROXY_URL=your_proxy_url_here

# ElevenLabs (required for text-to-speech)
ELEVENLABS_TTS_KEY=your_elevenlabs_api_key_here

# Optional
WEATHERAPI_API_KEY=your_weather_api_key_here
NGROK_AUTHTOKEN=your_ngrok_auth_token_here
```

### 2. Install Dependencies

```bash
cd agents/examples/voice-assistant-sip-telnyx
task install
```

This installs Python dependencies and frontend components.

### 3. Install Ngrok (for local development)

For local development, you will need ngrok to expose your local server publicly:

```bash
# Install ngrok using the official repository
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | gpg --dearmor > /etc/apt/trusted.gpg.d/ngrok.gpg
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" > /etc/apt/sources.list.d/ngrok.list
apt-get update && apt-get install -y ngrok
```

Or download directly from [ngrok.com](https://ngrok.com/download).

**Note**: You will need to sign up for a free ngrok account and get your auth token from [ngrok dashboard](https://dashboard.ngrok.com/get-started/your-authtoken).

### 4. Run the Voice Assistant

```bash
cd agents/examples/voice-assistant-sip-telnyx
task run
```

The voice assistant starts with all capabilities enabled.

### 5. Access the Application

- **Frontend**: http://localhost:3000
- **API Server**: http://localhost:9000
- **TMAN Designer**: http://localhost:49483

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
              "name": "stt",
              "addon": "deepgram_asr_python",
              "property": {
                "sample_rate": 8000,
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
            },
            {
              "name": "main_control",
              "addon": "main_python",
              "property": {
                "telnyx_api_key": "${env:TELNYX_API_KEY}",
                "telnyx_connection_id": "${env:TELNYX_CONNECTION_ID}",
                "telnyx_from_number": "${env:TELNYX_FROM_NUMBER}",
                "telnyx_server_port": 9000,
                "telnyx_public_server_url": "${env:TELNYX_PUBLIC_SERVER_URL}"
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
| `TELNYX_API_KEY` | string | - | Your Telnyx API key (required) |
| `TELNYX_CONNECTION_ID` | string | - | Your Telnyx Connection ID (required) |
| `TELNYX_FROM_NUMBER` | string | - | Your Telnyx phone number (required) |
| `TELNYX_PUBLIC_SERVER_URL` | string | - | Your public server URL for webhooks and WebSocket connections (required) - Telnyx uses this for webhooks and audio streaming. Use ngrok for local testing |
| `DEEPGRAM_API_KEY` | string | - | Deepgram API key (required) |
| `OPENAI_API_KEY` | string | - | OpenAI API key (required) |
| `OPENAI_MODEL` | string | - | OpenAI model name (optional) |
| `OPENAI_PROXY_URL` | string | - | Proxy URL for OpenAI API (optional) |
| `ELEVENLABS_TTS_KEY` | string | - | ElevenLabs API key (required) |
| `WEATHERAPI_API_KEY` | string | - | Weather API key (optional) |

## Customization

The voice assistant uses a modular design that allows you to easily replace STT, LLM, or TTS modules with other providers using TMAN Designer.

Access the visual designer at http://localhost:49483 to customize your voice agent. For detailed usage instructions, see the [TMAN Designer documentation](https://theten.ai/docs/ten_agent/customize_agent/tman-designer).

## Local Development with Ngrok

For local development, use the provided ngrok script to expose your local server:

```bash
./start-with-ngrok.sh
```

This will:
- Start ngrok with WebSocket support
- Expose your local server on a public URL
- Provide the URL for your `TELNYX_PUBLIC_SERVER_URL` environment variable

## Release as Docker image

**Note**: The following commands need to be executed outside of any Docker container.

### Build image

```bash
cd ai_agents
docker build -f agents/examples/voice-assistant-sip-telnyx/Dockerfile -t voice-assistant-sip-telnyx-app .
```

### Run

```bash
docker run --rm -it --env-file .env -p 9000:9000 -p 3000:3000 voice-assistant-sip-telnyx-app
```

### Access

- Frontend: http://localhost:3000
- API Server: http://localhost:9000

## API Usage

### RESTful API Endpoints

- `POST /api/call` - Create new outbound call
- `GET /api/calls` - List all active calls
- `GET /api/call/{call_id}` - Get call information
- `DELETE /api/call/{call_id}` - Stop and delete call
- `POST /webhook/status` - Telnyx status callback
- `GET /health` - Health check

### Starting a Call

```bash
curl -X POST http://localhost:9000/api/call \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+1234567890",
    "message": "Hello from AI assistant!"
  }'
```

### Getting Call Information

```bash
curl http://localhost:9000/api/call/v3:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Listing All Calls

```bash
curl http://localhost:9000/api/calls
```

### Stopping a Call

```bash
curl -X DELETE http://localhost:9000/api/call/v3:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## Learn More

- [Telnyx Programmable Voice Documentation](https://developers.telnyx.com/api/v2)
- [Telnyx Media Streams Documentation](https://developers.telnyx.com/api/v2/calls/voice)
- [Telnyx Call Control API](https://developers.telnyx.com/api-reference/call-commands/dial)
- [Deepgram API Documentation](https://developers.deepgram.com/)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [ElevenLabs API Documentation](https://docs.elevenlabs.io/)
- [TEN Framework Documentation](https://doc.theten.ai)

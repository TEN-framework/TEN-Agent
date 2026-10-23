# WebSocket Voice Assistant

A comprehensive voice assistant with real-time conversation capabilities using WebSocket communication, Deepgram STT, OpenAI LLM, and ElevenLabs TTS.

For the Agora Mind FDB-v3 graph, see [FDB.md](FDB.md), including Session control,
container configuration, collection events, and quick tests.

## Features

- **WebSocket-Based Real-time Voice Interaction**: Bidirectional audio streaming over WebSocket with complete STT → LLM → TTS processing
- **Base64 Audio Encoding**: Simple JSON message format for audio transmission

## Architecture

This example demonstrates a WebSocket-based voice assistant where:

1. **Audio Input**: Clients send base64-encoded PCM audio via WebSocket → STT → main_control → LLM → TTS
2. **Audio Output**: TTS audio is sent back to clients as base64-encoded JSON messages
3. **Data Messages**: Data messages (e.g., `asr_result`, `text_data`, `llm_response`) can be forwarded to clients if connected to websocket_server in the graph configuration
4. **Command Messages**: System commands (e.g., `tool_register`) are forwarded to clients as JSON messages if websocket_server receives them

```
┌─────────────────┐
│ WebSocket Client│
└────────┬────────┘
         │ {"audio": "<base64>"}
         ▼
┌─────────────────┐  pcm_frame  ┌─────┐  asr_result  ┌──────────────┐
│ websocket_server├────────────▶│ STT ├─────────────▶│ main_control │
└────────┬────────┘              └─────┘              └──────┬───────┘
         │                                                    │
         │ {"type": "audio|data|cmd"}                        │
         │                                                    ▼
         │                                                 ┌─────┐
         │                                                 │ LLM │
         │                                                 └──┬──┘
         │                                                    │
         │ pcm_frame                                          ▼
         │                                                 ┌─────┐
         └─────────────────────────────────────────────────┤ TTS │
                                                           └─────┘
```

## Prerequisites

### Required Environment Variables

1. **Deepgram Account**: Get credentials from [Deepgram Console](https://console.deepgram.com/)
   - `DEEPGRAM_API_KEY` - Your Deepgram API key (required)

2. **OpenAI Account**: Get credentials from [OpenAI Platform](https://platform.openai.com/)
   - `OPENAI_API_KEY` - Your OpenAI API key (required)

3. **ElevenLabs Account**: Get credentials from [ElevenLabs](https://elevenlabs.io/)
   - `ELEVENLABS_TTS_KEY` - Your ElevenLabs API key (required)

### Optional Environment Variables

- `OPENAI_MODEL` - OpenAI model name (optional, defaults to configured model)
- `OPENAI_PROXY_URL` - Proxy URL for OpenAI API (optional)
- `WEATHERAPI_API_KEY` - Weather API key for weather tool (optional)

## Setup

### 1. Set Environment Variables

Add to your `.env` file:

```bash
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
```

### 2. Install Dependencies

```bash
cd agents/examples/websocket-example
task install
```

This installs Python dependencies and frontend components.

### 3. Run the Voice Assistant

```bash
cd agents/examples/websocket-example
task run
```

### 4. Access the Application

- **Frontend**: http://localhost:3000 (The frontend will automatically generate a random WebSocket port between 8000-9000)
- **API Server**: http://localhost:8080
- **TMAN Designer**: http://localhost:49483

**Note**: The WebSocket server port is randomly assigned by the frontend client (between 8000-9000) and stored in browser localStorage. The port is displayed in the frontend UI. You can also configure a default port in `tenapp/property.json`, but the frontend will override it when starting the agent.

## WebSocket Protocol

### Connecting to the WebSocket Server

The WebSocket server port is randomly assigned by the frontend client (between 8000-9000) and can be configured in `tenapp/property.json`. When using the provided frontend, the port is automatically generated and displayed in the UI.

**Using the Frontend:**
The frontend automatically generates a random port, stores it in localStorage, and connects to it. The port is displayed in the UI badge.

**Connecting Programmatically:**
If you need to connect directly, you'll need to know the port. The frontend generates ports between 8000-9000:

```javascript
// Get the port from localStorage (if using the frontend)
const port = localStorage.getItem('websocket_port') || 8765; // fallback to default
const ws = new WebSocket(`ws://localhost:${port}`);

ws.onopen = () => {
  console.log('Connected to voice assistant');
};

ws.onerror = (error) => {
  console.error('Connection error:', error);
  // Check if error is due to existing connection
};

ws.onclose = (event) => {
  if (event.code === 1008) {
    console.log('Connection rejected: Another client is already connected');
  } else {
    console.log('Disconnected from voice assistant');
  }
};
```

### Sending Audio (Client → Server)

Send base64-encoded PCM audio in JSON format:

```javascript
// PCM audio format: 16kHz, mono, 16-bit
const audioBase64 = btoa(String.fromCharCode(...pcmData));

ws.send(JSON.stringify({
  audio: audioBase64,
  metadata: {
    session_id: "optional-session-id",
    // any other custom metadata
  }
}));
```

**Audio Requirements:**
- **Format**: Raw PCM (uncompressed)
- **Sample Rate**: 16000 Hz
- **Channels**: 1 (mono)
- **Bit Depth**: 16-bit (2 bytes per sample)
- **Encoding**: Base64

### Receiving Messages (Server → Client)

The server sends four types of messages:

#### 1. Audio Messages (TTS Output)

```javascript
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  if (message.type === 'audio') {
    // Decode base64 audio
    const pcmData = atob(message.audio);

    // Get audio properties from metadata
    const sampleRate = message.metadata.sample_rate; // 16000
    const channels = message.metadata.channels; // 1
    const bytesPerSample = message.metadata.bytes_per_sample; // 2
    const samplesPerChannel = message.metadata.samples_per_channel;

    // Play audio using Web Audio API or other audio playback
    playAudio(pcmData, sampleRate, channels);
  }
};
```

#### 2. Data Messages

The server sends data messages with different `name` fields depending on the message type:

**ASR Results:**
```javascript
if (message.type === 'data' && message.name === 'asr_result') {
  const text = message.data?.text || message.data?.transcript || '';
  const isFinal = message.data?.is_final || message.data?.final || false;

  if (isFinal) {
    console.log('Final transcription:', text);
    // Add to chat history as user message
  } else {
    console.log('Partial transcription:', text);
    // Show as live transcription
  }
}
```

**Text Data (with data_type: 'transcribe'):**
```javascript
if (message.type === 'data' && message.name === 'text_data' && message.data?.data_type === 'transcribe') {
  const text = message.data.text || '';
  const isFinal = message.data.is_final || false;
  const role = message.data.role === 'user' ? 'user' : 'assistant';

  if (isFinal && text) {
    console.log(`Final ${role} message:`, text);
    // Add to chat history
  } else if (text && role === 'user') {
    console.log('Partial transcription:', text);
    // Show as live transcription
  }
}
```

**LLM Responses:**
```javascript
if (message.type === 'data' && (message.name === 'llm_response' || message.name === 'chat_message')) {
  const text = message.data?.text || message.data?.content || '';
  if (text) {
    console.log('LLM response:', text);
    // Add to chat history as assistant message
  }
}
```

#### 3. Command Messages

```javascript
if (message.type === 'cmd') {
  console.log('Received command:', message.name, message.data);
  // Handle system commands (e.g., tool_register, on_user_joined)
}
```

#### 4. Error Messages

```javascript
if (message.type === 'error') {
  console.error('Server error:', message.error);
}
```

## Configuration

The voice assistant is configured in `tenapp/property.json`. The graph includes:

- **websocket_server**: Receives audio from clients and sends TTS audio back. Receives data messages forwarded by `main_control`.
- **stt** (Deepgram ASR): Converts speech to text, sends `asr_result` to main_control
- **main_control** (main_python): Orchestrates the conversation flow, receives `asr_result` from STT, and forwards transcription data (`text_data` with `data_type: 'transcribe'`) to `websocket_server` programmatically
- **llm** (OpenAI): Generates responses
- **tts** (ElevenLabs): Converts text to speech
- **weatherapi_tool_python**: Optional weather tool for LLM function calling

**Note**: The `main_control` extension handles message forwarding to `websocket_server` programmatically using `ten_env.send_data()`, so explicit data connections in `property.json` are not needed. The `main_control` extension forwards `text_data` messages with transcription information (both user and assistant messages) to `websocket_server` for broadcasting to clients.

Key configuration sections:

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
              "name": "websocket_server",
              "addon": "websocket_server",
              "property": {
                "port": 8765,
                "host": "0.0.0.0",
                "sample_rate": 16000,
                "channels": 1,
                "bytes_per_sample": 2
              }
            },
            // Note: The port can be overridden when starting the agent via the API
            // The frontend automatically generates a random port (8000-9000) and passes it in properties
            {
              "name": "stt",
              "addon": "deepgram_asr_python",
              "property": {
                "params": {
                  "api_key": "${env:DEEPGRAM_API_KEY}",
                  "language": "en-US",
                  "model": "nova-3"
                }
              }
            },
            {
              "name": "llm",
              "addon": "openai_llm2_python",
              "property": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "${env:OPENAI_API_KEY}",
                "model": "${env:OPENAI_MODEL}",
                "max_tokens": 512,
                "frequency_penalty": 0.9,
                "proxy_url": "${env:OPENAI_PROXY_URL|}",
                "greeting": "TEN Agent connected. How can I help you today?",
                "max_memory_length": 10
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
          ],
          "connections": [
            {
              "extension": "websocket_server",
              "audio_frame": [
                {
                  "name": "pcm_frame",
                  "dest": [{"extension": "stt"}]
                },
                {
                  "name": "pcm_frame",
                  "source": [{"extension": "tts"}]
                }
              ]
            }
          ]
        }
      }
    ]
  }
}
```

### Configuration Parameters

#### WebSocket Server

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `websocket_server.port` | int | 8765 | WebSocket server port. Can be overridden when starting the agent via API `properties` parameter. The frontend automatically generates a random port (8000-9000) and passes it in the start request. |
| `websocket_server.host` | string | 0.0.0.0 | WebSocket server host |
| `websocket_server.sample_rate` | int | 16000 | Audio sample rate in Hz |
| `websocket_server.channels` | int | 1 | Number of audio channels (mono) |
| `websocket_server.bytes_per_sample` | int | 2 | Bytes per sample (2 for 16-bit) |

**Port Assignment:**
- The port can be configured in `tenapp/property.json` as a default value
- When using the frontend, it automatically generates a random port between 8000-9000 and stores it in browser localStorage
- The frontend passes the port in the `properties` parameter when starting the agent via the API, which overrides the default from property.json
- The port is displayed in the frontend UI for reference

#### Environment Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `DEEPGRAM_API_KEY` | string | Yes | Deepgram API key for speech-to-text |
| `OPENAI_API_KEY` | string | Yes | OpenAI API key for language model |
| `OPENAI_MODEL` | string | No | OpenAI model name (e.g., gpt-4, gpt-3.5-turbo) |
| `OPENAI_PROXY_URL` | string | No | Proxy URL for OpenAI API requests |
| `ELEVENLABS_TTS_KEY` | string | Yes | ElevenLabs API key for text-to-speech |
| `WEATHERAPI_API_KEY` | string | No | Weather API key for weather tool (optional) |

**Note**: The WebSocket server only accepts one client connection at a time. If a client is already connected, new connection attempts will be rejected with an error message.

## Client Example

Here's a complete example of a WebSocket client:

```javascript
class VoiceAssistantClient {
  constructor(port = 8765) {
    // Port can be obtained from localStorage if using the frontend,
    // or passed directly if you know the port
    const wsUrl = `ws://localhost:${port}`;
    this.ws = new WebSocket(wsUrl);
    this.setupHandlers();
  }

  setupHandlers() {
    this.ws.onopen = () => {
      console.log('Connected to voice assistant');
    };

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);

      switch (message.type) {
        case 'audio':
          this.handleAudio(message);
          break;
        case 'data':
          this.handleData(message);
          break;
        case 'cmd':
          this.handleCommand(message);
          break;
        case 'error':
          console.error('Error:', message.error);
          break;
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    this.ws.onclose = () => {
      console.log('Disconnected from voice assistant');
    };
  }

  sendAudio(pcmData) {
    const audioBase64 = btoa(String.fromCharCode(...new Uint8Array(pcmData)));
    this.ws.send(JSON.stringify({
      audio: audioBase64,
      metadata: {
        timestamp: Date.now()
      }
    }));
  }

  handleAudio(message) {
    // Decode and play TTS audio
    const pcmData = atob(message.audio);
    console.log('Received audio:', pcmData.length, 'bytes');
    // Implement audio playback here
  }

  handleData(message) {
    console.log('Data:', message.name, message.data);

    // Handle ASR results
    if (message.name === 'asr_result') {
      const text = message.data?.text || message.data?.transcript || '';
      const isFinal = message.data?.is_final || message.data?.final || false;
      if (isFinal) {
        console.log('Final transcription:', text);
      } else {
        console.log('Partial transcription:', text);
      }
    }

    // Handle text_data with data_type: 'transcribe'
    if (message.name === 'text_data' && message.data?.data_type === 'transcribe') {
      const text = message.data.text || '';
      const isFinal = message.data.is_final || false;
      const role = message.data.role === 'user' ? 'user' : 'assistant';
      console.log(`${role} message (${isFinal ? 'final' : 'partial'}):`, text);
    }

    // Handle LLM responses
    if (message.name === 'llm_response' || message.name === 'chat_message') {
      const text = message.data?.text || message.data?.content || '';
      console.log('LLM response:', text);
    }
  }

  handleCommand(message) {
    console.log('Command:', message.name, message.data);
  }

  close() {
    this.ws.close();
  }
}

// Usage
// Get port from localStorage (if using the frontend) or use a known port
const port = localStorage.getItem('websocket_port')
  ? parseInt(localStorage.getItem('websocket_port'), 10)
  : 8765; // fallback to default

const client = new VoiceAssistantClient(port);

// Send audio from microphone or file
client.sendAudio(pcmAudioData);
```

## Customization

The voice assistant uses a modular design that allows you to easily replace STT, LLM, or TTS modules with other providers using TMAN Designer.

Access the visual designer at http://localhost:49483 to customize your voice agent. For detailed usage instructions, see the [TMAN Designer documentation](https://theten.ai/docs/ten_agent/customize_agent/tman-designer).

## Release as Docker image

**Note**: The following commands need to be executed outside of any Docker container.

### Build image

```bash
cd ai_agents
docker build -f agents/examples/websocket-example/Dockerfile -t websocket-voice-assistant .
```

### Run

```bash
# Note: The WebSocket port is dynamically assigned (8000-9000) by the frontend
# You'll need to expose the port range. Docker doesn't support port ranges directly,
# so you may need to expose multiple ports or use a specific port configuration.
# For a fixed port, configure it in tenapp/property.json and expose that port:
docker run --rm -it --env-file .env -p 8080:8080 -p 3000:3000 -p 8765:8765 websocket-voice-assistant
```

**Note**: If using dynamic ports, you'll need to either:
1. Configure a fixed port in `tenapp/property.json` and expose that specific port
2. Use Docker's `--publish-all` flag (not recommended for production)
3. Manually expose the specific port that the frontend generates

### Access

- Frontend: http://localhost:3000 (port is randomly assigned and displayed in UI)
- API Server: http://localhost:8080
- WebSocket Server: Port is randomly assigned by frontend (8000-9000) or configured in property.json

## Learn More

- [Deepgram API Documentation](https://developers.deepgram.com/)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [ElevenLabs API Documentation](https://docs.elevenlabs.io/)
- [TEN Framework Documentation](https://doc.theten.ai)

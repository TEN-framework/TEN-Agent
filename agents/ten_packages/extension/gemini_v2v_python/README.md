# gemini_v2v_python

An extension for integrating Gemini's Next Generation of **Multimodal** AI into your application, providing configurable AI-driven features such as conversational agents, task automation, and tool integration.

## Features

- Gemini **Multimodal** Integration: Leverage Gemini **Multimodal** models for voice-to-voice as well as text processing.
- Configurable: Easily customize API keys, model settings, prompts, temperature, etc.
- Async Queue Processing: Supports real-time message processing with task cancellation and prioritization.

## API

Refer to the `api` definition in [manifest.json] and default values in [property.json](property.json).

| **Property**               | **Type**   | **Description**                           |
|----------------------------|------------|-------------------------------------------|
| `api_key`                   | `string`   | API key for authenticating with Gemini    |
| `temperature`               | `float32`  | Sampling temperature, higher values mean more randomness |
| `model`                     | `string`   | Model identifier (e.g., GPT-4, Gemini-1)  |
| `max_tokens`                | `int32`    | Maximum number of tokens to generate      |
| `system_message`            | `string`   | Default system message to send to the model |
| `voice`                     | `string`   | Voice that Gemini model uses, such as `alloy`, `echo`, `shimmer`, etc. |
| `server_vad`                | `bool`     | Flag to enable or disable server VAD for Gemini |
| `language`                  | `string`   | Language that Gemini model responds in, such as `en-US`, `zh-CN`, etc. |
| `dump`                      | `bool`     | Flag to enable or disable audio dump for debugging purposes |
| `base_uri`                  | `string`   | Base URI for connecting to the Gemini service |
| `audio_out`                 | `bool`     | Flag to enable or disable audio output    |
| `input_transcript`          | `bool`     | Flag to enable input transcript processing |
| `sample_rate`               | `int32`    | Sample rate for audio processing          |
| `stream_id`                 | `int32`    | Stream ID for identifying audio streams   |
| `greeting`                  | `string`   | Greeting message for initial interaction  |

### Data Out

| **Name**       | **Property** | **Type**   | **Description**               |
|----------------|--------------|------------|-------------------------------|
| `text_data`    | `text`       | `string`   | Outgoing text data             |
| `append`       | `text`       | `string`   | Additional text appended to the output |

### Command Out

| **Name**       | **Description**                             |
|----------------|---------------------------------------------|
| `flush`        | Response after flushing the current state    |
| `tool_call`    | Invokes a tool with specific arguments       |

### Audio Frame In

| **Name**         | **Description**                           |
|------------------|-------------------------------------------|
| `pcm_frame`      | Audio frame input for voice processing    |

### Video Frame In

| **Name**         | **Description**                           |
|------------------|-------------------------------------------|
| `video_frame`    | Video frame input for processing          |

### Audio Frame Out

| **Name**         | **Description**                           |
|------------------|-------------------------------------------|
| `pcm_frame`      | Audio frame output after voice processing |

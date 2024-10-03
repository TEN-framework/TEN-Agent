# openai_v2v_python

An extension for integrating OpenAI's Next Generation of **Multimodal** AI into your application, providing configurable AI-driven features such as conversational agents, task automation, and tool integration.

## Features

<!-- main features introduction -->

- OpenAI **Multimodal** Integration: Leverage GPT **Multimodal** models for voice to voice as well as text processing.
- Configurable: Easily customize API keys, model settings, prompts, temperature, etc.
- Async Queue Processing: Supports real-time message processing with task cancellation and prioritization.
<!-- - Tool Support: Integrate external tools like image recognition via OpenAI's API. -->

## API

Refer to `api` definition in [manifest.json] and default values in [property.json](property.json).

<!-- Additional API.md can be referred to if extra introduction needed -->

| **Property**               | **Type**   | **Description**                           |
|----------------------------|------------|-------------------------------------------|
| `api_key`                   | `string`   | API key for authenticating with OpenAI    |
| `temperature`               | `float64`  | Sampling temperature, higher values mean more randomness |
| `model`                     | `string`   | Model identifier (e.g., GPT-3.5, GPT-4)   |
| `max_tokens`                | `int64`    | Maximum number of tokens to generate      |
| `system_message`            | `string`   | Default system message to send to the model       |
| `voice`                     | `string`   | Voice that OpenAI model speeches, such as `alloy`, `echo`, `shimmer`, etc |
| `server_vad`                | `bool`     | Flag to enable or disable server vad of OpenAI |
| `language`                  | `string`   | Language that OpenAO model reponds, such as `en-US`, `zh-CN`, etc | 
| `dump`                      | `bool`     | Flag to enable or disable audio dump for debugging purpose  |

### Data Out:
| **Name**       | **Property** | **Type**   | **Description**               |
|----------------|--------------|------------|-------------------------------|
| `text_data`    | `text`       | `string`   | Outgoing text data             |

### Command Out:
| **Name**       | **Description**                             |
|----------------|---------------------------------------------|
| `flush`        | Response after flushing the current state    |

### Audio Frame In:
| **Name**         | **Description**                           |
|------------------|-------------------------------------------|
| `pcm_frame`      | Audio frame input for voice processing    |

### Audio Frame Out:
| **Name**         | **Description**                           |
|------------------|-------------------------------------------|
| `pcm_frame`    | Audio frame output after voice processing    |

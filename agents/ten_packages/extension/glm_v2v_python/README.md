# glm_v2v_python

An extension for integrating GLM's **Multimodal** AI into your application, providing configurable AI-driven features such as conversational agents, task automation, and tool integration.

## Features

<!-- main features introduction -->

- GLM **Multimodal** Integration: Leverage GLM **Multimodal** models for voice to voice as well as text processing.
- Configurable: Easily customize API keys, model settings, prompts, temperature, etc.
- Async Queue Processing: Supports real-time message processing with task cancellation and prioritization.
<!-- - Tool Support: Integrate external tools like image recognition via OpenAI's API. -->

## API

Refer to `api` definition in [manifest.json] and default values in [property.json](property.json).

<!-- Additional API.md can be referred to if extra introduction needed -->

| **Property**               | **Type**   | **Description**                           |
|----------------------------|------------|-------------------------------------------|
| `api_key`                   | `string`   | API key for authenticating with OpenAI    |
| `max_tokens`                | `int64`    | Maximum number of tokens to generate      |
| `prompt`                    | `string`   | Default system message to send to the model       |
| `server_vad`                | `bool`     | Flag to enable or disable server vad of OpenAI |
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


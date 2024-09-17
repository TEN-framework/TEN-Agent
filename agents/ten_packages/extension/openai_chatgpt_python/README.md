# openai_chatgpt_python

An extension for integrating OpenAI's GPT models (e.g., GPT-4) into your application, providing configurable AI-driven features such as conversational agents, task automation, and tool integration.

## Features

<!-- main features introduction -->

- OpenAI GPT Integration: Leverage GPT models for text processing and conversational tasks.
- Configurable: Easily customize API keys, model settings, prompts, temperature, etc.
- Async Queue Processing: Supports real-time message processing with task cancellation and prioritization.
- Tool Support: Integrate external tools like image recognition via OpenAI's API.

## API

Refer to `api` definition in [manifest.json] and default values in [property.json](property.json).

<!-- Additional API.md can be referred to if extra introduction needed -->

| **Property**               | **Type**   | **Description**                           |
|----------------------------|------------|-------------------------------------------|
| `api_key`                   | `string`   | API key for authenticating with OpenAI    |
| `frequency_penalty`         | `float64`  | Controls how much to penalize new tokens based on their existing frequency in the text so far |
| `presence_penalty`          | `float64`  | Controls how much to penalize new tokens based on whether they appear in the text so far |
| `temperature`               | `float64`  | Sampling temperature, higher values mean more randomness |
| `top_p`                     | `float64`  | Nucleus sampling, chooses tokens with cumulative probability `p` |
| `model`                     | `string`   | Model identifier (e.g., GPT-3.5, GPT-4)   |
| `max_tokens`                | `int64`    | Maximum number of tokens to generate      |
| `base_url`                  | `string`   | API base URL                              |
| `prompt`                    | `string`   | Default prompt to send to the model       |
| `greeting`                  | `string`   | Greeting message to be used               |
| `checking_vision_text_items`| `string`   | Items for checking vision-based text responses |
| `proxy_url`                 | `string`   | URL of the proxy server                   |
| `max_memory_length`         | `int64`    | Maximum memory length for processing      |
| `enable_tools`              | `bool`     | Flag to enable or disable external tools  |

### Data In:
| **Name**       | **Property** | **Type**   | **Description**               |
|----------------|--------------|------------|-------------------------------|
| `text_data`    | `text`       | `string`   | Incoming text data             |

### Data Out:
| **Name**       | **Property** | **Type**   | **Description**               |
|----------------|--------------|------------|-------------------------------|
| `text_data`    | `text`       | `string`   | Outgoing text data             |

### Command In:
| **Name**       | **Description**                             |
|----------------|---------------------------------------------|
| `flush`        | Command to flush the current processing state |

### Command Out:
| **Name**       | **Description**                             |
|----------------|---------------------------------------------|
| `flush`        | Response after flushing the current state    |

### Video Frame In:
| **Name**         | **Description**                           |
|------------------|-------------------------------------------|
| `video_frame`    | Video frame input for vision processing    |

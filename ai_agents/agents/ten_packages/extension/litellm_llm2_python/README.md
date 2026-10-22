# litellm_llm2_python

An LLM extension that routes chat completions through [LiteLLM](https://github.com/BerriAI/litellm), a unified gateway to 100+ LLM providers (OpenAI, Anthropic, Google Gemini, Azure, AWS Bedrock, Mistral, Groq, Together, Ollama, and more). One extension replaces the need for a separate per-provider extension, and reaches providers whose auth is not OpenAI-compatible (Bedrock SigV4, Vertex ADC, Azure AD).

LiteLLM speaks the OpenAI wire format, so this extension reuses the same streaming, reasoning, and tool-call handling as `openai_llm2_python`; only the transport is swapped to `litellm.acompletion`.

## Features

- Multi-provider: select any provider by its LiteLLM model id (e.g. `anthropic/claude-3-5-sonnet-20241022`, `gpt-4o`, `gemini/gemini-1.5-pro`, `bedrock/...`).
- Native credentials: LiteLLM reads each provider's own env var (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, ...) when `api_key` is blank.
- Proxy-ready: set `base_url` (or `LITELLM_API_BASE`) + `api_key` to route through a self-hosted LiteLLM proxy.
- `drop_params=True` by default: per-provider-unsupported params are dropped instead of erroring.
- Streaming, reasoning (`reasoning_content`) deltas, and tool/function calling — same behavior as the OpenAI extension.

## API

Refer to the `api` definition in [manifest.json] and default values in [property.json](property.json).

| **Property**       | **Type**  | **Description**                                                                 |
|--------------------|-----------|---------------------------------------------------------------------------------|
| `api_key`          | `string`  | Optional. Provider/proxy key. Leave blank to use each provider's own env var.   |
| `model`            | `string`  | LiteLLM model id (e.g. `gpt-4o`, `anthropic/claude-3-5-sonnet-20241022`).       |
| `base_url`         | `string`  | Optional. Set only to target a LiteLLM proxy / OpenAI-compatible endpoint.      |
| `temperature`      | `float64` | Sampling temperature.                                                           |
| `top_p`            | `float64` | Nucleus sampling.                                                               |
| `frequency_penalty`| `float64` | Frequency penalty (dropped automatically for providers that don't support it).  |
| `presence_penalty` | `float64` | Presence penalty (dropped automatically for providers that don't support it).   |
| `max_tokens`       | `int64`   | Maximum number of tokens to generate.                                           |
| `prompt`           | `string`  | Default system prompt.                                                          |
| `proxy_url`        | `string`  | Optional HTTP proxy URL.                                                         |

### Data In:
| **Name**    | **Property** | **Type** | **Description**    |
|-------------|--------------|----------|--------------------|
| `text_data` | `text`       | `string` | Incoming text data |

### Data Out:
| **Name**    | **Property** | **Type** | **Description**    |
|-------------|--------------|----------|--------------------|
| `text_data` | `text`       | `string` | Outgoing text data |

### Command In:
| **Name** | **Description**                               |
|----------|-----------------------------------------------|
| `flush`  | Command to flush the current processing state |

### Command Out:
| **Name** | **Description**                            |
|----------|--------------------------------------------|
| `flush`  | Response after flushing the current state  |

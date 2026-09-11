# Speko Router LLM2 extension

Maps the TEN LLM2 command interface to Speko's Responses API. Streaming text,
function calls, full conversation history, usage, aborts, and Router errors
are preserved in TEN-native events.

## Configuration

Set `SPEKO_API_KEY` and add the extension to a graph.

| Property | Default | Description |
| --- | --- | --- |
| `base_url` | `https://router.speko.dev` | Speko Router origin |
| `prompt` | helpful assistant | Default system prompt |
| `max_output_tokens` | `512` | Required reservation ceiling |
| `temperature` | `0.7` | Sampling temperature |
| `top_p` | unset | Optional nucleus sampling value |
| `routing` | auto, balanced | Speko routing selection |

```json
{
  "type": "extension",
  "name": "llm",
  "addon": "speko_llm2_python",
  "extension_group": "llm",
  "property": {
    "api_key": "${env:SPEKO_API_KEY}",
    "routing": {"mode": "auto", "objective": "balanced"},
    "max_output_tokens": 512
  }
}
```

TEN request parameters may override `routing`, `max_output_tokens` (or
`max_tokens`), `temperature`, `top_p`, and `response_format`. A TEN `model`
override must use `provider/model`, unless `routing.provider` is already
configured in explicit mode.

Speko's launch Responses contract accepts text content only. Image content is
rejected locally with a clear error instead of being silently dropped.

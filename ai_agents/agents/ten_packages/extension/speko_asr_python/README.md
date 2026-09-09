# Speko ASR Extension

Streaming transcription through the [Speko](https://speko.ai) model
router. Instead of pinning one STT vendor, the router benchmarks
providers per language and dials the best one for each session, with
automatic failover between providers before the first byte.

## Features

- One API key for every supported STT provider
- Benchmark-led routing by language, word error rate, cost, and latency
- Interim (partial) and final transcripts over WebSocket
- Routing controls: objective, provider allow/deny lists, price ceiling

## Configuration

| Field | Default | Description |
|---|---|---|
| `params.api_key` | `${env:SPEKO_API_KEY}` | Speko router API key (`sk_live_...`) |
| `params.language` | `en` | BCP-47 tag or bare ISO 639-1 code |
| `params.sample_rate` | `16000` | Input PCM sample rate (8000–48000) |
| `params.interim_results` | `true` | Emit partial transcripts |
| `params.objective` | key policy | `latency` \| `quality` \| `cost` \| `balanced` |
| `params.allow` | — | CSV of `provider` or `provider:model` ids |
| `params.deny` | — | CSV of `provider` or `provider:model` ids |
| `params.max_price` | — | USD per minute ceiling |

Languages currently enabled by the router: `en`, `ar`, `de`, `es`,
`fr`, `hi`, `nb`, `ta`, `te`. `GET https://api.speko.ai/v1/models`
lists the live model catalog and language set.

## Wire

`wss://api.speko.ai/v1/transcribe/stream` — one JSON config frame,
then bare little-endian 16-bit mono PCM binary frames (no WAV header).
Transcript frames come back as JSON; an `end` frame flushes and closes
the session.

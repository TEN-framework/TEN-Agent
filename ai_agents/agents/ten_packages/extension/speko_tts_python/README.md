# Speko TTS Extension

Text-to-speech through the [Speko](https://speko.ai) model router.
Instead of pinning one TTS vendor, the router benchmarks providers per
language and dials the best one per request (`model: "auto"`), with
automatic failover between providers before the first byte.

## Features

- One API key for every supported TTS provider
- Benchmark-led routing by language, quality (Elo), cost, and latency
- Streamed raw PCM — always signed 16-bit mono 24 kHz, normalized at
  the router edge so failover never changes the audio format
- Voice pinning (a voice id restricts routing to its provider) and
  routing controls: objective, allow/deny lists, price ceiling

## Configuration

| Field | Default | Description |
|---|---|---|
| `params.api_key` | `${env:SPEKO_API_KEY}` | Speko router API key (`sk_live_...`) |
| `params.model` | `auto` | `auto` or a `provider:model` id from `/v1/models` |
| `params.voice` | routing decides | Voice id; pins routing to that voice's provider |
| `params.language` | `en` | BCP-47 tag; full accent tags (e.g. `es-PR`) count for TTS |
| `params.speed` | `1.0` | Playback speed multiplier |
| `params.objective` | key policy | `latency` \| `quality` \| `cost` \| `balanced` |
| `params.allow` / `params.deny` | — | CSV of `provider` or `provider:model` ids |
| `params.max_price` | — | USD per 1M characters ceiling |

Languages currently enabled by the router: `en`, `ar`, `de`, `es`,
`fr`, `hi`, `nb`, `ta`, `te`. `GET https://api.speko.ai/v1/models`
lists the live model catalog, per-model voice rosters, and languages.

## Wire

`POST https://api.speko.ai/v1/audio/speech/stream` — chunked raw PCM
(`Content-Type: audio/pcm;rate=24000`) streamed as it is decoded from
the serving provider. The `x-route` response header names the
provider/model the router dialed; it is surfaced in TTFB metrics.

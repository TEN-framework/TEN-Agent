# TypeSafe Jev decision extension

This TEN extension exposes TypeSafe Jev as a reusable, text-only decision
provider. It does not generate chat responses. Configure `TYPESAFE_API_KEY` in
`ai_agents/.env` and install the extension with the containing tenapp.

## Commands

Send `decision_evaluate` with a JSON property object:

```json
{
  "request_id": "turn-1",
  "state": {"latest_user_text": "What time is it?"},
  "questions": {
    "route": {
      "type": "choice",
      "instructions": "Which model should answer this request?",
      "criteria": {
        "fast": "Simple requests answerable directly",
        "deep": "Multi-step or uncertain requests"
      }
    }
  }
}
```

`state` may be a string, object, or array. Question types are `choice`, `score`,
and `noul` as defined by the [TypeSafe API](https://docs.typesafe.ai/api).
A successful `CmdResult` has `request_id`, actual `model`, keyed `answers`,
`usage`, and `latency_ms`. An error result has `request_id` when available and
a stable `error_code`; it never includes the user state or the API key.

Send `abort` with `{"request_id":"turn-1"}` to cancel an in-flight call. The
abort result has a `cancelled` boolean; the cancelled evaluation returns an
error result. Evaluations are independent and may run concurrently.

Configuration lives under `params`: `api_key`, `base_url`, `model`, and
`timeout_ms`. The default model is pinned to `jev-1.13.0`; the SDK is pinned to
`0.7.2`. Calls have no automatic retries and a hard deadline. Do not enable
SDK debug logging: it prints request and response bodies.

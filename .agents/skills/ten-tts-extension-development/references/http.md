# HTTP adapter

Use the HTTP base extension so common request state, audio framing, TTFB, PCM dumping, and terminal events stay in one place.

The provider client should expose a streaming iterator with this shape:

```python
async def get(text, request_id):
    yield audio_bytes, RESPONSE
    yield None, END
```

It must also expose `cancel`, `clean`, and `get_extra_metadata() -> dict`. `get_extra_metadata()` is required even when the provider has no additional fields; return `{}` in that case. The HTTP base calls it unconditionally when handling the first audio response to report TTFB, so omitting it turns successful synthesis into a `NotImplementedError` before the first PCM frame is emitted.

Before reading audio, check the HTTP status and parse the provider error body. Map authentication failures to the TEN invalid-key category and other failures to the appropriate provider/transport category. On cancellation, stop iteration promptly and return a flush/interruption signal.

Build headers and payloads from validated configuration. Remove secrets and endpoint-only fields from the payload when they belong in headers or URL construction. Use bounded timeouts and a connection pool, close the client during shutdown, retain incomplete PCM bytes between chunks, and never log raw authorization headers or request payloads containing credentials.

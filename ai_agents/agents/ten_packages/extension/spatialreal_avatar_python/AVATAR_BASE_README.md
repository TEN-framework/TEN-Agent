# AsyncAvatarBaseExtension - Quick Start Guide

## Overview

`AsyncAvatarBaseExtension` is a base class for implementing avatar/digital human extensions in the TEN Framework. It handles all lifecycle management, audio processing, and error handling automatically. You only need to implement 7 business methods.

**Key Benefits:**
- ✅ Automatic lifecycle management (init, start, stop)
- ✅ Built-in audio queue and processing loop
- ✅ Sample rate validation
- ✅ Error handling and logging
- ✅ Command handling (flush, tts_audio_end)
- ✅ Optional audio dumping for debugging

---

## Quick Start: 7 Required Methods

To create your own avatar extension, inherit from `AsyncAvatarBaseExtension` and implement these 7 methods:

### 1. `validate_config(ten_env) -> bool`
**Purpose:** Load and validate your configuration.
**Called:** During `on_init()` automatically.
**Return:** `True` if valid, `False` otherwise.

```python
async def validate_config(self, ten_env: AsyncTenEnv) -> bool:
    self.config = await MyAvatarConfig.create_async(ten_env)

    if not self.config.api_key:
        ten_env.log_error("api_key is required")
        return False

    return True
```

### 2. `get_target_sample_rate() -> list[int]`
**Purpose:** Specify supported audio sample rates.
**Called:** When audio frames arrive.
**Return:** List of supported sample rates in Hz.

```python
def get_target_sample_rate(self) -> list[int]:
    return [24000]  # HeyGen/Anam support 24kHz
    # return [16000]  # Sensetime supports 16kHz
    # return [24000, 48000]  # Multiple rates
```

### 3. `connect_to_avatar(ten_env) -> None`
**Purpose:** Establish connection to your avatar service.
**Called:** During `on_start()` after config validation.
**Behavior:** If this raises an exception, the extension will not start.

```python
async def connect_to_avatar(self, ten_env: AsyncTenEnv) -> None:
    self.client = MyAvatarClient(self.config)
    await self.client.connect()
    ten_env.log_info("Connected to avatar service")
```

### 4. `disconnect_from_avatar(ten_env) -> None`
**Purpose:** Disconnect from your avatar service and clean up resources.
**Called:** During `on_stop()` automatically.
**Behavior:** Exceptions are logged but not raised (cleanup continues).

```python
async def disconnect_from_avatar(self, ten_env: AsyncTenEnv) -> None:
    if self.client:
        await self.client.disconnect()
        ten_env.log_info("Disconnected from avatar service")
```

### 5. `send_audio_to_avatar(audio_data: bytes) -> None`
**Purpose:** Send audio data to your avatar service.
**Called:** Automatically by the audio processing loop.
**Note:** Audio is sent as-is (no resampling).

```python
async def send_audio_to_avatar(self, audio_data: bytes) -> None:
    # Example: Encode to base64 if your service requires it
    base64_audio = base64.b64encode(audio_data).decode("utf-8")
    await self.client.send_audio(base64_audio)
```

### 6. `send_eof_to_avatar() -> None`
**Purpose:** Signal end of audio stream.
**Called:** Automatically when:
- `tts_audio_end` event arrives with `reason=1` (TTS completion)

```python
async def send_eof_to_avatar(self) -> None:
    await self.client.send_eof()
```

### 7. `interrupt_avatar() -> None`
**Purpose:** Interrupt avatar immediately (stop current speech).
**Called:** When `flush` command is received.

```python
async def interrupt_avatar(self) -> None:
    if self.client:
        await self.client.interrupt()
```

---

## Optional Method

### `get_dump_config() -> tuple[bool, str]`
**Purpose:** Enable audio dumping for debugging.
**Return:** `(should_dump, dump_path)`
**Default:** `(False, "")`

```python
def get_dump_config(self) -> tuple[bool, str]:
    if self.config.dump:
        return (True, self.config.dump_path)
    return (False, "")
```

---

## Complete Example

Here's a complete implementation example:

```python
from ten_runtime import AsyncTenEnv
from ten_ai_base.config import BaseConfig
from avatar_base import AsyncAvatarBaseExtension
from dataclasses import dataclass
import base64

@dataclass
class MyAvatarConfig(BaseConfig):
    api_key: str = ""
    avatar_id: str = "default"
    sample_rate: int = 24000
    dump: bool = False
    dump_path: str = ""

class MyAvatarExtension(AsyncAvatarBaseExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.config: MyAvatarConfig | None = None
        self.client = None

    # 1. Validate configuration
    async def validate_config(self, ten_env: AsyncTenEnv) -> bool:
        self.config = await MyAvatarConfig.create_async(ten_env)

        if not self.config.api_key:
            ten_env.log_error("[MyAvatar] api_key is required")
            return False

        ten_env.log_info(f"[MyAvatar] Config validated (avatar={self.config.avatar_id})")
        return True

    # 2. Target sample rate
    def get_target_sample_rate(self) -> list[int]:
        return [self.config.sample_rate]

    # 3. Connect to service
    async def connect_to_avatar(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("[MyAvatar] Connecting...")
        self.client = MyAvatarClient(self.config)
        await self.client.connect()
        ten_env.log_info("[MyAvatar] Connected")

    # 4. Disconnect from service
    async def disconnect_from_avatar(self, ten_env: AsyncTenEnv) -> None:
        if self.client:
            await self.client.disconnect()
            ten_env.log_info("[MyAvatar] Disconnected")

    # 5. Send audio
    async def send_audio_to_avatar(self, audio_data: bytes) -> None:
        if self.client:
            base64_audio = base64.b64encode(audio_data).decode("utf-8")
            await self.client.send_audio(base64_audio)

    # 6. Send EOF
    async def send_eof_to_avatar(self) -> None:
        if self.client:
            await self.client.send_eof()

    # 7. Interrupt
    async def interrupt_avatar(self) -> None:
        if self.client:
            await self.client.interrupt()

    # Optional: Enable audio dumping
    def get_dump_config(self) -> tuple[bool, str]:
        if self.config:
            return (self.config.dump, self.config.dump_path)
        return (False, "")
```

---

## Automatic Lifecycle

The base class handles the complete lifecycle automatically:

```
1. on_init()
   └─> validate_config()

2. on_start()
   └─> connect_to_avatar()
   └─> Start audio processing loop

3. Audio Processing (automatic)
   └─> on_audio_frame() receives audio
   └─> Check sample rate
   └─> Queue audio
   └─> send_audio_to_avatar() called from loop

4. Commands (automatic)
   └─> flush command → interrupt_avatar()
   └─> tts_audio_end event → send_eof_to_avatar()

5. on_stop()
   └─> Stop audio processing loop
   └─> disconnect_from_avatar()
```

**You don't need to override `on_init()`, `on_start()`, or `on_stop()`!**

---

## Audio Processing Details

### Sample Rate Validation
- Audio frames are checked against `get_target_sample_rate()`
- Unsupported sample rates are rejected with an error message
- Error is sent only once to avoid log spam

### Audio Queue
- Audio is queued automatically (unbounded queue)
- Processing loop calls `send_audio_to_avatar()` for each frame
- Queue is cleared on `flush` command

### Audio Dumping
- Enable by returning `(True, "/path/to/dump")` from `get_dump_config()`
- Audio is saved to `{dump_path}/{extension_name}_in.pcm`
- Useful for debugging audio issues

---

## Error Handling

### Configuration Validation
- If `validate_config()` returns `False`:
  - Extension logs error
  - Audio processing is disabled
  - `connect_to_avatar()` is NOT called

### Connection Errors
- If `connect_to_avatar()` raises an exception:
  - Error is logged
  - Exception is propagated
  - Extension fails to start

### Disconnection Errors
- If `disconnect_from_avatar()` raises an exception:
  - Error is logged
  - Exception is NOT propagated
  - Cleanup continues

### Audio Processing Errors
- If `send_audio_to_avatar()` raises an exception:
  - Error is logged
  - Processing continues with next frame

---

## Command Handling

### Flush Command
When a `flush` command is received:
1. Audio queue is cleared
2. `interrupt_avatar()` is called
3. `flush` command is forwarded

### TTS Audio End Event
When `tts_audio_end` event arrives with `reason=1`:
1. `send_eof_to_avatar()` is called automatically
2. Signals that TTS generation is complete

---

## Reference Implementation

See `heygen_avatar_python2/extension.py` for a complete reference implementation using the HeyGen avatar service.

Key files:
- `avatar_base.py` - Base class implementation
- `extension.py` - HeyGen implementation example
- `heygen.py` - HeyGen client implementation

---

## Summary

To implement your own avatar extension:

1. ✅ Create a config class with your service parameters
2. ✅ Inherit from `AsyncAvatarBaseExtension`
3. ✅ Implement 7 required methods
4. ✅ Use consistent log prefixes
5. ✅ Test with different sample rates
6. ✅ Handle errors gracefully

The base class handles everything else automatically!

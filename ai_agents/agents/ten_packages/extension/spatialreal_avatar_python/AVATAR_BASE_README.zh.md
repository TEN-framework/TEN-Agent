# AsyncAvatarBaseExtension - 快速入门指南

## 概述

`AsyncAvatarBaseExtension` 是 TEN 框架中用于实现数字人/虚拟形象扩展的基类。它自动处理所有生命周期管理、音频处理和错误处理。你只需要实现 7 个业务方法。

**核心优势：**
- ✅ 自动生命周期管理（初始化、启动、停止）
- ✅ 内置音频队列和处理循环
- ✅ 采样率验证
- ✅ 错误处理和日志记录
- ✅ 命令处理（flush、tts_audio_end）
- ✅ 可选的音频转储功能用于调试

---

## 快速开始：7 个必需方法

要创建自己的数字人扩展，继承 `AsyncAvatarBaseExtension` 并实现以下 7 个方法：

### 1. `validate_config(ten_env) -> bool`
**用途：** 加载并验证配置。
**调用时机：** 在 `on_init()` 期间自动调用。
**返回值：** 有效返回 `True`，否则返回 `False`。

```python
async def validate_config(self, ten_env: AsyncTenEnv) -> bool:
    self.config = await MyAvatarConfig.create_async(ten_env)

    if not self.config.api_key:
        ten_env.log_error("api_key is required")
        return False

    return True
```

### 2. `get_target_sample_rate() -> list[int]`
**用途：** 指定支持的音频采样率。
**调用时机：** 当音频帧到达时。
**返回值：** 支持的采样率列表（单位：Hz）。

```python
def get_target_sample_rate(self) -> list[int]:
    return [24000]  # HeyGen/Anam 支持 24kHz
    # return [16000]  # Sensetime 支持 16kHz
    # return [24000, 48000]  # 支持多个采样率
```

### 3. `connect_to_avatar(ten_env) -> None`
**用途：** 建立与数字人服务的连接。
**调用时机：** 在 `on_start()` 期间，配置验证成功后。
**行为：** 如果抛出异常，扩展将不会启动。

```python
async def connect_to_avatar(self, ten_env: AsyncTenEnv) -> None:
    self.client = MyAvatarClient(self.config)
    await self.client.connect()
    ten_env.log_info("Connected to avatar service")
```

### 4. `disconnect_from_avatar(ten_env) -> None`
**用途：** 断开与数字人服务的连接并清理资源。
**调用时机：** 在 `on_stop()` 期间自动调用。
**行为：** 异常会被记录但不会抛出（清理继续进行）。

```python
async def disconnect_from_avatar(self, ten_env: AsyncTenEnv) -> None:
    if self.client:
        await self.client.disconnect()
        ten_env.log_info("Disconnected from avatar service")
```

### 5. `send_audio_to_avatar(audio_data: bytes) -> None`
**用途：** 将音频数据发送到数字人服务。
**调用时机：** 由音频处理循环自动调用。
**注意：** 音频按原样发送（不重采样）。

```python
async def send_audio_to_avatar(self, audio_data: bytes) -> None:
    # 示例：如果服务需要，编码为 base64
    base64_audio = base64.b64encode(audio_data).decode("utf-8")
    await self.client.send_audio(base64_audio)
```

### 6. `send_eof_to_avatar() -> None`
**用途：** 发送音频流结束信号。
**调用时机：** 自动调用，当：
- 收到 `tts_audio_end` 事件且 `reason=1`（TTS 完成）

```python
async def send_eof_to_avatar(self) -> None:
    await self.client.send_eof()
```

### 7. `interrupt_avatar() -> None`
**用途：** 立即中断数字人（停止当前语音）。
**调用时机：** 收到 `flush` 命令时。

```python
async def interrupt_avatar(self) -> None:
    if self.client:
        await self.client.interrupt()
```

---

## 可选方法

### `get_dump_config() -> tuple[bool, str]`
**用途：** 启用音频转储用于调试。
**返回值：** `(should_dump, dump_path)`
**默认值：** `(False, "")`

```python
def get_dump_config(self) -> tuple[bool, str]:
    if self.config.dump:
        return (True, self.config.dump_path)
    return (False, "")
```

---

## 完整示例

以下是一个完整的实现示例：

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

    # 1. 验证配置
    async def validate_config(self, ten_env: AsyncTenEnv) -> bool:
        self.config = await MyAvatarConfig.create_async(ten_env)

        if not self.config.api_key:
            ten_env.log_error("[MyAvatar] api_key is required")
            return False

        ten_env.log_info(f"[MyAvatar] Config validated (avatar={self.config.avatar_id})")
        return True

    # 2. 目标采样率
    def get_target_sample_rate(self) -> list[int]:
        return [self.config.sample_rate]

    # 3. 连接到服务
    async def connect_to_avatar(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_info("[MyAvatar] Connecting...")
        self.client = MyAvatarClient(self.config)
        await self.client.connect()
        ten_env.log_info("[MyAvatar] Connected")

    # 4. 断开服务连接
    async def disconnect_from_avatar(self, ten_env: AsyncTenEnv) -> None:
        if self.client:
            await self.client.disconnect()
            ten_env.log_info("[MyAvatar] Disconnected")

    # 5. 发送音频
    async def send_audio_to_avatar(self, audio_data: bytes) -> None:
        if self.client:
            base64_audio = base64.b64encode(audio_data).decode("utf-8")
            await self.client.send_audio(base64_audio)

    # 6. 发送 EOF
    async def send_eof_to_avatar(self) -> None:
        if self.client:
            await self.client.send_eof()

    # 7. 中断
    async def interrupt_avatar(self) -> None:
        if self.client:
            await self.client.interrupt()

    # 可选：启用音频转储
    def get_dump_config(self) -> tuple[bool, str]:
        if self.config:
            return (self.config.dump, self.config.dump_path)
        return (False, "")
```

---

## 自动生命周期

基类自动处理完整的生命周期：

```
1. on_init()
   └─> validate_config()

2. on_start()
   └─> connect_to_avatar()
   └─> 启动音频处理循环

3. 音频处理（自动）
   └─> on_audio_frame() 接收音频
   └─> 检查采样率
   └─> 音频入队
   └─> 从循环中调用 send_audio_to_avatar()

4. 命令处理（自动）
   └─> flush 命令 → interrupt_avatar()
   └─> tts_audio_end 事件 → send_eof_to_avatar()

5. on_stop()
   └─> 停止音频处理循环
   └─> disconnect_from_avatar()
```

**你不需要重写 `on_init()`、`on_start()` 或 `on_stop()`！**

---

## 音频处理细节

### 采样率验证
- 音频帧会根据 `get_target_sample_rate()` 进行检查
- 不支持的采样率会被拒绝并返回错误消息
- 错误只发送一次以避免日志刷屏

### 音频队列
- 音频自动入队（无界队列）
- 处理循环为每一帧调用 `send_audio_to_avatar()`
- 收到 `flush` 命令时清空队列

### 音频转储
- 通过从 `get_dump_config()` 返回 `(True, "/path/to/dump")` 来启用
- 音频保存到 `{dump_path}/{extension_name}_in.pcm`
- 用于调试音频问题

---

## 错误处理

### 配置验证
- 如果 `validate_config()` 返回 `False`：
  - 扩展记录错误
  - 音频处理被禁用
  - 不会调用 `connect_to_avatar()`

### 连接错误
- 如果 `connect_to_avatar()` 抛出异常：
  - 记录错误
  - 异常被传播
  - 扩展启动失败

### 断开连接错误
- 如果 `disconnect_from_avatar()` 抛出异常：
  - 记录错误
  - 异常不会传播
  - 清理继续进行

### 音频处理错误
- 如果 `send_audio_to_avatar()` 抛出异常：
  - 记录错误
  - 继续处理下一帧

---

## 命令处理

### Flush 命令
收到 `flush` 命令时：
1. 清空音频队列
2. 调用 `interrupt_avatar()`
3. 转发 `flush` 命令

### TTS Audio End 事件
收到 `tts_audio_end` 事件且 `reason=1` 时：
1. 自动调用 `send_eof_to_avatar()`
2. 表示 TTS 生成完成

---

## 参考实现

查看 `heygen_avatar_python2/extension.py` 获取使用 HeyGen 数字人服务的完整参考实现。

关键文件：
- `avatar_base.py` - 基类实现
- `extension.py` - HeyGen 实现示例
- `heygen.py` - HeyGen 客户端实现

---

## 总结

要实现自己的数字人扩展：

1. ✅ 创建包含服务参数的配置类
2. ✅ 继承 `AsyncAvatarBaseExtension`
3. ✅ 实现 7 个必需方法
4. ✅ 使用一致的日志前缀
5. ✅ 使用不同采样率进行测试
6. ✅ 优雅地处理错误

基类会自动处理其他所有事情！

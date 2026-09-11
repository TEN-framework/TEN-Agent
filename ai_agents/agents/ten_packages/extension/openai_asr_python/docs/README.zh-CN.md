# OpenAI ASR Python 扩展

一个用于 OpenAI 自动语音识别 (ASR) 服务的 Python 扩展，提供实时语音转文本转换功能，完全支持异步操作，使用 OpenAI Realtime 转录 API（GA 正式版）。

## 功能特性

- **完全异步支持**: 采用完整的异步架构，实现高性能语音识别
- **实时流式处理**: 使用 OpenAI 的 WebSocket API 支持低延迟实时音频流
- **OpenAI Realtime API**: 通过 GA 版 `session.update` 使用 OpenAI Realtime 转录 API
- **PCM16 音频**: 接受任意输入采样率，发送前重采样为 24 kHz PCM16
- **音频转储**: 可选的音频录制功能，用于调试和分析
- **可配置日志**: 可调整的日志级别，便于调试
- **错误处理**: 全面的错误处理和详细日志记录
- **多语言支持**: 通过 OpenAI 的转录模型支持多种语言
- **降噪功能**: 可选的降噪功能
- **对话检测**: 可配置的对话检测功能，用于对话分析

## 配置

扩展需要以下配置参数：

### 必需参数

- `api_key`: OpenAI API 密钥，用于身份验证
- `params`: OpenAI ASR 请求参数，包括音频格式和转录设置

### 可选参数

- `organization`: OpenAI 组织 ID（可选）
- `project`: OpenAI 项目 ID（可选）
- `base_url`: 自定义 WebSocket 基础 URL（可选）
- `dump`: 启用音频转储（默认：false）
- `dump_path`: 转储音频文件的路径（默认："openai_asr_in.pcm"）
- `log_level`: 日志级别（默认："INFO"）

### 配置示例

```json
{
  "params": {
    "api_key": "your_openai_api_key",
    "input_audio_format": "pcm16",
    "input_audio_transcription": {
      "model": "whisper-1",
      "prompt": "",
      "language": "en"
    },
    "turn_detection": {
      "type": "server_vad",
      "threshold": 0.5,
      "prefix_padding_ms": 300,
      "silence_duration_ms": 500
    }
  },
  "dump": false,
  "log_level": "INFO"
}
```

`organization`、`project`、`base_url` 等可选连接参数应放在 `params` 下。

## API

扩展实现了 `AsyncASRBaseExtension` 接口，提供以下关键方法：

### 核心方法

- `on_init()`: 初始化 OpenAI ASR 客户端和配置
- `start_connection()`: 建立与 OpenAI ASR 服务的连接
- `stop_connection()`: 关闭与 ASR 服务的连接
- `send_audio()`: 发送音频帧进行识别
- `finalize()`: 完成当前识别会话

### 事件处理器

- `on_asr_start()`: ASR 会话开始时调用
- `on_asr_delta()`: 收到转录增量时调用
- `on_asr_completed()`: 转录完成时调用
- `on_asr_committed()`: 音频缓冲区提交时调用
- `on_asr_server_error()`: 服务器错误时调用
- `on_asr_client_error()`: 客户端错误时调用

## 依赖项

- `typing_extensions`: 用于类型提示
- `pydantic`: 用于配置验证和数据模型
- `websockets`: 用于 WebSocket 通信
- `openai`: OpenAI Python 客户端库
- `pytest`: 用于测试（开发依赖）

## 开发

### 构建

扩展作为 TEN Framework 构建系统的一部分进行构建。无需额外的构建步骤。

### 测试

运行单元测试：

```bash
pytest tests/
```

扩展包含全面的测试：
- 配置验证
- 音频处理
- 错误处理
- 连接管理
- 转录结果处理

## 使用方法

1. **安装**: 扩展随 TEN Framework 自动安装
2. **配置**: 设置您的 OpenAI API 凭据和参数
3. **集成**: 通过 TEN Framework ASR 接口使用扩展
4. **监控**: 检查日志以进行调试和监控

## 错误处理

扩展通过以下方式提供详细的错误信息：
- 模块错误代码
- OpenAI 特定错误详情
- 全面的日志记录
- 优雅降级

## 性能

- **低延迟**: 使用 OpenAI 的流式 API 优化实时处理
- **高吞吐量**: 高效的音频帧处理
- **内存高效**: 最小的内存占用
- **连接复用**: 维护持久的 WebSocket 连接

## 安全性

- **凭据加密**: 敏感凭据在配置中加密
- **安全通信**: 使用与 OpenAI 的安全 WebSocket 连接
- **输入验证**: 全面的输入验证和清理

## 支持的 OpenAI 模型

扩展支持各种 OpenAI 转录模型：
- `whisper-1`: 标准 Whisper 模型
- `gpt-4o-transcribe`: GPT-4o 转录模型
- `gpt-4o-mini-transcribe`: GPT-4o mini 转录模型

## 音频格式支持

- **PCM16**（推荐）：扩展会将输入音频重采样为 24 kHz PCM16 后发送给 OpenAI。请将 `input_audio_format` 设为 `"pcm16"`。
- **G711 U-law / A-law**：配置中可接受以便向前兼容，但扩展目前无论此项如何设置，实际始终发送重采样后的 PCM16。

## 故障排除

### 常见问题

1. **连接失败**: 检查 API 密钥和网络连接
2. **音频质量问题**: 验证音频格式和采样率设置
3. **性能问题**: 调整缓冲区设置和模型选择
4. **日志问题**: 配置适当的日志级别

### 调试模式

通过在配置中设置 `dump: true` 启用调试模式，以录制音频进行分析。

## 许可证

此扩展是 TEN Framework 的一部分，根据 Apache License, Version 2.0 授权。

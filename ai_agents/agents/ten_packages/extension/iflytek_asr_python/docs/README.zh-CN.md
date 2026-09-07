# 讯飞 ASR Python 扩展

该扩展通过 WebSocket 接入讯飞实时转写服务，并将服务返回结果转换为 TEN Framework 标准 `ASRResult`。

## 功能

- 按讯飞协议发送首帧、中间帧和尾帧，状态依次为 `0`、`1`、`2`
- 使用 Base64 编码 PCM 音频，尾帧发送两个零字节作为结束标记
- 支持中间和最终转写结果、词边界、说话人标记及声纹元数据
- 支持多语种、引擎透传参数、热词、多用户热词和声纹库
- 意外断连时按有限次数的指数退避策略重连，成功后重置计数
- 输出 TEN 标准 FATAL/NON_FATAL 错误，并保留讯飞错误码和错误消息
- 使用分类日志和脱敏配置摘要，避免输出凭据和完整转写文本
- 支持 10 MB 保持缓冲、连接延迟指标和可选 PCM 音频 Dump
- 支持带超时兜底且只完成一次的 finalize，以及完整连接状态事件

## 配置

从 0.2.0 开始，供应商和连接参数必须统一放在 `params` 对象中，不再接受 0.1.0
的顶层字段。`dump` 与 `dump_path` 保持为扩展顶层属性。

必填配置：

- `url`：实时转写 WebSocket 地址，格式为 `ws(s)://host:port/tuling/ast/v3`
- `biz_id`：讯飞业务 ID，可通过环境变量 `IFLYTEK_BIZ_ID` 注入

常用可选配置：

- `app_id`：应用系统 ID
- `sample_rate`：输入 PCM 采样率，默认 `16000`
- `language`：识别语种，默认 `zh-CN`；多语种使用 `|` 分隔，例如 `zh-CN|en-US`
- `engine`：讯飞引擎透传参数。`language` 会自动写入 `wrec_param_language_name`
- `res_id_list`：额外用户热词资源 ID 列表
- `hotwords`：当前请求的文本热词
- `hotword_weight`：热词权重，范围 `1.0` 到 `4.0`
- `voiceprints`：声纹 ID 到 Base64 声纹数据的映射
- `connect_timeout`：WebSocket 连接超时秒数，默认 `10`
- `finalize_timeout`：等待终止响应的超时秒数，默认 `5`
- `reconnect_delay`：重连指数退避的初始延迟秒数，默认 `0.5`
- `reconnect_max_delay`：单次重连的最大延迟秒数，默认 `8`
- `reconnect_max_attempts`：意外断连后的最大重连次数，默认 `5`
- `buffer_max_bytes`：断连时保持的音频缓冲上限，默认 `10485760`（10 MB）
- `dump`：是否将已发送的 PCM 音频写入文件，默认 `false`
- `dump_path`：Dump 目录或 `.pcm` 文件路径，默认使用系统临时目录

初次连接失败和连接建立后的意外断连都会上报 NON_FATAL。扩展会按
`reconnect_delay * 2^n` 重试，并受 `reconnect_max_delay` 和
`reconnect_max_attempts` 限制；达到上限后上报 FATAL。重连成功后重试计数归零。

示例：

```json
{
  "params": {
    "url": "wss://asr.example.com/tuling/ast/v3",
    "app_id": "app-1",
    "biz_id": "tenant-1",
    "sample_rate": 16000,
    "language": "zh|en",
    "engine": {
      "wfep_param_nOnlineSpkdia_on": "2"
    },
    "res_id_list": ["tenant-2"],
    "hotwords": "zh-科大讯飞;en-Agora",
    "hotword_weight": 4.0,
    "voiceprints": {
      "10001": "Base64 encoded voiceprint"
    },
    "finalize_timeout": 5.0,
    "reconnect_delay": 0.5,
    "reconnect_max_delay": 8.0,
    "reconnect_max_attempts": 5,
    "buffer_max_bytes": 10485760
  },
  "dump": false,
  "dump_path": "/tmp"
}
```

也可以通过环境变量设置连接信息：

```bash
export IFLYTEK_ASR_URL="wss://asr.example.com/tuling/ast/v3"
export IFLYTEK_APP_ID="app-1"
export IFLYTEK_BIZ_ID="tenant-1"
```

## 音频与结果

输入音频应为单声道、16 位 PCM，采样率必须与 `sample_rate` 一致。协议建议单次发送约 4096 字节，至少覆盖 40 ms 音频；扩展拒绝超过 16 KiB 的单帧。

启用 `dump` 后，扩展只记录已成功发送给讯飞的音频。若 `dump_path` 是目录，
文件名为 `iflytek_asr_in.pcm`；Dump 失败会作为 NON_FATAL 错误上报，不影响
已成功发送音频的处理结果。使用系统共享临时目录时，扩展会先创建权限为
`0700` 的唯一 `iflytek_asr_*` 子目录，避免并发实例覆盖文件。生产环境启用前
请评估音频数据的隐私和磁盘空间。

结果中的 `bg`、`ed` 直接映射到 `start_ms` 和 `duration_ms`；词级 `wb`、`we` 乘以 10 后映射为毫秒。讯飞会话 ID、跟踪 ID、说话人映射等保存在 `metadata.asr_info`，TEN 的 `session_id` 保留在 `metadata.session_id`。

## 开发与测试

在扩展目录执行：

```bash
PYTHONPATH=.ten/app/ten_packages/system/ten_runtime_python/lib:.ten/app/ten_packages/system/ten_runtime_python/interface:.ten/app/ten_packages/system/ten_ai_base/interface:.ten/app \
  .python_venv/bin/python -m pytest tests/
```

离线测试包含本地 WebSocket 传输，不需要真实讯飞服务。发布前还必须运行官方 ASR Guarder 默认套件和单独的 5 分钟长时用例；不能把 skipped 或 deselected 计为通过。详细门禁见 `PRODUCTION_READINESS.md`。

## 参考资料

- [TEN ASR Extension 开发指南](https://theten.ai/cn/docs/ten_agent_examples/extension_dev/create_asr_extension)
- 工作区文档：`docs/实时转写接口文档v3-4.0.0.2004.md`

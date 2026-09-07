# 讯飞 ASR Python Extension

`iflytek_asr_python` 是一个 TEN Framework ASR Extension，通过 WebSocket
接入讯飞实时转写服务，将 TEN `AudioFrame` 转换为讯飞实时转写协议请求，并将
供应商响应转换为 TEN 标准 `ASRResult`、错误和指标消息。

当前实现覆盖官方指南的 Basic 与 Advanced 自动化测试范围，包括有限指数退避
重连、带超时保护且只完成一次的 finalize、错误分级、连接状态、分类日志、配置
与异常脱敏、断连音频缓冲、连接延迟指标和可选 PCM Dump。

## 实现状态

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| 讯飞 WebSocket 协议 | 已实现 | 支持首帧 `0`、中间帧 `1`、尾帧 `2` |
| PCM 音频发送 | 已实现 | 单声道 16-bit PCM，音频内容使用 Base64 编码 |
| 中间及最终结果 | 已实现 | 输出 TEN 标准 `ASRResult` |
| 词级时间轴 | 已实现 | 讯飞 `wb`、`we` 以 10 ms 为单位转换 |
| 说话人及声纹元数据 | 已实现 | 写入 `metadata.asr_info` |
| 热词及多用户资源 | 已实现 | 支持请求热词、资源 ID 和声纹库 |
| 自动重连 | 已实现 | 有限次数、指数退避、最大延迟、成功复位 |
| 错误分类 | 已实现 | FATAL/NON_FATAL，保留供应商错误信息 |
| 可观测性 | 已实现 | 分类日志、脱敏配置摘要、连接延迟及基类 ASR 指标 |
| 断连缓冲 | 已实现 | 默认保留最近 10 MB 音频 |
| PCM Dump | 已实现 | 可选记录已经成功发送的 PCM 音频 |
| Basic finalize | 已实现 | 发送尾帧并等待终止响应 |
| Advanced finalize | 已实现 | 等待终止响应、超时兜底、竞态下只发送一次完成事件 |
| 连接状态 | 已实现 | 输出 connecting/connected/disconnected 及重连状态转换 |
| 讯飞真实环境自动化测试 | 已验证 | 官方 Guarder 可执行用例和 5 分钟长时用例通过；2 项上游 allowlist 用例按官方逻辑跳过 |

## 数据流

```mermaid
flowchart LR
    A["TEN AudioFrame"] --> B["ASR Base 缓冲与会话管理"]
    B --> C["讯飞协议编码"]
    C --> D["WebSocket 实时转写服务"]
    D --> E["响应解析与错误映射"]
    E --> F["TEN ASRResult / error / metrics"]
```

关键实现文件：

| 文件 | 职责 |
| --- | --- |
| `extension.py` | TEN 生命周期、音频发送、结果输出、重连、错误、指标和 Dump |
| `client.py` | WebSocket 连接、并发发送、接收循环和连接状态 |
| `protocol.py` | 讯飞请求构造、响应解析、时间轴及元数据映射 |
| `config.py` | 配置模型、校验、引擎参数和日志脱敏 |
| `reconnect_manager.py` | 有限指数退避策略及计数器管理 |
| `manifest.json` | TEN Extension 元数据、依赖和属性 schema |
| `property.json` | 本地默认属性及环境变量入口 |
| `tests/` | 协议、客户端、扩展、配置和重连的离线测试 |

## 环境要求

| 组件 | 要求 |
| --- | --- |
| Python | `>= 3.10`，当前验证版本为 `3.10.20` |
| tman / TEN Framework | 当前验证版本为 `0.11.71` |
| `ten_runtime_python` | `0.11.71` |
| `ten_ai_base` | `0.7` |
| `websockets` | `>=14.0`，当前验证版本为 `14.2` |
| Pydantic | `>=2.13.4,<3.0`，当前验证版本为 `2.13.4` |
| pytest | 用于离线测试 |

## 快速开始

从 workspace 根目录进入扩展：

```bash
cd ten-framework/ai_agents/agents/ten_packages/extension/iflytek_asr_python
```

首次搭建环境：

```bash
python3.10 -m venv .python_venv
source .python_venv/bin/activate

tman install --standalone

python -m pip install --upgrade pip
python -m pip install \
  -r requirements.txt \
  -r .ten/app/ten_packages/system/ten_runtime_python/requirements.txt \
  -r .ten/app/ten_packages/system/ten_ai_base/requirements.txt \
  "pytest>=8.4,<9.0" "black>=26.3.1,<27.0"
```

运行完整离线测试：

```bash
tman run test -- -q
```

当前离线基线为 `88 passed`。这些测试不访问真实讯飞服务，也不需要业务凭据。

## 配置

TEN 从 `property.json` 读取扩展属性。0.2.0 起，供应商及连接参数统一放在
`params` 对象中，不再接受 0.1.0 的顶层参数。`dump` 和 `dump_path` 保持为
扩展顶层属性。连接信息默认支持通过环境变量注入：

```bash
export IFLYTEK_ASR_URL="wss://asr.example.com/tuling/ast/v3"
export IFLYTEK_APP_ID="app-system-id"
export IFLYTEK_BIZ_ID="business-id"
```

不要把真实凭据提交到 Git。生产环境应使用 Secret Manager、部署平台变量或其他
受控的配置注入机制，并优先使用 `wss://`。

### 配置项

| 配置项 | 必填 | 默认值 | 约束及用途 |
| --- | --- | --- | --- |
| `url` | 是 | `ws://127.0.0.1:9990/tuling/ast/v3` | 讯飞 WebSocket 地址，只接受 `ws://` 或 `wss://` |
| `app_id` | 否 | 空 | 应用系统 ID；通过 `IFLYTEK_APP_ID` 注入 |
| `biz_id` | 是 | 空 | 讯飞业务 ID；空值会导致初始化失败 |
| `trace_id_prefix` | 否 | `ten` | 每次连接的随机跟踪 ID 前缀，不能为空 |
| `sample_rate` | 否 | `16000` | 输入 PCM 采样率，必须大于 `0` |
| `language` | 否 | `zh-CN` | 识别语种；多语种使用 `|` 分隔，例如 `zh-CN|en-US` |
| `engine` | 否 | `{}` | 讯飞引擎透传参数，值必须是字符串 |
| `res_id_list` | 否 | `[]` | 多用户热词等额外资源 ID 列表 |
| `hotwords` | 否 | 空 | 当前请求的文本热词 |
| `hotword_weight` | 否 | `1.0` | 热词权重，范围 `1.0` 到 `4.0` |
| `voiceprints` | 否 | `{}` | 声纹 ID 到 Base64 声纹数据的映射 |
| `connect_timeout` | 否 | `10.0` | WebSocket 建连超时秒数，必须大于 `0` |
| `finalize_timeout` | 否 | `5.0` | 等待讯飞终止响应的超时秒数，范围 `(0,60]` |
| `reconnect_delay` | 否 | `0.5` | 指数退避初始延迟秒数，不能小于 `0` |
| `reconnect_max_delay` | 否 | `8.0` | 单次重连最大延迟，必须不小于 `reconnect_delay` |
| `reconnect_max_attempts` | 否 | `5` | 意外断连后的最大重试次数，至少为 `1` |
| `buffer_max_bytes` | 否 | `10485760` | 断连时保留的最近音频字节上限，必须大于 `0` |
| `dump` | 否 | `false` | 是否把成功发送的 PCM 音频写入本地文件 |
| `dump_path` | 否 | 系统临时目录 | Dump 目录或以 `.pcm` 结尾的文件路径 |

除 `dump` 和 `dump_path` 外，表中配置项均位于 `params` 对象内。
`language` 会在 `engine` 未显式设置时自动写入
`wrec_param_language_name`。未知配置项会被忽略，以兼容 TEN 图中的共享属性。

### 配置示例

```json
{
  "params": {
    "url": "${env:IFLYTEK_ASR_URL|wss://asr.example.com/tuling/ast/v3}",
    "app_id": "${env:IFLYTEK_APP_ID|}",
    "biz_id": "${env:IFLYTEK_BIZ_ID|}",
    "trace_id_prefix": "ten",
    "sample_rate": 16000,
    "language": "zh|en",
    "engine": {
      "wfep_param_nOnlineSpkdia_on": "2"
    },
    "res_id_list": [],
    "hotwords": "zh-科大讯飞;en-Agora",
    "hotword_weight": 4.0,
    "voiceprints": {},
    "connect_timeout": 10.0,
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

## 音频输入约束

输入应满足以下要求：

- 单声道 PCM。
- 每个采样点 16 bit，即 2 bytes。
- 实际采样率必须与 `sample_rate` 一致。
- 讯飞协议建议每次约 4096 bytes，至少包含 40 ms 音频。
- 单次发送原则上不超过 16 KB。

扩展会锁定 TEN `AudioFrame` 缓冲区、复制字节并立即解锁，避免在异步发送期间
长期持有运行时缓冲区。超过 16 KiB 的单帧会被拒绝；音频仅在 WebSocket 发送
成功后计入音频时间轴和 Dump。

## 协议和结果映射

### 请求

- 首个音频帧使用 `status=0`，携带引擎、资源、热词和声纹参数。
- 后续音频帧使用 `status=1`，只发送必要的请求头和音频。
- Basic finalize 使用 `status=2`，并按讯飞协议发送两个零字节。
- 所有音频都编码为 Base64 后放入 `payload.audio.audio`。
- 每次新连接生成独立的 `traceId`。

### 响应

| 讯飞字段 | TEN 输出 |
| --- | --- |
| `payload.result.ws[].cw[].w` | `ASRResult.text` 和 `words[].word` |
| `bg` | `start_ms` |
| `ed - bg` | `duration_ms` |
| `wb * 10` | `words[].start_ms` |
| `(we - wb) * 10` | `words[].duration_ms` |
| `ls`、`msgtype`、终止状态 | `final` |
| `sid`、`traceId`、`segId`、`sn` | `metadata.asr_info` |
| `nameMapping`、说话人事件 | `metadata.asr_info` |
| `tmpSwk` 的 Key | `metadata.asr_info.temporary_voiceprint_ids` |

TEN 上游提供的 `metadata.session_id` 会被保留，不会被讯飞 `sid` 覆盖。

## 重连和缓冲策略

初次连接失败和连接成功后的意外断连都会上报 NON_FATAL，并使用以下退避策略：

```text
delay = min(reconnect_delay * 2^attempt, reconnect_max_delay)
```

默认最多尝试 5 次，延迟依次为 `0.5s`、`1s`、`2s`、`4s`、`8s`：

- 中间重连失败上报 NON_FATAL。
- 最后一次失败上报 FATAL，并停止继续重连。
- 重连成功后尝试计数归零。
- Extension 停止时会取消正在等待的重连任务并关闭 WebSocket。

断连期间 TEN ASR 基类保留最近 `buffer_max_bytes` 音频；超过限制时优先丢弃最旧
帧。连接恢复后先发送缓冲帧，再发送当前帧。10 MB 的默认值约等于 16 kHz、
单声道、16-bit PCM 的 327 秒音频，生产环境应根据允许的内存占用和可接受的
延迟调整，而不是盲目增大。

## 错误处理

所有错误通过 TEN ASR `error` 数据输出，并包含 `ModuleErrorVendorInfo`：

```json
{
  "module": "asr",
  "code": 1000,
  "message": "vendor or client error",
  "vendor_info": {
    "vendor": "iflytek",
    "code": "vendor-code",
    "message": "vendor or client error"
  }
}
```

| 场景 | 分类 | TEN code |
| --- | --- | --- |
| 无效配置或初始化失败 | FATAL | `-1000` |
| 初次 WebSocket 连接失败 | NON_FATAL | `1000` |
| 运行中客户端或协议错误 | NON_FATAL | `1000` |
| 音频发送失败 | NON_FATAL | `1000` |
| 中间重连失败 | NON_FATAL | `1000` |
| 重连次数耗尽 | FATAL | `-1000` |
| Dump 写入失败 | NON_FATAL | `1000` |

讯飞非零响应码会保留原始 `code` 和消息。无法归类的客户端异常使用
`client_error` 作为供应商错误码。

## 日志、指标和隐私

日志使用 TEN 分类：

- `key_point`：初始化配置摘要、Dump 和指标异常等关键事件。
- `vendor`：讯飞连接、重连、响应和客户端错误。

配置摘要会移除 URL 用户信息、密码和 query，只记录 `app_id`、`biz_id`、热词、
声纹是否存在或数量，以及引擎参数名称，不记录引擎参数值。外部异常会折叠控制
字符、限制为 2 KiB，并脱敏 URL 凭据、业务标识、资源 ID、热词、引擎值和声纹
数据。结果日志只记录字符数，不记录完整转写文本。

扩展会发送连接延迟指标；TEN ASR 基类还负责 TTFW、TTLW 和实际发送音频等
通用指标。指标发送失败只记录警告，不中断识别。

## PCM Dump

设置 `dump=true` 后启用：

- `dump_path` 以 `.pcm` 结尾时，直接作为输出文件。
- 其他路径视为目录，输出文件为 `iflytek_asr_in.pcm`。
- 使用系统共享临时目录时，会先创建权限为 `0700` 的唯一
  `iflytek_asr_*` 子目录，避免不同进程覆盖同一文件。
- 文件以覆盖模式打开，每次 Extension 初始化会重新创建。
- 只写入已经成功发送给讯飞的 PCM 字节。
- 运行时写入失败上报 NON_FATAL，不改变已成功发送音频的返回值。

PCM 文件包含原始用户音频，可能属于敏感数据。生产环境启用前必须定义访问控制、
保存期限、磁盘配额和安全删除策略。默认应保持 `dump=false`。

## 测试

### 完整离线测试

```bash
tman run test -- -q
```

也可以直接使用测试脚本：

```bash
./tests/bin/start -q
```

### 按模块测试

```bash
./tests/bin/start tests/test_config.py -q
./tests/bin/start tests/test_protocol.py -q
./tests/bin/start tests/test_client.py -q
./tests/bin/start tests/test_reconnect_manager.py -q
./tests/bin/start tests/test_extension.py -q
```

离线测试覆盖：

- 配置校验、语言引擎参数和敏感信息脱敏。
- 首帧、中间帧、尾帧及 Base64 音频编码。
- 中间、最终、无结果和供应商错误响应解析。
- 词时间轴、会话、跟踪、说话人和声纹元数据。
- 使用本地 WebSocket Server 的真实 `websockets` 传输路径。
- TEN `ASRResult`、错误和连接延迟指标输出。
- 10 MB 缓冲策略和 PCM Dump 字节一致性。
- 指数退避、重试上限、NON_FATAL/FATAL 和成功复位。
- 初次连接失败重试、连接状态转换、异常脱敏和元数据并发更新。
- 非法响应状态、错误类型和 16 KiB 音频帧上限。

本地 WebSocket 测试只验证传输实现，不等同于真实讯飞服务验收。

### 官方 ASR Guarder

真实服务验证需要设置环境变量，再从 `ai_agents` 目录运行：

```bash
export IFLYTEK_ASR_URL="wss://asr.example.com/tuling/ast/v3"
export IFLYTEK_APP_ID="app-system-id"
export IFLYTEK_BIZ_ID="business-id"

task asr-guarder-test \
  EXTENSION=iflytek_asr_python \
  CONFIG_DIR=tests/configs
```

官方启动脚本默认排除约 5 分钟的 `test_long_duration_stream`，发布验收必须再单独
运行该用例，不能把 deselected 计为通过。2026-08-04 的真实服务验收结果为：

- Guarder 默认套件：`10 passed, 2 skipped, 1 deselected in 154.43s`；2 项
  connection-status 用例因官方 allowlist 尚未包含本扩展而按原始 UT 跳过，
  deselected 项为单独执行的长时用例。
- 长时稳定性：`1 passed, 12 deselected in 313.09s`，业务持续 `311.4s`，
  返回 469 条结果、58 条 final 结果。
- 未出现 409/max-duration 错误。

### 质量检查

```bash
tman check manifest-json --path manifest.json
tman check property-json --path property.json

.python_venv/bin/python -m black --check --line-length 80 \
  --target-version py310 \
  config.py protocol.py client.py reconnect_manager.py extension.py tests

.python_venv/bin/python -m compileall -q \
  config.py protocol.py client.py reconnect_manager.py extension.py tests

.python_venv/bin/pyright -p pyrightconfig.json

PYTHONPATH=.ten/app/ten_packages/system/ten_runtime_python/lib:.ten/app/ten_packages/system/ten_runtime_python/interface:.ten/app/ten_packages/system/ten_ai_base/interface:.ten/app \
  .python_venv/bin/pylint --disable=all --enable=E,F \
  --disable=no-member,access-member-before-definition \
  addon.py config.py protocol.py client.py reconnect_manager.py extension.py
```

### 打包检查

```bash
tman package --output-path /tmp/iflytek_asr_python.tpkg
tar -tzf /tmp/iflytek_asr_python.tpkg
```

检查产物不应包含 `.python_venv`、`.ten`、`__pycache__`、`.pytest_cache` 或本地
凭据文件。

## 真实讯飞联调

真实联调需要：

- 可访问的讯飞 WebSocket 地址。
- 有效 `biz_id`，以及服务端要求时提供的 `app_id`、资源 ID 或声纹数据。
- 符合采样率、声道数和位宽要求的实时 PCM 音频源。
- 包含本 Extension 的 TEN Agent 图或测试应用。

建议按以下顺序验收：

1. 使用 `wss://` 建立连接，确认收到 `connect_delay` 指标。
2. 发送固定 PCM 样本，核对中间结果、最终结果和词级时间轴。
3. 核对 `metadata.session_id` 与 `metadata.asr_info.sid/trace_id`。
4. 主动中断网络，验证指数退避、音频缓冲和恢复后的发送顺序。
5. 使用无效业务 ID 验证讯飞错误码和 FATAL/NON_FATAL 分类。
6. 在受控环境短时启用 Dump，核对 PCM 字节后立即关闭并删除测试数据。

发布前仍应在目标生产网络、目标凭据和目标音频链路上重复上述验收；历史 Guarder
结果不能代替环境特定验证。

## 常见问题

| 现象 | 检查项 |
| --- | --- |
| 初始化立即 FATAL | 确认 `biz_id` 非空、URL 使用 `ws://` 或 `wss://`、重连最大延迟不小于初始延迟 |
| `ModuleNotFoundError: ten_runtime` | 执行 `tman install --standalone`，并使用 `tests/bin/start` 提供的 `PYTHONPATH` |
| WebSocket 连接超时 | 检查 DNS、端口、防火墙、TLS 证书和 `connect_timeout` |
| 已连接但无转写结果 | 核对 PCM 是否为单声道 16-bit、采样率是否匹配、是否持续发送有效音频 |
| 热词或声纹无效 | 确认参数只放在首帧，并核对讯飞资源 ID、Base64 数据和权重范围 |
| 持续收到重连错误 | 查看 `vendor` 分类日志；达到上限后需修复外部连接并重启 Extension |
| Dump 文件不存在 | 确认 `dump=true`、目录可写，并检查 `key_point` 日志和 TEN `error` 数据 |
| Dump 文件为空 | 只有成功发送到 WebSocket 的音频才会写入文件 |

## 开发约定

- Python 代码使用 Black，行宽为 80。
- 修改协议时必须同时更新 `protocol.py` 和对应测试。
- 新增配置时同步更新 `config.py`、`manifest.json`、`property.json` 和文档。
- 不在日志、测试夹具、property 或提交记录中写入真实凭据和用户音频。
- 重连、错误分类、缓冲等共享行为应先增加失败测试，再修改实现。
- 修改 `finalize` 时必须同时验证正常终止、超时、连接提前关闭和完成竞态。

## 参考资料

- [TEN ASR Extension 开发完整指南](https://theten.ai/cn/docs/ten_agent_examples/extension_dev/create_asr_extension)
- [websockets 14.2 asyncio client API](https://websockets.readthedocs.io/en/14.2/reference/asyncio/client.html)
- [Pydantic 2.13 配置文档](https://docs.pydantic.dev/2.13/api/config/)
- [生产就绪与上线清单](docs/PRODUCTION_READINESS.md)
- [项目内中文使用说明](docs/README.zh-CN.md)
- [讯飞实时转写接口文档（workspace）](../../../../../../docs/实时转写接口文档v3-4.0.0.2004.md)

许可证遵循 TEN Framework 仓库根目录的 `LICENSE`。

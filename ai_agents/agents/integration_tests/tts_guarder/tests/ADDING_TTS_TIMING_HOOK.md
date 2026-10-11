# 新增 TTS 字幕时间测试

更新日期：2026-10-11

本文说明如何让一个新的 TTS extension 接入 `test_subtitle_alignment.py`。
现有校验规则和观察边界见 [SUBTITLE_TIMING.md](SUBTITLE_TIMING.md)。

## 先确定要验证什么

| 接入方式 | 能验证什么 | 需要修改什么 |
| --- | --- | --- |
| 仅通用检查 | request 内音频采样时钟、字幕范围、metadata 和结束状态 | 支持名单、字幕配置 |
| 通用检查 + vendor hook | 上述检查，以及 TEN 是否保留供应商的原始词时间，包括首字偏移 | 再增加一个 vendor 文件和 registry 注册项 |

未注册 hook 的 extension 不会安装任何 vendor observer。仅通用检查不能证明
首字偏移换算正确；即使字幕落在音频范围内，也可能整体提前。

当前仅 MiniMax Duplex 注册了 hook。Cartesia 运行通用检查；其他 extension
默认跳过字幕对齐用例，直到加入支持名单并准备配置。

## 1. 准备 extension 和配置

- 确认 extension 已能通过 TEN standalone runner 加载，并能产生带词时间的字幕。
- 按 extension 自己的文档准备有效的模型、音色和凭证；凭证使用环境变量。
- 在 extension 的 `tests/configs/` 中准备 `property_subtitle_alignment.json`，
  启用供应商的词时间输出。具体字段由 vendor 协议决定。
- 将 extension 名加入
  [test_subtitle_alignment.py](test_subtitle_alignment.py) 的
  `SUPPORTED_TTS_EXTENSIONS`。

用例顺序发送两个 request，每次输入都带有 `request_id`、`session_id` 和
`turn_id`。它从 TEN 公共回调观察字幕、音频帧以及 `tts_audio_start/end`，
并等待字幕结束标记和音频结束事件都到达。extension 必须支持这些公共输出。

正常 `task tts-guarder-test` 从
`ai_agents/agents/ten_packages/extension/<extension_name>/` 安装目标扩展。
若扩展来自其他仓库，先准备对应源码、配置和可运行的 Guarder app，明确记录
来源版本；只注册 hook 不会自动安装生产 extension。当前 Framework checkout
不包含 `minimax_tts_websocket_duplex`，此前 MiniMax 验证使用另行准备的 Engine 扩展。

## 2. 在一个 vendor 文件中实现采集和计算

需要原始词时间对照时，在 `timing_hooks/` 下增加一个文件，例如
`acme_tts_duplex.py`。该文件同时包含原始事实采集和参考时间计算，不再建立
独立的 calculator 包。可以参考
[minimax_duplex.py](timing_hooks/minimax_duplex.py) 的结构。

registry 对 vendor 对象的调用约定如下：

| 方法 | 调用时机 | 必须完成的事情 |
| --- | --- | --- |
| `install(monkeypatch, config)` | TEN tester 启动前 | 仅注入目标客户端的传输依赖；使用传入的 scoped monkeypatch |
| `begin_request(request_id)` | 每次发送 TEN 输入前 | 建立当前 request 身份，重置音频累计位置和字幕采集状态 |
| `reference(request_id)` | 当前 request 的音频和字幕都结束后 | 返回公共 `RequestTimingReference`；检查参考数据属于该 request |

采集回调只记录计算所需事实：实际生效的音频格式、原始词时间和句子音频起点。
如果词时间是句内相对时间，必须累计前面所有音频包，包括没有字幕的包。
连接级音频配置可能在第一个 request 之前收到，request 重置时应保留仍生效的配置。

`reference()` 再根据 vendor 协议处理单位、分句、重复词标记或空格标记，返回
[base.py](timing_hooks/base.py) 定义的数据：

| 字段 | 含义 |
| --- | --- |
| `vendor` | 用于诊断的供应商名称 |
| `sample_rate`、`channels` | 实际音频采样率和声道数 |
| `pcm_bytes` | 当前 request 的 PCM16 总字节数 |
| `captions` | 按字幕结果顺序分组的 `ReferenceWord` 元组 |
| `ReferenceWord.word` | 与公开 TEN 字幕对应的词文本 |
| `ReferenceWord.start_ms/end_ms` | 相对当前 request 音频起点的时间，使用 `Fraction` 保留小数 |
| `error` | 无法采集或计算时的诊断；正常情况下为 `None` |

公共比较器要求参考音频与 TEN 输出使用相同的 PCM16 采样率和声道数。供应商若
返回压缩音频、不同采样率或其他采样格式，必须先定义参考数据如何对应 TEN 输出；
不能直接拿传输字节数代替 PCM16 字节数。

例如，第一句有 3200 字节的 16kHz、单声道 PCM16，时长为 100ms。
第二句首词的供应商偏移为 42.667ms，则该词的 request 相对起点为
`100 + 42.667 = 142.667ms`。TEN 首帧 PTS 若为 1000ms，期望词 PTS 为
`1000 + floor(142.667) = 1142ms`。第一个词的原始偏移也必须保留，不能归零。
第二个 request 应重新从自己的首帧建立起点。

## 3. 限定 hook 的观察范围

- 观察供应商传输边界的原始消息和 TEN 公共输出，不读取生产 extension 的私有状态。
- 只替换目标客户端模块的依赖绑定，不修改第三方库共享的全局方法。
- 按客户端实际配置优先级确定目标 endpoint，包括顶层和 `params` 中的配置别名。
- 保持原始收发内容和连接行为，采集异常交给参考结果报告，避免改变生产收发路径。
- 使用 registry 提供的 monkeypatch 上下文，使成功、失败时都能恢复依赖。

使用 WebSocket 的 vendor 可以复用
[ObservedWebSockets](timing_hooks/transport.py)。连接库须支持
`create_connection`；它只为匹配 endpoint 的连接创建专用连接类型。
复用这个代理时，vendor 对象还需提供 `observe_send(payload)` 和
`observe_receive(payload)`，由代理调用它们记录原始收发事实。注入位置应按
extension 实际使用的连接入口选择，不机械复制 MiniMax 的模块依赖名称。
使用其他传输方式的 vendor 在自己的文件内实现等价的局部注入。
同一 extension 的用例串行运行；并行验证使用独立进程和独立安装目录。

## 4. 注册 vendor 对象

在 [registry.py](timing_hooks/registry.py) 的 `HOOK_FACTORIES` 中增加：

```python
"acme_tts_duplex": (".acme_tts_duplex", "AcmeTimingHook"),
```

键必须与传给 Guarder 的 extension 名完全一致。registry 按需导入模块，
每次创建新对象，安装后直接交给公共用例。无需修改公共比较器，也无需注册
单独的计算器。没有原始参考能力时不加注册项，保留无 hook 的通用检查路径。

## 5. 运行和核对结果

从 `ai_agents/` 运行字幕用例，确认测试实际执行，不能把 skip 当作通过：

```bash
task tts-guarder-test EXTENSION=acme_tts_duplex CONFIG_DIR=tests/configs -- \
  --enable_subtitle_alignment=True -k subtitle_alignment -s -vv
```

接入完成后运行该 extension 的完整 Guarder：

```bash
task tts-guarder-test EXTENSION=acme_tts_duplex CONFIG_DIR=tests/configs -- \
  --enable_subtitle_alignment=True -s -vv
```

关闭开关、不在支持名单或缺少字幕配置都会跳过字幕用例。已注册 hook 后，
未采集到有效原始参考应报失败，不能悄悄退回仅通用检查。

至少核对：两个 request 的参考身份和采样位置分别重置；非零首字偏移被保留；
错误偏移能够被拒绝；成功和失败退出后依赖恢复；未注册 extension 无注入。
用公共 TEN/传输边界构造或观察这些场景，无需访问 extension 私有字段。
记录 Guarder 和生产 extension 的版本、运行命令、通过/失败/跳过数量及使用的
验证环境适配。日志和配置脱敏后再分享。

## 当前验证边界

这些检查验证时间戳换算，不做声学强制对齐，不能证明供应商标注与真实发声完全一致。
当前 review 发现的实际 buffer 长度核对、空 `words` 的非结束字幕漏检，以及
MiniMax `params.url` 匹配问题仍待修复；本文的接入步骤不表示这些缺口已修复。
新增 vendor 应按实际协议实现配置解析，不直接照搬 MiniMax 当前的 URL 取值逻辑。

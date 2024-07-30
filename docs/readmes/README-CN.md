![ASTRA Banner Image](https://github.com/rte-design/ASTRA.ai/raw/main/images/banner-image-without-tagline.png)

<div align="center">

[![Follow on X](https://img.shields.io/twitter/follow/AstraFramework?logo=X&color=%20%23f5f5f5)](https://twitter.com/intent/follow?screen_name=AstraFramework)
[![Discussion posts](https://img.shields.io/github/discussions/rte-design/astra.ai?labelColor=%20%23FDB062&color=%20%23f79009)](https://github.com/rte-design/astra.ai/discussions/)
[![Commits](https://img.shields.io/github/commit-activity/m/rte-design/astra.ai?labelColor=%20%237d89b0&color=%20%235d6b98)](https://github.com/rte-design/astra.ai/graphs/commit-activity)
[![Issues closed](https://img.shields.io/github/issues-search?query=repo%3Arte-design%2Fastra.ai%20is%3Aclosed&label=issues%20closed&labelColor=green&color=green)](https://github.com/rte-design/ASTRA.ai/issues)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](https://github.com/rte-design/ASTRA.ai/pulls)
[![GitHub license](https://img.shields.io/badge/License-Apache_2.0-blue.svg?labelColor=%20%239b8afb&color=%20%237a5af8)](https://github.com/rte-design/ASTRA.ai/blob/main/LICENSE)
[![WeChat](https://img.shields.io/badge/WeChat-WeChat_Group-%2307C160?logo=wechat)](https://github.com/rte-design/ASTRA.ai/issues/125)

[![Discord](https://dcbadge.vercel.app/api/server/VnPftUzAMJ)](https://discord.gg/VnPftUzAMJ)

[![GitHub watchers](https://img.shields.io/github/watchers/rte-design/astra.ai?style=social&label=Watch)](https://GitHub.com/rte-design/astra.ai/watchers/?WT.mc_id=academic-105485-koreyst)
[![GitHub forks](https://img.shields.io/github/forks/rte-design/astra.ai?style=social&label=Fork)](https://GitHub.com/rte-design/astra.ai/network/?WT.mc_id=academic-105485-koreyst)
[![GitHub stars](https://img.shields.io/github/stars/rte-design/astra.ai?style=social&label=Star)](https://GitHub.com/rte-design/astra.ai/stargazers/?WT.mc_id=academic-105485-koreyst)

<a href="../../README.md"><img alt="README in English" src="https://img.shields.io/badge/English-lightgrey"></a>
<a href="../readmes/README-CN.md"><img alt="简体中文" src="https://img.shields.io/badge/简体中文-lightgrey"></a>
</div>

<div align="center">

[低延迟](./docs/astra-architecture.md)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[多模态](./docs/astra-architecture.md#astra-extension)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[高可配](./docs/astra-architecture.md#-astra-extension-store)

</div>

## 项目示例 - The voice agent

[示例项目](https://theastra.ai)是通过 ASTRA 搭建出来的 voice agent, 展示了多模态，低延迟的能力。

[![展示ASTRA语音助手](https://github.com/rte-design/ASTRA.ai/raw/main/images/astra-voice-agent.gif)](https://theastra.ai)

<br>
<h2>如何在本地搭建 voice agent</h2>

#### 先决条件

- Agora App ID 和 App Certificate（[点击此处了解详情](https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web)）
- Azure 的 [STT](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) 和 [TTS](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) API 密钥
- [OpenAI](https://openai.com/index/openai-api/) API 密钥
- [Docker](https://www.docker.com/)

#### Apple Silicon 上的 Docker 设置
如果您使用的是 Apple Silicon，您需要取消勾选 Docker 的 "Use Rosetta for x86_64/amd64 emulation on apple silicon" 选项，否则服务器将无法正常工作。

<div align="center">

![ASTRA Docker Setting](https://github.com/rte-design/ASTRA.ai/raw/main/images/docker-setting.gif)

</div>

#### 设置 Go 国内代理
如果在国内，我们建议跑下列命令来全局设定国内代理以便快速下载依赖([了解详情](https://goproxy.cn/))。

```
$ go env -w GO111MODULE=on
$ go env -w GOPROXY=https://goproxy.cn,direct
```

#### 1.创建 manifest 配置文件
从示例文件创建 manifest：

```bash
cp ./agents/manifest.json.example ./agents/manifest.json
```

#### 2. 基本配置

在 manifest 里面找到下列属性替换：
```json
"app_id": "<agora_appid>"
"api_key": "<openai_api_key>"
"agora_asr_vendor_key": "<azure_stt_key>"
"agora_asr_vendor_region": "<azure_stt_region>"
"azure_subscription_key": "<azure_tts_key>"
"azure_subscription_region": "<azure_tts_region>"
```

#### 3. 定制化
在 manifest 可以直接改 propmt 和问候语：
```json
"property": {
    "base_url": "",
    "api_key": "<openai_api_key>",
    "frequency_penalty": 0.9,
    "model": "gpt-3.5-turbo",
    "max_tokens": 512,
    "prompt": "",
    "proxy_url": "",
    "greeting": "ASTRA agent connected. How can i help you today?",
    "max_memory_length": 10
}
```

#### 4. 在 Docker 镜像中构建 agent

打开 Terminal， 跑下列命令：

```bash
# 拉取带有开发工具的 Docker 镜像，并将当前文件夹挂载为工作区
docker run -itd -v $(pwd):/app -w /app -p 8080:8080 --name astra_agents_dev ghcr.io/rte-design/astra_agents_build

# 对于 Windows Git Bash
# docker run -itd -v //$(pwd):/app -w //app -p 8080:8080 --name astra_agents_dev ghcr.io/rte-design/astra_agents_build

# 进入 Docker 容器
docker exec -it astra_agents_dev bash

# 在容器里构建 agent
make build
```

#### 5. 启动本地服务器


```bash
# Agent is ready to start on port 8080
make run-server
```

#### 6. 运行 voice agent 界面

voice agent 界面是基于 NextJS 14 构建的，因此需要 Node 18 或更高版本。

```bash
# 创建一个本地的环境文件
cd playground
cp .env.example .env

# 安装依赖
npm install && npm run dev
```

#### 7. 验证您定制的 voice agent 🎉

在浏览器中打开 `localhost:3000`，您应该能够看到一个与示例项目一样的 voice angent，但是这次是带有定制的 voice agent。

<br>
<h2>Voice agent 架构</h2>
要进一步探索， voice agent 是一个绝佳的起点。它包含以下扩展功能，其中一些将在不久的将来可以互换使用。请随意选择最适合您需求并最大化 ASTRA 功能的扩展。

| 扩展功能            | 特点           | 描述                                                                                                                                                                                                             |
| ------------------ | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| openai_chatgpt     | 语言模型            | [ GPT-4o ](https://platform.openai.com/docs/models/gpt-4o), [ GPT-4 Turbo ](https://platform.openai.com/docs/models/gpt-4-turbo-and-gpt-4), [ GPT-3.5 Turbo ](https://platform.openai.com/docs/models/gpt-3-5-turbo) |
| elevenlabs_tts     | 文本转语音 | [ElevanLabs 文本转语音](https://elevenlabs.io/) 将文本转换为音频                                                                                                                                              |
| azure_tts          | 文本转语音 | [Azure 文本转语音](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) 将文本转换为音频                                                                                                 |
| azure_stt          | 语音转文本 | [Azure 语音转文本](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) 将音频转换为文本                                                                                                 |
| chat_transcriber   | 转录工具    | 将聊天记录转发到频道的实用工具                                                                                                                                                                      |
| agora_rtc          | 传输工具    | 由 agora_rtc 提供支持的低延迟传输工具                                                                                                                                                                       |
| interrupt_detector | 中断工具    | 帮助中断语音助手的实用工具                                                                                                                                                                                |

<h3>Voice agent 架构图</h3>

![ASTRAvoice agent架构图](../../images/image-2.png)


<br>
<h2>ASTRA 服务</h2>

现在您已经创建了第一个 AI voice agent，创意并不会止步于此。 要开发更多的 AI agents， 您需要深入了解 ASTRA 的工作原理。请参阅 [ ASTRA 架构文档 ](./docs/astra-architecture.md)。

<br />
<h2>点星收藏</h2>

我们更新频繁，不想错过的话，请给我们的 repo 点星，以便获得第一时间的更新.

![ASTRA star us gif](https://github.com/rte-design/ASTRA.ai/raw/main/images/star-the-repo-confetti-higher-quality.gif)


<br>
<h2>加入社区</h2>

- [Discord](https://discord.gg/VnPftUzAMJ)：非常适合分享您的应用程序并与社区互动。
- [WeChat Group](https://github.com/rte-design/ASTRA.ai/issues/125): 如果喜欢用微信群的社区，欢迎加入。
- [Github Discussion](https://github.com/rte-design/astra.ai/discussions)：非常适合提供反馈和提问。
- [GitHub Issues](https://github.com/rte-design/astra.ai/issues)：最适合报告错误和提出新功能。有关更多详细信息，请参阅我们的[贡献指南](./docs/code-of-conduct/contributing.md)。
- [X（以前的Twitter）](https://twitter.com/intent/follow?screen_name=AstraFramework)：非常适合分享您的代理并与社区互动。

 <br>
 <h2>代码贡献者</h2>

[![ASTRA](https://contrib.rocks/image?repo=rte-design/astra.ai)](https://github.com/rte-design/astra.ai/graphs/contributors)


</br>

<h2>欢迎贡献</h2>

欢迎贡献！请先阅读 [贡献指南](../code-of-conduct/contributing.md)。

</br>

<h2>许可证授权</h2>

本项目使用 Apache 2.0 许可证授权 - 详细信息请参阅 [LICENSE](LICENSE)。

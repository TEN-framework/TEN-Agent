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

<a href="./README.md"><img alt="README in English" src="https://img.shields.io/badge/English-lightgrey"></a>
<a href="./docs/readmes/README-CN.md"><img alt="简体中文" src="https://img.shields.io/badge/简体中文-lightgrey"></a>
</div>

<div align="center">

[低延迟](./docs/astra-architecture.md)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[多模态](./docs/astra-architecture.md#astra-extension)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[高可配](./docs/astra-architecture.md#-astra-extension-store)

</div>

## 项目示例 - The voice agent

[示例项目](https://theastra.ai) 是通过 ASTRA 搭建出来的 voice agent, 展示了多模态，低延迟的能力。

[![展示ASTRA语音助手](https://github.com/rte-design/ASTRA.ai/raw/main/images/astra-voice-agent.gif)](https://theastra.ai)

<br>
<h2>如何在本地搭建 voice agent</h2>

#### 先决条件

- Agora App ID 和 App Certificate（[点击此处了解详情](https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web)）
- Azure 的 [语音转文本](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) 和 [文本转语音](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) API 密钥
- [OpenAI](https://openai.com/index/openai-api/) API 密钥
- [Docker](https://www.docker.com/)

#### Apple Silicon 上的 Docker 设置
如果您使用的是 Apple Silicon，您需要取消勾选 Docker 的 "Use Rosetta for x86_64/amd64 emulation on apple silicon" 选项，否则服务器将无法正常工作。

<div align="center">

![ASTRA Docker Setting](https://github.com/rte-design/ASTRA.ai/raw/main/images/docker-setting.gif)

</div>

#### 设置 Go 国内代理
如果在国内，我们建议跑下列命令来全局设定国内代理以便快速安装依赖([了解详情](https://goproxy.cn/))。

```
$ go env -w GO111MODULE=on
$ go env -w GOPROXY=https://goproxy.cn,direct
```

#### 1. 在 Docker 镜像中构建 agent

```bash
# 从示例文件创建 manifest
cp ./agents/manifest.json.example ./agents/manifest.json

# 拉取带有开发工具的 Docker 镜像，并将当前文件夹挂载为工作区
docker run -itd -v $(pwd):/app -w /app -p 8080:8080 --name astra_agents_dev ghcr.io/rte-design/astra_agents_build

# 对于 Windows Git Bash
# docker run -itd -v //$(pwd):/app -w //app -p 8080:8080 --name astra_agents_dev ghcr.io/rte-design/astra_agents_build

# 进入 Docker 镜像
docker exec -it astra_agents_dev bash

# 构建 agent
make build
```

#### 2. 改动 prompts
上述代码生成了一个代理可执行文件。要自定义提示和 OpenAI 参数，请修改 `agents/addon/extension/openai_chatgpt/openai_chatgpt.go` 中的以下代码：
```
func defaultOpenaiChatGPTConfig() openaiChatGPTConfig {
	return openaiChatGPTConfig{
		BaseUrl: "https://api.openai.com/v1",
		ApiKey:  "",
		Model:  openai.GPT4o,
		Prompt: "You are a voice assistant who talks in a conversational way and can chat with me like my friends. i will speak to you in english or chinese, and you will answer in the corrected and improved version of my text with the language i use. Don't talk like a robot, instead i would like you to talk like real human with emotions. i will use your answer for text-to-speech, so don't return me any meaningless characters. I want you to be helpful, when i'm asking you for advices, give me precise, practical and useful advices instead of being vague. When giving me list of options, express the options in a narrative way instead of bullet points.",
		FrequencyPenalty: 0.9,
		PresencePenalty:  0.9,
		TopP:             1.0,
		Temperature:      0.1,
		MaxTokens:        512,
		Seed:             rand.Int(),
		ProxyUrl: "",
	}
}
```

#### 3. 启动本地服务器

通过运行以下终端命令启动服务器：

```bash
# Agora App ID and Agora App Certificate
export AGORA_APP_ID=<your_agora_appid>
export AGORA_APP_CERTIFICATE=<your_agora_app_certificate>

# OpenAI API key
export OPENAI_API_KEY=<your_openai_api_key>

# Azure STT key and region
export AZURE_STT_KEY=<your_azure_stt_key>
export AZURE_STT_REGION=<your_azure_stt_region>

# TTS
# Here are three TTS options, either one will work
# Make sure to comment out the one you don't use

# 1. using Azure
export TTS_VENDOR_CHINESE=azure
export AZURE_TTS_KEY=<your_azure_tts_key>
export AZURE_TTS_REGION=<your_azure_tts_region>

# 2. using ElevenLabs
export TTS_VENDOR_ENGLISH=elevenlabs
export ELEVENLABS_TTS_KEY=<your_elevanlabs_tts_key>

# Agent is ready to start on port 8080
make run-server
```

#### 4. 运行 voice agent 界面

voice agent 界面是基于 NextJS 14 构建的，因此需要 Node 18 或更高版本。

```bash
# 创建一个本地的环境文件
cd playground
cp .env.example .env

# 安装依赖
npm install && npm run dev
```

#### 5. 验证您定制的 voice agent 🎉

在浏览器中打开 `localhost:3000`，您应该能够看到一个与展示相似的语音助手，但带有您自己的定制内容。

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
<h2>搭建无界面的 voice agent</h2>

#### 1. 在 Docker 镜像中搭建 voice agent

```
# 从示例文件创建 manifest
cp ./agents/manifest.json.example ./agents/manifest.json

# 拉取带有开发工具的 Docker 镜像，并将当前文件夹挂载为工作区
docker run -itd -v $(pwd):/app -w /app -p 8080:8080 --name astra_agents_dev ghcr.io/rte-design/astra_agents_build

# 对于 Windows Git Bash
# docker run -itd -v //$(pwd):/app -w //app -p 8080:8080 --name astra_agents_dev ghcr.io/rte-design/astra_agents_build

# 进入 Docker 镜像
docker exec -it astra_agents_dev bash

# 构建 agent
make build

# 启动 agent
cd ./agents && ./bin/start
```

#### 2. 测试 voice agent

前往 [Agora Web Demo](https://webdemo.agora.io/) 进行快速测试。

请注意，`channel` 和 `remote_stream_id` 需要与您在 `https://webdemo.agora.io/` 上使用的一致。

输入相应的 RTC ID 和频道名称后，您应该能够看到日志并听到音频输出。

<br>
<h2>ASTRA 服务</h2>
<h3>了解更多</h3>

现在您已经创建了第一个 AI voice agent，创意并不会止步于此。要开发更多令人惊叹的语音助手，您需要深入了解 ASTRA 在幕后的工作原理。请参阅 [ ASTRA 架构文档 ](./docs/astra-architecture.md)。

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

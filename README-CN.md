<div align="center">
 <img alt="astra.ai" width="300px" height="auto" src="https://github.com/rte-design/ASTRA.ai/assets/471561/ef098c57-9e5c-479d-8ca5-0ad62a1a1423">
</div>

<h1 align="center">Astra.ai</h1>

<div align="center">

<a href="https://discord.gg/9VDGJ9F7"><img src="https://img.shields.io/badge/Discord-@Astra AI%20-blue.svg?logo=discord"></a>
<a href="">
<img src="https://img.shields.io/static/v1?label=RTE&message=Real-Time Engagement&color=yellow" alt="Agora RTE" /></a>
<a href="">
<img src="https://img.shields.io/static/v1?label=RTC&message=Video Call SDK&color=orange" alt="Agora RTC" /></a>
<a href="">
<img src="https://img.shields.io/static/v1?label=RTM&message=IM Chat&color=success" alt="Agora Chat"/></a>

</div>

<div align="center">

<span>实时多模型交互</span>
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
<span>兼容各种大语言模型</span>
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
<span>超低延时</span>

🎉 创建实时多模态 AI 代理 🎉

</div>

## Quick Start

### Playground

<div align="center">
<img  alt="Astra Voice Agent" src="./images/astra-voice-agent.gif">
</div>

我们把 Astra.ai Agent 放在一个线上 [Playground](https://astra-agents.agora.io/)， 欢迎试玩。

### 本地运行 Agent

当然，我们更欢迎您在本地试玩我们的 Voice Agent， 这里有一个 Docker 镜像，您可以在 macOS 和 Windows 上构建并运行该代理。

开始之前，请确保您拥有：

- Agora App ID and App 证书([详细指南](https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web))
- Azure's [speech-to-text](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) and [text-to-speech](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) API keys
- [OpenAI](https://openai.com/index/openai-api/) API key
- [Docker](https://www.docker.com/)

```shell
# run the pre-built agent image
docker run --restart=always -itd -p 8080:8080 \
        -v /tmp:/tmp \
        -e AGORA_APP_ID=<your_agora_appid> \
        -e AGORA_APP_CERTIFICATE=<your_agora_app_certificate> \
        -e AZURE_STT_KEY=<your_azure_stt_key> \
        -e AZURE_STT_REGION=<your_azure_stt_region> \
        -e OPENAI_API_KEY=<your_openai_api_key> \
        -e AZURE_TTS_KEY=<your_azure_tts_key> \
        -e AZURE_TTS_REGION=<your_azure_tts_region> \
        --name astra_agents_server \
        agoraio/astra_agents_server:0.1.2
```

这条命令将启动一个运行在 8080 端口的代理服务器。

### 用 playground 链接您自己的 agent

您可以使用 Playground 项目来测试刚刚启动的服务器。

Playground 项目是基于 NextJS 14 构建的，因此需要 Node 18+ 版本。

```shell
# set up an .env file
cp ./playground/.env.example ./playground/.env
cd playground

# install npm dependencies & start
npm i && npm run dev
```

🎉 恭喜！您现在已经成功在本地运行了我们的 Astra Voice Agent.

</br>

## Agent 定制化

我们的语音代理是一个很好的起点，它使用了以下扩展：

- _agora_rtc_ / [Agora](https://docs.agora.io/en) for RTC transport + VAD + Azure speech-to-text (STT)
- _azure_tts_ / [Azure](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) for text-to-speech (TTS)
- _openai_chatgpt_ / [OpenAI](https://openai.com/index/openai-api/) for LLM
- _chat_transcriber_ / A utility ext to forward chat logs into channel
- _interrupt_detector_ / A utility ext to help interrupt agent

<div align="center">

<image alt="Astra.ai" width="800px" src="./images/image-2.png">

</div>

### 定制个性化 Agent

您可能希望添加更多的功能，以使代理更适合您的需求。为此，您需要修改扩展的源代码并自行构建代理。

首先需要改动 `manifest.json`:

```shell
# rename manifest example
cp ./agents/manifest.json.example ./agents/manifest.json

# pull the docker image with dev tools and mount your current folder as workspace
docker run -itd -v $(pwd):/app -w /app -p 8080:8080 --name astra_agents_dev agoraio/astra_agents_build:0.1.0

# enter docker image
docker exec -it astra_agents_dev bash

# build agent
make build
```

该代码生成一个代理可执行文件。要自定义提示和 OpenAI 参数，请修改 agents/addon/extension/openai_chatgpt/openai_chatgpt.go 源代码。

完成修改后，您可以使用以下命令启动服务器。然后，您可以像之前的步骤一样，使用 Astra Voice Agent 在 Playground 进行测试。

```shell

export AGORA_APP_ID=<your_agora_appid>
export AGORA_APP_CERTIFICATE=<your_agora_app_certificate>
export AZURE_STT_KEY=<your_azure_stt_key>
export AZURE_STT_REGION=<your_azure_stt_region>
export OPENAI_API_KEY=<your_openai_api_key>
export AZURE_TTS_KEY=<your_azure_tts_key>
export AZURE_TTS_REGION=<your_azure_tts_region>

# agent is ready to start on port 8080

make run-server
```

🎉 恭喜你！你已经创建了你的第一个个性化语音代理。我们对你的努力表示赞赏，并期待在 Astra 云商店中看到它。如果你能在社区中分享它，我们将不胜感激。

<br />

## Astra 服务

现在让我们来深入了解一下。Astra 服务由多种不同编程语言开发的 Astra 扩展组成。这些扩展通过图谱相互连接，描述它们的关系并展示数据流动。此外，通过 Astra 云商店和 Astra 包管理器，扩展的分享和下载变得更加简便。

<div align="center">

<image alt="Astra.ai" width="800px" src="./images/image.png">

</div>

### Astra 扩展

扩展是 Astra 框架中的基本组合单元。开发人员可以使用多种编程语言创建扩展，并将它们组合起来构建不同的场景和应用程序。Astra 强调跨语言协作，允许使用不同语言编写的扩展在同一应用程序或服务中无缝协同工作。

例如，如果一个应用程序需要实时通信（RTC）功能和先进的人工智能能力，开发人员可以选择使用 C++ 编写与音频和视频数据处理性能优势相关的 RTC 相关扩展。同时，他们可以使用 Python 开发 AI 扩展，利用其丰富的库和框架进行数据分析和机器学习任务。

### 语言支持

截至 2024 年 6 月，我们支持以下语言编写的扩展：

- C++
- Golang
- Python (7 月)

开发人员可以灵活选择最适合他们需求的语言，并将其无缝集成到 Astra 框架中。

这段内容详细描述了截至指定日期的 Astra 扩展支持的编程语言。

## 图谱

在 Astra 中，图谱描述了扩展之间的数据流，协调它们的交互。例如，语音转文本（STT）扩展的文本输出可以指向大型语言模型（LLM）扩展。简而言之，图谱定义了涉及的扩展以及它们之间数据流的方向。开发者可以定制这种流程，将一个扩展（如 STT）的输出引导到另一个（如 LLM）。

在 Astra 中，有四种主要类型的扩展之间数据流：

- Command
- Data
- Image frame
- PCM frame

通过在图谱中指定这些数据类型的方向，开发人员可以实现插件之间的相互调用和单向数据流。这对于 PCM 和图像数据类型尤其有用，简化了音频和视频处理。

### Astra 代理应用

Astra 代理应用是一个可运行的服务器端应用程序，根据图谱规则结合多个扩展来完成更复杂的操作。

### Astra 云商店

Astra 商店是一个集中的平台，开发人员可以在这里分享他们的扩展，并访问其他人创建的扩展。

### Astra 包管理器

Astra 包管理器简化了上传、分享、下载和安装 Astra 扩展的过程。扩展可以指定对其他扩展和环境的依赖关系，Astra 包管理器会自动管理这些依赖关系，使扩展的安装和发布变得非常方便和直观。

</br>

</br>

## Contributing

欢迎贡献！请先阅读 [贡献指南](CONTRIBUTING.md)。

</br>

## License

本项目使用 Apache 2.0 许可证授权 - 详细信息请参阅 [LICENSE](LICENSE)。

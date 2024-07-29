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

##  项目示例

[Voice Agent Astra](https://theastra.ai)

我们通过平台的能力搭建了一个语音助手，名字是 Astra,

[![Showcase ASTRA Voice Agent](https://github.com/rte-design/ASTRA.ai/raw/main/images/astra-voice-agent.gif)](https://theastra.ai)

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
        agoraio/astra_agents_server:latest
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

🎉 恭喜！您现在已经成功在本地运行了我们的 ASTRA Voice Agent.

</br>

## Agent 定制化

我们的语音代理是一个很好的起点，它使用了以下扩展：

| Extension          | Feature        | Description                                                                                                                                                                                                          |
| ------------------ | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| openai_chatgpt     | LLM            | [ GPT-4o ](https://platform.openai.com/docs/models/gpt-4o), [ GPT-4 Turbo ](https://platform.openai.com/docs/models/gpt-4-turbo-and-gpt-4), [ GPT-3.5 Turbo ](https://platform.openai.com/docs/models/gpt-3-5-turbo) |
| elevenlabs_tts     | Text-to-speech | [ElevanLabs text to speech](https://elevenlabs.io/) converts text to audio                                                                                                                                           |
| azure_tts          | Text-to-speech | [Azure text to speech](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) converts text to audio                                                                                                 |
| azure_stt          | Speech-to-text | [Azure speech to text](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) converts audio to text                                                                                                 |
| chat_transcriber   | Transcriber    | A utility ext to forward chat logs into channel                                                                                                                                                                      |
| agora_rtc          | Transporter    | A low latency transporter powered by agora_rtc                                                                                                                                                                       |
| interrupt_detector | Interrupter    | A utility ext to help interrupt agent                         

![](../../images/image-2.png)

### 定制个性化 Agent

您可能希望添加更多的功能，以使代理更适合您的需求。为此，您需要修改扩展的源代码并自行构建代理。

首先需要改动 `manifest.json`:

```shell
# rename manifest example
cp ./agents/manifest.json.example ./agents/manifest.json
cp ./agents/manifest.json.en.example ./agents/manifest.en.json
cp ./agents/manifest.json.cn.example ./agents/manifest.cn.json

# pull the docker image with dev tools and mount your current folder as workspace
docker run -itd -v $(pwd):/app -w /app -p 8080:8080 --name astra_agents_dev ghcr.io/rte-design/astra_agents_build:0.3.2

# for windows git bash
# docker run -itd -v //$(pwd):/app -w //app -p 8080:8080 --name astra_agents_dev ghcr.io/rte-design/astra_agents_build:0.3.2

# enter docker image
docker exec -it astra_agents_dev bash

# build agent
make build
```

该代码生成一个代理可执行文件。要自定义提示和 OpenAI 参数，请修改 agents/addon/extension/openai_chatgpt/openai_chatgpt.go 源代码。

完成修改后，您可以使用以下命令启动服务器。然后，您可以像之前的步骤一样，使用 ASTRA Voice Agent 在 Playground 进行测试。

```shell

export AGORA_APP_ID=<your_agora_appid>
export AGORA_APP_CERTIFICATE=<your_agora_app_certificate>
export AZURE_STT_KEY=<your_azure_stt_key>
export AZURE_STT_REGION=<your_azure_stt_region>

# LLM
export OPENAI_API_KEY=<your_openai_api_key>
export QWEN_API_KEY=<your_qwern_api_key>

# TTS
# cosy
export COSY_TTS_KEY=<your_cosy_tts_key>
# if you use AZURE_TTS
export AZURE_TTS_KEY=<your_azure_tts_key>
export AZURE_TTS_REGION=<your_azure_tts_region>


# agent is ready to start on port 8080

make run-server
```

🎉 到这里，您已经成功创建一个私人定制的语音助手。

<h3>Customize Agent</h3>

You might want to add more flavors to make the agent better suited to your needs. To achieve this, you need to change the source code of extensions and build the agent yourselves.

You need to prepare the proper `manifest.json` file first.

```bash
# Rename manifest example
cp ./agents/manifest.json.example ./agents/manifest.json
cp ./agents/manifest.json.elevenlabs.example ./agents/manifest.json.elevenlabs.example

# pull the docker image with dev tools and mount your current folder as workspace
docker run -itd -v $(pwd):/app -w /app -p 8080:8080 --name astra_agents_dev ghcr.io/rte-design/astra_agents_build

# for windows git bash
# docker run -itd -v //$(pwd):/app -w //app -p 8080:8080 --name astra_agents_dev ghcr.io/rte-design/astra_agents_build

# Enter docker image
docker exec -it astra_agents_dev bash

# Build agent
make build
```

The above code generates an agent executable. To customize your prompts and OpenAI parameters, modify the source code in `agents/addon/extension/openai_chatgpt/openai_chatgpt.go`.

<h3>Start Server</h3>

Once you have made the necessary changes, you can use the following commands to start a server. You can then test it out using the ASTRA voice agent from the showcase.

```bash
# TODO: need to refactor the contents
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

# agent is ready to start on port 8080
make run-server
```

🎉 Congratulations! You have created your first personalized voice agent.

<h3>Quick Agent Customize Test</h3>
The default agent control is managed via server gateway. For quick testing, you can also run the agent directly.

```

# rename manifest example
cp ./agents/manifest.json.example ./agents/manifest.json
cp ./agents/manifest.json.elevenlabs.example ./agents/manifest.json.elevenlabs.example

# pull the docker image with dev tools and mount your current folder as workspace
docker run -itd -v $(pwd):/app -w /app -p 8080:8080 --name astra_agents_dev ghcr.io/rte-design/astra_agents_build

# for windows git bash
# docker run -itd -v //$(pwd):/app -w //app -p 8080:8080 --name astra_agents_dev ghcr.io/rte-design/astra_agents_build

# enter docker image
docker exec -it astra_agents_dev bash

make build

cd ./agents
# manipulate values in manifest.json to replace <agora_appid>, <qwen_api_key>, <stt_api_key>, <stt_region> with your keys
./bin/start
```

use [https://webdemo.agora.io/](https://webdemo.agora.io/) to quickly test.

Note the `channel` and `remote_stream_id` needs to match with the one you use on `https://webdemo.agora.io/`

<br>
<h2>ASTRA Service</h2>
<h3>Discover More</h3>

Now that you’ve created your first AI agent, the creativity doesn’t stop here. To develop more amazing agents, you’ll need an advanced understanding of how the ASTRA works under the hood. Please refer to the [ ASTRA architecture documentation ](./docs/astra-architecture.md).

<br>
<h2>Join Community</h2>

- [Discord](https://discord.gg/VnPftUzAMJ):  加入我们的 Discord 频道
- [WeChat Group](https://github.com/rte-design/ASTRA.ai/issues/125): 加入微信群聊
- [Github Discussion](https://github.com/rte-design/astra.ai/discussions): Perfect for providing feedback and asking questions.
- [GitHub Issues](https://github.com/rte-design/astra.ai/issues): Best for reporting bugs and proposing new features. Refer to our [contribution guidelines](./docs/code-of-conduct/contributing.md) for more details.
- [X (formerly Twitter)](https://twitter.com/intent/follow?screen_name=AstraFramework): Great for sharing your agents and interacting with the community.

 <br>
 <h2>Code Contributors</h2>

[![ASTRA](https://contrib.rocks/image?repo=rte-design/astra.ai)](https://github.com/rte-design/astra.ai/graphs/contributors)


<br />
<h2>点星收藏</h2>

我们更新频繁，不想错过的话，请给我们的 repo 点星，以便获得第一时间的更新.

![ASTRA star us gif](https://github.com/rte-design/ASTRA.ai/raw/main/images/star-the-repo-confetti-higher-quality.gif)

</br>
<h2>Contributing</h2>

欢迎贡献！请先阅读 [贡献指南](../code-of-conduct/contributing.md)。

</br>
<h2>License</h2>

本项目使用 Apache 2.0 许可证授权 - 详细信息请参阅 [LICENSE](LICENSE)。

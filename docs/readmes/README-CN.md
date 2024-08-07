![Astra Banner Image](https://github.com/rte-design/docs/blob/main/assets/imgs/banner-image-without-tagline.png)

<div align="center">

[![Follow on X](https://img.shields.io/twitter/follow/AstraFramework?logo=X&color=%20%23f5f5f5)](https://twitter.com/intent/follow?screen_name=AstraFramework)
[![Discussion posts](https://img.shields.io/github/discussions/rte-design/astra.ai?labelColor=%20%23FDB062&color=%20%23f79009)](https://github.com/rte-design/astra.ai/discussions/)
[![Commits](https://img.shields.io/github/commit-activity/m/rte-design/astra.ai?labelColor=%20%237d89b0&color=%20%235d6b98)](https://github.com/rte-design/astra.ai/graphs/commit-activity)
[![Issues closed](https://img.shields.io/github/issues-search?query=repo%3Arte-design%2Fastra.ai%20is%3Aclosed&label=issues%20closed&labelColor=green&color=green)](https://github.com/rte-design/ASTRA.ai/issues)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](https://github.com/rte-design/ASTRA.ai/pulls)
[![GitHub license](https://img.shields.io/badge/License-Apache_2.0-blue.svg?labelColor=%20%239b8afb&color=%20%237a5af8)](https://github.com/rte-design/ASTRA.ai/blob/main/LICENSE)
[![WeChat](https://img.shields.io/badge/WeChat-WeChat_Group-%2307C160?logo=wechat)](https://github.com/rte-design/ASTRA.ai/discussions/170)

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

<br>

## Astra

[Astra](https://theastra.ai) 是通过 TEN 搭建出来的 voice agent, 展示了多模态，低延迟的能力。

[![Showcase Astra](https://github.com/rte-design/docs/blob/main/assets/gifs/astra-voice-agent.gif?raw=true)](https://theastra.ai)

<br>
<h2>如何用搭建的 graph designer 配置 voice agent</h2>

### 先决条件
#### Keys 
- Agora App ID 和 App Certificate（[点击此处了解详情](https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web)）
- Azure 的 [STT](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) 和 [TTS](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) API Keys
- [OpenAI](https://openai.com/index/openai-api/) API Key
#### 下载安装
- [Docker](https://www.docker.com/)	和 [Docker Compose](https://docs.docker.com/compose/install/)
- [Node.js(LTS) v18](https://nodejs.org/en)
#### 机器配置
- CPU >= 2 Core
- RAM >= 4 GB

#### Apple Silicon 上 Docker 设置
如果您使用的是 Apple Silicon Mac，您需要取消勾选 Docker 的 "Use Rosetta for x86_64/amd64 emulation on Apple Silicon" 选项，否则服务器将无法正常工作。

<div align="center">

![Docker Setting](https://github.com/rte-design/docs/blob/main/assets/gifs/docker-setting.gif?raw=true)

</div>

#### 设置 Go 国内代理
如果在国内，我们建议跑下列命令来全局设定国内代理以便快速下载依赖([了解详情](https://goproxy.cn/))。

```bash
 export GOPROXY=https://goproxy.cn 
```

### 下一步
#### 1. 准备设置文件
Clone 项目后，在根目录下跑下面的命创建 `property.json` 和 `.env`:
```bash
# 创建 .env 文件
cp ./.env.example ./.env

# 创建 property.json 文件
cp ./agents/property.json.example ./agents/property.json
```

#### 2. 绑定积木的 keys 
打开 `.env` 文件，绑定对应的积木 keys，这里可以通过配置不同的 keys 选用不用的积木：
```
# Agora App ID and Agora App Certificate
AGORA_APP_ID=
AGORA_APP_CERTIFICATE=

# Extension: agora_rtc
# Azure STT key and region
AZURE_STT_KEY=
AZURE_STT_REGION=

# Extension: azure_tts
# Azure TTS key and region
AZURE_TTS_KEY=
AZURE_TTS_REGION=

# Extension: openai_chatgpt
# OpenAI API key
OPENAI_API_KEY=
```

#### 3. 开启 Docker 容器
在同一个目录下，通过 Docker 镜像构建 Docker 容器：
```bash
# 开启 Docker 容器：
docker compose up
```

#### 4. 构建 Agent 并开启服务
再打开一个 Terminal 窗口，通过下面的命令进入 Docker 容器，创建并开启服务：
```bash
#  进入容器创建 Agent
docker exec -it astra_agents_dev bash
make build

# 端口 8080 开启服务
make run-server
```

#### 5. 验证 voice agent 和 graph designer 🎉

现在可以打开浏览器 `http://localhost:3000` 体验 voice agent，同时可以再开浏览器的一个窗口 `http://localhost:3001` 用 graph designer 定制 voice agent。

#### Graph designer

TEN Graph Designer (beta)，通过简单拖拽和动态节点连接轻松实现多模型配置。

![TEN Graph Designer](https://github.com/rte-design/docs/blob/main/assets/gifs/graph-designer.gif?raw=true)

<br>
<h2>点星收藏</h2>

我们更新频繁，不想错过的话，请给我们的 repo 点星，以便获得第一时间的更新.

![TEN star us gif](https://github.com/rte-design/docs/blob/main/assets/gifs/star-the-repo-confetti-higher-quality.gif?raw=true)



<br>
<h2>加入社区</h2>

- [Discord](https://discord.gg/VnPftUzAMJ)：非常适合分享您的应用程序并与社区互动。
- [WeChat Group](https://github.com/rte-design/ASTRA.ai/discussions/170): 如果喜欢用微信群的社区，欢迎加入。
- [Github Discussion](https://github.com/rte-design/astra.ai/discussions)：非常适合提供反馈和提问。
- [GitHub Issues](https://github.com/rte-design/astra.ai/issues)：最适合报告错误和提出新功能。有关更多详细信息，请参阅我们的[贡献指南](./docs/code-of-conduct/contributing.md)。
- [X（以前的Twitter）](https://twitter.com/intent/follow?screen_name=AstraFramework)：非常适合分享您的代理并与社区互动。

<br>
 <h2>代码贡献者</h2>

[![ASTRA](https://contrib.rocks/image?repo=rte-design/astra.ai)](https://github.com/rte-design/astra.ai/graphs/contributors)

<br>
<h2>欢迎贡献</h2>

欢迎贡献！请先阅读 [贡献指南](../code-of-conduct/contributing.md)。

<br>
<h2>许可证授权</h2>

本项目使用 Apache 2.0 许可证授权 - 详细信息请参阅 [LICENSE](LICENSE)。
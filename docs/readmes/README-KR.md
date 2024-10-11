![TEN Agent banner](https://github.com/TEN-framework/docs/blob/main/assets/jpg/banner.jpg?raw=true)

<div align="center">

[![Follow on X](https://img.shields.io/twitter/follow/TenFramework?logo=X&color=%20%23f5f5f5)](https://twitter.com/intent/follow?screen_name=TenFramework)
![Product fee](https://img.shields.io/badge/pricing-free-blue.svg?labelColor=%20%239b8afb&color=%20%237a5af8)
[![Discussion posts](https://img.shields.io/github/discussions/TEN-framework/ten-agent?labelColor=%20%23FDB062&color=%20%23f79009)](https://github.com/TEN-framework/ten-agent/discussions/)
[![Commits](https://img.shields.io/github/commit-activity/m/TEN-framework/ten-agent?labelColor=%20%237d89b0&color=%20%235d6b98)](https://github.com/TEN-framework/ten-agent/graphs/commit-activity)
[![Issues closed](https://img.shields.io/github/issues-search?query=repo%3ATEN-framework%2Ften-agent%20is%3Aclosed&label=issues%20closed&labelColor=green&color=green)](https://github.com/TEN-framework/ten-agent/issues)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](https://github.com/TEN-framework/ten-agent/pulls)
[![GitHub license](https://img.shields.io/badge/License-Apache_2.0-blue.svg?labelColor=%20%23155EEF&color=%20%23528bff)](https://github.com/TEN-framework/ten-agent/blob/main/LICENSE)

[![Discord TEN Community](https://dcbadge.vercel.app/api/server/VnPftUzAMJ)](https://discord.gg/VnPftUzAMJ)

[![GitHub watchers](https://img.shields.io/github/watchers/TEN-framework/ten-agent?style=social&label=Watch)](https://GitHub.com/TEN-framework/ten-agent/watchers/?WT.mc_id=academic-105485-koreyst)
[![GitHub forks](https://img.shields.io/github/forks/TEN-framework/ten-agent?style=social&label=Fork)](https://GitHub.com/TEN-framework/ten-agent/network/?WT.mc_id=academic-105485-koreyst)
[![GitHub stars](https://img.shields.io/github/stars/TEN-framework/ten-agent?style=social&label=Star)](https://GitHub.com/TEN-framework/ten-agent/stargazers/?WT.mc_id=academic-105485-koreyst)

<a href="https://github.com/TEN-framework/ten-agent/blob/main/README.md"><img alt="README in English" src="https://img.shields.io/badge/English-lightgrey"></a>
<a href="https://github.com/ten-framework/ten-agent/blob/main/docs/readmes/README-CN.md"><img alt="简体中文操作指南" src="https://img.shields.io/badge/简体中文-lightgrey"></a>
<a href="https://github.com/ten-framework/ten-agent/blob/main/docs/readmes/README-JP.md"><img alt="日本語のREADME" src="https://img.shields.io/badge/日本語-lightgrey"></a>
<a href="https://github.com/ten-framework/ten-agent/blob/main/docs/readmes/README-KR.md"><img alt="README in 한국어" src="https://img.shields.io/badge/한국어-lightgrey"></a>
<a href="https://github.com/ten-framework/ten-agent/blob/main/docs/readmes/README-ES.md"><img alt="README en Español" src="https://img.shields.io/badge/Español-lightgrey"></a>
<a href="https://github.com/ten-framework/ten-agent/blob/main/docs/readmes/README-FR.md"><img alt="README en Français" src="https://img.shields.io/badge/Français-lightgrey"></a>
<a href="https://github.com/ten-framework/ten-agent/blob/main/docs/readmes/README-IT.md"><img alt="README in Italiano" src="https://img.shields.io/badge/Italiano-lightgrey"></a>

[Getting Started](https://doc.theten.ai/ten-agent/getting_started)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[Create Extensions](https://doc.theten.ai/ten-agent/create_a_hello_world_extension)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[TEN Framework Repository](https://github.com/TEN-framework/ten_framework)



</div>

**TEN Agent**, powered by the world’s first real-time multimodal framework. It is open-source, with the ability to speak, see, and access a knowledge base. By taking advantage of TEN Framework, TEN Agent has the following features:

1. **High-Performance Real-Time Multimodal Interactions**:
Offers high-performance, low-latency solutions for complex audio-visual AI applications.

2. **Multi-Language and Multi-Platform Support** :
Supports extension development in C++, Go, Python, etc. Runs on Windows, Mac, Linux, and mobile devices.

3. **Edge-Cloud Integration**:
Flexibly combines edge and cloud-deployed extensions, balancing privacy, cost, and performance.

4. **Flexibility Beyond Model Limitations**:
Easily build complex AI applications through simple drag-and-drop programming, integrating audio-visual tools, databases, RAG, and more.

5. **Real-Time Agent State Management**:
Manages and adjusts agent behavior in real-time for dynamic responsiveness.

<br>
<h2>Stay Tuned</h2>

Before we get started, be sure to star our repository and get instant notifications for all new releases!

![TEN star us gif](https://github.com/TEN-framework/docs/blob/main/assets/gif/star_us_2.gif?raw=true)

<br>
<h2>TEN Agent</h2>

[TEN Agent](https://agent.theten.ai)

TEN Agent is a multimodal agent powered by [ TEN ](https://theten.ai), demonstrating its capabilities in speech, vision, and reasoning through  RAG from local documentation.

[![Showcase TEN multimodal agent](https://github.com/TEN-framework/docs/blob/main/assets/gif/features.gif?raw=true)](https://agent.theten.ai)
<br>
<h2>How to build TEN Agent locally

### Prerequisites

#### Keys
- Agora [ App ID ](https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web#create-an-agora-project) and [ App Certificate ](https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web#create-an-agora-project)(certificate is not required)
- Azure [SST](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) and [TTS](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) API keys (feel  free to use another provider)
- [OpenAI](https://openai.com/index/openai-api/) API key

#### Installation
  - [Docker](https://www.docker.com/) / [Docker Compose](https://docs.docker.com/compose/)
  - [Node.js(LTS) v18](https://nodejs.org/en)

#### Minimum system requirements
  - CPU >= 2 Core
  - RAM >= 4 GB

#### Docker setting on Apple Silicon
You will need to uncheck "Use Rosetta for x86_64/amd64 emulation on Apple Silicon" option for Docker if you are on Apple Silicon, otherwise the server is not going to work.

![Docker Setting](https://github.com/TEN-framework/docs/blob/main/assets/gif/docker_setting.gif?raw=true)

### Next step

#### 1. Modify config files
In the root of the project, use `cp` command to create `.env` from the example.

It will be used to store information for `docker compose` later.
```bash
cp ./.env.example ./.env
```

#### 2. Setup API keys
Open the `.env` file and fill in the `keys` and `regions`. This is also where you can choose to use any different `extensions`:
```bash
# Agora App ID and Agora App Certificate
AGORA_APP_ID=
# Leave empty unless you have enabled the certificate within the Agora account.
AGORA_APP_CERTIFICATE=

# Azure STT key and region
AZURE_STT_KEY=
AZURE_STT_REGION=

# Azure TTS key and region
AZURE_TTS_KEY=
AZURE_TTS_REGION=

# OpenAI API key
OPENAI_API_KEY=
```

#### 3. Start agent development containers
In the same directory, run the `docker compose up` command to compose containers:
```bash
docker compose up
```

#### 4. Enter container and build agent
Open up a separate terminal window, enter the container and build the agent:
```bash
docker exec -it ten_agent_server bash
make build
```

#### 5. Start the server
Once the build is done, `make run-server` on port `8080`:
```bash
make run-server
```

### Finish and verify 🎉

#### TEN Agent
Open up http://localhost:3000 in browser to play and test the TEN Agent.

#### Graph Designer

Open up another tab go to http://localhost:3001, and use Graph Designer to create, connect and edit extensions on canvas.

![TEN Graph Designer](https://github.com/TEN-framework/docs/blob/main/assets/gif/graph_designer.gif?raw=true)

<br>
<h2>TEN Agent Comparison</h2>

<div align="center">

| **Features**                             | **TEN Agent** | **Pipecat** | **LiveKit:KITT** | **Vapi.ai** | **DailyBots** | **Play.ai** |
|:----------------------------------------:|:-------:|:--------:|:-------------:|:----------------:|:----------------:|:----------------:|
| **Vision**                               |   ✅    |    ❌    |      ❌       |     ❌     |     ❌      |     ❌       |
| **Rich TTS Support for different languages** |   ✅    |    ❌    |      ❌       |     ❌      |     ❌      |     ❌      |
| **Go support for extension**              |   ✅    |    ❌    |      ❌       |     ❌     |      ❌     |     ❌      |
| **C++ support for extension**             |   ✅    |    ❌    |      ❌       |     ❌     |      ❌     |     ❌      |
| **RAG support**                          |   ✅    |    ❌    |      ❌       |     ❌     |      ❌     |     ❌      |
| **Workflow builder for extension**        |   ✅    |    ❌    |      ❌       |     ✅      |     ❌     |     ❌      |
| **Rich LLM Support**                      |   ✅    |    ✅    |      ✅       |     ✅     |     ✅     |    ✅      |
| **Python support for extension**          |   ✅    |    ✅    |      ✅       |     ✅     |     ✅      |     ✅     |
| **Open source**                          |   ✅    |    ✅    |      ✅       |     ❌     |     ❌      |     ❌      |

</div>

<br>


<br>
<h2>Join Community</h2>

- [Discord](https://discord.gg/VnPftUzAMJ): Ideal for sharing your applications and engaging with the community.
- [GitHub Discussion](https://github.com/TEN-framework/ten-agent/discussions): Perfect for providing feedback and asking questions.
- [GitHub Issues](https://github.com/TEN-framework/ten-agent/issues): Best for reporting bugs and proposing new features. Refer to our [contribution guidelines](./docs/code-of-conduct/contributing.md) for more details.
- [X (formerly Twitter)](https://img.shields.io/twitter/follow/TenFramework?logo=X&color=%20%23f5f5f5): Great for sharing your agents and interacting with the community.


 <br>
 <h2>Code Contributors</h2>

[![TEN](https://contrib.rocks/image?repo=TEN-framework/ten-agent)](https://github.com/TEN-framework/ten-agent/graphs/contributors)

<br>
<h2>Contribution Guidelines</h2>

Contributions are welcome! Please read the [contribution guidelines](./docs/code-of-conduct/contributing.md) first.

<br>
<h2>License</h2>

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

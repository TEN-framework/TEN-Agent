![Astra banner image](https://github.com/TEN-framework/docs/blob/main/assets/imgs/astra-banner.jpg?raw=true)
<div align="center">

[![Follow on X](https://img.shields.io/twitter/follow/AstraAIAgent?logo=X&color=%20%23f5f5f5)](https://twitter.com/intent/follow?screen_name=AstraAIAgent)
![Product fee](https://img.shields.io/badge/pricing-free-blue.svg?labelColor=%20%239b8afb&color=%20%237a5af8)
[![Discussion posts](https://img.shields.io/github/discussions/TEN-framework/astra.ai?labelColor=%20%23FDB062&color=%20%23f79009)](https://github.com/TEN-framework/astra.ai/discussions/)
[![Commits](https://img.shields.io/github/commit-activity/m/TEN-framework/astra.ai?labelColor=%20%237d89b0&color=%20%235d6b98)](https://github.com/TEN-framework/astra.ai/graphs/commit-activity)
[![Issues closed](https://img.shields.io/github/issues-search?query=repo%3ATEN-framework%2Fastra.ai%20is%3Aclosed&label=issues%20closed&labelColor=green&color=green)](https://github.com/TEN-framework/ASTRA.ai/issues)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](https://github.com/TEN-framework/ASTRA.ai/pulls)
[![GitHub license](https://img.shields.io/badge/License-Apache_2.0-blue.svg?labelColor=%20%23155EEF&color=%20%23528bff)](https://github.com/TEN-framework/ASTRA.ai/blob/main/LICENSE)

[![Discord TEN Community](https://dcbadge.vercel.app/api/server/VnPftUzAMJ)](https://discord.gg/VnPftUzAMJ)

[![GitHub watchers](https://img.shields.io/github/watchers/TEN-framework/astra.ai?style=social&label=Watch)](https://GitHub.com/TEN-framework/astra.ai/watchers/?WT.mc_id=academic-105485-koreyst)
[![GitHub forks](https://img.shields.io/github/forks/TEN-framework/astra.ai?style=social&label=Fork)](https://GitHub.com/TEN-framework/astra.ai/network/?WT.mc_id=academic-105485-koreyst)
[![GitHub stars](https://img.shields.io/github/stars/TEN-framework/astra.ai?style=social&label=Star)](https://GitHub.com/TEN-framework/astra.ai/stargazers/?WT.mc_id=academic-105485-koreyst)

<a href="https://github.com/TEN-framework/ASTRA.ai/blob/main/README.md"><img alt="README in English" src="https://img.shields.io/badge/English-lightgrey"></a>
<a href="https://github.com/ten-framework/astra.ai/blob/main/docs/readmes/README-CN.md"><img alt="简体中文操作指南" src="https://img.shields.io/badge/简体中文-lightgrey"></a>
<a href="https://github.com/ten-framework/astra.ai/blob/main/docs/readmes/README-JP.md"><img alt="日本語のREADME" src="https://img.shields.io/badge/日本語-lightgrey"></a>
<a href="https://github.com/ten-framework/astra.ai/blob/main/docs/readmes/README-KR.md"><img alt="README in 한국어" src="https://img.shields.io/badge/한국어-lightgrey"></a>
<a href="https://github.com/ten-framework/astra.ai/blob/main/docs/readmes/README-ES.md"><img alt="README en Español" src="https://img.shields.io/badge/Español-lightgrey"></a>
<a href="https://github.com/ten-framework/astra.ai/blob/main/docs/readmes/README-FR.md"><img alt="README en Français" src="https://img.shields.io/badge/Français-lightgrey"></a>
<a href="https://github.com/ten-framework/astra.ai/blob/main/docs/readmes/README-IT.md"><img alt="README in Italiano" src="https://img.shields.io/badge/Italiano-lightgrey"></a>


[Documentation](https://doc.theten.ai)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[Getting Started](https://doc.theten.ai/getting-started/quickstart)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[Tutorials](https://doc.theten.ai/getting-started/create-a-hello-world-extension)

</div>

<br>
<h2>Astra - a multimodal agent</h2>

[Astra multimodal agent](https://theastra.ai)

Astra is a multimodal agent powered by [ TEN ](https://doc.theten.ai), demonstrating its capabilities in speech, vision, and reasoning through  RAG from local documentation.

[![Showcase Astra multimodal agent](https://github.com/TEN-framework/docs/blob/main/assets/gifs/astra-voice-agent.gif?raw=true)](https://theastra.ai)
<br>
<h2>How to build Astra locally

### Prerequisites

#### Keys
- Agora App ID and App Certificate([read here on how](https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web))
- Azure's [speech-to-text](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) and [text-to-speech](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) API keys
- [OpenAI](https://openai.com/index/openai-api/) API key

#### Installation
  - [Docker](https://www.docker.com/) / [Docker Compose](https://docs.docker.com/compose/)
  - [Node.js(LTS) v18](https://nodejs.org/en)

#### Minimum system requirements
  - CPU >= 2 Core
  - RAM >= 4 GB

#### Docker setting on Apple Silicon
You will need to uncheck "Use Rosetta for x86_64/amd64 emulation on Apple Silicon" option for Docker if you are on Apple Silicon, otherwise the server is not going to work.

![Docker Setting](https://github.com/TEN-framework/docs/blob/main/assets/gifs/docker-setting.gif?raw=true)

### Next step

#### 1. Modify config files
In the root of the project, use the following command to create `.env` and `./agents/property.json` from the examples. 

They will be used to store information for `docker compose` later.
```bash
cp ./.env.example ./.env
cp ./agents/property.json.example ./agents/property.json
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
docker exec -it astra_agents_dev bash
make build
```

#### 5. Start the server
Once the build is done, `make run-server` on port `8080`:
```bash
make run-server
```

### Finish and verify 🎉

#### Astra multimodal agent
Open up http://localhost:3000 in browser to test Astra multimodal agent.

#### Graph designer

Open up another tab go to http://localhost:3001, and use graph designer to edit the flow and properties of any extensions.

![TEN Graph Designer](https://github.com/TEN-framework/docs/blob/main/assets/gifs/graph-designer.gif?raw=true)

<br>
<h2>TEN Platform</h2>

Now that you’ve created your first AI agent, the creativity doesn't stop here. To develop more amazing agents, you’ll need an advanced understanding of how the TEN service works under the hood. Please refer to the [ TEN platform documentation ](https://doc.theten.ai).

<br>
<h2>TEN Feature Comparison</h2>

<div align="center">

| **Features**                             | **TEN** | **Dify** | **LangChain** | **Flowise** |
|:----------------------------------------:|:-------:|:--------:|:-------------:|:-----------:|
| **Opensourced Multimodal Agent**         |   ✅    |    ❌    |      ❌       |      ❌     |
| **Python, Go, and C++ for Extensions**   |   ✅    |    ❌    |      ❌       |      ❌     |
| **All-in-one Package Manager**           |   ✅    |    ❌    |      ❌       |      ❌     |
| **RTC Transportation**                   |   ✅    |    ❌    |      ❌       |      ❌     |
| **Extension Store**                      |   ✅    |    ✅    |      ❌       |      ❌     |
| **RAG**                                  |   ✅    |    ✅    |      ✅       |      ✅     |
| **Workflow Builder**                     |   ✅    |    ✅    |      ✅       |      ✅     |
| **Local Deployment**                     |   ✅    |    ✅    |      ✅       |      ✅     |

</div>

<br>
<h2>Stay Tuned</h2>

Before we dive further, be sure to star our repository and get instant notifications for all new releases!

![TEN star us gif](https://github.com/TEN-framework/docs/blob/main/assets/gifs/star-the-repo-confetti-higher-quality.gif?raw=true)

<br>
<h2>Join Community</h2>

- [Discord](https://discord.gg/VnPftUzAMJ): Ideal for sharing your applications and engaging with the community.
- [GitHub Discussion](https://github.com/TEN-framework/astra.ai/discussions): Perfect for providing feedback and asking questions.
- [GitHub Issues](https://github.com/TEN-framework/astra.ai/issues): Best for reporting bugs and proposing new features. Refer to our [contribution guidelines](./docs/code-of-conduct/contributing.md) for more details.
- [X (formerly Twitter)](https://img.shields.io/twitter/follow/AstraAIAgent?logo=X&color=%20%23f5f5f5): Great for sharing your agents and interacting with the community.


 <br>
 <h2>Code Contributors</h2>

[![TEN](https://contrib.rocks/image?repo=TEN-framework/astra.ai)](https://github.com/TEN-framework/astra.ai/graphs/contributors)

<br>
<h2>Contribution Guidelines</h2>

Contributions are welcome! Please read the [contribution guidelines](./docs/code-of-conduct/contributing.md) first.

<br>
<h2>License</h2>

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

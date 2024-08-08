![Astra Banner Image](https://github.com/rte-design/docs/blob/main/assets/imgs/banner-image-without-tagline.png)

<div align="center">

[![Follow on X](https://img.shields.io/twitter/follow/AstraFramework?logo=X&color=%20%23f5f5f5)](https://twitter.com/intent/follow?screen_name=AstraFramework)
[![Discussion posts](https://img.shields.io/github/discussions/rte-design/astra.ai?labelColor=%20%23FDB062&color=%20%23f79009)](https://github.com/rte-design/astra.ai/discussions/)
[![Commits](https://img.shields.io/github/commit-activity/m/rte-design/astra.ai?labelColor=%20%237d89b0&color=%20%235d6b98)](https://github.com/rte-design/astra.ai/graphs/commit-activity)
[![Issues closed](https://img.shields.io/github/issues-search?query=repo%3Arte-design%2Fastra.ai%20is%3Aclosed&label=issues%20closed&labelColor=green&color=green)](https://github.com/rte-design/ASTRA.ai/issues)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](https://github.com/rte-design/ASTRA.ai/pulls)
[![GitHub license](https://img.shields.io/badge/License-Apache_2.0-blue.svg?labelColor=%20%239b8afb&color=%20%237a5af8)](https://github.com/rte-design/ASTRA.ai/blob/main/LICENSE)

[![Discord ASTRA Community](https://dcbadge.vercel.app/api/server/VnPftUzAMJ)](https://discord.gg/VnPftUzAMJ)

[![GitHub watchers](https://img.shields.io/github/watchers/rte-design/astra.ai?style=social&label=Watch)](https://GitHub.com/rte-design/astra.ai/watchers/?WT.mc_id=academic-105485-koreyst)
[![GitHub forks](https://img.shields.io/github/forks/rte-design/astra.ai?style=social&label=Fork)](https://GitHub.com/rte-design/astra.ai/network/?WT.mc_id=academic-105485-koreyst)
[![GitHub stars](https://img.shields.io/github/stars/rte-design/astra.ai?style=social&label=Star)](https://GitHub.com/rte-design/astra.ai/stargazers/?WT.mc_id=academic-105485-koreyst)

<a href="./README.md"><img alt="README in English" src="https://img.shields.io/badge/English-lightgrey"></a>
<a href="./docs/readmes/README-CN.md"><img alt="简体中文" src="https://img.shields.io/badge/简体中文-lightgrey"></a>

[Documentation](https://astra-9.gitbook.io/ten-platform)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[Getting Started](https://astra-9.gitbook.io/ten-platform/getting-started/quickstart)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[Tutorials](https://app.gitbook.com/o/we7IoLK5sA6RQzhItfkW/s/4KgjqM5ChU0dSGjTLZmG/~/changes/6/tutorials/how-to-build-extension-with-go)

</div>

<br>
<h2>Voice agent: Astra</h2>

[Voice agent: Astra](https://theastra.ai)

Astra is a voice agent, powered by TEN, demonstrating its ability to create intuitive and seamless conversational interactions.

[![Showcase Astra](https://github.com/rte-design/docs/blob/main/assets/gifs/astra-voice-agent.gif?raw=true)](https://theastra.ai)
<br>
<h2>How to build voice agent locally

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

![Docker Setting](https://github.com/rte-design/docs/blob/main/assets/gifs/docker-setting.gif?raw=true)

### Next step

#### 1. Modify config files
In the root of the project, create these files from the examples. They will be used to store information for Docker Compose later.
```bash
# Create .env from the example
cp ./.env.example ./.env

# Create property.json from the example
cp ./agents/property.json.example ./agents/property.json
```

#### 2. Setup API keys
Open the `.env` file and fill in the keys and regions. This is also where you can choose to use any different extensions:
```
# Agora App ID and Agora App Certificate
# required: this variable must be set
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

#### 3. Start agent development containers
In the same directory, run the `docker` command to compose containers:
```bash
# Execute docker compose up to start the services
docker compose up
```

#### 4. Build agent and start server
Open up a separate terminal window, build the agent and start the server:
```bash
# Enter container to build agent
docker exec -it astra_agents_dev bash
make build

# Once the build is done, run server on port 8080
make run-server
```

### Finish and verify 🎉

#### Astra voice agent
Open up localhost:3000 in browser to test Astra voice agent.

#### Graph designer

Open up another tab go to localhost:3001, and use graph designer to edit the flow and properties of any extensions.

![TEN Graph Designer](https://github.com/rte-design/docs/blob/main/assets/gifs/graph-designer.gif?raw=true)

<br>
<h2>TEN Platform</h2>

Now that you’ve created your first AI agent, the creativity doesn't stop here. To develop more amazing agents, you’ll need an advanced understanding of how the TEN service works under the hood. Please refer to the [ TEN platform documentation ](https://astra-9.gitbook.io/ten-platform).

<br>
<h2>Stay Tuned</h2>

Before we dive further, be sure to star our repository and get instant notifications for all new releases!

![TEN star us gif](https://github.com/rte-design/docs/blob/main/assets/gifs/star-the-repo-confetti-higher-quality.gif?raw=true)

<br>
<h2>Join Community</h2>

- [Discord](https://discord.gg/VnPftUzAMJ): Ideal for sharing your applications and engaging with the community.
- [GitHub Discussion](https://github.com/rte-design/astra.ai/discussions): Perfect for providing feedback and asking questions.
- [GitHub Issues](https://github.com/rte-design/astra.ai/issues): Best for reporting bugs and proposing new features. Refer to our [contribution guidelines](./docs/code-of-conduct/contributing.md) for more details.
- [X (formerly Twitter)](https://twitter.com/intent/follow?screen_name=AstraFramework): Great for sharing your agents and interacting with the community.

 <br>
 <h2>Code Contributors</h2>

[![TEN](https://contrib.rocks/image?repo=rte-design/astra.ai)](https://github.com/rte-design/astra.ai/graphs/contributors)

<br>
<h2>Contribution Guidelines</h2>

Contributions are welcome! Please read the [contribution guidelines](CONTRIBUTING.md) first.

<br>
<h2>License</h2>

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.
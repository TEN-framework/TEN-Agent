![ASTRA Banner Image](https://github.com/rte-design/ASTRA.ai/raw/main/images/banner-image-without-tagline.png)

<div align="center">

[![Follow on X](https://img.shields.io/twitter/follow/AstraFramework?logo=X&color=%20%23f5f5f5)](https://twitter.com/intent/follow?screen_name=AstraFramework)
[![Discussion posts](https://img.shields.io/github/discussions/rte-design/astra.ai?labelColor=%20%23FDB062&color=%20%23f79009)](https://github.com/rte-design/astra.ai/discussions/)
[![Commits](https://img.shields.io/github/commit-activity/m/rte-design/astra.ai?labelColor=%20%237d89b0&color=%20%235d6b98)](https://github.com/rte-design/astra.ai/graphs/commit-activity)
[![Issues closed](https://img.shields.io/github/issues-search?query=repo%3Arte-design%2Fastra.ai%20is%3Aclosed&label=issues%20closed&labelColor=green&color=green)](https://github.com/rte-design/ASTRA.ai/issues)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](https://github.com/rte-design/ASTRA.ai/pulls)
[![GitHub license](https://img.shields.io/badge/License-Apache_2.0-blue.svg?labelColor=%20%239b8afb&color=%20%237a5af8)](https://github.com/rte-design/ASTRA.ai/blob/main/LICENSE)

[![](https://dcbadge.vercel.app/api/server/VnPftUzAMJ)](https://discord.gg/VnPftUzAMJ)

[![GitHub watchers](https://img.shields.io/github/watchers/rte-design/astra.ai?style=social&label=Watch)](https://GitHub.com/rte-design/astra.ai/watchers/?WT.mc_id=academic-105485-koreyst)
[![GitHub forks](https://img.shields.io/github/forks/rte-design/astra.ai?style=social&label=Fork)](https://GitHub.com/rte-design/astra.ai/network/?WT.mc_id=academic-105485-koreyst)
[![GitHub stars](https://img.shields.io/github/stars/rte-design/astra.ai?style=social&label=Star)](https://GitHub.com/rte-design/astra.ai/stargazers/?WT.mc_id=academic-105485-koreyst)

<a href="./README.md"><img alt="README in English" src="https://img.shields.io/badge/English-lightgrey"></a>
<a href="./README-CN.md"><img alt="简体中文" src="https://img.shields.io/badge/简体中文-lightgrey"></a>

[Lightning Fast](./markdowns/astra-architecture.md)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[Multimodal Interactive](./markdowns/astra-architecture.md#astra-extension)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[Highly Customizable](./markdowns/astra-architecture.md#astra-extension)

</div>

ASTRA is a highly customizable platform that simplifies the development of AI agents like never before. With ASTRA, you can easily create lightning-fast, multimodal AI agents, even without any coding knowledge.

<br>
<h2>Voice Agent Showcase</h2>

[ASTRA Voice Agent](https://theastra.ai)

We showcase an impressive voice agent powered by ASTRA, demonstrating its ability to create intuitive and seamless conversational interactions.

[![Showcase ASTRA Voice Agent](https://github.com/rte-design/ASTRA.ai/raw/main/images/astra-voice-agent.gif)](https://theastra.ai)

<h3>Stay Tuned</h3>

Before we dive further, be sure to star our repository and get instant notifications for all new releases!

![ASTRA star us gif](https://github.com/rte-design/ASTRA.ai/raw/main/images/star-the-repo-confetti-higher-quality.gif)

<h3>Run Voice Agent Locally</h3>

Feel free to run the showcased voice agent locally. We provide a Docker image that you can easily build and run on both macOS and Windows.

To start, make sure you have:

- Agora App ID and App Certificate([Read here on how](https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web))
- Azure's [speech-to-text](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) and [text-to-speech](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) API keys
- [OpenAI](https://openai.com/index/openai-api/) API key
- [Docker](https://www.docker.com/)

```bash
# Run the pre-built agent image
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

This should start an agent server running on port 8080.

#### Mac with Apple Silicon

You will need to uncheck "Use Rosetta for x86_64/amd64 emulation on apple silicon" option for Docker if you are on Apple Silicon.

<div align="center">

![ASTRA Docker Setting](https://github.com/rte-design/ASTRA.ai/raw/main/images/docker-setting.gif)

</div>

<h3>Connect to Your Agent</h3>

You can use the showcase voice agent, in `/playground` folder, to test with the server you just started.

The project is built on NextJS 14, hence it needs Node 18 or later.

```bash
# Set up an .env file
cp ./playground/.env.example ./playground/.env
cd playground

# Install npm dependencies & start
npm i && npm run dev
```

🎉 Congratulations! You now have a ASTRA powered voice agent running locally.

<br>
<h2>Agent Customization</h2>

To explore further, the ASTRA voice agent is an excellent starting point. It incorporates the following extensions, some of which will be interchangeable in the near future. Feel free to choose the ones that best suit your needs and maximize ASTRA’s capabilities.

| Extension           | Feature         | Description                                                                                                 |
|---------------------|-----------------|-------------------------------------------------------------------------------------------------------------|
| openai_chatgpt      | LLM             | [ GPT-4o ](https://platform.openai.com/docs/models/gpt-4o), [ GPT-4 Turbo ](https://platform.openai.com/docs/models/gpt-4-turbo-and-gpt-4), [ GPT-3.5 Turbo ](https://platform.openai.com/docs/models/gpt-3-5-turbo) |
| elevenlabs_tts      | Text-to-speech  | [ElevanLabs text to speech](https://elevenlabs.io/) converts text to audio                                                                               |
| azure_tts           | Text-to-speech  | [Azure text to speech](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) converts text to audio |
| azure_stt           | Speech-to-text  | [Azure speech to text](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) converts audio to text                                                                                       |
| chat_transcriber    | Transcriber     | A utility ext to forward chat logs into channel                                                             |
| agora_rtc           | Transporter     | A low latency transporter powered by agora_rtc                                                              |
| interrupt_detector | Interrupter     | A utility ext to help interrupt agent                                                                       |

<h3>Voice Agent Diagram</h3>

![ASTRA voice agent diagram](./images/image-2.png)

<h3>Customize Agent</h3>

You might want to add more flavors to make the agent better suited to your needs. To achieve this, you need to change the source code of extensions and build the agent yourselves.

You need to prepare the proper `manifest.json` file first.

```bash
# Rename manifest example
cp ./agents/manifest.json.example ./agents/manifest.json

# Pull the docker image with dev tools and mount your current folder as workspace
docker run -itd -v $(pwd):/app -w /app -p 8080:8080 --name astra_agents_dev agoraio/astra_agents_build

# Enter docker image
docker exec -it astra_agents_dev bash

# Build agent
make build
```

The above code generates an agent executable. To customize your prompts and OpenAI parameters, modify the source code in `agents/addon/extension/openai_chatgpt/openai_chatgpt.go`.

<h3>Start Server</h3>

Once you have made the necessary changes, you can use the following commands to start a server. You can then test it out using the ASTRA voice agent from the showcase.

```bash

# Agora App ID and Agora App Certificate
export AGORA_APP_ID=<your_agora_appid>
export AGORA_APP_CERTIFICATE=<your_agora_app_certificate>

# OpenAI API key
export OPENAI_API_KEY=<your_openai_api_key>

# Azure STT key and region
export AZURE_STT_KEY=<your_azure_stt_key>
export AZURE_STT_REGION=<your_azure_stt_region>

# Here are two TTS options, either one will work
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

<h3>Discover More</h3>

Now that you’ve created your first AI agent, the creativity doesn’t stop here. To develop more amazing agents, you’ll need an advanced understanding of how the ASTRA works under the hood. Please refer to the [ ASTRA architecture documentation ](./markdowns/astra-architecture.md).

<br>
<h2>Join Community</h2>

- [Discord](https://discord.gg/VnPftUzAMJ): Ideal for sharing your applications and engaging with the community.
- [Github Discussion](https://github.com/rte-design/astra.ai/discussions): Perfect for providing feedback and asking questions.
- [GitHub Issues](https://github.com/rte-design/astra.ai/issues): Best for reporting bugs and proposing new features. Refer to our [contribution guidelines](./markdowns/code-of-conduct/contributing.md) for more details.
- [X (formerly Twitter)](https://twitter.com/intent/follow?screen_name=AstraFramework): Great for sharing your agents and interacting with the community.

 <br>
 <h2>Code Contributors</h2>

[![ASTRA](https://contrib.rocks/image?repo=rte-design/astra.ai)](https://github.com/rte-design/astra.ai/graphs/contributors)

<br>
<h2>Contribution Guidelines</h2>

Contributions are welcome! Please read the [contribution guidelines](CONTRIBUTING.md) first.

<br>
<h2>License</h2>

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

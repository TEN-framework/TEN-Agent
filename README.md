![ASTRA Banner Image](https://github.com/rte-design/ASTRA.ai/raw/main/images/banner-image-without-tagline.png)

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

[Lightning Fast](./docs/astra-architecture.md)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[Multimodal Interactive](./docs/astra-architecture.md#astra-extension)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[Highly Customizable](./docs/astra-architecture.md#-astra-extension-store)

</div>

ASTRA is a highly customizable platform that simplifies the development of AI agents like never before. With ASTRA, you can easily create lightning-fast, multimodal AI agents, even without any coding knowledge.

<br>
<h2>Voice agent showcase</h2>

[ASTRA voice agent](https://theastra.ai)

We showcase an impressive voice agent powered by ASTRA, demonstrating its ability to create intuitive and seamless conversational interactions.

[![Showcase ASTRA Voice Agent](https://github.com/rte-design/ASTRA.ai/raw/main/images/astra-voice-agent.gif)](https://theastra.ai)


<!-- <h2>How to run voice agent locally</h2> -->


<!-- #### Prerequisite

- Agora App ID and App Certificate([read here on how](https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web))
- Azure's [speech-to-text](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) and [text-to-speech](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) API keys
- [OpenAI](https://openai.com/index/openai-api/) API key
- [Docker](https://www.docker.com/) -->

<!-- #### 2. Start the `docker-compose`

```bash
# Copy the docker-compose.yml.example file to a new file named docker-compose.yml
# remember to provide your api keys in your docker-compose.yml file
cp ./docker-compose.yml.example ./docker-compose.yml

# Execute docker compose up to start the services
docker compose up
```

#### 3. Run the voice agent
This should start the voice agent just like in the showcase. The frontend is running at localhost:3000 in your browser, and the backend is running on the Docker port 8080. -->

<!-- #### 4. Mac with apple silicon

> [!Note]
> You will need to uncheck "Use Rosetta for x86_64/amd64 emulation on apple silicon" option for Docker if you are on Apple Silicon, otherwise the server is not gonna work.

<div align="center">

![ASTRA Docker Setting](https://github.com/rte-design/ASTRA.ai/raw/main/images/docker-setting.gif)

</div> -->

<br>
<h2>How to build voice agent locally</h2>

<!-- To explore further, the ASTRA voice agent is an excellent starting point. It incorporates the following extensions, some of which will be interchangeable in the near future. Feel free to choose the ones that best suit your needs and maximize ASTRA’s capabilities.

| Extension          | Feature        | Description                                                                                                                                                                                                          |
| ------------------ | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| openai_chatgpt     | LLM            | [ GPT-4o ](https://platform.openai.com/docs/models/gpt-4o), [ GPT-4 Turbo ](https://platform.openai.com/docs/models/gpt-4-turbo-and-gpt-4), [ GPT-3.5 Turbo ](https://platform.openai.com/docs/models/gpt-3-5-turbo) |
| elevenlabs_tts     | Text-to-speech | [ElevanLabs text to speech](https://elevenlabs.io/) converts text to audio                                                                                                                                           |
| azure_tts          | Text-to-speech | [Azure text to speech](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) converts text to audio                                                                                                 |
| azure_stt          | Speech-to-text | [Azure speech to text](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) converts audio to text                                                                                                 |
| chat_transcriber   | Transcriber    | A utility ext to forward chat logs into channel                                                                                                                                                                      |
| agora_rtc          | Transporter    | A low latency transporter powered by agora_rtc                                                                                                                                                                       |
| interrupt_detector | Interrupter    | A utility ext to help interrupt agent                                                                                                                                                                                |

<h3>Voice Agent Diagram</h3>

![ASTRA voice agent diagram](./images/image-2.png) -->

<!-- To customize the agent to your needs, modify the source code of the extensions and build the agent yourself. -->

#### Prerequisite

- Agora App ID and App Certificate([read here on how](https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web))
- Azure's [speech-to-text](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) and [text-to-speech](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) API keys
- [OpenAI](https://openai.com/index/openai-api/) API key
- [Docker](https://www.docker.com/)

#### Docker setting on apple silicon
You will need to uncheck "Use Rosetta for x86_64/amd64 emulation on apple silicon" option for Docker if you are on Apple Silicon, otherwise the server is not gonna work.

<div align="center">

![ASTRA Docker Setting](https://github.com/rte-design/ASTRA.ai/raw/main/images/docker-setting.gif)

</div>

#### 1. Build the agent within Docker image

```bash
# Create manifiest from example.
cp ./agents/manifest.json.example ./agents/manifest.json

# Pull the docker image with dev tools and mount your current folder as workspace
docker run -itd -v $(pwd):/app -w /app -p 8080:8080 --name astra_agents_dev ghcr.io/rte-design/astra_agents_build

# For windows git bash
# docker run -itd -v //$(pwd):/app -w //app -p 8080:8080 --name astra_agents_dev ghcr.io/rte-design/astra_agents_build

# Enter docker image
docker exec -it astra_agents_dev bash

# Build agent
make build
```

#### 2. Modify prompts
The above code generates an agent executable, to customize your prompts and OpenAI parameters, modify the following code in `agents/addon/extension/openai_chatgpt/openai_chatgpt.go`:
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


#### 3. Start local server

Start the server by running the following terminal commands:

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


#### 4. Run the voice agent interface

The voice agent interface is built on NextJS 14, hence it needs Node 18 or later.

```bash
# Create an env file from the example so the interface points to the right port
cd playground
cp .env.example .env

# Install npm dependencies & start localhost:3000 in browser
npm install && npm run dev
```

#### 5. Verify your customized voice agent 🎉

Open `localhost:3000` in your browser, you should be seeing a voice agent just like the showcase, yet with your own customizations.

<br>
<h2>How to build the agent in a headless way</h2>

#### 1. Build the agent within Docker image

```
# Create manifest from the example file
cp ./agents/manifest.json.example ./agents/manifest.json

# Pull the docker image with dev tools and mount your current folder as workspace
docker run -itd -v $(pwd):/app -w /app -p 8080:8080 --name astra_agents_dev ghcr.io/rte-design/astra_agents_build

# For windows git bash
# docker run -itd -v //$(pwd):/app -w //app -p 8080:8080 --name astra_agents_dev ghcr.io/rte-design/astra_agents_build

# Enter docker image
docker exec -it astra_agents_dev bash

# Build agent
make build

# Start agent
cd ./agents && ./bin/start
```

#### 2. Test agent

Finally let's use [Agora Web Demo](https://webdemo.agora.io/) to test really quick.

Note the `channel` and `remote_stream_id` needs to match with the one you use on `https://webdemo.agora.io/`

After entering the corresponding RTC ID and channel name, you should be able to see the log and hear the audio output.

<br>
<h2>ASTRA Service</h2>
<h3>Discover More</h3>

Now that you’ve created your first AI agent, the creativity doesn’t stop here. To develop more amazing agents, you’ll need an advanced understanding of how the ASTRA works under the hood. Please refer to the [ ASTRA architecture documentation ](./docs/astra-architecture.md).

<br>
<h2>Stay Tuned</h2>

Before we dive further, be sure to star our repository and get instant notifications for all new releases!

![ASTRA star us gif](https://github.com/rte-design/ASTRA.ai/raw/main/images/star-the-repo-confetti-higher-quality.gif)

<br>
<h2>Join Community</h2>

- [Discord](https://discord.gg/VnPftUzAMJ): Ideal for sharing your applications and engaging with the community.
- [Github Discussion](https://github.com/rte-design/astra.ai/discussions): Perfect for providing feedback and asking questions.
- [GitHub Issues](https://github.com/rte-design/astra.ai/issues): Best for reporting bugs and proposing new features. Refer to our [contribution guidelines](./docs/code-of-conduct/contributing.md) for more details.
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

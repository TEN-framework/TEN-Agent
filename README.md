<div align="center">
 <img alt="ASTRA"  height="auto" src="./images/new-banner.png">
</div>

<br>

<div align="center">

<a href="https://discord.gg/p85NR8UD" target="_blank"><img alt="ASTRA Discord" src="https://img.shields.io/badge/Discord-@ASTRA%20-blue.svg?logo=discord"></a>
<a href="https://twitter.com/intent/follow?screen_name=AstraFramework" target="_blank">
<img src="https://img.shields.io/twitter/follow/AstraFramework?logo=X&color=%20%23f5f5f5"
            alt="follow on X"></a>
<a href="" target="_blank">
<img src="https://img.shields.io/static/v1?label=RTE&message=Real-Time Engagement&color=yellow" alt="Real time engagement" /></a>
<a href="https://github.com/rte-design/astra.ai/graphs/commit-activity" target="_blank">
<img alt="Commits" src="https://img.shields.io/github/commit-activity/m/rte-design/astra.ai?labelColor=%20%237d89b0&color=%20%235d6b98"></a>
<a href="https://github.com/rte-design/ASTRA.ai/issues" target="_blank">
<img alt="Issues closed" src="https://img.shields.io/github/issues-search?query=repo%3Arte-design%2Fastra.ai%20is%3Aclosed&label=issues%20closed&labelColor=green&color=green"></a>

</div>

<p align="center">
<a href="./README.md"><img alt="README in English" src="https://img.shields.io/badge/English-lightgrey"></a>
<a href="./README-CN.md"><img alt="简体中文" src="https://img.shields.io/badge/简体中文-lightgrey"></a>
</p>

<div align="center">
        <a href="" target="_blank">
        <span>Real-time Multi-model Interactions</span>
        </a>
        <span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
        <a href="" target="_blank">
        <span>Low Latency</span>
        </a>
        <span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
        <a href="" target="_blank">
        <span>Supporting Multiple languages</span>
        </a>
</div>

<br >

ASTRA is an open-source platform designed for developing applications utilizing large language models. It merges the ideas of Backend-as-a-Service and LLM operations, allowing developers to swiftly create production-ready generative AI applications. Additionally, it empowers non-technical users to engage in defining and managing data operations for AI applications.

With ASTRA, you can easily create real-time, multi-modal AI applications with low latency, even without any coding knowledge. 🎉

<br>

## Voice Agent

ASTRA is a versatile platform that can be used to build a wide range of applications. Here, we present a fantastic example of [an intuitive Voice Agent ](https://astra-agents.agora.io/) built on ASTRA.

<div align="center">
<img alt="ASTRA Voice Agent" src="./images/astra-voice-agent.gif">
</div>

As you can see, the real-time multimodal interactions, low latency, and responsive feedback all showcase the power of ASTRA.

### Run Voice Agent Locally

Of course, you are more than welcome to run our voice agent locally. We have a Docker image ready for you to build and run the agent on both macOS and Windows.

#### Mac with Apple Silicon

> [!NOTE]
> You will need to uncheck "Use Rosetta for x86_64/amd64 emulation on apple silicon" option for Docker if you are on Apple Silicon.
>
> ![run_on_rosetta](https://github.com/rte-design/ASTRA.ai/assets/471561/6332341c-cd18-429f-af5e-dca65e675b1c)

To start, make sure you have:

- Agora App ID and App Certificate([Read here on how](https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web))
- Azure's [speech-to-text](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) and [text-to-speech](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) API keys
- [OpenAI](https://openai.com/index/openai-api/) API key
- [Docker](https://www.docker.com/)

```bash
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

This should start an agent server running on port 8080.

### Use the playground to connect to your agent

You can use the playground project to test with the server you just started.

The Playground project is built on NextJS 14, hence it needs Node 18+.

```bash
# set up an .env file
cp ./playground/.env.example ./playground/.env
cd playground

# install npm dependencies & start
npm i && npm run dev
```

🎉 Congratulations! You now have our ASTRA powered voice agent running locally.

</br>

# Agent Customization

Our voice agent is a great place for you to start with, it uses following Extensions:

- _agora_rtc_ / [Agora](https://docs.agora.io/en) for RTC transport + VAD + Azure speech-to-text (STT)
- _azure_tts_ / [Azure](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) for text-to-speech (TTS)
- _openai_chatgpt_ / [OpenAI](https://openai.com/index/openai-api/) for LLM
- _chat_transcriber_ / A utility ext to forward chat logs into channel
- _interrupt_detector_ / A utility ext to help interrupt agent

<div align="center">

<image alt="ASTRA" width="800px" src="./images/image-2.png">

</div>

### Customize your own agent

You might want to add more flavors to make the agent better suited to your needs. To achieve this, you need to change the source code of extensions and build the agent yourselves.

You need to prepare the proper `manifest.json` file first.

```bash
# rename manifest example
cp ./agents/manifest.json.example ./agents/manifest.json

# pull the docker image with dev tools and mount your current folder as workspace
docker run -itd -v $(pwd):/app -w /app -p 8080:8080 --name astra_agents_dev agoraio/astra_agents_build

# enter docker image
docker exec -it astra_agents_dev bash

# build agent
make build
```

This code generates an agent executable. To customize your prompts and OpenAI parameters, modify the source code in agents/addon/extension/openai_chatgpt/openai_chatgpt.go.

Once you have made the necessary changes, you can use the following commands to start a server. You can then test it out using the ASTRA voice agent playground as we did in previous steps.

```bash

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

🎉 Congratulations! You have created your first personalized voice agent.

<br />

# ASTRA Service

Now let's discuss what's under the hood. The ASTRA Service is composed of various ASTRA extensions, developed in different programming languages. These extensions are interconnected using Graph, which describes their relationships and illustrates the flow of data. Furthermore, sharing and downloading extensions are simplified through the ASTRA Extension Store and the ASTRA Package Manager.

<div align="center">

<image alt="ASTRA" width="800px" src="./images/image.png">

</div>

### ASTRA Extensions

An extension is the fundamental unit of composition within the ASTRA framework. Developers can create extensions in various programming languages and combine them to build diverse scenarios and applications. ASTRA emphasizes cross-language collaboration, allowing extensions written in different languages to work together seamlessly within the same application or service.

For example, if an application requires real-time communication (RTC) features and advanced AI capabilities, a developer might choose to write RTC-related extensions in C++ for its performance advantages in processing audio and video data. Meanwhile, they could develop AI extensions in Python to leverage its extensive libraries and frameworks for data analysis and machine learning tasks.

#### Supported Languages

As of June 2024, we support extensions written in the following languages:

- C++
- Golang
- Python (planned for July)

### Graph

A Graph in ASTRA describes the data flow between extensions, orchestrating their interactions. For example, the text output from a speech-to-text (STT) extension might be directed to a large language model (LLM) extension. Essentially, a Graph defines which extensions are involved and the direction of data flow between them. Developers can customize this flow, directing outputs from one extension, such as an STT, into another, like an LLM.

In ASTRA, there are four main types of data flow between extensions:

- Command
- Data
- Image frame
- PCM frame

By specifying the direction of these data types in the Graph, developers can enable mutual invocation and unidirectional data flow between plugins. This is especially useful for PCM and image data types, simplifying audio and video processing.

### ASTRA Agent App

An ASTRA Agent App is a runnable server-side application that combines multiple Extensions following Graph rules to accomplish more sophisticated operations.

### ASTRA Extension Store

The ASTRA Store is a centralized platform where developers can share their extensions and access those created by others.

### ASTRA Package Manager

The ASTRA Package Manager simplifies the process of uploading, sharing, downloading, and installing ASTRA extensions. Extensions can specify dependencies on other extensions and the environment, and the ASTRA Package Manager automatically manages these dependencies, making the installation and release of extensions extremely convenient and intuitive.

</br>

## Contributing

Contributions are welcome! Please read the [contribution guidelines](CONTRIBUTING.md) first.

## Code Contributors

[![ASTRA](https://contrib.rocks/image?repo=rte-design/astra.ai)](https://github.com/rte-design/astra.ai/graphs/contributors)
</br>

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

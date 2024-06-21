<div align="center">
 <img alt="astra.ai" width="300px" height="auto" src="https://github.com/rte-design/ASTRA.ai/assets/471561/ef098c57-9e5c-479d-8ca5-0ad62a1a1423">
</div>

<h1 align="center">Astra AI</h1>

<div align="center">

[![](https://dcbadge.limes.pink/api/server/6k6xtWtF)](https://discord.gg/6k6xtWtF)

</div>

<div align="center">
🎉 Creation of real-time multi-modal AI Agents 🎉

Enables the rapid orchestration and reuses of the latest large model capabilities, achieves low-latency, real-time multi-modal interactions with AI Agents.

</div>

</br>

## Quick Start

### Playground

We provide a [playground](https://astra-agents.agora.io/) for you to play with.

### Local Agent

Currently, the agent we have built runs only on Linux. However, we have a Docker image ready for you to build and run the agent on Windows and macOS.

To start, make sure you have:

- Agora App ID and App Certificate([Read here on how](https://docs.agora.io/en/3.x/video-calling/reference/manage-agora-account?platform=android))
- Azure's [speech-to-text](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) and [text-to-speech](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) API keys
- [OpenAI](https://openai.com/index/openai-api/) API keys.
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
        agoraio/astra_agents_server:0.1.0
```

This should start an agent server running on port 8080.

### Use Astra AI playground to connect to your agent

You can use the playground project to test with the server you just started.

The playground project is built on NextJS 14, hence it needs Node 18+.

```shell
# set up an .env file
cp ./playground/.env.example ./playground/.env
cd playground

# install npm dependencies & start
npm i && npm run dev
```

🎉 Now you have our Astra Agent.

</br>

## Concepts

The Astra Service is built from various Astra extensions developed in different programming languages. The concept of a graph is used to describe the relationships between these extensions and illustrate the flow of data. Additionally, sharing and downloading extensions are made easy through the Astra cloud store and Astra package manager.

<div align="center">
 <img src="https://github.com/AgoraIO-Community/ASTRA.ai/assets/471561/9fd7fa08-4eff-46b0-bd50-012c8dccfd9a" width="800">
</div>

### Extension

An extension is the fundamental unit of composition. Developers can create extensions in various languages and combine them in different ways to build diverse scenarios and applications. The Astra framework emphasizes cross-language collaboration, allowing extensions written in different programming languages to seamlessly work together within the same application or service.

For example, if an application requires real-time communication (RTC) features and advanced AI capabilities, a developer might choose to write RTC-related extensions in C++ for its performance advantages in processing audio and video data. At the same time, they could develop AI extensions in Python to leverage its extensive libraries and frameworks for data analysis and machine learning tasks.

#### Supported Languages

Up until June 2024, we support extensions written in following languages,

- C++
- Golang
- Python (Planned in July)

### Graph

A graph is used to describe the data flow between extensions, a graph in Astra orchestrates how different extensions interact. For example, the text output from a speech-to-text (STT) extension might be directed to a large language model (LLM) extension. Essentially, a graph defines which extensions are involved and the direction of data flow between them. Developers can customize this flow, directing outputs from one extension, such as an STT, into another, like an LLM.

In Astra, there are four main types of data flow between extensions:

- Command
- Data
- Image frame
- PCM frame

By specifying the direction of these data types in the graph, developers can enable mutual invocation and unidirectional data flow between plugins. This is especially useful for PCM and image data types, making audio and video processing simpler and more intuitive.

### Agent App

A runnable server-side participant application compiled to combine multiple **Extensions** following **Graph** rules to accomplish more sophisticated operations.

### Cloud Store

Cloud Store is a centralized platform for developers to share their extensions and access those created by others.

### Package Manager

Simplifies the process of uploading, sharing, downloading, and installing Astra extensions. Extensions can specify dependencies on other extensions and the environment, and the package manager automatically manages these dependencies, making the installation and release of extensions extremely convenient.

</br>

# Fine-tune your agent

### Example

This project provides an example Agent App to help you get started.
It uses following Extensions:

- _agora_rtc_ / [Agora](https://docs.agora.io/en) for RTC transport + VAD + Azure speech-to-text (STT)
- _azure_tts_ / [Azure](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) for text-to-speech (TTS)
- _openai_chatgpt_ / [OpenAI](https://openai.com/index/openai-api/) for LLM
- _chat_transcriber_ / A utility ext to forward chat logs into channel
- _interrupt_detector_ / A utility ext to help interrupt agent

<div align="left">
 <img src="https://github.com/AgoraIO-Community/ASTRA.ai/assets/471561/bff35c13-e19b-43f7-ba1f-f9f0d7ec095f" width="600">
</div>

### Customize your own agent

You might want to add more flavors to make the agent better suited to your needs. To achieve this, you need to change the source code of extensions and build the agent yourselves.

You need to prepare the proper `manifest.json` file first.

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

This will generate an agent executable. We can change the source code in `agents/addon/extension/openai_chatgpt/openai_chatgpt.go` for instance to adjust your prompts and OpenAI parameters.

Once done, we can use the following commands to start a server you then can test out with Astra Agent playground like we did in previous steps.

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

</br>

## TODO

- [ ] Extension Language Support: Python
- [ ] Extension: Elevenlabs, Google, Whisper and Moondream
- [ ] Example Agent: real-time video agent
- [ ] Extension Store
- [ ] UI Graph Editor

</br>

## Code Contributors

A heartfelt thanks to all contributors!

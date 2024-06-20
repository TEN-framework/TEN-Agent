<div align="center">
 <img alt="astra.ai" width="300px" height="auto" src="https://github.com/rte-design/ASTRA.ai/assets/471561/ef098c57-9e5c-479d-8ca5-0ad62a1a1423">
</div>

# ASTRA.ai
ASTRA.ai is an agent framework that supports the creation of real-time multimodal AI Agents. It enables the rapid orchestration and reuse of the latest large model capabilities, achieving low-latency, real-time multimodal interaction with AI Agents.

ASTRA.ai is the perfect framework for building multimodal AI agents that communicate through text, vision, and audio using the latest AI capabilities, such as those from OpenAI, in real time.

## Quick Start
### Try out ASTRA.ai playground demo we deployed
We provide [a web playground](https://astra-agents.agora.io/) for you to experience.

### Run the example agent locally
Currently, the agent we build runs on Linux only, while we have prepared a Docker image so that you can build and run the agent on Windows / MacOS too.

We have prepared a prebuilt agent to help you get started right away.

To start, ensure you have following prepared,
- [Docker](https://www.docker.com/)
- We use [Agora](https://console.agora.io/) as RTC transport, so we need an agora APP_ID / APP_CERTIFICATE.
- Azure's [speech-to-text](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) and [text-to-speech](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) API keys
- [OpenAI](https://openai.com/index/openai-api/) API keys.


```
# run the prebuilt agent image
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

### Use ASTRA.ai playground to connect to your agent
You can use the playground project to test with the server you just started.

The playground project is built based on Next.js, it requires Node.js 18.17 or above.

```
# set up an .env file
cp ./playground/.env.example ./playground/.env
cd playground

# install npm dependencies & start
npm i
npm run dev
```

Greetings ASTRA.ai Agent!

## Concepts


<div align="center">
 <img src="https://github.com/AgoraIO-Community/ASTRA.ai/assets/471561/9fd7fa08-4eff-46b0-bd50-012c8dccfd9a" width="800">
</div>

### Extension
An extension is the fundamental unit of composition. Developers can create extensions in various languages and combine them in different ways to build diverse scenarios and applications. The ASTRA.ai framework emphasizes cross-language collaboration, allowing extensions written in different programming languages to seamlessly work together within the same application or service.

For example, if an application requires real-time communication (RTC) features and advanced AI capabilities, a developer might choose to write RTC-related extensions in C++ for its performance advantages in processing audio and video data. At the same time, they could develop AI extensions in Python to leverage its extensive libraries and frameworks for data analysis and machine learning tasks.

### Graph
A graph is used to describe the data flow between extensions, a graph in ASTRA orchestrates how different extensions interact. For example, the text output from a speech-to-text (STT) extension might be directed to a large language model (LLM) extension. Essentially, a graph defines which extensions are involved and the direction of data flow between them. Developers can customize this flow, directing outputs from one extension, such as an STT, into another, like an LLM.

In ASTRA, there are four main types of data flow between extensions:

- Command
- Data
- Image frame
- PCM frame

By specifying the direction of these data types in the graph, developers can enable mutual invocation and unidirectional data flow between plugins. This is especially useful for PCM and image data types, making audio and video processing simpler and more intuitive.

### Agent App
A runnable server-side participant application compiled to combine multiple **Extensions** following **Graph** rules to accomplish more sophisticated operations.


### ASTRA Cloud Store
Cloud Store is a hub for developers to share their extensions or use extensions from other developers.

### ASTRA Package Manager
Simplifies the process of uploading, sharing, downloading, and installing ASTRA extensions. Extensions can specify dependencies on other extensions and the environment, and the package manager automatically manages these dependencies, making the installation and release of extensions extremely convenient.


## Fine-tune your agent
### Example
This project provides an example Agent App to help you get started.
It uses following Extensions:
- *agora_rtc* / [Agora](https://docs.agora.io/en) for RTC transport + VAD + Azure speech-to-text (STT)
- *azure_tts* / [Azure](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) for text-to-speech (TTS)
- *openai_chatgpt* / [OpenAI](https://openai.com/index/openai-api/) for LLM
- *chat_transcriber* / A utility ext to forward chat logs into channel
- *interrupt_detector* / A utility ext to help interrupt agent

<div align="left">
 <img src="https://github.com/AgoraIO-Community/ASTRA.ai/assets/471561/bff35c13-e19b-43f7-ba1f-f9f0d7ec095f" width="600">
</div>

### Customize your own agent
We might want to add more flavours and customizations to make the agent better suited to our needs. To achieve this, we need to change the source code of extensions and build the agent ourselves.

We need to prepare the proper `manifest.json` file first.

```
# rename manifest example
cp ./agents/manifest.json.example ./agents/manifest.json

# pull the docker image with dev tools and mount your current folder as workspace
docker run -itd -v $(pwd):/app -w /app -p 8080:8080 --name astra_agents_dev agoraio/astra_agents_build:0.1.0

# enter docker image
docker exec -it astra_agents_dev bash

# build agent
make build
```

This will generate an agent executable. We can change the source code in `agents/addon/extension/openai_chatgpt/openai_chatgpt.go` for instance to adjust your prompt and openai parameters.
Once done, we can use the following command to start a server which you can test out with ASTRA.ai playground like we did in previous steps.

```
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

## TODO
- [ ] Extension Support: Python
- [ ] Extension: elevenlabs, google, whisper, moondream
- [ ] Example Agent: real-time video agent
- [ ] Extension Store
- [ ] UI Graph Editor
- ...
Stay tuned!

## Code Contributors
Thanks to all contributors!

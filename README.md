<div align="center">
 <img alt="astra.ai" width="300px" height="auto" src="https://github.com/AgoraIO-Community/ASTRA.ai/assets/471561/20ae3baa-5f84-44b6-8a17-19ca70d37c95">
</div>

# ASTRA.ai
ASTRA.ai is an agent framework that supports the creation of real-time multimodal AI Agents. It enables the rapid orchestration and reuse of the latest large model capabilities, achieving low-latency, real-time multimodal interaction with AI Agents.

ASTRA.ai is the perfect framework for building multimodal AI agents that communicate through text, vision, and audio using the latest AI capabilities, such as those from OpenAI, in real time.

## Concepts
- **Extension**: An extension created to perform tasks using multimodal input/output, such as speech-to-text (audio to text), text-to-speech (text to audio), and LLM (text to text), from a specific provider.
- **Graph**: A set of programmable rules that define how control and data flows between different **Extensions**.
- **Agent App**: A runnable server-side participant application compiled to combine multiple **Extensions** following **Graph** rules to accomplish more sophisticated operations.

<div align="center">
 <img src="https://github.com/AgoraIO-Community/ASTRA.ai/assets/471561/9fd7fa08-4eff-46b0-bd50-012c8dccfd9a" width="800">
</div>

## Example

This project provides an example Agent App to help you get started.
We'll use following Extensions:
- *agora_rtc* / [Agora](https://docs.agora.io/en) for RTC transport + VAD + Azure speech-to-text (STT)
- *azure_tts* / [Azure](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) for text-to-speech (TTS)
- *openai_chatgpt* / [OpenAI](https://openai.com/index/openai-api/) for LLM
- *chat_transcriber* / A utility ext to forward chat logs into channel
- *interrupt_detector* / A utility ext to help interrupt agent

We also provide a web playground to help you test with the agent you built.

<div align="center">
 <img src="https://github.com/AgoraIO-Community/ASTRA.ai/assets/471561/d6bffda1-52fa-470c-866f-2e7836e239ea" width="800">
</div>
## Running Locally
Currently, the agent we build runs on Linux only, while we have prepared a Docker image so that you can build and run the agent on Windows / MacOS too.

To start, ensure you have Docker installed.
We need to prepare the proper `manifest.json` file first.

```
# set up a manifest file with API keys
cp ./agents/manifest.json.example ./agents/manifest.json
```

```
# pull the docker image with dev tools and mount your current folder as workspace
docker run -itd -v $(pwd):/app -w /app -p 8080:8080 --name astra_agents_dev agoraio/astra_agents_build:0.1.0

# enter docker image
docker exec -it astra_agents_dev bash

# build agent
make build
```

We use Agora as RTC transport, so we also need an [Agora](https://console.agora.io/) APP_ID / APP_CERTIFICATE.

We use Azure's [speech-to-text](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) and [text-to-speech](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) services.

We use OpenAI's [API](https://openai.com/index/openai-api/) service.
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

## Playground

You can use the playground project to test with the server you just started.

The playground project is built based on Next.js, it requires Node.js 18.17 or above.

```
# set up an .env file with AGORA_APP_ID and AGORA_APP_CERTIFICATE
cp ./playground/.env.example ./playground/.env

cd playground

# install npm dependencies & start
npm i
npm run dev
```

Greetings ASTRA.ai Agent!

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

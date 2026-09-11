<div align="center" id="readme-top">

![Image][ten-framework-banner]

[![TEN Releases][ten-releases-badge]][ten-releases]
[![Coverage Status][coverage-badge]][coverage]
[![Release Date][release-date-badge]][ten-releases]
[![Commits][commits-badge]][commit-activity]
[![Issues closed][issues-closed-badge]][issues-closed]
[![Contributors][contributors-badge]][contributors]
[![GitHub license][license-badge]][license]
[![Ask DeepWiki][deepwiki-badge]][deepwiki]
[![ReadmeX][readmex-badge]][readmex]

[![README in English][lang-en-badge]][lang-en-readme]
[![简体中文操作指南][lang-zh-badge]][lang-zh-readme]
[![日本語のREADME][lang-jp-badge]][lang-jp-readme]
[![README in 한국어][lang-kr-badge]][lang-kr-readme]
[![README en Español][lang-es-badge]][lang-es-readme]
[![README en Français][lang-fr-badge]][lang-fr-readme]
[![README in Italiano][lang-it-badge]][lang-it-readme]

<a href="https://trendshift.io/repositories/13772?utm_source=repository-badge&amp;utm_medium=badge&amp;utm_campaign=badge-repository-13772" target="_blank" rel="noopener noreferrer"><img src="https://trendshift.io/api/badge/repositories/13772" alt="TEN-framework%2Ften-framework | Trendshift" width="250" height="55"/></a>

[Official Site][official-site] •
[Documentation][documentation] •
[Blog][blog]

</div>

<br>

<details open>
  <summary><kbd>Table of Contents</kbd></summary>

  <br>

- [Welcome to TEN][welcome-to-ten]
- [Agent Examples][agent-examples-section]
- [Quick Start with Agent Examples][quick-start]
  - [Localhost][localhost-section]
  - [Codespaces][codespaces-section]
- [Agent Examples Self-Hosting][agent-examples-self-hosting]
  - [Deploying with Docker][deploying-with-docker]
  - [Deploying with other cloud services][deploying-with-other-cloud-services]
- [Stay Tuned][stay-tuned]
- [TEN Ecosystem][ten-ecosystem-anchor]
- [Questions][questions]
- [Contributing][contributing]
  - [Code Contributors][code-contributors]
  - [Contribution Guidelines][contribution-guidelines]
  - [License][license-section]

<br/>

</details>

## Welcome to TEN

TEN is an open-source framework for real-time multimodal conversational AI.

[TEN Ecosystem][ten-ecosystem-anchor] includes [TEN Framework][ten-framework], [Agent Examples][agent-examples-repo], [VAD][ten-vad], [Turn Detection][ten-turn-detection] and [Portal][ten-portal].

<br>

| Community Channel | Purpose |
| ---------------- | ------- |
| [![Follow on X][follow-on-x-badge]][follow-on-x] | Follow TEN Framework on X for updates and announcements |
| [![Discord TEN Community][discord-badge]][discord-invite] | Join our Discord community to connect with developers |
| [![Follow on LinkedIn][linkedin-badge]][linkedin] | Follow TEN Framework on LinkedIn for updates and announcements |
| [![Hugging Face Space][hugging-face-badge]][hugging-face] | Join our Hugging Face community to explore our spaces and models |

<br>

## Agent Examples

<br>

![Image][voice-assistant-image]

<strong>Multi-Purpose Voice Assistant</strong> — This low-latency, high-quality real-time assistant supports both RTC and [WebSocket][websocket-example] connections, and you can extend it with [Memory][memory-example], [VAD][voice-assistant-vad-example], [Turn Detection][voice-assistant-turn-detection-example], and other extensions.

See the [Example code][voice-assistant-example] for more details.

<br>

![divider][divider-light]
![divider][divider-dark]

<br>


![Image][doodler-image]

<strong>Doodler</strong> — A doodle board that turns spoken or typed prompts into simple hand-drawn sketches, complete with a crayon palette and real-time drawing.

[Example code][doodler-example]

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

![Image][speaker-diarization-image]

<strong>Speaker Diarization</strong> — Real-time diarization that detects and labels speakers, the Who Likes What game shows an interactive use case.

[Example code][speechmatics-diarization-example]

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

![Image][lip-sync-image]


<strong>Lip Sync Avatars</strong> — Works with multiple avatar vendors, the main character features Kei, an anime character with MotionSync-powered lip sync, and also supports realistic avatars from Trulience, HeyGen, and Tavus.

See the [Example code][voice-assistant-live2d-example] for different Live2D characters.

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

![Image][sip-call-image]

<strong>SIP Call</strong> — SIP extension that enables phone calls powered by TEN.

[Example code][voice-assistant-sip-example]

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

![Image][transcription-image]

<strong>Transcription</strong> — A transcription tool that transcribes audio to text.

[Example code][transcription-example]

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

![Image][esp32-image]

<strong>ESP32-S3 Korvo V3</strong> — Runs TEN agent example on the Espressif ESP32-S3 Korvo V3 development board to integrate LLM-powered communication with hardware.

See the [integration guide][esp32-guide] for more details.

<br>
<div align="right">

[![][back-to-top]][readme-top]

</div>

## Quick Start with Agent Examples

### Localhost

#### Step ⓵ - Prerequisites

| Category | Requirements |
| --- | --- |
| **Keys** | • Agora [App ID][agora-app-id] and [App Certificate][agora-app-certificate]<br>• [OpenAI][openai-api] API key<br>• [Deepgram][deepgram] ASR <br>• [ElevenLabs][elevenlabs] TTS  |
| **Installation** | • [Docker][docker] / [Docker Compose][docker-compose]<br>• [Node.js (LTS) v18][nodejs] |
| **Minimum System Requirements** | • CPU >= 2 cores<br>• RAM >= 4 GB |

<br>

![divider][divider-light]
![divider][divider-dark]

<!-- > [!NOTE]
> **macOS: Docker setting on Apple Silicon**
>
> Uncheck "Use Rosetta for x86/amd64 emulation" in Docker settings, it may result in slower build times on ARM, but performance will be normal when deployed to x64 servers. -->

#### Step ⓶ - Build agent examples in VM

##### 1. Clone the repo, `cd` into `ai_agents`, and create a `.env` file from `.env.example`

```bash
cd ai_agents
cp ./.env.example ./.env
```

##### 2. Set up the Agora App ID and App Certificate in `.env`

```bash
AGORA_APP_ID=
AGORA_APP_CERTIFICATE=

# Deepgram (required for speech-to-text)
DEEPGRAM_API_KEY=

# OpenAI (required for language model)
OPENAI_API_KEY=

# ElevenLabs (required for text-to-speech)
ELEVENLABS_TTS_KEY=
```

##### 3. Start agent development containers

```bash
docker compose up -d
```

##### 4. Enter the container

```bash
docker exec -it ten_agent_dev bash
```

##### 5. Build the agent with the default example (~5-8 min)

Check the `agents/examples` folder for additional samples.
Start with one of these defaults:

```bash
# use the chained voice assistant
cd agents/examples/voice-assistant

# or use the speech-to-speech voice assistant in real time
cd agents/examples/voice-assistant-realtime
```

##### 6. Start the web server

Run `task install` before the first launch and after changing dependencies or Go source code. It installs the TEN, Python, and frontend dependencies and builds the Go API server. Python-only source changes do not require reinstalling.

```bash
task install
task run
```

##### 7. Access the agent

Once the agent example is running, you can access the following interfaces:

| **localhost:49483** | **localhost:3000** |
| :-----------------: | :----------------: |
| ![Screenshot 1][localhost-49483-image] | ![Screenshot 2][localhost-3000-image] |

- TMAN Designer: [localhost:49483][localhost-49483]
- Agent Examples UI: [localhost:3000][localhost-3000]

<br>

![divider][divider-light]
![divider][divider-dark]

#### Step ⓷ - Customize your agent example

1. Open [localhost:49483][localhost-49483].
2. Right-click the STT, LLM, and TTS extensions.
3. Open their properties and enter the corresponding API keys.
4. Submit your changes, now you can see the updated Agent Example in [localhost:3000][localhost-3000].

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

#### Run a transcriber app from TEN Manager without Docker (Beta)

TEN also provides a transcriber app that you can run from TEN Manager without using Docker.

Check the [quick start guide][quick-start-guide-ten-manager] for more details.

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

### Codespaces

GitHub offers free Codespaces for each repository. You can run Agent Examples in Codespaces without using Docker. Codespaces typically start faster than local Docker environments.

[![][codespaces-shield]][codespaces-new]

Check out [this guide][codespaces-guide] for more details.

<div align="right">

[![][back-to-top]][readme-top]

</div>

<br>

## Agent Examples Self-Hosting

### Deploying with Docker

Once you have customized your agent (either by using the TMAN Designer or editing `property.json` directly), you can deploy it by creating a release Docker image for your service.

##### Release as Docker image

**Note**: The following commands need to be executed outside of any Docker container.

###### Build image

```bash
cd ai_agents
docker build -f agents/examples/<example-name>/Dockerfile -t example-app .
```

###### Run

```bash
docker run --rm -it --env-file .env -p 3000:3000 example-app
```

<br>

![divider][divider-light]
![divider][divider-dark]

### Deploying with other cloud services

You can split the deployment into two pieces when you want to host TEN on providers such as [Vercel][vercel] or [Netlify][netlify].

1. Run the TEN backend on any container-friendly platform (a VM with Docker, Fly.io, Render, ECS, Cloud Run, or similar). Use the example Docker image without modifying it and expose port `8080` from that service.

2. Deploy only the frontend to Vercel or Netlify. Point the project root to `ai_agents/agents/examples/<example>/frontend`, run `pnpm install` (or `bun install`) followed by `pnpm build` (or `bun run build`), and keep the default `.next` output directory.

3. Configure environment variables in your hosting dashboard so that `AGENT_SERVER_URL` points to the backend URL, and add any `NEXT_PUBLIC_*` keys the UI needs (for example, Agora credentials you surface to the browser).

4. Ensure your backend accepts requests from the frontend origin — via open CORS or by using the built-in proxy middleware.

With this setup, the backend handles long-running worker processes, while the hosted frontend simply forwards API traffic to it.

<div align="right">

[![][back-to-top]][readme-top]

</div>

<br>

## Stay Tuned

Get instant notifications for new releases and updates. Your support helps us grow and improve TEN!

<br>

![Image][stay-tuned-image]

<br>
<div align="right">

[![][back-to-top]][readme-top]

</div>

<br>

## TEN Ecosystem

<br>

| Project | Preview |
| ------- | ------- |
| [**️TEN Framework**][ten-framework-link]<br>Open-source framework for conversational AI Agents.<br><br>![][ten-framework-shield] | ![][ten-framework-banner] |
| [**TEN VAD**][ten-vad-link]<br>Low-latency, lightweight and high-performance streaming voice activity detector (VAD).<br><br>![][ten-vad-shield] | ![][ten-vad-banner] |
| [**️ TEN Turn Detection**][ten-turn-detection-link]<br>TEN Turn Detection enables full-duplex dialogue communication.<br><br>![][ten-turn-detection-shield] | ![][ten-turn-detection-banner] |
| [**TEN Agent Examples**][ten-agent-example-link]<br>Usecases powered by TEN.<br><br> | ![][ten-agent-example-banner] |
| [**TEN Portal**][ten-portal-link]<br>The official site of the TEN Framework with documentation and a blog.<br><br>![][ten-portal-shield] | ![][ten-portal-banner] |

<br>
<div align="right">

[![][back-to-top]][readme-top]

</div>

<br>

## Questions

TEN Framework is available on these AI-powered Q&A platforms. They can help you find answers quickly and accurately in multiple languages, covering everything from basic setup to advanced implementation details.

| Service | Link |
| ------- | ---- |
| DeepWiki | [![Ask DeepWiki][deepwiki-badge]][deepwiki] |
| ReadmeX | [![ReadmeX][readmex-badge]][readmex] |

<br>
<div align="right">

[![][back-to-top]][readme-top]

</div>

## Contributing

We welcome all forms of open-source collaboration! Whether you're fixing bugs, adding features, improving documentation, or sharing ideas, your contributions help advance personalized AI tools. Check out our GitHub Issues and Projects to find ways to contribute and show your skills. Together, we can build something amazing!

<br>

> [!TIP]
>
> **Welcome all kinds of contributions** 🙏
>
> Join us in building TEN better! Every contribution makes a difference, from code to documentation. Share your TEN Agent projects on social media to inspire others!
>
> Connect with one of the TEN maintainers [@elliotchen200][elliotchen200-x] on 𝕏 or [@cyfyifanchen][cyfyifanchen-github] on GitHub for project updates, discussions, and collaboration opportunities.

<br>

![divider][divider-light]
![divider][divider-dark]

### Code Contributors

[![TEN][contributors-image]][contributors]

### Contribution Guidelines

Contributions are welcome! Please read the [contribution guidelines][contribution-guidelines-doc] first.

<br>

![divider][divider-light]
![divider][divider-dark]

### License

1. The entire TEN framework (except for the folders explicitly listed below) is released pursuant the Apache License, Version 2.0, with additional restrictions. For details, please refer to the [LICENSE][license-file] file located in the root directory of the TEN framework.

2. The components within the `packages` directory are released under the Apache License, Version 2.0. For details, please refer to the `LICENSE` file located in each package's root directory.

3. The third-party libraries used by the TEN framework are listed and described in detail. For more information, please refer to the [third_party][third-party-folder] folder.

<div align="right">

[![][back-to-top]][readme-top]

</div>

[back-to-top]: https://img.shields.io/badge/-Back_to_top-gray?style=flat-square
[readme-top]: #readme-top

<!-- Navigation -->
[welcome-to-ten]: #welcome-to-ten
[agent-examples-section]: #agent-examples
[quick-start]: #quick-start-with-agent-examples
[localhost-section]: #localhost
[codespaces-section]: #codespaces
[agent-examples-self-hosting]: #agent-examples-self-hosting
[deploying-with-docker]: #deploying-with-docker
[deploying-with-other-cloud-services]: #deploying-with-other-cloud-services
[stay-tuned]: #stay-tuned
[ten-ecosystem-anchor]: #ten-ecosystem
[questions]: #questions
[contributing]: #contributing
[code-contributors]: #code-contributors
[contribution-guidelines]: #contribution-guidelines
[license-section]: #license

<!-- Header badges -->
[ten-releases-badge]: https://img.shields.io/github/v/release/ten-framework/ten-framework?color=369eff&labelColor=gray&logo=github&style=flat-square
[ten-releases]: https://github.com/TEN-framework/ten-framework/releases
[coverage-badge]: https://coveralls.io/repos/github/TEN-framework/ten-framework/badge.svg?branch=main
[coverage]: https://coveralls.io/github/TEN-framework/ten-framework?branch=main
[release-date-badge]: https://img.shields.io/github/release-date/ten-framework/ten-framework?labelColor=gray&style=flat-square
[commits-badge]: https://img.shields.io/github/commit-activity/m/TEN-framework/ten-framework?labelColor=gray&color=pink
[commit-activity]: https://github.com/TEN-framework/ten-framework/graphs/commit-activity
[issues-closed-badge]: https://img.shields.io/github/issues-search?query=repo%3ATEN-framework%2Ften-framework%20is%3Aclosed&label=issues%20closed&labelColor=gray&color=green
[issues-closed]: https://github.com/TEN-framework/ten-framework/issues
[contributors-badge]: https://img.shields.io/github/contributors/ten-framework/ten-framework?color=c4f042&labelColor=gray&style=flat-square
[contributors]: https://github.com/TEN-framework/ten-framework/graphs/contributors
[license-badge]: https://img.shields.io/badge/License-Apache_2.0_with_certain_conditions-blue.svg?labelColor=%20%23155EEF&color=%20%23528bff
[license]: https://github.com/TEN-framework/ten-framework/blob/main/LICENSE
[deepwiki-badge]: https://deepwiki.com/badge.svg
[deepwiki]: https://deepwiki.com/TEN-framework/TEN-framework
[readmex-badge]: https://raw.githubusercontent.com/CodePhiliaX/resource-trusteeship/main/readmex.svg
[readmex]: https://readmex.com/TEN-framework/ten-framework
[trendshift-badge]: https://trendshift.io/api/badge/repositories/11978
[trendshift]: https://trendshift.io/repositories/11978

<!-- Localized READMEs -->
[lang-en-badge]: https://img.shields.io/badge/English-lightgrey
[lang-en-readme]: https://github.com/TEN-framework/ten-framework/blob/main/README.md
[lang-zh-badge]: https://img.shields.io/badge/简体中文-lightgrey
[lang-zh-readme]: https://github.com/TEN-framework/ten-framework/blob/main/docs/README-CN.md
[lang-jp-badge]: https://img.shields.io/badge/日本語-lightgrey
[lang-jp-readme]: https://github.com/TEN-framework/ten-framework/blob/main/docs/README-JP.md
[lang-kr-badge]: https://img.shields.io/badge/한국어-lightgrey
[lang-kr-readme]: https://github.com/TEN-framework/ten-framework/blob/main/docs/README-KR.md
[lang-es-badge]: https://img.shields.io/badge/Español-lightgrey
[lang-es-readme]: https://github.com/TEN-framework/ten-framework/blob/main/docs/README-ES.md
[lang-fr-badge]: https://img.shields.io/badge/Français-lightgrey
[lang-fr-readme]: https://github.com/TEN-framework/ten-framework/blob/main/docs/README-FR.md
[lang-it-badge]: https://img.shields.io/badge/Italiano-lightgrey
[lang-it-readme]: https://github.com/TEN-framework/ten-framework/blob/main/docs/README-IT.md

<!-- Primary sites -->
[official-site]: https://theten.ai
[documentation]: https://theten.ai/docs
[blog]: https://theten.ai/blog

<!-- Welcome -->
[ten-framework]: https://github.com/ten-framework/ten-framework
[agent-examples-repo]: https://github.com/TEN-framework/ten-framework/tree/main/ai_agents/agents/examples
[ten-vad]: https://github.com/ten-framework/ten-vad
[ten-turn-detection]: https://github.com/ten-framework/ten-turn-detection
[ten-portal]: https://github.com/ten-framework/portal

<!-- Community -->
[follow-on-x-badge]: https://img.shields.io/twitter/follow/TenFramework?logo=X&color=%20%23f5f5f5
[follow-on-x]: https://twitter.com/intent/follow?screen_name=TenFramework
[discord-badge]: https://img.shields.io/badge/Discord-Join%20TEN%20Community-5865F2?style=flat&logo=discord&logoColor=white
[discord-invite]: https://discord.gg/VnPftUzAMJ
[linkedin-badge]: https://custom-icon-badges.demolab.com/badge/LinkedIn-TEN_Framework-0A66C2?logo=linkedin-white&logoColor=fff
[linkedin]: https://www.linkedin.com/company/ten-framework
[hugging-face-badge]: https://img.shields.io/badge/Hugging%20Face-TEN%20Framework-yellow?style=flat&logo=huggingface
[hugging-face]: https://huggingface.co/TEN-framework
[wechat-badge]: https://img.shields.io/badge/TEN_Framework-WeChat_Group-%2307C160?logo=wechat&labelColor=darkgreen&color=gray
[wechat-discussion]: https://github.com/TEN-framework/ten-agent/discussions/170

<!-- Agent examples -->
[voice-assistant-image]: https://github.com/user-attachments/assets/dce3db80-fb48-4e2a-8ac7-33f50bcffa32
[websocket-example]: ai_agents/agents/examples/websocket-example
[memory-example]: ai_agents/agents/examples/voice-assistant-with-memU
[voice-assistant-vad-example]: ai_agents/agents/examples/voice-assistant-with-ten-vad
[voice-assistant-turn-detection-example]: ai_agents/agents/examples/voice-assistant-with-turn-detection
[voice-assistant-example]: ai_agents/agents/examples/voice-assistant
[divider-light]: https://github.com/user-attachments/assets/aec54c94-ced9-4683-ae58-0a5a7ed803bd#gh-light-mode-only
[divider-dark]: https://github.com/user-attachments/assets/d57fad08-4f49-4a1c-bdfc-f659a5d86150#gh-dark-mode-only
[lip-sync-image]: https://github.com/user-attachments/assets/51ab1504-b67c-49d4-8a7a-5582d9b254da
[voice-assistant-live2d-example]: ai_agents/agents/examples/voice-assistant-live2d
[speaker-diarization-image]: https://github.com/user-attachments/assets/f94b21b8-9dda-4efc-9274-b028cc01296a
[speechmatics-diarization-example]: ai_agents/agents/examples/speaker-diarization
[sip-call-image]: https://github.com/user-attachments/assets/6ed5b04d-945a-4a30-a1cc-f8014b602b38
[voice-assistant-sip-example]: ai_agents/agents/examples/voice-assistant-sip-twilio
[transcription-image]: https://github.com/user-attachments/assets/d793bc6c-c8de-4996-bd85-9ce88c69dd8d
[transcription-example]: ai_agents/agents/examples/transcription
[doodler-image]: https://github.com/user-attachments/assets/80c4eabd-de96-4971-8956-6b365d4fbd64
[doodler-example]: ai_agents/agents/examples/doodler
[esp32-image]: https://github.com/user-attachments/assets/3d60f1ff-0f82-4fe7-b5c2-ac03d284f60c
[esp32-guide]: ai_agents/esp32-client

<!-- Quick start -->
[agora-app-id]: https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web#create-an-agora-project
[agora-app-certificate]: https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web#create-an-agora-project
[openai-api]: https://openai.com/index/openai-api/
[deepgram]: https://deepgram.com/
[elevenlabs]: https://elevenlabs.io/
[docker]: https://www.docker.com/
[docker-compose]: https://docs.docker.com/compose/
[nodejs]: https://nodejs.org/en
[quick-start-guide-ten-manager]: https://theten.ai/docs/ten_framework/getting-started/quick-start
[localhost-49483-image]: https://github.com/user-attachments/assets/191a7c0a-d8e6-48f9-866f-6a70c58f0118
[localhost-3000-image]: https://github.com/user-attachments/assets/13e482b6-d907-4449-a779-9454bb24c0b1
[localhost-49483]: http://localhost:49483
[localhost-3000]: http://localhost:3000

<!-- Codespaces -->
[codespaces-shield]: https://github.com/codespaces/badge.svg
[codespaces-new]: https://codespaces.new/ten-framework/ten-agent
[codespaces-guide]: https://theten.ai/docs/ten_agent_examples/setup_development_env/setting_up_development_inside_codespace

<!-- Deployment -->
[vercel]: https://vercel.com
[netlify]: https://www.netlify.com

<!-- Stay tuned -->
[stay-tuned-image]: https://github.com/user-attachments/assets/72c6cc46-a2a2-484d-82a9-f3079269c815

<!-- TEN ecosystem -->
[ten-framework-shield]: https://img.shields.io/github/stars/ten-framework/ten-framework?color=ffcb47&labelColor=gray&style=flat-square&logo=github
[ten-framework-banner]: https://github.com/user-attachments/assets/a99e13c5-aca4-4b28-bedf-10c89eedcd86
[ten-framework-link]: https://github.com/ten-framework/ten-framework

[ten-vad-link]: https://github.com/ten-framework/ten-vad
[ten-vad-shield]: https://img.shields.io/github/stars/ten-framework/ten-vad?color=ffcb47&labelColor=gray&style=flat-square&logo=github
[ten-vad-banner]: https://github.com/user-attachments/assets/e504135e-67fd-4fa1-b0e4-d495358d8aa5

[ten-turn-detection-link]: https://github.com/ten-framework/ten-turn-detection
[ten-turn-detection-shield]: https://img.shields.io/github/stars/ten-framework/ten-turn-detection?color=ffcb47&labelColor=gray&style=flat-square&logo=github
[ten-turn-detection-banner]: https://github.com/user-attachments/assets/c72d82cc-3667-496c-8bd6-3d194a91c452

[ten-agent-example-link]: https://github.com/TEN-framework/ten-framework/tree/main/ai_agents/agents/examples
[ten-agent-example-banner]: https://github.com/user-attachments/assets/7f735633-c7f6-4432-b6b4-d2a2977ca588

[ten-portal-link]: https://github.com/ten-framework/portal
[ten-portal-shield]: https://img.shields.io/github/stars/ten-framework/portal?color=ffcb47&labelColor=gray&style=flat-square&logo=github
[ten-portal-banner]: https://github.com/user-attachments/assets/f56c75b9-722c-4156-902d-ae98ce2b3b5e

<!-- Contributing -->
[elliotchen200-x]: https://x.com/elliotchen200
[cyfyifanchen-github]: https://github.com/cyfyifanchen
[contributors-image]: https://contrib.rocks/image?repo=TEN-framework/ten-framework
[contribution-guidelines-doc]: ./docs/code-of-conduct/contributing.md
[license-file]: ./LICENSE
[third-party-folder]: ./third_party/

<div align="center">

[![Follow on X](https://img.shields.io/twitter/follow/ten_platform?logo=X&color=%20%23f5f5f5)](https://twitter.com/intent/follow?screen_name=ten_platform)
[![Discussion posts](https://img.shields.io/github/discussions/rte-design/astra.ai?labelColor=%20%23FDB062&color=%20%23f79009)](https://github.com/rte-design/astra.ai/discussions/)
[![Commits](https://img.shields.io/github/commit-activity/m/rte-design/astra.ai?labelColor=%20%237d89b0&color=%20%235d6b98)](https://github.com/rte-design/astra.ai/graphs/commit-activity)
[![Issues closed](https://img.shields.io/github/issues-search?query=repo%3Arte-design%2Fastra.ai%20is%3Aclosed&label=issues%20closed&labelColor=green&color=green)](https://github.com/rte-design/ASTRA.ai/issues)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](https://github.com/rte-design/ASTRA.ai/pulls)
[![GitHub license](https://img.shields.io/badge/License-Apache_2.0-blue.svg?labelColor=%20%239b8afb&color=%20%237a5af8)](https://github.com/rte-design/ASTRA.ai/blob/main/LICENSE)

[![Discord TEN Community](https://dcbadge.vercel.app/api/server/VnPftUzAMJ)](https://discord.gg/VnPftUzAMJ)

[![GitHub watchers](https://img.shields.io/github/watchers/rte-design/astra.ai?style=social&label=Watch)](https://GitHub.com/rte-design/astra.ai/watchers/?WT.mc_id=academic-105485-koreyst)
[![GitHub forks](https://img.shields.io/github/forks/rte-design/astra.ai?style=social&label=Fork)](https://GitHub.com/rte-design/astra.ai/network/?WT.mc_id=academic-105485-koreyst)
[![GitHub stars](https://img.shields.io/github/stars/rte-design/astra.ai?style=social&label=Star)](https://GitHub.com/rte-design/astra.ai/stargazers/?WT.mc_id=academic-105485-koreyst)

<a href="../../README.md"><img alt="README in English" src="https://img.shields.io/badge/English-lightgrey"></a>
<a href="../readmes/README-CN.md"><img alt="简体中文" src="https://img.shields.io/badge/简体中文-lightgrey"></a>
<a href="../readmes/README-JP.md"><img alt="日本語" src="https://img.shields.io/badge/日本語-lightgrey"></a>
<a href="../readmes/README-KR.md"><img alt="한국어" src="https://img.shields.io/badge/한국어-lightgrey"></a>

[문서](https://astra-9.gitbook.io/ten-platform)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[시작하기](https://astra-9.gitbook.io/ten-platform/getting-started/quickstart)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[튜토리얼](https://app.gitbook.com/o/we7IoLK5sA6RQzhItfkW/s/4KgjqM5ChU0dSGjTLZmG/~/changes/6/tutorials/how-to-build-extension-with-go)

</div>

<br>
<h2>Voice agent: Astra</h2>

[보이스 에이전트: Astra](https://theastra.ai)

Astra는 TEN을 통해 구동되는 보이스 에이전트로, 직관적이고 원활한 대화 상호작용을 만들어내는 능력을 보여줍니다.

[![Astra 쇼케이스](https://github.com/rte-design/docs/blob/main/assets/gifs/astra-voice-agent.gif?raw=true)](https://theastra.ai)
<br>
<h2>로컬에서 보이스 에이전트 구축하는 방법

### 전제 조건

#### 키
- Agora 앱 ID 및 앱 인증서([여기서 방법 읽기](https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web))
- Azure의 [음성-텍스트](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) 및 [텍스트-음성](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) API 키
- [OpenAI](https://openai.com/index/openai-api/) API 키

#### 설치
  - [Docker](https://www.docker.com/) / [Docker Compose](https://docs.docker.com/compose/)
  - [Node.js(LTS) v18](https://nodejs.org/en)

#### 최소 시스템 요구 사항
  - CPU >= 2 코어
  - RAM >= 4 GB

#### Apple Silicon에서의 Docker 설정
Apple Silicon을 사용하는 경우 Docker의 "Use Rosetta for x86_64/amd64 emulation on Apple Silicon" 옵션을 선택 해제해야 합니다. 그렇지 않으면 서버가 작동하지 않습니다.

![Docker 설정](https://github.com/rte-design/docs/blob/main/assets/gifs/docker-setting.gif?raw=true)

### 다음 단계

#### 1. 설정 파일 수정
프로젝트 루트에서 예제 파일로부터 이 파일들을 생성하세요. 나중에 Docker Compose를 위한 정보를 저장하는 데 사용됩니다.
```bash
# .env 예제로부터 .env 생성
cp ./.env.example ./.env

# property.json 예제로부터 property.json 생성
cp ./agents/property.json.example ./agents/property.json
```

#### 2. API 키 설정
`.env` 파일을 열고 키와 지역을 입력하세요. 다른 확장 기능을 사용하려면 이곳에서 선택할 수 있습니다:

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

#### 3. 에이전트 개발 컨테이너 시작
같은 디렉토리에서 `docker` 명령어를 실행하여 컨테이너를 구성합니다:
```bash
# Execute docker compose up to start the services
docker compose up
```

#### 4. 에이전트 빌드 및 서버 시작
별도의 터미널 창을 열고, 에이전트를 빌드하고 서버를 시작합니다:
```bash
# Enter container to build agent
docker exec -it astra_agents_dev bash
make build

# Once the build is done, run server on port 8080
make run-server
```

### 완료 및 검증 🎉

#### Astra 음성 에이전트
브라우저에서 localhost:3000을 열어 Astra 음성 에이전트를 테스트하세요.

#### 그래프 디자이너

다른 탭을 열어 localhost:3001로 이동하고, 그래프 디자이너를 사용하여 확장 기능의 흐름과 속성을 편집하세요.


![TEN Graph Designer](https://github.com/rte-design/docs/blob/main/assets/gifs/graph-designer.gif?raw=true)

<br>
<h2>TEN 플랫폼</h2>

이제 첫 번째 AI 에이전트를 만들었으니, 여기서 창의력이 멈추지 않습니다. 더 놀라운 에이전트를 개발하려면 TEN 서비스가 내부적으로 어떻게 작동하는지에 대한 고급 이해가 필요합니다. [TEN 플랫폼 문서](https://astra-9.gitbook.io/ten-platform)를 참조하십시오.

<br>
<h2>연락을 유지하세요</h2>

더 깊이 들어가기 전에, 꼭 우리 저장소에 별표를 표시하고 모든 새 릴리스에 대한 즉각적인 알림을 받으세요!

![TEN 별표 표시 gif](https://github.com/rte-design/docs/blob/main/assets/gifs/star-the-repo-confetti-higher-quality.gif?raw=true)

<br>
<h2>커뮤니티 가입</h2>


- [Discord](https://discord.gg/VnPftUzAMJ): Ideal for sharing your applications and engaging with the community.
- [GitHub Discussion](https://github.com/rte-design/astra.ai/discussions): Perfect for providing feedback and asking questions.
- [GitHub Issues](https://github.com/rte-design/astra.ai/issues): Best for reporting bugs and proposing new features. Refer to our [contribution guidelines](./docs/code-of-conduct/contributing.md) for more details.
- [X (formerly Twitter)](https://twitter.com/intent/follow?screen_name=ten_platform): Great for sharing your agents and interacting with the community.

 <br>
 <h2>코드 기여자</h2>

[![TEN](https://contrib.rocks/image?repo=rte-design/astra.ai)](https://github.com/rte-design/astra.ai/graphs/contributors)

<br>
<h2>기여 가이드라인</h2>

기여는 환영합니다! 먼저 [기여 가이드라인](CONTRIBUTING.md)을 읽어주세요.

<br>
<h2>라이선스</h2>

이 프로젝트는 Apache 2.0 라이선스에 따라 라이선스가 부여됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하십시오.


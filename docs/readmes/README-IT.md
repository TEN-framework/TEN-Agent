![Astra banner image](https://github.com/TEN-framework/docs/blob/main/assets/jpg/astra_banner.jpg?raw=true)
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
<h2>Astra - un agente multimodale</h2>

[Astra agente multimodale](https://theastra.ai)

Astra è un agente multimodale alimentato da [ TEN ](https://doc.theten.ai), che dimostra le sue capacità in termini di linguaggio, visione e ragionamento attraverso RAG dalla documentazione locale.

[![Mostra Astra agente multimodale](https://github.com/TEN-framework/docs/blob/main/assets/gif/astra_voice_agent.gif?raw=true)](https://theastra.ai)
<br>
<h2>Come costruire Astra localmente

### Prerequisiti

#### Chiavi
- Agora App ID e App Certificate([leggi qui come](https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web))
- Chiavi API di [speech-to-text](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) e [text-to-speech](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) di Azure
- Chiave API di [OpenAI](https://openai.com/index/openai-api/)

#### Installazione
  - [Docker](https://www.docker.com/) / [Docker Compose](https://docs.docker.com/compose/)
  - [Node.js(LTS) v18](https://nodejs.org/en)

#### Requisiti minimi di sistema
  - CPU >= 2 Core
  - RAM >= 4 GB

#### Impostazione Docker su Apple Silicon
Se si utilizza Apple Silicon, è necessario deselezionare l'opzione "Use Rosetta for x86_64/amd64 emulation on Apple Silicon" per Docker, altrimenti il server non funzionerà.

![Impostazione Docker](https://github.com/TEN-framework/docs/blob/main/assets/gif/docker_setting.gif?raw=true)

### Prossimo passo

#### 1. Modifica dei file di configurazione
Nella radice del progetto, usa il comando cp per creare .env dall’esempio.

Verranno utilizzati per memorizzare le informazioni per `docker compose` successivamente.
```bash
cp ./.env.example ./.env
```

#### 2. Configurazione delle chiavi API
Apri il file `.env` e compila le sezioni `keys` e `regions`. Puoi anche scegliere di utilizzare diverse `extensions`:
```bash
# Agora App ID e Agora App Certificate
AGORA_APP_ID=
# Lascia vuoto a meno che tu non abbia abilitato il certificato all'interno dell'account Agora.
AGORA_APP_CERTIFICATE=

# Chiave e regione di Azure STT
AZURE_STT_KEY=
AZURE_STT_REGION=

# Chiave e regione di Azure TTS
AZURE_TTS_KEY=
AZURE_TTS_REGION=

# Chiave API di OpenAI
OPENAI_API_KEY=
```

#### 3. Avvia i container di sviluppo dell'agente
Nella stessa directory, esegui il comando `docker compose up` per comporre i container:
```bash
docker compose up
```

#### 4. Entra nel container e crea l'agente
Apri una finestra del terminale separata, entra nel container e crea l'agente:
```bash
docker exec -it astra_agents_dev bash
make build
```

#### 5. Avvia il server
Una volta completata la compilazione, esegui `make run-server` sulla porta `8080`:
```bash
make run-server
```

### Completato e verifica 🎉

#### Astra agente multimodale
Apri http://localhost:3000 nel browser per testare Astra agente multimodale.

#### Graph designer

Apri un'altra scheda e vai su http://localhost:3001, utilizza il graph designer per modificare il flusso e le proprietà delle estensioni.

![TEN Graph Designer](https://github.com/TEN-framework/docs/blob/main/assets/gif/graph_designer.gif?raw=true)

<br>
<h2>La piattaforma TEN</h2>

Ora che hai creato il tuo primo agente di intelligenza artificiale, la creatività non si ferma qui. Per sviluppare agenti ancora più sorprendenti, avrai bisogno di una comprensione avanzata di come funziona il servizio TEN nel dettaglio. Consulta la [documentazione della piattaforma TEN](https://doc.theten.ai).

<br>
<h2>Confronto delle funzionalità di TEN</h2>

<div align="center">

| **Funzionalità**                         | **TEN** | **Dify** | **LangChain** | **Flowise** |
|:----------------------------------------:|:-------:|:--------:|:-------------:|:-----------:|
| **Agente multimodale open source**       |   ✅    |    ❌    |      ❌       |      ❌     |
| **Estensioni in Python, Go e C++**       |   ✅    |    ❌    |      ❌       |      ❌     |
| **Gestore pacchetti all-in-one**         |   ✅    |    ❌    |      ❌       |      ❌     |
| **Trasporto RTC**                        |   ✅    |    ❌    |      ❌       |      ❌     |
| **Store di estensioni**                   |   ✅    |    ✅    |      ❌       |      ❌     |
| **RAG**                                  |   ✅    |    ✅    |      ✅       |      ✅     |
| **Workflow Builder**                     |   ✅    |    ✅    |      ✅       |      ✅     |
| **Deployment locale**                    |   ✅    |    ✅    |      ✅       |      ✅     |

</div>

<br>
<h2>Rimani aggiornato</h2>

Prima di continuare, assicurati di mettere una stella al nostro repository e ricevere notifiche istantanee per tutte le nuove versioni!

![TEN star us gif](https://github.com/TEN-framework/docs/blob/main/assets/gif/star_the_repo_confetti_higher_quality.gif?raw=true)

<br>
<h2>Unisciti alla community</h2>

- [Discord](https://discord.gg/VnPftUzAMJ): Ideale per condividere le tue applicazioni e interagire con la community.
- [GitHub Discussion](https://github.com/TEN-framework/astra.ai/discussions): Perfetto per fornire feedback e fare domande.
- [GitHub Issues](https://github.com/TEN-framework/astra.ai/issues): Il migliore per segnalare bug e proporre nuove funzionalità. Consulta le nostre [linee guida per il contributo](./docs/code-of-conduct/contributing.md) per ulteriori dettagli.
- [X (precedentemente Twitter)](https://img.shields.io/twitter/follow/AstraAIAgent?logo=X&color=%20%23f5f5f5): Ottimo per condividere i tuoi agenti e interagire con la community.

<br>
<h2>Contributori al codice</h2>

[![TEN](https://contrib.rocks/image?repo=TEN-framework/astra.ai)](https://github.com/TEN-framework/astra.ai/graphs/contributors)

<br>
<h2>Linee guida per il contributo</h2>

I contributi sono benvenuti! Leggi prima le [linee guida per il contributo](./docs/code-of-conduct/contributing.md).

<br>
<h2>Licenza</h2>

Questo progetto è concesso in licenza con licenza Apache 2.0 - consulta il file [LICENSE](LICENSE) per ulteriori dettagli.

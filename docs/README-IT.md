<div align="center"> <a name="readme-top"></a>

![Image][ten-framework-banner]

[![TEN Releases][ten-releases-badge]][ten-releases]
[![Coverage Status][coverage-badge]][coverage]
[![][release-date-badge]][ten-releases]
[![Discussion posts][discussion-badge]][discussions]
[![Commits][commits-badge]][commit-activity]
[![Issues closed][issues-closed-badge]][issues-closed]
[![][contributors-badge]][contributors]
[![GitHub license][license-badge]][license]
[![Ask DeepWiki][deepwiki-badge]][deepwiki]
[![ReadmeX][readmex-badge]][readmex]

[Sito ufficiale][official-site]
•
[Documentazione][documentation]
•
[Blog][blog]

[![README in inglese][lang-en-badge]][lang-en-readme]
[![Guida in cinese semplificato][lang-zh-badge]][lang-zh-readme]
[![README in giapponese][lang-jp-badge]][lang-jp-readme]
[![README in coreano][lang-kr-badge]][lang-kr-readme]
[![README in spagnolo][lang-es-badge]][lang-es-readme]
[![README in francese][lang-fr-badge]][lang-fr-readme]
[![README in italiano][lang-it-badge]][lang-it-readme]

<a href="https://trendshift.io/repositories/13772?utm_source=repository-badge&amp;utm_medium=badge&amp;utm_campaign=badge-repository-13772" target="_blank" rel="noopener noreferrer"><img src="https://trendshift.io/api/badge/repositories/13772" alt="TEN-framework%2Ften-framework | Trendshift" width="250" height="55"/></a>

</div>

<br>

<details open>
  <summary><kbd>Indice</kbd></summary>

  <br>

- [Benvenuto in TEN][welcome-to-ten]
- [Esempi di agenti][agent-examples-section]
- [Guida rapida agli esempi di agenti][quick-start]
  - [Ambiente locale][localhost-section]
  - [Codespaces][codespaces-section]
- [Auto-hosting degli esempi][agent-examples-self-hosting]
  - [Distribuire con Docker][deploying-with-docker]
  - [Distribuire su altri servizi cloud][deploying-with-other-cloud-services]
- [Rimani aggiornato][stay-tuned]
- [Ecosistema TEN][ten-ecosystem-anchor]
- [Domande][questions]
- [Contribuire][contributing]
  - [Contributor del codice][code-contributors]
  - [Linee guida per contribuire][contribution-guidelines]
  - [Licenza][license-section]

<br/>

</details>

<a name="welcome-to-ten"></a>

## Benvenuto in TEN

TEN è un framework open source per creare agenti vocali conversazionali.

L’[ecosistema TEN][ten-ecosystem-anchor] comprende [TEN Framework][ten-framework-link], [Esempi di agenti][ten-agent-example-link], [VAD][ten-vad-link], [Turn Detection][ten-turn-detection-link] e [Portal][ten-portal-link].

<br>

| Canale della community | Scopo |
| ---------------- | ------- |
| [![Follow on X][follow-on-x-badge]][follow-on-x] | Segui TEN Framework su X per aggiornamenti e annunci |
| [![Discord TEN Community][discord-badge]][discord-invite] | Unisciti alla community Discord per confrontarti con altri sviluppatori |
| [![Follow on LinkedIn][linkedin-badge]][linkedin] | Segui TEN Framework su LinkedIn per non perdere nessuna novità |
| [![Hugging Face Space][hugging-face-badge]][hugging-face] | Esplora i nostri spazi e modelli su Hugging Face |
| [![WeChat][wechat-badge]][wechat-discussion] | Entra nel gruppo WeChat per parlare con la community cinese |

<br>

<a name="agent-examples"></a>

## Esempi di agenti

<br>

![Image][voice-assistant-image]

<strong>Assistente vocale multiuso</strong> — Assistente in tempo reale, a bassa latenza e alta qualità, estendibile con [memoria][memory-example], [VAD][voice-assistant-vad-example], [rilevamento dei turni][voice-assistant-turn-detection-example] e altre estensioni.

Consulta il [codice di esempio][voice-assistant-example] per maggiori dettagli.

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

![Image][doodler-image]

<strong>Doodler</strong> — Una lavagna di scarabocchi che trasforma prompt vocali o digitati in semplici schizzi a mano, con una palette di pastelli e disegno in tempo reale.

[Codice di esempio][doodler-example]

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

![Image][lip-sync-image]

<strong>Avatar con lip sync</strong> — Supporta diversi provider di avatar. La demo mostra Kei, un personaggio anime con sincronizzazione labiale Live2D, e presto includerà avatar realistici di Trulience, HeyGen e Tavus.

Guarda il [codice di esempio Live2D][voice-assistant-live2d-example].

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

![Image][speech-diarization-image]

<strong>Diarizzazione vocale</strong> — Rilevamento e etichettatura dei parlanti in tempo reale. Il gioco "Who Likes What" mostra un caso d’uso interattivo.

[Codice di esempio][speechmatics-diarization-example]

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

![Image][sip-call-image]

<strong>Chiamata SIP</strong> — Estensione SIP che abilita chiamate telefoniche gestite da TEN.

[Codice di esempio][voice-assistant-sip-example]

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

![Image][transcription-image]

<strong>Trascrizione</strong> — Strumento che trascrive l’audio in testo.

[Codice di esempio][transcription-example]

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

![Image][esp32-image]

<strong>ESP32-S3 Korvo V3</strong> — Esegue un esempio di TEN Agent sulla scheda di sviluppo Espressif ESP32-S3 Korvo V3 per portare comunicazioni basate su LLM sull’hardware.

Consulta la [guida di integrazione][esp32-guide] per ulteriori informazioni.

<br>
<div align="right">

[![][back-to-top]][readme-top]

</div>

<a name="quick-start-with-agent-examples"></a>

## Guida rapida agli esempi di agenti

<a name="localhost"></a>

### Ambiente locale

#### Passaggio ⓵ - Prerequisiti

| Categoria | Requisiti |
| --- | --- |
| **Chiavi** | • Agora [App ID][agora-app-certificate] e [App Certificate][agora-app-certificate] (minuti gratuiti ogni mese)<br>• Chiave API [OpenAI][openai-api] (qualsiasi LLM compatibile con OpenAI)<br>• ASR [Deepgram][deepgram] (crediti gratuiti alla registrazione)<br>• TTS [ElevenLabs][elevenlabs] (crediti gratuiti alla registrazione) |
| **Installazione** | • [Docker][docker] / [Docker Compose][docker-compose]<br>• [Node.js (LTS) v18][nodejs] |
| **Requisiti minimi** | • CPU ≥ 2 core<br>• RAM ≥ 4 GB |

<br>

![divider][divider-light]
![divider][divider-dark]

<!-- > [!NOTE]
> **macOS: impostazioni Docker su Apple Silicon**
>
> Deseleziona "Use Rosetta for x86/amd64 emulation" nelle impostazioni di Docker. Le build possono essere più lente su ARM, ma le prestazioni risultano normali sui server x64. -->

#### Passaggio ⓶ - Compila gli esempi nella VM

##### 1. Clona il repo, entra in `ai_agents` e crea `.env` da `.env.example`

```bash
cd ai_agents
cp ./.env.example ./.env
```

##### 2. Configura Agora App ID e App Certificate in `.env`

```bash
AGORA_APP_ID=
AGORA_APP_CERTIFICATE=

# Esegui l’esempio predefinito dell’assistente vocale
# Deepgram (necessario per STT)
DEEPGRAM_API_KEY=your_deepgram_api_key_here

# OpenAI (necessario per il modello linguistico)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o

# ElevenLabs (necessario per TTS)
ELEVENLABS_TTS_KEY=your_elevenlabs_api_key_here
```

##### 3. Avvia i container di sviluppo

```bash
docker compose up -d
```

##### 4. Entra nel container

```bash
docker exec -it ten_agent_dev bash
```

##### 5. Compila l’agente con l’esempio predefinito (≈5-8 min)

Trovi altre demo nella cartella `agents/examples`.
Inizia da una di queste:

```bash
# Assistente vocale concatenato
cd agents/examples/voice-assistant

# Assistente voce-a-voce in tempo reale
cd agents/examples/voice-assistant-realtime
```

##### 6. Avvia il server web

Esegui `task install` prima del primo avvio e dopo aver modificato le dipendenze o il codice sorgente Go. Questo comando installa le dipendenze TEN, Python e frontend e compila il server API Go. Le modifiche al solo codice Python non richiedono una nuova installazione.

```bash
task install
task run
```

##### 7. Accedi all’agente

Quando l’esempio è in esecuzione puoi usare queste interfacce:

<table>
  <tr>
    <td align="center">
      <b>localhost:49483</b>
      <img src="https://github.com/user-attachments/assets/191a7c0a-d8e6-48f9-866f-6a70c58f0118" alt="Screenshot 1" /><br/>
    </td>
    <td align="center">
      <b>localhost:3000</b>
      <img src="https://github.com/user-attachments/assets/13e482b6-d907-4449-a779-9454bb24c0b1" alt="Screenshot 2" /><br/>
    </td>
  </tr>
</table>

- TMAN Designer: <http://localhost:49483>
- UI degli esempi: <http://localhost:3000>

<br>

![divider][divider-light]
![divider][divider-dark]

#### Passaggio ⓷ - Personalizza l’esempio

1. Apri [localhost:49483][localhost-49483].
2. Fai clic con il tasto destro sulle estensioni STT, LLM e TTS.
3. Inserisci le relative API key.
4. Dopo aver salvato, la versione aggiornata sarà visibile su [localhost:3000][localhost-3000].

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

#### Esegui un’app di trascrizione da TEN Manager senza Docker (Beta)

TEN offre anche un’app di trascrizione che puoi eseguire in TEN Manager senza usare Docker.

Consulta la [guida rapida][quick-start-guide-ten-manager] per ulteriori dettagli.

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

<a name="codespaces"></a>

### Codespaces

GitHub offre Codespaces gratuiti per ogni repository. Puoi eseguire gli esempi senza Docker e, in genere, l’avvio è più rapido rispetto all’ambiente locale basato su container.

[codespaces-shield]: <https://github.com/codespaces/badge.svg>
[![][codespaces-shield]][codespaces-new]

Consulta [questa guida][codespaces-guide] per i dettagli.

<div align="right">

[![][back-to-top]][readme-top]

</div>

<br>

<a name="agent-examples-self-hosting"></a>

## Auto-hosting degli esempi

<a name="deploying-with-docker"></a>

### Distribuire con Docker

Dopo aver personalizzato l’agente (con TMAN Designer o modificando `property.json`), crea un’immagine Docker di release e distribuiscila.

##### Pubblicare come immagine Docker

**Nota**: esegui i comandi al di fuori di qualsiasi container.

###### Build dell’immagine

```bash
cd ai_agents
docker build -f agents/examples/<example-name>/Dockerfile -t example-app .
```

###### Esecuzione

```bash
docker run --rm -it --env-file .env -p 3000:3000 example-app
```

<br>

![divider][divider-light]
![divider][divider-dark]

<a name="deploying-with-other-cloud-services"></a>

### Distribuire su altri servizi cloud

Puoi dividere il deployment in due parti quando ospiti TEN su piattaforme come [Vercel][vercel] o [Netlify][netlify].

1. Esegui il backend TEN su una piattaforma compatibile con container (VM Docker, Fly.io, Render, ECS, Cloud Run, ecc.). Usa l’immagine di esempio senza modificarla ed esponi la porta `8080`.
2. Distribuisci solo il frontend su Vercel o Netlify. Imposta la radice del progetto su `ai_agents/agents/examples/<example>/frontend`, esegui `pnpm install` (o `bun install`) e poi `pnpm build` (o `bun run build`), mantenendo la cartella di output `.next` predefinita.
3. Configura le variabili di ambiente dal pannello del provider: `AGENT_SERVER_URL` deve puntare al backend e aggiungi le chiavi `NEXT_PUBLIC_*` necessarie (per esempio le credenziali Agora esposte al browser).
4. Consenti al backend di accettare richieste dall’origine del frontend tramite CORS aperto o usando il middleware proxy incluso.

In questo modo il backend gestisce i processi di lunga durata e il frontend hostato instrada semplicemente il traffico API.

<div align="right">

[![][back-to-top]][readme-top]

</div>

<br>

<a name="stay-tuned"></a>

## Rimani aggiornato

Ricevi notifiche immediate su nuove release e aggiornamenti. Il tuo supporto ci aiuta a migliorare TEN!

<br>

![Image][stay-tuned-image]

<br>
<div align="right">

[![][back-to-top]][readme-top]

</div>

<br>

<a name="ten-ecosystem"></a>

## Ecosistema TEN

<br>

| Progetto | Anteprima |
| ------- | ------- |
| [**️TEN Framework**][ten-framework-link]<br>Framework open source per agenti conversazionali.<br><br>![][ten-framework-shield] | ![][ten-framework-banner] |
| [**TEN VAD**][ten-vad-link]<br>Rilevatore di attività vocale in streaming, leggero e a bassa latenza.<br><br>![][ten-vad-shield] | ![][ten-vad-banner] |
| [**️TEN Turn Detection**][ten-turn-detection-link]<br>Abilita dialoghi full-duplex tramite rilevamento dei turni.<br><br>![][ten-turn-detection-shield] | ![][ten-turn-detection-banner] |
| [**TEN Agent Examples**][ten-agent-example-link]<br>Casi d'uso costruiti con TEN.<br><br> | ![][ten-agent-example-banner] |
| [**TEN Portal**][ten-portal-link]<br>Sito ufficiale con documentazione e blog.<br><br>![][ten-portal-shield] | ![][ten-portal-banner] |

<br>
<div align="right">

[![][back-to-top]][readme-top]

</div>

<br>

<a name="questions"></a>

## Domande

TEN Framework è presente anche su piattaforme di Q&A alimentate dall’IA. Offrono risposte multilingue, dalla configurazione di base agli scenari avanzati.

| Servizio | Link |
| ------- | ---- |
| DeepWiki | [![Ask DeepWiki][deepwiki-badge]][deepwiki] |
| ReadmeX | [![ReadmeX][readmex-badge]][readmex] |

<br>
<div align="right">

[![][back-to-top]][readme-top]

</div>

<a name="contributing"></a>

## Contribuire

Accogliamo qualsiasi forma di collaborazione open source! Bugfix, nuove funzionalità, documentazione o idee: ogni contributo aiuta a far crescere strumenti di IA personalizzati. Dai un’occhiata a Issues e Projects su GitHub per trovare attività su cui lavorare e mostrare le tue competenze. Costruiamo TEN insieme!

<br>

> [!TIP]
>
> **Ogni contributo è importante** 🙏
>
> Aiutaci a migliorare TEN: dal codice alla documentazione, tutto conta. Condividi i tuoi progetti TEN Agent sui social per ispirare altre persone.
>
> Contatta un maintainer — [@elliotchen200][elliotchen200-x] su 𝕏 o [@cyfyifanchen][cyfyifanchen-github] su GitHub — per aggiornamenti, discussioni e collaborazioni.

<br>

![divider][divider-light]
![divider][divider-dark]

<a name="code-contributors"></a>

### Contributor del codice

[![TEN][contributors-image]][contributors]

<a name="contribution-guidelines"></a>

### Linee guida per contribuire

Le contribuzioni sono benvenute! Leggi prima le [linee guida per contribuire][contribution-guidelines-doc].

<br>

![divider][divider-light]
![divider][divider-dark]

<a name="license"></a>

### Licenza

1. L’intero TEN Framework (esclusi i folder elencati qui sotto) è rilasciato sotto Apache License 2.0 con restrizioni aggiuntive. Consulta il file [LICENSE][license-file] nella root del progetto.
2. I componenti nella directory `packages` sono distribuiti sotto Apache License 2.0. Ogni package contiene il proprio file `LICENSE`.
3. Le librerie di terze parti utilizzate da TEN Framework sono elencate nella cartella [third_party][third-party-folder].

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
[discussion-badge]: https://img.shields.io/github/discussions/TEN-framework/ten_framework?labelColor=gray&color=%20%23f79009
[discussions]: https://github.com/TEN-framework/ten-framework/discussions/
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
[websocket-example]: ../ai_agents/agents/examples/websocket-example
[memory-example]: ../ai_agents/agents/examples/voice-assistant-with-memU
[voice-assistant-vad-example]: ../ai_agents/agents/examples/voice-assistant-with-ten-vad
[voice-assistant-turn-detection-example]: ../ai_agents/agents/examples/voice-assistant-with-turn-detection
[voice-assistant-example]: ../ai_agents/agents/examples/voice-assistant
[divider-light]: https://github.com/user-attachments/assets/aec54c94-ced9-4683-ae58-0a5a7ed803bd#gh-light-mode-only
[divider-dark]: https://github.com/user-attachments/assets/d57fad08-4f49-4a1c-bdfc-f659a5d86150#gh-dark-mode-only
[lip-sync-image]: https://github.com/user-attachments/assets/51ab1504-b67c-49d4-8a7a-5582d9b254da
[voice-assistant-live2d-example]: ../ai_agents/agents/examples/voice-assistant-live2d
[speech-diarization-image]: https://github.com/user-attachments/assets/f94b21b8-9dda-4efc-9274-b028cc01296a
[speechmatics-diarization-example]: ../ai_agents/agents/examples/speaker-diarization
[sip-call-image]: https://github.com/user-attachments/assets/6ed5b04d-945a-4a30-a1cc-f8014b602b38
[voice-assistant-sip-example]: ../ai_agents/agents/examples/voice-assistant-sip-twilio
[transcription-image]: https://github.com/user-attachments/assets/d793bc6c-c8de-4996-bd85-9ce88c69dd8d
[transcription-example]: ../ai_agents/agents/examples/transcription
[doodler-image]: https://github.com/user-attachments/assets/80c4eabd-de96-4971-8956-6b365d4fbd64
[doodler-example]: ../ai_agents/agents/examples/doodler
[esp32-image]: https://github.com/user-attachments/assets/3d60f1ff-0f82-4fe7-b5c2-ac03d284f60c
[esp32-guide]: ../ai_agents/esp32-client

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
[contribution-guidelines-doc]: ./code-of-conduct/contributing.md
[license-file]: ../LICENSE
[third-party-folder]: ../third_party/

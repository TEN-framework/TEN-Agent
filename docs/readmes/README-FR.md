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
[Commencer](https://doc.theten.ai/getting-started/quickstart)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[Tutoriels](https://doc.theten.ai/getting-started/create-a-hello-world-extension)

</div>

<br>
<h2>Astra - un agent multimodal</h2>

[Agent multimodal Astra](https://theastra.ai)

Astra est un agent multimodal alimenté par [TEN](https://doc.theten.ai), démontrant ses capacités en matière de parole, de vision et de raisonnement grâce à RAG à partir de la documentation locale.

[![Présentation de l'agent multimodal Astra](https://github.com/TEN-framework/docs/blob/main/assets/gif/astra_voice_agent.gif?raw=true)](https://theastra.ai)
<br>
<h2>Comment construire Astra localement

### Prérequis

#### Clés
- ID et certificat d'application Agora ([lire ici comment](https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web))
- Clés d'API de [speech-to-text](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) et de [text-to-speech](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) d'Azure
- Clé d'API [OpenAI](https://openai.com/index/openai-api/)

#### Installation
  - [Docker](https://www.docker.com/) / [Docker Compose](https://docs.docker.com/compose/)
  - [Node.js(LTS) v18](https://nodejs.org/en)

#### Configuration système minimale requise
  - CPU >= 2 cœurs
  - RAM >= 4 Go

#### Paramètres Docker sur Apple Silicon
Si vous utilisez Apple Silicon, vous devrez décocher l'option "Utiliser Rosetta pour l'émulation x86_64/amd64 sur Apple Silicon" pour Docker, sinon le serveur ne fonctionnera pas.

![Paramètres Docker](https://github.com/TEN-framework/docs/blob/main/assets/gif/docker_setting.gif?raw=true)

### Étape suivante

#### 1. Modifier les fichiers de configuration
À la racine du projet, utilisez la commande cp pour créer .env à partir de l’exemple.

Ils seront utilisés pour stocker les informations pour `docker compose` ultérieurement.
```bash
cp ./.env.example ./.env
```

#### 2. Configuration des clés API
Ouvrez le fichier `.env` et remplissez les champs `keys` et `regions`. C'est également ici que vous pouvez choisir d'utiliser différentes `extensions` :
```bash
# Agora App ID et Agora App Certificate
AGORA_APP_ID=
# Laissez vide à moins que vous n'ayez activé le certificat dans le compte Agora.
AGORA_APP_CERTIFICATE=

# Clé et région Azure STT
AZURE_STT_KEY=
AZURE_STT_REGION=

# Clé et région Azure TTS
AZURE_TTS_KEY=
AZURE_TTS_REGION=

# Clé API OpenAI
OPENAI_API_KEY=
```

#### 3. Démarrer les conteneurs de développement de l'agent
Dans le même répertoire, exécutez la commande `docker compose up` pour composer les conteneurs :
```bash
docker compose up
```

#### 4. Accéder au conteneur et construire l'agent
Ouvrez une nouvelle fenêtre de terminal, accédez au conteneur et construisez l'agent :
```bash
docker exec -it astra_agents_dev bash
make build
```

#### 5. Démarrer le serveur
Une fois la construction terminée, exécutez `make run-server` sur le port `8080` :
```bash
make run-server
```

### Terminé et vérifié 🎉

#### Agent multimodal Astra
Ouvrez http://localhost:3000 dans votre navigateur pour tester l'agent multimodal Astra.

#### Concepteur de graphiques
Ouvrez un autre onglet et allez sur http://localhost:3001 pour utiliser le concepteur de graphiques et modifier le flux et les propriétés des extensions.

![Concepteur de graphiques TEN](https://github.com/TEN-framework/docs/blob/main/assets/gif/graph_designer.gif?raw=true)

<br>
<h2>Plateforme TEN</h2>

Maintenant que vous avez créé votre premier agent d'IA, la créativité ne s'arrête pas là. Pour développer d'autres agents incroyables, vous aurez besoin d'une compréhension avancée du fonctionnement du service TEN. Veuillez consulter la [documentation de la plateforme TEN](https://doc.theten.ai).

<br>
<h2>Comparaison des fonctionnalités TEN</h2>

<div align="center">

| **Fonctionnalités**                      | **TEN** | **Dify** | **LangChain** | **Flowise** |
|:----------------------------------------:|:-------:|:--------:|:-------------:|:-----------:|
| **Agent multimodal open source**         |   ✅    |    ❌    |      ❌       |      ❌     |
| **Extensions en Python, Go et C++**      |   ✅    |    ❌    |      ❌       |      ❌     |
| **Gestionnaire de paquets tout-en-un**   |   ✅    |    ❌    |      ❌       |      ❌     |
| **Transport RTC**                        |   ✅    |    ❌    |      ❌       |      ❌     |
| **Boutique d'extensions**                 |   ✅    |    ✅    |      ❌       |      ❌     |
| **RAG**                                  |   ✅    |    ✅    |      ✅       |      ✅     |
| **Constructeur de flux**                  |   ✅    |    ✅    |      ✅       |      ✅     |
| **Déploiement local**                     |   ✅    |    ✅    |      ✅       |      ✅     |

</div>

<br>
<h2>Reste à l'écoute</h2>

Avant de continuer, assurez-vous de mettre une étoile à notre dépôt et recevez des notifications instantanées pour toutes les nouvelles versions !

![Animation étoile TEN](https://github.com/TEN-framework/docs/blob/main/assets/gif/star_the_repo_confetti_higher_quality.gif?raw=true)

<br>
<h2>Rejoignez la communauté</h2>

- [Discord](https://discord.gg/VnPftUzAMJ) : Idéal pour partager vos applications et interagir avec la communauté.
- [Discussion GitHub](https://github.com/TEN-framework/astra.ai/discussions) : Parfait pour donner votre avis et poser des questions.
- [Problèmes GitHub](https://github.com/TEN-framework/astra.ai/issues) : Le meilleur moyen de signaler des bugs et de proposer de nouvelles fonctionnalités. Consultez nos [directives de contribution](./docs/code-of-conduct/contributing.md) pour plus de détails.
- [X (anciennement Twitter)](https://img.shields.io/twitter/follow/AstraAIAgent?logo=X&color=%20%23f5f5f5) : Idéal pour partager vos agents et interagir avec la communauté.

 <br>
 <h2>Contributeurs au code</h2>

[![TEN](https://contrib.rocks/image?repo=TEN-framework/astra.ai)](https://github.com/TEN-framework/astra.ai/graphs/contributors)

<br>
<h2>Directives de contribution</h2>

Les contributions sont les bienvenues ! Veuillez d'abord lire les [directives de contribution](./docs/code-of-conduct/contributing.md).

<br>
<h2>Licence</h2>

Ce projet est sous licence Apache 2.0 - consultez le fichier [LICENSE](LICENSE) pour plus de détails.

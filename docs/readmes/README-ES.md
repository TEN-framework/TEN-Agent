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


[Documentación](https://doc.theten.ai)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[Empezando](https://doc.theten.ai/getting-started/quickstart)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[Tutoriales](https://doc.theten.ai/getting-started/create-a-hello-world-extension)


</div>

<br>
<h2>Astra - un agente multimodal</h2>

[Astra multimodal agent](https://theastra.ai)

Astra es un agente multimodal impulsado por [TEN](https://doc.theten.ai), que demuestra sus capacidades en habla, visión y razonamiento a través de RAG a partir de la documentación local.

[![Demostración del agente multimodal Astra](https://github.com/TEN-framework/docs/blob/main/assets/gif/astra_voice_agent.gif?raw=true)](https://theastra.ai)
<br>
<h2>Cómo construir Astra localmente

### Requisitos previos

#### Claves
- ID de aplicación y certificado de aplicación de Agora ([lea aquí cómo](https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web))
- Claves de API de [speech-to-text](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) y [text-to-speech](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) de Azure
- Clave de API de [OpenAI](https://openai.com/index/openai-api/)

#### Instalación
  - [Docker](https://www.docker.com/) / [Docker Compose](https://docs.docker.com/compose/)
  - [Node.js(LTS) v18](https://nodejs.org/en)

#### Requisitos mínimos del sistema
  - CPU >= 2 núcleos
  - RAM >= 4 GB

#### Configuración de Docker en Apple Silicon
Si está utilizando Apple Silicon, deberá desmarcar la opción "Use Rosetta for x86_64/amd64 emulation on Apple Silicon" en Docker, de lo contrario, el servidor no funcionará.

![Configuración de Docker](https://github.com/TEN-framework/docs/blob/main/assets/gif/docker_setting.gif?raw=true)

### Siguiente paso

#### 1. Modificar archivos de configuración
En la raíz del proyecto, usa el siguiente comando para crear .env a partir del ejemplo.

Se utilizarán para almacenar información para `docker compose` más adelante.
```bash
cp ./.env.example ./.env
```

#### 2. Configurar claves de API
Abre el archivo `.env` y completa las secciones `keys` y `regions`. Aquí también puedes elegir usar diferentes `extensions`:
```bash
# Agora App ID y Agora App Certificate
AGORA_APP_ID=
# Deja en blanco a menos que hayas habilitado el certificado dentro de la cuenta de Agora.
AGORA_APP_CERTIFICATE=

# Clave y región de Azure STT
AZURE_STT_KEY=
AZURE_STT_REGION=

# Clave y región de Azure TTS
AZURE_TTS_KEY=
AZURE_TTS_REGION=

# Clave de API de OpenAI
OPENAI_API_KEY=
```

#### 3. Iniciar contenedores de desarrollo del agente
En el mismo directorio, ejecuta el comando `docker compose up` para componer los contenedores:
```bash
docker compose up
```

#### 4. Ingresar al contenedor y construir el agente
Abre una ventana de terminal separada, ingresa al contenedor y construye el agente:
```bash
docker exec -it astra_agents_dev bash
make build
```

#### 5. Iniciar el servidor
Una vez que se haya completado la construcción, ejecuta `make run-server` en el puerto `8080`:
```bash
make run-server
```

### ¡Finaliza y verifica 🎉

#### Agente multimodal Astra
Abre http://localhost:3000 en el navegador para probar el agente multimodal Astra.

#### Diseñador de gráficos

Abre otra pestaña e ingresa a http://localhost:3001, y utiliza el diseñador de gráficos para editar el flujo y las propiedades de cualquier extensión.

![Diseñador de gráficos TEN](https://github.com/TEN-framework/docs/blob/main/assets/gif/graph_designer.gif?raw=true)

<br>
<h2>Plataforma TEN</h2>

Ahora que has creado tu primer agente de IA, la creatividad no se detiene aquí. Para desarrollar agentes más sorprendentes, necesitarás una comprensión avanzada de cómo funciona el servicio TEN en el fondo. Consulta la [documentación de la plataforma TEN](https://doc.theten.ai).

<br>
<h2>Comparación de características de TEN</h2>

<div align="center">

| **Características**                      | **TEN** | **Dify** | **LangChain** | **Flowise** |
|:----------------------------------------:|:-------:|:--------:|:-------------:|:-----------:|
| **Agente multimodal de código abierto**  |   ✅    |    ❌    |      ❌       |      ❌     |
| **Python, Go y C++ para extensiones**    |   ✅    |    ❌    |      ❌       |      ❌     |
| **Gestor de paquetes todo en uno**       |   ✅    |    ❌    |      ❌       |      ❌     |
| **Transporte RTC**                       |   ✅    |    ❌    |      ❌       |      ❌     |
| **Tienda de extensiones**                |   ✅    |    ✅    |      ❌       |      ❌     |
| **RAG**                                  |   ✅    |    ✅    |      ✅       |      ✅     |
| **Constructor de flujo de trabajo**      |   ✅    |    ✅    |      ✅       |      ✅     |
| **Implementación local**                 |   ✅    |    ✅    |      ✅       |      ✅     |

</div>

<br>
<h2>Mantente informado</h2>

Antes de continuar, ¡asegúrate de marcar nuestro repositorio como favorito y recibir notificaciones instantáneas sobre todas las nuevas versiones!

![TEN marcar repositorio gif](https://github.com/TEN-framework/docs/blob/main/assets/gif/star_the_repo_confetti_higher_quality.gif?raw=true)

<br>
<h2>Únete a la comunidad</h2>

- [Discord](https://discord.gg/VnPftUzAMJ): Ideal para compartir tus aplicaciones y participar en la comunidad.
- [Discusión en GitHub](https://github.com/TEN-framework/astra.ai/discussions): Perfecto para brindar comentarios y hacer preguntas.
- [Informar problemas en GitHub](https://github.com/TEN-framework/astra.ai/issues): Lo mejor para informar errores y proponer nuevas características. Consulta nuestras [pautas de contribución](./docs/code-of-conduct/contributing.md) para obtener más detalles.
- [X (anteriormente Twitter)](https://img.shields.io/twitter/follow/AstraAIAgent?logo=X&color=%20%23f5f5f5): Genial para compartir tus agentes e interactuar con la comunidad.

<br>
<h2>Contribuyentes de código</h2>

[![TEN](https://contrib.rocks/image?repo=TEN-framework/astra.ai)](https://github.com/TEN-framework/astra.ai/graphs/contributors)

<br>
<h2>Pautas de contribución</h2>

¡Las contribuciones son bienvenidas! Por favor, lee primero las [pautas de contribución](./docs/code-of-conduct/contributing.md).

<br>
<h2>Licencia</h2>

Este proyecto está licenciado bajo la Licencia Apache 2.0. Consulta el archivo [LICENSE](LICENSE) para obtener más detalles.


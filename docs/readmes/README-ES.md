<div align="center"> <a name="readme-top"></a>

![TEN Agent banner](https://github.com/TEN-framework/docs/blob/main/assets/jpg/banner.jpg?raw=true)

[![Seguimiento en X](https://img.shields.io/twitter/follow/TenFramework?logo=X&color=%20%23f5f5f5)](https://twitter.com/intent/follow?screen_name=TenFramework)
[![Publicaciones de discusión](https://img.shields.io/github/discussions/TEN-framework/ten-agent?labelColor=%20%23FDB062&color=%20%23f79009)](https://github.com/TEN-framework/ten-agent/discussions/)
[![Commits](https://img.shields.io/github/commit-activity/m/TEN-framework/ten-agent?labelColor=%20%237d89b0&color=%20%235d6b98)](https://github.com/TEN-framework/ten-agent/graphs/commit-activity)
[![Issues cerrados](https://img.shields.io/github/issues-search?query=repo%3ATEN-framework%2Ften-agent%20is%3Aclosed&label=issues%20closed&labelColor=green&color=green)](https://github.com/TEN-framework/ten-agent/issues)
[![PRs Bienvenidos](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](https://github.com/TEN-framework/ten-agent/pulls)
[![Licencia GitHub](https://img.shields.io/badge/License-Apache_2.0-blue.svg?labelColor=%20%23155EEF&color=%20%23528bff)](https://github.com/TEN-framework/ten-agent/blob/main/LICENSE)

[![Discord TEN Community](https://dcbadge.vercel.app/api/server/VnPftUzAMJ)](https://discord.gg/VnPftUzAMJ)

[![Observadores en GitHub](https://img.shields.io/github/watchers/TEN-framework/ten-agent?style=social&label=Watch)](https://GitHub.com/TEN-framework/ten-agent/watchers/?WT.mc_id=academic-105485-koreyst)
[![Bifurcaciones en GitHub](https://img.shields.io/github/forks/TEN-framework/ten-agent?style=social&label=Fork)](https://GitHub.com/TEN-framework/ten-agent/network/?WT.mc_id=academic-105485-koreyst)
[![Estrellas en GitHub](https://img.shields.io/github/stars/TEN-framework/ten-agent?style=social&label=Star)](https://GitHub.com/TEN-framework/ten-agent/stargazers/?WT.mc_id=academic-105485-koreyst)

<a href="https://github.com/TEN-framework/ten-agent/blob/main/README.md"><img alt="README en inglés" src="https://img.shields.io/badge/English-lightgrey"></a>
<a href="https://github.com/ten-framework/ten-agent/blob/main/docs/readmes/README-CN.md"><img alt="简体中文操作指南" src="https://img.shields.io/badge/简体中文-lightgrey"></a>
<a href="https://github.com/ten-framework/ten-agent/blob/main/docs/readmes/README-JP.md"><img alt="README en japonés" src="https://img.shields.io/badge/日本語-lightgrey"></a>
<a href="https://github.com/ten-framework/ten-agent/blob/main/docs/readmes/README-KR.md"><img alt="README en coreano" src="https://img.shields.io/badge/한국어-lightgrey"></a>
<a href="https://github.com/ten-framework/ten-agent/blob/main/docs/readmes/README-ES.md"><img alt="README en español" src="https://img.shields.io/badge/Español-lightgrey"></a>
<a href="https://github.com/ten-framework/ten-agent/blob/main/docs/readmes/README-FR.md"><img alt="README en francés" src="https://img.shields.io/badge/Français-lightgrey"></a>
<a href="https://github.com/ten-framework/ten-agent/blob/main/docs/readmes/README-IT.md"><img alt="README en italiano" src="https://img.shields.io/badge/Italiano-lightgrey"></a>

[Documentación](https://doc.theten.ai/docs/ten_agent/overview)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[Comenzando](https://doc.theten.ai/docs/ten_agent/getting_started)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[Repositorio TEN Framework](https://github.com/TEN-framework/ten_framework)

<a href="https://trendshift.io/repositories/11978" target="_blank"><img src="https://trendshift.io/api/badge/repositories/11978" alt="TEN-framework%2FTEN-Agent | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

</div>

<br>

<details open>
  <summary><kbd>Tabla de contenidos</kbd></summary>

#### Tabla de contenido

- [👋 Comenzando y Unirse a la Comunidad TEN](#-getting-started--join-ten-community)
- [✨ Funciones](#-features)
  - [1️⃣ Ten Agent + Trulience](#1️⃣--ten-agent--trulience)
  - [2️⃣ Ten Agent + Deepseek](#2️⃣-ten-agent--deepseek)
  - [3️⃣ Ten Agent + ESP32](#3️⃣-ten-agent--esp32)
  - [4️⃣ Ten Agent + Gemini Multimodal Live API](#4️⃣-ten-agent--gemini-multimodal-live-api)
  - [5️⃣ Ten Agent + Storyteller + Image Generator](#5️⃣-ten-agent--storyteller--image-generator)
  - [6️⃣ Ten Agent + Dify](#6️⃣-ten-agent--dify)
  - [7️⃣ Ten Agent + Coze](#7️⃣-ten-agent--coze)
- [💡 Casos de uso de TEN Agent](#-ten-agent-usecases)
- [🔌 Extensiones listas para usar](#-ready-to-use-extensions)
- [🎮 Playground de TEN Agent](#-ten-agent-playground)
  - [️🅰 Ejecutar Playground en `localhost` (Entorno local)](#🅰️-run-playground-in-localhost)
  - [️🅱 Ejecutar Playground en espacio de código(no docker)](#🅱️-run-playground-in-codespaceno-docker)
- [🎥 Ejecutar demo del Agente ](#-ten-agent-demo)
- [️🛳️ Despliegue](#️-deployment)
  - [🅰 Despliegue con Docker](#🅰️-deploying-with-docker)
  - [🅱 Despliegue con otros servicios](#🅱️-deploying-with-other-services)
- [🏗️ Arquitectura de TEN Agent](#️-ten-agent-architecture)
- [🌍 Ecosistema de TEN Framework](#-ten-framework-ecosystem)
- [🤝 Contribuciones](#-contributing)

<br/>

</details>

## 👋 Comenzando y Unirse a la Comunidad TEN

TEN Agent es un agente de voz conversacional IA potenciado por TEN, integrando **DeepSeek**, **Gemini**, **OpenAI**, **RTC**, y hardware como **ESP32**. Habilita capacidades IA en tiempo real como vista, escucha, y habla, y es completamente compatible con plataformas como **Dify** and **Coze**.

<br>

| Canal de la comunidad                                                                                                                                                                  | Propósito                                                                                                   |
|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------|
| [![Discord TEN Community](https://dcbadge.vercel.app/api/server/VnPftUzAMJ?&style=flat&theme=light&color=lightgray)](https://discord.gg/VnPftUzAMJ)                                    | Únete a nuestra comunidad de Discord para conectar con desarrolladores, compartir proyectos y obtener ayuda |
| [![Follow on X](https://img.shields.io/badge/@TenFramework-658_Followers-07C160?logo=x&labelColor=blue&color=white)](https://twitter.com/intent/follow?screen_name=TenFramework)       | Sigue a TEN Framework en X para actualizaciones y anuncios                                                  |
| [![WeChat](https://img.shields.io/badge/TEN_Framework-1K+_members-%2307C160?logo=wechat&labelColor=darkgreen&color=white)](https://github.com/TEN-framework/ten-agent/discussions/170) | Únete a nuestro grupo de WeChat para discusiones en la comunidad China                                      |

<br>

> \[!IMPORTANT]
>
> **Destaca nuestro Repositorio** ⭐️
>
> Obtén notificaciones instantáneas para nuevos lanzamientos y actualizaciones. Tu apoyo nos ayuda a crecer y a mejorar TEN Agent!

<br>

![TEN star us gif](https://github.com/TEN-framework/docs/blob/main/assets/gif/star_us_2.gif?raw=true)

<details>
  <summary><kbd>Historial de estrellas</kbd></summary>
  <picture>
    <img width="100%" src="https://api.star-history.com/svg?repos=ten-framework/ten-agent&type=Date">
  </picture>
</details>

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<br>

## ✨ Funciones

### 1️⃣ 🔥 Ten Agent + Trulience

Construye avatares AI atractivos con TEN Agent usando la colección diversa de opciones de avatares gratuitos de [Trulience](https://trulience.com). Para ponerlo en funcionamiento, solo necesitas 2 pasos:

1. Sigue el README para terminar la configuración y ejecutar el Playground en `localhost:3000`
2. Ingresa el ID del avatar y el [token](https://trulience.com/docs#/authentication/jwt-tokens/jwt-tokens?id=use-your-custom-userid) que obtienes de  [Trulience](https://trulience.com)

<details open>
  <summary><kbd>TEN Agent + Trulience</kbd></summary>

  <br>
  <picture>

![TEN Agent with Trulience](https://github.com/TEN-framework/docs/blob/main/assets/gif/ten-trulience.gif?raw=true)

  </picture>

</details>

<div align="right">

[![][back-to-top]](#readme-top)

</div>

### 2️⃣ [TEN Agent + DeepSeek](https://ten-framework.medium.com/deepgram-deepseek-fish-audio-build-your-own-voice-assistant-with-ten-agent-d3ee65faabe8)

TEN es un marco muy versátil. Dicho esto, TEN Agent es compatible con DeepSeek R1, ¡intenta experimentar conversaciones en tiempo real con DeepSeek R1!

<div align="right">

[![][back-to-top]](#readme-top)

</div>

### 3️⃣ [TEN Agent + ESP32](https://github.com/TEN-framework/TEN-Agent/tree/main/esp32-client)

TEN Agent ahora funciona en la placa de desarrollo Espressif ESP32-S3 Korvo V3, una excelente manera de integrar la comunicación en tiempo real con LLM en hardware.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

### 4️⃣ TEN Agent + Gemini Multimodal Live API

Prueba **Google Gemini Multimodal Live API** con capacidades de **visión en tiempo real** y **detección de pantalla compartida en tiempo real**,  es una extensión lista para usar, junto con herramientas poderosas como **Weather Check** y **Web Search** integradas perfectamente en TEN Agent.

<details>
  <summary><kbd>Gemini 2.0 Multimodal Live API</kbd></summary>

  <br>
  <picture>

![Usecases](https://github.com/TEN-framework/docs/blob/main/assets/gif/gemini.gif?raw=true)

  </picture>

</details>

<div align="right">

[![][back-to-top]](#readme-top)

</div>

### 5️⃣ TEN Agent + Storyteller + Image Generator

Describe un tema y pide a TEN Agent que te cuente una historia mientras también genera imágenes de la historia para proporcionar una experiencia más inmersiva para los niños.

<details>
  <summary><kbd>Storyteller + Image Generator</kbd></summary>

  <br>
  <picture>

![Usecases](https://github.com/TEN-framework/docs/blob/main/assets/jpg/storyteller_image_generator.jpg?raw=true)

  </picture>

</details>

<div align="right">

[![][back-to-top]](#readme-top)

</div>

### 6️⃣ TEN Agent + Dify

[TEN Agent + Dify](https://doc.theten.ai/docs/ten_agent/quickstart-1/use-cases/run_va/run_dify)

TEN ofrece un gran soporte para mejorar la experiencia interactiva en tiempo real en otras plataformas LLM también, consulta los documentos para más información.

<details>
  <summary><kbd>TEN Agent + Dify with RAG</kbd></summary>

  <br>
  <picture>

![Dify with RAG](https://github.com/TEN-framework/docs/blob/main/assets/gif/dify-rag.gif?raw=true)

  </picture>

</details>

<div align="right">

[![][back-to-top]](#readme-top)

</div>

### 7️⃣ TEN Agent + Coze

[TEN Agent + Coze](https://doc.theten.ai/docs/ten_agent/quickstart-1/use-cases/run_va/run_coze)

TEN se integra a la perfección con la plataforma Coze para mejorar las experiencias interactivas en tiempo real. Consulta nuestra documentación para saber cómo aprovechar estas potentes integraciones.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<br>

## 💡 TEN Agent Usecases

![Usecases](https://github.com/TEN-framework/docs/blob/main/assets/jpg/usecases.jpg?raw=true)

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<br>

## 🔌 Extensions listas para usar

![Ready-to-use Extensions](https://github.com/TEN-framework/docs/blob/main/assets/jpg/extensions.jpg?raw=true)

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<br>

## 🎮 Playground de TEN Agent

#### 🅰️ Ejecutar Playground en localhost (Entorno local)

#### Paso 1 ⓵ - Requisitos previos

| Category                           | Requirements                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
|------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Claves**                         | • Agora [App ID](https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web#create-an-agora-project) y [App Certificate](https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web#create-an-agora-project) (minutos gratuitos cada mes) <br>• [OpenAI](https://openai.com/index/openai-api/) clave API (cualquier LLM compatible con OpenAI)<br>• [Deepgram](https://deepgram.com/) ASR (créditos gratuitos disponibles con el registro)<br>• [Elevenlabs](https://elevenlabs.io/) TTS (free credits available with signup) |
| **Instalación**                    | • [Docker](https://www.docker.com/) / [Docker Compose](https://docs.docker.com/compose/)<br>• [Node.js(LTS) v18](https://nodejs.org/en)                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| **Requisitos mínimos del sistema** | • CPU >= 2 Núcleos<br>• RAM >= 4 GB                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |

<br>

> \[!NOTA]
>
> **macOS:  Configuración de Docker en Apple Silicon**
>
> Desmarque "Use Rosetta for x86/amd64 emulation" en la configuración de Docker. Esto puede resultar en tiempos de construcción más lentos en ARM, pero el rendimiento será normal cuando se despliegue en servidores x64.

<!-- ![Docker Setting](https://github.com/TEN-framework/docs/blob/main/assets/gif/docker_setting.gif?raw=true) -->

<br>

#### Paso ⓶ - Construir el agente en Máquina virtual

##### 1. Clonar el repositorio y crear el archivo `.env` desde `.env.example`

```bash
cp ./.env.example ./.env
```

##### 2. Configurar Agora App ID y App Certificate en `.env`

```bash
AGORA_APP_ID=
AGORA_APP_CERTIFICATE=
```

##### 3. Iniciar contenedores de desarrollo de agente

```bash
docker compose up -d
```

##### 4. Ingresar al contenedor

```bash
docker exec -it ten_agent_dev bash
```

##### 5. Construir al agente con el `graph` por defecto ( ~5min - ~8min)

Revisar la carpeta `/examples` para más ejemplos

```bash
task use
```

##### 6. Iniciar el servidor web

```bash
task run
```

<br>

#### Step ⓷ - Personalizar tu agente

1. Abre [localhost:3000](http://localhost:3000) y selecciona un tipo de gráfico
2. Elije un módulo correspondiente
3. Selecciona una extensión y configura sus ajustes de clave API

<details>
  <summary><kbd>Module Picker Example</kbd></summary>

  <br>
  <picture>

![Module Picker Example](https://github.com/TEN-framework/docs/blob/main/assets/gif/module-example.gif?raw=true)

  </picture>

</details>

Ahora, hemos configurado exitosamente el playground. Esto es solo el comienzo de TEN Agent. Hay muchas formas diferentes de explorar y utilizar TEN Agent. Para obtener más información, consulta la [documentación](https://doc.theten.ai/docs/ten_agent/overview).

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<br>

#### 🅱️ Ejecutar Playground en espacio de código(no docker)

GitHub ofrece un espacio de código gratis para cada repositorio, puedes ejecutar el playground en el espacio de código sin usar Docker. También, La velocidad del espacio de código es mucho más rápida que localhost.

Revisa [esta guía](https://doc.theten.ai/docs/ten_agent/setup_development_env/setting_up_development_inside_codespace) para más detalles

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<br>

## 🎥 Ejecutar Demo de TEN Agent 

El Playground y el servidor Demo tienen diferentes propósitos, en pocas palabras, piensa que el Playground es para que personalices a tu agente, y el demo es para que despliegues a tu agente.

Check out [this guide](https://doc.theten.ai/docs/ten_agent/demo) for more details.
<div align="right">

[![][back-to-top]](#readme-top)

</div>

<br>

## 🛳️ Auto hospedaje

#### 🅰️ 🐳 Despliegue con Docker

Una vez que hayas personalizado a tu agente (ya sea usando playground o editando `property.json` directamente), puedes desplegarlo creando una imagen de Docker de lanzamiento para tu servicio.
Lee la [Guía de despliegue](https://doc.theten.ai/docs/ten_agent/deployment_ten_agent/deploy_agent_service) para información detallada acerca del despliegue.

<br>

#### 🅱️ Despliegue con otros servicios

*Próximamente...*

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<br>

## 🏗️ Arquitectura de TEN Agent 

1️⃣ **TEN Agent App**: Aplicación central que administra extensiones y flujo de datos basado en configuración de gráficos.

2️⃣ **Dev Server**: `port:49480`- Servidor local para propósitos de desarrollo.

3️⃣ **Web Server**: `port:8080`- Servidor Golang que maneja peticiones HTTP y gestión de procesos del agente

4️⃣ **Front-end UI**:

- `port:3000` Playground - Para personalizar y probar la configuración de tu agente.
- `port:3002` Demo - Para desplegar tu agente sin selector de módulo.

![Components Diagram](https://github.com/TEN-framework/docs/blob/main/assets/jpg/diagram.jpg?raw=true)

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<br>

## 🌍 Ecosistema de TEN Framework 

| [**🏚️ TEN Framework**][ten-framework-link]<br/>TEN, un framework de agente IA para crear varios agentes IA los cuales soportan conversaciones en tiempo real.<br/><br/>![][ten-framework-shield]                                                                                                                                                   | ![][ten-framework-banner] |
|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------| :----------------------------------------- |
| [**🎙️ TEN Agent**][ten-agent-link]<br/>TEN Agent es un agente de voz conversacional IA potenciado por TEN, integrando DeepSeek, Gemini, OpenAI, RTC, y hardware como ESP32. Habilita capacidades IA en tiempo real como vista, escucha, y habla, y es completamente compatible con plataformas como Dify and Coze..<br/><br/>![][ten-agent-shield] | ![][ten-agent-banner] |
| **🎨 TMAN Designer** `alpha`<br/>TMAN Designer es una opción que requiere poco o ningún código para creae un agente de voz atractivo. Con su interfaz de flujo de trabajo intuitiva, puedes crear cosas fácilmente. Incluye tiempo de ejecución, temas oscuros/claros, editores y terminales integrados.<br/><br/>![][tman-designer-shield]         | ![][tman-designer-banner] |
| **📒 TEN Portal**<br/>El sitio oficial de TEN framework, contiene documentación, blog y demostraciones.<br/><br/>![][ten-docs-shield]                                                                                                                                                                                                     | ![][ten-docs-banner]   |

<div align="right">

[![][back-to-top]](#readme-top)

</div>

<br>

## 🤝 Contribuciones

¡Le damos la bienvenida a cualquier forma de colaboración de código abierto! Ya sea que estés arreglando errores, añadiendo características, mejorando documentación o compartiendo ideas - tu contribución ayuda a avanzar en herramientas personalizadas de IA. Revisa nuestros GitHub Issues y Proyectos para encontrar maneras de contribuir y mostrar tus habilidades. ¡Juntos, podemos construir algo sorprendente!
<br>

> \[!TIP]
>
> **Bienvenidos todos los tipos de contribuciones** 🙏
>
> ¡Únete a nosotros para mejorar TEN! Cada contribución hace la diferencia. desde código hasta documentación. ¡Comparte tus proyectos de TEN Agent en redes sociales para inspirar a otros!
>
> Conecta con el mantenedor de TEN [@cyfyifanchen](https://github.com/cyfyifanchen) en GitHub y [@elliotchen100](https://x.com/elliotchen100) en 𝕏 para actualizaciones del proyecto, discusiones y oportunidades de colaboración.


### Contribuyentes de Código

[![TEN](https://contrib.rocks/image?repo=TEN-framework/ten-agent)](https://github.com/TEN-framework/ten-agent/graphs/contributors)

### Directrices de Contribución 

¡Las contribuciones son bienvenidas! Por favor, lee primero las [directrices de contribución](../code-of-conduct/contributing.md).

### Licencia

Este proyecto está licenciado bajo la Licencia [Apache 2.0](../../LICENSE).


<div align="right">

[![][back-to-top]](#readme-top)

</div>

[back-to-top]:https://img.shields.io/badge/-Volver_al_inicio-gray?style=flat-square

[ten-framework-shield]: https://img.shields.io/github/stars/ten-framework/ten_framework?color=ffcb47&labelColor=gray&style=flat-square&logo=github&label=Estrellas
[ten-agent-shield]: https://img.shields.io/github/stars/ten-framework/ten-agent?color=ffcb47&labelColor=gray&style=flat-square&logo=github&label=Estrellas
[tman-designer-shield]: https://img.shields.io/github/stars/ten-framework/ten_ai_base?color=ffcb47&labelColor=gray&style=flat-square&logo=github&label=Estrellas
[ten-docs-shield]: https://img.shields.io/github/stars/ten-framework/docs?color=ffcb47&labelColor=gray&style=flat-square&logo=github&label=Estrellas

[ten-framework-link]: https://github.com/ten-framework/ten_framework
[ten-agent-link]: https://github.com/ten-framework/ten-agent

[ten-framework-banner]: https://github.com/TEN-framework/docs/blob/main/assets/jpg/1.jpg?raw=true
[ten-agent-banner]: https://github.com/TEN-framework/docs/blob/main/assets/jpg/3.jpg?raw=true
[tman-designer-banner]: https://github.com/TEN-framework/docs/blob/main/assets/jpg/4.jpg?raw=true
[ten-docs-banner]: https://github.com/TEN-framework/docs/blob/main/assets/jpg/2.jpg?raw=true

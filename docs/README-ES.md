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

[Sitio oficial][official-site]
•
[Documentación][documentation]
•
[Blog][blog]

[![README en inglés][lang-en-badge]][lang-en-readme]
[![Guía en chino simplificado][lang-zh-badge]][lang-zh-readme]
[![README en japonés][lang-jp-badge]][lang-jp-readme]
[![README en coreano][lang-kr-badge]][lang-kr-readme]
[![README en español][lang-es-badge]][lang-es-readme]
[![README en francés][lang-fr-badge]][lang-fr-readme]
[![README en italiano][lang-it-badge]][lang-it-readme]

<a href="https://trendshift.io/repositories/13772?utm_source=repository-badge&amp;utm_medium=badge&amp;utm_campaign=badge-repository-13772" target="_blank" rel="noopener noreferrer"><img src="https://trendshift.io/api/badge/repositories/13772" alt="TEN-framework%2Ften-framework | Trendshift" width="250" height="55"/></a>

</div>

<br>

<details open>
  <summary><kbd>Tabla de contenido</kbd></summary>

  <br>

- [Bienvenido a TEN][welcome-to-ten]
- [Ejemplos de agente][agent-examples-section]
- [Inicio rápido con los ejemplos de agente][quick-start]
  - [Entorno local][localhost-section]
  - [Codespaces][codespaces-section]
- [Auto-hospedaje de los ejemplos de agente][agent-examples-self-hosting]
  - [Implementar con Docker][deploying-with-docker]
  - [Implementar en otros servicios en la nube][deploying-with-other-cloud-services]
- [Mantente al día][stay-tuned]
- [Ecosistema TEN][ten-ecosystem-anchor]
- [Preguntas][questions]
- [Cómo contribuir][contributing]
  - [Personas contribuidoras][code-contributors]
  - [Guía de contribución][contribution-guidelines]
  - [Licencia][license-section]

<br/>

</details>

<a name="welcome-to-ten"></a>

## Bienvenido a TEN

TEN es un marco de código abierto para agentes conversacionales de voz impulsados por IA.

El [ecosistema TEN][ten-ecosystem-anchor] incluye [TEN Framework][ten-framework-link], [Ejemplos de agente][ten-agent-example-link], [VAD][ten-vad-link], [Turn Detection][ten-turn-detection-link] y [Portal][ten-portal-link].

<br>

| Canal de la comunidad | Propósito |
| ---------------- | ------- |
| [![Follow on X][follow-on-x-badge]][follow-on-x] | Sigue TEN Framework en X para enterarte de novedades y anuncios |
| [![Discord TEN Community][discord-badge]][discord-invite] | Únete a la comunidad de Discord y conecta con otras personas desarrolladoras |
| [![Follow on LinkedIn][linkedin-badge]][linkedin] | Sigue TEN Framework en LinkedIn para recibir actualizaciones y noticias |
| [![Hugging Face Space][hugging-face-badge]][hugging-face] | Explora nuestros espacios y modelos en la comunidad de Hugging Face |
| [![WeChat][wechat-badge]][wechat-discussion] | Únete al grupo de WeChat para conversar con la comunidad china |

<br>

<a name="agent-examples"></a>

## Ejemplos de agente

<br>

![Image][voice-assistant-image]

<strong>Asistente de voz multipropósito</strong> — Un asistente en tiempo real, de baja latencia y alta calidad que puedes ampliar con [memoria][memory-example], [VAD][voice-assistant-vad-example], [detección de turnos][voice-assistant-turn-detection-example] y otras extensiones.

Consulta el [código de ejemplo][voice-assistant-example] para obtener más detalles.

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

![Image][doodler-image]

<strong>Doodler</strong> — Un tablero de garabatos que convierte indicaciones habladas o escritas en bocetos sencillos a mano, con una paleta de crayones y dibujo en tiempo real.

[Código de ejemplo][doodler-example]

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

![Image][lip-sync-image]

<strong>Avatares con sincronización labial</strong> — Compatible con múltiples proveedores de avatares. La demo incluye a Kei, un personaje anime con sincronización labial gracias a Live2D, y pronto añadirá avatares realistas de Trulience, HeyGen y Tavus.

Revisa el [código de ejemplo][voice-assistant-live2d-example] para Live2D.

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

![Image][speech-diarization-image]

<strong>Diarización de voz</strong> — Detección y etiquetado de hablantes en tiempo real. El juego "Who Likes What" muestra un caso de uso interactivo.

[Código de ejemplo][speechmatics-diarization-example]

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

![Image][sip-call-image]

<strong>Llamada SIP</strong> — Extensión SIP que habilita llamadas telefónicas impulsadas por TEN.

[Código de ejemplo][voice-assistant-sip-example]

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

![Image][transcription-image]

<strong>Transcripción</strong> — Herramienta de transcripción que convierte audio en texto.

[Código de ejemplo][transcription-example]

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

![Image][esp32-image]

<strong>ESP32-S3 Korvo V3</strong> — Ejecuta el ejemplo de TEN Agent en la placa de desarrollo Espressif ESP32-S3 Korvo V3 para integrar comunicación impulsada por LLM con hardware.

Consulta la [guía de integración][esp32-guide] para conocer más.

<br>
<div align="right">

[![][back-to-top]][readme-top]

</div>

<a name="quick-start-with-agent-examples"></a>

## Inicio rápido con los ejemplos de agente

<a name="localhost"></a>

### Entorno local

#### Paso ⓵ - Requisitos previos

| Categoría | Requisitos |
| --- | --- |
| **Credenciales** | • Agora [App ID][agora-app-certificate] y [App Certificate][agora-app-certificate] (minutos gratuitos mensuales)<br>• Clave de API de [OpenAI][openai-api] (cualquier LLM compatible con el protocolo de OpenAI)<br>• ASR de [Deepgram][deepgram] (créditos gratuitos al registrarte)<br>• TTS de [ElevenLabs][elevenlabs] (créditos gratuitos al registrarte) |
| **Instalación** | • [Docker][docker] / [Docker Compose][docker-compose]<br>• [Node.js (LTS) v18][nodejs] |
| **Requisitos mínimos del sistema** | • CPU ≥ 2 núcleos<br>• RAM ≥ 4 GB |

<br>

![divider][divider-light]
![divider][divider-dark]

<!-- > [!NOTE]
> **macOS: configuración de Docker en Apple Silicon**
>
> Desmarca "Use Rosetta for x86/amd64 emulation" en los ajustes de Docker. La compilación puede tardar más en ARM, pero el rendimiento será normal al desplegar en servidores x64. -->

#### Paso ⓶ - Compila los ejemplos dentro de una VM

##### 1. Clona el repositorio, entra en `ai_agents` y crea un `.env` a partir de `.env.example`

```bash
cd ai_agents
cp ./.env.example ./.env
```

##### 2. Configura el Agora App ID y App Certificate en `.env`

```bash
AGORA_APP_ID=
AGORA_APP_CERTIFICATE=

# Ejecutar el ejemplo predeterminado del asistente de voz
# Deepgram (requerido para STT)
DEEPGRAM_API_KEY=your_deepgram_api_key_here

# OpenAI (requerido para el modelo de lenguaje)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o

# ElevenLabs (requerido para TTS)
ELEVENLABS_TTS_KEY=your_elevenlabs_api_key_here
```

##### 3. Inicia los contenedores de desarrollo del agente

```bash
docker compose up -d
```

##### 4. Entra en el contenedor

```bash
docker exec -it ten_agent_dev bash
```

##### 5. Compila el agente con el ejemplo predeterminado (≈5‑8 min)

En la carpeta `agents/examples` encontrarás más muestras.
Empieza con una de estas opciones:

```bash
# Usa el asistente de voz encadenado
cd agents/examples/voice-assistant

# O usa el asistente voz-a-voz en tiempo real
cd agents/examples/voice-assistant-realtime
```

##### 6. Inicia el servidor web

Ejecuta `task install` antes del primer inicio y después de cambiar las dependencias o el código fuente de Go. Este comando instala las dependencias de TEN, Python y frontend, y compila el servidor API de Go. Los cambios que solo afectan a Python no requieren reinstalación.

```bash
task install
task run
```

##### 7. Accede al agente

Cuando el ejemplo esté en marcha podrás usar estas interfaces:

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
- UI de ejemplos de agente: <http://localhost:3000>

<br>

![divider][divider-light]
![divider][divider-dark]

#### Paso ⓷ - Personaliza tu ejemplo de agente

1. Abre [localhost:49483][localhost-49483].
2. Haz clic derecho en las extensiones STT, LLM y TTS.
3. Rellena sus propiedades con las API keys correspondientes.
4. Envía los cambios; el ejemplo actualizado aparecerá en [localhost:3000][localhost-3000].

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

#### Ejecuta una app de transcripción desde TEN Manager sin Docker (Beta)

TEN también ofrece una app de transcripción que puedes ejecutar en TEN Manager sin usar Docker.

Consulta la [guía de inicio rápido][quick-start-guide-ten-manager] para más detalles.

<br>

![divider][divider-light]
![divider][divider-dark]

<br>

<a name="codespaces"></a>

### Codespaces

GitHub ofrece Codespaces gratuitos para cada repositorio. Puedes ejecutar los ejemplos de agente allí sin usar Docker, y normalmente inicia más rápido que un entorno local con contenedores.

[codespaces-shield]: <https://github.com/codespaces/badge.svg>
[![][codespaces-shield]][codespaces-new]

Consulta [esta guía][codespaces-guide] para obtener más detalles.

<div align="right">

[![][back-to-top]][readme-top]

</div>

<br>

<a name="agent-examples-self-hosting"></a>

## Auto-hospedaje de los ejemplos de agente

<a name="deploying-with-docker"></a>

### Implementar con Docker

Cuando personalices tu agente (ya sea con TMAN Designer o editando `property.json`), crea una imagen de Docker lista para producción y despliega tu servicio.

##### Publicar como imagen de Docker

**Nota**: Ejecuta estos comandos fuera de cualquier contenedor Docker.

###### Compilar la imagen

```bash
cd ai_agents
docker build -f agents/examples/<example-name>/Dockerfile -t example-app .
```

###### Ejecutar

```bash
docker run --rm -it --env-file .env -p 3000:3000 example-app
```

<br>

![divider][divider-light]
![divider][divider-dark]

<a name="deploying-with-other-cloud-services"></a>

### Implementar en otros servicios en la nube

Puedes dividir el despliegue en dos partes si deseas alojar TEN en proveedores como [Vercel][vercel] o [Netlify][netlify].

1. Ejecuta el backend de TEN en cualquier plataforma preparada para contenedores (una VM con Docker, Fly.io, Render, ECS, Cloud Run, etc.). Usa la imagen de ejemplo sin modificar y expón el puerto `8080`.
2. Despliega solo el frontend en Vercel o Netlify. Apunta la raíz del proyecto a `ai_agents/agents/examples/<example>/frontend`, ejecuta `pnpm install` (o `bun install`), luego `pnpm build` (o `bun run build`) y conserva el directorio de salida `.next` predeterminado.
3. Configura las variables de entorno en el panel de tu hosting. `AGENT_SERVER_URL` debe apuntar al backend y añade cualquier clave `NEXT_PUBLIC_*` necesaria (por ejemplo, credenciales de Agora visibles para el navegador).
4. Asegúrate de que tu backend acepte solicitudes desde el origen del frontend, ya sea mediante CORS abierto o usando el middleware proxy incluido.

Con esta arquitectura, el backend gestiona los procesos de larga duración y el frontend alojado solo reenvía el tráfico al backend.

<div align="right">

[![][back-to-top]][readme-top]

</div>

<br>

<a name="stay-tuned"></a>

## Mantente al día

Recibe notificaciones instantáneas sobre nuevas versiones y actualizaciones. Tu apoyo nos ayuda a seguir mejorando TEN.

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

| Proyecto | Vista previa |
| ------- | ------- |
| [**️TEN Framework**][ten-framework-link]<br>Marco de código abierto para agentes conversacionales.<br><br>![][ten-framework-shield] | ![][ten-framework-banner] |
| [**TEN VAD**][ten-vad-link]<br>Detector de actividad de voz (VAD) en streaming, ligero y de baja latencia.<br><br>![][ten-vad-shield] | ![][ten-vad-banner] |
| [**️TEN Turn Detection**][ten-turn-detection-link]<br>Permite diálogo full-duplex mediante detección de turnos.<br><br>![][ten-turn-detection-shield] | ![][ten-turn-detection-banner] |
| [**TEN Agent Examples**][ten-agent-example-link]<br>Casos de uso impulsados por TEN.<br><br> | ![][ten-agent-example-banner] |
| [**TEN Portal**][ten-portal-link]<br>Sitio oficial con documentación y blog.<br><br>![][ten-portal-shield] | ![][ten-portal-banner] |

<br>
<div align="right">

[![][back-to-top]][readme-top]

</div>

<br>

<a name="questions"></a>

## Preguntas

TEN Framework también está disponible en plataformas de preguntas y respuestas impulsadas por IA. Ofrecen soporte multilingüe para todo, desde la configuración básica hasta la implementación avanzada.

| Servicio | Enlace |
| ------- | ---- |
| DeepWiki | [![Ask DeepWiki][deepwiki-badge]][deepwiki] |
| ReadmeX | [![ReadmeX][readmex-badge]][readmex] |

<br>
<div align="right">

[![][back-to-top]][readme-top]

</div>

<a name="contributing"></a>

## Cómo contribuir

¡Toda forma de colaboración de código abierto es bienvenida! Ya sea que corrijas bugs, agregues funciones, mejores la documentación o compartas ideas, tus aportes ayudan a impulsar herramientas de IA personalizadas. Revisa los Issues y Projects de GitHub para encontrar oportunidades y mostrar tus habilidades. ¡Construyamos juntas y juntos algo increíble!

<br>

> [!TIP]
>
> **Agradecemos todo tipo de contribuciones** 🙏
>
> Acompáñanos a mejorar TEN. Cada PR, issue o guía suma. Comparte tus proyectos con TEN Agent en redes sociales para inspirar a la comunidad.
>
> Ponte en contacto con la persona mantenedora [@elliotchen200][elliotchen200-x] en 𝕏 o [@cyfyifanchen][cyfyifanchen-github] en GitHub para recibir novedades, debatir ideas y explorar colaboraciones.

<br>

![divider][divider-light]
![divider][divider-dark]

<a name="code-contributors"></a>

### Personas contribuidoras

[![TEN][contributors-image]][contributors]

<a name="contribution-guidelines"></a>

### Guía de contribución

¡Contribuye cuando quieras! Lee primero la [guía de contribución][contribution-guidelines-doc].

<br>

![divider][divider-light]
![divider][divider-dark]

<a name="license"></a>

### Licencia

1. Todo TEN Framework, salvo los directorios listados más abajo, se publica bajo la licencia Apache 2.0 con restricciones adicionales. Consulta el archivo [LICENSE][license-file] en la raíz del proyecto.
2. Los componentes dentro de `packages` se liberan bajo Apache License 2.0. Cada paquete contiene su propio archivo `LICENSE` con los detalles.
3. Las dependencias de terceros que usa TEN Framework se describen en la carpeta [third_party][third-party-folder].

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

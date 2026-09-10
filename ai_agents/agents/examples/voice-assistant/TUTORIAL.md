# Tutorial: Blaze realtime voice stack

How a new developer runs the TEN **voice assistant** with **Blaze STT + Blaze TTS** end to end.

Graph name: **`voice_assistant_blaze_full`**

Pipeline:

```text
Mic (browser)
  → Agora RTC
  → blaze_stt_python   (WebSocket  wss://…/v1/stt/realtime, model stt-stream-1.5)
  → openai_llm2_python (chat completion)
  → blaze_tts_python   (WebSocket  wss://…/v1/tts/realtime, model 2.0-realtime)
  → Agora RTC
  → Speaker (browser)
```

Default language in the graph is **Vietnamese (`vi`)**. Greeting text is Vietnamese as well.

---

## 1. What you need

| Requirement | Notes |
| ----------- | ----- |
| Docker + Docker Compose | Dev runs inside `ten_agent_dev` |
| Agora project | Real-time audio between browser and agent |
| Blaze API key | From [Blaze](https://app.blaze.vn) / your Blaze admin |
| OpenAI API key | LLM for the reply (or any OpenAI-compatible key + base URL) |
| Hardware | ~2+ CPU cores, 4 GB RAM |

You do **not** need Deepgram or ElevenLabs for this graph.

---

## 2. Clone and enter the example

```bash
git clone <your-fork-or-upstream>/ten-framework.git
cd ten-framework/ai_agents
```

This tutorial assumes commands run from `ai_agents/` unless noted.

---

## 3. Configure `ai_agents/.env`

Copy the example if you do not have a local file yet:

```bash
cp .env.example .env
```

Fill at least:

```bash
# Agora (browser ↔ agent audio)
AGORA_APP_ID=your_agora_app_id
AGORA_APP_CERTIFICATE=   # optional but recommended

# OpenAI-compatible LLM
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
# OPENAI_API_BASE=https://api.openai.com/v1   # override if needed
# OPENAI_PROXY_URL=

# Blaze Speech (https://api.blaze.vn)
BLAZE_API_KEY=your_blaze_key
BLAZE_STT_API_KEY=your_blaze_key
BLAZE_TTS_API_KEY=your_blaze_key
BLAZE_STT_API_URL=https://api.blaze.vn
BLAZE_TTS_API_URL=https://api.blaze.vn

# Runtime (defaults from .env.example are fine)
LOG_PATH=/tmp/ten_agent
LOG_STDOUT=true
SERVER_PORT=8080
GRAPH_DESIGNER_SERVER_PORT=49483
```

Notes:

- `BLAZE_API_KEY` is a convenience alias. The graph reads `BLAZE_STT_API_KEY` and `BLAZE_TTS_API_KEY`. Set all three to the same value unless you intentionally split keys.
- Never commit `.env`. It is gitignored / should stay local.
- After changing `.env`, recreate the container so env is reloaded (see §8).

---

## 4. Start the dev container

```bash
cd ai_agents
docker compose up -d
docker ps | grep ten_agent_dev
```

Default host ports:

| Host port | Service |
| --------- | ------- |
| `3000` | Playground (Next.js) |
| `8080` | Go API server |
| `49483` | TMAN Designer |

### Port already in use?

If `docker compose up` fails with `Bind for 0.0.0.0:3000 failed`, something else on the machine owns that port. Remap the playground only:

Create `ai_agents/docker-compose.local.yml` (local-only; do not commit secrets or machine-specific files unless your team wants them):

```yaml
services:
  ten_agent_dev:
    ports: !override
      - "${GRAPH_DESIGNER_SERVER_PORT}:${GRAPH_DESIGNER_SERVER_PORT}"
      - "3002:3000"
      - "8080:8080"
```

Then:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d
```

Use **http://localhost:3002** instead of `:3000` below. The wide default publish range `8000-9001` can also collide with other stacks; the override above avoids that.

---

## 5. Install the voice-assistant example

First install can take several minutes (Go API build, Python deps, playground `bun install`).

```bash
docker exec -w /app/agents/examples/voice-assistant ten_agent_dev bash -lc 'task install'
```

What this does:

1. `tman install` for the tenapp + Blaze extension packages  
2. Python deps for extensions under `tenapp/`  
3. Playground frontend install  
4. Builds `server/bin/api`

After a **container recreate**, re-run `task install` (Python deps inside the image are not always persisted the way you expect).

---

## 6. Run the stack

```bash
docker exec -d -w /app/agents/examples/voice-assistant ten_agent_dev \
  bash -lc 'task run > /tmp/ten_task_run.log 2>&1'
```

Always start with `task run` (API + playground + designer together). Do not start `./bin/api` alone for normal demos.

### Health checks

```bash
curl -s http://localhost:8080/health
# {"code":"0","data":null,"msg":"ok"}

curl -s http://localhost:8080/graphs | python3 -c \
  'import sys,json; d=json.load(sys.stdin); print([g["name"] for g in d["data"]])'
# ... should include voice_assistant_blaze_full
```

Tail logs:

```bash
docker exec ten_agent_dev tail -f /tmp/ten_task_run.log
# or filter:
docker exec ten_agent_dev bash -lc 'tail -f /tmp/ten_task_run.log | grep --line-buffered -i blaze'
```

---

## 7. Open the playground and talk

1. Open:

   ```text
   http://localhost:3000/?graph=voice_assistant_blaze_full
   ```

   (or `http://localhost:3002/?graph=voice_assistant_blaze_full` if you remapped)

2. Allow microphone access in the browser.
3. Connect / join the session.
4. Speak Vietnamese (or change `language` — see §9).
5. You should hear the agent greeting, then replies via Blaze TTS.

Optional: TMAN Designer at http://localhost:49483 to inspect the graph visually.

---

## 8. Smoke-test Blaze APIs without the full UI

From the **repo root** (host Python with network access), with keys in `ai_agents/.env`:

```bash
python ai_agents/scripts/smoke_blaze.py
python ai_agents/scripts/smoke_blaze.py --skip-stt --text "Xin chào"
python ai_agents/scripts/smoke_blaze.py --skip-tts --audio /path/to/sample.wav
```

This hits Blaze HTTP helpers used by the smoke script. The **live agent graph** uses the **realtime WebSocket** clients in:

- `agents/ten_packages/extension/blaze_stt_python/extension.py`
- `agents/ten_packages/extension/blaze_tts_python/ten_tts_client.py`

If smoke fails with auth / 401, fix keys before debugging Agora or the playground.

---

## 9. Customize the Blaze graph

Graph definition:

`agents/examples/voice-assistant/tenapp/property.json`  
→ `predefined_graphs[]` entry named `voice_assistant_blaze_full`

Useful fields today:

| Node | Key settings |
| ---- | ------------ |
| `stt` (`blaze_stt_python`) | `params.language`, `params.model` (`stt-stream-1.5`), `params.sample_rate` (**16000**), optional `topic` / `context` |
| `llm` (`openai_llm2_python`) | `api_key`, `model`, `greeting`, `base_url` |
| `tts` (`blaze_tts_python`) | `params.speaker_id`, `params.language`, `params.model` (`2.0-realtime`), `params.sample_rate` (**24000**), `params.audio_speed` |

Example TTS speaker in the graph:

```text
HN-Nu-CSKH-HuongGiang
```

Change `speaker_id` / `language` / greetings in `property.json`, then do a **nuclear restart** of `task run` processes (see §11). Config-only tweaks that workers already pick up from env may not need a restart; **new graphs or node wiring changes do**.

---

## 10. Code map (where to look)

```text
ai_agents/
├── .env / .env.example              # keys (Blaze, Agora, OpenAI)
├── docker-compose.yml               # ten_agent_dev
├── scripts/smoke_blaze.py           # API smoke test
├── playground/                      # Next.js UI (:3000)
├── server/                          # Go API (:8080)
└── agents/
    ├── examples/voice-assistant/
    │   ├── Taskfile.yml             # task install / task run
    │   ├── tenapp/property.json     # voice_assistant_blaze_full
    │   └── tenapp/manifest.json     # pulls blaze_* extensions
    └── ten_packages/extension/
        ├── blaze_stt_python/        # realtime STT WebSocket
        └── blaze_tts_python/        # realtime TTS WebSocket
```

Extension READMEs:

- [`blaze_stt_python/README.md`](../../ten_packages/extension/blaze_stt_python/README.md)
- [`blaze_tts_python/README.md`](../../ten_packages/extension/blaze_tts_python/README.md)

---

## 11. Troubleshooting

| Symptom | What to check |
| ------- | ------------- |
| Compose fails on port bind | Remap playground (§4); stop conflicting containers or use `docker-compose.local.yml` |
| `/health` not ok | `docker ps`; `tail /tmp/ten_task_run.log`; confirm `task run` is up |
| Graph missing from `/graphs` | Re-`task install`; confirm `property.json` has `voice_assistant_blaze_full`; restart `task run` |
| Connects but no transcription | `BLAZE_STT_API_KEY`, `BLAZE_STT_API_URL`, network to `api.blaze.vn`, mic permission, language |
| Transcription OK, no voice | `BLAZE_TTS_API_KEY`, `speaker_id`, TTS model, Agora publish audio |
| LLM errors in logs | `OPENAI_API_KEY` / model / base URL |
| After editing `.env` | `docker compose down && docker compose up -d`, then `task install`, then `task run` |
| After editing extension Python | Restart `task run` processes (no need to rebuild image) |

**Nuclear restart** (safe after graph / process mess):

```bash
docker exec ten_agent_dev bash -lc \
  "pkill -9 -f 'bin/api'; pkill -9 -f bun; pkill -9 -f node; \
   pkill -9 -f next-server; pkill -9 -f tman; \
   rm -f /app/playground/.next/dev/lock"
sleep 5
docker exec -d -w /app/agents/examples/voice-assistant ten_agent_dev \
  bash -lc 'task run > /tmp/ten_task_run.log 2>&1'
```

---

## 12. Quick checklist

- [ ] `ai_agents/.env` has Agora + OpenAI + Blaze keys  
- [ ] `docker compose up -d` → `ten_agent_dev` running  
- [ ] `task install` finished without errors  
- [ ] `task run` → `/health` ok and graph listed  
- [ ] Open `/?graph=voice_assistant_blaze_full`  
- [ ] Mic allowed; greeting plays; conversation works  

---

## Related docs

- Example overview: [README.md](./README.md)
- Agent setup (generic): `docs/ai/L1/01_setup.md` in the repo root docs tree
- Blaze STT / TTS package READMEs under `agents/ten_packages/extension/blaze_*_python/`

# 01 Setup

> Environment setup, local development, and quick commands for TEN Framework AI Agents.

## Prerequisites

| Requirement       | Version / Notes                                              |
| ----------------- | ------------------------------------------------------------ |
| Docker + Compose  | Required for container-based development                     |
| Node.js           | LTS v18+ on host; container has Node 22                      |
| API Keys          | Agora App ID, LLM provider, ASR provider, TTS provider      |
| Hardware          | 2+ CPU cores, 4 GB RAM minimum                              |

## Docker Container

```bash
cd /home/ubuntu/ten-framework/ai_agents
docker compose up -d
docker ps | grep ten_agent_dev   # Verify running
```

Container image: `ghcr.io/ten-framework/ten_agent_build:0.7.14`

**Permissions:** if your user is not in the `docker` group, prefix every
`docker` / `docker exec` / `docker compose` command in this guide with `sudo`.
A bare `docker ps` failing with `permission denied while trying to connect to
the docker API at unix:///var/run/docker.sock` is the diagnostic — switch to
`sudo docker ps` and the rest works.

## Environment Variables

**Single .env file**: `ai_agents/.env` — the ONLY source of environment config.

| Variable                     | Purpose                      | Required |
| ---------------------------- | ---------------------------- | -------- |
| `AGORA_APP_ID`               | Agora RTC app identifier     | Yes      |
| `AGORA_APP_CERTIFICATE`      | Agora RTC certificate        | No       |
| `OPENAI_API_KEY`             | LLM provider                 | Yes      |
| `OPENAI_MODEL`               | Model name (e.g., `gpt-4o`)  | Yes      |
| `DEEPGRAM_API_KEY`           | ASR provider                 | Yes      |
| `ELEVENLABS_TTS_KEY`         | TTS provider                 | Yes      |
| `LOG_PATH`                   | Container log directory bind | Yes      |
| `LOG_STDOUT`                 | Worker log visibility         | Yes (`true`) |
| `SERVER_PORT`                | API server port               | Yes (`8080`) |
| `WORKERS_MAX`                | Max concurrent sessions       | Yes (`100`)  |
| `WORKER_QUIT_TIMEOUT_SECONDS`| Worker idle timeout           | Yes (`60`)   |

See `.env.example` for the complete list. Extensions may require different provider
keys (Deepgram, ElevenLabs, Cartesia, Azure, AWS, Rime, etc.) — check extension
README files.

## Install and Run

```bash
# 1. Install Python dependencies (NOT persisted across container restarts)
docker exec ten_agent_dev bash -c \
  "cd /app/agents/examples/<example>/tenapp && \
   bash scripts/install_python_deps.sh"

# 2. Build and install (5-8 minutes first time)
docker exec ten_agent_dev bash -c \
  "cd /app/agents/examples/<example> && task install"

# 3. Start everything (API server + playground + TMAN Designer)
docker exec -d ten_agent_dev bash -c \
  "cd /app/agents/examples/<example> && \
   task run > /tmp/task_run.log 2>&1"
```

**Fresh worktree/checkout**: run `task install` FIRST (it includes the
python-deps step). Running `install_python_deps.sh` alone on a fresh tree
fails with `failed to build go app` because `ten_packages/system/` (including
`ten_runtime_go`) is only populated by the install. Step 1 above is for
refreshing deps after a container restart, when packages already exist.

Typical choices:
- `voice-assistant` for standard vendor iteration and demo graphs
- `voice-assistant-advanced` for generated multi-graph setups

**CRITICAL**: Always use `task run` to start — never run `./bin/api` directly.

## Ports

| Port  | Service          |
| ----- | ---------------- |
| 8080  | Go API server    |
| 3000  | Playground (Next.js) |
| 49483 | TMAN Designer    |

## Health Checks

```bash
curl -s http://localhost:8080/health
# {"code":"0","data":null,"msg":"ok"}

curl -s http://localhost:8080/graphs | jq -r '.data[].name'
# voice_assistant, voice_assistant_oracle, etc.
```

## Restart Procedures

| What Changed                    | Container? | Server?           | Frontend?         |
| ------------------------------- | ---------- | ----------------- | ----------------- |
| `property.json` (graphs added)  | No         | Nuclear restart   | Nuclear restart   |
| `property.json` (config only)   | No         | No                | No                |
| `.env` file                     | Yes        | Yes               | No                |
| Python extension code           | No         | Yes               | No                |
| Go server code                  | No         | Yes + `task install` | No             |

**Nuclear restart** (safest after graph changes):

```bash
sudo docker exec ten_agent_dev bash -c \
  "pkill -9 -f 'bin/api'; pkill -9 -f bun; pkill -9 -f node; \
   pkill -9 -f next-server; pkill -9 -f tman"
sudo docker exec ten_agent_dev bash -c "rm -f /app/playground/.next/dev/lock"
sleep 30
sudo docker exec -d ten_agent_dev bash -c \
  "cd /app/agents/examples/<example> && task run > /tmp/task_run.log 2>&1"
```

**After container restart**: always reinstall Python deps, then `task run`.

**After .env changes**: `docker compose down && docker compose up -d`, reinstall deps, `task run`.

## Logs

```bash
# All logs (inside container)
docker exec ten_agent_dev tail -f /tmp/task_run.log

# Filter by extension or channel
docker exec ten_agent_dev tail -f /tmp/task_run.log | grep --line-buffered "deepgram"

# If grep reports binary/noisy output, inspect printable strings instead
docker exec ten_agent_dev bash -c "strings /tmp/task_run.log | tail -n 80"
```

## Related Deep Dives

- [Deployment](L2/deployment.md) — Docker Compose, Cloudflare tunnel, Nginx, Grafana monitoring

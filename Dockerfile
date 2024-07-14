FROM agoraio/astra_agents_build:latest AS builder

ARG SESSION_CONTROL_CONF=session_control.conf

WORKDIR /app

COPY . .
COPY agents/manifest.json.example agents/manifest.json
COPY agents/manifest.json.elevenlabs.example agents/manifest.elevenlabs.json
COPY agents/manifest.json.cn.example agents/manifest.cn.json
COPY agents/manifest.json.en.example agents/manifest.en.json
COPY agents/${SESSION_CONTROL_CONF} agents/session_control.conf

RUN make build && \
    cd agents && ./scripts/package.sh

FROM ubuntu:22.04

RUN apt-get clean && apt-get update && apt-get install -y --no-install-recommends \
    libasound2 \
    libgstreamer1.0-dev \
    libunwind-dev \
    libc++1 \
    libssl-dev \
    ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/* && rm -rf /tmp/*

WORKDIR /app

COPY --from=builder /app/agents/.release/ agents/
COPY --from=builder /app/server/bin/api /app/server/bin/api

EXPOSE 8080

ENTRYPOINT ["/app/server/bin/api"]

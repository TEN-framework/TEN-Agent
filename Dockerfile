FROM ghcr.io/rte-design/astra_agents_build:0.3.3 AS builder

ARG SESSION_CONTROL_CONF=session_control.conf

WORKDIR /app

COPY . .
COPY agents/manifest.json.example agents/manifest.json
COPY agents/manifest.json.elevenlabs.example agents/manifest.elevenlabs.json
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
    python3 \
    python3-venv \
    python3-pip \
    python3-dev \
    jq \
    ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/* && rm -rf /tmp/*

WORKDIR /app

COPY --from=builder /app/agents/.release/ agents/
COPY --from=builder /app/server/bin/api /app/server/bin/api
COPY --from=builder /usr/local/lib /usr/local/lib
COPY --from=builder /usr/lib/python3 /usr/lib/python3

EXPOSE 8080

ENTRYPOINT ["/app/server/bin/api"]

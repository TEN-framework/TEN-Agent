FROM ghcr.io/ten-framework/ten_agent_build:0.2.4 AS builder

ARG SESSION_CONTROL_CONF=session_control.conf

WORKDIR /app

COPY . .
COPY agents/${SESSION_CONTROL_CONF} agents/session_control.conf

RUN task clean && task use && \
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
    jq vim \
    ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/* && rm -rf /tmp/*

WORKDIR /app

COPY --from=builder /app/agents/.release/ agents/
COPY --from=builder /app/server/bin/api /app/server/bin/api
COPY --from=builder /usr/local/lib /usr/local/lib
COPY --from=builder /usr/lib/python3 /usr/lib/python3

EXPOSE 8080

ENTRYPOINT ["/app/server/bin/api"]

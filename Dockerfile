FROM ghcr.io/ten-framework/ten_agent_build:0.5.0 AS builder

ARG SESSION_CONTROL_CONF=session_control.conf
# Add a new argument for USE_AGENT (defaulting to 'agents/examples/default')
ARG USE_AGENT=agents/examples/default

WORKDIR /app

COPY . .
COPY agents/${SESSION_CONTROL_CONF} agents/session_control.conf

RUN task clean && task use AGENT=${USE_AGENT} && \
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
    gcc \
    && apt-get clean && rm -rf /var/lib/apt/lists/* && rm -rf /tmp/*

WORKDIR /app

COPY --from=builder /app/agents/ agents/
COPY --from=builder /app/server/bin/api /app/server/bin/api
COPY --from=builder /usr/local/lib /usr/local/lib
COPY --from=builder /usr/lib/python3 /usr/lib/python3
COPY --from=builder /usr/local/bin/ /usr/local/bin/
COPY --from=builder /usr/local/ten_gn/ /usr/local/ten_gn/
COPY --from=builder /usr/local/go/ /usr/local/go/

ENV PATH=/usr/local/go/bin:/usr/local/ten_gn:$PATH

ENV CGO_ENABLED=1

EXPOSE 8080

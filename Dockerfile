FROM ghcr.io/ten-framework/astra_agents_build:0.4.0 AS builder

ARG SESSION_CONTROL_CONF=session_control.conf

WORKDIR /app

COPY . .
COPY agents/${SESSION_CONTROL_CONF} agents/session_control.conf
COPY agents/scripts/requirements.txt agents/scripts/requirements.txt

RUN make clean && make build && \
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
    build-essential \
    libboost-all-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/* && rm -rf /tmp/*

# Add these lines to copy the necessary header files
COPY agents/ten_packages/system/azure_speech_sdk/include /usr/local/include/azure_speech_sdk
COPY agents/ten_packages/system/ten_runtime/include /usr/local/include/ten_runtime

WORKDIR /app

COPY --from=builder /app/agents/.release/ agents/
COPY --from=builder /app/server/bin/api /app/server/bin/api
COPY --from=builder /usr/local/lib /usr/local/lib
COPY --from=builder /usr/lib/python3 /usr/lib/python3

# Add these lines to set the include paths
ENV CPLUS_INCLUDE_PATH=/usr/local/include/azure_speech_sdk:/usr/local/include/ten_runtime:$CPLUS_INCLUDE_PATH
ENV C_INCLUDE_PATH=/usr/local/include/azure_speech_sdk:/usr/local/include/ten_runtime:$C_INCLUDE_PATH

EXPOSE 8080

ENTRYPOINT ["/app/server/bin/api"]

FROM ghcr.io/ten-framework/ten_agent_build:0.4.17 AS builder

ARG SESSION_CONTROL_CONF=session_control.conf
# Add a new argument for USE_AGENT (defaulting to 'agents/examples/default')
ARG USE_AGENT=agents/examples/default

WORKDIR /app

COPY . .
COPY agents/${SESSION_CONTROL_CONF} agents/session_control.conf

RUN task clean && task use AGENT=${USE_AGENT} && task install-tools && task lint && \
    cd agents && ./scripts/package.sh

RUN cd playground && npm i

EXPOSE 8080

ENTRYPOINT ["task", "run"]

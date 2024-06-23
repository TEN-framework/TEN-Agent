FROM agoraio/astra_agents_build:0.1.0 AS builder

ARG SESSION_CONTROL_CONF=session_control.conf

WORKDIR /app

COPY . .
COPY agents/manifest.json.example agents/manifest.json
COPY agents/${SESSION_CONTROL_CONF} agents/session_control.conf

RUN make build && \
    cd agents && ./scripts/package.sh

FROM agoraio/astra_agents_run:0.1.0

ARG AGORA_APP_ID
ARG AGORA_APP_CERTIFICATE
ARG MANIFEST_JSON_FILE=./agents/manifest.json
ARG AZURE_STT_KEY
ARG AZURE_STT_REGION
ARG OPENAI_API_KEY
ARG AZURE_TTS_KEY
ARG AZURE_TTS_REGION

ENV AGORA_APP_ID=${AGORA_APP_ID}
ENV AGORA_APP_CERTIFICATE=${AGORA_APP_CERTIFICATE}
ENV MANIFEST_JSON_FILE=${MANIFEST_JSON_FILE}
ENV AZURE_STT_KEY=${AZURE_STT_KEY}
ENV AZURE_STT_REGION=${AZURE_STT_REGION}
ENV OPENAI_API_KEY=${OPENAI_API_KEY}
ENV AZURE_TTS_KEY=${AZURE_TTS_KEY}
ENV AZURE_TTS_REGION=${AZURE_TTS_REGION}

WORKDIR /app

COPY --from=builder /app/agents/.release/ agents/
COPY --from=builder /app/server/bin/api /app/server/bin/api

EXPOSE 8080

ENTRYPOINT ["/app/server/bin/api"]

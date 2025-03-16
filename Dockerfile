FROM ghcr.io/ten-framework/ten_agent_build:0.4.17 AS builder

ARG SESSION_CONTROL_CONF=session_control.conf
# Add a new argument for USE_AGENT (defaulting to 'agents/examples/default')
ARG USE_AGENT=agents/examples/default

WORKDIR /app

COPY . .
COPY agents/${SESSION_CONTROL_CONF} agents/session_control.conf

RUN task clean && task use AGENT=${USE_AGENT} && task install-tools && task lint && \
    cd agents && ./scripts/package.sh

# Use bash for the shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Create a script file sourced by both interactive and non-interactive bash shells
ENV BASH_ENV /root/.bash_env
RUN touch "${BASH_ENV}"
RUN echo '. "${BASH_ENV}"' >> ~/.bashrc

# Download and install nvm
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.2/install.sh | PROFILE="${BASH_ENV}" bash
RUN echo node > .nvmrc
RUN nvm install

RUN task build-playground

EXPOSE 8080

ENTRYPOINT ["task", "run"]

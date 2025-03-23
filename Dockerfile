FROM ghcr.io/ten-framework/ten_agent_build:0.5.0-2-g7d064cd-vllm-cpu

ARG SESSION_CONTROL_CONF=session_control.conf
# Add a new argument for USE_AGENT (defaulting to 'agents/examples/default')
ARG USE_AGENT=agents/examples/default

WORKDIR /app

COPY . .
COPY agents/${SESSION_CONTROL_CONF} agents/session_control.conf

RUN task clean && task use AGENT=${USE_AGENT} && task install-tools && task lint && \
    cd agents && ./scripts/package.sh


# install node and npm for demo
ENV NVM_DIR /usr/local/nvm
RUN mkdir -p $NVM_DIR
# Create a script file sourced by both interactive and non-interactive bash shells
ENV BASH_ENV /usr/local/nvm/.nvm_bash_env
RUN touch "${BASH_ENV}"
RUN echo '. "${BASH_ENV}"' >> ~/.bashrc
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | PROFILE="${BASH_ENV}" bash
RUN . $NVM_DIR/nvm.sh && nvm install node


RUN . $NVM_DIR/nvm.sh && task build-playground

EXPOSE 8080

ENTRYPOINT ["task", "run"]

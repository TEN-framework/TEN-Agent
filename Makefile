PROJECT_NAME := astra
PROJECT_VERSION ?= "0.1."$(shell date -u +'%Y%m%d%H')
REGISTRY ?= agoraio/

.PHONY: build build-agents build-playground build-server clean clean-agents docker-build docker-build-playground docker-build-server run-gd-server run-server run-dev build-and-run run-services run-all

build: build-agents build-server

build-agents:
	@echo ">> build agents"
	cd agents && ./scripts/install_deps_and_build.sh linux x64 && mv bin/main bin/worker
	@echo ">> done"

# Add this new target for debugging
debug-build-agents:
	@echo ">> debug build agents"
	cd agents && \
	VERBOSE=1 ./scripts/install_deps_and_build.sh $(OS) $(CPU) && \
	mv bin/main bin/worker
	@echo ">> done"

build-playground:
	@echo ">> build playground"
	cd playground && npm i && npm run build
	@echo ">> done"

build-server:
	@echo ">> build server"
	cd server && go mod tidy && go mod download && go build -o bin/api main.go
	@echo ">> done"

clean: clean-agents

clean-agents:
	@echo ">> clean agents"
	rm -rf agents/bin/worker agents/out agents/interface agents/include agents/lib agents/lib64 agents/ten_packages/system agents/ten_packages/extension_group agents/.release
	@echo ">> done"

docker-build: docker-build-playground docker-build-server

docker-build-playground:
	@echo ">> docker build playground"
	cd playground && docker build -t $(REGISTRY)$(PROJECT_NAME)_playground:$(PROJECT_VERSION) --platform linux/amd64 -f Dockerfile .
	@echo ">> done"

docker-build-server:
	@echo ">> docker build server"
	docker build -t $(REGISTRY)$(PROJECT_NAME)_agents_server:$(PROJECT_VERSION) --platform linux/amd64 -f Dockerfile .
	@echo ">> done"

run-gd-server:
	@echo ">> run graph designer server"
	cd agents && tman dev-server
	@echo ">> done"

run-server:
	@echo ">> run server"
	server/bin/api
	@echo ">> done"

run-dev: build run-server

# Update the run-services target to use debug-build-agents
run-services:
	@echo ">> Running services: $(SERVICES)"
	$(if $(LOCAL),\
		ASTRA_AGENTS_IMAGE=astra_agents_dev \
		ASTRA_PLAYGROUND_IMAGE=astra_playground \
	) \
	$(if $(BUILD),docker compose build astra_agents_dev astra_playground &&) \
	docker compose up $(SERVICES)

run-all:
	@$(MAKE) run-services SERVICES="astra_agents_dev astra_playground ten_graph_designer" BUILD=$(BUILD) LOCAL=$(LOCAL)

# Catch-all rule for more flexible service specification
%:
	@:

# Usage examples:
# make run-services SERVICES="astra_agents_dev astra_playground" BUILD=true
# make run-all BUILD=true
# make run-services SERVICES="astra_agents_dev"
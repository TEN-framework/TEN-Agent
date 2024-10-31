PROJECT_NAME := ten_agent
PROJECT_VERSION ?= "0.1."$(shell date -u +'%Y%m%d%H')
REGISTRY ?= agoraio/

.PHONY: build build-agents build-playground build-server clean clean-agents docker-build-playground docker-build-server run-gd-server run-server

build: build-agents build-server

build-agents:
	@echo ">> build agents"
	cd agents && ./scripts/install_deps_and_build.sh linux x64 && mv bin/main bin/worker
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
	rm -rf agents/bin/worker agents/out agents/interface agents/include agents/lib agents/lib64 agents/ten_packages/system/ten_runtime* agents/ten_packages/system/agora_rtc_sdk agents/ten_packages/system/azure_speech_sdk agents/ten_packages/system/nlohmann_json agents/.release
	@echo ">> done"

docker-build-playground:
	@echo ">> docker build playground"
	cd playground && docker build -t $(REGISTRY)$(PROJECT_NAME)_playground:$(PROJECT_VERSION) --platform linux/amd64 -f Dockerfile .
	@echo ">> done"

docker-build-server:
	@echo ">> docker build server"
	docker build -t $(REGISTRY)$(PROJECT_NAME)_server:$(PROJECT_VERSION) --platform linux/amd64 -f Dockerfile .
	@echo ">> done"

run-gd-server:
	@echo ">> run graph designer server"
	cd agents && tman dev-server
	@echo ">> done"

run-server:
	@echo ">> run server"
	server/bin/api
	@echo ">> done"

PROJECT_NAME := astra
PROJECT_VERSION ?= "0.1."$(shell date -u +'%Y%m%d%H')
REGISTRY ?= agoraio/

.PHONY: build build-agents build-server docker-build-server run-server

build: build-agents build-server

build-agents:
	@echo ">> build agents"
	cd agents && ./scripts/install_deps_and_build.sh linux x64 && mv ./bin/main ./bin/worker
	@echo ">> done"

build-server:
	@echo ">> build server"
	cd server && go mod tidy && go mod download && go build -o bin/api main.go
	@echo ">> done"

clean: clean-agents

clean-agents:
	@echo ">> clean agents"
	rm -rf agents/manifest.json agents/bin agents/out agents/interface agents/include agents/lib agents/lib64 agents/addon/system agents/addon/extension_group agents/.release
	@echo ">> done"

docker-build-server:
	@echo ">> docker build server"
	docker build -t $(REGISTRY)$(PROJECT_NAME):$(PROJECT_VERSION) --platform linux/amd64 -f Dockerfile .
	@echo ">> done"

run-server:
	@echo ">> run server"
	server/bin/api
	@echo ">> done"

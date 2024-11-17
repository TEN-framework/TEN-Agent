PROJECT_NAME := ten_agent
PROJECT_VERSION ?= "0.1."$(shell date -u +'%Y%m%d%H')
REGISTRY ?= agoraio/

.PHONY: build build-agents build-playground build-server clean clean-agents docker-build-playground docker-build-server run-gd-server run-server

build: 
	task build

build-playground:
	@echo ">> build playground"
	cd playground && npm i && npm run build
	@echo ">> done"

clean: 
	task clean

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
	task server:run

package main

import (
	"fmt"
	"log/slog"
	"os"
	"strconv"

	"github.com/joho/godotenv"
	"github.com/tidwall/gjson"
	"github.com/tidwall/sjson"

	"app/internal"
)

func main() {
	// Load .env
	err := godotenv.Load()
	if err != nil {
		slog.Warn("load .env file failed", "err", err)
	}

	// Check environment
	agoraAppId := os.Getenv("AGORA_APP_ID")
	if len(agoraAppId) != 32 {
		slog.Error("environment AGORA_APP_ID invalid")
		os.Exit(1)
	}

	workersMax, err := strconv.Atoi(os.Getenv("WORKERS_MAX"))
	if err != nil || workersMax <= 0 {
		slog.Error("environment WORKERS_MAX invalid")
		os.Exit(1)
	}

	workerQuitTimeoutSeconds, err := strconv.Atoi(os.Getenv("WORKER_QUIT_TIMEOUT_SECONDES"))
	if err != nil || workerQuitTimeoutSeconds <= 0 {
		slog.Error("environment WORKER_QUIT_TIMEOUT_SECONDES invalid")
		os.Exit(1)
	}

	// Process property.json
	if err = processProperty(internal.PropertyJsonFile); err != nil {
		slog.Error("process property.json failed", "err", err)
		os.Exit(1)
	}

	// Start server
	httpServerConfig := &internal.HttpServerConfig{
		AppId:                    agoraAppId,
		AppCertificate:           os.Getenv("AGORA_APP_CERTIFICATE"),
		LogPath:                  os.Getenv("LOG_PATH"),
		Port:                     os.Getenv("PLAYGROUND_SERVER_PORT"),
		WorkersMax:               workersMax,
		WorkerQuitTimeoutSeconds: workerQuitTimeoutSeconds,
	}
	httpServer := internal.NewHttpServer(httpServerConfig)
	httpServer.Start()
}

func processProperty(propertyJsonFile string) (err error) {
	content, err := os.ReadFile(propertyJsonFile)
	if err != nil {
		slog.Error("read property.json failed", "err", err, "propertyJsonFile", propertyJsonFile)
		return
	}

	propertyJson := string(content)
	for i := range gjson.Get(propertyJson, "rte.predefined_graphs").Array() {
		graph := fmt.Sprintf("rte.predefined_graphs.%d", i)
		// Shut down all auto-starting Graphs
		propertyJson, _ = sjson.Set(propertyJson, fmt.Sprintf(`%s.auto_start`, graph), false)

		// Set environment variable values to property.json
		for envKey, envProps := range internal.EnvPropMap {
			if envVal := os.Getenv(envKey); envVal != "" {
				for _, envProp := range envProps {
					propertyJson, _ = sjson.Set(propertyJson, fmt.Sprintf(`%s.nodes.#(name=="%s").property.%s`, graph, envProp.ExtensionName, envProp.Property), envVal)
				}
			}
		}
	}

	err = os.WriteFile(propertyJsonFile, []byte(propertyJson), 0644)
	return
}

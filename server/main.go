package main

import (
	"flag"
	"log/slog"
	"os"
	"strconv"

	"github.com/tidwall/sjson"

	"app/internal"
)

func main() {
	httpServerConfig := &internal.HttpServerConfig{}

	workersMax, err := strconv.Atoi(os.Getenv("WORKERS_MAX"))
	if err != nil || workersMax <= 0 {
		workersMax = 2
	}

	workerQuitTimeoutSeconds, err := strconv.Atoi(os.Getenv("WORKER_QUIT_TIMEOUT_SECONDES"))
	if err != nil || workerQuitTimeoutSeconds <= 0 {
		workerQuitTimeoutSeconds = 60
	}

	flag.StringVar(&httpServerConfig.AppId, "appId", os.Getenv("AGORA_APP_ID"), "agora appid")
	flag.StringVar(&httpServerConfig.AppCertificate, "appCertificate", os.Getenv("AGORA_APP_CERTIFICATE"), "agora certificate")
	flag.StringVar(&httpServerConfig.ManifestJsonFile, "manifestJsonFile", os.Getenv("MANIFEST_JSON_FILE"), "manifest json file")
	flag.IntVar(&httpServerConfig.WorkersMax, "workersMax", workersMax, "workers max")
	flag.IntVar(&httpServerConfig.WorkerQuitTimeoutSeconds, "workerQuitTimeoutSeconds", workerQuitTimeoutSeconds, "worker quit timeout seconds")
	flag.StringVar(&httpServerConfig.Port, "port", ":8080", "http server port")
	flag.Parse()

	slog.Info("server config", "appId", httpServerConfig.AppId, "manifestJsonFile", httpServerConfig.ManifestJsonFile,
		"workersMax", httpServerConfig.WorkersMax, "workerQuitTimeoutSeconds", httpServerConfig.WorkerQuitTimeoutSeconds)

	processManifest(httpServerConfig.ManifestJsonFile)
	httpServer := internal.NewHttpServer(httpServerConfig)
	httpServer.Start()
}

func processManifest(manifestJsonFile string) {
	content, err := os.ReadFile(manifestJsonFile)
	if err != nil {
		slog.Error("read manifest.json failed", "err", err, "manifestJsonFile", manifestJsonFile)
		return
	}

	manifestJson := string(content)

	appId := os.Getenv("AGORA_APP_ID")
	slog.Info("processManifest", "AGORA_APP_ID", appId)
	if appId != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="agora_rtc").property.app_id`, appId)
	}

	azureSttKey := os.Getenv("AZURE_STT_KEY")
	slog.Info("processManifest", "AZURE_STT_KEY", azureSttKey)
	if azureSttKey != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="agora_rtc").property.agora_asr_vendor_key`, azureSttKey)
	}

	azureSttRegion := os.Getenv("AZURE_STT_REGION")
	slog.Info("processManifest", "AZURE_STT_REGION", azureSttRegion)
	if azureSttRegion != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="agora_rtc").property.agora_asr_vendor_region`, azureSttRegion)
	}

	openaiBaseUrl := os.Getenv("OPENAI_BASE_URL")
	slog.Info("processManifest", "OPENAI_BASE_URL", openaiBaseUrl)
	if openaiBaseUrl != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="openai_chatgpt").property.base_url`, openaiBaseUrl)
	}

	openaiApiKey := os.Getenv("OPENAI_API_KEY")
	slog.Info("processManifest", "OPENAI_API_KEY", openaiApiKey)
	if openaiApiKey != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="openai_chatgpt").property.api_key`, openaiApiKey)
	}

	openaiModel := os.Getenv("OPENAI_MODEL")
	slog.Info("processManifest", "OPENAI_MODEL", openaiModel)
	if openaiModel != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="openai_chatgpt").property.model`, openaiModel)
	}

	proxyUrl := os.Getenv("PROXY_URL")
	slog.Info("processManifest", "PROXY_URL", proxyUrl)
	if proxyUrl != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="openai_chatgpt").property.proxy_url`, proxyUrl)
	}

	azureTtsKey := os.Getenv("AZURE_TTS_KEY")
	slog.Info("processManifest", "AZURE_TTS_KEY", azureTtsKey)
	if azureTtsKey != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="azure_tts").property.azure_subscription_key`, azureTtsKey)
	}

	azure_tts_region := os.Getenv("AZURE_TTS_REGION")
	slog.Info("processManifest", "AZURE_TTS_REGION", azure_tts_region)
	if azure_tts_region != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="azure_tts").property.azure_subscription_region`, azure_tts_region)
	}

	os.WriteFile(manifestJsonFile, []byte(manifestJson), 0644)
	return
}
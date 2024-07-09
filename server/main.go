package main

import (
	"context"
	"errors"
	"flag"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/tidwall/sjson"

	"app/internal"
	"app/internal/service"
)

const (
	ManifestJsonFile           = "./agents/manifest.json"
	ManifestJsonFileElevenlabs = "./agents/manifest.elevenlabs.json"
)

func main() {
	httpServerConfig := internal.HttpServerConfig{}

	ttsVendorChinese := os.Getenv("TTS_VENDOR_CHINESE")
	if len(ttsVendorChinese) == 0 {
		ttsVendorChinese = service.TTSVendorAzure //TODO vendor provider
	}

	ttsVendorEnglish := os.Getenv("TTS_VENDOR_ENGLISH")
	if len(ttsVendorEnglish) == 0 {
		ttsVendorEnglish = service.TTSVendorAzure //TODO vendor provider
	}

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
	flag.StringVar(&httpServerConfig.Address, "port", ":8080", "http server listen address")
	flag.StringVar(&httpServerConfig.TTSVendorChinese, "ttsVendorChinese", ttsVendorChinese, "tts vendor for chinese")
	flag.StringVar(&httpServerConfig.TTSVendorEnglish, "ttsVendorEnglish", ttsVendorEnglish, "tts vendor for english")
	flag.IntVar(&httpServerConfig.WorkersMax, "workersMax", workersMax, "workers max")
	flag.IntVar(&httpServerConfig.WorkerQuitTimeoutSeconds, "workerQuitTimeoutSeconds", workerQuitTimeoutSeconds, "worker quit timeout seconds")
	flag.Parse()

	slog.Info("server config", "ttsVendorChinese", httpServerConfig.TTSVendorChinese, "ttsVendorEnglish", httpServerConfig.TTSVendorEnglish,
		"workersMax", httpServerConfig.WorkersMax, "workerQuitTimeoutSeconds", httpServerConfig.WorkerQuitTimeoutSeconds)

	httpServerConfig.ManifestJson, err = loadManifest(ManifestJsonFile)
	if err != nil {
		panic(err)
	}

	httpServerConfig.ManifestJsonElevenlabs, err = loadManifest(ManifestJsonFileElevenlabs)
	if err != nil {
		panic(err)
	}

	httpServer := internal.NewHttpServer(httpServerConfig)

	errCh := make(chan error, 1)
	go func() {
		defer close(errCh)
		err := httpServer.Run()
		if errors.Is(err, http.ErrServerClosed) {
			errCh <- nil
		}
		errCh <- err
	}()

	sigCh := make(chan os.Signal, 1)
	defer close(sigCh)
	signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGQUIT, syscall.SIGINT)
	<-sigCh

	ctx := context.Background()
	ctx, cancel := context.WithTimeout(ctx, time.Second*3)
	err = httpServer.Shutdown(ctx)
	if err != nil {
		slog.Error("httpServer Shutdown error", "err", err)
	}
	defer cancel() // fix warning lostcancel

	err = <-errCh
	if err != nil {
		panic(err)
	}
}

func loadManifest(manifestJsonFile string) (string, error) {
	content, err := os.ReadFile(manifestJsonFile)
	if err != nil {
		slog.Error("read manifest.json failed", "err", err, "manifestJsonFile", manifestJsonFile)
		return "", err
	}

	manifestJson := string(content)

	appId := os.Getenv("AGORA_APP_ID")
	if appId != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="agora_rtc").property.app_id`, appId)
	}

	azureSttKey := os.Getenv("AZURE_STT_KEY")
	if azureSttKey != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="agora_rtc").property.agora_asr_vendor_key`, azureSttKey)
	}

	azureSttRegion := os.Getenv("AZURE_STT_REGION")
	if azureSttRegion != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="agora_rtc").property.agora_asr_vendor_region`, azureSttRegion)
	}

	openaiBaseUrl := os.Getenv("OPENAI_BASE_URL")
	if openaiBaseUrl != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="openai_chatgpt").property.base_url`, openaiBaseUrl)
	}

	openaiApiKey := os.Getenv("OPENAI_API_KEY")
	if openaiApiKey != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="openai_chatgpt").property.api_key`, openaiApiKey)
	}

	openaiModel := os.Getenv("OPENAI_MODEL")
	if openaiModel != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="openai_chatgpt").property.model`, openaiModel)
	}

	proxyUrl := os.Getenv("PROXY_URL")
	if proxyUrl != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="openai_chatgpt").property.proxy_url`, proxyUrl)
	}

	azureTtsKey := os.Getenv("AZURE_TTS_KEY")
	if azureTtsKey != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="azure_tts").property.azure_subscription_key`, azureTtsKey)
	}

	azureTtsRegion := os.Getenv("AZURE_TTS_REGION")
	if azureTtsRegion != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="azure_tts").property.azure_subscription_region`, azureTtsRegion)
	}

	elevenlabsTtsKey := os.Getenv("ELEVENLABS_TTS_KEY")
	if elevenlabsTtsKey != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="elevenlabs_tts").property.api_key`, elevenlabsTtsKey)
	}

	return manifestJson, nil
}

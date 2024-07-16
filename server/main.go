package main

import (
	"flag"
	"log/slog"
	"os"
	"strconv"

	"app/internal"
)

func main() {
	httpServerConfig := &internal.HttpServerConfig{}

	ttsVendorChinese := os.Getenv("TTS_VENDOR_CHINESE")
	if len(ttsVendorChinese) == 0 {
		ttsVendorChinese = internal.TTSVendorAzure
	}

	ttsVendorEnglish := os.Getenv("TTS_VENDOR_ENGLISH")
	if len(ttsVendorEnglish) == 0 {
		ttsVendorEnglish = internal.TTSVendorAzure
	}

	workersMax, err := strconv.Atoi(os.Getenv("WORKERS_MAX"))
	if err != nil || workersMax <= 0 {
		workersMax = 2
	}

	workerQuitTimeoutSeconds, err := strconv.Atoi(os.Getenv("WORKER_QUIT_TIMEOUT_SECONDES"))
	if err != nil || workerQuitTimeoutSeconds <= 0 {
		workerQuitTimeoutSeconds = 60
	}

	var manifestJsonDir string

	flag.StringVar(&httpServerConfig.AppId, "appId", os.Getenv("AGORA_APP_ID"), "agora appid")
	flag.StringVar(&httpServerConfig.AppCertificate, "appCertificate", os.Getenv("AGORA_APP_CERTIFICATE"), "agora certificate")
	flag.StringVar(&httpServerConfig.Port, "port", ":8080", "http server port")
	flag.StringVar(&manifestJsonDir, "manifestJsonDir", "./agents/", "manifest json dir")
	flag.StringVar(&httpServerConfig.TTSVendorChinese, "ttsVendorChinese", ttsVendorChinese, "tts vendor for chinese")
	flag.StringVar(&httpServerConfig.TTSVendorEnglish, "ttsVendorEnglish", ttsVendorEnglish, "tts vendor for english")
	flag.IntVar(&httpServerConfig.WorkersMax, "workersMax", workersMax, "workers max")
	flag.IntVar(&httpServerConfig.WorkerQuitTimeoutSeconds, "workerQuitTimeoutSeconds", workerQuitTimeoutSeconds, "worker quit timeout seconds")
	flag.Parse()

	slog.Info("server config", "ttsVendorChinese", httpServerConfig.TTSVendorChinese, "ttsVendorEnglish", httpServerConfig.TTSVendorEnglish,
		"workersMax", httpServerConfig.WorkersMax, "workerQuitTimeoutSeconds", httpServerConfig.WorkerQuitTimeoutSeconds)

	manifestProvider := internal.NewManifestProvider()
	err = manifestProvider.LoadManifest(manifestJsonDir)
	if err != nil {
		panic(err)
	}

	httpServer := internal.NewHttpServer(httpServerConfig, manifestProvider)
	httpServer.Start()
}

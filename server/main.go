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

	"app/internal"
	"app/internal/provider"
	"app/internal/service"
	"app/third_party/azure"
)

func main() {
	ttsVendorChinese := os.Getenv("TTS_VENDOR_CHINESE")
	if len(ttsVendorChinese) == 0 {
		ttsVendorChinese = azure.NAME
	}

	ttsVendorEnglish := os.Getenv("TTS_VENDOR_ENGLISH")
	if len(ttsVendorEnglish) == 0 {
		ttsVendorEnglish = azure.NAME
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
	flag.StringVar(&manifestJsonDir, "manifestJsonDir", "./agents/", "manifest json dir")

	httpServerConfig := internal.HttpServerConfig{}
	flag.StringVar(&httpServerConfig.Address, "port", ":8080", "http server listen address")

	mainServiceConfig := service.MainServiceConfig{}
	flag.StringVar(&mainServiceConfig.AppId, "appId", os.Getenv("AGORA_APP_ID"), "agora appid")
	flag.StringVar(&mainServiceConfig.AppCertificate, "appCertificate", os.Getenv("AGORA_APP_CERTIFICATE"), "agora certificate")
	flag.StringVar(&mainServiceConfig.TTSVendorChinese, "ttsVendorChinese", ttsVendorChinese, "tts vendor for chinese")
	flag.StringVar(&mainServiceConfig.TTSVendorEnglish, "ttsVendorEnglish", ttsVendorEnglish, "tts vendor for english")
	flag.IntVar(&mainServiceConfig.WorkersMax, "workersMax", workersMax, "workers max")
	flag.IntVar(&mainServiceConfig.WorkerQuitTimeoutSeconds, "workerQuitTimeoutSeconds", workerQuitTimeoutSeconds, "worker quit timeout seconds")

	flag.Parse()

	slog.Info("server config",
		"ttsVendorChinese", mainServiceConfig.TTSVendorChinese,
		"ttsVendorEnglish", mainServiceConfig.TTSVendorEnglish,
		"workersMax", mainServiceConfig.WorkersMax,
		"workerQuitTimeoutSeconds", mainServiceConfig.WorkerQuitTimeoutSeconds)

	manifestProvider := provider.NewManifestProvider()
	err = manifestProvider.LoadManifest(manifestJsonDir)
	if err != nil {
		panic(err)
	}

	mainSvc := service.NewMainService(service.MainServiceDepends{
		Config:           mainServiceConfig,
		ManifestProvider: manifestProvider,
	})

	httpServer := internal.NewHttpServer(internal.HttpServerDepends{
		Config:  httpServerConfig,
		MainSvc: mainSvc,
	})

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

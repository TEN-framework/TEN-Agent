/**
 *
 * Agora Real Time Engagement
 * Created by lixinhui in 2024.
 * Copyright (c) 2024 Agora IO. All rights reserved.
 *
 */
// Note that this is just an example extension written in the GO programming
// language, so the package name does not equal to the containing directory
// name. However, it is not common in Go.
package internal

import (
	"app/internal/router"
	"app/internal/service"
	"log/slog"

	"github.com/gin-gonic/gin"
)

type HttpServer struct {
	config *HttpServerConfig
}

type HttpServerConfig struct {
	AppId                    string
	AppCertificate           string
	ManifestJsonFile         string
	Port                     string
	TTSVendorChinese         string
	TTSVendorEnglish         string
	WorkersMax               int
	WorkerQuitTimeoutSeconds int
}

var (
	logTag = slog.String("service", "HTTP_SERVER")
)

func NewHttpServer(httpServerConfig *HttpServerConfig) *HttpServer {
	return &HttpServer{
		config: httpServerConfig,
	}
}

func (s *HttpServer) Start() {
	r := gin.Default()
	r.Use(corsMiddleware())

	mainSvcConf := service.MainServiceConfig{
		AppId:                    s.config.AppId,
		AppCertificate:           s.config.AppCertificate,
		ManifestJsonFile:         s.config.ManifestJsonFile,
		TTSVendorChinese:         s.config.TTSVendorChinese,
		TTSVendorEnglish:         s.config.TTSVendorEnglish,
		WorkersMax:               s.config.WorkersMax,
		WorkerQuitTimeoutSeconds: s.config.WorkerQuitTimeoutSeconds,
	}
	mainSvc := service.NewMainService(mainSvcConf)
	router.Apply(r, mainSvc)

	slog.Info("server start", "port", s.config.Port, logTag)

	go mainSvc.CleanWorker()
	r.Run(s.config.Port)
}

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
	"context"
	"log/slog"
	"net/http"

	"github.com/gin-gonic/gin"
)

type HttpServer struct {
	config HttpServerConfig
	server *http.Server
}

type HttpServerConfig struct {
	Address string

	service.MainServiceConfig
}

var (
	logTag = slog.String("service", "HTTP_SERVER")
)

func NewHttpServer(httpServerConfig HttpServerConfig) *HttpServer {
	return &HttpServer{
		config: httpServerConfig,
	}
}

func (s *HttpServer) Run() error {
	r := gin.Default()
	r.Use(corsMiddleware())

	mainSvc := service.NewMainService(s.config.MainServiceConfig)
	go mainSvc.CleanWorker()
	router.Apply(r, mainSvc)

	slog.Info("server start", "address", s.config.Address, logTag)

	s.server = &http.Server{
		Addr:    s.config.Address,
		Handler: r,
	}
	return s.server.ListenAndServe()
}

func (s *HttpServer) Shutdown(ctx context.Context) error {
	return s.server.Shutdown(ctx)
}

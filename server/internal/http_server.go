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
	deps   HttpServerDepends
	server *http.Server
}

type HttpServerDepends struct {
	Config  HttpServerConfig
	MainSvc *service.MainService
}

type HttpServerConfig struct {
	Address string
}

var (
	logTag = slog.String("service", "HTTP_SERVER")
)

func NewHttpServer(deps HttpServerDepends) *HttpServer {
	r := gin.Default()
	r.Use(corsMiddleware())

	router.Apply(r, deps.MainSvc)

	return &HttpServer{
		deps: deps,
		server: &http.Server{
			Addr:    deps.Config.Address,
			Handler: r,
		},
	}
}

func (s *HttpServer) Run() error {
	slog.Info("server start", "address", s.server.Addr, logTag)
	go s.deps.MainSvc.CleanWorker()
	return s.server.ListenAndServe()
}

func (s *HttpServer) Shutdown(ctx context.Context) error {
	return s.server.Shutdown(ctx)
}

package router

import (
	"app/internal/service"

	"github.com/gin-gonic/gin"
)

func Apply(r gin.IRouter, mainSvc *service.MainService) {
	r.GET("/", mainSvc.HandlerHealth)
	r.GET("/health", mainSvc.HandlerHealth)
	r.POST("/ping", mainSvc.HandlerPing)
	r.POST("/start", mainSvc.HandlerStart)
	r.POST("/stop", mainSvc.HandlerStop)
	r.POST("/token/generate", mainSvc.HandlerGenerateToken)
}

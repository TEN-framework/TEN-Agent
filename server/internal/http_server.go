/**
 *
 * Agora Real Time Engagement
 * Created by Xinhui Li in 2024.
 * Copyright (c) 2024 Agora IO. All rights reserved.
 *
 */
package internal

import (
	"fmt"
	"log/slog"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	rtctokenbuilder "github.com/AgoraIO/Tools/DynamicKey/AgoraDynamicKey/go/src/rtctokenbuilder2"
	"github.com/gin-gonic/gin"
	"github.com/gin-gonic/gin/binding"
	"github.com/gogf/gf/crypto/gmd5"
	"github.com/tidwall/sjson"
)

type HttpServer struct {
	config *HttpServerConfig
}

type HttpServerConfig struct {
	AppId                    string
	AppCertificate           string
	LogPath                  string
	PropertyJsonFile         string
	Port                     string
	TTSVendorChinese         string
	TTSVendorEnglish         string
	WorkersMax               int
	WorkerQuitTimeoutSeconds int
}

type PingReq struct {
	RequestId   string `json:"request_id,omitempty"`
	ChannelName string `json:"channel_name,omitempty"`
}

type StartReq struct {
	RequestId            string `json:"request_id,omitempty"`
	AgoraAsrLanguage     string `json:"agora_asr_language,omitempty"`
	ChannelName          string `json:"channel_name,omitempty"`
	GraphName            string `json:"graph_name,omitempty"`
	RemoteStreamId       uint32 `json:"remote_stream_id,omitempty"`
	Token                string `json:"token,omitempty"`
	VoiceType            string `json:"voice_type,omitempty"`
	WorkerHttpServerPort int32  `json:"worker_http_server_port,omitempty"`
}

type StopReq struct {
	RequestId   string `json:"request_id,omitempty"`
	ChannelName string `json:"channel_name,omitempty"`
}

type GenerateTokenReq struct {
	RequestId   string `json:"request_id,omitempty"`
	ChannelName string `json:"channel_name,omitempty"`
	Uid         uint32 `json:"uid,omitempty"`
}

type UploadReq struct {
	RequestId   string                `form:"request_id,omitempty" json:"request_id,omitempty"`
	ChannelName string                `form:"channel_name,omitempty" json:"channel_name,omitempty"`
	File        *multipart.FileHeader `form:"file" binding:"required"`
	Uid         uint32                `form:"uid,omitempty" json:"uid,omitempty"`
}

func NewHttpServer(httpServerConfig *HttpServerConfig) *HttpServer {
	return &HttpServer{
		config: httpServerConfig,
	}
}

func (s *HttpServer) handlerHealth(c *gin.Context) {
	slog.Debug("handlerHealth", logTag)
	s.output(c, codeOk, nil)
}

func (s *HttpServer) handlerPing(c *gin.Context) {
	var req PingReq

	if err := c.ShouldBindBodyWith(&req, binding.JSON); err != nil {
		slog.Error("handlerPing params invalid", "err", err, logTag)
		s.output(c, codeErrParamsInvalid, http.StatusBadRequest)
		return
	}

	slog.Info("handlerPing start", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)

	if strings.TrimSpace(req.ChannelName) == "" {
		slog.Error("handlerPing channel empty", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrChannelEmpty, http.StatusBadRequest)
		return
	}

	if !workers.Contains(req.ChannelName) {
		slog.Error("handlerPing channel not existed", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrChannelNotExisted, http.StatusBadRequest)
		return
	}

	// Update worker
	worker := workers.Get(req.ChannelName).(*Worker)
	worker.UpdateTs = time.Now().Unix()

	slog.Info("handlerPing end", "worker", worker, "requestId", req.RequestId, logTag)
	s.output(c, codeSuccess, nil)
}

func (s *HttpServer) handlerStart(c *gin.Context) {
	workersRunning := workers.Size()

	slog.Info("handlerStart start", "workersRunning", workersRunning, logTag)

	var req StartReq
	if err := c.ShouldBindBodyWith(&req, binding.JSON); err != nil {
		slog.Error("handlerStart params invalid", "err", err, "requestId", req.RequestId, logTag)
		s.output(c, codeErrParamsInvalid, http.StatusBadRequest)
		return
	}

	if strings.TrimSpace(req.ChannelName) == "" {
		slog.Error("handlerStart channel empty", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrChannelEmpty, http.StatusBadRequest)
		return
	}

	if workersRunning >= s.config.WorkersMax {
		slog.Error("handlerStart workers exceed", "workersRunning", workersRunning, "WorkersMax", s.config.WorkersMax, "requestId", req.RequestId, logTag)
		s.output(c, codeErrWorkersLimit, http.StatusTooManyRequests)
		return
	}

	if workers.Contains(req.ChannelName) {
		slog.Error("handlerStart channel existed", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrChannelExisted, http.StatusBadRequest)
		return
	}

	req.WorkerHttpServerPort = getHttpServerPort()
	propertyJsonFile, logFile, err := s.processProperty(&req)
	if err != nil {
		slog.Error("handlerStart process property", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrProcessPropertyFailed, http.StatusInternalServerError)
		return
	}

	worker := newWorker(req.ChannelName, logFile, propertyJsonFile)
	worker.HttpServerPort = req.WorkerHttpServerPort
	worker.QuitTimeoutSeconds = s.config.WorkerQuitTimeoutSeconds
	if err := worker.start(&req); err != nil {
		slog.Error("handlerStart start worker failed", "err", err, "requestId", req.RequestId, logTag)
		s.output(c, codeErrStartWorkerFailed, http.StatusInternalServerError)
		return
	}
	workers.SetIfNotExist(req.ChannelName, worker)

	slog.Info("handlerStart end", "workersRunning", workers.Size(), "worker", worker, "requestId", req.RequestId, logTag)
	s.output(c, codeSuccess, nil)
}

func (s *HttpServer) handlerStop(c *gin.Context) {
	var req StopReq

	if err := c.ShouldBindBodyWith(&req, binding.JSON); err != nil {
		slog.Error("handlerStop params invalid", "err", err, logTag)
		s.output(c, codeErrParamsInvalid, http.StatusBadRequest)
		return
	}

	slog.Info("handlerStop start", "req", req, logTag)

	if strings.TrimSpace(req.ChannelName) == "" {
		slog.Error("handlerStop channel empty", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrChannelEmpty, http.StatusBadRequest)
		return
	}

	if !workers.Contains(req.ChannelName) {
		slog.Error("handlerStop channel not existed", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrChannelNotExisted, http.StatusBadRequest)
		return
	}

	worker := workers.Get(req.ChannelName).(*Worker)
	if err := worker.stop(req.RequestId, req.ChannelName); err != nil {
		slog.Error("handlerStop kill app failed", "err", err, "worker", workers.Get(req.ChannelName), "requestId", req.RequestId, logTag)
		s.output(c, codeErrStopWorkerFailed, http.StatusInternalServerError)
		return
	}

	slog.Info("handlerStop end", "requestId", req.RequestId, logTag)
	s.output(c, codeSuccess, nil)
}

func (s *HttpServer) handlerGenerateToken(c *gin.Context) {
	var req GenerateTokenReq

	if err := c.ShouldBindBodyWith(&req, binding.JSON); err != nil {
		slog.Error("handlerGenerateToken params invalid", "err", err, logTag)
		s.output(c, codeErrParamsInvalid, http.StatusBadRequest)
		return
	}

	slog.Info("handlerGenerateToken start", "req", req, logTag)

	if strings.TrimSpace(req.ChannelName) == "" {
		slog.Error("handlerGenerateToken channel empty", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrChannelEmpty, http.StatusBadRequest)
		return
	}

	if s.config.AppCertificate == "" {
		s.output(c, codeSuccess, map[string]any{"appId": s.config.AppId, "token": s.config.AppId, "channel_name": req.ChannelName, "uid": req.Uid})
		return
	}

	token, err := rtctokenbuilder.BuildTokenWithUid(s.config.AppId, s.config.AppCertificate, req.ChannelName, req.Uid, rtctokenbuilder.RolePublisher, tokenExpirationInSeconds, tokenExpirationInSeconds)
	if err != nil {
		slog.Error("handlerGenerateToken generate token failed", "err", err, "requestId", req.RequestId, logTag)
		s.output(c, codeErrGenerateTokenFailed, http.StatusBadRequest)
		return
	}

	slog.Info("handlerGenerateToken end", "requestId", req.RequestId, logTag)
	s.output(c, codeSuccess, map[string]any{"appId": s.config.AppId, "token": token, "channel_name": req.ChannelName, "uid": req.Uid})
}

func (s *HttpServer) handlerUpload(c *gin.Context) {
	var req UploadReq

	if err := c.ShouldBind(&req); err != nil {
		slog.Error("handlerUpload params invalid", "err", err, "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrParamsInvalid, http.StatusBadRequest)
		return
	}

	if !workers.Contains(req.ChannelName) {
		slog.Error("handlerUpload channel not existed", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrChannelNotExisted, http.StatusBadRequest)
		return
	}

	slog.Info("handlerUpload start", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)

	file := req.File
	uploadFile := fmt.Sprintf("%s/file-%s-%d%s", s.config.LogPath, gmd5.MustEncryptString(req.ChannelName), time.Now().UnixNano(), filepath.Ext(file.Filename))
	if err := c.SaveUploadedFile(file, uploadFile); err != nil {
		slog.Error("handlerUpload save file failed", "err", err, "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrSaveFileFailed, http.StatusBadRequest)
		return
	}

	// update worker
	worker := workers.Get(req.ChannelName).(*Worker)
	err := worker.update(&WorkerUpdateReq{
		RequestId:   req.RequestId,
		ChannelName: req.ChannelName,
		Path:        uploadFile,
		Rte: &WorkerUpdateReqRte{
			Name: "file_download",
			Type: "cmd",
		},
	})
	if err != nil {
		slog.Error("handlerUpload update worker failed", "err", err, "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrUpdateWorkerFailed, http.StatusBadRequest)
		return
	}

	slog.Info("handlerUpload end", "channelName", req.ChannelName, "uploadFile", uploadFile, "requestId", req.RequestId, logTag)
	s.output(c, codeSuccess, map[string]any{"channel_name": req.ChannelName, "uid": req.Uid})
}

func (s *HttpServer) output(c *gin.Context, code *Code, data any, httpStatus ...int) {
	if len(httpStatus) == 0 {
		httpStatus = append(httpStatus, http.StatusOK)
	}

	c.JSON(httpStatus[0], gin.H{"code": code.code, "msg": code.msg, "data": data})
}

func (s *HttpServer) processProperty(req *StartReq) (propertyJsonFile string, logFile string, err error) {
	content, err := os.ReadFile(PropertyJsonFile)
	if err != nil {
		slog.Error("handlerStart read property.json failed", "err", err, "propertyJsonFile", propertyJsonFile, "requestId", req.RequestId, logTag)
		return
	}

	propertyJson := string(content)

	// Get graph name
	graphName := req.GraphName
	if graphName == "" {
		graphName = graphNameDefault
	}

	// Generate token
	req.Token = s.config.AppId
	if s.config.AppCertificate != "" {
		req.Token, err = rtctokenbuilder.BuildTokenWithUid(s.config.AppId, s.config.AppCertificate, req.ChannelName, 0, rtctokenbuilder.RoleSubscriber, tokenExpirationInSeconds, tokenExpirationInSeconds)
		if err != nil {
			slog.Error("handlerStart generate token failed", "err", err, "requestId", req.RequestId, logTag)
			return
		}
	}

	graph := fmt.Sprintf(`rte.predefined_graphs.#(name=="%s")`, graphName)
	// Automatically start on launch
	propertyJson, _ = sjson.Set(propertyJson, fmt.Sprintf(`%s.auto_start`, graph), true)

	// Set parameters from the request to property.json
	for key, props := range startPropMap {
		if val := getFieldValue(req, key); val != "" {
			for _, prop := range props {
				if key == "VoiceType" {
					val = voiceNameMap[req.AgoraAsrLanguage][prop.ExtensionName][req.VoiceType]
				}
				propertyJson, _ = sjson.Set(propertyJson, fmt.Sprintf(`%s.nodes.#(name=="%s").property.%s`, graph, prop.ExtensionName, prop.Property), val)
			}
		}
	}

	channelNameMd5 := gmd5.MustEncryptString(req.ChannelName)
	ts := time.Now().UnixNano()
	propertyJsonFile = fmt.Sprintf("%s/property-%s-%d.json", s.config.LogPath, channelNameMd5, ts)
	logFile = fmt.Sprintf("%s/app-%s-%d.log", s.config.LogPath, channelNameMd5, ts)
	os.WriteFile(propertyJsonFile, []byte(propertyJson), 0644)

	return
}

func (s *HttpServer) Start() {
	r := gin.Default()
	r.Use(corsMiddleware())

	r.GET("/", s.handlerHealth)
	r.GET("/health", s.handlerHealth)
	r.POST("/ping", s.handlerPing)
	r.POST("/start", s.handlerStart)
	r.POST("/stop", s.handlerStop)
	r.POST("/token/generate", s.handlerGenerateToken)
	r.POST("/upload", s.handlerUpload)

	slog.Info("server start", "port", s.config.Port, logTag)

	go cleanWorker()
	r.Run(fmt.Sprintf(":%s", s.config.Port))
}

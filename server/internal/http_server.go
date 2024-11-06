/**
 *
 * Agora Real Time Engagement
 * Created by XinHui Li in 2024.
 * Copyright (c) 2024 Agora IO. All rights reserved.
 *
 */
package internal

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"mime/multipart"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"

	rtctokenbuilder "github.com/AgoraIO/Tools/DynamicKey/AgoraDynamicKey/go/src/rtctokenbuilder2"
	"github.com/gin-gonic/gin"
	"github.com/gin-gonic/gin/binding"
	"github.com/gogf/gf/crypto/gmd5"
)

type HttpServer struct {
	config *HttpServerConfig
}

type HttpServerConfig struct {
	AppId                    string
	AppCertificate           string
	LogPath                  string
	Log2Stdout               bool
	PropertyJsonFile         string
	Port                     string
	WorkersMax               int
	WorkerQuitTimeoutSeconds int
}

type PingReq struct {
	RequestId   string `json:"request_id,omitempty"`
	ChannelName string `json:"channel_name,omitempty"`
}

type StartReq struct {
	RequestId            string                            `json:"request_id,omitempty"`
	ChannelName          string                            `json:"channel_name,omitempty"`
	GraphName            string                            `json:"graph_name,omitempty"`
	RemoteStreamId       uint32                            `json:"user_uid,omitempty"`
	BotStreamId          uint32                            `json:"bot_uid,omitempty"`
	Token                string                            `json:"token,omitempty"`
	WorkerHttpServerPort int32                             `json:"worker_http_server_port,omitempty"`
	Properties           map[string]map[string]interface{} `json:"properties,omitempty"`
	QuitTimeoutSeconds   int                               `json:"timeout,omitempty"`
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

type VectorDocumentUpdate struct {
	RequestId   string `json:"request_id,omitempty"`
	ChannelName string `json:"channel_name,omitempty"`
	Collection  string `json:"collection,omitempty"`
	FileName    string `json:"file_name,omitempty"`
}

type VectorDocumentUpload struct {
	RequestId   string                `form:"request_id,omitempty" json:"request_id,omitempty"`
	ChannelName string                `form:"channel_name,omitempty" json:"channel_name,omitempty"`
	File        *multipart.FileHeader `form:"file" binding:"required"`
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

func (s *HttpServer) handlerList(c *gin.Context) {
	slog.Info("handlerList start", logTag)
	// Create a slice of maps to hold the filtered data
	filtered := make([]map[string]interface{}, len(workers.Keys()))
	for _, channelName := range workers.Keys() {
		worker := workers.Get(channelName).(*Worker)
		workerJson := map[string]interface{}{
			"channelName": worker.ChannelName,
			"createTs":    worker.CreateTs,
		}
		filtered = append(filtered, workerJson)
	}
	slog.Info("handlerList end", logTag)
	s.output(c, codeSuccess, filtered)
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

	worker := newWorker(req.ChannelName, logFile, s.config.Log2Stdout, propertyJsonFile)
	worker.HttpServerPort = req.WorkerHttpServerPort

	if req.QuitTimeoutSeconds > 0 {
		worker.QuitTimeoutSeconds = req.QuitTimeoutSeconds
	} else {
		worker.QuitTimeoutSeconds = s.config.WorkerQuitTimeoutSeconds
	}

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

	token, err := rtctokenbuilder.BuildTokenWithRtm(s.config.AppId, s.config.AppCertificate, req.ChannelName, fmt.Sprintf("%d", req.Uid), rtctokenbuilder.RolePublisher, tokenExpirationInSeconds, tokenExpirationInSeconds)
	if err != nil {
		slog.Error("handlerGenerateToken generate token failed", "err", err, "requestId", req.RequestId, logTag)
		s.output(c, codeErrGenerateTokenFailed, http.StatusBadRequest)
		return
	}

	slog.Info("handlerGenerateToken end", "requestId", req.RequestId, logTag)
	s.output(c, codeSuccess, map[string]any{"appId": s.config.AppId, "token": token, "channel_name": req.ChannelName, "uid": req.Uid})
}

func (s *HttpServer) handlerVectorDocumentPresetList(c *gin.Context) {
	presetList := []map[string]any{}
	vectorDocumentPresetList := os.Getenv("VECTOR_DOCUMENT_PRESET_LIST")

	if vectorDocumentPresetList != "" {
		err := json.Unmarshal([]byte(vectorDocumentPresetList), &presetList)
		if err != nil {
			slog.Error("handlerVectorDocumentPresetList parse json failed", "err", err, logTag)
			s.output(c, codeErrParseJsonFailed, http.StatusBadRequest)
			return
		}
	}

	s.output(c, codeSuccess, presetList)
}

func (s *HttpServer) handlerVectorDocumentUpdate(c *gin.Context) {
	var req VectorDocumentUpdate

	if err := c.ShouldBind(&req); err != nil {
		slog.Error("handlerVectorDocumentUpdate params invalid", "err", err, "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrParamsInvalid, http.StatusBadRequest)
		return
	}

	if !workers.Contains(req.ChannelName) {
		slog.Error("handlerVectorDocumentUpdate channel not existed", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrChannelNotExisted, http.StatusBadRequest)
		return
	}

	slog.Info("handlerVectorDocumentUpdate start", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)

	// update worker
	worker := workers.Get(req.ChannelName).(*Worker)
	err := worker.update(&WorkerUpdateReq{
		RequestId:   req.RequestId,
		ChannelName: req.ChannelName,
		Collection:  req.Collection,
		FileName:    req.FileName,
		Ten: &WorkerUpdateReqTen{
			Name: "update_querying_collection",
			Type: "cmd",
		},
	})
	if err != nil {
		slog.Error("handlerVectorDocumentUpdate update worker failed", "err", err, "channelName", req.ChannelName, "Collection", req.Collection, "FileName", req.FileName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrUpdateWorkerFailed, http.StatusBadRequest)
		return
	}

	slog.Info("handlerVectorDocumentUpdate end", "channelName", req.ChannelName, "Collection", req.Collection, "FileName", req.FileName, "requestId", req.RequestId, logTag)
	s.output(c, codeSuccess, map[string]any{"channel_name": req.ChannelName})
}

func (s *HttpServer) handlerVectorDocumentUpload(c *gin.Context) {
	var req VectorDocumentUpload

	if err := c.ShouldBind(&req); err != nil {
		slog.Error("handlerVectorDocumentUpload params invalid", "err", err, "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrParamsInvalid, http.StatusBadRequest)
		return
	}

	if !workers.Contains(req.ChannelName) {
		slog.Error("handlerVectorDocumentUpload channel not existed", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrChannelNotExisted, http.StatusBadRequest)
		return
	}

	slog.Info("handlerVectorDocumentUpload start", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)

	file := req.File
	uploadFile := fmt.Sprintf("%s/file-%s-%d%s", s.config.LogPath, gmd5.MustEncryptString(req.ChannelName), time.Now().UnixNano(), filepath.Ext(file.Filename))
	if err := c.SaveUploadedFile(file, uploadFile); err != nil {
		slog.Error("handlerVectorDocumentUpload save file failed", "err", err, "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrSaveFileFailed, http.StatusBadRequest)
		return
	}

	// Generate collection
	collection := fmt.Sprintf("a%s_%d", gmd5.MustEncryptString(req.ChannelName), time.Now().UnixNano())
	fileName := filepath.Base(file.Filename)

	// update worker
	worker := workers.Get(req.ChannelName).(*Worker)
	err := worker.update(&WorkerUpdateReq{
		RequestId:   req.RequestId,
		ChannelName: req.ChannelName,
		Collection:  collection,
		FileName:    fileName,
		Path:        uploadFile,
		Ten: &WorkerUpdateReqTen{
			Name: "file_chunk",
			Type: "cmd",
		},
	})
	if err != nil {
		slog.Error("handlerVectorDocumentUpload update worker failed", "err", err, "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrUpdateWorkerFailed, http.StatusBadRequest)
		return
	}

	slog.Info("handlerVectorDocumentUpload end", "channelName", req.ChannelName, "collection", collection, "uploadFile", uploadFile, "requestId", req.RequestId, logTag)
	s.output(c, codeSuccess, map[string]any{"channel_name": req.ChannelName, "collection": collection, "file_name": fileName})
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

	// Unmarshal the JSON content into a map
	var propertyJson map[string]interface{}
	err = json.Unmarshal(content, &propertyJson)
	if err != nil {
		slog.Error("handlerStart unmarshal property.json failed", "err", err, "requestId", req.RequestId, logTag)
		return
	}

	// Get graph name
	graphName := req.GraphName
	if graphName == "" {
		slog.Error("graph_name is mandatory", "requestId", req.RequestId, logTag)
		return
	}

	// Generate token
	req.Token = s.config.AppId
	if s.config.AppCertificate != "" {
		//req.Token, err = rtctokenbuilder.BuildTokenWithUid(s.config.AppId, s.config.AppCertificate, req.ChannelName, 0, rtctokenbuilder.RoleSubscriber, tokenExpirationInSeconds, tokenExpirationInSeconds)
		req.Token, err = rtctokenbuilder.BuildTokenWithRtm(s.config.AppId, s.config.AppCertificate, req.ChannelName, fmt.Sprintf("%d", 0), rtctokenbuilder.RolePublisher, tokenExpirationInSeconds, tokenExpirationInSeconds)
		if err != nil {
			slog.Error("handlerStart generate token failed", "err", err, "requestId", req.RequestId, logTag)
			return
		}
	}

	// Locate the predefined graphs array
	tenSection, ok := propertyJson["_ten"].(map[string]interface{})
	if !ok {
		slog.Error("Invalid format: _ten section missing", "requestId", req.RequestId, logTag)
		return
	}

	predefinedGraphs, ok := tenSection["predefined_graphs"].([]interface{})
	if !ok {
		slog.Error("Invalid format: predefined_graphs missing or not an array", "requestId", req.RequestId, logTag)
		return
	}

	// Filter the graph with the matching name
	var newGraphs []interface{}
	for _, graph := range predefinedGraphs {
		graphMap, ok := graph.(map[string]interface{})
		if ok && graphMap["name"] == graphName {
			newGraphs = append(newGraphs, graph)
		}
	}

	if len(newGraphs) == 0 {
		slog.Error("handlerStart graph not found", "graph", graphName, "requestId", req.RequestId, logTag)
		err = fmt.Errorf("graph not found")
		return
	}

	// Replace the predefined_graphs array with the filtered array
	tenSection["predefined_graphs"] = newGraphs

	// Automatically start on launch
	for _, graph := range newGraphs {
		graphMap, _ := graph.(map[string]interface{})
		graphMap["auto_start"] = true
	}

	// Set additional properties to property.json
	for extensionName, props := range req.Properties {
		if extensionName != "" {
			for prop, val := range props {
				// Construct the path in the nested graph structure
				for _, graph := range newGraphs {
					graphMap, _ := graph.(map[string]interface{})
					nodes, _ := graphMap["nodes"].([]interface{})
					for _, node := range nodes {
						nodeMap, _ := node.(map[string]interface{})
						if nodeMap["name"] == extensionName {
							properties := nodeMap["property"].(map[string]interface{})
							properties[prop] = val
						}
					}
				}
			}
		}
	}

	// Set start parameters to property.json
	for key, props := range startPropMap {
		val := getFieldValue(req, key)
		if val != "" {
			for _, prop := range props {
				// Set each start parameter to the appropriate graph and property
				for _, graph := range newGraphs {
					graphMap, _ := graph.(map[string]interface{})
					nodes, _ := graphMap["nodes"].([]interface{})
					for _, node := range nodes {
						nodeMap, _ := node.(map[string]interface{})
						if nodeMap["name"] == prop.ExtensionName {
							properties := nodeMap["property"].(map[string]interface{})
							properties[prop.Property] = val
						}
					}
				}
			}
		}
	}

	// Marshal the modified JSON back to a string
	modifiedPropertyJson, err := json.MarshalIndent(propertyJson, "", "  ")
	if err != nil {
		slog.Error("handlerStart marshal modified JSON failed", "err", err, "requestId", req.RequestId, logTag)
		return
	}

	ts := time.Now().Format("20060102_150405_000")
	propertyJsonFile = fmt.Sprintf("%s/property-%s-%s.json", s.config.LogPath, url.QueryEscape(req.ChannelName), ts)
	logFile = fmt.Sprintf("%s/app-%s-%s.log", s.config.LogPath, url.QueryEscape(req.ChannelName), ts)
	os.WriteFile(propertyJsonFile, []byte(modifiedPropertyJson), 0644)

	return
}

func (s *HttpServer) Start() {
	r := gin.Default()
	r.Use(corsMiddleware())

	r.GET("/", s.handlerHealth)
	r.GET("/health", s.handlerHealth)
	r.GET("/list", s.handlerList)
	r.POST("/start", s.handlerStart)
	r.POST("/stop", s.handlerStop)
	r.POST("/ping", s.handlerPing)
	r.POST("/token/generate", s.handlerGenerateToken)
	r.GET("/vector/document/preset/list", s.handlerVectorDocumentPresetList)
	r.POST("/vector/document/update", s.handlerVectorDocumentUpdate)
	r.POST("/vector/document/upload", s.handlerVectorDocumentUpload)

	slog.Info("server start", "port", s.config.Port, logTag)

	go timeoutWorkers()
	r.Run(fmt.Sprintf(":%s", s.config.Port))
}

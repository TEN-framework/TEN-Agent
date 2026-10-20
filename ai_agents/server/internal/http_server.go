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
	"os"
	"path/filepath"
	"regexp"
	"strconv"
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
	TenappDir                string
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
	TenappDir            string                            `json:"tenapp_dir,omitempty"` // IGNORED for security - always uses launch tenapp_dir
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

func (s *HttpServer) handleGraphs(c *gin.Context) {
	// read the property.json file and get the graph list from predefined_graphs, return the result as response
    // for every graph object returned, only keep the name and auto_start fields
    // Read property.json from tenapp_dir
    propertyJsonPath := filepath.Join(s.config.TenappDir, "property.json")
    content, err := os.ReadFile(propertyJsonPath)
	if err != nil {
        slog.Error("failed to read property.json file", "err", err, "path", propertyJsonPath, logTag)
		s.output(c, codeErrReadFileFailed, http.StatusInternalServerError)
		return
	}

	var propertyJson map[string]interface{}
	err = json.Unmarshal(content, &propertyJson)
	if err != nil {
		slog.Error("failed to parse property.json file", "err", err, logTag)
		s.output(c, codeErrParseJsonFailed, http.StatusInternalServerError)
		return
	}

	tenSection, ok := propertyJson["ten"].(map[string]interface{})
	if !ok {
		slog.Error("Invalid format: _ten section missing", logTag)
		s.output(c, codeErrParseJsonFailed, http.StatusInternalServerError)
		return
	}

	predefinedGraphs, ok := tenSection["predefined_graphs"].([]interface{})
	if !ok {
		slog.Error("Invalid format: predefined_graphs missing or not an array", logTag)
		s.output(c, codeErrParseJsonFailed, http.StatusInternalServerError)
		return
	}

	// Filter the graph with the matching name
	var graphs []map[string]interface{}
	for _, graph := range predefinedGraphs {
		graphMap, ok := graph.(map[string]interface{})
		if ok {
			graphs = append(graphs, map[string]interface{}{
				"name":       graphMap["name"],
				"graph_id":   graphMap["name"],
				"auto_start": graphMap["auto_start"],
			})
		}
	}

	s.output(c, codeSuccess, graphs)
}

func (s *HttpServer) handleAddonDefaultProperties(c *gin.Context) {
	// Get the base directory path
	baseDir := "./agents/ten_packages/extension"

	// Read all folders under the base directory
	entries, err := os.ReadDir(baseDir)
	if err != nil {
		slog.Error("failed to read extension directory", "err", err, logTag)
		s.output(c, codeErrReadDirectoryFailed, http.StatusInternalServerError)
		return
	}

	// Iterate through each folder and read the property.json file
	var addons []map[string]interface{}
	for _, entry := range entries {
		if entry.IsDir() {
			addonName := entry.Name()
			propertyFilePath := fmt.Sprintf("%s/%s/property.json", baseDir, addonName)
			content, err := os.ReadFile(propertyFilePath)
			if err != nil {
				slog.Warn("failed to read property file", "addon", addonName, "err", err, logTag)
				continue
			}

			var properties map[string]interface{}
			err = json.Unmarshal(content, &properties)
			if err != nil {
				slog.Warn("failed to parse property file", "addon", addonName, "err", err, logTag)
				continue
			}

			addons = append(addons, map[string]interface{}{
				"addon":    addonName,
				"property": properties,
			})
		}
	}

	s.output(c, codeSuccess, addons)
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

	// Check if the graphName contains "gemini"
	if strings.Contains(req.GraphName, "gemini") {
		// Count existing workers with the same graphName
		graphNameCount := 0
		for _, channelName := range workers.Keys() {
			worker := workers.Get(channelName).(*Worker)
			if worker.GraphName == req.GraphName {
				graphNameCount++
			}
		}

		// Reject if more than 3 workers are using the same graphName
		if graphNameCount >= MAX_GEMINI_WORKER_COUNT {
			slog.Error("handlerStart graphName workers exceed limit", "graphName", req.GraphName, "graphNameCount", graphNameCount, logTag)
			s.output(c, codeErrWorkersLimit, http.StatusTooManyRequests)
			return
		}
	}

	req.WorkerHttpServerPort = getHttpServerPort()

	// Security: Always use launch tenapp_dir, ignore request tenapp_dir to prevent path traversal attacks
	tenappDir := s.config.TenappDir
	if req.TenappDir != "" {
		slog.Warn("Ignoring request tenapp_dir for security", "requestId", req.RequestId, "requestedTenappDir", req.TenappDir, logTag)
	}
	slog.Info("Using launch tenapp_dir", "requestId", req.RequestId, "tenappDir", tenappDir, logTag)

	propertyJsonFile, logFile, err := s.processProperty(&req, tenappDir)
	if err != nil {
		slog.Error("handlerStart process property", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrProcessPropertyFailed, http.StatusInternalServerError)
		return
	}

	worker := newWorker(req.ChannelName, logFile, s.config.Log2Stdout, propertyJsonFile, tenappDir)
	worker.HttpServerPort = req.WorkerHttpServerPort
	worker.GraphName = req.GraphName // Save graphName in the Worker instance

	if req.QuitTimeoutSeconds > 0 || req.QuitTimeoutSeconds == WORKER_TIMEOUT_INFINITY {
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

	// Validate channel name to prevent path injection
	safeChannelName, err := sanitizeChannelName(req.ChannelName)
	if err != nil {
		slog.Error("Invalid channel name in upload", "channelName", req.ChannelName, "requestId", req.RequestId, "err", err, logTag)
		s.output(c, codeErrParamsInvalid, http.StatusBadRequest)
		return
	}

	file := req.File
	uploadFile := fmt.Sprintf("%s/file-%s-%d%s", s.config.LogPath, gmd5.MustEncryptString(safeChannelName), time.Now().UnixNano(), filepath.Ext(file.Filename))
	if err := c.SaveUploadedFile(file, uploadFile); err != nil {
		slog.Error("handlerVectorDocumentUpload save file failed", "err", err, "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrSaveFileFailed, http.StatusBadRequest)
		return
	}

	// Generate collection
	collection := fmt.Sprintf("a%s_%d", gmd5.MustEncryptString(safeChannelName), time.Now().UnixNano())
	fileName := filepath.Base(file.Filename)

	// update worker
	worker := workers.Get(req.ChannelName).(*Worker)
	err = worker.update(&WorkerUpdateReq{
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

// Helper function to recursively merge two maps
func mergeProperties(original, newProps map[string]interface{}) map[string]interface{} {
	for key, newValue := range newProps {
		if existingValue, exists := original[key]; exists {
			// If the existing value is a map, recursively merge
			if existingMap, ok := existingValue.(map[string]interface{}); ok {
				if newMap, ok := newValue.(map[string]interface{}); ok {
					original[key] = mergeProperties(existingMap, newMap)
				} else {
					original[key] = newValue // Replace value if it's not a map
				}
			} else {
				original[key] = newValue // Replace non-map values
			}
		} else {
			// If the key doesn't exist, simply add the new value
			original[key] = newValue
		}
	}
	return original
}

// convertToString converts a value of any type to string using strconv package
func convertToString(val interface{}) string {
	if val == nil {
		return ""
	}

	switch v := val.(type) {
	case string:
		return v
	case bool:
		return strconv.FormatBool(v)
	case int:
		return strconv.FormatInt(int64(v), 10)
	case int32:
		return strconv.FormatInt(int64(v), 10)
	case int64:
		return strconv.FormatInt(v, 10)
	case uint32:
		return strconv.FormatUint(uint64(v), 10)
	case uint64:
		return strconv.FormatUint(v, 10)
	case float32:
		return strconv.FormatFloat(float64(v), 'f', -1, 32)
	case float64:
		return strconv.FormatFloat(v, 'f', -1, 64)
	default:
		// Fallback for unsupported types
		return fmt.Sprintf("%v", val)
	}
}

func (s *HttpServer) processProperty(req *StartReq, tenappDir string) (propertyJsonFile string, logFile string, err error) {
	// Debug logging
	slog.Info("processProperty called", "requestId", req.RequestId, "tenappDir", tenappDir, "logPath", s.config.LogPath, logTag)

	// Build property.json path based on tenapp_dir
	propertyJsonPath := filepath.Join(tenappDir, "property.json")
	slog.Info("Reading property.json from", "requestId", req.RequestId, "propertyJsonPath", propertyJsonPath, logTag)

	content, err := os.ReadFile(propertyJsonPath)
	if err != nil {
		slog.Error("handlerStart read property.json failed", "err", err, "propertyJsonPath", propertyJsonPath, "requestId", req.RequestId, logTag)
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
	tenSection, ok := propertyJson["ten"].(map[string]interface{})
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
					graphData, _ := graphMap["graph"].(map[string]interface{})
					nodes, _ := graphData["nodes"].([]interface{})
					for _, node := range nodes {
						nodeMap, _ := node.(map[string]interface{})
						if nodeMap["name"] == extensionName {
							properties := nodeMap["property"].(map[string]interface{})

							// Handle type assertion properly
							if existingProp, ok := properties[prop].(map[string]interface{}); ok {
								// If the existing property is a map, merge it
								properties[prop] = mergeProperties(existingProp, val.(map[string]interface{}))
							} else {
								// If the existing property is not a map, convert it or skip the merge
								// You can initialize a new map or just replace the value
								if newProp, ok := val.(map[string]interface{}); ok {
									properties[prop] = newProp
								} else {
									// If val is not a map, you may just set it as a value directly
									properties[prop] = val
								}
							}
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
				// Convert value type if specified
				var finalVal interface{} = val
				if prop.ConvertType == "string" {
					finalVal = convertToString(val)
				}

				// Set each start parameter to the appropriate graph and property
				for _, graph := range newGraphs {
					graphMap, _ := graph.(map[string]interface{})
					graphData, _ := graphMap["graph"].(map[string]interface{})
					nodes, _ := graphData["nodes"].([]interface{})
					for _, node := range nodes {
						nodeMap, _ := node.(map[string]interface{})
						if nodeMap["name"] == prop.ExtensionName {
							properties := nodeMap["property"].(map[string]interface{})
							properties[prop.Property] = finalVal
						}
					}
				}
			}
		}
	}

	// Property-based channel auto-injection: inject channel into ANY node that has a "channel" property
	// This is additive to the startPropMap above and enables dynamic channel for extensions like
	// heygen_avatar_python, anam_avatar_python, etc. without needing to add them to startPropMap
	if req.ChannelName != "" {
		for _, graph := range newGraphs {
			graphMap, _ := graph.(map[string]interface{})
			graphData, _ := graphMap["graph"].(map[string]interface{})
			nodes, _ := graphData["nodes"].([]interface{})
			for _, node := range nodes {
				nodeMap, _ := node.(map[string]interface{})
				if properties, ok := nodeMap["property"].(map[string]interface{}); ok {
					// If this node has a "channel" property defined, inject the dynamic value
					if _, hasChannel := properties["channel"]; hasChannel {
						properties["channel"] = req.ChannelName
						slog.Info("Auto-injected channel into node", "node", nodeMap["name"], "channel", req.ChannelName, "requestId", req.RequestId, logTag)
					}
				}
			}
		}
	}

	// Validate environment variables in the "nodes" section
	// Support optional env placeholder with default: ${env:VAR|default}
	// Capture groups:
	//  1) variable name
	//  2) optional default part starting with '|', may be empty string like '|'
	envPattern := regexp.MustCompile(`\${env:([^}|]+)(\|[^}]*)?}`)
	for _, graph := range newGraphs {
		graphMap, _ := graph.(map[string]interface{})
		graphData, _ := graphMap["graph"].(map[string]interface{})
		nodes, ok := graphData["nodes"].([]interface{})
		if !ok {
			slog.Info("No nodes section in the graph", "graph", graphName, "requestId", req.RequestId, logTag)
			continue
		}
		for _, node := range nodes {
			nodeMap, _ := node.(map[string]interface{})
			properties, ok := nodeMap["property"].(map[string]interface{})
			if !ok {
				// slog.Info("No property section in the node", "node", nodeMap, "requestId", req.RequestId, logTag)
				continue
			}
			for key, val := range properties {
				strVal, ok := val.(string)
				if !ok {
					continue
				}
				// Log the property value being processed
				// slog.Info("Processing property", "key", key, "value", strVal)

				matches := envPattern.FindAllStringSubmatch(strVal, -1)
				// if len(matches) == 0 {
				// 	slog.Info("No environment variable patterns found in property", "key", key, "value", strVal)
				// }

				for _, match := range matches {
					if len(match) < 2 {
						continue
					}
					variable := match[1]
					// match[2] contains the optional default part (e.g., "|some-default" or just "|")
					hasDefault := len(match) >= 3 && match[2] != ""
					exists := os.Getenv(variable) != ""
					// slog.Info("Checking environment variable", "variable", variable, "exists", exists, "hasDefault", hasDefault)
					if !exists {
						if hasDefault {
							// Optional env not set; skip error logging
							slog.Info("Optional environment variable not set; using default", "variable", variable, "property", key, "requestId", req.RequestId, logTag)
						} else {
							slog.Error("Environment variable not found", "variable", variable, "property", key, "requestId", req.RequestId, logTag)
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

	// Use a more reliable temp directory if LogPath is not writable
	tempDir := s.config.LogPath

	// Test if we can actually write to the directory by trying to create a test file
	testFile := filepath.Join(tempDir, "test-write-permission")
	if testFileHandle, testErr := os.Create(testFile); testErr != nil {
		// Fallback to system temp directory
		tempDir = os.TempDir()
		slog.Info("Using system temp directory as fallback", "requestId", req.RequestId, "tempDir", tempDir, "originalLogPath", s.config.LogPath, "testErr", testErr, logTag)
	} else {
		// Clean up test file
		testFileHandle.Close()
		os.Remove(testFile)
		slog.Info("LogPath is writable", "requestId", req.RequestId, "tempDir", tempDir, logTag)
	}

	// Validate and sanitize channel name to prevent path injection
	safeChannelName, err := sanitizeChannelName(req.ChannelName)
	if err != nil {
		slog.Error("Invalid channel name", "channelName", req.ChannelName, "requestId", req.RequestId, "err", err, logTag)
		return "", "", fmt.Errorf("invalid channel name: %w", err)
	}

	propertyJsonFile = filepath.Join(tempDir, fmt.Sprintf("property-%s-%s.json", safeChannelName, ts))
	// Ensure absolute path for property.json file
	propertyJsonFile, err = filepath.Abs(propertyJsonFile)
	if err != nil {
		slog.Error("Failed to get absolute path for property.json", "err", err, "requestId", req.RequestId, logTag)
		return "", "", err
	}

	// Validate that the final path is within the expected directory
	if !isPathSafe(propertyJsonFile, tempDir) {
		slog.Error("Path traversal detected", "propertyJsonFile", propertyJsonFile, "tempDir", tempDir, "requestId", req.RequestId, logTag)
		return "", "", fmt.Errorf("path traversal detected in property file path")
	}
	logFile = fmt.Sprintf("%s/app-%s-%s.log", s.config.LogPath, safeChannelName, ts)

	// Debug logging
	slog.Info("Writing temporary property.json file", "requestId", req.RequestId, "propertyJsonFile", propertyJsonFile, "logPath", s.config.LogPath, logTag)

	// Ensure the directory exists before writing the file
	dir := filepath.Dir(propertyJsonFile)
	slog.Info("Creating directory", "requestId", req.RequestId, "dir", dir, logTag)
	if mkdirErr := os.MkdirAll(dir, 0755); mkdirErr != nil {
		slog.Error("Failed to create directory for property.json file", "err", mkdirErr, "dir", dir, "requestId", req.RequestId, logTag)
		return
	}
	slog.Info("Directory created successfully", "requestId", req.RequestId, "dir", dir, logTag)

	// Check if directory exists and is writable
	if stat, statErr := os.Stat(dir); statErr != nil {
		slog.Error("Directory stat failed", "err", statErr, "dir", dir, "requestId", req.RequestId, logTag)
		return
	} else {
		slog.Info("Directory stat", "requestId", req.RequestId, "dir", dir, "mode", stat.Mode(), "isDir", stat.IsDir(), logTag)
	}

	// Additional debugging for file path
	slog.Info("About to write file", "requestId", req.RequestId, "propertyJsonFile", propertyJsonFile, "fileSize", len(modifiedPropertyJson), logTag)

	// Try to create the file first to see if there are any permission issues
	file, createErr := os.Create(propertyJsonFile)
	if createErr != nil {
		slog.Error("Failed to create file", "err", createErr, "propertyJsonFile", propertyJsonFile, "requestId", req.RequestId, logTag)
		return
	}
	defer file.Close()

	// Write content to file
	_, writeErr := file.Write([]byte(modifiedPropertyJson))
	if writeErr != nil {
		slog.Error("Failed to write content to file", "err", writeErr, "propertyJsonFile", propertyJsonFile, "requestId", req.RequestId, logTag)
		return
	}

	// Sync to ensure data is written to disk
	if syncErr := file.Sync(); syncErr != nil {
		slog.Error("Failed to sync file", "err", syncErr, "propertyJsonFile", propertyJsonFile, "requestId", req.RequestId, logTag)
		return
	}

	slog.Info("Successfully wrote temporary property.json file", "requestId", req.RequestId, "propertyJsonFile", propertyJsonFile, logTag)

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
	r.GET("/graphs", s.handleGraphs)
	r.GET("/dev-tmp/addons/default-properties", s.handleAddonDefaultProperties)
	r.POST("/token/generate", s.handlerGenerateToken)
	r.GET("/vector/document/preset/list", s.handlerVectorDocumentPresetList)
	r.POST("/vector/document/update", s.handlerVectorDocumentUpdate)
	r.POST("/vector/document/upload", s.handlerVectorDocumentUpload)

	slog.Info("server start", "port", s.config.Port, logTag)

	go timeoutWorkers()
	r.Run(fmt.Sprintf(":%s", s.config.Port))
}

// sanitizeChannelName validates and sanitizes channel name to prevent path injection
func sanitizeChannelName(channelName string) (string, error) {
	if channelName == "" {
		return "", fmt.Errorf("channel name cannot be empty")
	}

	// Check length limit
	if len(channelName) > 100 {
		return "", fmt.Errorf("channel name too long")
	}

	// Check for path traversal characters
	if strings.Contains(channelName, "..") ||
	   strings.Contains(channelName, "/") ||
	   strings.Contains(channelName, "\\") ||
	   strings.Contains(channelName, "\x00") {
		return "", fmt.Errorf("channel name contains invalid characters")
	}

	// Check if starts with dot (hidden file)
	if strings.HasPrefix(channelName, ".") {
		return "", fmt.Errorf("channel name cannot start with dot")
	}

	// Sanitize the channel name for safe use in filenames
	sanitized := strings.ReplaceAll(channelName, "/", "_")
	sanitized = strings.ReplaceAll(sanitized, "\\", "_")
	sanitized = strings.ReplaceAll(sanitized, "..", "__")
	sanitized = strings.ReplaceAll(sanitized, "\x00", "")

	// Remove any other potentially dangerous characters
	sanitized = strings.ReplaceAll(sanitized, ":", "_")
	sanitized = strings.ReplaceAll(sanitized, "*", "_")
	sanitized = strings.ReplaceAll(sanitized, "?", "_")
	sanitized = strings.ReplaceAll(sanitized, "\"", "_")
	sanitized = strings.ReplaceAll(sanitized, "<", "_")
	sanitized = strings.ReplaceAll(sanitized, ">", "_")
	sanitized = strings.ReplaceAll(sanitized, "|", "_")

	// Limit length after sanitization
	if len(sanitized) > 50 {
		sanitized = sanitized[:50]
	}

	// If result is empty, use default value
	if sanitized == "" {
		sanitized = "default"
	}

	return sanitized, nil
}

// isPathSafe validates that the given path is within the expected base directory
func isPathSafe(path, baseDir string) bool {
	absPath, err := filepath.Abs(path)
	if err != nil {
		return false
	}

	absBase, err := filepath.Abs(baseDir)
	if err != nil {
		return false
	}

	// Check if the path is within the base directory
	return strings.HasPrefix(absPath, absBase)
}

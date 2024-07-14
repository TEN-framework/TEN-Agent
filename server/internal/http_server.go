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
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"strings"
	"time"

	rtctokenbuilder "github.com/AgoraIO/Tools/DynamicKey/AgoraDynamicKey/go/src/rtctokenbuilder2"
	"github.com/gin-gonic/gin"
	"github.com/gin-gonic/gin/binding"
	"github.com/gogf/gf/crypto/gmd5"
	"github.com/tidwall/gjson"
	"github.com/tidwall/sjson"
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

type PingReq struct {
	RequestId   string `form:"request_id,omitempty" json:"request_id,omitempty"`
	ChannelName string `form:"channel_name,omitempty" json:"channel_name,omitempty"`
}

type StartReq struct {
	RequestId        string `form:"request_id,omitempty" json:"request_id,omitempty"`
	AgoraAsrLanguage string `form:"agora_asr_language,omitempty" json:"agora_asr_language,omitempty"`
	ChannelName      string `form:"channel_name,omitempty" json:"channel_name,omitempty"`
	RemoteStreamId   uint32 `form:"remote_stream_id,omitempty" json:"remote_stream_id,omitempty"`
	VoiceType        string `form:"voice_type,omitempty" json:"voice_type,omitempty"`
}

type StopReq struct {
	RequestId   string `form:"request_id,omitempty" json:"request_id,omitempty"`
	ChannelName string `form:"channel_name,omitempty" json:"channel_name,omitempty"`
}

type GenerateTokenReq struct {
	RequestId   string `form:"request_id,omitempty" json:"request_id,omitempty"`
	ChannelName string `form:"channel_name,omitempty" json:"channel_name,omitempty"`
	Uid         uint32 `form:"uid,omitempty" json:"uid,omitempty"`
}

const (
	privilegeExpirationInSeconds = uint32(86400)
	tokenExpirationInSeconds     = uint32(86400)

	languageChinese = "zh-CN"
	languageEnglish = "en-US"

	ManifestJsonFile           = "./agents/manifest.json"
	ManifestJsonFileElevenlabs = "./agents/manifest.elevenlabs.json"
	ManifestJsonFileEN         = "./agents/manifest.en.json"
	ManifestJsonFileCN         = "./agents/manifest.cn.json"

	TTSVendorAzure      = "azure"
	TTSVendorElevenlabs = "elevenlabs"

	voiceTypeMale   = "male"
	voiceTypeFemale = "female"
)

var (
	voiceNameMap = map[string]map[string]map[string]string{
		languageChinese: {
			TTSVendorAzure: {
				voiceTypeMale:   "zh-CN-YunxiNeural",
				voiceTypeFemale: "zh-CN-XiaoxiaoNeural",
			},
			TTSVendorElevenlabs: {
				voiceTypeMale:   "pNInz6obpgDQGcFmaJgB", // Adam
				voiceTypeFemale: "Xb7hH8MSUJpSbSDYk0k2", // Alice
			},
		},
		languageEnglish: {
			TTSVendorAzure: {
				voiceTypeMale:   "en-US-BrianNeural",
				voiceTypeFemale: "en-US-JaneNeural",
			},
			TTSVendorElevenlabs: {
				voiceTypeMale:   "pNInz6obpgDQGcFmaJgB", // Adam
				voiceTypeFemale: "Xb7hH8MSUJpSbSDYk0k2", // Alice
			},
		},
	}

	logTag = slog.String("service", "HTTP_SERVER")
)

func NewHttpServer(httpServerConfig *HttpServerConfig) *HttpServer {
	return &HttpServer{
		config: httpServerConfig,
	}
}

func (s *HttpServer) getManifestJsonFile(language string) (manifestJsonFile string) {
	// ttsVendor := s.getTtsVendor(language)
	manifestJsonFile = ManifestJsonFile

	if language == languageEnglish {
		manifestJsonFile = ManifestJsonFileEN
	} else if language == languageChinese {
		manifestJsonFile = ManifestJsonFileCN
	}
	// if ttsVendor == TTSVendorElevenlabs {
	// 	manifestJsonFile = ManifestJsonFileElevenlabs
	// }

	return
}

func (s *HttpServer) getTtsVendor(language string) string {
	if language == languageChinese {
		return s.config.TTSVendorChinese
	}

	return s.config.TTSVendorEnglish
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

	manifestJsonFile, logFile, err := s.processManifest(&req)
	if err != nil {
		slog.Error("handlerStart process manifest", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, codeErrProcessManifestFailed, http.StatusInternalServerError)
		return
	}

	worker := newWorker(req.ChannelName, logFile, manifestJsonFile)
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
		s.output(c, codeErrStopAppFailed, http.StatusInternalServerError)
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

	token, err := rtctokenbuilder.BuildTokenWithUid(s.config.AppId, s.config.AppCertificate, req.ChannelName, req.Uid, rtctokenbuilder.RolePublisher, tokenExpirationInSeconds, privilegeExpirationInSeconds)
	if err != nil {
		slog.Error("handlerGenerateToken generate token failed", "err", err, "requestId", req.RequestId, logTag)
		s.output(c, codeErrGenerateTokenFailed, http.StatusBadRequest)
		return
	}

	slog.Info("handlerGenerateToken end", "requestId", req.RequestId, logTag)
	s.output(c, codeSuccess, map[string]any{"appId": s.config.AppId, "token": token, "channel_name": req.ChannelName, "uid": req.Uid})
}

func (s *HttpServer) output(c *gin.Context, code *Code, data any, httpStatus ...int) {
	if len(httpStatus) == 0 {
		httpStatus = append(httpStatus, http.StatusOK)
	}

	c.JSON(httpStatus[0], gin.H{"code": code.code, "msg": code.msg, "data": data})
}

func (s *HttpServer) processManifest(req *StartReq) (manifestJsonFile string, logFile string, err error) {
	manifestJsonFile = s.getManifestJsonFile(req.AgoraAsrLanguage)
	content, err := os.ReadFile(manifestJsonFile)
	if err != nil {
		slog.Error("handlerStart read manifest.json failed", "err", err, "manifestJsonFile", manifestJsonFile, "requestId", req.RequestId, logTag)
		return
	}

	manifestJson := string(content)

	if s.config.AppId != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="agora_rtc").property.app_id`, s.config.AppId)
	}
	appId := gjson.Get(manifestJson, `predefined_graphs.0.nodes.#(name=="agora_rtc").property.app_id`).String()

	// Generate token
	token := appId
	if s.config.AppCertificate != "" {
		token, err = rtctokenbuilder.BuildTokenWithUid(appId, s.config.AppCertificate, req.ChannelName, 0, rtctokenbuilder.RoleSubscriber, tokenExpirationInSeconds, privilegeExpirationInSeconds)
		if err != nil {
			slog.Error("handlerStart generate token failed", "err", err, "requestId", req.RequestId, logTag)
			return
		}
	}

	manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="agora_rtc").property.token`, token)
	if req.AgoraAsrLanguage != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="agora_rtc").property.agora_asr_language`, req.AgoraAsrLanguage)
	}
	if req.ChannelName != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="agora_rtc").property.channel`, req.ChannelName)
	}
	if req.RemoteStreamId != 0 {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="agora_rtc").property.remote_stream_id`, req.RemoteStreamId)
	}

	language := gjson.Get(manifestJson, `predefined_graphs.0.nodes.#(name=="agora_rtc").property.agora_asr_language`).String()

	ttsVendor := s.getTtsVendor(language)
	voiceName := voiceNameMap[language][ttsVendor][req.VoiceType]
	if voiceName != "" {
		if ttsVendor == TTSVendorAzure {
			manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="azure_tts").property.azure_synthesis_voice_name`, voiceName)
		} else if ttsVendor == TTSVendorElevenlabs {
			manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="elevenlabs_tts").property.voice_id`, voiceName)
		}
	}

	channelNameMd5 := gmd5.MustEncryptString(req.ChannelName)
	ts := time.Now().UnixNano()
	manifestJsonFile = fmt.Sprintf("/tmp/manifest-%s-%d.json", channelNameMd5, ts)
	logFile = fmt.Sprintf("/tmp/app-%s-%d.log", channelNameMd5, ts)
	os.WriteFile(manifestJsonFile, []byte(manifestJson), 0644)

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

	slog.Info("server start", "port", s.config.Port, logTag)

	go cleanWorker()
	r.Run(s.config.Port)
}

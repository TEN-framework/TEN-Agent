package service

import (
	"app/internal/common"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"strings"
	"time"

	rtctokenbuilder "github.com/AgoraIO/Tools/DynamicKey/AgoraDynamicKey/go/src/rtctokenbuilder2"
	"github.com/gin-gonic/gin"
	"github.com/gin-gonic/gin/binding"
	"github.com/gogf/gf/container/gmap"
	"github.com/gogf/gf/crypto/gmd5"
	"github.com/google/uuid"
	"github.com/tidwall/gjson"
	"github.com/tidwall/sjson"
)

const (
	privilegeExpirationInSeconds = uint32(86400)
	tokenExpirationInSeconds     = uint32(86400)

	languageChinese = "zh-CN"
	languageEnglish = "en-US"

	ManifestJsonFile           = "./agents/manifest.json"
	ManifestJsonFileElevenlabs = "./agents/manifest.elevenlabs.json"

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
	logTag = slog.String("service", "MAIN_SERVICE")
)

type MainService struct {
	config  MainServiceConfig
	workers *gmap.Map
}

type MainServiceConfig struct {
	AppId                    string
	AppCertificate           string
	ManifestJsonFile         string
	TTSVendorChinese         string
	TTSVendorEnglish         string
	WorkersMax               int
	WorkerQuitTimeoutSeconds int
}

func NewMainService(config MainServiceConfig) *MainService {
	return &MainService{
		config:  config,
		workers: gmap.New(true),
	}
}

func (s *MainService) output(c *gin.Context, code *common.Code, data any, httpStatus ...int) {
	if len(httpStatus) == 0 {
		httpStatus = append(httpStatus, http.StatusOK)
	}

	c.JSON(httpStatus[0], gin.H{"code": code.Code, "msg": code.Msg, "data": data})
}

func (s *MainService) HandlerHealth(c *gin.Context) {
	slog.Debug("handlerHealth", logTag)
	s.output(c, common.CodeOk, nil)
}

func (s *MainService) HandlerPing(c *gin.Context) {
	var req common.PingReq

	if err := c.ShouldBindBodyWith(&req, binding.JSON); err != nil {
		slog.Error("handlerPing params invalid", "err", err, logTag)
		s.output(c, common.CodeErrParamsInvalid, http.StatusBadRequest)
		return
	}

	slog.Info("handlerPing start", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)

	if strings.TrimSpace(req.ChannelName) == "" {
		slog.Error("handlerPing channel empty", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, common.CodeErrChannelEmpty, http.StatusBadRequest)
		return
	}

	if !s.workers.Contains(req.ChannelName) {
		slog.Error("handlerPing channel not existed", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, common.CodeErrChannelNotExisted, http.StatusBadRequest)
		return
	}

	// Update worker
	worker := s.workers.Get(req.ChannelName).(*Worker)
	worker.UpdateTs = time.Now().Unix()

	slog.Info("handlerPing end", "worker", worker, "requestId", req.RequestId, logTag)
	s.output(c, common.CodeSuccess, nil)
}

// HandlerStart is a handle for start worker.
func (s *MainService) HandlerStart(c *gin.Context) {
	workersRunning := s.workers.Size()

	slog.Info("handlerStart start", "workersRunning", workersRunning, logTag)

	var req common.StartReq
	if err := c.ShouldBindBodyWith(&req, binding.JSON); err != nil {
		slog.Error("handlerStart params invalid", "err", err, "requestId", req.RequestId, logTag)
		s.output(c, common.CodeErrParamsInvalid, http.StatusBadRequest)
		return
	}

	if strings.TrimSpace(req.ChannelName) == "" {
		slog.Error("handlerStart channel empty", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, common.CodeErrChannelEmpty, http.StatusBadRequest)
		return
	}

	if workersRunning >= s.config.WorkersMax {
		slog.Error("handlerStart workers exceed", "workersRunning", workersRunning, "WorkersMax", s.config.WorkersMax, "requestId", req.RequestId, logTag)
		s.output(c, common.CodeErrWorkersLimit, http.StatusTooManyRequests)
		return
	}

	if s.workers.Contains(req.ChannelName) {
		slog.Error("handlerStart channel existed", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, common.CodeErrChannelExisted, http.StatusBadRequest)
		return
	}

	manifestJsonFile, logFile, err := s.createWorkerManifest(&req)
	if err != nil {
		slog.Error("handlerStart create worker manifest", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, common.CodeErrProcessManifestFailed, http.StatusInternalServerError)
		return
	}

	worker := newWorker(req.ChannelName, logFile, manifestJsonFile)
	worker.QuitTimeoutSeconds = s.config.WorkerQuitTimeoutSeconds
	if err := worker.start(&req); err != nil {
		slog.Error("handlerStart start worker failed", "err", err, "requestId", req.RequestId, logTag)
		s.output(c, common.CodeErrStartWorkerFailed, http.StatusInternalServerError)
		return
	}
	s.workers.SetIfNotExist(req.ChannelName, worker)

	slog.Info("handlerStart end", "workersRunning", s.workers.Size(), "worker", worker, "requestId", req.RequestId, logTag)
	s.output(c, common.CodeSuccess, nil)
}

func (s *MainService) HandlerStop(c *gin.Context) {
	var req common.StopReq

	if err := c.ShouldBindBodyWith(&req, binding.JSON); err != nil {
		slog.Error("handlerStop params invalid", "err", err, logTag)
		s.output(c, common.CodeErrParamsInvalid, http.StatusBadRequest)
		return
	}

	slog.Info("handlerStop start", "req", req, logTag)

	if strings.TrimSpace(req.ChannelName) == "" {
		slog.Error("handlerStop channel empty", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, common.CodeErrChannelEmpty, http.StatusBadRequest)
		return
	}

	if !s.workers.Contains(req.ChannelName) {
		slog.Error("handlerStop channel not existed", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, common.CodeErrChannelNotExisted, http.StatusBadRequest)
		return
	}

	worker := s.workers.Get(req.ChannelName).(*Worker)
	if err := worker.stop(req.RequestId, req.ChannelName); err != nil {
		slog.Error("handlerStop kill app failed", "err", err, "worker", s.workers.Get(req.ChannelName), "requestId", req.RequestId, logTag)
		s.output(c, common.CodeErrStopAppFailed, http.StatusInternalServerError)
		return
	}
	s.workers.Remove(req.ChannelName)

	slog.Info("handlerStop end", "requestId", req.RequestId, logTag)
	s.output(c, common.CodeSuccess, nil)
}

func (s *MainService) HandlerGenerateToken(c *gin.Context) {
	var req common.GenerateTokenReq

	if err := c.ShouldBindBodyWith(&req, binding.JSON); err != nil {
		slog.Error("handlerGenerateToken params invalid", "err", err, logTag)
		s.output(c, common.CodeErrParamsInvalid, http.StatusBadRequest)
		return
	}

	slog.Info("handlerGenerateToken start", "req", req, logTag)

	if strings.TrimSpace(req.ChannelName) == "" {
		slog.Error("handlerGenerateToken channel empty", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		s.output(c, common.CodeErrChannelEmpty, http.StatusBadRequest)
		return
	}

	if s.config.AppCertificate == "" {
		s.output(c, common.CodeSuccess, map[string]any{"appId": s.config.AppId, "token": s.config.AppId, "channel_name": req.ChannelName, "uid": req.Uid})
		return
	}

	token, err := rtctokenbuilder.BuildTokenWithUid(s.config.AppId, s.config.AppCertificate, req.ChannelName, req.Uid, rtctokenbuilder.RolePublisher, tokenExpirationInSeconds, privilegeExpirationInSeconds)
	if err != nil {
		slog.Error("handlerGenerateToken generate token failed", "err", err, "requestId", req.RequestId, logTag)
		s.output(c, common.CodeErrGenerateTokenFailed, http.StatusBadRequest)
		return
	}

	slog.Info("handlerGenerateToken end", "requestId", req.RequestId, logTag)
	s.output(c, common.CodeSuccess, map[string]any{"appId": s.config.AppId, "token": token, "channel_name": req.ChannelName, "uid": req.Uid})
}

// createWorkerManifest create worker temporary Mainfest.
func (s *MainService) createWorkerManifest(req *common.StartReq) (manifestJsonFile string, logFile string, err error) {
	content, err := os.ReadFile(s.config.ManifestJsonFile)
	if err != nil {
		slog.Error("handlerStart read manifest.json failed", "err", err, "manifestJsonFile", s.config.ManifestJsonFile, "requestId", req.RequestId, logTag)
		return "", "", err
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
			return "", "", err
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
	err = os.WriteFile(manifestJsonFile, []byte(manifestJson), 0644)
	if err != nil {
		slog.Error("handlerStart write manifest.json failed", "err", err, "manifestJsonFile", s.config.ManifestJsonFile, "requestId", req.RequestId, logTag)
		return "", "", err
	}

	return manifestJsonFile, logFile, nil
}

// CleanWorker clean unused workers in background.
func (s *MainService) CleanWorker() {
	for {
		for _, channelName := range s.workers.Keys() {
			worker := s.workers.Get(channelName).(*Worker)

			nowTs := time.Now().Unix()
			if worker.UpdateTs+int64(worker.QuitTimeoutSeconds) < nowTs {
				if err := worker.stop(uuid.New().String(), channelName.(string)); err != nil {
					slog.Error("Worker cleanWorker failed", "err", err, "channelName", channelName, logTag)
					continue
				}

				slog.Info("Worker cleanWorker success", "channelName", channelName, "worker", worker, "nowTs", nowTs, logTag)
			}
		}

		slog.Debug("Worker cleanWorker sleep", "sleep", workerCleanSleepSeconds, logTag)
		time.Sleep(workerCleanSleepSeconds * time.Second)
	}
}

func (s *MainService) getManifestJsonFile(language string) (manifestJsonFile string) {
	ttsVendor := s.getTtsVendor(language)
	manifestJsonFile = ManifestJsonFile

	if ttsVendor == TTSVendorElevenlabs {
		manifestJsonFile = ManifestJsonFileElevenlabs
	}

	return
}

func (s *MainService) getTtsVendor(language string) string {
	if language == languageChinese {
		return s.config.TTSVendorChinese
	}

	return s.config.TTSVendorEnglish
}

package internal

import (
	"log/slog"
)

type Prop struct {
	ExtensionName string
	Property      string
}

const (
	// Extension name
	extensionNameAgoraRTC                      = "agora_rtc"
	extensionNameAzureTTS                      = "azure_tts"
	extensionNameBedrockLLM                    = "bedrock_llm"
	extensionNameCosyTTS                       = "cosy_tts"
	extensionNameElevenlabsTTS                 = "elevenlabs_tts"
	extensionNameGeminiLLM                     = "gemini_llm"
	extensionNameLiteLLM                       = "litellm"
	extensionNameOpenaiChatgpt                 = "openai_chatgpt"
	extensionNamePollyTTS                      = "polly_tts"
	extensionNameQwenLLM                       = "qwen_llm"
	extensionNameTranscribeAsr                 = "transcribe_asr"
	extensionNameHttpServer                    = "http_server"
	extensionNameAliyunAnalyticdbVectorStorage = "aliyun_analyticdb_vector_storage"
	extensionNameAliyunTextEmbedding           = "aliyun_text_embedding"

	// Language
	languageChinese = "zh-CN"
	languageEnglish = "en-US"
	// Property json
	PropertyJsonFile = "./agents/property.json"
	// Token expire time
	tokenExpirationInSeconds = uint32(86400)
)

var (
	logTag = slog.String("service", "HTTP_SERVER")

	// Retrieve parameters from the request and map them to the property.json file
	startPropMap = map[string][]Prop{
		"ChannelName": {
			{ExtensionName: extensionNameAgoraRTC, Property: "channel"},
		},
		"RemoteStreamId": {
			{ExtensionName: extensionNameAgoraRTC, Property: "remote_stream_id"},
		},
		"Token": {
			{ExtensionName: extensionNameAgoraRTC, Property: "token"},
		},
		"WorkerHttpServerPort": {
			{ExtensionName: extensionNameHttpServer, Property: "listen_port"},
		},
	}
)

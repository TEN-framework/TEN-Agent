package internal

import (
	"log/slog"
	"os"
)

type Prop struct {
	ExtensionName string
	Property      string
}

const (
	// Extension name
	extensionNameAgoraRTC      = "agora_rtc"
	extensionNameAzureTTS      = "azure_tts"
	extensionNameBedrockLLM    = "bedrock_llm"
	extensionNameCosyTTS       = "cosy_tts"
	extensionNameElevenlabsTTS = "elevenlabs_tts"
	extensionNameGeminiLLM     = "gemini_llm"
	extensionNameLiteLLM       = "litellm"
	extensionNameOpenaiChatgpt = "openai_chatgpt"
	extensionNamePollyTTS      = "polly_tts"
	extensionNameQwenLLM       = "qwen_llm"
	extensionNameTranscribeAsr = "transcribe_asr"

	// Language
	languageChinese = "zh-CN"
	languageEnglish = "en-US"
	// Property json
	PropertyJsonFile = "./agents/property.json"
	// Token expire time
	tokenExpirationInSeconds = uint32(86400)
	// Voice type
	voiceTypeMale   = "male"
	voiceTypeFemale = "female"
)

var (
	logTag = slog.String("service", "HTTP_SERVER")

	// Retrieve configuration information from environment variables and map it to the property.json file
	EnvPropMap = map[string][]Prop{
		"AGORA_APP_ID": {
			{ExtensionName: extensionNameAgoraRTC, Property: "app_id"},
		},
		"ALIBABA_CLOUD_ACCESS_KEY_ID": {
			{ExtensionName: extensionNameAliyunAnalyticdbVectorStorage, Property: "alibaba_cloud_access_key_id"},
		},
		"ALIBABA_CLOUD_ACCESS_KEY_SECRET": {
			{ExtensionName: extensionNameAliyunAnalyticdbVectorStorage, Property: "alibaba_cloud_access_key_secret"},
		},
		"ALIYUN_ANALYTICDB_ACCOUNT": {
			{ExtensionName: extensionNameAliyunAnalyticdbVectorStorage, Property: "adbpg_account"},
		},
		"ALIYUN_ANALYTICDB_ACCOUNT_PASSWORD": {
			{ExtensionName: extensionNameAliyunAnalyticdbVectorStorage, Property: "adbpg_account_password"},
		},
		"ALIYUN_ANALYTICDB_INSTANCE_ID": {
			{ExtensionName: extensionNameAliyunAnalyticdbVectorStorage, Property: "adbpg_instance_id"},
		},
		"ALIYUN_ANALYTICDB_INSTANCE_REGION": {
			{ExtensionName: extensionNameAliyunAnalyticdbVectorStorage, Property: "adbpg_instance_region"},
		},
		"ALIYUN_ANALYTICDB_NAMESPACE": {
			{ExtensionName: extensionNameAliyunAnalyticdbVectorStorage, Property: "adbpg_namespace"},
		},
		"ALIYUN_ANALYTICDB_NAMESPACE_PASSWORD": {
			{ExtensionName: extensionNameAliyunAnalyticdbVectorStorage, Property: "adbpg_namespace_password"},
		},
		"ALIYUN_TEXT_EMBEDDING_API_KEY": {
			{ExtensionName: extensionNameAliyunTextEmbedding, Property: "api_key"},
		},
		"AWS_ACCESS_KEY_ID": {
			{ExtensionName: extensionNameBedrockLLM, Property: "access_key"},
			{ExtensionName: extensionNamePollyTTS, Property: "access_key"},
			{ExtensionName: extensionNameTranscribeAsr, Property: "access_key"},
		},
		"AWS_SECRET_ACCESS_KEY": {
			{ExtensionName: extensionNameBedrockLLM, Property: "secret_key"},
			{ExtensionName: extensionNamePollyTTS, Property: "secret_key"},
			{ExtensionName: extensionNameTranscribeAsr, Property: "secret_key"},
		},
		"AWS_BEDROCK_MODEL": {
			{ExtensionName: extensionNameBedrockLLM, Property: "model"},
		},
		"AWS_REGION": {
			{ExtensionName: extensionNameBedrockLLM, Property: "region"},
			{ExtensionName: extensionNamePollyTTS, Property: "region"},
			{ExtensionName: extensionNameTranscribeAsr, Property: "region"},
		},
		"AZURE_STT_KEY": {
			{ExtensionName: extensionNameAgoraRTC, Property: "agora_asr_vendor_key"},
		},
		"AZURE_STT_REGION": {
			{ExtensionName: extensionNameAgoraRTC, Property: "agora_asr_vendor_region"},
		},
		"AZURE_TTS_KEY": {
			{ExtensionName: extensionNameAzureTTS, Property: "azure_subscription_key"},
		},
		"AZURE_TTS_REGION": {
			{ExtensionName: extensionNameAzureTTS, Property: "azure_subscription_region"}},
		"COSY_TTS_KEY": {
			{ExtensionName: extensionNameCosyTTS, Property: "api_key"},
		},
		"ELEVENLABS_TTS_KEY": {
			{ExtensionName: extensionNameElevenlabsTTS, Property: "api_key"},
		},
		"GEMINI_API_KEY": {
			{ExtensionName: extensionNameGeminiLLM, Property: "api_key"},
		},
		"OPENAI_API_KEY": {
			{ExtensionName: extensionNameOpenaiChatgpt, Property: "api_key"},
		},
		"LITELLM_API_KEY": {
			{ExtensionName: extensionNameLiteLLM, Property: "api_key"},
		},
		"LITELLM_MODEL": {
			{ExtensionName: extensionNameLiteLLM, Property: "model"},
		},
		"LITELLM_PROVIDER": {
			{ExtensionName: extensionNameLiteLLM, Property: "provider"},
		},
		"OPENAI_BASE_URL": {
			{ExtensionName: extensionNameOpenaiChatgpt, Property: "base_url"},
		},
		"OPENAI_MODEL": {
			{ExtensionName: extensionNameOpenaiChatgpt, Property: "model"},
		},
		"OPENAI_PROXY_URL": {
			{ExtensionName: extensionNameOpenaiChatgpt, Property: "proxy_url"},
		},
		"QWEN_API_KEY": {
			{ExtensionName: extensionNameQwenLLM, Property: "api_key"},
		},
	}

	// The corresponding graph name based on the language
	graphNameMap = map[string]string{
		languageChinese: "va.openai.azure",
		languageEnglish: "va.openai.azure",
	}

	// Retrieve parameters from the request and map them to the property.json file
	startPropMap = map[string][]Prop{
		"AgoraAsrLanguage": {
			{ExtensionName: extensionNameAgoraRTC, Property: "agora_asr_language"},
		},
		"ChannelName": {
			{ExtensionName: extensionNameAgoraRTC, Property: "channel"},
		},
		"RemoteStreamId": {
			{ExtensionName: extensionNameAgoraRTC, Property: "remote_stream_id"},
		},
		"Token": {
			{ExtensionName: extensionNameAgoraRTC, Property: "token"},
		},
		"VoiceType": {
			{ExtensionName: extensionNameAzureTTS, Property: "azure_synthesis_voice_name"},
			{ExtensionName: extensionNameElevenlabsTTS, Property: "voice_id"},
		},
		"WorkerHttpServerPort": {
			{ExtensionName: extensionNameHttpServer, Property: "listen_port"},
		},
	}

	// Map the voice name to the voice type
	voiceNameMap = map[string]map[string]map[string]string{
		languageChinese: {
			extensionNameAzureTTS: {
				voiceTypeMale:   "zh-CN-YunxiNeural",
				voiceTypeFemale: "zh-CN-XiaoxiaoNeural",
			},
			extensionNameElevenlabsTTS: {
				voiceTypeMale:   "pNInz6obpgDQGcFmaJgB", // Adam
				voiceTypeFemale: "Xb7hH8MSUJpSbSDYk0k2", // Alice
			},
			extensionNamePollyTTS: {
				voiceTypeMale:   "Zhiyu",
				voiceTypeFemale: "Zhiyu",
			},
		},
		languageEnglish: {
			extensionNameAzureTTS: {
				voiceTypeMale:   "en-US-BrianNeural",
				voiceTypeFemale: "en-US-JaneNeural",
			},
			extensionNameElevenlabsTTS: {
				voiceTypeMale:   "pNInz6obpgDQGcFmaJgB", // Adam
				voiceTypeFemale: "Xb7hH8MSUJpSbSDYk0k2", // Alice
			},
			extensionNamePollyTTS: {
				voiceTypeMale:   "Matthew",
				voiceTypeFemale: "Ruth",
			},
		},
	}
)

func SetGraphNameMap() {
	if graphNameZH := os.Getenv("GRAPH_NAME_ZH"); graphNameZH != "" {
		graphNameMap[languageChinese] = graphNameZH
	}

	if graphNameEN := os.Getenv("GRAPH_NAME_EN"); graphNameEN != "" {
		graphNameMap[languageEnglish] = graphNameEN
	}
}

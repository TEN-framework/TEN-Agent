package internal

import "log/slog"

type Prop struct {
	ExtensionName string
	Property      string
}

const (
	// Extension name
	extensionNameAgoraRTC      = "agora_rtc"
	extensionNameBedrockLLM    = "bedrock_llm"
	extensionNameAzureTTS      = "azure_tts"
	extensionNameCosyTTS       = "cosy_tts"
	extensionNameElevenlabsTTS = "elevenlabs_tts"
	extensionNameOpenaiChatgpt = "openai_chatgpt"
	extensionNamePollyTTS      = "polly_tts"
	extensionNameQwenLLM       = "qwen_llm"

	// Language
	languageChinese = "zh-CN"
	languageEnglish = "en-US"
	// Default graph name
	graphNameDefault = "va.openai.azure"
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
		"AWS_ACCESS_KEY_ID": {
			{ExtensionName: extensionNameBedrockLLM, Property: "access_key"},
			{ExtensionName: extensionNamePollyTTS, Property: "access_key"},
		},
		"AWS_SECRET_ACCESS_KEY": {
			{ExtensionName: extensionNameBedrockLLM, Property: "secret_key"},
			{ExtensionName: extensionNamePollyTTS, Property: "secret_key"},
		},
		"AWS_BEDROCK_MODEL": {
			{ExtensionName: extensionNameBedrockLLM, Property: "model"},
		},
		"AWS_REGION": {
			{ExtensionName: extensionNameBedrockLLM, Property: "region"},
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
		"OPENAI_API_KEY": {
			{ExtensionName: extensionNameOpenaiChatgpt, Property: "api_key"},
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

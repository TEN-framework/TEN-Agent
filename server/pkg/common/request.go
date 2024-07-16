package common

type Language string

const (
	LanguageChinese Language = "zh-CN"
	LanguageEnglish Language = "en-US"
)

type VoiceType string

const (
	VoiceTypeMale   = "male"
	VoiceTypeFemale = "female"
)

type PingReq struct {
	RequestId   string `form:"request_id,omitempty" json:"request_id,omitempty"`
	ChannelName string `form:"channel_name,omitempty" json:"channel_name,omitempty"`
}

type StartReq struct {
	RequestId        string    `form:"request_id,omitempty" json:"request_id,omitempty"`
	AgoraAsrLanguage Language  `form:"agora_asr_language,omitempty" json:"agora_asr_language,omitempty"`
	ChannelName      string    `form:"channel_name,omitempty" json:"channel_name,omitempty"`
	RemoteStreamId   uint32    `form:"remote_stream_id,omitempty" json:"remote_stream_id,omitempty"`
	VoiceType        VoiceType `form:"voice_type,omitempty" json:"voice_type,omitempty"`
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

package common

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

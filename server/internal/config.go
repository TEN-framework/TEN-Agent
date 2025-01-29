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
	extensionNameAgoraRTC   = "agora_rtc"
	extensionNameAgoraRTM   = "agora_rtm"
	extensionNameTSDBFirestore   = "tsdb_firestore"
	extensionNameHttpServer = "http_server"

	// Property json
	PropertyJsonFile = "./agents/property.json"
	// Token expire time
	tokenExpirationInSeconds = uint32(86400)

	WORKER_TIMEOUT_INFINITY = -1

	MAX_GEMINI_WORKER_COUNT = 3
)

var (
	logTag = slog.String("service", "HTTP_SERVER")

	// Retrieve parameters from the request and map them to the property.json file
	startPropMap = map[string][]Prop{
		"ChannelName": {
			{ExtensionName: extensionNameAgoraRTC, Property: "channel"},
			{ExtensionName: extensionNameAgoraRTM, Property: "channel"},
			{ExtensionName: extensionNameTSDBFirestore, Property: "channel_name"},
		},
		"RemoteStreamId": {
			{ExtensionName: extensionNameAgoraRTC, Property: "remote_stream_id"},
		},
		"BotStreamId": {
			{ExtensionName: extensionNameAgoraRTC, Property: "stream_id"},
		},
		"Token": {
			{ExtensionName: extensionNameAgoraRTC, Property: "token"},
			{ExtensionName: extensionNameAgoraRTM, Property: "token"},
		},
		"WorkerHttpServerPort": {
			{ExtensionName: extensionNameHttpServer, Property: "listen_port"},
		},
	}
)

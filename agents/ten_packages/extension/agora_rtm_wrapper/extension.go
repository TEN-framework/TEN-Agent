/**
 *
 * Agora Real Time Engagement
 * Created by Wei Hu in 2022-10.
 * Copyright (c) 2024 Agora IO. All rights reserved.
 *
 */
// Note that this is just an example extension written in the GO programming
// language, so the package name does not equal to the containing directory
// name. However, it is not common in Go.
package extension

import (
	"encoding/json"
	"log/slog"
	"strconv"

	"ten_framework/ten"
)

// Message colllector represents the text output result
// @Description 输出结果
type ColllectorMessage struct {
	Text     string `json:"text"`      // 识别出的文本
	IsFinal  bool   `json:"is_final"`  // 是否为最终结果
	StreamID int32  `json:"stream_id"` // 流ID
	Type     string `json:"data_type"` // 数据类型
	Ts       uint64 `json:"text_ts"`   // 时间戳
}

// Message represents the text output result
// @Description 输出结果
type Message struct {
	Text     string `json:"text"`      // 识别出的文本
	IsFinal  bool   `json:"is_final"`  // 是否为最终结果
	StreamID string `json:"stream_id"` // 流ID
	Type     string `json:"type"`      // 数据类型
	Ts       uint64 `json:"ts"`        // 时间戳
}

// RtcUserSate represents the rtc user state
// @Description RTC用户状态
type RtcUserSate struct {
	RemoteUserID string `json:"remote_user_id"` // 远程用户ID
	State        string `json:"state"`          // 状态
	Reason       string `json:"reason"`         // 原因
}

var (
	logTag = slog.String("extension", "AGORA_RTM_WRAPPER_EXTENSION")
)

type agoraRtmWrapperExtension struct {
	ten.DefaultExtension
}

func newExtension(name string) ten.Extension {
	return &agoraRtmWrapperExtension{}
}

// OnData receives data from ten graph.
func (p *agoraRtmWrapperExtension) OnData(
	tenEnv ten.TenEnv,
	data ten.Data,
) {
	buf, err := data.GetPropertyBytes("data")
	if err != nil {
		slog.Error("OnData GetProperty data error: " + err.Error())
		return
	}
	colllectorMessage := ColllectorMessage{}
	err = json.Unmarshal(buf, &colllectorMessage)
	if err != nil {
		slog.Error("OnData Unmarshal data error: " + err.Error())
		return
	}

	message := Message{
		Text:     colllectorMessage.Text,
		IsFinal:  colllectorMessage.IsFinal,
		StreamID: strconv.Itoa(int(colllectorMessage.StreamID)),
		Type:     colllectorMessage.Type,
		Ts:       colllectorMessage.Ts,
	}
	jsonBytes, err := json.Marshal(message)
	if err != nil {
		slog.Error("failed to marshal JSON: " + err.Error())
		return
	}
	slog.Info("AGORA_RTM_WRAPPER_EXTENSION OnData: "+string(jsonBytes), logTag)

	cmd, _ := ten.NewCmd("publish")

	err = cmd.SetPropertyBytes("message", jsonBytes)
	if err != nil {
		slog.Error("failed to set property message: " + err.Error())
		return
	}
	if err := tenEnv.SendCmd(cmd, func(_ ten.TenEnv, result ten.CmdResult) {
		slog.Info("AGORA_RTM_WRAPPER_EXTENSION publish result " + result.ToJSON())
		status, err := result.GetStatusCode()
		if status != ten.StatusCodeOk || err != nil {
			slog.Error("failed to subscribe ")
		}
	}); err != nil {
		slog.Error("failed to send command " + err.Error())
	}
}

func (p *agoraRtmWrapperExtension) OnCmd(tenEnv ten.TenEnv, cmd ten.Cmd) {
	defer func() {
		if r := recover(); r != nil {
			slog.Error("OnCmd panic", "recover", r)
		}
		cmdResult, err := ten.NewCmdResult(ten.StatusCodeOk)
		if err != nil {
			slog.Error("failed to create cmd result", "err", err)
			return
		}
		tenEnv.ReturnResult(cmdResult, cmd)
	}()
	cmdName, err := cmd.GetName()
	if err != nil {
		slog.Error("failed to get cmd name", "err", err)
		return
	}
	slog.Info(cmd.ToJSON(), logTag)
	switch cmdName {
	case "on_user_audio_track_state_changed":
		// on_user_audio_track_state_changed
		p.handleUserStateChanged(tenEnv, cmd)
	default:
		slog.Warn("unsupported cmd", "cmd", cmdName)
	}
}

func (p *agoraRtmWrapperExtension) handleUserStateChanged(tenEnv ten.TenEnv, cmd ten.Cmd) {
	remoteUserID, err := cmd.GetPropertyString("remote_user_id")
	if err != nil {
		slog.Error("failed to get remote_user_id", "err", err)
		return
	}
	state, err := cmd.GetPropertyInt32("state")
	if err != nil {
		slog.Error("failed to get state", "err", err)
		return
	}
	reason, err := cmd.GetPropertyInt32("reason")
	if err != nil {
		slog.Error("failed to get reason", "err", err)
		return
	}
	userState := RtcUserSate{
		RemoteUserID: remoteUserID,
		State:        strconv.Itoa(int(state)),
		Reason:       strconv.Itoa(int(reason)),
	}
	jsonBytes, err := json.Marshal(userState)
	if err != nil {
		slog.Error("failed to marshal JSON: " + err.Error())
		return
	}
	sendCmd, _ := ten.NewCmd("set_presence_state")
	sendCmd.SetPropertyString("states", string(jsonBytes))
	cmdStr := sendCmd.ToJSON()
	slog.Info("AGORA_RTM_WRAPPER_EXTENSION SetRtmPresenceState " + cmdStr)
	if err := tenEnv.SendCmd(sendCmd, func(_ ten.TenEnv, result ten.CmdResult) {
		slog.Info("AGORA_RTM_WRAPPER_EXTENSION SetRtmPresenceState result " + result.ToJSON())
		status, err := result.GetStatusCode()
		if status != ten.StatusCodeOk || err != nil {
			panic("failed to SetRtmPresenceState ")
		}
	}); err != nil {
		slog.Error("failed to send command " + err.Error())
	}

}

func init() {
	slog.Info("agora_rtm_wrapper extension init", logTag)

	// Register addon
	ten.RegisterAddonAsExtension(
		"agora_rtm_wrapper",
		ten.NewDefaultExtensionAddon(newExtension),
	)
}

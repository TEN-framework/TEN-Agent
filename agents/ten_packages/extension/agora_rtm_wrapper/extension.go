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
	"fmt"
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
		tenEnv.LogError("OnData GetProperty data error: " + err.Error())
		return
	}
	tenEnv.LogInfo("AGORA_RTM_WRAPPER_EXTENSION OnData: " + string(buf))
	colllectorMessage := ColllectorMessage{}
	err = json.Unmarshal(buf, &colllectorMessage)
	if err != nil {
		tenEnv.LogError("OnData Unmarshal data error: " + err.Error())
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
		tenEnv.LogError("failed to marshal JSON: " + err.Error())
		return
	}
	tenEnv.LogInfo("AGORA_RTM_WRAPPER_EXTENSION OnData: " + string(jsonBytes))

	cmd, _ := ten.NewCmd("publish")

	err = cmd.SetPropertyBytes("message", jsonBytes)
	if err != nil {
		tenEnv.LogError("failed to set property message: " + err.Error())
		return
	}
	if err := tenEnv.SendCmd(cmd, func(_ ten.TenEnv, result ten.CmdResult, _ error) {
		status, err := result.GetStatusCode()
		tenEnv.LogInfo(fmt.Sprintf("AGORA_RTM_WRAPPER_EXTENSION publish result %d", status))
		if status != ten.StatusCodeOk || err != nil {
			tenEnv.LogError("failed to subscribe")
		}
	}); err != nil {
		tenEnv.LogError("failed to send command " + err.Error())
	}
}

func (p *agoraRtmWrapperExtension) OnCmd(tenEnv ten.TenEnv, cmd ten.Cmd) {
	defer func() {
		if r := recover(); r != nil {
			tenEnv.LogError(fmt.Sprintf("OnCmd panic: %v", r))
		}
		cmdResult, err := ten.NewCmdResult(ten.StatusCodeOk)
		if err != nil {
			tenEnv.LogError(fmt.Sprintf("failed to create cmd result: %v", err))
			return
		}
		tenEnv.ReturnResult(cmdResult, cmd, nil)
	}()
	cmdName, err := cmd.GetName()
	if err != nil {
		tenEnv.LogError(fmt.Sprintf("failed to get cmd name: %v", err))
		return
	}
	tenEnv.LogInfo(fmt.Sprintf("received command: %s", cmdName))
	switch cmdName {
	case "on_user_audio_track_state_changed":
		// on_user_audio_track_state_changed
		p.handleUserStateChanged(tenEnv, cmd)
	default:
		tenEnv.LogWarn(fmt.Sprintf("unsupported cmd: %s", cmdName))
	}
}

func (p *agoraRtmWrapperExtension) handleUserStateChanged(tenEnv ten.TenEnv, cmd ten.Cmd) {
	remoteUserID, err := cmd.GetPropertyString("remote_user_id")
	if err != nil {
		tenEnv.LogError(fmt.Sprintf("failed to get remote_user_id: %v", err))
		return
	}
	state, err := cmd.GetPropertyInt32("state")
	if err != nil {
		tenEnv.LogError(fmt.Sprintf("failed to get state: %v", err))
		return
	}
	reason, err := cmd.GetPropertyInt32("reason")
	if err != nil {
		tenEnv.LogError(fmt.Sprintf("failed to get reason: %v", err))
		return
	}
	userState := RtcUserSate{
		RemoteUserID: remoteUserID,
		State:        strconv.Itoa(int(state)),
		Reason:       strconv.Itoa(int(reason)),
	}
	jsonBytes, err := json.Marshal(userState)
	if err != nil {
		tenEnv.LogError("failed to marshal JSON: " + err.Error())
		return
	}
	sendCmd, _ := ten.NewCmd("set_presence_state")
	sendCmd.SetPropertyString("states", string(jsonBytes))
	tenEnv.LogInfo("AGORA_RTM_WRAPPER_EXTENSION SetRtmPresenceState " + string(jsonBytes))
	if err := tenEnv.SendCmd(sendCmd, func(_ ten.TenEnv, result ten.CmdResult, _ error) {
		status, err := result.GetStatusCode()
		tenEnv.LogInfo(fmt.Sprintf("AGORA_RTM_WRAPPER_EXTENSION SetRtmPresenceState result %d", status))
		if status != ten.StatusCodeOk || err != nil {
			panic("failed to SetRtmPresenceState")
		}
	}); err != nil {
		tenEnv.LogError("failed to send command " + err.Error())
	}
}

func init() {
	// Register addon
	ten.RegisterAddonAsExtension(
		"agora_rtm_wrapper",
		ten.NewDefaultExtensionAddon(newExtension),
	)
}

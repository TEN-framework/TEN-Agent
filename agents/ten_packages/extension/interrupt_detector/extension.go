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
	"fmt"

	"ten_framework/ten"
)

const (
	textDataTextField  = "text"
	textDataFinalField = "is_final"

	cmdNameFlush = "flush"
)

type interruptDetectorExtension struct {
	ten.DefaultExtension
}

func newExtension(name string) ten.Extension {
	return &interruptDetectorExtension{}
}

// OnData receives data from ten graph.
// current supported data:
//   - name: text_data
//     example:
//     {name: text_data, properties: {text: "hello", is_final: false}
func (p *interruptDetectorExtension) OnData(
	tenEnv ten.TenEnv,
	data ten.Data,
) {
	text, err := data.GetPropertyString(textDataTextField)
	if err != nil {
		tenEnv.LogWarn(fmt.Sprintf("OnData GetProperty %s error: %v", textDataTextField, err))
		return
	}

	final, err := data.GetPropertyBool(textDataFinalField)
	if err != nil {
		tenEnv.LogWarn(fmt.Sprintf("OnData GetProperty %s error: %v", textDataFinalField, err))
		return
	}

	tenEnv.LogDebug(fmt.Sprintf("OnData %s: %s %s: %t", textDataTextField, text, textDataFinalField, final))

	if final || len(text) >= 2 {
		flushCmd, _ := ten.NewCmd(cmdNameFlush)
		tenEnv.SendCmd(flushCmd, nil)

		tenEnv.LogInfo(fmt.Sprintf("sent cmd: %s", cmdNameFlush))
	}
}

func init() {
	// Register addon
	ten.RegisterAddonAsExtension(
		"interrupt_detector",
		ten.NewDefaultExtensionAddon(newExtension),
	)
}

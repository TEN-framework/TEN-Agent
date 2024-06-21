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
	"log/slog"

	"agora.io/rte/rtego"
)

const (
	textDataTextField  = "text"
	textDataFinalField = "is_final"

	cmdNameFlush = "flush"
)

var (
	logTag = slog.String("extension", "INTERRUPT_DETECTOR_EXTENSION")
)

type interruptDetectorExtension struct {
	rtego.DefaultExtension
}

func newExtension(name string) rtego.Extension {
	return &interruptDetectorExtension{}
}

// OnData receives data from rte graph.
// current supported data:
//   - name: text_data
//     example:
//     {name: text_data, properties: {text: "hello", is_final: false}
func (p *interruptDetectorExtension) OnData(
	rte rtego.Rte,
	data rtego.Data,
) {
	text, err := data.GetPropertyString(textDataTextField)
	if err != nil {
		slog.Warn(fmt.Sprintf("OnData GetProperty %s error: %v", textDataTextField, err), logTag)
		return
	}

	final, err := data.GetPropertyBool(textDataFinalField)
	if err != nil {
		slog.Warn(fmt.Sprintf("OnData GetProperty %s error: %v", textDataFinalField, err), logTag)
		return
	}

	slog.Debug(fmt.Sprintf("OnData %s: %s %s: %t", textDataTextField, text, textDataFinalField, final), logTag)

	if final {
		flushCmd, _ := rtego.NewCmd(cmdNameFlush)
		rte.SendCmd(flushCmd, nil)

		slog.Info(fmt.Sprintf("sent cmd: %s", cmdNameFlush), logTag)
	}
}

func init() {
	slog.Info("interrupt_detector extension init", logTag)

	// Register addon
	rtego.RegisterAddonAsExtension(
		"interrupt_detector",
		rtego.NewDefaultExtensionAddon(newExtension),
	)
}

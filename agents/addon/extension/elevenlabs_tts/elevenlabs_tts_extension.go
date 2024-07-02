/**
 *
 * Agora Real Time Engagement
 * Created by XinHui Li in 2024-07.
 * Copyright (c) 2024 Agora IO. All rights reserved.
 *
 */
// Note that this is just an example extension written in the GO programming
// language, so the package name does not equal to the containing directory
// name. However, it is not common in Go.
package extension

import (
	"fmt"
	"io"
	"log/slog"
	"sync"

	"agora.io/rte/rtego"
)

const (
	cmdInFlush                 = "flush"
	cmdOutFlush                = "flush"
	dataInTextDataPropertyText = "text"

	propertyApiKey                = "api_key"                 // Required
	propertyModelId               = "model_id"                // Optional
	propertyRequestTimeoutSeconds = "request_timeout_seconds" // Optional
	propertyVoiceId               = "voice_id"                // Optional
)

const (
	textChanMax = 1024
)

var (
	logTag = slog.String("extension", "ELEVENLABS_TTS_EXTENSION")

	textChan chan string
	wg       sync.WaitGroup
)

type elevenlabsTTSExtension struct {
	rtego.DefaultExtension
	elevenlabsTTS *elevenlabsTTS
}

func newElevenlabsTTSExtension(name string) rtego.Extension {
	return &elevenlabsTTSExtension{}
}

// OnStart will be called when the extension is starting,
// properies can be read here to initialize and start the extension.
// current supported properties:
//   - api_key (required)
//   - model_id
//   - request_timeout_seconds
//   - voice_id
func (e *elevenlabsTTSExtension) OnStart(rte rtego.Rte) {
	slog.Info("OnStart", logTag)

	// prepare configuration
	elevenlabsTTSConfig := defaultElevenlabsTTSConfig()

	if apiKey, err := rte.GetPropertyString(propertyApiKey); err != nil {
		slog.Error(fmt.Sprintf("GetProperty required %s failed, err: %v", propertyApiKey, err), logTag)
		return
	} else {
		elevenlabsTTSConfig.ApiKey = apiKey
	}

	if modelId, err := rte.GetPropertyString(propertyModelId); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyModelId, err), logTag)
	} else {
		if len(modelId) > 0 {
			elevenlabsTTSConfig.ModelId = modelId
		}
	}

	if requestTimeoutSeconds, err := rte.GetPropertyInt64(propertyRequestTimeoutSeconds); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyRequestTimeoutSeconds, err), logTag)
	} else {
		if requestTimeoutSeconds > 0 {
			elevenlabsTTSConfig.RequestTimeoutSeconds = int(requestTimeoutSeconds)
		}
	}

	if voiceId, err := rte.GetPropertyString(propertyVoiceId); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyVoiceId, err), logTag)
	} else {
		if len(voiceId) > 0 {
			elevenlabsTTSConfig.VoiceId = voiceId
		}
	}

	// create elevenlabsTTS instance
	elevenlabsTTS, err := newElevenlabsTTS(elevenlabsTTSConfig)
	if err != nil {
		slog.Error(fmt.Sprintf("newElevenlabsTTS failed, err: %v", err), logTag)
		return
	}

	slog.Info(fmt.Sprintf("newElevenlabsTTS succeed with ModelId: %s, VoiceId: %s",
		elevenlabsTTSConfig.ModelId, elevenlabsTTSConfig.VoiceId), logTag)

	// set elevenlabsTTS instance
	e.elevenlabsTTS = elevenlabsTTS

	// pcm parameters
	sampleRate := int32(16000)
	samplesPer10ms := sampleRate / 100
	channel := int32(1)
	bytesPerSample := int32(2)
	pcmFrameSize := int(samplesPer10ms * channel * bytesPerSample) // per 10ms

	// init chan
	textChan = make(chan string, textChanMax)

	go func() {
		defer func() {
			slog.Info("process textChan quit", logTag)
		}()

		slog.Info("process textChan start", logTag)

		for text := range textChan {
			wg.Add(1)
			slog.Info(fmt.Sprintf("textChan text: [%s]", text), logTag)

			r, w := io.Pipe()

			go func() {
				defer wg.Done()
				defer w.Close()

				slog.Info(fmt.Sprintf("textToSpeechStream text: [%s]", text), logTag)

				err = e.elevenlabsTTS.textToSpeechStream(w, text)
				if err != nil {
					slog.Error(fmt.Sprintf("textToSpeechStream failed, err: %v", err), logTag)
					return
				}
			}()

			slog.Info(fmt.Sprintf("read pcm stream, text: [%s]", text), logTag)

			defer r.Close()

			var n int
			buf := make([]byte, pcmFrameSize)
			for {
				n, err = r.Read(buf)

				slog.Info(fmt.Sprintf("read pcm stream, err: %v, n:%d, pcmFrameSize:%d", err, n, pcmFrameSize), logTag)

				if err == io.EOF {
					break
				}
				if err != nil {
					slog.Error(fmt.Sprintf("read pcm stream failed, err: %v", err), logTag)
					break
				}

				if n != pcmFrameSize {
					slog.Info(fmt.Sprintf("read pcm stream continue, n:%d", n), logTag)
					continue
				}

				pcmFrame, err := rtego.NewPcmFrame("pcm_frame")
				if err != nil {
					slog.Error(fmt.Sprintf("NewPcmFrame failed, err: %v", err), logTag)
					break
				}

				pcmFrame.SetBytesPerSample(bytesPerSample)
				pcmFrame.SetSampleRate(sampleRate)
				pcmFrame.SetChannelLayout(1)
				pcmFrame.SetNumberOfChannels(channel)
				pcmFrame.SetTimestamp(0)
				pcmFrame.SetDataFmt(rtego.PcmFrameDataFmtInterleave)
				pcmFrame.SetSamplesPerChannel(samplesPer10ms)
				pcmFrame.AllocBuf(pcmFrameSize)

				borrowedBuf, err := pcmFrame.BorrowBuf()
				if err != nil {
					slog.Error(fmt.Sprintf("BorrowBuf failed, err: %v", err), logTag)
					break
				}

				// copy data
				copy(borrowedBuf, buf)

				pcmFrame.GiveBackBuf(&borrowedBuf)
				rte.SendPcmFrame(pcmFrame)
				buf = make([]byte, pcmFrameSize)

				slog.Info(fmt.Sprintf("sending pcm data, text: [%s]", text), logTag)
			}

			wg.Wait()
			slog.Info(fmt.Sprintf("send pcm data finished, text: [%s]", text), logTag)
		}
	}()

	rte.OnStartDone()
}

// OnCmd receives cmd from rte graph.
// current supported cmd:
//   - name: flush
//     example:
//     {"name": "flush"}
func (e *elevenlabsTTSExtension) OnCmd(
	rte rtego.Rte,
	cmd rtego.Cmd,
) {
	cmdName, err := cmd.CmdName()
	if err != nil {
		slog.Error(fmt.Sprintf("OnCmd get name failed, err: %v", err), logTag)
		rte.ReturnString(rtego.Error, "error", cmd)
		return
	}

	slog.Info(fmt.Sprintf("OnCmd %s", cmdInFlush), logTag)

	switch cmdName {
	case cmdInFlush:
		// clear chan
		// TODO
		// textChan = make(chan string, cap(textChan))

		// send out
		outCmd, err := rtego.NewCmd(cmdOutFlush)
		if err != nil {
			slog.Error(fmt.Sprintf("new cmd %s failed, err: %v", cmdOutFlush, err), logTag)
			rte.ReturnString(rtego.Error, "error", cmd)
			return
		}

		if err := rte.SendCmd(outCmd, nil); err != nil {
			slog.Error(fmt.Sprintf("send cmd %s failed, err: %v", cmdOutFlush, err), logTag)
			rte.ReturnString(rtego.Error, "error", cmd)
			return
		} else {
			slog.Info(fmt.Sprintf("cmd %s sent", cmdOutFlush), logTag)
		}
	}

	rte.ReturnString(rtego.Ok, "ok", cmd)
}

// OnData receives data from rte graph.
// current supported data:
//   - name: text_data
//     example:
//     {name: text_data, properties: {text: "hello"}
func (e *elevenlabsTTSExtension) OnData(
	rte rtego.Rte,
	data rtego.Data,
) {
	text, err := data.GetPropertyString(dataInTextDataPropertyText)
	if err != nil {
		slog.Warn(fmt.Sprintf("OnData GetProperty %s failed, err: %v", dataInTextDataPropertyText, err), logTag)
		return
	}

	if len(text) == 0 {
		slog.Debug("OnData text is empty, ignored", logTag)
		return
	}

	slog.Info(fmt.Sprintf("OnData input text: [%s]", text), logTag)

	go func() {
		textChan <- text
	}()
}

func init() {
	slog.Info("elevenlabs_tts extension init", logTag)

	// Register addon
	rtego.RegisterAddonAsExtension(
		"elevenlabs_tts",
		rtego.NewDefaultExtensionAddon(newElevenlabsTTSExtension),
	)
}

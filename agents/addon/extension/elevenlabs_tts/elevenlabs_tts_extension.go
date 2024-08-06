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
	"sync/atomic"
	"time"

	"agora.io/rte/rte"
)

const (
	cmdInFlush                 = "flush"
	cmdOutFlush                = "flush"
	dataInTextDataPropertyText = "text"

	propertyApiKey                   = "api_key"                    // Required
	propertyModelId                  = "model_id"                   // Optional
	propertyOptimizeStreamingLatency = "optimize_streaming_latency" // Optional
	propertyRequestTimeoutSeconds    = "request_timeout_seconds"    // Optional
	propertySimilarityBoost          = "similarity_boost"           // Optional
	propertySpeakerBoost             = "speaker_boost"              // Optional
	propertyStability                = "stability"                  // Optional
	propertyStyle                    = "style"                      // Optional
	propertyVoiceId                  = "voice_id"                   // Optional
)

const (
	textChanMax = 1024
)

var (
	logTag = slog.String("extension", "ELEVENLABS_TTS_EXTENSION")

	outdateTs atomic.Int64
	textChan  chan *message
	wg        sync.WaitGroup
)

type elevenlabsTTSExtension struct {
	rte.DefaultExtension
	elevenlabsTTS *elevenlabsTTS
}

type message struct {
	text       string
	receivedTs int64
}

func newElevenlabsTTSExtension(name string) rte.Extension {
	return &elevenlabsTTSExtension{}
}

// OnStart will be called when the extension is starting,
// properies can be read here to initialize and start the extension.
// current supported properties:
//   - api_key (required)
//   - model_id
//   - optimize_streaming_latency
//   - request_timeout_seconds
//   - similarity_boost
//   - speaker_boost
//   - stability
//   - style
//   - voice_id
func (e *elevenlabsTTSExtension) OnStart(rte rte.RteEnv) {
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

	if optimizeStreamingLatency, err := rte.GetPropertyInt64(propertyOptimizeStreamingLatency); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyOptimizeStreamingLatency, err), logTag)
	} else {
		if optimizeStreamingLatency > 0 {
			elevenlabsTTSConfig.OptimizeStreamingLatency = int(optimizeStreamingLatency)
		}
	}

	if requestTimeoutSeconds, err := rte.GetPropertyInt64(propertyRequestTimeoutSeconds); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyRequestTimeoutSeconds, err), logTag)
	} else {
		if requestTimeoutSeconds > 0 {
			elevenlabsTTSConfig.RequestTimeoutSeconds = int(requestTimeoutSeconds)
		}
	}

	if similarityBoost, err := rte.GetPropertyFloat64(propertySimilarityBoost); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertySimilarityBoost, err), logTag)
	} else {
		elevenlabsTTSConfig.SimilarityBoost = float32(similarityBoost)
	}

	if speakerBoost, err := rte.GetPropertyBool(propertySpeakerBoost); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertySpeakerBoost, err), logTag)
	} else {
		elevenlabsTTSConfig.SpeakerBoost = speakerBoost
	}

	if stability, err := rte.GetPropertyFloat64(propertyStability); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyStability, err), logTag)
	} else {
		elevenlabsTTSConfig.Stability = float32(stability)
	}

	if style, err := rte.GetPropertyFloat64(propertyStyle); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyStyle, err), logTag)
	} else {
		elevenlabsTTSConfig.Style = float32(style)
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

	// create pcm instance
	pcm := newPcm(defaultPcmConfig())
	pcmFrameSize := pcm.getPcmFrameSize()

	// init chan
	textChan = make(chan *message, textChanMax)

	go func() {
		slog.Info("process textChan", logTag)

		for msg := range textChan {
			if msg.receivedTs < outdateTs.Load() { // Check whether to interrupt
				slog.Info(fmt.Sprintf("textChan interrupt and flushing for input text: [%s], receivedTs: %d, outdateTs: %d",
					msg.text, msg.receivedTs, outdateTs.Load()), logTag)
				continue
			}

			wg.Add(1)
			slog.Info(fmt.Sprintf("textChan text: [%s]", msg.text), logTag)

			r, w := io.Pipe()
			startTime := time.Now()

			go func() {
				defer wg.Done()
				defer w.Close()

				slog.Info(fmt.Sprintf("textToSpeechStream text: [%s]", msg.text), logTag)

				err = e.elevenlabsTTS.textToSpeechStream(w, msg.text)
				if err != nil {
					slog.Error(fmt.Sprintf("textToSpeechStream failed, err: %v", err), logTag)
					return
				}
			}()

			slog.Info(fmt.Sprintf("read pcm stream, text:[%s], pcmFrameSize:%d", msg.text, pcmFrameSize), logTag)

			var (
				firstFrameLatency int64
				n                 int
				pcmFrameRead      int
				readBytes         int
				sentFrames        int
			)
			buf := pcm.newBuf()

			// read pcm stream
			for {
				if msg.receivedTs < outdateTs.Load() { // Check whether to interrupt
					slog.Info(fmt.Sprintf("read pcm stream interrupt and flushing for input text: [%s], receivedTs: %d, outdateTs: %d",
						msg.text, msg.receivedTs, outdateTs.Load()), logTag)
					break
				}

				n, err = r.Read(buf[pcmFrameRead:])
				readBytes += n
				pcmFrameRead += n

				if err != nil {
					if err == io.EOF {
						slog.Info("read pcm stream EOF", logTag)
						break
					}

					slog.Error(fmt.Sprintf("read pcm stream failed, err: %v", err), logTag)
					break
				}

				if pcmFrameRead != pcmFrameSize {
					slog.Debug(fmt.Sprintf("the number of bytes read is [%d] inconsistent with pcm frame size", pcmFrameRead), logTag)
					continue
				}

				pcm.send(rte, buf)
				// clear buf
				buf = pcm.newBuf()
				pcmFrameRead = 0
				sentFrames++

				if firstFrameLatency == 0 {
					firstFrameLatency = time.Since(startTime).Milliseconds()
					slog.Info(fmt.Sprintf("first frame available for text: [%s], receivedTs: %d, firstFrameLatency: %dms", msg.text, msg.receivedTs, firstFrameLatency), logTag)
				}

				slog.Debug(fmt.Sprintf("sending pcm data, text: [%s]", msg.text), logTag)
			}

			if pcmFrameRead > 0 {
				pcm.send(rte, buf)
				sentFrames++
				slog.Info(fmt.Sprintf("sending pcm remain data, text: [%s], pcmFrameRead: %d", msg.text, pcmFrameRead), logTag)
			}

			r.Close()
			slog.Info(fmt.Sprintf("send pcm data finished, text: [%s], receivedTs: %d, readBytes: %d, sentFrames: %d, firstFrameLatency: %dms, finishLatency: %dms",
				msg.text, msg.receivedTs, readBytes, sentFrames, firstFrameLatency, time.Since(startTime).Milliseconds()), logTag)
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
	rteEnv rte.RteEnv,
	cmd rte.Cmd,
) {
	cmdName, err := cmd.GetName()
	if err != nil {
		slog.Error(fmt.Sprintf("OnCmd get name failed, err: %v", err), logTag)
		cmdResult, _ := rte.NewCmdResult(rte.StatusCodeError)
		rteEnv.ReturnResult(cmdResult, cmd)
		return
	}

	slog.Info(fmt.Sprintf("OnCmd %s", cmdInFlush), logTag)

	switch cmdName {
	case cmdInFlush:
		outdateTs.Store(time.Now().UnixMicro())

		// send out
		outCmd, err := rte.NewCmd(cmdOutFlush)
		if err != nil {
			slog.Error(fmt.Sprintf("new cmd %s failed, err: %v", cmdOutFlush, err), logTag)
			cmdResult, _ := rte.NewCmdResult(rte.StatusCodeError)
			rteEnv.ReturnResult(cmdResult, cmd)
			return
		}

		if err := rteEnv.SendCmd(outCmd, nil); err != nil {
			slog.Error(fmt.Sprintf("send cmd %s failed, err: %v", cmdOutFlush, err), logTag)
			cmdResult, _ := rte.NewCmdResult(rte.StatusCodeError)
			rteEnv.ReturnResult(cmdResult, cmd)
			return
		} else {
			slog.Info(fmt.Sprintf("cmd %s sent", cmdOutFlush), logTag)
		}
	}

	cmdResult, _ := rte.NewCmdResult(rte.StatusCodeOk)
	rteEnv.ReturnResult(cmdResult, cmd)
}

// OnData receives data from rte graph.
// current supported data:
//   - name: text_data
//     example:
//     {name: text_data, properties: {text: "hello"}
func (e *elevenlabsTTSExtension) OnData(
	rteEnv rte.RteEnv,
	data rte.Data,
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
		textChan <- &message{text: text, receivedTs: time.Now().UnixMicro()}
	}()
}

func init() {
	slog.Info("elevenlabs_tts extension init", logTag)

	// Register addon
	rte.RegisterAddonAsExtension(
		"elevenlabs_tts",
		rte.NewDefaultExtensionAddon(newElevenlabsTTSExtension),
	)
}

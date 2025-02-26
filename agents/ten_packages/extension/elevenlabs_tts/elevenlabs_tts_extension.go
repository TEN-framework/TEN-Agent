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
	"sync"
	"sync/atomic"
	"time"

	"ten_framework/ten"
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
	outdateTs atomic.Int64
	textChan  chan *message
	wg        sync.WaitGroup
)

type elevenlabsTTSExtension struct {
	ten.DefaultExtension
	elevenlabsTTS *elevenlabsTTS
}

type message struct {
	text       string
	receivedTs int64
}

func newElevenlabsTTSExtension(name string) ten.Extension {
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
func (e *elevenlabsTTSExtension) OnStart(ten ten.TenEnv) {
	ten.LogInfo("OnStart")

	// prepare configuration
	elevenlabsTTSConfig := defaultElevenlabsTTSConfig()

	if apiKey, err := ten.GetPropertyString(propertyApiKey); err != nil {
		ten.LogError(fmt.Sprintf("GetProperty required %s failed, err: %v", propertyApiKey, err))
		return
	} else {
		elevenlabsTTSConfig.ApiKey = apiKey
	}

	if modelId, err := ten.GetPropertyString(propertyModelId); err != nil {
		ten.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyModelId, err))
	} else {
		if len(modelId) > 0 {
			elevenlabsTTSConfig.ModelId = modelId
		}
	}

	if optimizeStreamingLatency, err := ten.GetPropertyInt64(propertyOptimizeStreamingLatency); err != nil {
		ten.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyOptimizeStreamingLatency, err))
	} else {
		if optimizeStreamingLatency > 0 {
			elevenlabsTTSConfig.OptimizeStreamingLatency = int(optimizeStreamingLatency)
		}
	}

	if requestTimeoutSeconds, err := ten.GetPropertyInt64(propertyRequestTimeoutSeconds); err != nil {
		ten.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyRequestTimeoutSeconds, err))
	} else {
		if requestTimeoutSeconds > 0 {
			elevenlabsTTSConfig.RequestTimeoutSeconds = int(requestTimeoutSeconds)
		}
	}

	if similarityBoost, err := ten.GetPropertyFloat64(propertySimilarityBoost); err != nil {
		ten.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertySimilarityBoost, err))
	} else {
		elevenlabsTTSConfig.SimilarityBoost = float32(similarityBoost)
	}

	if speakerBoost, err := ten.GetPropertyBool(propertySpeakerBoost); err != nil {
		ten.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertySpeakerBoost, err))
	} else {
		elevenlabsTTSConfig.SpeakerBoost = speakerBoost
	}

	if stability, err := ten.GetPropertyFloat64(propertyStability); err != nil {
		ten.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyStability, err))
	} else {
		elevenlabsTTSConfig.Stability = float32(stability)
	}

	if style, err := ten.GetPropertyFloat64(propertyStyle); err != nil {
		ten.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyStyle, err))
	} else {
		elevenlabsTTSConfig.Style = float32(style)
	}

	if voiceId, err := ten.GetPropertyString(propertyVoiceId); err != nil {
		ten.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyVoiceId, err))
	} else {
		if len(voiceId) > 0 {
			elevenlabsTTSConfig.VoiceId = voiceId
		}
	}

	// create elevenlabsTTS instance
	elevenlabsTTS, err := newElevenlabsTTS(elevenlabsTTSConfig)
	if err != nil {
		ten.LogError(fmt.Sprintf("newElevenlabsTTS failed, err: %v", err))
		return
	}

	ten.LogInfo(fmt.Sprintf("newElevenlabsTTS succeed with ModelId: %s, VoiceId: %s",
		elevenlabsTTSConfig.ModelId, elevenlabsTTSConfig.VoiceId))

	// set elevenlabsTTS instance
	e.elevenlabsTTS = elevenlabsTTS

	// create pcm instance
	pcm := newPcm(defaultPcmConfig())
	pcmFrameSize := pcm.getPcmFrameSize()

	// init chan
	textChan = make(chan *message, textChanMax)

	go func() {
		ten.LogInfo("process textChan")

		for msg := range textChan {
			if msg.receivedTs < outdateTs.Load() { // Check whether to interrupt
				ten.LogInfo(fmt.Sprintf("textChan interrupt and flushing for input text: [%s], receivedTs: %d, outdateTs: %d",
					msg.text, msg.receivedTs, outdateTs.Load()))
				continue
			}

			wg.Add(1)
			ten.LogInfo(fmt.Sprintf("textChan text: [%s]", msg.text))

			r, w := io.Pipe()
			startTime := time.Now()

			go func() {
				defer wg.Done()
				defer w.Close()

				ten.LogInfo(fmt.Sprintf("textToSpeechStream text: [%s]", msg.text))

				err = e.elevenlabsTTS.textToSpeechStream(w, msg.text)
				if err != nil {
					ten.LogError(fmt.Sprintf("textToSpeechStream failed, err: %v", err))
					return
				}
			}()

			ten.LogInfo(fmt.Sprintf("read pcm stream, text:[%s], pcmFrameSize:%d", msg.text, pcmFrameSize))

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
					ten.LogInfo(fmt.Sprintf("read pcm stream interrupt and flushing for input text: [%s], receivedTs: %d, outdateTs: %d",
						msg.text, msg.receivedTs, outdateTs.Load()))
					break
				}

				n, err = r.Read(buf[pcmFrameRead:])
				readBytes += n
				pcmFrameRead += n

				if err != nil {
					if err == io.EOF {
						ten.LogInfo("read pcm stream EOF")
						break
					}

					ten.LogError(fmt.Sprintf("read pcm stream failed, err: %v", err))
					break
				}

				if pcmFrameRead != pcmFrameSize {
					ten.LogDebug(fmt.Sprintf("the number of bytes read is [%d] inconsistent with pcm frame size", pcmFrameRead))
					continue
				}

				pcm.send(ten, buf)
				// clear buf
				buf = pcm.newBuf()
				pcmFrameRead = 0
				sentFrames++

				if firstFrameLatency == 0 {
					firstFrameLatency = time.Since(startTime).Milliseconds()
					ten.LogInfo(fmt.Sprintf("first frame available for text: [%s], receivedTs: %d, firstFrameLatency: %dms", msg.text, msg.receivedTs, firstFrameLatency))
				}

				ten.LogDebug(fmt.Sprintf("sending pcm data, text: [%s]", msg.text))
			}

			if pcmFrameRead > 0 {
				pcm.send(ten, buf)
				sentFrames++
				ten.LogInfo(fmt.Sprintf("sending pcm remain data, text: [%s], pcmFrameRead: %d", msg.text, pcmFrameRead))
			}

			r.Close()
			ten.LogInfo(fmt.Sprintf("send pcm data finished, text: [%s], receivedTs: %d, readBytes: %d, sentFrames: %d, firstFrameLatency: %dms, finishLatency: %dms",
				msg.text, msg.receivedTs, readBytes, sentFrames, firstFrameLatency, time.Since(startTime).Milliseconds()))
		}
	}()

	ten.OnStartDone()
}

// OnCmd receives cmd from ten graph.
// current supported cmd:
//   - name: flush
//     example:
//     {"name": "flush"}
func (e *elevenlabsTTSExtension) OnCmd(
	tenEnv ten.TenEnv,
	cmd ten.Cmd,
) {
	cmdName, err := cmd.GetName()
	if err != nil {
		tenEnv.LogError(fmt.Sprintf("OnCmd get name failed, err: %v", err))
		cmdResult, _ := ten.NewCmdResult(ten.StatusCodeError)
		tenEnv.ReturnResult(cmdResult, cmd, nil)
		return
	}

	tenEnv.LogInfo(fmt.Sprintf("OnCmd %s", cmdInFlush))

	switch cmdName {
	case cmdInFlush:
		outdateTs.Store(time.Now().UnixMicro())

		// send out
		outCmd, err := ten.NewCmd(cmdOutFlush)
		if err != nil {
			tenEnv.LogError(fmt.Sprintf("new cmd %s failed, err: %v", cmdOutFlush, err))
			cmdResult, _ := ten.NewCmdResult(ten.StatusCodeError)
			tenEnv.ReturnResult(cmdResult, cmd, nil)
			return
		}

		if err := tenEnv.SendCmd(outCmd, nil); err != nil {
			tenEnv.LogError(fmt.Sprintf("send cmd %s failed, err: %v", cmdOutFlush, err))
			cmdResult, _ := ten.NewCmdResult(ten.StatusCodeError)
			tenEnv.ReturnResult(cmdResult, cmd, nil)
			return
		} else {
			tenEnv.LogInfo(fmt.Sprintf("cmd %s sent", cmdOutFlush))
		}
	}

	cmdResult, _ := ten.NewCmdResult(ten.StatusCodeOk)
	tenEnv.ReturnResult(cmdResult, cmd, nil)
}

// OnData receives data from ten graph.
// current supported data:
//   - name: text_data
//     example:
//     {name: text_data, properties: {text: "hello"}
func (e *elevenlabsTTSExtension) OnData(
	tenEnv ten.TenEnv,
	data ten.Data,
) {
	text, err := data.GetPropertyString(dataInTextDataPropertyText)
	if err != nil {
		tenEnv.LogWarn(fmt.Sprintf("OnData GetProperty %s failed, err: %v", dataInTextDataPropertyText, err))
		return
	}

	if len(text) == 0 {
		tenEnv.LogDebug("OnData text is empty, ignored")
		return
	}

	tenEnv.LogInfo(fmt.Sprintf("OnData input text: [%s]", text))

	go func() {
		textChan <- &message{text: text, receivedTs: time.Now().UnixMicro()}
	}()
}

func init() {
	// Register addon
	ten.RegisterAddonAsExtension(
		"elevenlabs_tts",
		ten.NewDefaultExtensionAddon(newElevenlabsTTSExtension),
	)
}

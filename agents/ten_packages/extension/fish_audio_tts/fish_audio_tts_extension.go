/**
 *
 * Agora Real Time Engagement
 * Created by Hai Guo in 2024-08.
 * Copyright (c) 2024 Agora IO. All rights reserved.
 *
 */
// An extension written by Go for TTS
package extension

import (
	"fmt"
	"io"
	"log/slog"
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
	logTag = slog.String("extension", "FISH_AUDIO_TTS_EXTENSION")

	outdateTs atomic.Int64
	textChan  chan *message
	wg        sync.WaitGroup
)

type fishAudioTTSExtension struct {
	ten.DefaultExtension
	fishAudioTTS *fishAudioTTS
}

type message struct {
	text       string
	receivedTs int64
}

func newFishAudioTTSExtension(name string) ten.Extension {
	return &fishAudioTTSExtension{}
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
func (e *fishAudioTTSExtension) OnStart(ten ten.TenEnv) {
	slog.Info("OnStart", logTag)

	// prepare configuration
	fishAudioTTSConfig := defaultFishAudioTTSConfig()

	if apiKey, err := ten.GetPropertyString(propertyApiKey); err != nil {
		slog.Error(fmt.Sprintf("GetProperty required %s failed, err: %v", propertyApiKey, err), logTag)
		return
	} else {
		fishAudioTTSConfig.ApiKey = apiKey
	}

	if modelId, err := ten.GetPropertyString(propertyModelId); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyModelId, err), logTag)
	} else {
		if len(modelId) > 0 {
			fishAudioTTSConfig.ModelId = modelId
		}
	}

	if optimizeStreamingLatency, err := ten.GetPropertyInt64(propertyOptimizeStreamingLatency); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyOptimizeStreamingLatency, err), logTag)
	} else {
		if optimizeStreamingLatency > 0 {
			fishAudioTTSConfig.OptimizeStreamingLatency = int(optimizeStreamingLatency)
		}
	}

	if requestTimeoutSeconds, err := ten.GetPropertyInt64(propertyRequestTimeoutSeconds); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyRequestTimeoutSeconds, err), logTag)
	} else {
		if requestTimeoutSeconds > 0 {
			fishAudioTTSConfig.RequestTimeoutSeconds = int(requestTimeoutSeconds)
		}
	}

	if similarityBoost, err := ten.GetPropertyFloat64(propertySimilarityBoost); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertySimilarityBoost, err), logTag)
	} else {
		fishAudioTTSConfig.SimilarityBoost = float32(similarityBoost)
	}

	if speakerBoost, err := ten.GetPropertyBool(propertySpeakerBoost); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertySpeakerBoost, err), logTag)
	} else {
		fishAudioTTSConfig.SpeakerBoost = speakerBoost
	}

	if stability, err := ten.GetPropertyFloat64(propertyStability); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyStability, err), logTag)
	} else {
		fishAudioTTSConfig.Stability = float32(stability)
	}

	if style, err := ten.GetPropertyFloat64(propertyStyle); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyStyle, err), logTag)
	} else {
		fishAudioTTSConfig.Style = float32(style)
	}

	if voiceId, err := ten.GetPropertyString(propertyVoiceId); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyVoiceId, err), logTag)
	} else {
		if len(voiceId) > 0 {
			fishAudioTTSConfig.VoiceId = voiceId
		}
	}

	// create fishAudioTTS instance
	fishAudioTTS, err := newFishAudioTTS(fishAudioTTSConfig)
	if err != nil {
		slog.Error(fmt.Sprintf("newFishAudioTTS failed, err: %v", err), logTag)
		return
	}

	slog.Info(fmt.Sprintf("newFishAudioTTS succeed with ModelId: %s, VoiceId: %s",
	fishAudioTTSConfig.ModelId, fishAudioTTSConfig.VoiceId), logTag)

	// set fishAudio instance
	e.fishAudioTTS = fishAudioTTS

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
				err = e.fishAudioTTS.textToSpeechStream(w, msg.text)
				slog.Info(fmt.Sprintf("textToSpeechStream result: [%v]", err), logTag)
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

				pcm.send(ten, buf)
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
				pcm.send(ten, buf)
				sentFrames++
				slog.Info(fmt.Sprintf("sending pcm remain data, text: [%s], pcmFrameRead: %d", msg.text, pcmFrameRead), logTag)
			}

			r.Close()
			slog.Info(fmt.Sprintf("send pcm data finished, text: [%s], receivedTs: %d, readBytes: %d, sentFrames: %d, firstFrameLatency: %dms, finishLatency: %dms",
				msg.text, msg.receivedTs, readBytes, sentFrames, firstFrameLatency, time.Since(startTime).Milliseconds()), logTag)
		}
	}()

	ten.OnStartDone()
}

// OnCmd receives cmd from ten graph.
// current supported cmd:
//   - name: flush
//     example:
//     {"name": "flush"}
func (e *fishAudioTTSExtension) OnCmd(
	tenEnv ten.TenEnv,
	cmd ten.Cmd,
) {
	cmdName, err := cmd.GetName()
	if err != nil {
		slog.Error(fmt.Sprintf("OnCmd get name failed, err: %v", err), logTag)
		cmdResult, _ := ten.NewCmdResult(ten.StatusCodeError)
		tenEnv.ReturnResult(cmdResult, cmd)
		return
	}

	slog.Info(fmt.Sprintf("OnCmd %s", cmdInFlush), logTag)

	switch cmdName {
	case cmdInFlush:
		outdateTs.Store(time.Now().UnixMicro())

		// send out
		outCmd, err := ten.NewCmd(cmdOutFlush)
		if err != nil {
			slog.Error(fmt.Sprintf("new cmd %s failed, err: %v", cmdOutFlush, err), logTag)
			cmdResult, _ := ten.NewCmdResult(ten.StatusCodeError)
			tenEnv.ReturnResult(cmdResult, cmd)
			return
		}

		if err := tenEnv.SendCmd(outCmd, nil); err != nil {
			slog.Error(fmt.Sprintf("send cmd %s failed, err: %v", cmdOutFlush, err), logTag)
			cmdResult, _ := ten.NewCmdResult(ten.StatusCodeError)
			tenEnv.ReturnResult(cmdResult, cmd)
			return
		} else {
			slog.Info(fmt.Sprintf("cmd %s sent", cmdOutFlush), logTag)
		}
	}

	cmdResult, _ := ten.NewCmdResult(ten.StatusCodeOk)
	tenEnv.ReturnResult(cmdResult, cmd)
}

// OnData receives data from ten graph.
// current supported data:
//   - name: text_data
//     example:
//     {name: text_data, properties: {text: "hello"}
func (e *fishAudioTTSExtension) OnData(
	tenEnv ten.TenEnv,
	data ten.Data,
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
	slog.Info("fish_audio_tts extension init", logTag)

	// Register addon
	ten.RegisterAddonAsExtension(
		"fish_audio_tts",
		ten.NewDefaultExtensionAddon(newFishAudioTTSExtension),
	)
}

/**
 *
 * Agora Real Time Engagement
 * Created by XinHui Li in 2024.
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

	propertyApiKey                = "api_key"                 // Required
	propertyGroupId               = "group_id"                // Required
	propertyModel                 = "model"                   // Optional
	propertyRequestTimeoutSeconds = "request_timeout_seconds" // Optional
	propertySampleRate            = "sample_rate"             // Optional
	propertyUrl                   = "url"                     // Optional
	propertyVoiceId               = "voice_id"                // Optional
)

const (
	textChanMax = 1024
)

var (
	logTag = slog.String("extension", "MINIMAX_TTS_EXTENSION")

	outdateTs atomic.Int64
	textChan  chan *message
	wg        sync.WaitGroup
)

type minimaxTTSExtension struct {
	ten.DefaultExtension
	minimaxTTS *minimaxTTS
}

type message struct {
	text       string
	receivedTs int64
}

func newMinimaxTTSExtension(name string) ten.Extension {
	return &minimaxTTSExtension{}
}

// OnStart will be called when the extension is starting,
// properies can be read here to initialize and start the extension.
// current supported properties:
//   - api_key (required)
//   - group_id (required)
//   - model
//   - request_timeout_seconds
//   - sample_rate
//   - url
//   - voice_id
func (e *minimaxTTSExtension) OnStart(ten ten.TenEnv) {
	slog.Info("OnStart", logTag)

	// prepare configuration
	minimaxTTSConfig := defaultMinimaxTTSConfig()

	if apiKey, err := ten.GetPropertyString(propertyApiKey); err != nil {
		slog.Error(fmt.Sprintf("GetProperty required %s failed, err: %v", propertyApiKey, err), logTag)
		return
	} else {
		minimaxTTSConfig.ApiKey = apiKey
	}

	if groupId, err := ten.GetPropertyString(propertyGroupId); err != nil {
		slog.Error(fmt.Sprintf("GetProperty required %s failed, err: %v", propertyGroupId, err), logTag)
		return
	} else {
		minimaxTTSConfig.GroupId = groupId
	}

	if model, err := ten.GetPropertyString(propertyModel); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyModel, err), logTag)
	} else {
		if len(model) > 0 {
			minimaxTTSConfig.Model = model
		}
	}

	if requestTimeoutSeconds, err := ten.GetPropertyInt64(propertyRequestTimeoutSeconds); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyRequestTimeoutSeconds, err), logTag)
	} else {
		if requestTimeoutSeconds > 0 {
			minimaxTTSConfig.RequestTimeoutSeconds = int(requestTimeoutSeconds)
		}
	}

	if sampleRate, err := ten.GetPropertyInt64(propertySampleRate); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertySampleRate, err), logTag)
	} else {
		if sampleRate > 0 {
			minimaxTTSConfig.SampleRate = int32(sampleRate)
		}
	}

	if url, err := ten.GetPropertyString(propertyUrl); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyUrl, err), logTag)
	} else {
		if len(url) > 0 {
			minimaxTTSConfig.Url = url
		}
	}

	if voiceId, err := ten.GetPropertyString(propertyVoiceId); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyVoiceId, err), logTag)
	} else {
		minimaxTTSConfig.VoiceId = voiceId
	}

	// create minimaxTTS instance
	minimaxTTS, err := newMinimaxTTS(minimaxTTSConfig)
	if err != nil {
		slog.Error(fmt.Sprintf("newMinimaxTTS failed, err: %v", err), logTag)
		return
	}

	slog.Info(fmt.Sprintf("newMinimaxTTS succeed with Model: %s", minimaxTTSConfig.Model), logTag)

	// set minimaxTTS instance
	e.minimaxTTS = minimaxTTS

	// create pcm instance
	pcmConfig := defaultPcmConfig()
	pcmConfig.SampleRate = minimaxTTSConfig.SampleRate
	pcmConfig.SamplesPerChannel = minimaxTTSConfig.SampleRate / 100
	pcm := newPcm(pcmConfig)
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
				err = e.minimaxTTS.textToSpeechStream(w, msg.text)
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
func (e *minimaxTTSExtension) OnCmd(
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
func (e *minimaxTTSExtension) OnData(
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
	slog.Info("minimax_tts extension init", logTag)

	// Register addon
	ten.RegisterAddonAsExtension(
		"minimax_tts",
		ten.NewDefaultExtensionAddon(newMinimaxTTSExtension),
	)
}

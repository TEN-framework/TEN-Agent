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
	ten.LogInfo("OnStart")

	// prepare configuration
	minimaxTTSConfig := defaultMinimaxTTSConfig()

	if apiKey, err := ten.GetPropertyString(propertyApiKey); err != nil {
		ten.LogError(fmt.Sprintf("GetProperty required %s failed, err: %v", propertyApiKey, err))
		return
	} else {
		minimaxTTSConfig.ApiKey = apiKey
	}

	if groupId, err := ten.GetPropertyString(propertyGroupId); err != nil {
		ten.LogError(fmt.Sprintf("GetProperty required %s failed, err: %v", propertyGroupId, err))
		return
	} else {
		minimaxTTSConfig.GroupId = groupId
	}

	if model, err := ten.GetPropertyString(propertyModel); err != nil {
		ten.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyModel, err))
	} else {
		if len(model) > 0 {
			minimaxTTSConfig.Model = model
		}
	}

	if requestTimeoutSeconds, err := ten.GetPropertyInt64(propertyRequestTimeoutSeconds); err != nil {
		ten.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyRequestTimeoutSeconds, err))
	} else {
		if requestTimeoutSeconds > 0 {
			minimaxTTSConfig.RequestTimeoutSeconds = int(requestTimeoutSeconds)
		}
	}

	if sampleRate, err := ten.GetPropertyInt64(propertySampleRate); err != nil {
		ten.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertySampleRate, err))
	} else {
		if sampleRate > 0 {
			minimaxTTSConfig.SampleRate = int32(sampleRate)
		}
	}

	if url, err := ten.GetPropertyString(propertyUrl); err != nil {
		ten.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyUrl, err))
	} else {
		if len(url) > 0 {
			minimaxTTSConfig.Url = url
		}
	}

	if voiceId, err := ten.GetPropertyString(propertyVoiceId); err != nil {
		ten.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyVoiceId, err))
	} else {
		minimaxTTSConfig.VoiceId = voiceId
	}

	// create minimaxTTS instance
	minimaxTTS, err := newMinimaxTTS(minimaxTTSConfig)
	if err != nil {
		ten.LogError(fmt.Sprintf("newMinimaxTTS failed, err: %v", err))
		return
	}

	ten.LogInfo(fmt.Sprintf("newMinimaxTTS succeed with Model: %s", minimaxTTSConfig.Model))

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
				err = e.minimaxTTS.textToSpeechStream(ten, w, msg.text)
				ten.LogInfo(fmt.Sprintf("textToSpeechStream result: [%v]", err))
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
func (e *minimaxTTSExtension) OnCmd(
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
func (e *minimaxTTSExtension) OnData(
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
		"minimax_tts",
		ten.NewDefaultExtensionAddon(newMinimaxTTSExtension),
	)
}

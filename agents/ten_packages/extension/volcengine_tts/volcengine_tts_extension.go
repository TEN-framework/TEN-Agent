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
	"sync"
	"sync/atomic"
	"time"

	"ten_framework/ten"
)

const (
	cmdInFlush                 = "flush"
	cmdOutFlush                = "flush"
	dataInTextDataPropertyText = "text"

	propertyAppId                 = "app_id"                  // Required
	propertyToken                 = "token"                   // Required
	propertyCluster               = "cluster"                 // Required
	propertyTimbre                = "timbre"                  // Required
	propertySampleRate            = "sample_rate"             // Required
	propertySpeedRatio            = "speed_ratio"             // Optional
	propertyVolumnRatio           = "volume_ratio"            // Optional
	propertyPitchRatio            = "pitch_ratio"             // Optional
	propertyRequestTimeoutSeconds = "request_timeout_seconds" // Optional
)

const (
	textChanMax = 1024
)

var (
	outdateTs atomic.Int64
	textChan  chan *message
	wg        sync.WaitGroup
)

type volcengineTTSExtension struct {
	ten.DefaultExtension
	volcengineTTS *volcengineTTS
}

type message struct {
	text       string
	receivedTs int64
}

func newVolcengineTTSExtension(name string) ten.Extension {
	return &volcengineTTSExtension{}
}

// OnStart will be called when the extension is starting,
// properies can be read here to initialize and start the extension.
// current supported properties:
//   - api_key (required)
//   - model_id
//   - optimize_streaming_latency
//   - request_timeout_seconds
//   - base_url
func (e *volcengineTTSExtension) OnStart(ten ten.TenEnv) {
	ten.LogInfo("OnStart")

	// prepare configuration
	volcengineTTSConfig := defaultVolcengineTTSConfig()

	if appID, err := ten.GetPropertyString(propertyAppId); err != nil {
		ten.LogError(fmt.Sprintf("GetProperty required %s failed, err: %v", propertyAppId, err))
		return
	} else {
		if len(appID) > 0 {
			volcengineTTSConfig.AppID = appID
		}
	}

	if token, err := ten.GetPropertyString(propertyToken); err != nil {
		ten.LogError(fmt.Sprintf("GetProperty required %s failed, err: %v", propertyToken, err))
	} else {
		if len(token) > 0 {
			volcengineTTSConfig.Token = token
		}
	}

	if cluster, err := ten.GetPropertyString(propertyCluster); err != nil {
		ten.LogError(fmt.Sprintf("GetProperty required %s failed, err: %v", propertyCluster, err))
	} else {
		if len(cluster) > 0 {
			volcengineTTSConfig.Cluster = cluster
		}
	}

	if timbre, err := ten.GetPropertyString(propertyTimbre); err != nil {
		ten.LogError(fmt.Sprintf("GetProperty required %s failed, err: %v", propertyTimbre, err))
	} else {
		if len(timbre) > 0 {
			volcengineTTSConfig.Timbre = timbre
		}
	}

	if sampleRate, err := ten.GetPropertyInt32(propertySampleRate); err != nil {
		ten.LogError(fmt.Sprintf("GetProperty required %s failed, err: %v", propertySampleRate, err))
	} else {
		if sampleRate != 8000 && sampleRate != 16000 && sampleRate != 24000 {
			ten.LogError(fmt.Sprintf("GetProperty required %s invalid value %d", propertySampleRate, sampleRate))
		} else {
			volcengineTTSConfig.SampleRate = sampleRate
		}
	}

	if speedRatio, err := ten.GetPropertyFloat64(propertySpeedRatio); err != nil {
		ten.LogError(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertySpeedRatio, err))
	} else {
		if speedRatio >= 0.2 && speedRatio <= 3 {
			volcengineTTSConfig.SpeedRatio = float32(speedRatio)
		}
	}

	if volumnRatio, err := ten.GetPropertyFloat64(propertyVolumnRatio); err != nil {
		ten.LogError(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyVolumnRatio, err))
	} else {
		if volumnRatio >= 0.1 && volumnRatio <= 3 {
			volcengineTTSConfig.VolumnRatio = float32(volumnRatio)
		}
	}

	if pitchRatio, err := ten.GetPropertyFloat64(propertyPitchRatio); err != nil {
		ten.LogError(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyPitchRatio, err))
	} else {
		if pitchRatio >= 0.1 && pitchRatio <= 3 {
			volcengineTTSConfig.PitchRatio = float32(pitchRatio)
		}
	}

	if requestTimeoutSeconds, err := ten.GetPropertyInt64(propertyRequestTimeoutSeconds); err != nil {
		ten.LogError(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyRequestTimeoutSeconds, err))
	} else {
		if requestTimeoutSeconds > 0 {
			volcengineTTSConfig.RequestTimeoutSeconds = int(requestTimeoutSeconds)
		}
	}
	ten.LogInfo(fmt.Sprintf("volcengineTTSConfig: %v", volcengineTTSConfig))
	// create volcengineTTS instance
	volcengineTTS, err := newVolcengineTTS(volcengineTTSConfig)
	if err != nil {
		ten.LogError(fmt.Sprintf("newVolcengineTTS failed, err: %v", err))
		return
	}

	ten.LogInfo(fmt.Sprintf("newVolcengineTTS succeed with token: %s",
		volcengineTTSConfig.Token))

	// set volcengine instance
	e.volcengineTTS = volcengineTTS

	// create pcm instance
	pcmConfig := defaultPcmConfig()
	pcmConfig.SampleRate = volcengineTTSConfig.SampleRate
	pcmConfig.SamplesPerChannel = volcengineTTSConfig.SampleRate / 100
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
				err = e.volcengineTTS.textToSpeechStream(ten, w, msg.text)
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
func (e *volcengineTTSExtension) OnCmd(
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
func (e *volcengineTTSExtension) OnData(
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
		"volcengine_tts",
		ten.NewDefaultExtensionAddon(newVolcengineTTSExtension),
	)
}

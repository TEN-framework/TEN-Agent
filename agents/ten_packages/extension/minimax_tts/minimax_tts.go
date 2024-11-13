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
	"bufio"
	"bytes"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"time"

	"github.com/go-resty/resty/v2"
)

type minimaxTTS struct {
	client *resty.Client
	config minimaxTTSConfig
}

type minimaxTTSConfig struct {
	ApiKey                string
	GroupId               string
	Model                 string
	RequestTimeoutSeconds int
	SampleRate            int32
	Url                   string
	VoiceId               string
}

func defaultMinimaxTTSConfig() minimaxTTSConfig {
	return minimaxTTSConfig{
		ApiKey:                "",
		GroupId:               "",
		Model:                 "speech-01-turbo",
		RequestTimeoutSeconds: 10,
		SampleRate:            32000,
		Url:                   "https://api.minimax.chat/v1/t2a_v2",
		VoiceId:               "male-qn-qingse",
	}
}

func newMinimaxTTS(config minimaxTTSConfig) (*minimaxTTS, error) {
	return &minimaxTTS{
		config: config,
		client: resty.New().
			SetRetryCount(0).
			SetTimeout(time.Duration(config.RequestTimeoutSeconds) * time.Second),
	}, nil
}

func (e *minimaxTTS) textToSpeechStream(streamWriter io.Writer, text string) (err error) {
	slog.Debug("textToSpeechStream start tts", "text", text)

	payload := map[string]any{
		"audio_setting": map[string]any{
			"channel":     1,
			"format":      "pcm",
			"sample_rate": e.config.SampleRate,
		},
		"model": e.config.Model,
		"pronunciation_dict": map[string]any{
			"tone": []string{},
		},
		"stream": true,
		"text":   text,
		"voice_setting": map[string]any{
			"pitch":    0,
			"speed":    1.0,
			"voice_id": e.config.VoiceId,
			"vol":      1.0,
		},
	}

	resp, err := e.client.R().
		SetHeader("Content-Type", "application/json").
		SetHeader("Authorization", "Bearer "+e.config.ApiKey).
		SetDoNotParseResponse(true).
		SetBody(payload).
		Post(fmt.Sprintf("%s?GroupId=%s", e.config.Url, e.config.GroupId))

	if err != nil {
		slog.Error("request failed", "err", err, "text", text)
		return fmt.Errorf("textToSpeechStream failed, err: %v", err)
	}

	defer func() {
		resp.RawBody().Close()

		slog.Debug("textToSpeechStream close response", "err", err, "text", text)
	}()

	// Check the response status code
	if resp.StatusCode() != http.StatusOK {
		slog.Error("unexpected response status", "status", resp.StatusCode())
		return fmt.Errorf("unexpected response status: %d", resp.StatusCode())
	}

	reader := bufio.NewReader(resp.RawBody())
	for {
		line, err := reader.ReadBytes('\n')
		if err != nil {
			if err == io.EOF {
				break
			}

			slog.Error("failed to read line", "error", err)
			return err
		}

		if !bytes.HasPrefix(line, []byte("data:")) {
			slog.Debug("drop chunk", "text", text, "line", line)
			continue
		}

		var chunk struct {
			Data struct {
				Audio  string `json:"audio"`
				Status int    `json:"status"`
			} `json:"data"`
			TraceId  string `json:"trace_id"`
			BaseResp struct {
				StatusCode int    `json:"status_code"`
				StatusMsg  string `json:"status_msg"`
			} `json:"base_resp"`
		}

		if err = json.Unmarshal(line[5:], &chunk); err != nil {
			slog.Error("failed to decode JSON chunk", "err", err)
			break
		}

		if chunk.Data.Status == 2 {
			break
		}

		audioData, err := hex.DecodeString(chunk.Data.Audio)
		if err != nil {
			slog.Error("failed to decode audio data", "err", err, "traceId", chunk.TraceId, "BaseResp", chunk.BaseResp)
			break
		}

		_, err = streamWriter.Write(audioData)
		if err != nil {
			slog.Error("failed to write to streamWriter", "err", err, "traceId", chunk.TraceId, "BaseResp", chunk.BaseResp)
			break
		}
	}

	return
}

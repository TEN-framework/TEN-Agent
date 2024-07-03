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
	"context"
	"fmt"
	"io"
	"time"

	elevenlabs "github.com/haguro/elevenlabs-go"
)

type elevenlabsTTS struct {
	client *elevenlabs.Client
	config elevenlabsTTSConfig
}

type elevenlabsTTSConfig struct {
	ApiKey                   string
	ModelId                  string
	OptimizeStreamingLatency int
	RequestTimeoutSeconds    int
	SimilarityBoost          float32
	SpeakerBoost             bool
	Stability                float32
	Style                    float32
	VoiceId                  string
}

func defaultElevenlabsTTSConfig() elevenlabsTTSConfig {
	return elevenlabsTTSConfig{
		ApiKey:                   "",
		ModelId:                  "eleven_multilingual_v2",
		OptimizeStreamingLatency: 0.0,
		RequestTimeoutSeconds:    30,
		SimilarityBoost:          0.75,
		SpeakerBoost:             false,
		Stability:                0.5,
		Style:                    0.0,
		VoiceId:                  "pNInz6obpgDQGcFmaJgB",
	}
}

func newElevenlabsTTS(config elevenlabsTTSConfig) (*elevenlabsTTS, error) {
	return &elevenlabsTTS{
		config: config,
		client: elevenlabs.NewClient(context.Background(), config.ApiKey, time.Duration(config.RequestTimeoutSeconds)*time.Second),
	}, nil
}

func (e *elevenlabsTTS) textToSpeechStream(streamWriter io.Writer, text string) (err error) {
	req := elevenlabs.TextToSpeechRequest{
		Text:    text,
		ModelID: e.config.ModelId,
		VoiceSettings: &elevenlabs.VoiceSettings{
			SimilarityBoost: e.config.SimilarityBoost,
			SpeakerBoost:    e.config.SpeakerBoost,
			Stability:       e.config.Stability,
			Style:           e.config.Style,
		},
	}
	queries := []elevenlabs.QueryFunc{
		elevenlabs.LatencyOptimizations(e.config.OptimizeStreamingLatency),
		elevenlabs.OutputFormat("pcm_16000"),
	}

	err = e.client.TextToSpeechStream(streamWriter, e.config.VoiceId, req, queries...)
	if err != nil {
		return fmt.Errorf("TextToSpeechStream failed, err: %v", err)
	}

	return nil
}

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
	"time"
	"bytes"
	"net/http"
	
	"github.com/vmihailenco/msgpack/v5"
)

type fishAudioTTS struct {
	client *http.Client //?
	config fishAudioTTSConfig
}

type fishAudioTTSConfig struct {
	ApiKey                   string
	ModelId                  string
	OptimizeStreamingLatency bool
	RequestTimeoutSeconds    int
}

func defaultFishAudioTTSConfig() fishAudioTTSConfig {
	return fishAudioTTSConfig{
		ApiKey:                   "",
		ModelId:                  "d8639b5cc95548f5afbcfe22d3ba5ce5",
		OptimizeStreamingLatency: true,
		RequestTimeoutSeconds:    30,
	}
}

func newFishAudioTTS(config fishAudioTTSConfig) (*fishAudioTTS, error) {
	return &fishAudioTTS{
		config: config,
		client: &http.Client{
			Timeout: time.Second * 10,
		},
	}, nil
}

func (e *fishAudioTTS) textToSpeechStream(streamWriter io.Writer, text string) (err error) {
	latency := "normal"
	if e.config.OptimizeStreamingLatency {
		latency = "balanced"
	}

	// Create the payload
	payload := map[string]interface{}{
		"text":         text,
		"chunk_length": 100,
		"latency":      latency,
		"reference_id": e.config.ModelId,
		"format":       "pcm", // 44100/ 1ch/ 16bit
	}

	// Encode the payload to MessagePack
	body, err := msgpack.Marshal(payload)
	if err != nil {
		panic(err)
	}

	// Create a new POST request
	req, err := http.NewRequest("POST", "https://api.fish.audio/v1/tts", bytes.NewBuffer(body))
	if err != nil {
		panic(err)
	}

	// Set the headers
	req.Header.Add("Authorization", "Bearer " + e.config.ApiKey)
	req.Header.Set("Content-Type", "application/msgpack")

	// Create a client and send the request
	client := e.client
	resp, err := client.Do(req)
	if err != nil {
		panic(err)
	}
	defer resp.Body.Close()

	if err != nil {
		return fmt.Errorf("TextToSpeechStream failed, err: %v", err)
	}

// Check the response status code
if resp.StatusCode != http.StatusOK {
	slog.Error("Unexpected response status", "status", resp.StatusCode)
	return fmt.Errorf("unexpected response status: %d", resp.StatusCode)
}

// Write the returned PCM data to streamWriter
buffer := make([]byte, 4096) // 4KB buffer size
for {
	n, err := resp.Body.Read(buffer)
	if err != nil && err != io.EOF {
		slog.Error("Failed to read from response body", "error", err)
		return fmt.Errorf("failed to read from response body: %w", err)
	}
	if n == 0 {
		break // end of the stream
	}

	_, writeErr := streamWriter.Write(buffer[:n])
	if writeErr != nil {
		slog.Error("Failed to write to streamWriter", "error", writeErr)
		return fmt.Errorf("failed to write to streamWriter: %w", writeErr)
	}
}

	return nil
}

/**
 *
 * Agora Real Time Engagement
 * Created by lixinhui in 2024.
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
	"math/rand"
	"net/http"
	"net/url"

	openai "github.com/sashabaranov/go-openai"
)

type openaiChatGPT struct {
	client *openai.Client
	config openaiChatGPTConfig
}

type openaiChatGPTConfig struct {
	ApiKey string

	Model  string
	Prompt string

	FrequencyPenalty float32
	PresencePenalty  float32
	TopP             float32
	Temperature      float32
	MaxTokens        int
	Seed             int

	ProxyUrl string
}

func defaultOpenaiChatGPTConfig() openaiChatGPTConfig {
	return openaiChatGPTConfig{
		ApiKey: "",

		Model:  openai.GPT4o,
		Prompt: "You are a voice assistant who talks in a conversational way and can chat with me like my friends. i will speak to you in english or chinese, and you will answer in the corrected and improved version of my text with the language i use. Don't talk like a robot, instead i would like you to talk like real human with emotions. i will use your answer for text-to-speech, so don't return me any meaningless characters. I want you to be helpful, when i'm asking you for advices, give me precise, practical and useful advices instead of being vague. When giving me list of options, express the options in a narrative way instead of bullet points.",

		FrequencyPenalty: 0.9,
		PresencePenalty:  0.9,
		TopP:             1.0,
		Temperature:      0.1,
		MaxTokens:        512,
		Seed:             rand.Int(),

		ProxyUrl: "",
	}
}

func newOpenaiChatGPT(config openaiChatGPTConfig) (*openaiChatGPT, error) {
	conf := openai.DefaultConfig(config.ApiKey)
	if config.ProxyUrl != "" {
		proxyUrl, err := url.Parse(config.ProxyUrl)
		if err != nil {
			return nil, fmt.Errorf("newOpenaiChatGPT failed on parsing proxy url, err: %v", err)
		}
		conf.HTTPClient = &http.Client{Transport: &http.Transport{Proxy: http.ProxyURL(proxyUrl)}}
	}

	return &openaiChatGPT{
		config: config,
		client: openai.NewClientWithConfig(conf),
	}, nil
}

func (c *openaiChatGPT) getChatCompletionsStream(messages []openai.ChatCompletionMessage) (*openai.ChatCompletionStream, error) {
	req := openai.ChatCompletionRequest{
		Temperature:      c.config.Temperature,
		TopP:             c.config.TopP,
		PresencePenalty:  c.config.PresencePenalty,
		FrequencyPenalty: c.config.FrequencyPenalty,
		MaxTokens:        c.config.MaxTokens,
		Seed:             &c.config.Seed,
		Messages: append(
			[]openai.ChatCompletionMessage{
				{
					Role:    openai.ChatMessageRoleSystem,
					Content: c.config.Prompt,
				},
			},
			messages...,
		),
		Model:  c.config.Model,
		Stream: true,
	}

	resp, err := c.client.CreateChatCompletionStream(context.Background(), req)
	if err != nil {
		return nil, fmt.Errorf("CreateChatCompletionStream failed,err: %v", err)
	}
	return resp, nil
}

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
	"errors"
	"fmt"
	"io"
	"sync"
	"sync/atomic"
	"time"

	"ten_framework/ten"

	openai "github.com/sashabaranov/go-openai"
)

type openaiChatGPTExtension struct {
	ten.DefaultExtension
	openaiChatGPT *openaiChatGPT
}

const (
	cmdInFlush                              = "flush"
	cmdOutFlush                             = "flush"
	dataInTextDataPropertyText              = "text"
	dataInTextDataPropertyIsFinal           = "is_final"
	dataOutTextDataPropertyText             = "text"
	dataOutTextDataPropertyTextEndOfSegment = "end_of_segment"

	propertyBaseUrl          = "base_url"          // Optional
	propertyApiKey           = "api_key"           // Required
	propertyModel            = "model"             // Optional
	propertyPrompt           = "prompt"            // Optional
	propertyFrequencyPenalty = "frequency_penalty" // Optional
	propertyPresencePenalty  = "presence_penalty"  // Optional
	propertyTemperature      = "temperature"       // Optional
	propertyTopP             = "top_p"             // Optional
	propertyMaxTokens        = "max_tokens"        // Optional
	propertyGreeting         = "greeting"          // Optional
	propertyProxyUrl         = "proxy_url"         // Optional
	propertyMaxMemoryLength  = "max_memory_length" // Optional
)

var (
	memory          []openai.ChatCompletionMessage
	memoryChan      chan openai.ChatCompletionMessage
	maxMemoryLength = 10

	outdateTs atomic.Int64
	wg        sync.WaitGroup
)

func newChatGPTExtension(name string) ten.Extension {
	return &openaiChatGPTExtension{}
}

// OnStart will be called when the extension is starting,
// properies can be read here to initialize and start the extension.
// current supported properties:
//   - api_key (required)
//   - model
//   - prompt
//   - frequency_penalty
//   - presence_penalty
//   - temperature
//   - top_p
//   - max_tokens
//   - greeting
//   - proxy_url
func (p *openaiChatGPTExtension) OnStart(tenEnv ten.TenEnv) {
	tenEnv.LogInfo("OnStart")

	// prepare configuration
	openaiChatGPTConfig := defaultOpenaiChatGPTConfig()

	if baseUrl, err := tenEnv.GetPropertyString(propertyBaseUrl); err != nil {
		tenEnv.LogError(fmt.Sprintf("GetProperty required %s failed, err: %v", propertyBaseUrl, err))
	} else {
		if len(baseUrl) > 0 {
			openaiChatGPTConfig.BaseUrl = baseUrl
		}
	}

	if apiKey, err := tenEnv.GetPropertyString(propertyApiKey); err != nil {
		tenEnv.LogError(fmt.Sprintf("GetProperty required %s failed, err: %v", propertyApiKey, err))
		return
	} else {
		openaiChatGPTConfig.ApiKey = apiKey
	}

	if model, err := tenEnv.GetPropertyString(propertyModel); err != nil {
		tenEnv.LogWarn(fmt.Sprintf("GetProperty optional %s error:%v", propertyModel, err))
	} else {
		if len(model) > 0 {
			openaiChatGPTConfig.Model = model
		}
	}

	if prompt, err := tenEnv.GetPropertyString(propertyPrompt); err != nil {
		tenEnv.LogWarn(fmt.Sprintf("GetProperty optional %s error:%v", propertyPrompt, err))
	} else {
		if len(prompt) > 0 {
			openaiChatGPTConfig.Prompt = prompt
		}
	}

	if frequencyPenalty, err := tenEnv.GetPropertyFloat64(propertyFrequencyPenalty); err != nil {
		tenEnv.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyFrequencyPenalty, err))
	} else {
		openaiChatGPTConfig.FrequencyPenalty = float32(frequencyPenalty)
	}

	if presencePenalty, err := tenEnv.GetPropertyFloat64(propertyPresencePenalty); err != nil {
		tenEnv.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyPresencePenalty, err))
	} else {
		openaiChatGPTConfig.PresencePenalty = float32(presencePenalty)
	}

	if temperature, err := tenEnv.GetPropertyFloat64(propertyTemperature); err != nil {
		tenEnv.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyTemperature, err))
	} else {
		openaiChatGPTConfig.Temperature = float32(temperature)
	}

	if topP, err := tenEnv.GetPropertyFloat64(propertyTopP); err != nil {
		tenEnv.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyTopP, err))
	} else {
		openaiChatGPTConfig.TopP = float32(topP)
	}

	if maxTokens, err := tenEnv.GetPropertyInt64(propertyMaxTokens); err != nil {
		tenEnv.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyMaxTokens, err))
	} else {
		if maxTokens > 0 {
			openaiChatGPTConfig.MaxTokens = int(maxTokens)
		}
	}

	if proxyUrl, err := tenEnv.GetPropertyString(propertyProxyUrl); err != nil {
		tenEnv.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyProxyUrl, err))
	} else {
		openaiChatGPTConfig.ProxyUrl = proxyUrl
	}

	greeting, err := tenEnv.GetPropertyString(propertyGreeting)
	if err != nil {
		tenEnv.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyGreeting, err))
	}

	if propMaxMemoryLength, err := tenEnv.GetPropertyInt64(propertyMaxMemoryLength); err != nil {
		tenEnv.LogWarn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyMaxMemoryLength, err))
	} else {
		if propMaxMemoryLength > 0 {
			maxMemoryLength = int(propMaxMemoryLength)
		}
	}

	// create openaiChatGPT instance
	openaiChatgpt, err := newOpenaiChatGPT(openaiChatGPTConfig)
	if err != nil {
		tenEnv.LogError(fmt.Sprintf("newOpenaiChatGPT failed, err: %v", err))
		return
	}
	tenEnv.LogInfo(fmt.Sprintf("newOpenaiChatGPT succeed with max_tokens: %d, model: %s",
		openaiChatGPTConfig.MaxTokens, openaiChatGPTConfig.Model))

	p.openaiChatGPT = openaiChatgpt

	memoryChan = make(chan openai.ChatCompletionMessage, maxMemoryLength*2)

	// send greeting if available
	if len(greeting) > 0 {
		outputData, _ := ten.NewData("text_data")
		outputData.SetProperty(dataOutTextDataPropertyText, greeting)
		outputData.SetProperty(dataOutTextDataPropertyTextEndOfSegment, true)
		if err := tenEnv.SendData(outputData, nil); err != nil {
			tenEnv.LogError(fmt.Sprintf("greeting [%s] send failed, err: %v", greeting, err))
		} else {
			tenEnv.LogInfo(fmt.Sprintf("greeting [%s] sent", greeting))
		}
	}

	tenEnv.OnStartDone()
}

// OnCmd receives cmd from ten graph.
// current supported cmd:
//   - name: flush
//     example:
//     {"name": "flush"}
func (p *openaiChatGPTExtension) OnCmd(
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

		wg.Wait() // wait for chat completion stream to finish

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
//     {"name": "text_data", "properties": {"text": "hello", "is_final": true}
func (p *openaiChatGPTExtension) OnData(
	tenEnv ten.TenEnv,
	data ten.Data,
) {
	// Get isFinal
	isFinal, err := data.GetPropertyBool(dataInTextDataPropertyIsFinal)
	if err != nil {
		tenEnv.LogWarn(fmt.Sprintf("OnData GetProperty %s failed, err: %v", dataInTextDataPropertyIsFinal, err))
		return
	}
	if !isFinal { // ignore non-final
		tenEnv.LogDebug("ignore non-final input")
		return
	}

	// Get input text
	inputText, err := data.GetPropertyString(dataInTextDataPropertyText)
	if err != nil {
		tenEnv.LogError(fmt.Sprintf("OnData GetProperty %s failed, err: %v", dataInTextDataPropertyText, err))
		return
	}
	if len(inputText) == 0 {
		tenEnv.LogDebug("ignore empty text")
		return
	}
	tenEnv.LogInfo(fmt.Sprintf("OnData input text: [%s]", inputText))

	// prepare memory
	for len(memoryChan) > 0 {
		m, ok := <-memoryChan
		if !ok {
			break
		}
		memory = append(memory, m)
		if len(memory) > maxMemoryLength {
			memory = memory[1:]
		}
	}
	memory = append(memory, openai.ChatCompletionMessage{
		Role:    openai.ChatMessageRoleUser,
		Content: inputText,
	})
	if len(memory) > maxMemoryLength {
		memory = memory[1:]
	}

	// start goroutine to request and read responses from openai
	wg.Add(1)
	go func(startTime time.Time, inputText string, memory []openai.ChatCompletionMessage) {
		defer wg.Done()
		tenEnv.LogInfo(fmt.Sprintf("GetChatCompletionsStream for input text: [%s] memory: %v", inputText, memory))

		// Get result from ai
		resp, err := p.openaiChatGPT.getChatCompletionsStream(memory)
		if err != nil {
			tenEnv.LogError(fmt.Sprintf("GetChatCompletionsStream for input text: [%s] failed, err: %v", inputText, err))
			return
		}
		defer func() {
			if resp != nil { // Close stream object
				resp.Close()
			}
		}()
		tenEnv.LogDebug(fmt.Sprintf("GetChatCompletionsStream start to recv for input text: [%s]", inputText))

		var sentence, fullContent string
		var firstSentenceSent bool
		for {
			if startTime.UnixMicro() < outdateTs.Load() { // Check whether to interrupt
				tenEnv.LogInfo(fmt.Sprintf("GetChatCompletionsStream recv interrupt and flushing for input text: [%s], startTs: %d, outdateTs: %d",
					inputText, startTime.UnixMicro(), outdateTs.Load()))
				break
			}

			chatCompletions, err := resp.Recv()
			if errors.Is(err, io.EOF) {
				tenEnv.LogDebug(fmt.Sprintf("GetChatCompletionsStream recv for input text: [%s], io.EOF break", inputText))
				break
			}

			var content string
			if len(chatCompletions.Choices) > 0 && chatCompletions.Choices[0].Delta.Content != "" {
				content = chatCompletions.Choices[0].Delta.Content
			}
			fullContent += content

			for {
				// feed content and check whether sentence is available
				var sentenceIsFinal bool
				sentence, content, sentenceIsFinal = parseSentence(sentence, content)
				if len(sentence) == 0 || !sentenceIsFinal {
					tenEnv.LogDebug(fmt.Sprintf("sentence %s is empty or not final", sentence))
					break
				}
				tenEnv.LogDebug(fmt.Sprintf("GetChatCompletionsStream recv for input text: [%s] got sentence: [%s]", inputText, sentence))

				// send sentence
				outputData, err := ten.NewData("text_data")
				if err != nil {
					tenEnv.LogError(fmt.Sprintf("NewData failed, err: %v", err))
					break
				}
				outputData.SetProperty(dataOutTextDataPropertyText, sentence)
				outputData.SetProperty(dataOutTextDataPropertyTextEndOfSegment, false)
				if err := tenEnv.SendData(outputData, nil); err != nil {
					tenEnv.LogError(fmt.Sprintf("GetChatCompletionsStream recv for input text: [%s] send sentence [%s] failed, err: %v", inputText, sentence, err))
					break
				} else {
					tenEnv.LogInfo(fmt.Sprintf("GetChatCompletionsStream recv for input text: [%s] sent sentence [%s]", inputText, sentence))
				}
				sentence = ""

				if !firstSentenceSent {
					firstSentenceSent = true
					tenEnv.LogInfo(fmt.Sprintf("GetChatCompletionsStream recv for input text: [%s] first sentence sent, first_sentency_latency %dms",
						inputText, time.Since(startTime).Milliseconds()))
				}
			}
		}

		// remember response as assistant content in memory
		memoryChan <- openai.ChatCompletionMessage{
			Role:    openai.ChatMessageRoleAssistant,
			Content: fullContent,
		}

		// send end of segment
		outputData, _ := ten.NewData("text_data")
		outputData.SetProperty(dataOutTextDataPropertyText, sentence)
		outputData.SetProperty(dataOutTextDataPropertyTextEndOfSegment, true)
		if err := tenEnv.SendData(outputData, nil); err != nil {
			tenEnv.LogError(fmt.Sprintf("GetChatCompletionsStream for input text: [%s] end of segment with sentence [%s] send failed, err: %v", inputText, sentence, err))
		} else {
			tenEnv.LogInfo(fmt.Sprintf("GetChatCompletionsStream for input text: [%s] end of segment with sentence [%s] sent", inputText, sentence))
		}
	}(time.Now(), inputText, append([]openai.ChatCompletionMessage{}, memory...))
}

func init() {
	// Register addon
	ten.RegisterAddonAsExtension(
		"openai_chatgpt",
		ten.NewDefaultExtensionAddon(newChatGPTExtension),
	)
}

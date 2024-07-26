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
	"fmt"
	"log/slog"
	"sync"
	"sync/atomic"
	"time"

	"agora.io/rte/rtego"
	"github.com/aws/aws-sdk-go-v2/service/bedrockruntime/types"
)

var (
	logTag = slog.String("extension", "BEDROCK_LLM_EXTENSION")
)

type bedrockLLMExtension struct {
	rtego.DefaultExtension
	bedrockLLM *bedrockLLM
}

const (
	cmdInFlush                              = "flush"
	cmdOutFlush                             = "flush"
	dataInTextDataPropertyText              = "text"
	dataInTextDataPropertyIsFinal           = "is_final"
	dataOutTextDataPropertyText             = "text"
	dataOutTextDataPropertyTextEndOfSegment = "end_of_segment"

	propertyRegion          = "region"            // Optional
	propertyAccessKey       = "access_key"        // Required
	propertySecretKey       = "secret_key"        // Required
	propertyModel           = "model"             // Optional
	propertyPrompt          = "prompt"            // Optional
	propertyTemperature     = "temperature"       // Optional
	propertyTopP            = "top_p"             // Optional
	propertyMaxTokens       = "max_tokens"        // Optional
	propertyGreeting        = "greeting"          // Optional
	propertyMaxMemoryLength = "max_memory_length" // Optional
)

var (
	memory          []types.Message
	memoryChan      chan types.Message
	maxMemoryLength = 10

	outdateTs atomic.Int64
	wg        sync.WaitGroup
)

func newBedrockLLMExtension(name string) rtego.Extension {
	return &bedrockLLMExtension{}
}

// OnStart will be called when the extension is starting,
// properies can be read here to initialize and start the extension.
// current supported properties:
//   - region (optional)
//   - access_key (required)
//   - secret_key (required)
//   - prompt
//   - temperature
//   - top_p
//   - max_tokens
//   - greeting
func (p *bedrockLLMExtension) OnStart(rte rtego.Rte) {
	slog.Info("OnStart", logTag)

	// prepare configuration
	bedrockLLMConfig := defaultBedrockLLMConfig()

	if accessKey, err := rte.GetPropertyString(propertyAccessKey); err != nil {
		slog.Error(fmt.Sprintf("GetProperty required %s failed, err: %v", propertyAccessKey, err), logTag)
	} else {
		if len(accessKey) > 0 {
			bedrockLLMConfig.AccessKey = accessKey
		}
	}
	if secretKey, err := rte.GetPropertyString(propertySecretKey); err != nil {
		slog.Error(fmt.Sprintf("GetProperty required %s failed, err: %v", propertySecretKey, err), logTag)
	} else {
		if len(secretKey) > 0 {
			bedrockLLMConfig.SecretKey = secretKey
		}
	}

	if model, err := rte.GetPropertyString(propertyModel); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s error:%v", propertyModel, err), logTag)
	} else {
		if len(model) > 0 {
			bedrockLLMConfig.Model = model
		}
	}

	if prompt, err := rte.GetPropertyString(propertyPrompt); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s error:%v", propertyPrompt, err), logTag)
	} else {
		if len(prompt) > 0 {
			bedrockLLMConfig.Prompt = prompt
		}
	}

	if temperature, err := rte.GetPropertyFloat64(propertyTemperature); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyTemperature, err), logTag)
	} else {
		bedrockLLMConfig.Temperature = float32(temperature)
	}

	if topP, err := rte.GetPropertyFloat64(propertyTopP); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyTopP, err), logTag)
	} else {
		bedrockLLMConfig.TopP = float32(topP)
	}

	if maxTokens, err := rte.GetPropertyInt64(propertyMaxTokens); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyMaxTokens, err), logTag)
	} else {
		if maxTokens > 0 {
			bedrockLLMConfig.MaxTokens = int32(maxTokens)
		}
	}

	greeting, err := rte.GetPropertyString(propertyGreeting)
	if err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyGreeting, err), logTag)
	}

	if propMaxMemoryLength, err := rte.GetPropertyInt64(propertyMaxMemoryLength); err != nil {
		slog.Warn(fmt.Sprintf("GetProperty optional %s failed, err: %v", propertyMaxMemoryLength, err), logTag)
	} else {
		if propMaxMemoryLength > 0 {
			maxMemoryLength = int(propMaxMemoryLength)
		}
	}

	// create bedrockLLM instance
	bedrockLLM, err := newBedrockLLM(bedrockLLMConfig)
	if err != nil {
		slog.Error(fmt.Sprintf("newBedrockLLM failed, err: %v", err), logTag)
		return
	}
	slog.Info(fmt.Sprintf("newBedrockLLM succeed with max_tokens: %d, model: %s",
		bedrockLLMConfig.MaxTokens, bedrockLLMConfig.Model), logTag)

	p.bedrockLLM = bedrockLLM

	memoryChan = make(chan types.Message, maxMemoryLength*2)

	// send greeting if available
	if len(greeting) > 0 {
		outputData, _ := rtego.NewData("text_data")
		outputData.SetProperty(dataOutTextDataPropertyText, greeting)
		outputData.SetProperty(dataOutTextDataPropertyTextEndOfSegment, true)
		if err := rte.SendData(outputData); err != nil {
			slog.Error(fmt.Sprintf("greeting [%s] send failed, err: %v", greeting, err), logTag)
		} else {
			slog.Info(fmt.Sprintf("greeting [%s] sent", greeting), logTag)
		}
	}

	rte.OnStartDone()
}

// OnCmd receives cmd from rte graph.
// current supported cmd:
//   - name: flush
//     example:
//     {"name": "flush"}
func (p *bedrockLLMExtension) OnCmd(
	rte rtego.Rte,
	cmd rtego.Cmd,
) {
	cmdName, err := cmd.GetName()
	if err != nil {
		result, fatal := rtego.NewCmdResult(rtego.Error)

		if fatal != nil {
			slog.Error(fmt.Sprintf("OnCmd get name failed, err: %v", err), logTag)
		}
		rte.ReturnResult(result, cmd)
		return
	}
	slog.Info(fmt.Sprintf("OnCmd %s", cmdInFlush), logTag)

	switch cmdName {
	case cmdInFlush:
		outdateTs.Store(time.Now().UnixMicro())

		wg.Wait() // wait for chat completion stream to finish

		// send out
		outCmd, err := rtego.NewCmd(cmdOutFlush)
		if err != nil {
			result, fatal := rtego.NewCmdResult(rtego.Error)

			if fatal != nil {
				slog.Error(fmt.Sprintf("new cmd %s failed, err: %v", cmdOutFlush, err), logTag)
			}
			rte.ReturnResult(result, cmd)
			return
		}
		if err := rte.SendCmd(outCmd, nil); err != nil {
			result, fatal := rtego.NewCmdResult(rtego.Error)

			if fatal != nil {
				slog.Error(fmt.Sprintf("send cmd %s failed, err: %v", cmdOutFlush, err), logTag)
			}
			rte.ReturnResult(result, cmd)
			return
		} else {
			slog.Info(fmt.Sprintf("cmd %s sent", cmdOutFlush), logTag)
		}
	}

	result, _ := rtego.NewCmdResult(rtego.Ok)
	rte.ReturnResult(result, cmd)
}

// OnData receives data from rte graph.
// current supported data:
//   - name: text_data
//     example:
//     {"name": "text_data", "properties": {"text": "hello", "is_final": true}
func (p *bedrockLLMExtension) OnData(
	rte rtego.Rte,
	data rtego.Data,
) {
	// Get isFinal
	isFinal, err := data.GetPropertyBool(dataInTextDataPropertyIsFinal)
	if err != nil {
		slog.Warn(fmt.Sprintf("OnData GetProperty %s failed, err: %v", dataInTextDataPropertyIsFinal, err), logTag)
		return
	}
	if !isFinal { // ignore non-final
		slog.Debug("ignore non-final input", logTag)
		return
	}

	// Get input text
	inputText, err := data.GetPropertyString(dataInTextDataPropertyText)
	if err != nil {
		slog.Error(fmt.Sprintf("OnData GetProperty %s failed, err: %v", dataInTextDataPropertyText, err), logTag)
		return
	}
	if len(inputText) == 0 {
		slog.Debug("ignore empty text", logTag)
		return
	}
	slog.Info(fmt.Sprintf("OnData input text: [%s]", inputText), logTag)

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

	memory = append(memory, types.Message{
		Role: types.ConversationRoleUser,
		Content: []types.ContentBlock{
			&types.ContentBlockMemberText{
				Value: inputText,
			},
		},
	})

	if len(memory) > maxMemoryLength {
		memory = memory[1:]
	}

	// start goroutine to request and read responses from bedrock
	wg.Add(1)
	go func(startTime time.Time, inputText string, memory []types.Message) {
		defer wg.Done()
		slog.Info(fmt.Sprintf("getConvserseStream for input text: [%s] memory: %v", inputText, memory), logTag)

		// Get result from ai
		resp, err := p.bedrockLLM.getConverseStream(memory)
		if err != nil {
			slog.Error(fmt.Sprintf("getConvserseStream for input text: [%s] failed, err: %v", inputText, err), logTag)
			return
		}
		// defer func() {
		// 	if resp != nil { // Close stream object
		// 		resp.Close()
		// 	}
		// }()
		slog.Debug(fmt.Sprintf("getConvserseStream start to recv for input text: [%s]", inputText), logTag)

		var sentence, fullContent string
		var firstSentenceSent bool
		for event := range resp.GetStream().Events() {
			if startTime.UnixMicro() < outdateTs.Load() { // Check whether to interrupt
				slog.Info(fmt.Sprintf("GetChatCompletionsStream recv interrupt and flushing for input text: [%s], startTs: %d, outdateTs: %d",
					inputText, startTime.UnixMicro(), outdateTs.Load()), logTag)
				break
			}
			var content string

			switch v := event.(type) {
			// case *types.ConverseStreamOutputMemberMessageStart:
			// msg.Role = v.Value.Role
			case *types.ConverseStreamOutputMemberContentBlockDelta:
				textResponse := v.Value.Delta.(*types.ContentBlockDeltaMemberText)
				content = textResponse.Value

			case *types.UnknownUnionMember:
				fmt.Println("unknown tag:", v.Tag)
			}

			// chatCompletions, err := resp.Recv()
			// if errors.Is(err, io.EOF) {
			// 	slog.Debug(fmt.Sprintf("GetChatCompletionsStream recv for input text: [%s], io.EOF break", inputText), logTag)
			// 	break
			// }

			// if len(chatCompletions.Choices) > 0 && chatCompletions.Choices[0].Delta.Content != "" {
			// 	content = chatCompletions.Choices[0].Delta.Content
			// }
			fullContent += content

			for {
				// feed content and check whether sentence is available
				var sentenceIsFinal bool
				sentence, content, sentenceIsFinal = parseSentence(sentence, content)
				if len(sentence) == 0 || !sentenceIsFinal {
					slog.Debug(fmt.Sprintf("sentence %s is empty or not final", sentence), logTag)
					break
				}
				slog.Debug(fmt.Sprintf("GetChatCompletionsStream recv for input text: [%s] got sentence: [%s]", inputText, sentence), logTag)

				// send sentence
				outputData, err := rtego.NewData("text_data")
				if err != nil {
					slog.Error(fmt.Sprintf("NewData failed, err: %v", err), logTag)
					break
				}
				outputData.SetProperty(dataOutTextDataPropertyText, sentence)
				outputData.SetProperty(dataOutTextDataPropertyTextEndOfSegment, false)
				if err := rte.SendData(outputData); err != nil {
					slog.Error(fmt.Sprintf("GetChatCompletionsStream recv for input text: [%s] send sentence [%s] failed, err: %v", inputText, sentence, err), logTag)
					break
				} else {
					slog.Info(fmt.Sprintf("GetChatCompletionsStream recv for input text: [%s] sent sentence [%s]", inputText, sentence), logTag)
				}
				sentence = ""

				if !firstSentenceSent {
					firstSentenceSent = true
					slog.Info(fmt.Sprintf("GetChatCompletionsStream recv for input text: [%s] first sentence sent, first_sentency_latency %dms",
						inputText, time.Since(startTime).Milliseconds()), logTag)
				}
			}
		}

		// remember response as assistant content in memory
		memoryChan <- types.Message{
			Role: types.ConversationRoleAssistant,
			Content: []types.ContentBlock{
				&types.ContentBlockMemberText{
					Value: fullContent,
				},
			},
		}

		// send end of segment
		outputData, _ := rtego.NewData("text_data")
		outputData.SetProperty(dataOutTextDataPropertyText, sentence)
		outputData.SetProperty(dataOutTextDataPropertyTextEndOfSegment, true)
		if err := rte.SendData(outputData); err != nil {
			slog.Error(fmt.Sprintf("GetChatCompletionsStream for input text: [%s] end of segment with sentence [%s] send failed, err: %v", inputText, sentence, err), logTag)
		} else {
			slog.Info(fmt.Sprintf("GetChatCompletionsStream for input text: [%s] end of segment with sentence [%s] sent", inputText, sentence), logTag)
		}
	}(time.Now(), inputText, append([]types.Message{}, memory...))
}

func init() {
	slog.Info("init")

	// Register addon
	rtego.RegisterAddonAsExtension(
		"bedrock_llm",
		rtego.NewDefaultExtensionAddon(newBedrockLLMExtension),
	)
}

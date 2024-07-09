package azure

import (
	"app/pkg/common"
	"app/pkg/provider"
	"errors"

	"github.com/tidwall/sjson"
)

const NAME string = "azure"

func init() {
	provider.RegisterTts(NewAzureTtsProvider())
}

type AzureTtsProvider struct {
	voiceNameMap map[common.Language]map[common.VoiceType]string
}

func NewAzureTtsProvider() provider.ITtsProvider {
	return &AzureTtsProvider{
		voiceNameMap: map[common.Language]map[common.VoiceType]string{
			common.LanguageChinese: {
				common.VoiceTypeMale:   "zh-CN-YunxiNeural",
				common.VoiceTypeFemale: "zh-CN-XiaoxiaoNeural",
			},
			common.LanguageEnglish: {
				common.VoiceTypeMale:   "en-US-BrianNeural",
				common.VoiceTypeFemale: "en-US-JaneNeural",
			},
		},
	}
}

// Name implements provider.ITtsProvider.
func (p *AzureTtsProvider) Name() string {
	return NAME
}

// ProcessManifest implements provider.ITtsProvider.
func (p *AzureTtsProvider) ProcessManifest(manifestJson string, language common.Language, voiceType common.VoiceType) (string, error) {
	voiceTypeMap, ok := p.voiceNameMap[language]
	if !ok {
		return "", errors.New("unknow language")
	}
	voiceName, ok := voiceTypeMap[voiceType]
	if !ok {
		return "", errors.New("unknow voiceType")
	}
	return sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="azure_tts").property.azure_synthesis_voice_name`, voiceName)
}

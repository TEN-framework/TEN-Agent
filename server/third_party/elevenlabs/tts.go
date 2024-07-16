package elevenlabs

import (
	"app/pkg/common"
	"app/pkg/provider"
	"errors"

	"github.com/tidwall/sjson"
)

const NAME string = "elevenlabs"

func init() {
	provider.RegisterTts(NewElevenLabsTtsProvider())
}

type ElevenLabsTtsProvider struct {
	voiceNameMap map[common.Language]map[common.VoiceType]string
}

func NewElevenLabsTtsProvider() provider.ITtsProvider {
	return &ElevenLabsTtsProvider{
		voiceNameMap: map[common.Language]map[common.VoiceType]string{
			common.LanguageChinese: {
				common.VoiceTypeMale:   "pNInz6obpgDQGcFmaJgB", // Adam
				common.VoiceTypeFemale: "Xb7hH8MSUJpSbSDYk0k2", // Alice
			},
			common.LanguageEnglish: {
				common.VoiceTypeMale:   "pNInz6obpgDQGcFmaJgB", // Adam
				common.VoiceTypeFemale: "Xb7hH8MSUJpSbSDYk0k2", // Alice
			},
		},
	}
}

// Name implements provider.ITtsProvider.
func (p *ElevenLabsTtsProvider) Name() string {
	return NAME
}

// ProcessManifest implements provider.ITtsProvider.
func (p *ElevenLabsTtsProvider) ProcessManifest(manifestJson string, language common.Language, voiceType common.VoiceType) (string, error) {
	voiceTypeMap, ok := p.voiceNameMap[language]
	if !ok {
		return "", errors.New("unknow language")
	}
	voiceName, ok := voiceTypeMap[voiceType]
	if !ok {
		return "", errors.New("unknow voiceType")
	}
	return sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="elevenlabs_tts").property.voice_id`, voiceName)
}

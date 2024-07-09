package provider

import "app/pkg/common"

var registeredTts = make(map[string]ITtsProvider)

type ITtsProvider interface {
	Name() string
	ProcessManifest(manifestJson string, language common.Language, voiceType common.VoiceType) (string, error)
}

func RegisterTts(provider ITtsProvider) {
	if provider == nil {
		panic("cannot register a nil ITtsProvider")
	}
	if provider.Name() == "" {
		panic("cannot register ITtsProvider with empty string result for Name()")
	}
	registeredTts[provider.Name()] = provider
}

func GetTts(name string) ITtsProvider {
	return registeredTts[name]
}

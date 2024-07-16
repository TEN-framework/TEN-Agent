package internal

import (
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"regexp"

	"github.com/tidwall/sjson"
)

type ManifestProvider struct {
	// manifestJsons
	//	key: fileName string `manifest.json` `manifest.elevenlabs.json`
	//	value: manifestJson string
	manifestJsons map[string]string
}

func NewManifestProvider() *ManifestProvider {
	return &ManifestProvider{
		manifestJsons: make(map[string]string),
	}
}

func (p *ManifestProvider) LoadManifest(manifestJsonDir string) error {
	files, err := os.ReadDir(manifestJsonDir)
	if err != nil {
		slog.Error("read manifestJsonDir failed", "err", err, "manifestJsonDir", manifestJsonDir)
		return err
	}

	matcher := regexp.MustCompile(`^manifest(\..+)?\.json$`) // `manifest.json` or `manifest.elevenlabs.json`
	for _, file := range files {
		if file.IsDir() {
			continue
		}
		if !matcher.MatchString(file.Name()) {
			continue
		}

		manifestJsonFile := filepath.Join(manifestJsonDir, file.Name())
		content, err := os.ReadFile(manifestJsonFile)
		if err != nil {
			slog.Error("read manifest json failed", "err", err, "manifestJsonFile", manifestJsonFile)
			return err
		}

		manifestJson := string(content)
		manifestJson = p.injectEnvVar(manifestJson)

		p.manifestJsons[file.Name()] = manifestJson
	}

	return nil
}

func (p *ManifestProvider) injectEnvVar(manifestJson string) string {
	appId := os.Getenv("AGORA_APP_ID")
	if appId != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="agora_rtc").property.app_id`, appId)
	}

	azureSttKey := os.Getenv("AZURE_STT_KEY")
	if azureSttKey != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="agora_rtc").property.agora_asr_vendor_key`, azureSttKey)
	}

	azureSttRegion := os.Getenv("AZURE_STT_REGION")
	if azureSttRegion != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="agora_rtc").property.agora_asr_vendor_region`, azureSttRegion)
	}

	openaiBaseUrl := os.Getenv("OPENAI_BASE_URL")
	if openaiBaseUrl != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="openai_chatgpt").property.base_url`, openaiBaseUrl)
	}

	openaiApiKey := os.Getenv("OPENAI_API_KEY")
	if openaiApiKey != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="openai_chatgpt").property.api_key`, openaiApiKey)
	}

	openaiModel := os.Getenv("OPENAI_MODEL")
	if openaiModel != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="openai_chatgpt").property.model`, openaiModel)
	}

	proxyUrl := os.Getenv("PROXY_URL")
	if proxyUrl != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="openai_chatgpt").property.proxy_url`, proxyUrl)
	}

	azureTtsKey := os.Getenv("AZURE_TTS_KEY")
	if azureTtsKey != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="azure_tts").property.azure_subscription_key`, azureTtsKey)
	}

	azureTtsRegion := os.Getenv("AZURE_TTS_REGION")
	if azureTtsRegion != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="azure_tts").property.azure_subscription_region`, azureTtsRegion)
	}

	elevenlabsTtsKey := os.Getenv("ELEVENLABS_TTS_KEY")
	if elevenlabsTtsKey != "" {
		manifestJson, _ = sjson.Set(manifestJson, `predefined_graphs.0.nodes.#(name=="elevenlabs_tts").property.api_key`, elevenlabsTtsKey)
	}

	return manifestJson
}

func (p *ManifestProvider) GetManifestJson(vendor string) (manifestJson string, err error) {
	if len(vendor) > 0 {
		vendor = "." + vendor
	}
	manifestJson, ok := p.manifestJsons["manifest"+vendor+".json"] // `manifest.json` or `manifest.elevenlabs.json`
	if !ok {
		return "", fmt.Errorf("unknow manifest vendor: %s", vendor)
	}

	return manifestJson, nil
}

import { voiceNameMap } from "./constant"

export const getGraphWithLanguage = (graphName: string, language: string) => {
    if (graphName == "camera.va.openai.azure") {
        if (language == "zh-CN") {
            return `${graphName}.cn`
        }
        return `${graphName}.en`
    }
    return graphName
}

export const getGraphProperties = (graphName: string, language: string, voiceType: string) => {
    if (graphName == "camera.va.openai.azure") {
        return {
            "agora_rtc": {
                "agora_asr_language": language,
            },
            "openai_chatgpt": {
                "model": "gpt-4o"
            },
            "azure_tts": {
                "azure_synthesis_voice_name": voiceNameMap[language]["azure"][voiceType]
            }
        }
    } else if (graphName == "va.openai.azure") {
        return {
            "agora_rtc": {
                "agora_asr_language": language,
            },
            "azure_tts": {
                "azure_synthesis_voice_name": voiceNameMap[language]["azure"][voiceType]
            }
        }
    } else if (graphName == "va.qwen.rag") {
        return {
            "agora_rtc": {
                "agora_asr_language": language,
            },
            "azure_tts": {
                "azure_synthesis_voice_name": voiceNameMap[language]["azure"][voiceType]
            }
        }
    }
    return {}
}
import { LanguageMap } from "./constant";

export const voiceNameMap: LanguageMap = {
    "zh-CN": {
        azure: {
            male: "zh-CN-YunxiNeural",
            female: "zh-CN-XiaoxiaoNeural",
        },
        elevenlabs: {
            male: "pNInz6obpgDQGcFmaJgB", // Adam
            female: "Xb7hH8MSUJpSbSDYk0k2", // Alice
        },
        polly: {
            male: "Zhiyu",
            female: "Zhiyu",
        },
    },
    "en-US": {
        azure: {
            male: "en-US-BrianNeural",
            female: "en-US-JaneNeural",
        },
        elevenlabs: {
            male: "pNInz6obpgDQGcFmaJgB", // Adam
            female: "Xb7hH8MSUJpSbSDYk0k2", // Alice
        },
        polly: {
            male: "Matthew",
            female: "Ruth",
        },
    },
    "ja-JP": {
        azure: {
            male: "ja-JP-KeitaNeural",
            female: "ja-JP-NanamiNeural",
        },
    },
    "ko-KR": {
        azure: {
            male: "ko-KR-InJoonNeural",
            female: "ko-KR-JiMinNeural",
        },
    },
};

export const getGraphProperties = (graphName: string, language: string, voiceType: string) => {
    let localizationOptions = {
        "greeting": "ASTRA agent connected. How can i help you today?",
        "checking_vision_text_items": "[\"Let me take a look...\",\"Let me check your camera...\",\"Please wait for a second...\"]",
    }

    if (language === "zh-CN") {
        localizationOptions = {
            "greeting": "Astra已连接，需要我为您提供什么帮助?",
            "checking_vision_text_items": "[\"让我看看你的摄像头...\",\"让我看一下...\",\"我看一下，请稍候...\"]",
        }
    } else if (language === "ja-JP") {
        localizationOptions = {
            "greeting": "ASTRAエージェントに接続されました。今日は何をお手伝いしましょうか?",
            "checking_vision_text_items": "[\"ちょっと見てみます...\",\"カメラをチェックします...\",\"少々お待ちください...\"]",
        }
    } else if (language === "ko-KR") {
        localizationOptions = {
            "greeting": "ASTRA 에이전트에 연결되었습니다. 오늘은 무엇을 도와드릴까요?",
            "checking_vision_text_items": "[\"조금만 기다려 주세요...\",\"카메라를 확인해 보겠습니다...\",\"잠시만 기다려 주세요...\"]",
        }
    }

    if (graphName == "camera.va.openai.azure") {
        return {
            "agora_rtc": {
                "agora_asr_language": language,
            },
            "openai_chatgpt": {
                "model": "gpt-4o",
                ...localizationOptions
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
            "openai_chatgpt": {
                "model": "gpt-4o-mini",
                ...localizationOptions
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
    } else if (graphName == "va.transcribe-bedrock.polly") {
        return {
            "transcribe_asr": {
                "lang_code": language,
            },
            "polly_tts": {
                "voice": voiceNameMap[language]["polly"][voiceType],
                "lang_code": language
            }
        }
    }
    return {}
}
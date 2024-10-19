import { LanguageMap } from "@/common/constant";

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
        openai: {
            male: "alloy",
            female: "shimmer"
        }
    },
    "en-US": {
        azure: {
            male: "en-US-AndrewMultilingualNeural",
            female: "en-US-AvaMultilingualNeural",
        },
        elevenlabs: {
            male: "pNInz6obpgDQGcFmaJgB", // Adam
            female: "Xb7hH8MSUJpSbSDYk0k2", // Alice
        },
        polly: {
            male: "Matthew",
            female: "Ruth",
        },
        openai: {
            male: "alloy",
            female: "shimmer"
        }
    },
    "ja-JP": {
        azure: {
            male: "ja-JP-KeitaNeural",
            female: "ja-JP-NanamiNeural",
        },
        openai: {
            male: "alloy",
            female: "shimmer"
        }
    },
    "ko-KR": {
        azure: {
            male: "ko-KR-InJoonNeural",
            female: "ko-KR-JiMinNeural",
        },
        openai: {
            male: "alloy",
            female: "shimmer"
        }
    },
};

// Get the graph properties based on the graph name, language, and voice type
// This is the place where you can customize the properties for different graphs to override default property.json
export const getGraphProperties = (
    graphName: string,
    language: string,
    voiceType: string,
    prompt: string | undefined,
    greeting: string | undefined
) => {
    let localizationOptions = {
        "greeting": "Hey, I\'m TEN Agent, I can speak, see, and reason from a knowledge base, ask me anything!",
        "checking_vision_text_items": "[\"Let me take a look...\",\"Let me check your camera...\",\"Please wait for a second...\"]",
    }

    if (language === "zh-CN") {
        localizationOptions = {
            "greeting": "嗨，我是 TEN Agent，我可以说话、看东西，还能从知识库中推理，问我任何问题吧！",
            "checking_vision_text_items": "[\"让我看看你的摄像头...\",\"让我看一下...\",\"我看一下，请稍候...\"]",
        }
    } else if (language === "ja-JP") {
        localizationOptions = {
            "greeting": "こんにちは、TEN Agentです。私は話したり、見たり、知識ベースから推論したりできます。何でも聞いてください！",
            "checking_vision_text_items": "[\"ちょっと見てみます...\",\"カメラをチェックします...\",\"少々お待ちください...\"]",
        }
    } else if (language === "ko-KR") {
        localizationOptions = {
            "greeting": "안녕하세요, 저는 TEN Agent입니다. 말하고, 보고, 지식 베이스에서 추론할 수 있어요. 무엇이든 물어보세요!",
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
                ...localizationOptions,
                "prompt": prompt,
                "greeting": greeting,
            },
            "azure_tts": {
                "azure_synthesis_voice_name": voiceNameMap[language]["azure"][voiceType]
            }
        }
    } else if (graphName == "va.openai.v2v") {
        return {
            "openai_v2v_python": {
                "model": "gpt-4o-realtime-preview",
                "voice": voiceNameMap[language]["openai"][voiceType],
                "language": language,
                ...localizationOptions,
                "system_message": prompt,
                "greeting": greeting,
            }
        }
    } else if (graphName == "va.openai.azure") {
        return {
            "agora_rtc": {
                "agora_asr_language": language,
            },
            "openai_chatgpt": {
                "model": "gpt-4o-mini",
                ...localizationOptions,
                "prompt": prompt,
                "greeting": greeting,
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

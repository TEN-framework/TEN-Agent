import { LanguageMap } from '@/common/constant';
import { NextRequest, NextResponse } from 'next/server';


const { AGENT_SERVER_URL } = process.env;

// Check if environment variables are available
if (!AGENT_SERVER_URL) {
    throw "Environment variables AGENT_SERVER_URL are not available";
}


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
            female: "en-US-AndrewMultilingualNeural",
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

// Get the graph properties based on the graph name, language, and voice type
// This is the place where you can customize the properties for different graphs to override default property.json
export const getGraphProperties = (graphName: string, language: string, voiceType: string) => {
    let localizationOptions = {
        "greeting": "TEN agent connected. How can I help you today?",
        "checking_vision_text_items": "[\"Let me take a look...\",\"Let me check your camera...\",\"Please wait for a second...\"]",
    }

    if (language === "zh-CN") {
        localizationOptions = {
            "greeting": "TEN Agent 已连接，需要我为您提供什么帮助?",
            "checking_vision_text_items": "[\"让我看看你的摄像头...\",\"让我看一下...\",\"我看一下，请稍候...\"]",
        }
    } else if (language === "ja-JP") {
        localizationOptions = {
            "greeting": "TEN Agent エージェントに接続されました。今日は何をお手伝いしましょうか?",
            "checking_vision_text_items": "[\"ちょっと見てみます...\",\"カメラをチェックします...\",\"少々お待ちください...\"]",
        }
    } else if (language === "ko-KR") {
        localizationOptions = {
            "greeting": "TEN Agent  에이전트에 연결되었습니다. 오늘은 무엇을 도와드릴까요?",
            "checking_vision_text_items": "[\"조금만 기다려 주세요...\",\"카메라를 확인해 보겠습니다...\",\"잠시만 기다려 주세요...\"]",
        }
    }

    if (graphName == "camera_va_openai_azure") {
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
    } else if (graphName == "va_openai_azure") {
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
    } else if (graphName == "va_qwen_rag") {
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

export async function startAgent(request: NextRequest) {
    try {
        const body = await request.json();
        const {
            request_id,
            channel_name,
            user_uid,
            graph_name,
            language,
            voice_type,
        } = body;

        // Send a POST request to start the agent
        const response = await fetch(`${AGENT_SERVER_URL}/start`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                request_id,
                channel_name,
                user_uid,
                graph_name,
                // Get the graph properties based on the graph name, language, and voice type
                properties: getGraphProperties(graph_name, language, voice_type),
            }),
        });

        const responseData = await response.json();

        return NextResponse.json(responseData, { status: response.status });
    } catch (error) {
        if (error instanceof Response) {
            const errorData = await error.json();
            return NextResponse.json(errorData, { status: error.status });
        } else {
            return NextResponse.json({ code: "1", data: null, msg: "Internal Server Error" }, { status: 500 });
        }
    }
}

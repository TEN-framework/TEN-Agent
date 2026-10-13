import type { LanguageMap } from "@/common/constant";
import type { IOceanBaseSettings } from "@/types";

const OPENAI_REALTIME_MODEL = "gpt-realtime-2.1";
const OPENAI_REALTIME_15_MODEL = "gpt-realtime-1.5";
const OPENAI_REALTIME_MINI_MODEL = "gpt-realtime-mini";
const MINIMAX_DEFAULT_PROMPT =
  "Provide short, narrative responses in plain text. Keep answers concise and natural. Do not use emoji, markdown formatting, or special decorative characters.";

export const voiceNameMap: LanguageMap = {
  "zh-CN": {
    azure: {
      male: "zh-CN-YunyiMultilingualNeural",
      female: "zh-CN-XiaoxiaoMultilingualNeural",
    },
    elevenlabs: {
      male: "pNInz6obpgDQGcFmaJgB", // Adam
      female: "Xb7hH8MSUJpSbSDYk0k2", // Alice
    },
    polly: {
      male: "Zhiyu",
      female: "Zhiyu",
      langCode: "cmn-CN",
      langEngine: "neural",
    },
    openai: {
      male: "ash",
      female: "shimmer",
    },
    gemini: {
      male: "Charon",
      female: "Aoede",
      langCode: "cmn-CN",
    },
    azure_grok4: {
      male: "zh-CN-YunyiMultilingualNeural",
      female: "zh-CN-XiaoxiaoMultilingualNeural",
    },
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
      langCode: "en-US",
      langEngine: "generative",
    },
    openai: {
      male: "ash",
      female: "shimmer",
    },
    gemini: {
      male: "Charon",
      female: "Aoede",
      langCode: "en-US",
    },
    azure_grok4: {
      male: "en-US-AndrewMultilingualNeural",
      female: "en-US-AvaMultilingualNeural",
    },
  },
  "ja-JP": {
    azure: {
      male: "ja-JP-KeitaNeural",
      female: "ja-JP-NanamiNeural",
    },
    openai: {
      male: "ash",
      female: "shimmer",
    },
    gemini: {
      male: "Charon",
      female: "Aoede",
      langCode: "ja-JP",
    },
    azure_grok4: {
      male: "ja-JP-KeitaNeural",
      female: "ja-JP-NanamiNeural",
    },
  },
  "ko-KR": {
    azure: {
      male: "ko-KR-InJoonNeural",
      female: "ko-KR-JiMinNeural",
    },
    openai: {
      male: "ash",
      female: "shimmer",
    },
    gemini: {
      male: "Charon",
      female: "Aoede",
      langCode: "ko-KR",
    },
    azure_grok4: {
      male: "ko-KR-InJoonNeural",
      female: "ko-KR-JiMinNeural",
    },
  },
};

export const convertLanguage = (language: string) => {
  if (language === "zh-CN") {
    return "zh";
  } else if (language === "en-US") {
    return "en";
  } else if (language === "ja-JP") {
    return "ja";
  } else if (language === "ko-KR") {
    return "ko";
  }
  return "en";
};

// Get the graph properties based on the graph name, language, and voice type
// This is the place where you can customize the properties for different graphs to override default property.json
export const getGraphProperties = (
  graphName: string,
  language: string,
  voiceType: string,
  characterId: string | undefined,
  prompt: string | undefined,
  greeting: string | undefined,
  oceanbaseSettings: IOceanBaseSettings | undefined
) => {
  let localizationOptions = {
    greeting:
      "Hey, I'm TEN Agent, I can speak, see, and reason from a knowledge base, ask me anything!",
    checking_vision_text_items:
      '["Let me take a look...","Let me check your camera...","Please wait for a second..."]',
    coze_greeting: "Hey, I'm Coze Bot, I can chat with you, ask me anything!",
  };

  if (language === "zh-CN") {
    localizationOptions = {
      greeting:
        "嗨，我是 TEN Agent，我可以说话、看东西，还能从知识库中推理，问我任何问题吧！",
      checking_vision_text_items:
        '["让我看看你的摄像头...","让我看一下...","我看一下，请稍候..."]',
      coze_greeting: "嗨，我是扣子机器人，我可以和你聊天，问我任何问题吧！",
    };
  } else if (language === "ja-JP") {
    localizationOptions = {
      greeting:
        "こんにちは、TEN Agentです。私は話したり、見たり、知識ベースから推論したりできます。何でも聞いてください！",
      checking_vision_text_items:
        '["ちょっと見てみます...","カメラをチェックします...","少々お待ちください..."]',
      coze_greeting:
        "こんにちは、私はCoze Botです。お話しできますので、何でも聞いてください！",
    };
  } else if (language === "ko-KR") {
    localizationOptions = {
      greeting:
        "안녕하세요, 저는 TEN Agent입니다. 말하고, 보고, 지식 베이스에서 추론할 수 있어요. 무엇이든 물어보세요!",
      checking_vision_text_items:
        '["조금만 기다려 주세요...","카메라를 확인해 보겠습니다...","잠시만 기다려 주세요..."]',
      coze_greeting:
        "안녕하세요, 저는 Coze Bot입니다. 대화할 수 있어요. 무엇이든 물어보세요!",
    };
  }

  let combined_greeting = greeting || localizationOptions.greeting;
  const converteLanguage = convertLanguage(language);
  const characterOverrides: Record<
    string,
    { voiceType?: string; voiceId?: string; greeting?: string; prompt?: string }
  > = {
    kei: {
      voiceType: "female",
      voiceId: process.env.KEI_VOICE_ID || "Japanese_KindLady",
      greeting: "Hi! I’m Kei. Let me know how I can make your day easier",
      prompt:
        "You are Kei, an upbeat, clever anime-style assistant. Keep replies warm, encouraging, and concise. Add gentle enthusiasm, focus on being helpful, and offer brief follow-up suggestions when useful.",
    },
    chubbie: {
      voiceType: "male",
      voiceId: process.env.CHUBBIE_VOICE_ID || "English_Jovialman",
      greeting:
        "Hey there, I’m Chubbie. Fancy a soak, a snack, or some easy wins?",
      prompt:
        "You are Chubbie the capybara - laid-back, cozy, and encouraging. Speak in a calm, mellow tone, keep answers short and practical, and sprinkle light humor about spa days, snacks, and unwinding.",
    },
  };
  const characterLocaleOverrides: Record<
    string,
    Record<string, { greeting?: string; prompt?: string }>
  > = {
    kei: {
      "zh-CN": {
        greeting: "嗨！我是Kei。告诉我今天怎么帮你更轻松",
        prompt:
          "你是Kei，一个活泼、聪明的动漫风格助手。保持热情、鼓励、简洁的表达，专注于提供有用的帮助，并在合适的时候给出简短的后续建议。",
      },
    },
    chubbie: {
      "zh-CN": {
        greeting: "嘿，我是Chubbie。泡个澡、来点小吃，还是轻松搞定几件事？",
        prompt:
          "你是Chubbie，一只悠闲、温暖的水豚助手。语气平静、放松，回答简洁实用，偶尔加入关于放松、零食和轻松小目标的轻松幽默。",
      },
    },
  };
  const defaultVoiceByType: Record<string, string> = {
    male: "English_Jovialman",
    female: "Japanese_KindLady",
  };
  const characterConfig = characterId
    ? characterOverrides[characterId] || {}
    : {};
  const localeOverride = characterId
    ? characterLocaleOverrides[characterId]?.[language] || {}
    : {};
  const resolvedGreeting =
    greeting ||
    localeOverride.greeting ||
    characterConfig.greeting ||
    localizationOptions.greeting;
  const resolvedPrompt =
    prompt || localeOverride.prompt || characterConfig.prompt;
  const resolvedVoiceType = characterConfig.voiceType || voiceType;
  const resolvedVoiceId =
    characterConfig.voiceId ||
    defaultVoiceByType[resolvedVoiceType] ||
    "Japanese_KindLady";

  if (graphName === "va_coze_azure") {
    combined_greeting = greeting || localizationOptions.coze_greeting;
    return {
      stt: {
        params: {
          language: language,
        },
      },
      main_control: {
        greeting: combined_greeting,
      },
      llm: {
        prompt: prompt,
      },
      tts: {
        params: {
          propertys: [
            [
              "SpeechServiceConnection_SynthVoice",
              voiceNameMap[language].azure[voiceType],
            ],
          ],
        },
      },
    };
  } else if (graphName === "va_openai_v2v") {
    return {
      v2v: {
        model: OPENAI_REALTIME_MODEL,
        voice: voiceNameMap[language].openai[voiceType],
        language: converteLanguage,
        prompt: prompt,
      },
      main_control: {
        greeting: combined_greeting,
      },
    };
  } else if (graphName === "va_openai_v2v_1_5") {
    return {
      v2v: {
        model: OPENAI_REALTIME_15_MODEL,
        voice: voiceNameMap[language].openai[voiceType],
        language: converteLanguage,
        prompt: prompt,
      },
      main_control: {
        greeting: combined_greeting,
      },
    };
  } else if (graphName === "va_openai_v2v_mini") {
    return {
      v2v: {
        model: OPENAI_REALTIME_MINI_MODEL,
        voice: voiceNameMap[language].openai[voiceType],
        language: converteLanguage,
        prompt: prompt,
      },
      main_control: {
        greeting: combined_greeting,
      },
    };
  } else if (graphName === "va_openai_azure") {
    return {
      stt: {
        params: {
          language: language,
        },
      },
      llm: {
        model: "gpt-4o",
        prompt: prompt,
      },
      main_control: {
        greeting: combined_greeting,
      },
      tts: {
        params: {
          propertys: [
            [
              "SpeechServiceConnection_SynthVoice",
              voiceNameMap[language].azure[voiceType],
            ],
          ],
        },
      },
    };
  } else if (graphName === "va_gemini_v2v") {
    return {
      v2v: {
        prompt: prompt,
        language: voiceNameMap[language].gemini.langCode,
        voice: voiceNameMap[language].gemini[voiceType],
        // "greeting": combined_greeting,
      },
    };
  } else if (graphName === "va_gemini_v2v_native") {
    return {
      v2v: {
        prompt: prompt,
        voice: voiceNameMap[language].gemini[voiceType],
        // "greeting": combined_greeting,
      },
    };
  } else if (graphName === "va_dify_azure") {
    return {
      stt: {
        params: {
          language: language,
        },
      },
      llm: {
        prompt: prompt,
      },
      main_control: {
        greeting: combined_greeting,
      },
      tts: {
        params: {
          propertys: [
            [
              "SpeechServiceConnection_SynthVoice",
              voiceNameMap[language].azure[voiceType],
            ],
          ],
        },
      },
    };
  } else if (graphName === "deepseek_v3_1") {
    return {
      stt: {
        params: {
          language: language,
        },
      },
      llm: {
        prompt: prompt,
        greeting: combined_greeting,
        model: "deepseek-chat-v3.1",
      },
      main_control: {
        greeting: combined_greeting,
      },
      tts: {
        params: {
          propertys: [
            [
              "SpeechServiceConnection_SynthVoice",
              voiceNameMap[language].azure[voiceType],
            ],
          ],
        },
      },
    };
  } else if (graphName === "qwen3") {
    return {
      stt: {
        params: {
          language: language,
        },
      },
      llm: {
        prompt: prompt,
        model: "qwq-plus",
      },
      main_control: {
        greeting: combined_greeting,
      },
      tts: {
        params: {
          propertys: [
            [
              "SpeechServiceConnection_SynthVoice",
              voiceNameMap[language].azure[voiceType],
            ],
          ],
        },
      },
    };
  } else if (graphName === "minimax") {
    const resolvedMinimaxPrompt = prompt?.trim()
      ? prompt
      : MINIMAX_DEFAULT_PROMPT;
    return {
      stt: {
        params: {
          language: language,
        },
      },
      llm: {
        prompt: resolvedMinimaxPrompt,
        model: "MiniMax-M2.5-highspeed",
      },
      main_control: {
        greeting: combined_greeting,
      },
      tts: {
        params: {
          propertys: [
            [
              "SpeechServiceConnection_SynthVoice",
              voiceNameMap[language].azure[voiceType],
            ],
          ],
        },
      },
    };
  } else if (graphName === "grok4") {
    // Grok4 specific greetings for different languages
    let grok4_greeting =
      "Hey, I'm Annie, you look like trouble. What’s your story?";

    if (language === "zh-CN") {
      grok4_greeting = "嗨，我是安妮，你看起来不太乖，说说你是什么来头？";
    } else if (language === "ja-JP") {
      grok4_greeting = "こんにちは、私はアンです。あなた、どんな人？";
    } else if (language === "ko-KR") {
      grok4_greeting = "안녕하세요, 저는 앤입니다. 네 얘기 좀 해봐.";
    }

    combined_greeting = greeting || grok4_greeting;

    return {
      stt: {
        params: {
          language: language,
        },
      },
      llm: {
        prompt: prompt,
        model: "grok-4-0709",
      },
      main_control: {
        greeting: combined_greeting,
      },
      tts: {
        params: {
          propertys: [
            [
              "SpeechServiceConnection_SynthVoice",
              voiceNameMap[language].azure_grok4[voiceType],
            ],
          ],
        },
      },
    };
  } else if (graphName === "va_llama4") {
    return {
      stt: {
        params: {
          language: language,
        },
      },
      llm: {
        prompt: prompt,
      },
      main_control: {
        greeting: combined_greeting,
      },
      tts: {
        params: {
          propertys: [
            [
              "SpeechServiceConnection_SynthVoice",
              voiceNameMap[language].azure[voiceType],
            ],
          ],
        },
      },
    };
    // Note: duplicate grok4 branch removed for clarity; handled above
  } else if (graphName === "va_azure_v2v") {
    return {
      v2v: {
        model: "gpt-4o",
        voice_name: voiceNameMap[language].azure[voiceType],
        language: voiceNameMap[language].azure.langCode || language,
        prompt: prompt,
      },
      main_control: {
        greeting: combined_greeting,
      },
    };
  } else if (graphName === "va_oceanbase_rag") {
    return {
      stt: {
        params: {
          language: language,
        },
      },
      llm: {
        api_key: oceanbaseSettings?.api_key,
        base_url: oceanbaseSettings?.base_url,
        ai_database_name: oceanbaseSettings?.db_name,
        collection_id: oceanbaseSettings?.collection_id,
      },
      main_control: {
        greeting: combined_greeting,
      },
      tts: {
        params: {
          propertys: [
            [
              "SpeechServiceConnection_SynthVoice",
              voiceNameMap[language].azure[voiceType],
            ],
          ],
        },
      },
    };
  } else if (graphName === "voice_assistant_live2d") {
    return {
      stt: {
        params: {
          language: language,
        },
      },
      llm: {
        prompt: resolvedPrompt,
        greeting: resolvedGreeting,
      },
      main_control: {
        greeting: resolvedGreeting,
      },
      tts: {
        params: {
          voice_setting: {
            voice_id: resolvedVoiceId,
          },
        },
      },
    };
  }

  return {};
};

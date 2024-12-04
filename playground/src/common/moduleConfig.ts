export namespace ModuleRegistry {
    export type ModuleType = "stt" | "llm" | "v2v" | "tts";
    export type ToolModuleType = "tool";

    export interface Module {
        name: string;
        type: ModuleType | ToolModuleType;
        label: string;
    }

    export type ToolModule = ModuleRegistry.Module & { type: "tool" };
}


// Custom labels for specific keys
export const ModuleTypeLabels: Record<ModuleRegistry.ModuleType, string> = {
    stt: "STT (Speech to Text)",
    llm: "LLM (Large Language Model)",
    tts: "TTS (Text to Speech)",
    v2v: "LLM v2v (V2V Large Language Model)",
};

export const sttModuleRegistry:Record<string, ModuleRegistry.Module> = {
    deepgram_asr_python: {
        name: "deepgram_asr_python",
        type: "stt",
        label: "Deepgram STT",
    },
    transcribe_asr_python: {
        name: "transcribe_asr_python",
        type: "stt",
        label: "Transcribe STT",
    }
}

export const llmModuleRegistry:Record<string, ModuleRegistry.Module> = {
    openai_chatgpt_python: {
        name: "openai_chatgpt_python",
        type: "llm",
        label: "OpenAI ChatGPT",
    },
    gemini_llm_python: {
        name: "gemini_llm_python",
        type: "llm",
        label: "Gemini LLM",
    },
    bedrock_llm_python: {
        name: "bedrock_llm_python",
        type: "llm",
        label: "Bedrock LLM",
    },
}

export const ttsModuleRegistry:Record<string, ModuleRegistry.Module> = {
    azure_tts: {
        name: "azure_tts",
        type: "tts",
        label: "Azure TTS",
    },
    cartesia_tts: {
        name: "cartesia_tts",
        type: "tts",
        label: "Cartesia TTS",
    },
    cosy_tts_python: {
        name: "cosy_tts_python",
        type: "tts",
        label: "Cosy TTS",
    },
    elevenlabs_tts_python: {
        name: "elevenlabs_tts_python",
        type: "tts",
        label: "Elevenlabs TTS",
    },
    fish_audio_tts: {
        name: "fish_audio_tts",
        type: "tts",
        label: "Fish Audio TTS",
    },
    minimax_tts_python: {
        name: "minimax_tts_python",
        type: "tts",
        label: "Minimax TTS",
    },
    polly_tts: {
        name: "polly_tts",
        type: "tts",
        label: "Polly TTS",
    }
}

export const v2vModuleRegistry:Record<string, ModuleRegistry.Module> = {
    openai_v2v_python: {
        name: "openai_v2v_python",
        type: "v2v",
        label: "OpenAI Realtime",
    }
}

export const toolModuleRegistry:Record<string, ModuleRegistry.ToolModule> = {
    vision_analyze_tool_python: {
        name: "vision_analyze_tool_python",
        type: "tool",
        label: "Vision Analyze Tool",
    },
    weatherapi_tool_python: {
        name: "weatherapi_tool_python",
        type: "tool",
        label: "WeatherAPI Tool",
    },
    bingsearch_tool_python: {
        name: "bingsearch_tool_python",
        type: "tool",
        label: "BingSearch Tool",
    },
    vision_tool_python: {
        name: "vision_tool_python",
        type: "tool",
        label: "Vision Tool",
    },
}

export const moduleRegistry: Record<string, ModuleRegistry.Module> = {
    ...sttModuleRegistry,
    ...llmModuleRegistry,
    ...ttsModuleRegistry,
    ...v2vModuleRegistry
}

export const compatibleTools: Record<string, string[]> = {
    openai_chatgpt_python: ["vision_tool_python", "weatherapi_tool_python", "bingsearch_tool_python"],
    openai_v2v_python: ["weatherapi_tool_python", "bingsearch_tool_python"],
}
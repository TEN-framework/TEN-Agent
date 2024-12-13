export namespace ModuleRegistry {
    export enum ModuleType {
        STT = "stt",
        LLM = "llm",
        V2V = "v2v",
        TTS = "tts",
        TOOL = "tool",
    }

    export interface Module {
        name: string;
        type: ModuleType;
        label: string;
    }

    export type NonToolModuleType = Exclude<ModuleType, ModuleType.TOOL>
    export type NonToolModule = Module & { type: NonToolModuleType };
    export type ToolModule = Module & { type: ModuleType.TOOL };
}


// Custom labels for specific keys
export const ModuleTypeLabels: Record<ModuleRegistry.NonToolModuleType, string> = {
    [ModuleRegistry.ModuleType.STT]: "STT (Speech to Text)",
    [ModuleRegistry.ModuleType.LLM]: "LLM (Large Language Model)",
    [ModuleRegistry.ModuleType.TTS]: "TTS (Text to Speech)",
    [ModuleRegistry.ModuleType.V2V]: "LLM v2v (V2V Large Language Model)",
};

export const sttModuleRegistry: Record<string, ModuleRegistry.Module> = {
    deepgram_asr_python: {
        name: "deepgram_asr_python",
        type: ModuleRegistry.ModuleType.STT,
        label: "Deepgram STT",
    },
    transcribe_asr_python: {
        name: "transcribe_asr_python",
        type: ModuleRegistry.ModuleType.STT,
        label: "Transcribe STT",
    }
}

export const llmModuleRegistry: Record<string, ModuleRegistry.Module> = {
    openai_chatgpt_python: {
        name: "openai_chatgpt_python",
        type: ModuleRegistry.ModuleType.LLM,
        label: "OpenAI ChatGPT",
    },
    gemini_llm_python: {
        name: "gemini_llm_python",
        type: ModuleRegistry.ModuleType.LLM,
        label: "Gemini LLM",
    },
    bedrock_llm_python: {
        name: "bedrock_llm_python",
        type: ModuleRegistry.ModuleType.LLM,
        label: "Bedrock LLM",
    },
}

export const ttsModuleRegistry: Record<string, ModuleRegistry.Module> = {
    azure_tts: {
        name: "azure_tts",
        type: ModuleRegistry.ModuleType.TTS,
        label: "Azure TTS",
    },
    cartesia_tts: {
        name: "cartesia_tts",
        type: ModuleRegistry.ModuleType.TTS,
        label: "Cartesia TTS",
    },
    cosy_tts_python: {
        name: "cosy_tts_python",
        type: ModuleRegistry.ModuleType.TTS,
        label: "Cosy TTS",
    },
    elevenlabs_tts_python: {
        name: "elevenlabs_tts_python",
        type: ModuleRegistry.ModuleType.TTS,
        label: "Elevenlabs TTS",
    },
    fish_audio_tts: {
        name: "fish_audio_tts",
        type: ModuleRegistry.ModuleType.TTS,
        label: "Fish Audio TTS",
    },
    minimax_tts_python: {
        name: "minimax_tts_python",
        type: ModuleRegistry.ModuleType.TTS,
        label: "Minimax TTS",
    },
    polly_tts: {
        name: "polly_tts",
        type: ModuleRegistry.ModuleType.TTS,
        label: "Polly TTS",
    }
}

export const v2vModuleRegistry: Record<string, ModuleRegistry.Module> = {
    openai_v2v_python: {
        name: "openai_v2v_python",
        type: ModuleRegistry.ModuleType.V2V,
        label: "OpenAI Realtime",
    },
    gemini_v2v_python: {
        name: "gemini_v2v_python",
        type: ModuleRegistry.ModuleType.V2V,
        label: "Gemini Realtime",
    }
}

export const toolModuleRegistry: Record<string, ModuleRegistry.ToolModule> = {
    vision_analyze_tool_python: {
        name: "vision_analyze_tool_python",
        type: ModuleRegistry.ModuleType.TOOL,
        label: "Vision Analyze Tool",
    },
    weatherapi_tool_python: {
        name: "weatherapi_tool_python",
        type: ModuleRegistry.ModuleType.TOOL,
        label: "WeatherAPI Tool",
    },
    bingsearch_tool_python: {
        name: "bingsearch_tool_python",
        type: ModuleRegistry.ModuleType.TOOL,
        label: "BingSearch Tool",
    },
    vision_tool_python: {
        name: "vision_tool_python",
        type: ModuleRegistry.ModuleType.TOOL,
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
    gemini_v2v_python: ["weatherapi_tool_python", "bingsearch_tool_python"],
}
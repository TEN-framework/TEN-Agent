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
    export enum Modalities {
        Video = "video",
        Audio = "audio",
        Text = "text"
    }
    export interface LLMModuleOptions {
        inputModalities: Modalities[]
    }
    export interface V2VModuleOptions {
        inputModalities: Modalities[]
    }
    // Extending Module to define LLMModule with options
    export interface LLMModule extends Module {
        type: ModuleType.LLM; // Ensuring it's specific to LLM
        options: LLMModuleOptions;
    }
    export interface V2VModule extends Module {
        type: ModuleType.V2V,
        options: LLMModuleOptions
    }
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

export const llmModuleRegistry: Record<string, ModuleRegistry.LLMModule> = {
    openai_chatgpt_python: {
        name: "openai_chatgpt_python",
        type: ModuleRegistry.ModuleType.LLM,
        label: "OpenAI ChatGPT",
        options: { inputModalities: [ModuleRegistry.Modalities.Text] }
    },
    dify_python: {
        name: "dify_python",
        type: ModuleRegistry.ModuleType.LLM,
        label: "Dify Chat Bot",
        options: { inputModalities: [ModuleRegistry.Modalities.Text] }
    },
    coze_python_async: {
        name: "coze_python_async",
        type: ModuleRegistry.ModuleType.LLM,
        label: "Coze Chat Bot",
        options: { inputModalities: [ModuleRegistry.Modalities.Text] }
    },
    gemini_llm_python: {
        name: "gemini_llm_python",
        type: ModuleRegistry.ModuleType.LLM,
        label: "Gemini LLM",
        options: { inputModalities: [ModuleRegistry.Modalities.Text] }
    },
    bedrock_llm_python: {
        name: "bedrock_llm_python",
        type: ModuleRegistry.ModuleType.LLM,
        label: "Bedrock LLM",
        options: { inputModalities: [ModuleRegistry.Modalities.Text, ModuleRegistry.Modalities.Video] }
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

export const v2vModuleRegistry: Record<string, ModuleRegistry.V2VModule> = {
    openai_v2v_python: {
        name: "openai_v2v_python",
        type: ModuleRegistry.ModuleType.V2V,
        label: "OpenAI Realtime",
        options: { inputModalities: [ModuleRegistry.Modalities.Audio] }
    },
    gemini_v2v_python: {
        name: "gemini_v2v_python",
        type: ModuleRegistry.ModuleType.V2V,
        label: "Gemini Realtime",
        options: { inputModalities: [ModuleRegistry.Modalities.Video, ModuleRegistry.Modalities.Audio] }
    },
    glm_v2v_python: {
        name: "glm_v2v_python",
        type: ModuleRegistry.ModuleType.V2V,
        label: "GLM Realtime",
        options: { inputModalities: [ModuleRegistry.Modalities.Audio] }
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
    openai_image_generate_tool: {
        name: "openai_image_generate_tool",
        type: ModuleRegistry.ModuleType.TOOL,
        label: "OpenAI Image Generate Tool",
    },
}

export const moduleRegistry: Record<string, ModuleRegistry.Module> = {
    ...sttModuleRegistry,
    ...llmModuleRegistry,
    ...ttsModuleRegistry,
    ...v2vModuleRegistry
}

export const compatibleTools: Record<string, string[]> = {
    openai_chatgpt_python: ["vision_tool_python", "weatherapi_tool_python", "bingsearch_tool_python", "openai_image_generate_tool"],
    openai_v2v_python: ["weatherapi_tool_python", "bingsearch_tool_python", "openai_image_generate_tool"],
    gemini_v2v_python: ["weatherapi_tool_python", "bingsearch_tool_python", "openai_image_generate_tool"],
    glm_v2v_python: ["weatherapi_tool_python", "bingsearch_tool_python", "openai_image_generate_tool"],
}

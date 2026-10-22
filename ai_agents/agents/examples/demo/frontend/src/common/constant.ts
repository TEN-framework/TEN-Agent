import type {
  ColorItem,
  GraphOptionItem,
  ICozeSettings,
  IDifySettings,
  IOceanBaseSettings,
  IOptions,
  LanguageOptionItem,
  VoiceOptionItem,
} from "@/types";
export const GITHUB_URL = "https://github.com/TEN-framework/TEN-Agent";
export const API_GH_GET_REPO_INFO =
  "https://api.github.com/repos/TEN-framework/TEN-Agent";
export const OPTIONS_KEY = "__options__";
export const AGENT_SETTINGS_KEY = "__agent_settings__";
export const COZE_SETTINGS_KEY = "__coze_settings__";
export const DIFY_SETTINGS_KEY = "__dify_settings__";
export const OCEANBASE_SETTINGS_KEY = "__oceanbase_settings__";

export const DEFAULT_OPTIONS: IOptions = {
  channel: "",
  userName: "",
  userId: 0,
  appId: "",
  token: "",
};

export const DEFAULT_AGENT_SETTINGS = {
  greeting: "",
  prompt: "",
};

export enum ECozeBaseUrl {
  CN = "https://api.coze.cn",
  GLOBAL = "https://api.coze.com",
}

export const DEFAULT_COZE_SETTINGS: ICozeSettings = {
  token: "",
  bot_id: "",
  base_url: ECozeBaseUrl.GLOBAL,
};

export const DEFAULT_DIFY_SETTINGS: IDifySettings = {
  api_key: "",
  base_url: "https://api.dify.ai/v1",
};

export const DEFAULT_OCEAN_BASE_SETTINGS: IOceanBaseSettings = {
  api_key: "",
  base_url: "",
  db_name: "",
  collection_id: "",
};

export const DESCRIPTION =
  "Multi-Purpose Voice Assistant Agent Example Powered by TEN";
export const LANGUAGE_OPTIONS: LanguageOptionItem[] = [
  {
    label: "English",
    value: "en-US",
  },
  {
    label: "Chinese",
    value: "zh-CN",
  },
  {
    label: "Korean",
    value: "ko-KR",
  },
  {
    label: "Japanese",
    value: "ja-JP",
  },
];
export const GROUPED_GRAPH_OPTIONS = {
  "Voice AI (STT + LLM + TTS)": [
    {
      label: "OpenAI GPT 5",
      value: "va_openai_azure",
    },
    {
      label: "Minimax M2.5 highspeed",
      value: "minimax",
    },
    // {
    //   label: "OpenAI Realtime + Custom STT/TTS",
    //   value: "va_openai_v2v_fish",
    // },
    {
      label: "Llama 4",
      value: "va_llama4",
    },
    {
      label: "Qwen 3 Reasoning",
      value: "qwen3",
    },
    {
      label: "OrcaRouter",
      value: "orcarouter",
    },
    // {
    //   label: "Grok 4 Reasoning",
    //   value: "grok4",
    // },
    // {
    //   label: "DeepSeek V3.1 Chat",
    //   value: "deepseek_v3_1",
    // },
  ],
  // "Multimodal Voice AI": [
  // {
  //   label: "Nova Multimodal",
  //   value: "va_nova_multimodal_aws",
  // },
  // ],
  "Speech to Speech Voice AI": [
    {
      label: "OpenAI GPT Realtime",
      value: "va_openai_v2v",
    },
    {
      label: "OpenAI GPT Realtime 1.5",
      value: "va_openai_v2v_1_5",
    },
    {
      label: "OpenAI GPT Realtime Mini",
      value: "va_openai_v2v_mini",
    },
    {
      label: "Gemini 2.0 Flash Live",
      value: "va_gemini_v2v",
    },
    {
      label: "Gemini 2.5 Flash Native Audio",
      value: "va_gemini_v2v_native",
    },
    {
      label: "Azure Voice AI API",
      value: "va_azure_v2v",
    },
  ],
  "AI Platform Integrations": [
    {
      label: "OceanBase PowerRAG",
      value: "va_oceanbase_rag",
    },
    {
      label: "Dify Agent",
      value: "va_dify_azure",
    },
    {
      label: "Coze Bot",
      value: "va_coze_azure",
    },
  ],
  // "Specialized Agents": [
  //   {
  //     label: "Story Teller with Image Generator",
  //     value: "story_teller_stt_integrated",
  //   },
  // Uncomment when needed
};

export const GRAPH_OPTIONS: GraphOptionItem[] = Object.values(
  GROUPED_GRAPH_OPTIONS
).flat();

export const isRagGraph = (graphName: string) => {
  return graphName === "va_qwen_rag";
};

export const isLanguageSupported = (graphName: string) => {
  return !["va_gemini_v2v_native"].includes(graphName);
};

// export const isVoiceGenderSupported = (graphName: string) => {
//   return !["va_gemini_v2v"].includes(graphName)
// }

export enum VideoSourceType {
  CAMERA = "camera",
  SCREEN = "screen",
}

export const VIDEO_SOURCE_OPTIONS = [
  {
    label: "Camera",
    value: VideoSourceType.CAMERA,
  },
  {
    label: "Screen Share",
    value: VideoSourceType.SCREEN,
  },
];

export const VOICE_OPTIONS: VoiceOptionItem[] = [
  {
    label: "Male",
    value: "male",
  },
  {
    label: "Female",
    value: "female",
  },
];
export const COLOR_LIST: ColorItem[] = [
  {
    active: "#0888FF",
    default: "#143354",
  },
  {
    active: "#563FD8",
    default: "#2C2553",
  },
  {
    active: "#18A957",
    default: "#173526",
  },
  {
    active: "#FFAB08",
    default: "#423115",
  },
  {
    active: "#FD5C63",
    default: "#462629",
  },
  {
    active: "#E225B2",
    default: "#481C3F",
  },
];

export type VoiceTypeMap = {
  [voiceType: string]: string;
};

export type VendorNameMap = {
  [vendorName: string]: VoiceTypeMap;
};

export type LanguageMap = {
  [language: string]: VendorNameMap;
};

export enum EMobileActiveTab {
  AGENT = "agent",
  CHAT = "chat",
}

export const MOBILE_ACTIVE_TAB_MAP = {
  [EMobileActiveTab.AGENT]: "Agent",
  [EMobileActiveTab.CHAT]: "Chat",
};

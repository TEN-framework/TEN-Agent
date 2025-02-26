import {
  IOptions,
  ColorItem,
  LanguageOptionItem,
  VoiceOptionItem,
  GraphOptionItem,
  ICozeSettings,
  IDifySettings,
} from "@/types"
export const GITHUB_URL = "https://github.com/TEN-framework/TEN-Agent"
export const API_GH_GET_REPO_INFO =
  "https://api.github.com/repos/TEN-framework/TEN-Agent"
export const OPTIONS_KEY = "__options__"
export const AGENT_SETTINGS_KEY = "__agent_settings__"
export const COZE_SETTINGS_KEY = "__coze_settings__"
export const DIFY_SETTINGS_KEY = "__dify_settings__"
export const DEFAULT_OPTIONS: IOptions = {
  channel: "",
  userName: "",
  userId: 0,
  appId: "",
  token: "",
}

export const DEFAULT_AGENT_SETTINGS = {
  greeting: "",
  prompt: "",
}

export enum ECozeBaseUrl {
  CN = "https://api.coze.cn",
  GLOBAL = "https://api.coze.com",
}

export const DEFAULT_COZE_SETTINGS: ICozeSettings = {
  token: "",
  bot_id: "",
  base_url: ECozeBaseUrl.GLOBAL,
}

export const DEFAULT_DIFY_SETTINGS: IDifySettings = {
  api_key: "",
}

export const DESCRIPTION = "A Realtime Conversational AI Agent powered by TEN"
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
]
export const GRAPH_OPTIONS: GraphOptionItem[] = [
  {
    label: "Voice Agent with DeepSeek R1 Reasoning",
    value: "deepseek_r1",
  },
  {
    label: "Voice Agent Gemini 2.0 Realtime",
    value: "va_gemini_v2v",
  },
  {
    label: "Voice Agent with Dify",
    value: "va_dify_azure",
  },
  {
    label: "Voice Agent / STT + LLM + TTS",
    value: "va_openai_azure",
  },
  // {
  //   label: "Voice Agent with Knowledge - RAG + Qwen LLM + Cosy TTS",
  //   value: "va_qwen_rag"
  // },
  {
    label: "Voice Agent OpenAI Realtime",
    value: "va_openai_v2v",
  },
  {
    label: "Voice Agent OpenAI Realtime + Custom STT/TTS",
    value: "va_openai_v2v_fish",
  },
  {
    label: "Voice Agent Coze Bot + Azure TTS",
    value: "va_coze_azure",
  },
  {
    label: "Voice Story Teller with Image Generator",
    value: "story_teller_stt_integrated",
  },
  {
    label: "Voice Agent / STT + Nova Multimodal + TTS",
    value: "va_nova_multimodal_aws",
  },
]

export const isRagGraph = (graphName: string) => {
  return graphName === "va_qwen_rag"
}

export const isLanguageSupported = (graphName: string) => {
  return !["va_gemini_v2v"].includes(graphName)
}

export const isVoiceGenderSupported = (graphName: string) => {
  return !["va_gemini_v2v"].includes(graphName)
}


export enum VideoSourceType {
  CAMERA = 'camera',
  SCREEN = 'screen',
}

export const VIDEO_SOURCE_OPTIONS = [{
  label: "Camera",
  value: VideoSourceType.CAMERA,
}, {
  label: "Screen Share",
  value: VideoSourceType.SCREEN,
}]

export const VOICE_OPTIONS: VoiceOptionItem[] = [
  {
    label: "Male",
    value: "male",
  },
  {
    label: "Female",
    value: "female",
  },
]
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
]

export type VoiceTypeMap = {
  [voiceType: string]: string
}

export type VendorNameMap = {
  [vendorName: string]: VoiceTypeMap
}

export type LanguageMap = {
  [language: string]: VendorNameMap
}

export enum EMobileActiveTab {
  AGENT = "agent",
  CHAT = "chat",
}

export const MOBILE_ACTIVE_TAB_MAP = {
  [EMobileActiveTab.AGENT]: "Agent",
  [EMobileActiveTab.CHAT]: "Chat",
}
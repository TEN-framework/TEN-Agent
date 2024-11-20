import {
  IOptions,
  ColorItem,
  LanguageOptionItem,
  VoiceOptionItem,
  GraphOptionItem,
  ICozeSettings,
} from "@/types"
export const GITHUB_URL = "https://github.com/TEN-framework/TEN-Agent"
export const OPTIONS_KEY = "__options__"
export const AGENT_SETTINGS_KEY = "__agent_settings__"
export const COZE_SETTINGS_KEY = "__coze_settings__"
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
  CN = "api.coze.cn",
  GLOBAL = "api.coze.com",
}

export const DEFAULT_COZE_SETTINGS: ICozeSettings = {
  token: "",
  bot_id: "",
  base_url: ECozeBaseUrl.GLOBAL,
}

export const DESCRIPTION =
  "The World's First Multimodal AI Agent with the OpenAI Realtime API (Beta)"
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
    label: "Voice Agent - OpenAI LLM + Azure TTS",
    value: "va_openai_azure",
  },
  {
    label: "Voice Agent with Vision - OpenAI LLM + Azure TTS",
    value: "camera_va_openai_azure",
  },
  // {
  //   label: "Voice Agent with Knowledge - RAG + Qwen LLM + Cosy TTS",
  //   value: "va_qwen_rag"
  // },
  {
    label: "Voice Agent with OpenAI Realtime API (Beta)",
    value: "va_openai_v2v",
  },
  {
    label: "Voice Agent with OpenAI Realtime API (Beta) + FishAudio TTS",
    value: "va_openai_v2v_fish",
  },
  {
    label: "Voice Agent with Vision - OpenAI LLM + Azure TTS + RTM",
    value: "camera_va_openai_azure_rtm",
  },
  {
    label: "Voice Agent Coze Bot + Azure TTS",
    value: "va_coze_azure",
  },
]

export const isRagGraph = (graphName: string) => {
  return graphName === "va_qwen_rag"
}

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

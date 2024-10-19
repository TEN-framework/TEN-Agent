import { IOptions, ColorItem, LanguageOptionItem, VoiceOptionItem, GraphOptionItem } from "@/types"
export const GITHUB_URL = "https://github.com/TEN-framework/TEN-Agent"
export const OPTIONS_KEY = "__options__"
export const DEFAULT_OPTIONS: IOptions = {
  channel: "",
  userName: "",
  userId: 0
}
export const DESCRIPTION = "TEN Agent is an open-source multimodal AI agent that can speak, see, and access a knowledge base(RAG)."
export const LANGUAGE_OPTIONS: LanguageOptionItem[] = [
  {
    label: "English",
    value: "en-US"
  },
  {
    label: "Chinese",
    value: "zh-CN"
  },
  {
    label: "Korean",
    value: "ko-KR"
  },
  {
    label: "Japanese",
    value: "ja-JP"
  }
]
export const GRAPH_OPTIONS: GraphOptionItem[] = [
  {
    label: "Voice Agent - OpenAI LLM + Azure TTS",
    value: "va_openai_azure"
  },
  {
    label: "Voice Agent with Vision - OpenAI LLM + Azure TTS",
    value: "camera_va_openai_azure"
  },
  //{
  //  label: "Voice Agent with Knowledge - RAG + Qwen LLM + Cosy TTS",
  //  value: "va_qwen_rag"
  // },
]

export const isRagGraph = (graphName: string) => {
  return graphName === "va_qwen_rag"
}

export const VOICE_OPTIONS: VoiceOptionItem[] = [
  {
    label: "Male",
    value: "male"
  },
  {
    label: "Female",
    value: "female"
  }
]
export const COLOR_LIST: ColorItem[] = [{
  active: "#0888FF",
  default: "#143354"
}, {
  active: "#563FD8",
  default: "#2C2553"
},
{
  active: "#18A957",
  default: "#173526"
}, {
  active: "#FFAB08",
  default: "#423115"
}, {
  active: "#FD5C63",
  default: "#462629"
}, {
  active: "#E225B2",
  default: "#481C3F"
}]

export type VoiceTypeMap = {
  [voiceType: string]: string;
};

export type VendorNameMap = {
  [vendorName: string]: VoiceTypeMap;
};

export type LanguageMap = {
  [language: string]: VendorNameMap;
};

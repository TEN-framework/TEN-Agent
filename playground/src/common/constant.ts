import { IOptions, ColorItem } from "@/types"

export const REQUEST_URL = process.env.NEXT_PUBLIC_REQUEST_URL ?? ""
export const GITHUB_URL = "https://github.com/rte-design/ASTRA.ai"
export const OPTIONS_KEY = "__options__"
export const DEFAULT_OPTIONS: IOptions = {
  channel: "",
  userName: "",
  userId: 0
}
export const DESCRIPTION = "This is an AI voice assistant powered by ASTRA.ai framework, Agora, Azure and ChatGPT."
export const LANG_OPTIONS = [
  {
    label: "English",
    value: "en-US"
  },
  {
    label: "Chinese",
    value: "zh-CN"
  }
]
export const VOICE_OPTIONS = [
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
  default: "#112941"
}, {
  active: "#563FD8",
  default: "#221C40"
},
{
  active: "#18A957",
  default: "#112A1E"
}, {
  active: "#FFAB08",
  default: "#392B13"
}, {
  active: "#FD5C63",
  default: "#3C2023"
}, {
  active: "#E225B2",
  default: "#371530"
}]


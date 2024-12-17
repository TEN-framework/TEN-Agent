export type Language = "en-US" | "zh-CN" | "ja-JP" | "ko-KR"
export type VoiceType = "male" | "female"

export interface ColorItem {
  active: string
  default: string
}

export interface IOptions {
  channel: string
  userName: string
  userId: number
  appId: string
  token: string
}

export interface IAgentSettings {
  prompt: string
  greeting: string
}

export interface ICozeSettings {
  token: string
  bot_id: string
  base_url: string
}


export interface IDifySettings {
  api_key: string
}

export enum EMessageType {
  AGENT = "agent",
  USER = "user",
}

export interface IChatItem {
  userId: number | string
  userName?: string
  text: string
  type: EMessageType
  isFinal?: boolean
  time: number
}

/** @deprecated */
export interface ITextItem {
  dataType: "transcribe" | "translate"
  uid: string
  time: number
  text: string
  isFinal: boolean
}

export enum ERTMTextType {
  TRANSCRIBE = "transcribe",
  TRANSLATE = "translate",
  INPUT_TEXT = "input_text",
  INPUT_IMAGE = "input_image",
  INPUT_AUDIO = "input_audio",
  INPUT_FILE = "input_file",
}

export interface IRTMTextItem {
  is_final: boolean
  type: ERTMTextType
  ts: number
  text: string
  stream_id: string
}

export interface GraphOptionItem {
  label: string
  value: string
}

export interface LanguageOptionItem {
  label: string
  value: Language
}

export interface VoiceOptionItem {
  label: string
  value: VoiceType
}

export interface OptionType {
  value: string
  label: string
}

export interface IPdfData {
  fileName: string
  collection: string
}

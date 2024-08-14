export type Language = "en-US" | "zh-CN"
export type VoiceType = "male" | "female"

export interface ColorItem {
  active: string,
  default: string
}


export interface IOptions {
  channel: string,
  userName: string,
  userId: number
}


export interface IChatItem {
  userId: number | string,
  userName?: string,
  text: string
  type: "agent" | "user"
  isFinal?: boolean
  time: number
}


export interface ITextItem {
  dataType: "transcribe" | "translate"
  uid: string
  language: string
  time: number
  text: string
  isFinal: boolean
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
  value: string;
  label: string;
}


export interface IPdfData {
  fileName: string,
  collection: string
}


export type Language = "en-US" | "zh-CN" | "ja-JP" | "ko-KR";
export type VoiceType = "male" | "female";

export interface ColorItem {
  active: string;
  default: string;
}

export interface IOptions {
  channel: string;
  userName: string;
  userId: number;
  appId: string;
  token: string;
  spatialwalkToken: string;
}

export interface IAgentSettings {
  prompt: string;
  greeting: string;
}

export interface ISpatialwalkSettings {
  enabled: boolean;
  avatarId: string;
  appId: string;
  environment: "cn" | "intl";
  avatarDesktopLargeWindow: boolean;
}

export type FestivalEffectName = "gold_rain" | "fireworks";

export interface IFestivalEffect {
  name: FestivalEffectName;
  active: boolean;
  nonce: number;
}

export interface IFortuneModal {
  open: boolean;
  imageId: string;
}

export enum EMessageType {
  AGENT = "agent",
  USER = "user",
}

export enum EMessageDataType {
  TEXT = "text",
  REASON = "reason",
  IMAGE = "image",
}

export interface IChatItem {
  userId: number | string;
  userName?: string;
  text: string;
  data_type: EMessageDataType;
  type: EMessageType;
  isFinal?: boolean;
  time: number;
}

/** @deprecated */
export interface ITextItem {
  dataType: "transcribe" | "translate" | "image_url";
  uid: string;
  time: number;
  text: string;
  isFinal: boolean;
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
  is_final: boolean;
  data_type: string;
  role?: "user" | "assistant";
  text_ts: number;
  text: string;
  stream_id: number;
}

export interface GraphOptionItem {
  label: string;
  value: string;
}

export interface LanguageOptionItem {
  label: string;
  value: Language;
}

export interface VoiceOptionItem {
  label: string;
  value: VoiceType;
}

export interface OptionType {
  value: string;
  label: string;
}

export interface IPdfData {
  fileName: string;
  collection: string;
}

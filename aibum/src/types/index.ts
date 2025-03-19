export enum EMessageType {
  USER = 'user',
  AGENT = 'agent',
  SYSTEM = 'system'
}

export enum EMessageDataType {
  TEXT = 'text',
  IMAGE = 'image',
  REASON = 'reason'
}

export interface ITextItem {
  type: EMessageType;
  time: number;
  text: string;
  data_type: EMessageDataType;
  userId: string | number;
  isFinal: boolean;
}

export type Language = 'zh-CN' | 'en-US'; 
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


"use client"

import AgoraRTM, { type RTMClient, type RTMStreamChannel } from "agora-rtm"
import { AGEventEmitter } from "../events"
import { apiGenAgoraData } from "@/common"
import { type IRTMTextItem, ERTMTextType } from "@/types"

export interface IRtmEvents {
  textChanged: (text: any) => void // TODO: update type
}

export type TRTMMessageEvent = {
  channelType: "STREAM" | "MESSAGE" | "USER"
  channelName: string
  topicName?: string
  messageType: "STRING" | "BINARY"
  customType?: string
  publisher: string
  message: string | Uint8Array
  timestamp: number
}

export const DEFAULT_TOPIC = "chat"

export class RtmManager extends AGEventEmitter<IRtmEvents> {
  private _joined: boolean
  private _client: RTMClient | null
  channel: string = ""
  userId: number = 0
  appId: string = ""
  token: string = ""

  constructor() {
    super()
    this._joined = false
    this._client = null
  }

  async init({
    channel,
    userId,
    appId,
    token,
  }: {
    channel: string
    userId: number
    appId: string
    token: string
  }) {
    if (this._joined) {
      return
    }
    this.channel = channel
    this.userId = userId
    this.appId = appId
    this.token = token
    const rtm = new AgoraRTM.RTM(appId, String(userId), {
      logLevel: "debug", // TODO: use INFO
      // update config: https://doc.shengwang.cn/api-ref/rtm2/javascript/toc-configuration/configuration#rtmConfig
    })
    await rtm.login({ token })
    try {
      // subscribe message channel(will be created automatically)
      const subscribeResult = await rtm.subscribe(channel, {
        withMessage: true,
        withPresence: true,
        beQuiet: false,
        withMetadata: true,
        withLock: true,
      })
      console.log("[RTM] Subscribe Message Channel success!: ", subscribeResult)

      this._joined = true
      this._client = rtm

      // listen events
      this._listenRtmEvents()
    } catch (status) {
      console.error("Failed to Create/Join Message Channel", status)
    }
  }

  private _listenRtmEvents() {
    this._client!.addEventListener("message", this.handleRtmMessage)
    // tmp add presence
    this._client!.addEventListener("presence", this.handleRtmPresence)
    console.log("[RTM] Listen RTM events success!")
  }

  async handleRtmMessage(e: TRTMMessageEvent) {
    console.log("[RTM] [TRTMMessageEvent] RAW", JSON.stringify(e))
    const { message, messageType } = e
    if (messageType === "STRING") {
      const msg: IRTMTextItem = JSON.parse(message as string)
      this.emit("textChanged", msg)
    }
    if (messageType === "BINARY") {
      const decoder = new TextDecoder("utf-8")
      const decodedMessage = decoder.decode(message as Uint8Array)
      const msg: IRTMTextItem = JSON.parse(decodedMessage)
      this.emit("textChanged", msg)
    }
  }

  async handleRtmPresence(e: any) {
    console.log("[RTM] [TRTMPresenceEvent] RAW", JSON.stringify(e))
  }

  async sendText(text: string) {
    const msg: IRTMTextItem = {
      is_final: true,
      ts: Date.now(),
      text,
      type: ERTMTextType.INPUT_TEXT,
    }
    await this._client?.publish(this.channel, JSON.stringify(msg), {
      customType: "PainTxt",
    })
    this.emit("textChanged", msg)
  }

  async destroy() {
    // remove listener
    this._client?.removeEventListener("message", this.handleRtmMessage)
    this._client?.removeEventListener("presence", this.handleRtmPresence)
    // unsubscribe
    await this._client?.unsubscribe(this.channel)
    // logout
    await this._client?.logout()

    this._client = null
    this._joined = false
  }
}

export const rtmManager = new RtmManager()

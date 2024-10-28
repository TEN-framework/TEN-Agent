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
  private _stChannel: RTMStreamChannel | null
  protected TOPIC = DEFAULT_TOPIC

  constructor() {
    super()
    this._joined = false
    this._client = null
    this._stChannel = null
  }

  private async _getRemoteConfig({
    channel,
    userId,
  }: {
    channel: string
    userId: number
  }) {
    // const res = await apiGenAgoraData({ channel, userId })
    // const { code, data } = res ?? {}
    // if (code != 0) {
    //   throw new Error("Failed to get Agora token")
    // }
    // TODO: remove this
    const data = {
      appId: "123",
      token: "456",
    }
    const { appId, token } = data
    return { appId, token }
  }

  async init({ channel, userId }: { channel: string; userId: number }) {
    if (this._joined) {
      return
    }
    const { appId, token } = await this._getRemoteConfig({ channel, userId })
    const rtm = new AgoraRTM.RTM(appId, String(userId), {
      logLevel: "debug", // TODO: use INFO
      // update config: https://doc.shengwang.cn/api-ref/rtm2/javascript/toc-configuration/configuration#rtmConfig
    })
    await rtm.login({ token })
    try {
      // create StreamChannel
      const stChannel = await rtm.createStreamChannel(channel)
      console.log("Create Stream Channel success!: ", channel)
      // join StreamChannel
      const stJoinResult = await stChannel.join({
        token: token,
        withPresence: true,
        beQuiet: false,
        withMetadata: false,
        withLock: false,
      })
      console.log("Join Stream Channel success!: ", stJoinResult)
      // join topic: max 64 subscribtions
      const topicJoinResult = await stChannel.joinTopic(this.TOPIC)
      console.log("Join Topic success!: ", topicJoinResult)

      this._joined = true
      this._client = rtm
      this._stChannel = stChannel

      // listen events
      this._listenRtmEvents()
    } catch (status) {
      console.error("Failed to Create/Join Stream Channel", status)
    }
  }

  private _listenRtmEvents() {
    this._client?.on("message", this.handleRtmMessage)
  }

  async handleRtmMessage(e: TRTMMessageEvent) {
    console.log("[TRTMMessageEvent] RAW", JSON.stringify(e))
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

  async sendText(text: string) {
    const msg: IRTMTextItem = {
      is_final: true,
      ts: Date.now(),
      text,
      type: ERTMTextType.INPUT_TEXT,
    }
    await this._stChannel?.publishTopicMessage(
      this.TOPIC,
      JSON.stringify(msg),
      { customType: "PainTxt" },
    )
    this.emit("textChanged", msg)
  }

  async destory() {
    // remove listener
    this._client?.removeEventListener("message", this.handleRtmMessage)
    // leave topic
    await this._stChannel?.leaveTopic(this.TOPIC)
    // leave StreamChannel
    await this._stChannel?.leave()
    // logout
    await this._client?.logout()

    this._client = null
    this._stChannel = null
    this._joined = false
  }
}

export const rtmManager = new RtmManager()

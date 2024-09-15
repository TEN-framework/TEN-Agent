"use client"

import protoRoot from "@/protobuf/SttMessage_es6.js"
import AgoraRTC, {
  IAgoraRTCClient,
  IMicrophoneAudioTrack,
  IRemoteAudioTrack,
  UID,
} from "agora-rtc-sdk-ng"
import { ITextItem } from "@/types"
import { AGEventEmitter } from "../events"
import { RtcEvents, IUserTracks } from "./types"
import { apiGenAgoraData } from "@/common"

export class RtcManager extends AGEventEmitter<RtcEvents> {
  private _joined
  client: IAgoraRTCClient
  localTracks: IUserTracks

  constructor() {
    super()
    this._joined = false
    this.localTracks = {}
    this.client = AgoraRTC.createClient({ mode: "rtc", codec: "vp8" })
    this._listenRtcEvents()
  }

  async join({ channel, userId }: { channel: string; userId: number }) {
    if (!this._joined) {
      const res = await apiGenAgoraData({ channel, userId })
      const { code, data } = res
      if (code != 0) {
        throw new Error("Failed to get Agora token")
      }
      const { appId, token } = data
      await this.client?.join(appId, channel, token, userId)
      this._joined = true
    }
  }

  async createTracks() {
    try {
      const videoTrack = await AgoraRTC.createCameraVideoTrack()
      this.localTracks.videoTrack = videoTrack
    } catch (err) {
      console.error("Failed to create video track", err)
    }
    try {
      const audioTrack = await AgoraRTC.createMicrophoneAudioTrack()
      this.localTracks.audioTrack = audioTrack
    } catch (err) {
      console.error("Failed to create audio track", err)
    }
    this.emit("localTracksChanged", this.localTracks)
  }

  async publish() {
    const tracks = []
    if (this.localTracks.videoTrack) {
      tracks.push(this.localTracks.videoTrack)
    }
    if (this.localTracks.audioTrack) {
      tracks.push(this.localTracks.audioTrack)
    }
    if (tracks.length) {
      await this.client.publish(tracks)
    }
  }

  async destroy() {
    this.localTracks?.audioTrack?.close()
    this.localTracks?.videoTrack?.close()
    if (this._joined) {
      await this.client?.leave()
    }
    this._resetData()
  }

  // ----------- public methods ------------

  // -------------- private methods --------------
  private _listenRtcEvents() {
    this.client.on("network-quality", (quality) => {
      this.emit("networkQuality", quality)
    })
    this.client.on("user-published", async (user, mediaType) => {
      await this.client.subscribe(user, mediaType)
      if (mediaType === "audio") {
        this._playAudio(user.audioTrack)
      }
      this.emit("remoteUserChanged", {
        userId: user.uid,
        audioTrack: user.audioTrack,
        videoTrack: user.videoTrack,
      })
    })
    this.client.on("user-unpublished", async (user, mediaType) => {
      await this.client.unsubscribe(user, mediaType)
      this.emit("remoteUserChanged", {
        userId: user.uid,
        audioTrack: user.audioTrack,
        videoTrack: user.videoTrack,
      })
    })
    this.client.on("stream-message", (uid: UID, stream: any) => {
      this._praseData(stream)
    })
  }

  private _praseData(data: any): ITextItem | void {
    // @ts-ignore
    // const textstream = protoRoot.Agora.SpeechToText.lookup("Text").decode(data)
    // if (!textstream) {
    //   return console.warn("Prase data failed.")
    // }
    let decoder = new TextDecoder('utf-8')
    let decodedMessage = decoder.decode(data)

    const textstream = JSON.parse(decodedMessage)

    console.log("[test] textstream raw data", JSON.stringify(textstream))
    const { stream_id, is_final, text, text_ts, data_type } = textstream
    let textStr: string = ""
    let isFinal = false
    const textItem: ITextItem = {} as ITextItem
    textItem.uid = stream_id
    textItem.time = text_ts
    // switch (dataType) {
    //   case "transcribe":
    //     words.forEach((word: any) => {
    //       textStr += word.text
    //       if (word.isFinal) {
    //         isFinal = true
    //       }
    //     })
    textItem.dataType = "transcribe"
    // textItem.language = culture
    textItem.text = text
    textItem.isFinal = is_final
    this.emit("textChanged", textItem)
    // break
    // case "translate":
    //   if (!trans?.length) {
    //     return
    //   }
    //   trans.forEach((transItem: any) => {
    //     textStr = transItem.texts.join("")
    //     isFinal = !!transItem.isFinal
    //     textItem.dataType = "translate"
    //     textItem.language = transItem.lang
    //     textItem.isFinal = isFinal
    //     textItem.text = textStr
    //     this.emit("textChanged", textItem)
    //   })
    //   break
    // }
  }


  _playAudio(audioTrack: IMicrophoneAudioTrack | IRemoteAudioTrack | undefined) {
    if (audioTrack && !audioTrack.isPlaying) {
      audioTrack.play()
    }
  }


  private _resetData() {
    this.localTracks = {}
    this._joined = false
  }
}


export const rtcManager = new RtcManager()

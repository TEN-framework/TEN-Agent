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


const TIMEOUT_MS = 5000; // Timeout for incomplete messages

interface TextDataChunk {
  message_id: string;
  part_index: number;
  total_parts: number;
  content: string;
}

export class RtcManager extends AGEventEmitter<RtcEvents> {
  private _joined
  client: IAgoraRTCClient
  localTracks: IUserTracks
  appId: string | null = null
  token: string | null = null

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
      this.appId = appId
      this.token = token
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
      this._parseData(stream)
    })
  }

  private _parseData(data: any): ITextItem | void {
    let decoder = new TextDecoder('utf-8');
    let decodedMessage = decoder.decode(data);
  
    console.log("[test] textstream raw data", decodedMessage);
    
    // const { stream_id, is_final, text, text_ts, data_type, message_id, part_number, total_parts } = textstream;
  
    // if (total_parts > 0) {
    //   // If message is split, handle it accordingly
    //   this._handleSplitMessage(message_id, part_number, total_parts, stream_id, is_final, text, text_ts);
    // } else {
    //   // If there is no message_id, treat it as a complete message
    //   this._handleCompleteMessage(stream_id, is_final, text, text_ts);
    // }

    this.handleChunk(decodedMessage);
  }
  

  private messageCache: { [key: string]: TextDataChunk[] } = {};

  // Function to process received chunk via event emitter
  handleChunk(formattedChunk: string) {
    try {
      // Split the chunk by the delimiter "|"
      const [message_id, partIndexStr, totalPartsStr, content] = formattedChunk.split('|');

      const part_index = parseInt(partIndexStr, 10);
      const total_parts = totalPartsStr === '???' ? -1 : parseInt(totalPartsStr, 10); // -1 means total parts unknown

      // Ensure total_parts is known before processing further
      if (total_parts === -1) {
        console.warn(`Total parts for message ${message_id} unknown, waiting for further parts.`);
        return;
      }

      const chunkData: TextDataChunk = {
        message_id,
        part_index,
        total_parts,
        content,
      };

      // Check if we already have an entry for this message
      if (!this.messageCache[message_id]) {
        this.messageCache[message_id] = [];
        // Set a timeout to discard incomplete messages
        setTimeout(() => {
          if (this.messageCache[message_id]?.length !== total_parts) {
            console.warn(`Incomplete message with ID ${message_id} discarded`);
            delete this.messageCache[message_id]; // Discard incomplete message
          }
        }, TIMEOUT_MS);
      }

      // Cache this chunk by message_id
      this.messageCache[message_id].push(chunkData);

      // If all parts are received, reconstruct the message
      if (this.messageCache[message_id].length === total_parts) {
        const completeMessage = this.reconstructMessage(this.messageCache[message_id]);
        const { stream_id, is_final, text, text_ts } = JSON.parse(atob(completeMessage));
        const textItem: ITextItem = {
          uid: `${stream_id}`,
          time: text_ts,
          dataType: "transcribe",
          text: text,
          isFinal: is_final
        };

        if (text.trim().length > 0) {
          this.emit("textChanged", textItem);
        }


        // Clean up the cache
        delete this.messageCache[message_id];
      }
    } catch (error) {
      console.error('Error processing chunk:', error);
    }
  }

  // Function to reconstruct the full message from chunks
  reconstructMessage(chunks: TextDataChunk[]): string {
    // Sort chunks by their part index
    chunks.sort((a, b) => a.part_index - b.part_index);

    // Concatenate all chunks to form the full message
    return chunks.map(chunk => chunk.content).join('');
  }

  _playAudio(
    audioTrack: IMicrophoneAudioTrack | IRemoteAudioTrack | undefined,
  ) {
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

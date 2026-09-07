"use client";

import type {
  IAgoraRTCClient,
  IMicrophoneAudioTrack,
  IRemoteAudioTrack,
  NetworkQuality,
  UID,
} from "agora-rtc-sdk-ng";
import { apiGenAgoraData, apiGenSpatialwalkToken } from "@/common";
import {
  EMessageDataType,
  EMessageType,
  type IChatItem,
  type ITextItem,
} from "@/types";
import { AGEventEmitter } from "../events";
import type { IUserTracks, RtcEvents } from "./types";

const TIMEOUT_MS = 5000; // Timeout for incomplete messages

interface TextDataChunk {
  message_id: string;
  part_index: number;
  total_parts: number;
  content: string;
}

interface NativeClientWaiter {
  resolve: (client: IAgoraRTCClient) => void;
  reject: (error: Error) => void;
  timeoutId: ReturnType<typeof setTimeout>;
}

let cachedAgoraRTC: any = null;
const getAgoraRTC = async () => {
  if (cachedAgoraRTC) {
    return cachedAgoraRTC;
  }
  const mod = await import("agora-rtc-sdk-ng");
  cachedAgoraRTC = mod.default ?? mod;
  return cachedAgoraRTC;
};

export class RtcManager extends AGEventEmitter<RtcEvents> {
  client: IAgoraRTCClient | null;
  localTracks: IUserTracks;
  appId: string | null = null;
  token: string | null = null;
  spatialwalkToken: string | null = null;
  userId: number | null = null;

  private _boundClient: IAgoraRTCClient | null;
  private _attachKey: string | null;
  private _nativeClientWaiters: NativeClientWaiter[];

  constructor() {
    super();
    this.localTracks = {};
    this.client = null;
    this._boundClient = null;
    this._attachKey = null;
    this._nativeClientWaiters = [];
  }

  async prepareSession({
    channel,
    userId,
    enableSpatialwalk,
  }: {
    channel: string;
    userId: number;
    enableSpatialwalk: boolean;
  }) {
    let rtcRes: any;

    if (enableSpatialwalk) {
      const [rtcTokenResult, spatialwalkTokenResult] = await Promise.allSettled([
        apiGenAgoraData({ channel, userId }),
        apiGenSpatialwalkToken({ channel, userId }),
      ]);

      if (rtcTokenResult.status === "rejected") {
        throw rtcTokenResult.reason;
      }
      rtcRes = rtcTokenResult.value;

      if (spatialwalkTokenResult.status === "fulfilled") {
        const { code, data } = spatialwalkTokenResult.value || {};
        if (code == 0) {
          this.spatialwalkToken = data?.token ?? "";
        } else {
          console.warn(
            "[rtc] failed to get spatialwalk token, continue without avatar token",
            spatialwalkTokenResult.value
          );
          this.spatialwalkToken = "";
        }
      } else {
        console.warn(
          "[rtc] spatialwalk token request failed, continue without avatar token",
          spatialwalkTokenResult.reason
        );
        this.spatialwalkToken = "";
      }
    } else {
      rtcRes = await apiGenAgoraData({ channel, userId });
      this.spatialwalkToken = "";
    }

    const { code, data } = rtcRes;
    if (code != 0) {
      throw new Error("Failed to get Agora token");
    }

    this.appId = data?.appId ?? "";
    this.token = data?.token ?? "";
    this.userId = userId;
  }

  attachNativeClient(client: IAgoraRTCClient, attachKey: string) {
    if (!client) {
      throw new Error("[rtc] Invalid native client");
    }

    if (this.client === client && this._attachKey === attachKey) {
      return;
    }

    this.client = client;
    this._attachKey = attachKey;
    this._listenRtcEvents();
    this._resolveNativeClientWaiters();
  }

  async waitForNativeClient(timeoutMs = 10000): Promise<IAgoraRTCClient> {
    if (this.client) {
      return this.client;
    }

    return new Promise((resolve, reject) => {
      const timeoutId = setTimeout(() => {
        this._nativeClientWaiters = this._nativeClientWaiters.filter(
          (waiter) => waiter.timeoutId !== timeoutId
        );
        reject(new Error("[rtc] Timeout waiting for native Agora client"));
      }, timeoutMs);

      this._nativeClientWaiters.push({ resolve, reject, timeoutId });
    });
  }

  detachNativeClient() {
    this._unlistenRtcEvents();
    this.client = null;
    this._attachKey = null;
    this._rejectNativeClientWaiters(new Error("[rtc] Native client detached"));
  }

  async createMicrophoneAudioTrack() {
    try {
      const AgoraRTC = await getAgoraRTC();
      const audioTrack = await AgoraRTC.createMicrophoneAudioTrack();
      this.localTracks.audioTrack = audioTrack;
    } catch (err) {
      console.error("Failed to create audio track", err);
    }
    this.emit("localTracksChanged", this.localTracks);
  }

  async publish() {
    const client = this.client;
    if (!client) {
      throw new Error("[rtc] Native client not attached");
    }

    const tracks = [];
    if (this.localTracks.audioTrack) {
      tracks.push(this.localTracks.audioTrack);
    }
    if (tracks.length) {
      await client.publish(tracks);
    }
  }

  async destroy() {
    this.localTracks?.audioTrack?.close();

    if (this.client) {
      try {
        await this.client.leave();
      } catch (error) {
        console.warn("[rtc] leave failed", error);
      }
    }

    this.detachNativeClient();
    this._resetData();
  }

  private _resolveNativeClientWaiters() {
    if (!this.client) {
      return;
    }

    for (const waiter of this._nativeClientWaiters) {
      clearTimeout(waiter.timeoutId);
      waiter.resolve(this.client);
    }
    this._nativeClientWaiters = [];
  }

  private _rejectNativeClientWaiters(error: Error) {
    for (const waiter of this._nativeClientWaiters) {
      clearTimeout(waiter.timeoutId);
      waiter.reject(error);
    }
    this._nativeClientWaiters = [];
  }

  private _onNetworkQuality = (quality: NetworkQuality) => {
    this.emit("networkQuality", quality);
  };

  private _onUserPublished = (user: any) => {
    this.emit("remoteUserChanged", {
      userId: user.uid,
      audioTrack: user.audioTrack,
      videoTrack: user.videoTrack,
    });
  };

  private _onUserUnpublished = (user: any) => {
    this.emit("remoteUserChanged", {
      userId: user.uid,
      audioTrack: user.audioTrack,
      videoTrack: user.videoTrack,
    });
  };

  private _onStreamMessage = (uid: UID, stream: any) => {
    this._parseData(stream);
  };

  private _listenRtcEvents() {
    if (!this.client) {
      return;
    }
    if (this._boundClient === this.client) {
      return;
    }

    this._unlistenRtcEvents();

    this.client.on("network-quality", this._onNetworkQuality);
    this.client.on("user-published", this._onUserPublished);
    this.client.on("user-unpublished", this._onUserUnpublished);
    // RTM is the only active server->client messaging transport.
    this._boundClient = this.client;
  }

  private _unlistenRtcEvents() {
    if (!this._boundClient) {
      return;
    }

    this._boundClient.off("network-quality", this._onNetworkQuality);
    this._boundClient.off("user-published", this._onUserPublished);
    this._boundClient.off("user-unpublished", this._onUserUnpublished);
    this._boundClient = null;
  }

  private _parseData(data: any): ITextItem | void {
    const ascii = String.fromCharCode(...new Uint8Array(data));

    console.log("[test] textstream raw data", ascii);

    this.handleChunk(ascii);
  }

  private messageCache: { [key: string]: TextDataChunk[] } = {};

  // Function to process received chunk via event emitter
  handleChunk(formattedChunk: string) {
    try {
      // Split the chunk by the delimiter "|"
      const [message_id, partIndexStr, totalPartsStr, content] =
        formattedChunk.split("|");

      const part_index = parseInt(partIndexStr, 10);
      const total_parts =
        totalPartsStr === "???" ? -1 : parseInt(totalPartsStr, 10); // -1 means total parts unknown

      // Ensure total_parts is known before processing further
      if (total_parts === -1) {
        console.warn(
          `Total parts for message ${message_id} unknown, waiting for further parts.`
        );
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
        const completeMessage = this.reconstructMessage(
          this.messageCache[message_id]
        );
        const { stream_id, is_final, text, text_ts, data_type, role } =
          JSON.parse(this.base64ToUtf8(completeMessage));
        console.log(
          `[test] message_id: ${message_id} stream_id: ${stream_id}, text: ${text}, data_type: ${data_type}`
        );
        const isAgent = role === "assistant";
        let textItem: IChatItem = {
          type: isAgent ? EMessageType.AGENT : EMessageType.USER,
          time: text_ts,
          text: text,
          data_type: EMessageDataType.TEXT,
          userId: stream_id,
          isFinal: is_final,
        };

        if (data_type === "raw") {
          const { data, type } = JSON.parse(text);
          if (type === "image_url") {
            textItem = {
              ...textItem,
              data_type: EMessageDataType.IMAGE,
              text: data.image_url,
            };
          } else if (type === "reasoning") {
            textItem = {
              ...textItem,
              data_type: EMessageDataType.REASON,
              text: data.text,
            };
          } else if (type === "action") {
            const action = data?.action;
            const actionData = data?.data ?? {};
            if (action && typeof action === "string") {
              this.emit("uiAction", {
                action,
                data: actionData,
              });
            }
            // Clean up the cache for action messages and skip chat rendering.
            delete this.messageCache[message_id];
            return;
          }
        }

        if (text.trim().length > 0) {
          this.emit("textChanged", textItem);
        }

        // Clean up the cache
        delete this.messageCache[message_id];
      }
    } catch (error) {
      console.error("Error processing chunk:", error);
    }
  }

  // Function to reconstruct the full message from chunks
  reconstructMessage(chunks: TextDataChunk[]): string {
    // Sort chunks by their part index
    chunks.sort((a, b) => a.part_index - b.part_index);

    // Concatenate all chunks to form the full message
    return chunks.map((chunk) => chunk.content).join("");
  }

  base64ToUtf8(base64: string): string {
    const binaryString = atob(base64); // Latin-1 binary string
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return new TextDecoder("utf-8").decode(bytes);
  }

  _playAudio(
    audioTrack: IMicrophoneAudioTrack | IRemoteAudioTrack | undefined
  ) {
    if (audioTrack && !audioTrack.isPlaying) {
      audioTrack.play();
    }
  }

  private _resetData() {
    this.localTracks = {};
    this.spatialwalkToken = null;
    this.appId = null;
    this.token = null;
    this.userId = null;
  }
}

export const rtcManager = new RtcManager();
